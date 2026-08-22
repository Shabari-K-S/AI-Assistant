"""Model Context Protocol (MCP) Client and Manager for A.T.H.E.N.A.

Connects to standard MCP servers over JSON-RPC 2.0 stdio, discovers dynamic tools,
and registers them directly into A.T.H.E.N.A.'s ToolRegistry for LLM function calling.
Provides cross-platform storage in ~/.athena/mcp_servers.json with dynamic online discovery,
doubt-clarification, live installation, and tool hot-reloading.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("ev.mcp")


# --------------------------------------------------------------------------- #
# Generic Cross-Platform Athena Home & Storage Resolution (~/.athena)
# --------------------------------------------------------------------------- #
def get_athena_home_dir() -> Path:
    """Return the cross-platform Athena home directory (~/.athena or $ATHENA_HOME).
    Works consistently across Linux, macOS, Windows, Termux/Android, and container environments.
    """
    custom = os.environ.get("ATHENA_HOME")
    if custom and custom.strip():
        p = Path(custom.strip()).expanduser().resolve()
    else:
        p = (Path.home() / ".athena").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_athena_mcp_dir() -> Path:
    """Return ~/.athena/mcp/ for dynamic or custom server scripts."""
    p = get_athena_home_dir() / "mcp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_athena_mcp_config_path() -> Path:
    """Return path to ~/.athena/mcp_servers.json.
    If not found in ~/.athena, checks for existing project backend/mcp_servers.json and
    migrates it seamlessly so configurations are preserved across platforms.
    """
    athena_home = get_athena_home_dir()
    target_config = athena_home / "mcp_servers.json"

    if not target_config.exists():
        # Check if project backend/mcp_servers.json exists to seed from
        backend_config = Path(__file__).resolve().parent / "mcp_servers.json"
        if backend_config.exists():
            try:
                shutil.copy2(backend_config, target_config)
                log.info("Migrated seed MCP config from %s to %s", backend_config, target_config)
            except Exception:
                log.exception("Failed migrating seed config to %s", target_config)
    return target_config


# --------------------------------------------------------------------------- #
# MCP Process Client (JSON-RPC 2.0 stdio)
# --------------------------------------------------------------------------- #
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

    def start(self, timeout: float = 6.0) -> bool:
        """Start the MCP server subprocess and perform protocol handshake."""
        full_env = os.environ.copy()
        backend_dir = Path(__file__).resolve().parent

        # Expand environment variables in custom env dictionary
        for k, v in self.custom_env.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                var_name = v[2:-1]
                full_env[k] = os.environ.get(var_name, "")
            else:
                full_env[k] = str(v)

        # Resolve command (e.g. .venv/bin/python3, python3, npx, uvx)
        exec_cmd = self.command
        cmd_p = Path(self.command)
        if not cmd_p.is_absolute():
            candidate = backend_dir / cmd_p
            if candidate.exists():
                exec_cmd = str(candidate)
            elif "python" in self.command and not shutil.which(self.command):
                exec_cmd = sys.executable or "python3"

        # Expand args if needed
        expanded_args = []
        for a in self.args:
            if isinstance(a, str) and a.startswith("${") and a.endswith("}"):
                expanded_args.append(os.environ.get(a[2:-1], ""))
            else:
                arg_str = str(a)
                if arg_str.endswith(".py") and not Path(arg_str).is_absolute() and (backend_dir / arg_str).exists():
                    expanded_args.append(str(backend_dir / arg_str))
                else:
                    expanded_args.append(arg_str)

        cmd = [exec_cmd] + expanded_args
        log.info("Starting MCP server %r: %s", self.name, " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(backend_dir),
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
                    "clientInfo": {"name": "athena-assistant", "version": "2.0.0"},
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

    def call_tool(self, tool_name: str, arguments: dict[str, Any], timeout: float = 45.0) -> str:
        """Execute a tool on this MCP server and return text content."""
        if any(w in tool_name.lower() for w in ("camera", "vision", "scan", "scrape", "search", "terminal", "install")):
            timeout = max(timeout, 60.0)

        res = self._send_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
            timeout=timeout,
        )
        if not res:
            return f"Error: MCP server {self.name!r} timed out or failed executing {tool_name!r}"

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
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    log.debug("MCP [%s] non-JSON stdout ignored: %s", self.name, line[:160])
                    continue

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


# --------------------------------------------------------------------------- #
# Curated Pre-Configured MCP Catalog
# --------------------------------------------------------------------------- #
CURATED_MCP_CATALOG: list[dict[str, Any]] = [
    {
        "id": "dummy-demo",
        "name": "Desktop Utilities & Weather",
        "description": "Real-time weather (default: Chennai, TN, India), math evaluator, dice roller, and unit converter.",
        "category": "utilities",
        "icon": "CloudSun",
        "command": ".venv/bin/python3",
        "args": ["dummy_mcp_server.py"],
        "env": {},
        "preinstalled": True,
    },
    {
        "id": "notes-memory",
        "name": "Personal Notes & Memory",
        "description": "Store thoughts, search notes, manage to-do checklists, and retain user memory across sessions.",
        "category": "productivity",
        "icon": "BookOpen",
        "command": ".venv/bin/python3",
        "args": ["notes_mcp_server.py"],
        "env": {},
        "preinstalled": True,
    },
    {
        "id": "opencode",
        "name": "OpenCode Workspace",
        "description": "Project navigation, file reading/writing, terminal execution, and VS Code integration.",
        "category": "developer",
        "icon": "Terminal",
        "command": ".venv/bin/python3",
        "args": ["opencode_mcp_server.py"],
        "env": {"WORKSPACE_ROOT": "/home/shabari/projects"},
        "preinstalled": True,
    },
    {
        "id": "duckduckgo-search",
        "name": "DuckDuckGo Web Search",
        "description": "Real-time web & news search via DuckDuckGo with ZERO API keys or registration required.",
        "category": "search",
        "icon": "Search",
        "command": ".venv/bin/python3",
        "args": ["duckduckgo_mcp_server.py"],
        "env": {},
        "preinstalled": True,
    },
    {
        "id": "web-scraper",
        "name": "Custom Web Scraper & Reader",
        "description": "Extract full text, articles, headers, and hyperlinks directly from websites without commercial APIs.",
        "category": "search",
        "icon": "Globe",
        "command": ".venv/bin/python3",
        "args": ["web_scraper_mcp_server.py"],
        "env": {},
        "preinstalled": True,
    },
    {
        "id": "security-audit",
        "name": "Security & Bug Bounty Auditor",
        "description": "Vulnerability scanning, offline CVE searchsploit lookups, passive subdomain recon, SAST code analysis, and HTTP header auditing.",
        "category": "developer",
        "icon": "ShieldCheck",
        "command": ".venv/bin/python3",
        "args": ["security_mcp_server.py"],
        "env": {
            "SECURITY_TARGET_ALLOWLIST": "localhost,127.0.0.1,::1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12"
        },
        "preinstalled": True,
    },
    {
        "id": "android-termux",
        "name": "Android Mobile Superpowers (Termux:API)",
        "description": "Hardware control, live battery status, torch, haptics, phone clipboard, notifications, camera vision, and GPS location.",
        "category": "utilities",
        "icon": "Smartphone",
        "command": ".venv/bin/python3",
        "args": ["termux_mcp_server.py"],
        "env": {},
        "preinstalled": True,
    },
    {
        "id": "robot-qa",
        "name": "Robot Framework QA Auto-Fix",
        "description": "Autonomous Robot Framework test suite execution, error diagnosis, and code-fixing engine.",
        "category": "developer",
        "icon": "Wrench",
        "command": ".venv/bin/python3",
        "args": ["robot_mcp_server.py"],
        "env": {"WORKSPACE_ROOT": "/home/shabari/projects/AI assistant"},
        "preinstalled": True,
    },
    {
        "id": "git-copilot",
        "name": "Autonomous Git Copilot",
        "description": "Git repository intelligence, commit staging, branch management, conflict review, and smart diff analysis.",
        "category": "developer",
        "icon": "GitBranch",
        "command": ".venv/bin/python3",
        "args": ["git_mcp_server.py"],
        "env": {"WORKSPACE_ROOT": "/home/shabari/projects/AI assistant"},
        "preinstalled": True,
    },
    {
        "id": "brave-search",
        "name": "Brave Web & Local Search",
        "description": "Brave Search official MCP server for web search, AI summaries, local business search, and real-time news.",
        "category": "search",
        "icon": "Search",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
        "required_env": ["BRAVE_API_KEY"],
        "preinstalled": False,
    },
    {
        "id": "sqlite",
        "name": "SQLite Database Explorer",
        "description": "Query, inspect tables, analyze schemas, and run SQL queries against local SQLite database files.",
        "category": "developer",
        "icon": "Terminal",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "/home/shabari/projects/data.db"],
        "env": {},
        "required_args": ["--db-path"],
        "preinstalled": False,
    },
    {
        "id": "filesystem",
        "name": "Local Filesystem Bridge",
        "description": "Secure, scoped read/write access to specific local directories and project roots.",
        "category": "developer",
        "icon": "Terminal",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/shabari/projects"],
        "env": {},
        "required_args": ["<directory_path>"],
        "preinstalled": False,
    },
    {
        "id": "puppeteer",
        "name": "Puppeteer Headless Browser",
        "description": "Automate headless Chromium browser to navigate pages, capture screenshots, and scrape dynamic JS content.",
        "category": "search",
        "icon": "Compass",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        "env": {},
        "preinstalled": False,
    },
    {
        "id": "github",
        "name": "GitHub Assistant",
        "description": "Browse repositories, inspect pull requests, read commits, create issues, and search code.",
        "category": "developer",
        "icon": "GitBranch",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
        "required_env": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        "preinstalled": False,
    },
    {
        "id": "postgres",
        "name": "PostgreSQL Database Bridge",
        "description": "Read-only inspection, schema discovery, and query execution for PostgreSQL databases.",
        "category": "developer",
        "icon": "Terminal",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"],
        "env": {},
        "required_args": ["<postgres_connection_url>"],
        "preinstalled": False,
    },
    {
        "id": "fetch",
        "name": "Fetch & Markdown Converter",
        "description": "Fetch web pages and convert HTML into clean, LLM-optimized Markdown text.",
        "category": "search",
        "icon": "Globe",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],
        "env": {},
        "preinstalled": False,
    },
    {
        "id": "slack",
        "name": "Slack Integration",
        "description": "Interact with Slack channels, post messages, and read thread history.",
        "category": "productivity",
        "icon": "Smartphone",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env": {"SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}", "SLACK_TEAM_ID": "${SLACK_TEAM_ID}"},
        "required_env": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
        "preinstalled": False,
    },
]


# --------------------------------------------------------------------------- #
# Autonomous Online Discovery Engine for MCP Ecosystem
# --------------------------------------------------------------------------- #
def discover_mcp(query: str) -> dict[str, Any]:
    """Search the internet (NPM Registry, PyPI, and DuckDuckGo) for Model Context Protocol servers.

    Returns structured findings including package names, default commands,
    required/detected environment variables, and any missing clarification needed from the operator.
    """
    clean_q = query.strip()
    if not clean_q:
        return {"ok": False, "error": "Search query cannot be empty"}

    q_lower = clean_q.lower()

    # 1. Match against Curated Catalog first
    for item in CURATED_MCP_CATALOG:
        if (
            q_lower == item["id"].lower()
            or q_lower in item["name"].lower()
            or q_lower in item["description"].lower()
            or (item["id"].replace("-", " ") in q_lower)
            or (item.get("args") and any(q_lower in str(a).lower() for a in item["args"]))
        ):
            required_env = item.get("required_env", [])
            required_args = item.get("required_args", [])
            clarification_needed = bool(required_env or required_args)
            prompt = ""
            if required_env:
                prompt += f"To configure '{item['name']}', I need the environment variable(s): {', '.join(required_env)}."
            if required_args:
                prompt += f" It also requires argument parameter(s): {', '.join(required_args)}."

            return {
                "ok": True,
                "source": "curated_catalog",
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "command": item["command"],
                "args": item["args"],
                "env": item.get("env", {}),
                "required_env": required_env,
                "required_args": required_args,
                "clarification_needed": clarification_needed,
                "clarification_prompt": prompt.strip(),
                "preinstalled": item.get("preinstalled", False),
            }

    # 2. Query NPM Registry API
    npm_results: list[dict[str, Any]] = []
    try:
        import httpx

        search_terms = f"mcp server {clean_q}"
        url = f"https://registry.npmjs.org/-/v1/search?text={httpx.URL('', params={'q': search_terms}).params.get('q')}&size=6"
        res = httpx.get(url, timeout=5.0)
        if res.status_code == 200:
            data = res.json()
            for obj in data.get("objects", []):
                pkg = obj.get("package", {})
                pkg_name = pkg.get("name", "")
                if not pkg_name:
                    continue
                desc = pkg.get("description", "")
                keywords = pkg.get("keywords", [])
                links = pkg.get("links", {})

                # Check if it's an MCP server package
                is_mcp = (
                    "modelcontextprotocol" in pkg_name
                    or "mcp" in pkg_name.lower()
                    or "mcp" in " ".join(keywords).lower()
                    or "model context protocol" in desc.lower()
                )
                if is_mcp:
                    npm_results.append({
                        "name": pkg_name,
                        "description": desc,
                        "version": pkg.get("version", "latest"),
                        "links": links,
                    })
    except Exception as exc:
        log.warning("NPM search query failed: %s", exc)

    # 3. Analyze best matching package
    if npm_results:
        best = npm_results[0]
        pkg_name = best["name"]
        desc = best["description"]

        # Infer required environment variables via common patterns in description/name
        detected_env: list[str] = []
        env_pattern = re.compile(r"\b([A-Z0-9_]{3,}(?:_API_KEY|_TOKEN|_SECRET|_URL|_KEY|_PASSWORD|_AUTH))\b")
        for match in env_pattern.finditer(desc + " " + pkg_name):
            val = match.group(1)
            if val not in detected_env:
                detected_env.append(val)

        # Common package-specific defaults
        if "brave" in pkg_name.lower() and "BRAVE_API_KEY" not in detected_env:
            detected_env.append("BRAVE_API_KEY")
        elif "github" in pkg_name.lower() and "GITHUB_PERSONAL_ACCESS_TOKEN" not in detected_env:
            detected_env.append("GITHUB_PERSONAL_ACCESS_TOKEN")
        elif "slack" in pkg_name.lower() and "SLACK_BOT_TOKEN" not in detected_env:
            detected_env.append("SLACK_BOT_TOKEN")
        elif "sentry" in pkg_name.lower() and "SENTRY_AUTH_TOKEN" not in detected_env:
            detected_env.append("SENTRY_AUTH_TOKEN")
        elif "tavily" in pkg_name.lower() and "TAVILY_API_KEY" not in detected_env:
            detected_env.append("TAVILY_API_KEY")
        elif "firecrawl" in pkg_name.lower() and "FIRECRAWL_API_KEY" not in detected_env:
            detected_env.append("FIRECRAWL_API_KEY")

        # Generate a clean ID slug
        server_id = pkg_name.split("/")[-1].replace("server-", "").replace("-mcp", "").replace("mcp-", "")

        env_dict = {k: f"${{{k}}}" for k in detected_env}
        clarification_needed = len(detected_env) > 0
        prompt = ""
        if clarification_needed:
            prompt = (
                f"I found the package '{pkg_name}' for '{clean_q}'. "
                f"It appears to require the environment credential(s): {', '.join(detected_env)}. "
                f"Would you like to provide the key(s) now, or should I install it in standby mode?"
            )

        return {
            "ok": True,
            "source": "npm_registry",
            "id": server_id,
            "name": f"{server_id.capitalize()} MCP Server",
            "package": pkg_name,
            "description": desc or f"MCP server from {pkg_name}",
            "command": "npx",
            "args": ["-y", pkg_name],
            "env": env_dict,
            "required_env": detected_env,
            "required_args": [],
            "clarification_needed": clarification_needed,
            "clarification_prompt": prompt,
            "candidates": npm_results[:4],
        }

    # 4. Fallback search via DuckDuckGo
    try:
        from duckduckgo_mcp_server import perform_ddg_search

        ddg_res = perform_ddg_search(f"mcp server modelcontextprotocol {clean_q}", max_results=3)
        if ddg_res and not ddg_res.startswith("Error"):
            return {
                "ok": True,
                "source": "web_search",
                "id": clean_q.replace(" ", "-").lower(),
                "name": f"{clean_q.capitalize()} MCP Server",
                "description": f"Discovered via web search for '{clean_q}'.",
                "command": "npx",
                "args": ["-y", f"@modelcontextprotocol/server-{clean_q.replace(' ', '-').lower()}"],
                "env": {},
                "required_env": [],
                "required_args": [],
                "clarification_needed": True,
                "clarification_prompt": (
                    f"I found information online regarding {clean_q} MCP. "
                    f"Please confirm if you want me to install '@modelcontextprotocol/server-{clean_q.replace(' ', '-').lower()}' "
                    f"or specify a custom package name/script path."
                ),
                "web_summary": ddg_res[:400],
            }
    except Exception as exc:
        log.warning("DDG fallback search failed: %s", exc)

    return {
        "ok": False,
        "error": f"No MCP server package found for query: '{clean_q}'. You can specify a custom command (e.g. 'npx <pkg>' or '.venv/bin/python3 <script.py>').",
    }


# --------------------------------------------------------------------------- #
# MCP Manager (Dynamic Integration & Hot-Reloading)
# --------------------------------------------------------------------------- #
class MCPManager:
    """Loads MCP servers from ~/.athena/mcp_servers.json and integrates tools dynamically into A.T.H.E.N.A.'s ToolRegistry."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            config_path = get_athena_mcp_config_path()
        self.config_path = Path(config_path)
        self.clients: dict[str, MCPProcessClient] = {}
        self.registry: Any = None
        self._lock = threading.Lock()
        atexit.register(self.close)

    def set_registry(self, registry: Any) -> None:
        """Attach active ToolRegistry for dynamic tool registration/unregistration."""
        self.registry = registry

    def ensure_default_config(self) -> None:
        """Create a default mcp_servers.json in ~/.athena/ if it doesn't already exist."""
        if not self.config_path.exists():
            default_config = {
                "mcpServers": {
                    "dummy-demo": {
                        "command": ".venv/bin/python3",
                        "args": ["dummy_mcp_server.py"],
                        "env": {},
                        "enabled": True,
                    },
                    "notes-memory": {
                        "command": ".venv/bin/python3",
                        "args": ["notes_mcp_server.py"],
                        "env": {},
                        "enabled": True,
                    },
                    "opencode": {
                        "command": ".venv/bin/python3",
                        "args": ["opencode_mcp_server.py"],
                        "env": {
                            "WORKSPACE_ROOT": "/home/shabari/projects"
                        },
                        "enabled": True,
                    },
                }
            }
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2)
                log.info("Created default MCP config at %s", self.config_path)
            except Exception:
                log.exception("Failed to create default MCP config")

    def _read_config(self) -> dict[str, Any]:
        self.ensure_default_config()
        try:
            with open(self.config_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            log.exception("Failed to read MCP config %s", self.config_path)
            return {"mcpServers": {}}

    def _write_config(self, data: dict[str, Any]) -> bool:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            log.exception("Failed to write MCP config %s", self.config_path)
            return False

    def start_servers(self) -> None:
        """Read config file and launch all enabled MCP servers."""
        with self._lock:
            data = self._read_config()
            servers = data.get("mcpServers", {})
            for name, spec in servers.items():
                enabled = spec.get("enabled", True)
                if not enabled:
                    log.info("MCP server %r is disabled in config — skipping", name)
                    continue

                cmd = spec.get("command")
                if not cmd:
                    continue
                args = spec.get("args", [])
                env = spec.get("env", {})
                client = MCPProcessClient(name, cmd, args, env)
                if client.start(timeout=6.0):
                    self.clients[name] = client

    def register_into_tool_registry(self, registry: Any | None = None) -> int:
        """Register all discovered MCP tools into A.T.H.E.N.A.'s ToolRegistry."""
        if registry is not None:
            self.registry = registry
        if self.registry is None:
            return 0

        total_registered = 0
        with self._lock:
            for srv_name in list(self.clients.keys()):
                total_registered += self._register_client_tools(srv_name)

        log.info("Total MCP tools registered in registry: %d", total_registered)
        return total_registered

    def _register_client_tools(self, srv_name: str) -> int:
        """Register tools for a single active client into ToolRegistry."""
        if not self.registry:
            return 0
        from tools import Tool

        client = self.clients.get(srv_name)
        if not client or not client.tools:
            return 0

        # Unregister previous tools for this server first to prevent duplicates
        if hasattr(self.registry, "unregister_server_tools"):
            self.registry.unregister_server_tools(srv_name)

        registered = 0
        for tool_spec in client.tools:
            tool_name = tool_spec.get("name")
            if not tool_name:
                continue
            desc = tool_spec.get("description", f"MCP tool {tool_name}")
            schema = tool_spec.get("inputSchema", {"type": "object", "properties": {}})

            def make_handler(c: MCPProcessClient, t_name: str, server: str) -> Callable[[dict], str]:
                def handler(args: dict) -> str:
                    if "terminal" in t_name.lower() or "shell" in t_name.lower():
                        from tools import is_safe_read_only_command
                        cmd = str(args.get("command", "")).strip()
                        if not is_safe_read_only_command(cmd):
                            if hasattr(self.registry, "_cfg") and hasattr(self.registry, "_confirm"):
                                policy = getattr(self.registry._cfg, "confirm_shell", "ask")
                                if policy == "always" or policy == "ask":
                                    if not self.registry._confirm(f"run MCP [{server}] command: {cmd!r}"):
                                        raise PermissionError(f"declined by user: {cmd!r}")
                    return c.call_tool(t_name, args)
                return handler

            t = Tool(
                name=tool_name,
                description=f"[MCP: {srv_name}] {desc}",
                parameters=schema,
                handler=make_handler(client, tool_name, srv_name),
            )
            self.registry.register(t)
            registered += 1

        return registered

    def toggle_server(self, name: str, enabled: bool) -> dict[str, Any]:
        """Dynamically enable or disable an MCP server, updating processes, registry and config."""
        with self._lock:
            data = self._read_config()
            servers = data.get("mcpServers", {})
            if name not in servers:
                return {"ok": False, "error": f"Server {name!r} not found in configuration."}

            servers[name]["enabled"] = bool(enabled)
            self._write_config(data)

            if enabled:
                # Start if not already running
                if name in self.clients:
                    self.clients[name].close()
                    del self.clients[name]

                spec = servers[name]
                cmd = spec.get("command")
                args = spec.get("args", [])
                env = spec.get("env", {})
                client = MCPProcessClient(name, cmd, args, env)
                started = client.start(timeout=6.0)
                if started:
                    self.clients[name] = client
                    tools_count = self._register_client_tools(name)
                    log.info("Enabled and started MCP server %r with %d tools", name, tools_count)
                    return {
                        "ok": True,
                        "name": name,
                        "enabled": True,
                        "running": True,
                        "tools_count": tools_count,
                        "tools": client.tools,
                    }
                else:
                    log.warning("Failed starting MCP server %r on enable", name)
                    return {"ok": False, "error": f"Failed to start server {name!r}"}
            else:
                # Stop and unregister tools
                if name in self.clients:
                    self.clients[name].close()
                    del self.clients[name]
                if self.registry and hasattr(self.registry, "unregister_server_tools"):
                    self.registry.unregister_server_tools(name)
                log.info("Disabled MCP server %r and unregistered its tools", name)
                return {"ok": True, "name": name, "enabled": False, "running": False, "tools_count": 0}

    def restart_server(self, name: str) -> dict[str, Any]:
        """Restart an active or enabled MCP server."""
        with self._lock:
            data = self._read_config()
            servers = data.get("mcpServers", {})
            if name not in servers:
                return {"ok": False, "error": f"Server {name!r} not found"}

            if name in self.clients:
                self.clients[name].close()
                del self.clients[name]
            if self.registry and hasattr(self.registry, "unregister_server_tools"):
                self.registry.unregister_server_tools(name)

            spec = servers[name]
            cmd = spec.get("command")
            args = spec.get("args", [])
            env = spec.get("env", {})
            client = MCPProcessClient(name, cmd, args, env)
            if client.start(timeout=6.0):
                self.clients[name] = client
                tools_count = self._register_client_tools(name)
                return {
                    "ok": True,
                    "name": name,
                    "running": True,
                    "tools_count": tools_count,
                    "tools": client.tools,
                }
            return {"ok": False, "error": f"Failed to restart {name!r}"}

    def save_server(self, name: str, spec: dict[str, Any]) -> dict[str, Any]:
        """Add or update an MCP server configuration in ~/.athena/mcp_servers.json and hot-load it."""
        name = name.strip()
        if not name:
            return {"ok": False, "error": "Server name cannot be empty"}

        with self._lock:
            data = self._read_config()
            servers = data.setdefault("mcpServers", {})
            enabled = spec.get("enabled", True)
            servers[name] = {
                "command": spec.get("command", ""),
                "args": spec.get("args", []),
                "env": spec.get("env", {}),
                "enabled": enabled,
            }
            self._write_config(data)

        # Apply toggle/start if enabled
        if enabled:
            return self.toggle_server(name, True)
        else:
            return self.toggle_server(name, False)

    def install_and_hotload(self, name: str, spec: dict[str, Any]) -> dict[str, Any]:
        """Convenience alias for saving, starting, and hotloading an MCP server."""
        return self.save_server(name, spec)

    def update_server(self, name: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update an existing MCP server's command, args, or environment variables and hot-reload tools."""
        name = name.strip()
        data = self._read_config()
        servers = data.get("mcpServers", {})
        if name not in servers:
            return {"ok": False, "error": f"Server {name!r} does not exist"}

        current_spec = servers[name]
        if "command" in updates and updates["command"]:
            current_spec["command"] = updates["command"]
        if "args" in updates and updates["args"] is not None:
            current_spec["args"] = updates["args"]
        if "env" in updates and isinstance(updates["env"], dict):
            current_spec.setdefault("env", {}).update(updates["env"])
        if "enabled" in updates:
            current_spec["enabled"] = bool(updates["enabled"])

        return self.save_server(name, current_spec)

    def delete_server(self, name: str) -> dict[str, Any]:
        """Delete an MCP server from configuration and terminate it."""
        with self._lock:
            data = self._read_config()
            servers = data.get("mcpServers", {})
            if name in servers:
                del servers[name]
                self._write_config(data)

            if name in self.clients:
                self.clients[name].close()
                del self.clients[name]
            if self.registry and hasattr(self.registry, "unregister_server_tools"):
                self.registry.unregister_server_tools(name)

        log.info("Deleted MCP server %r", name)
        return {"ok": True, "name": name}

    def get_all_status(self) -> dict[str, Any]:
        """Return comprehensive live status of all configured MCP servers, active tools, and catalog presets."""
        data = self._read_config()
        configured = data.get("mcpServers", {})

        server_list = []
        for name, spec in configured.items():
            enabled = spec.get("enabled", True)
            client = self.clients.get(name)
            is_running = client is not None and client._running and (client._proc and client._proc.poll() is None)
            tools = client.tools if (client and is_running) else []
            server_info = client.server_info if (client and is_running) else {}

            server_list.append({
                "name": name,
                "command": spec.get("command", ""),
                "args": spec.get("args", []),
                "env": spec.get("env", {}),
                "enabled": enabled,
                "running": is_running,
                "tools_count": len(tools),
                "tools": tools,
                "server_info": server_info,
            })

        return {
            "ok": True,
            "config_path": str(self.config_path),
            "athena_home": str(get_athena_home_dir()),
            "servers": server_list,
            "catalog": CURATED_MCP_CATALOG,
            "total_tools": sum(s["tools_count"] for s in server_list),
            "active_servers": sum(1 for s in server_list if s["running"]),
        }

    def list_active_tools(self) -> list[dict[str, Any]]:
        """Return a flat list of all active MCP tools and their descriptions."""
        result = []
        with self._lock:
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
        with self._lock:
            for client in self.clients.values():
                client.close()
            self.clients.clear()
