#!/usr/bin/env python3
"""OpenCode MCP Server (Model Context Protocol JSON-RPC 2.0 stdio).

Provides S.A.R.A. with full autonomous coding & terminal control:
- opencode_run_terminal: Run bash/cmd commands in project directories
- opencode_open_in_editor: Open VS Code / IDE on files or directories
- opencode_read_code: Read source code with line ranges
- opencode_write_code: Write or update source code files
- opencode_search_code: Fast search across workspace codebase
- opencode_list_files: Browse project directory structure
- opencode_git_summary: Git status, branch, and diff summary
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/home/shabari/projects")).resolve()


def _resolve_safe_path(target_path: str) -> Path:
    """Resolve and validate that the path is strictly within the allowed workspace."""
    p = Path(target_path).expanduser()
    if not p.is_absolute():
        p = WORKSPACE_ROOT / p
    p = p.resolve()
    if not (p == WORKSPACE_ROOT or p.is_relative_to(WORKSPACE_ROOT)):
        raise PermissionError(
            f"Access denied: path '{target_path}' resolves outside allowed workspace '{WORKSPACE_ROOT}'"
        )
    return p


def tool_opencode_run_terminal(args: dict[str, Any]) -> str:
    """Run a terminal / shell command in the project workspace."""
    command = str(args.get("command", "")).strip()
    if not command:
        return "Error: command is required."

    cwd_str = str(args.get("cwd", "")).strip()
    cwd = _resolve_safe_path(cwd_str) if cwd_str else WORKSPACE_ROOT
    if not cwd.exists():
        cwd = WORKSPACE_ROOT

    timeout = int(args.get("timeout_seconds", 30))

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        code = proc.returncode

        out = []
        out.append(f"Exit code: {code}")
        if stdout:
            if len(stdout) > 2500:
                stdout = stdout[:2500] + f"\n... [truncated, {len(proc.stdout)} bytes total]"
            out.append(f"STDOUT:\n{stdout}")
        if stderr:
            if len(stderr) > 1000:
                stderr = stderr[:1000] + f"\n... [truncated, {len(proc.stderr)} bytes total]"
            out.append(f"STDERR:\n{stderr}")
        if not stdout and not stderr:
            out.append("(No output)")
        return "\n".join(out)
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as exc:
        return f"Error executing terminal command: {exc}"


def tool_opencode_open_in_editor(args: dict[str, Any]) -> str:
    """Open a file or project folder in VS Code / default editor."""
    target_path = str(args.get("path", "")).strip()
    line_number = args.get("line")

    p = _resolve_safe_path(target_path) if target_path else WORKSPACE_ROOT

    editor = shutil.which("code") or shutil.which("cursor") or shutil.which("code-insiders")
    if not editor:
        # Fallback to xdg-open if gui editor binary not in path
        editor = shutil.which("xdg-open")

    if not editor:
        return f"Could not find VS Code or default editor in PATH to open {p}"

    cmd = [editor]
    if line_number and editor.endswith("code"):
        cmd.extend(["--goto", f"{p}:{line_number}"])
    else:
        cmd.append(str(p))

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return f"Successfully opened {p} in editor ({os.path.basename(editor)})."
    except Exception as exc:
        return f"Error launching editor: {exc}"


def tool_opencode_read_code(args: dict[str, Any]) -> str:
    """Read contents of a source code file with optional line range."""
    file_path = str(args.get("file_path", "")).strip()
    if not file_path:
        return "Error: file_path is required."

    p = _resolve_safe_path(file_path)
    if not p.exists():
        return f"Error: file not found: {p}"
    if not p.is_file():
        return f"Error: not a file: {p}"

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        total_lines = len(lines)

        start = int(args.get("start_line", 1))
        end = int(args.get("end_line", min(total_lines, start + 100)))

        start = max(1, min(start, total_lines))
        end = max(start, min(end, total_lines))

        selected = lines[start - 1 : end]
        numbered = [f"{i:4d} | {line}" for i, line in enumerate(selected, start=start)]

        header = f"=== {p.name} (Lines {start}-{end} of {total_lines}) ===\n"
        return header + "\n".join(numbered)
    except Exception as exc:
        return f"Error reading file {p}: {exc}"


def tool_opencode_write_code(args: dict[str, Any]) -> str:
    """Write or overwrite a file in the workspace."""
    file_path = str(args.get("file_path", "")).strip()
    content = args.get("content", "")
    if not file_path:
        return "Error: file_path is required."

    p = _resolve_safe_path(file_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {p}"
    except Exception as exc:
        return f"Error writing file {p}: {exc}"


def tool_opencode_search_code(args: dict[str, Any]) -> str:
    """Search for text or regular expressions across code files in workspace."""
    query = str(args.get("query", "")).strip()
    if not query:
        return "Error: query is required."

    sub_dir = str(args.get("directory", "")).strip()
    search_root = _resolve_safe_path(sub_dir) if sub_dir else WORKSPACE_ROOT
    if not search_root.exists():
        search_root = WORKSPACE_ROOT

    # Use ripgrep if available, else git grep, else python walk
    rg = shutil.which("rg")
    if rg:
        try:
            res = subprocess.run(
                [rg, "-n", "--max-count", "20", "--ignore-case", query, str(search_root)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = res.stdout.strip()
            return output if output else f"No matches found for {query!r} in {search_root}"
        except Exception:
            pass

    # Fallback Python search
    matches = []
    ignore_dirs = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", ".next"}
    for root, dirs, files in os.walk(search_root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            fp = Path(root) / f
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
                for idx, line in enumerate(text.splitlines(), start=1):
                    if query.lower() in line.lower():
                        rel = fp.relative_to(search_root)
                        matches.append(f"{rel}:{idx}: {line.strip()}")
                        if len(matches) >= 30:
                            return "\n".join(matches) + "\n... [capped at 30 matches]"
            except Exception:
                continue

    return "\n".join(matches) if matches else f"No matches found for {query!r} in {search_root}"


def tool_opencode_list_files(args: dict[str, Any]) -> str:
    """List files and subdirectories in a workspace path."""
    sub_dir = str(args.get("directory", "")).strip()
    target = _resolve_safe_path(sub_dir) if sub_dir else WORKSPACE_ROOT
    if not target.exists():
        return f"Error: directory does not exist: {target}"

    ignore = {".git", "node_modules", ".venv", "__pycache__", ".next", "dist"}
    items = []
    try:
        for entry in sorted(target.iterdir()):
            if entry.name in ignore:
                continue
            kind = "DIR " if entry.is_dir() else "FILE"
            items.append(f"[{kind}] {entry.name}")
        return f"Directory: {target}\n" + "\n".join(items)
    except Exception as exc:
        return f"Error listing directory: {exc}"


def tool_opencode_git_summary(args: dict[str, Any]) -> str:
    """Get git branch, modified files, and recent commit history."""
    sub_dir = str(args.get("directory", "")).strip()
    target = _resolve_safe_path(sub_dir) if sub_dir else WORKSPACE_ROOT

    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(target),
            capture_output=True,
            text=True,
        ).stdout.strip()

        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(target),
            capture_output=True,
            text=True,
        ).stdout.strip()

        log = subprocess.run(
            ["git", "log", "-n", "3", "--oneline"],
            cwd=str(target),
            capture_output=True,
            text=True,
        ).stdout.strip()

        out = [f"Git Repository: {target}"]
        out.append(f"Active Branch: {branch or 'unknown'}")
        out.append(f"\nModified Files:\n{status if status else 'Working tree clean'}")
        out.append(f"\nRecent Commits:\n{log if log else 'No commits'}")
        return "\n".join(out)
    except Exception as exc:
        return f"Error retrieving git summary: {exc}"


TOOLS_CATALOG = [
    {
        "name": "opencode_run_terminal",
        "description": "Run terminal / shell / cmd commands in the project application workspace (e.g. npm run build, pytest, git, ls, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The exact shell command to execute."},
                "cwd": {"type": "string", "description": "Optional subdirectory path relative to workspace or absolute."},
                "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (default 30)."},
            },
            "required": ["command"],
        },
        "handler": tool_opencode_run_terminal,
    },
    {
        "name": "opencode_open_in_editor",
        "description": "Open VS Code / IDE editor on a file or directory in the application.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File or folder path to open in VS Code."},
                "line": {"type": "integer", "description": "Optional line number to jump to."},
            },
            "required": [],
        },
        "handler": tool_opencode_open_in_editor,
    },
    {
        "name": "opencode_read_code",
        "description": "Read source code from a file in the application with line numbers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative or absolute path to the file to read."},
                "start_line": {"type": "integer", "description": "Starting line number (1-indexed)."},
                "end_line": {"type": "integer", "description": "Ending line number (inclusive)."},
            },
            "required": ["file_path"],
        },
        "handler": tool_opencode_read_code,
    },
    {
        "name": "opencode_write_code",
        "description": "Write or update code in a file in the application workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to write or update."},
                "content": {"type": "string", "description": "Complete content to write to the file."},
            },
            "required": ["file_path", "content"],
        },
        "handler": tool_opencode_write_code,
    },
    {
        "name": "opencode_search_code",
        "description": "Search codebase for function names, symbols, imports, or text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search string or pattern."},
                "directory": {"type": "string", "description": "Subdirectory to restrict search."},
            },
            "required": ["query"],
        },
        "handler": tool_opencode_search_code,
    },
    {
        "name": "opencode_list_files",
        "description": "List files and directories in the application workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory path to list."},
            },
            "required": [],
        },
        "handler": tool_opencode_list_files,
    },
    {
        "name": "opencode_git_summary",
        "description": "Check git branch, modified files, and recent commits in the project repository.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Repository path."},
            },
            "required": [],
        },
        "handler": tool_opencode_git_summary,
    },
]

TOOL_HANDLERS = {t["name"]: t["handler"] for t in TOOLS_CATALOG}


def _send_response(req_id: Any, result: Any = None, error: Any = None) -> None:
    resp: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        resp["error"] = error
    else:
        resp["result"] = result
    sys.stdout.write(json.dumps(resp) + "\n")
    sys.stdout.flush()


def _handle_request(msg: dict[str, Any]) -> None:
    req_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {})

    if method == "initialize":
        _send_response(
            req_id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "opencode-mcp",
                    "version": "1.0.0",
                },
            },
        )
    elif method == "tools/list":
        tools_meta = [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in TOOLS_CATALOG
        ]
        _send_response(req_id, result={"tools": tools_meta})
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            _send_response(
                req_id,
                error={"code": -32601, "message": f"Tool '{tool_name}' not found in OpenCode MCP server."},
            )
            return

        try:
            output_text = handler(tool_args)
            _send_response(
                req_id,
                result={
                    "content": [{"type": "text", "text": str(output_text)}],
                    "isError": False,
                },
            )
        except Exception as exc:
            _send_response(
                req_id,
                result={
                    "content": [{"type": "text", "text": f"Tool execution failed: {exc}"}],
                    "isError": True,
                },
            )
    elif method == "notifications/initialized":
        pass
    else:
        if req_id is not None:
            _send_response(req_id, error={"code": -32601, "message": f"Method '{method}' not implemented."})


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            _handle_request(msg)
        except json.JSONDecodeError:
            pass
        except Exception as exc:
            sys.stderr.write(f"[OpenCode-MCP-Error] {exc}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
