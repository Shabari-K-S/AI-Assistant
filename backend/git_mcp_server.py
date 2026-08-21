#!/usr/bin/env python3
"""Autonomous Git Copilot & Robot Framework QA Auto-Fix MCP Server for Athena.

Implements JSON-RPC 2.0 stdio Model Context Protocol (2024-11-05 spec) providing:
- git_status: Inspect branch, staged/unstaged changes, and untracked files.
- git_diff: View working tree code diffs against HEAD or specific branches.
- git_create_branch: Create and switch to new fix/feature branches.
- git_apply_patch: Apply code changes and modifications.
- git_commit: Stage files and create structured conventional commits.
- qa_auto_repair_loop: Connects Robot Framework execution, failure isolation, and patch verification.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", Path(__file__).resolve().parent.parent)).resolve()

TOOLS = [
    {
        "name": "git_status",
        "description": "Inspect Git workspace state: active branch, staged/unstaged changes, modified files, and untracked files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_path": {
                    "type": "string",
                    "description": "Optional subdirectory path within the repository (default: repository root).",
                }
            },
        },
    },
    {
        "name": "git_diff",
        "description": "Inspect code diffs between working directory, staging area, or against HEAD/branches.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Optional specific file to view diff for.",
                },
                "staged": {
                    "type": "boolean",
                    "description": "Whether to view staged diffs (git diff --staged). Default: false.",
                    "default": False,
                },
            },
        },
    },
    {
        "name": "git_create_branch",
        "description": "Create and check out a new Git branch for bug fixes, test repairs, or feature implementations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "branch_name": {
                    "type": "string",
                    "description": "Name of the branch to create (e.g. 'fix/robot-test-auth-timeout').",
                },
            },
            "required": ["branch_name"],
        },
    },
    {
        "name": "git_commit",
        "description": "Stage files and create a structured Git commit with a descriptive message.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message (e.g. 'fix(qa): repair failing auth token test in Robot suite').",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of specific file paths to stage (default: '.' for all modified files).",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "git_apply_patch",
        "description": "Write or overwrite content in a workspace file to apply an automated fix.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative file path within repository (e.g. 'backend/main.py').",
                },
                "content": {
                    "type": "string",
                    "description": "New complete file content to write.",
                },
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "qa_auto_repair_loop",
        "description": "Autonomous QA Auto-Fix Loop: Runs a Robot Framework test suite, analyzes failures, prepares diagnostic fix context, and verifies repaired code until green.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "suite_path": {
                    "type": "string",
                    "description": "Path to the .robot test file or directory.",
                },
                "create_fix_branch": {
                    "type": "boolean",
                    "description": "Whether to create a dedicated fix branch automatically (default: true).",
                    "default": True,
                },
            },
            "required": ["suite_path"],
        },
    },
]


def _run_git_cmd(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Execute a git command safely in the workspace."""
    target_cwd = cwd or WORKSPACE_ROOT
    try:
        proc = subprocess.run(
            ["git"] + cmd,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=15.0,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "Git command timed out."
    except Exception as exc:
        return 1, "", str(exc)


# --------------------------------------------------------------------------- #
# Tool Handlers
# --------------------------------------------------------------------------- #

def handle_git_status(args: dict[str, Any]) -> str:
    """Inspect git branch, status, and modified files."""
    code, stdout, stderr = _run_git_cmd(["status", "--short", "--branch"])
    if code != 0:
        return f"Error querying git status: {stderr}"

    code_head, head_out, _ = _run_git_cmd(["rev-parse", "--short", "HEAD"])
    current_commit = head_out if code_head == 0 else "None"

    lines = stdout.splitlines()
    branch_line = lines[0] if lines else "## No branch"
    changed_files = lines[1:] if len(lines) > 1 else []

    status_lines = [
        f"🌿 **Git Repository Status:**",
        f"- **Branch:** `{branch_line.replace('## ', '')}`",
        f"- **HEAD Commit:** `{current_commit}`",
        f"- **Modified / Untracked Files:** `{len(changed_files)} file(s)`",
    ]

    if changed_files:
        status_lines.append("\n**File Changes:**")
        for f in changed_files[:20]:
            status_lines.append(f"- `{f}`")
        if len(changed_files) > 20:
            status_lines.append(f"- *...and {len(changed_files) - 20} more files.*")
    else:
        status_lines.append("\n✨ Working tree clean — no uncommitted changes.")

    return "\n".join(status_lines)


def handle_git_diff(args: dict[str, Any]) -> str:
    """Get git diff output."""
    file_path = str(args.get("file_path", "")).strip()
    staged = bool(args.get("staged", False))

    cmd = ["diff"]
    if staged:
        cmd.append("--staged")
    if file_path:
        cmd.append(file_path)

    code, stdout, stderr = _run_git_cmd(cmd)
    if code != 0:
        return f"Error retrieving git diff: {stderr}"
    if not stdout:
        return "✨ No code differences detected in specified scope."

    # Truncate if very large
    if len(stdout) > 6000:
        preview = stdout[:6000] + f"\n\n... (truncated {len(stdout) - 6000} characters)"
    else:
        preview = stdout

    return f"📝 **Git Diff ({'Staged' if staged else 'Working Tree'}):**\n\n```diff\n{preview}\n```"


def handle_git_create_branch(args: dict[str, Any]) -> str:
    """Create and switch to a new branch."""
    raw_name = str(args.get("branch_name", "")).strip()
    if not raw_name:
        return "Error: branch_name parameter is required."

    branch_name = raw_name.replace(" ", "-").lower()
    code, stdout, stderr = _run_git_cmd(["checkout", "-b", branch_name])
    if code != 0:
        return f"Error creating branch '{branch_name}': {stderr}"
    return f"🌿 Created and switched to new branch: **`{branch_name}`**"


def handle_git_commit(args: dict[str, Any]) -> str:
    """Stage and commit changes."""
    msg = str(args.get("message", "")).strip()
    files = args.get("files") or []

    if not msg:
        return "Error: commit message is required."

    # 1. Stage
    stage_cmd = ["add"]
    if files and isinstance(files, list):
        stage_cmd.extend([str(f) for f in files])
    else:
        stage_cmd.append(".")

    c1, _, e1 = _run_git_cmd(stage_cmd)
    if c1 != 0:
        return f"Error staging files: {e1}"

    # 2. Commit
    c2, out2, e2 = _run_git_cmd(["commit", "-m", msg])
    if c2 != 0:
        if "nothing to commit" in (out2 + e2).lower():
            return "ℹ️ Nothing to commit, working tree clean."
        return f"Error creating commit: {e2 or out2}"

    return f"💾 **Git Commit Created Successfully:**\n`{msg}`\n\nOutput:\n```text\n{out2}\n```"


def handle_git_apply_patch(args: dict[str, Any]) -> str:
    """Apply targeted file modifications."""
    file_path = str(args.get("file_path", "")).strip()
    content = args.get("content", "")

    if not file_path:
        return "Error: file_path is required."

    target_file = (WORKSPACE_ROOT / file_path).resolve()
    # Prevent directory traversal outside workspace
    if not str(target_file).startswith(str(WORKSPACE_ROOT)):
        return f"Error: Path '{file_path}' is outside the project workspace."

    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
        return f"✅ Successfully updated file: `{file_path}` ({len(content)} characters written)."
    except Exception as exc:
        return f"Error writing to file '{file_path}': {exc}"


def handle_qa_auto_repair_loop(args: dict[str, Any]) -> str:
    """Connect Robot Framework execution, failure isolation, and patch context preparation."""
    from robot_mcp_server import handle_run_suite, handle_analyze_failures

    suite_path = str(args.get("suite_path", "")).strip()
    create_branch = bool(args.get("create_fix_branch", True))

    if not suite_path:
        return "Error: suite_path parameter is required."

    # 1. Run the target suite
    run_output = handle_run_suite({"suite_path": suite_path})

    if "🟢 PASSED" in run_output or "Failed: 0" in run_output:
        return (
            f"🎉 **QA Auto-Repair Loop Completed:** Suite is already **100% GREEN**!\n\n"
            f"{run_output}"
        )

    # 2. Extract failure diagnostics
    failure_diag = handle_analyze_failures({"suite_path": suite_path})

    # 3. Create fix branch if requested
    branch_info = ""
    if create_branch:
        safe_suite_name = Path(suite_path).stem.replace("_", "-")
        branch_name = f"auto-fix/robot-{safe_suite_name}-{int(time.time()) % 10000}"
        c, _, _ = _run_git_cmd(["checkout", "-b", branch_name])
        if c == 0:
            branch_info = f"🌿 Switched to dedicated repair branch: **`{branch_name}`**\n"

    return (
        f"🚨 **Robot Framework QA Auto-Repair Loop (Failures Detected):**\n\n"
        f"{branch_info}"
        f"### 1. Test Execution Summary\n"
        f"{run_output}\n\n"
        f"### 2. Root-Cause Failure Diagnostic\n"
        f"{failure_diag}\n\n"
        f"💡 **AI Copilot Next Step:** Review the failing keyword chain above, identify the bug in source code, use `git_apply_patch` to fix it, and call `robot_run_suite` to verify the fix."
    )


def handle_call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name", "")
    args = params.get("arguments", {})

    if name == "git_status":
        out = handle_git_status(args)
    elif name == "git_diff":
        out = handle_git_diff(args)
    elif name == "git_create_branch":
        out = handle_git_create_branch(args)
    elif name == "git_commit":
        out = handle_git_commit(args)
    elif name == "git_apply_patch":
        out = handle_git_apply_patch(args)
    elif name == "qa_auto_repair_loop":
        out = handle_qa_auto_repair_loop(args)
    else:
        out = f"error: unknown tool '{name}'"

    return {
        "content": [
            {
                "type": "text",
                "text": out,
            }
        ]
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "git-copilot-mcp-server",
                        "version": "1.0.0",
                    },
                },
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS},
            }
        elif method == "tools/call":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": handle_call_tool(params),
            }
        elif req_id is not None:
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"},
            }
        else:
            continue

        sys.stdout.write(json.dumps(res) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
