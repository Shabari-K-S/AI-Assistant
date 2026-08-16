"""Model Context Protocol (MCP) Client and Manager for S.A.R.A.

Connects to standard MCP servers over JSON-RPC 2.0 stdio, discovers dynamic tools,
and registers them directly into S.A.R.A.'s ToolRegistry for LLM function calling.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("ev.mcp")


class MCPProcessClient:
    """Manages an active stdio connection to a single MCP server."""

    def __init__(self, name: str, command: str, args: list[str] | None = None, env: dict[str, str] | None = None) -> None:
        self.name = name
        self.command = command
        self.args = args or []
        self.custom_env = env or {}
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._req_counter = 0
        self._pending_requests: dict[int, tuple[threading.Event, dict[str, Any]]] = {}
        self._running = False
        self._reader_thread: threading.Thread | None = None
        self.server_info: dict[str, Any] = {}
        self.tools: list[dict[str, Any]] = []

    def start(self, timeout: float = 5.0) -> bool:
        """Start the MCP server subprocess and perform protocol handshake."""
        full_env = os.environ.copy()
        
        # Expand environment variables in custom env dictionary
        for k, v in self.custom_env.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                var_name = v[2:-1]
                full_env[k] = os.environ.get(var_name, "")
            else:
                full_env[k] = str(v)

        # Expand args if needed
        expanded_args = []
        for a in self.args:
            if isinstance(a, str) and a.startswith("${") and a.endswith("}"):
                expanded_args.append(os.environ.get(a[2:-1], ""))
            else:
                expanded_args.append(str(a))

        cmd = [self.command] + expanded_args
        log.info("Starting MCP server %r: %s", self.name, " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=full_env,
            )
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_stdout_loop, daemon=True)
            self._reader_thread.start()

            # Start stderr logger thread
            threading.Thread(target=self._read_stderr_loop, daemon=True).start()

            # 1. Send initialize
            init_res = self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "sara-assistant", "version": "2.0.0"},
                },
                timeout=timeout,
            )
            if not init_res or init_res.get("isError"):
                log.warning("MCP server %r failed initialize handshake", self.name)
                self.close()
                return False

            self.server_info = init_res.get("serverInfo", {})
            log.info("MCP server %r connected: %s", self.name, self.server_info)

            # 2. Send initialized notification
            self._send_notification("notifications/initialized", {})

            # 3. List tools
            list_res = self._send_request("tools/list", {}, timeout=timeout)
            if list_res and not list_res.get("isError") and "tools" in list_res:
                self.tools = list_res["tools"]
                log.info("MCP server %r registered %d tools: %s", self.name, len(self.tools), [t["name"] for t in self.tools])
            return True
        except Exception:
            log.exception("Failed to start MCP server %r", self.name)
            self.close()
            return False

    def call_tool(self, tool_name: str, arguments: dict[str, Any], timeout: float = 15.0) -> str:
        """Execute a tool on this MCP server and return text content."""
        res = self._send_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
            timeout=timeout,
        )
        if not res:
            return f"Error: MCP server {self.name!r} timed out or failed executing {tool_name!r}"

        # Parse MCP CallToolResult format
        content = res.get("content", [])
        is_error = res.get("isError", False)

        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))

        result_text = "\n".join(parts) if parts else str(res)
        if is_error:
            return f"MCP Tool Error: {result_text}"
        return result_text

    def _send_request(self, method: str, params: dict[str, Any], timeout: float = 10.0) -> dict[str, Any] | None:
        if not self._proc or self._proc.poll() is not None or not self._running:
            return None

        event = threading.Event()
        result_holder: dict[str, Any] = {}

        with self._lock:
            self._req_counter += 1
            req_id = self._req_counter
            self._pending_requests[req_id] = (event, result_holder)

        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        try:
            assert self._proc.stdin is not None
            self._proc.stdin.write(json.dumps(msg) + "\n")
            self._proc.stdin.flush()
        except Exception:
            log.exception("Failed writing to MCP server %r stdin", self.name)
            with self._lock:
                self._pending_requests.pop(req_id, None)
            return None

        if event.wait(timeout=timeout):
            return result_holder.get("result")
        else:
            log.warning("MCP request %d (%s) to %r timed out after %ss", req_id, method, self.name, timeout)
            with self._lock:
                self._pending_requests.pop(req_id, None)
            return None

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        if not self._proc or self._proc.poll() is not None or not self._running:
            return
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        try:
            assert self._proc.stdin is not None
            self._proc.stdin.write(json.dumps(msg) + "\n")
            self._proc.stdin.flush()
        except Exception:
            log.exception("Failed writing notification to MCP server %r", self.name)

    def _read_stdout_loop(self) -> None:
        while self._running and self._proc and self._proc.poll() is None:
            try:
                line = self._proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                req_id = data.get("id")
                if req_id is not None:
                    with self._lock:
                        pending = self._pending_requests.pop(req_id, None)
                    if pending:
                        ev, holder = pending
                        if "result" in data:
                            holder["result"] = data["result"]
                        elif "error" in data:
                            holder["result"] = {"isError": True, "content": [{"type": "text", "text": str(data["error"])}]}
                        ev.set()
            except Exception:
                if self._running:
                    log.exception("Error in MCP reader loop for %r", self.name)
                break

    def _read_stderr_loop(self) -> None:
        while self._running and self._proc and self._proc.poll() is None:
            try:
                line = self._proc.stderr.readline()
                if not line:
                    break
                log.debug("[MCP %s stderr] %s", self.name, line.strip())
            except Exception:
                break

    def close(self) -> None:
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None


class MCPManager:
    """Loads MCP servers from config and integrates tools into S.A.R.A.'s ToolRegistry."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            config_path = Path(__file__).resolve().parent / "mcp_servers.json"
        self.config_path = Path(config_path)
        self.clients: dict[str, MCPProcessClient] = {}
        atexit.register(self.close)

    def ensure_default_config(self) -> None:
        """Create a default mcp_servers.json if it doesn't already exist."""
        if not self.config_path.exists():
            default_config = {
                "mcpServers": {
                    "dummy-demo": {
                        "command": ".venv/bin/python3",
                        "args": ["dummy_mcp_server.py"],
                        "env": {},
                    }
                }
            }
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2)
                log.info("Created default MCP config at %s", self.config_path)
            except Exception:
                log.exception("Failed to create default MCP config")

    def start_servers(self) -> None:
        """Read config file and launch all configured MCP servers."""
        self.ensure_default_config()
        if not self.config_path.exists():
            log.warning("No MCP configuration file found at %s", self.config_path)
            return

        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            log.exception("Failed to parse MCP config %s", self.config_path)
            return

        servers = data.get("mcpServers", {})
        for name, spec in servers.items():
            cmd = spec.get("command")
            if not cmd:
                continue
            args = spec.get("args", [])
            env = spec.get("env", {})
            client = MCPProcessClient(name, cmd, args, env)
            if client.start(timeout=6.0):
                self.clients[name] = client

    def register_into_tool_registry(self, registry: Any) -> int:
        """Register all discovered MCP tools into S.A.R.A.'s ToolRegistry.
        
        Returns the number of registered MCP tools.
        """
        from tools import Tool

        total_registered = 0
        for srv_name, client in self.clients.items():
            for tool_spec in client.tools:
                tool_name = tool_spec.get("name")
                desc = tool_spec.get("description", f"MCP tool {tool_name}")
                schema = tool_spec.get("inputSchema", {"type": "object", "properties": {}})

                # Create a closure handler with confirmation policy enforcement
                def make_handler(c: MCPProcessClient, t_name: str, server: str) -> Callable[[dict], str]:
                    def handler(args: dict) -> str:
                        # If tool involves running terminal commands, respect registry confirmation policy
                        if "terminal" in t_name.lower() or "shell" in t_name.lower():
                            if hasattr(registry, "_cfg") and hasattr(registry, "_confirm"):
                                policy = getattr(registry._cfg, "confirm_shell", "ask")
                                cmd = str(args.get("command", "")).strip()
                                if policy == "always" or policy == "ask":
                                    if not registry._confirm(f"run MCP [{server}] command: {cmd!r}"):
                                        raise PermissionError(f"declined by user: {cmd!r}")
                        return c.call_tool(t_name, args)
                    return handler

                t = Tool(
                    name=tool_name,
                    description=f"[MCP: {srv_name}] {desc}",
                    parameters=schema,
                    handler=make_handler(client, tool_name, srv_name),
                )
                registry.register(t)
                total_registered += 1

        log.info("Total MCP tools registered in registry: %d", total_registered)
        return total_registered

    def list_active_tools(self) -> list[dict[str, Any]]:
        """Return a flat list of all active MCP tools and their descriptions."""
        result = []
        for srv_name, client in self.clients.items():
            for t in client.tools:
                result.append({
                    "server": srv_name,
                    "name": t.get("name"),
                    "description": t.get("description"),
                    "parameters": t.get("inputSchema"),
                })
        return result

    def close(self) -> None:
        """Close all MCP server processes."""
        for client in self.clients.values():
            client.close()
        self.clients.clear()
