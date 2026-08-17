#!/usr/bin/env python3
"""Personal Notes & Memory MCP Server for S.A.R.A.

Implements JSON-RPC 2.0 stdio Model Context Protocol (2024-11-05 spec) to provide
persistent personal notes, scratchpad, thoughts, and to-do list management for everyday users.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

SERVER_NAME = "notes-memory"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"
START_TIME = time.time()

# Storage directory
DATA_DIR = Path(__file__).resolve().parent / "data"
NOTES_FILE = DATA_DIR / "user_notes.json"


def _load_data() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not NOTES_FILE.exists():
        initial = {
            "notes": [
                {
                    "id": "note-1",
                    "title": "Welcome to S.A.R.A. Notes",
                    "content": "You can ask S.A.R.A. to save thoughts, reminders, notes, and tasks anytime.",
                    "category": "general",
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            ],
            "todos": [
                {
                    "id": 1,
                    "task": "Explore S.A.R.A. voice and MCP module configuration",
                    "priority": "normal",
                    "completed": False,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            ],
        }
        _save_data(initial)
        return initial
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"notes": [], "todos": []}


def _save_data(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def handle_add_note(args: dict[str, Any]) -> str:
    title = str(args.get("title", "")).strip()
    content = str(args.get("content", "")).strip()
    category = str(args.get("category", "general")).strip().lower() or "general"

    if not title and not content:
        return "Error: Note title or content is required."
    if not title:
        title = content[:30] + ("..." if len(content) > 30 else "")

    data = _load_data()
    note_id = f"note-{int(time.time() * 1000) % 1000000}"
    new_note = {
        "id": note_id,
        "title": title,
        "content": content,
        "category": category,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    data.setdefault("notes", []).append(new_note)
    _save_data(data)
    return f"Note Saved (MCP):\n• Title: {title}\n• Category: {category}\n• ID: {note_id}\n• Content: {content}"


def handle_list_notes(args: dict[str, Any]) -> str:
    category = str(args.get("category", "")).strip().lower()
    data = _load_data()
    notes = data.get("notes", [])

    if category:
        notes = [n for n in notes if n.get("category", "").lower() == category]

    if not notes:
        return f"No notes found{' in category ' + category if category else ''}."

    lines = [f"Personal Notes ({len(notes)} items):"]
    for i, n in enumerate(notes, 1):
        lines.append(f"{i}. [{n.get('category', 'general').upper()}] {n.get('title')}: {n.get('content')} ({n.get('created_at')})")
    return "\n".join(lines)


def handle_search_notes(args: dict[str, Any]) -> str:
    query = str(args.get("query", "")).strip().lower()
    if not query:
        return "Error: Search query cannot be empty."

    data = _load_data()
    notes = data.get("notes", [])
    matches = [
        n for n in notes
        if query in n.get("title", "").lower() or query in n.get("content", "").lower() or query in n.get("category", "").lower()
    ]
    if not matches:
        return f"No notes matching '{query}' found."

    lines = [f"Search Results for '{query}' ({len(matches)} matches):"]
    for n in matches:
        lines.append(f"• [{n.get('category')}] {n.get('title')}: {n.get('content')}")
    return "\n".join(lines)


def handle_delete_note(args: dict[str, Any]) -> str:
    target = str(args.get("note_id_or_title", "")).strip().lower()
    if not target:
        return "Error: note_id_or_title is required."

    data = _load_data()
    notes = data.get("notes", [])
    remaining = []
    deleted = []

    for n in notes:
        if n.get("id", "").lower() == target or n.get("title", "").lower() == target:
            deleted.append(n)
        else:
            remaining.append(n)

    if not deleted:
        return f"No note matching '{target}' was found to delete."

    data["notes"] = remaining
    _save_data(data)
    return f"Successfully deleted {len(deleted)} note(s): {', '.join(d.get('title', '') for d in deleted)}"


def handle_add_todo(args: dict[str, Any]) -> str:
    task = str(args.get("task", "")).strip()
    priority = str(args.get("priority", "normal")).strip().lower()
    due_date = str(args.get("due_date", "")).strip()

    if not task:
        return "Error: Task description is required."

    data = _load_data()
    todos = data.setdefault("todos", [])
    next_id = max([t.get("id", 0) for t in todos], default=0) + 1

    new_todo = {
        "id": next_id,
        "task": task,
        "priority": priority,
        "completed": False,
        "due_date": due_date,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    todos.append(new_todo)
    _save_data(data)
    return f"To-Do Created (MCP):\n• Task #{next_id}: {task}\n• Priority: {priority}{f' (Due: {due_date})' if due_date else ''}"


def handle_list_todos(args: dict[str, Any]) -> str:
    status = str(args.get("status", "all")).strip().lower()
    data = _load_data()
    todos = data.get("todos", [])

    if status == "active" or status == "pending":
        todos = [t for t in todos if not t.get("completed")]
    elif status == "completed" or status == "done":
        todos = [t for t in todos if t.get("completed")]

    if not todos:
        return f"No {status if status != 'all' else ''} tasks found."

    lines = [f"To-Do List ({len(todos)} tasks):"]
    for t in todos:
        mark = "✓" if t.get("completed") else "◻"
        due = f" [Due: {t.get('due_date')}]" if t.get("due_date") else ""
        lines.append(f"#{t.get('id')} {mark} [{t.get('priority', 'normal').upper()}] {t.get('task')}{due}")
    return "\n".join(lines)


def handle_complete_todo(args: dict[str, Any]) -> str:
    try:
        task_id = int(args.get("task_id", 0))
    except (ValueError, TypeError):
        return "Error: task_id must be a valid integer number."

    data = _load_data()
    todos = data.get("todos", [])
    found = False
    task_name = ""

    for t in todos:
        if t.get("id") == task_id:
            t["completed"] = True
            t["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            found = True
            task_name = t.get("task", "")
            break

    if not found:
        return f"Task #{task_id} not found."

    _save_data(data)
    return f"Completed Task #{task_id}: {task_name}"


def handle_notes_summary(args: dict[str, Any]) -> str:
    del args
    data = _load_data()
    notes = data.get("notes", [])
    todos = data.get("todos", [])
    active_todos = [t for t in todos if not t.get("completed")]

    return (
        f"Personal Notes & Memory Hub:\n"
        f"• Total Saved Notes: {len(notes)}\n"
        f"• Active Pending Tasks: {len(active_todos)}\n"
        f"• Completed Tasks: {len(todos) - len(active_todos)}\n"
        f"• Categories: {', '.join(set(n.get('category', 'general') for n in notes)) or 'None'}"
    )


TOOLS = [
    {
        "name": "notes_add_note",
        "description": "Save a new personal note, thought, snippet, or reminder into user memory via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short summary title of the note"},
                "content": {"type": "string", "description": "Detailed text content or thought"},
                "category": {"type": "string", "description": "Category tag, e.g., 'work', 'personal', 'ideas', 'general'"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "notes_list_notes",
        "description": "List saved notes from user memory, optionally filtering by category.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category filter (e.g. 'work', 'personal')"},
            },
        },
    },
    {
        "name": "notes_search_notes",
        "description": "Search saved notes and thoughts by keywords.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "notes_delete_note",
        "description": "Delete a note from memory by its ID or title.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note_id_or_title": {"type": "string", "description": "ID (e.g. 'note-1') or exact title of note"},
            },
            "required": ["note_id_or_title"],
        },
    },
    {
        "name": "notes_add_todo",
        "description": "Add a new task or to-do item to the user's checklist.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Actionable task description"},
                "priority": {"type": "string", "description": "'low', 'normal', 'high', or 'urgent' (default: 'normal')"},
                "due_date": {"type": "string", "description": "Optional due date, e.g., 'today', 'tomorrow', 'Friday'"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "notes_list_todos",
        "description": "List checklist tasks and to-dos (active, completed, or all).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "'active', 'completed', or 'all' (default: 'all')"},
            },
        },
    },
    {
        "name": "notes_complete_todo",
        "description": "Mark a task or to-do item as completed by task ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Numeric ID of the task to complete (e.g. 1, 2)"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "notes_summary",
        "description": "Get a high-level summary count of notes, categories, and pending tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

TOOL_HANDLERS = {
    "notes_add_note": handle_add_note,
    "notes_list_notes": handle_list_notes,
    "notes_search_notes": handle_search_notes,
    "notes_delete_note": handle_delete_note,
    "notes_add_todo": handle_add_todo,
    "notes_list_todos": handle_list_todos,
    "notes_complete_todo": handle_complete_todo,
    "notes_summary": handle_notes_summary,
}


def send_response(response: dict) -> None:
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            })
        elif method == "notifications/initialized":
            pass
        elif method == "ping":
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        elif method == "tools/list":
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            handler = TOOL_HANDLERS.get(tool_name)
            if handler:
                try:
                    text_result = handler(tool_args)
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": text_result}],
                            "isError": False,
                        },
                    })
                except Exception as err:
                    send_response({
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Error executing {tool_name}: {err}"}],
                            "isError": True,
                        },
                    })
            else:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
                })
        elif req_id is not None:
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not supported"},
            })


if __name__ == "__main__":
    main()
