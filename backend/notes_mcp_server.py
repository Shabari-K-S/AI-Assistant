#!/usr/bin/env python3
"""Personal Notes & Markdown Vault MCP Server for S.A.R.A.

Implements JSON-RPC 2.0 stdio Model Context Protocol (2024-11-05 spec) to provide
a folder-based Markdown (.md) vault, personal notes, deep research reports,
and to-do checklist management for S.A.R.A.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

SERVER_NAME = "notes-memory"
SERVER_VERSION = "2.0.0"
PROTOCOL_VERSION = "2024-11-05"
START_TIME = time.time()

# Storage directory structure
DATA_DIR = Path(__file__).resolve().parent / "data"
VAULT_DIR = DATA_DIR / "notes"
INDEX_FILE = DATA_DIR / "notes_index.json"
TODOS_FILE = VAULT_DIR / "todos" / "active_todos.md"


def _slugify(text: str) -> str:
    """Convert text into a safe, clean file slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_") or "untitled"


def _init_vault() -> None:
    """Ensure vault category folders and initial notes exist."""
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    for cat in ["general", "deep-research", "work", "ideas", "todos"]:
        (VAULT_DIR / cat).mkdir(parents=True, exist_ok=True)

    # Create welcome note if no content notes exist yet
    welcome_path = VAULT_DIR / "general" / "welcome_note.md"
    content_notes = [f for f in VAULT_DIR.glob("**/*.md") if f.name != "active_todos.md"]
    if not welcome_path.exists() and not content_notes:
        _write_markdown_file(
            welcome_path,
            {
                "id": "note-1",
                "title": "Welcome to S.A.R.A. Markdown Vault",
                "category": "general",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "tags": ["welcome", "getting-started"],
            },
            "# Welcome to S.A.R.A. Notes & Research Vault\n\nYou can ask S.A.R.A. to save thoughts, markdown notes, tasks, and autonomous deep research briefs.\n\nAll notes are stored as organized `.md` files.",
        )

    if not TODOS_FILE.exists():
        TODOS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TODOS_FILE.write_text(
            "# Active To-Do Checklist\n\n- [ ] #1 Explore S.A.R.A. voice and MCP modules (priority: normal)\n",
            encoding="utf-8",
        )


def _parse_markdown_frontmatter(file_path: Path) -> tuple[dict[str, Any], str]:
    """Parse YAML-style frontmatter and Markdown body from a .md file."""
    if not file_path.exists():
        return {}, ""
    try:
        raw = file_path.read_text(encoding="utf-8")
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                front_raw = parts[1].strip()
                body = parts[2].strip()
                meta: dict[str, Any] = {}
                for line in front_raw.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip()
                        v = v.strip()
                        if v.startswith("[") and v.endswith("]"):
                            meta[k] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
                        else:
                            meta[k] = v.strip("'\"")
                return meta, body
        return {}, raw.strip()
    except Exception:
        return {}, ""


def _write_markdown_file(file_path: Path, frontmatter: dict[str, Any], body: str) -> None:
    """Write markdown file with YAML frontmatter."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            items_str = ", ".join(f'"{x}"' for x in v)
            fm_lines.append(f"{k}: [{items_str}]")
        else:
            fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    full_text = "\n".join(fm_lines) + "\n\n" + body.strip() + "\n"
    file_path.write_text(full_text, encoding="utf-8")


def _load_index() -> dict[str, Any]:
    """Load or rebuild notes index."""
    _init_vault()
    if not INDEX_FILE.exists():
        return _rebuild_index()
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data.get("notes") and list(VAULT_DIR.glob("**/*.md")):
                return _rebuild_index()
            return data
    except Exception:
        return _rebuild_index()


def _rebuild_index() -> dict[str, Any]:
    """Scan all .md files in the vault, generate notes_index.json, and sync vector RAG index."""
    _init_vault()
    from memory_engine import get_memory_engine
    mem_engine = get_memory_engine()

    notes: list[dict[str, Any]] = []
    for md_file in VAULT_DIR.glob("**/*.md"):
        if md_file.name == "active_todos.md":
            continue
        meta, body = _parse_markdown_frontmatter(md_file)
        rel_path = str(md_file.relative_to(DATA_DIR))
        cat = md_file.parent.name
        title = meta.get("title") or md_file.stem.replace("_", " ").title()
        note_id = meta.get("id") or f"note-{int(md_file.stat().st_mtime * 1000) % 1000000}"
        created_at = meta.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(md_file.stat().st_ctime))
        preview = (body[:160] + "...") if len(body) > 160 else body

        # Sync into vector search engine
        try:
            mem_engine.index_vault_file(rel_path, meta, body)
        except Exception as exc:
            pass

        notes.append({
            "id": note_id,
            "title": title,
            "category": cat,
            "path": rel_path,
            "created_at": created_at,
            "preview": preview,
            "tags": meta.get("tags", []),
            "sources_count": meta.get("sources_count"),
            "model_used": meta.get("model_used"),
        })

    index_data = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "vault_path": str(VAULT_DIR),
        "notes": notes,
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    return index_data


def _find_note_file(target: str) -> tuple[Path | None, dict[str, Any] | None]:
    """Find a note file by ID, title, filename, or partial path."""
    target_clean = target.strip().lower()
    index_data = _load_index()

    for item in index_data.get("notes", []):
        if (
            item.get("id", "").lower() == target_clean
            or item.get("title", "").lower() == target_clean
            or item.get("path", "").lower().endswith(target_clean)
            or Path(item.get("path", "")).stem.lower() == target_clean
        ):
            full_path = DATA_DIR / item["path"]
            if full_path.exists():
                return full_path, item

    # Direct filesystem check
    for md_file in VAULT_DIR.glob("**/*.md"):
        if md_file.stem.lower() == target_clean or md_file.name.lower() == target_clean:
            return md_file, None

    return None, None


# --------------------------------------------------------------------------- #
# Tool Handlers
# --------------------------------------------------------------------------- #

def handle_add_note(args: dict[str, Any]) -> str:
    title = str(args.get("title", "")).strip()
    content = str(args.get("content", "")).strip()
    category = str(args.get("category", "general")).strip().lower() or "general"
    tags = args.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    if not title and not content:
        return "Error: Note title or content is required."
    if not title:
        title = content[:35] + ("..." if len(content) > 35 else "")

    slug = _slugify(title)
    cat_dir = VAULT_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    file_path = cat_dir / f"{slug}.md"
    # Prevent collision
    counter = 1
    while file_path.exists():
        file_path = cat_dir / f"{slug}_{counter}.md"
        counter += 1

    note_id = f"note-{int(time.time() * 1000) % 1000000}"
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    frontmatter = {
        "id": note_id,
        "title": title,
        "category": category,
        "created_at": created_at,
        "tags": tags,
    }

    _write_markdown_file(file_path, frontmatter, content)
    _rebuild_index()

    return (
        f"Markdown Note Created (MCP Vault):\n"
        f"• Title: {title}\n"
        f"• Category: {category}\n"
        f"• File: {file_path.relative_to(DATA_DIR)}\n"
        f"• ID: {note_id}\n"
        f"• Content Length: {len(content)} chars"
    )


def handle_read_note(args: dict[str, Any]) -> str:
    target = str(args.get("note_id_or_title_or_path", "")).strip()
    if not target:
        return "Error: note_id_or_title_or_path is required."

    file_path, meta = _find_note_file(target)
    if not file_path or not file_path.exists():
        return f"Error: Note '{target}' not found in Markdown vault."

    frontmatter, body = _parse_markdown_frontmatter(file_path)
    title = frontmatter.get("title") or (meta.get("title") if meta else file_path.stem)
    category = frontmatter.get("category") or file_path.parent.name
    created_at = frontmatter.get("created_at", "unknown")

    return (
        f"📄 Markdown Note: {title} [{category.upper()}]\n"
        f"📁 Path: {file_path.relative_to(DATA_DIR)} | Date: {created_at}\n"
        f"{'━' * 60}\n\n"
        f"{body}"
    )


def handle_edit_note(args: dict[str, Any]) -> str:
    target = str(args.get("note_id_or_title_or_path", "")).strip()
    content = str(args.get("content", "")).strip()
    append = bool(args.get("append", False))

    if not target:
        return "Error: note_id_or_title_or_path is required."
    if not content:
        return "Error: content is required for editing."

    file_path, meta = _find_note_file(target)
    if not file_path or not file_path.exists():
        return f"Error: Note '{target}' not found to edit."

    frontmatter, existing_body = _parse_markdown_frontmatter(file_path)
    if append:
        new_body = existing_body + "\n\n" + content
    else:
        new_body = content

    frontmatter["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_markdown_file(file_path, frontmatter, new_body)
    _rebuild_index()

    action = "Appended content to" if append else "Updated"
    return f"Successfully {action} note '{frontmatter.get('title', file_path.name)}' ({file_path.relative_to(DATA_DIR)})."


def handle_list_notes(args: dict[str, Any]) -> str:
    category = str(args.get("category", "")).strip().lower()
    index_data = _load_index()
    notes = index_data.get("notes", [])

    if category:
        notes = [n for n in notes if n.get("category", "").lower() == category]

    if not notes:
        return f"No markdown notes found{' in category ' + category if category else ''}."

    lines = [f"Markdown Vault Notes ({len(notes)} items):\n"]
    for i, n in enumerate(notes, 1):
        lines.append(f"{i}. [{n.get('category', 'general').upper()}] {n.get('title')} (ID: {n.get('id')})")
        lines.append(f"   File: {n.get('path')}")
        lines.append(f"   Preview: {n.get('preview')}\n")
    return "\n".join(lines).strip()


def handle_search_notes(args: dict[str, Any]) -> str:
    query = str(args.get("query", "")).strip().lower()
    if not query:
        return "Error: Search query cannot be empty."

    index_data = _load_index()
    notes = index_data.get("notes", [])
    matches: list[tuple[dict[str, Any], str]] = []

    for n in notes:
        full_path = DATA_DIR / n["path"]
        if full_path.exists():
            _, body = _parse_markdown_frontmatter(full_path)
            if (
                query in n.get("title", "").lower()
                or query in body.lower()
                or query in n.get("category", "").lower()
                or any(query in str(t).lower() for t in n.get("tags", []))
            ):
                snippet = body[:200] + ("..." if len(body) > 200 else "")
                matches.append((n, snippet))

    if not matches:
        return f"No markdown notes matching '{query}' found."

    lines = [f"🔍 Search Results in Vault for '{query}' ({len(matches)} matches):\n"]
    for item, snippet in matches:
        lines.append(f"• [{item.get('category').upper()}] {item.get('title')} (File: {item.get('path')})")
        lines.append(f"  Content: {snippet}\n")
    return "\n".join(lines).strip()


def handle_delete_note(args: dict[str, Any]) -> str:
    target = str(args.get("note_id_or_title_or_path", "")).strip()
    if not target:
        return "Error: note_id_or_title_or_path is required."

    file_path, _ = _find_note_file(target)
    if not file_path or not file_path.exists():
        return f"No note matching '{target}' was found in vault."

    file_name = file_path.name
    try:
        file_path.unlink()
        _rebuild_index()
        return f"Successfully deleted markdown note: {file_name}"
    except Exception as exc:
        return f"Error deleting note '{file_name}': {exc}"


def handle_add_todo(args: dict[str, Any]) -> str:
    task = str(args.get("task", "")).strip()
    priority = str(args.get("priority", "normal")).strip().lower()
    due_date = str(args.get("due_date", "")).strip()

    if not task:
        return "Error: Task description is required."

    _init_vault()
    raw = TODOS_FILE.read_text(encoding="utf-8") if TODOS_FILE.exists() else "# Active To-Do Checklist\n\n"

    # Find highest task ID
    existing_ids = [int(m) for m in re.findall(r"- \[[ xX]\] #(\d+)", raw)]
    next_id = max(existing_ids, default=0) + 1

    due_str = f" (due: {due_date})" if due_date else ""
    new_entry = f"- [ ] #{next_id} {task} [priority: {priority}]{due_str}\n"
    TODOS_FILE.write_text(raw.strip() + "\n" + new_entry, encoding="utf-8")

    return f"To-Do Added to Vault:\n• Task #{next_id}: {task}\n• Priority: {priority}{due_str}\n• Saved in: notes/todos/active_todos.md"


def handle_list_todos(args: dict[str, Any]) -> str:
    status = str(args.get("status", "all")).strip().lower()
    _init_vault()
    if not TODOS_FILE.exists():
        return "No tasks found in vault."

    raw = TODOS_FILE.read_text(encoding="utf-8")
    lines = [line.strip() for line in raw.splitlines() if line.strip().startswith("- [")]

    filtered = []
    for l in lines:
        is_done = l.startswith("- [x]") or l.startswith("- [X]")
        if status in ("active", "pending") and is_done:
            continue
        if status in ("completed", "done") and not is_done:
            continue
        filtered.append(l)

    if not filtered:
        return f"No {status if status != 'all' else ''} tasks found in active_todos.md."

    out = [f"To-Do Checklist ({len(filtered)} tasks in notes/todos/active_todos.md):"]
    out.extend(filtered)
    return "\n".join(out)


def handle_complete_todo(args: dict[str, Any]) -> str:
    try:
        task_id = int(args.get("task_id", 0))
    except (ValueError, TypeError):
        return "Error: task_id must be an integer."

    _init_vault()
    if not TODOS_FILE.exists():
        return "Error: active_todos.md does not exist."

    raw = TODOS_FILE.read_text(encoding="utf-8")
    pattern = rf"- \[ \] #{task_id}\b"

    if not re.search(pattern, raw):
        return f"Active task #{task_id} not found."

    updated = re.sub(pattern, f"- [x] #{task_id}", raw)
    TODOS_FILE.write_text(updated, encoding="utf-8")
    return f"Marked Task #{task_id} as completed in active_todos.md."


def handle_delete_todo(args: dict[str, Any]) -> str:
    """Delete a specific to-do item from active_todos.md by task ID or keyword."""
    _init_vault()
    if not TODOS_FILE.exists():
        return "Error: active_todos.md does not exist."

    task_id = args.get("task_id")
    keyword = str(args.get("keyword", "")).strip().lower()

    raw = TODOS_FILE.read_text(encoding="utf-8")
    lines = raw.splitlines()
    remaining = []
    deleted_count = 0

    for line in lines:
        if not line.startswith("- ["):
            remaining.append(line)
            continue
        should_delete = False
        if task_id is not None:
            try:
                tid = int(task_id)
                if re.search(rf"- \[[ xX]\] #{tid}\b", line):
                    should_delete = True
            except (ValueError, TypeError):
                pass
        if not should_delete and keyword:
            if keyword in line.lower():
                should_delete = True

        if should_delete:
            deleted_count += 1
        else:
            remaining.append(line)

    if deleted_count == 0:
        return f"No matching task found to delete in active_todos.md (searched task_id={task_id}, keyword='{keyword}')."

    TODOS_FILE.write_text("\n".join(remaining).strip() + "\n", encoding="utf-8")
    return f"Successfully deleted {deleted_count} task(s) from active_todos.md."


def handle_clear_completed_todos(args: dict[str, Any] | None = None) -> str:
    """Remove all completed [x] tasks from active_todos.md to keep checklist clean."""
    del args
    _init_vault()
    if not TODOS_FILE.exists():
        return "Error: active_todos.md does not exist."

    raw = TODOS_FILE.read_text(encoding="utf-8")
    lines = raw.splitlines()
    remaining = []
    removed_count = 0

    for line in lines:
        if line.startswith("- [x]") or line.startswith("- [X]"):
            removed_count += 1
        else:
            remaining.append(line)

    if removed_count == 0:
        return "No completed tasks found to clear in active_todos.md (all tasks are still pending)."

    TODOS_FILE.write_text("\n".join(remaining).strip() + "\n", encoding="utf-8")
    return f"Cleaned up to-do checklist: removed {removed_count} completed task(s) from active_todos.md."


def handle_deduplicate_todos(args: dict[str, Any] | None = None) -> str:
    """Remove duplicate task items from active_todos.md while preserving unique tasks."""
    del args
    _init_vault()
    if not TODOS_FILE.exists():
        return "Error: active_todos.md does not exist."

    raw = TODOS_FILE.read_text(encoding="utf-8")
    lines = raw.splitlines()
    seen_texts: set[str] = set()
    cleaned_lines = []
    dup_count = 0

    for line in lines:
        if not line.startswith("- ["):
            cleaned_lines.append(line)
            continue
        normalized = re.sub(r"-\s*\[[ xX]\]\s*(?:#\d+\s*)?", "", line).strip().lower()
        if normalized in seen_texts:
            dup_count += 1
        else:
            seen_texts.add(normalized)
            cleaned_lines.append(line)

    if dup_count == 0:
        return "No duplicate tasks found in active_todos.md."

    TODOS_FILE.write_text("\n".join(cleaned_lines).strip() + "\n", encoding="utf-8")
    return f"Deduplicated to-do checklist: removed {dup_count} duplicate task(s)."


def handle_notes_summary(args: dict[str, Any]) -> str:
    del args
    index_data = _load_index()
    notes = index_data.get("notes", [])
    categories = set(n.get("category", "general") for n in notes)

    todo_count = 0
    done_count = 0
    if TODOS_FILE.exists():
        raw = TODOS_FILE.read_text(encoding="utf-8")
        todo_count = len(re.findall(r"- \[ \]", raw))
        done_count = len(re.findall(r"- \[[xX]\]", raw))

    return (
        f"Markdown Notes & Research Vault:\n"
        f"• Total Markdown Notes: {len(notes)}\n"
        f"• Categories: {', '.join(sorted(categories)) or 'general'}\n"
        f"• Pending To-Dos: {todo_count}\n"
        f"• Completed Tasks: {done_count}\n"
        f"• Storage Location: backend/data/notes/"
    )


def handle_semantic_rag_search(args: dict[str, Any]) -> str:
    """Perform neural semantic vector RAG search across all Markdown notes and deep research documents."""
    query = str(args.get("query", "")).strip()
    if not query:
        return "Error: query parameter is required."
    category = args.get("category")
    top_k = min(10, max(1, int(args.get("top_k", 4))))

    from memory_engine import get_memory_engine
    engine = get_memory_engine()
    results = engine.search_vault(query, top_k=top_k, category=category)
    if not results:
        return f"No relevant note sections found in the vault matching '{query}'."

    out = [f"🧠 **Vault Semantic RAG Results for:** *'{query}'* ({len(results)} matches)\n"]
    for i, r in enumerate(results, 1):
        rel_percent = int(r["score"] * 100)
        out.append(f"### {i}. [{r['title']}]({r['file_path']}) — *{r['heading']}* (Relevance: {rel_percent}%)")
        out.append(f"**Category:** `{r['category']}` | **Path:** `{r['file_path']}`")
        out.append(f"```markdown\n{r['content']}\n```\n")

    return "\n".join(out)


def handle_voice_brain_dump(args: dict[str, Any]) -> str:
    """Process an unstructured, stream-of-consciousness raw voice transcript, extracting tasks, notes, and memory facts in one step."""
    raw_speech = str(args.get("raw_speech_stream", "")).strip()
    if not raw_speech:
        return "Error: raw_speech_stream is required."
    default_cat = str(args.get("default_category", "ideas")).strip() or "ideas"

    extracted_tasks: list[dict[str, str]] = []
    extracted_facts: list[str] = []
    extracted_notes: list[dict[str, str]] = []

    # Clean introductory conversational starters
    cleaned_speech = re.sub(
        r"(?i)^(?:hey\s+athena|athena|hi\s+athena|ok\s+athena|hey\s+sara|sara|hi\s+sara|ok\s+sara|assistant)?[\s,:-]*(?:take\s+a\s+brain\s+dump|brain\s+dump(?:\s+mode)?|quick\s+note)?[\s,:-]*",
        "",
        raw_speech,
    ).strip()

    # Segment stream by periods, semicolons, or conjunction transitions
    raw_segments = re.split(
        r"(?<=[.!?])\s+|[;]+|(?:\s*,\s*(?=(?:and\s+also|also|furthermore|additionally|plus|and\s+remember|and\s+need|and\s+our|and\s+i|and\s+we)\b))|(?:\b(?:and\s+also|furthermore|additionally|plus)\b)",
        cleaned_speech,
        flags=re.IGNORECASE,
    )
    unassigned_thoughts: list[str] = []

    for s in raw_segments:
        s_clean = s.strip(" ,.-")
        if not s_clean:
            continue

        # 1. Check for Fact/Preference/Memory pattern first
        fact_match = re.search(r"(?i)\b(?:i\s+prefer|i\s+like|my\s+favorite|his\s+all\s+time\s+favorite|favorite|recommended|recommendation|told\s+me\s+that|configured\s+with|runs\s+on)\b", s_clean)
        if fact_match and len(s_clean.split()) <= 30:
            fact_text = re.sub(r"(?i)^(?:and\s+)?(?:also\s+)?", "", s_clean).strip(" ,.-")
            extracted_facts.append(fact_text)
            continue

        # 2. Check for Task/Todo pattern
        task_match = re.search(r"(?i)\b(?:need\s+to|remember\s+to|todo:?|have\s+to|must|buy|purchase|email|call|fix|schedule|update)\s+(.+)", s_clean)
        if task_match and len(s_clean.split()) <= 25:
            task_text = s_clean
            task_text = re.sub(r"(?i)^(?:and\s+)?(?:i\s+|we\s+)?(?:need\s+to|remember\s+to|todo:?|have\s+to|must)\s+", "", task_text).strip()
            task_text = re.sub(r"(?i)^(?:and\s+)?", "", task_text).strip(" ,.-")
            prio = "high" if any(w in s_clean.lower() for w in ("urgent", "asap", "important", "immediately")) else "normal"
            extracted_tasks.append({"task": task_text.capitalize(), "priority": prio})
            continue

        # 3. Residual technical or conceptual thoughts
        residual_text = re.sub(r"(?i)^(?:and\s+)?(?:also\s+)?", "", s_clean).strip(" ,.-")
        if residual_text:
            unassigned_thoughts.append(residual_text)

    # Group residual ideas into a structured note
    if unassigned_thoughts:
        note_body = "\n\n".join(f"- {t}" for t in unassigned_thoughts)
        first_words = unassigned_thoughts[0].split()[:5]
        note_title = " ".join(first_words).capitalize()
        if not note_title:
            note_title = f"Brain Dump {time.strftime('%b %d %H:%M')}"
        extracted_notes.append({
            "title": note_title,
            "category": default_cat,
            "content": f"# {note_title}\n\n*Captured via S.A.R.A. Voice Brain Dump on {time.strftime('%Y-%m-%d %H:%M')}*\n\n## Key Thoughts & Insights\n{note_body}",
        })

    results_log = ["🧠 **S.A.R.A. Second Brain Dump Processed Successfully:**\n"]

    # 1. Store extracted tasks into active_todos.md
    if extracted_tasks:
        results_log.append("### 📋 Extracted Tasks (Added to Checklist):")
        for t in extracted_tasks:
            handle_add_todo({"task": t["task"], "priority": t["priority"]})
            results_log.append(f"- [ ] **{t['task']}** *(Priority: {t['priority']})*")
        results_log.append("")

    # 2. Store structured markdown notes
    if extracted_notes:
        results_log.append("### 📝 Structured Notes (Saved to Vault):")
        for n in extracted_notes:
            handle_add_note({"title": n["title"], "content": n["content"], "category": n["category"], "tags": ["brain-dump", "voice-note"]})
            slug = _slugify(n["title"])
            results_log.append(f"- 📄 `{n['category']}/{slug}.md` — *{n['title']}*")
        results_log.append("")

    # 3. Ingest personal facts into long-term episodic memory
    if extracted_facts:
        from memory_engine import get_memory_engine
        mem_engine = get_memory_engine()
        results_log.append("### 🧠 Episodic Facts (Ingested into Long-Term Memory):")
        for f in extracted_facts:
            mem_engine.store_fact(f, category="personal", tags=["brain-dump", "fact"])
            results_log.append(f"- 💡 {f}")
        results_log.append("")

    if not extracted_tasks and not extracted_notes and not extracted_facts:
        handle_add_note({"title": f"Voice Thought {time.strftime('%b %d')}", "content": raw_speech, "category": default_cat, "tags": ["brain-dump"]})
        results_log.append(f"Saved raw voice thought as `{default_cat}/voice_thought.md`")

    _rebuild_index()
    return "\n".join(results_log)


TOOLS = [
    {
        "name": "notes_add_note",
        "description": "Create and save a new Markdown (.md) note into the user's organized note vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title or headline of the note"},
                "content": {"type": "string", "description": "Markdown formatted content, article, or thoughts"},
                "category": {"type": "string", "description": "Category folder: 'general', 'deep-research', 'work', 'ideas', etc."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional list of tags"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "notes_read_note",
        "description": "Read the full Markdown content and metadata of a specific note by ID, title, or filename.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note_id_or_title_or_path": {"type": "string", "description": "Note ID (e.g. 'note-1'), title, or filename (e.g. 'quantum_computing.md')"},
            },
            "required": ["note_id_or_title_or_path"],
        },
    },
    {
        "name": "notes_edit_note",
        "description": "Update or append markdown content to an existing note file in the vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note_id_or_title_or_path": {"type": "string", "description": "Note ID, title, or filename"},
                "content": {"type": "string", "description": "New markdown content to write or append"},
                "append": {"type": "boolean", "description": "If true, appends content to the end of the note instead of overwriting", "default": False},
            },
            "required": ["note_id_or_title_or_path", "content"],
        },
    },
    {
        "name": "notes_list_notes",
        "description": "List all Markdown files in the vault with categories, file paths, and summaries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category filter ('deep-research', 'general', 'work')"},
            },
        },
    },
    {
        "name": "notes_search_notes",
        "description": "Full-text search across all Markdown notes and deep research files in the vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword, topic, or phrase"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "notes_semantic_rag_search",
        "description": "Perform deep neural and semantic vector search across all notes, research briefs, and ideas in your Markdown Vault to find relevant answers without needing exact keywords.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language question or search topic (e.g. 'What was the movie recommendation?' or 'database scaling strategy')."},
                "category": {"type": "string", "description": "Optional category filter ('general', 'ideas', 'work', 'deep-research', 'todos')."},
                "top_k": {"type": "integer", "description": "Max number of relevant note sections to return (default: 4).", "default": 4},
            },
            "required": ["query"],
        },
    },
    {
        "name": "voice_brain_dump_processor",
        "description": "Process an unstructured, stream-of-consciousness raw voice transcript, automatically extracting action items into to-dos, structured thoughts into markdown notes, and personal facts into long-term memory in one step.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "raw_speech_stream": {"type": "string", "description": "The raw, stream-of-consciousness spoken thought stream from the user."},
                "default_category": {"type": "string", "description": "Category for generated notes (default: 'ideas').", "default": 'ideas'},
            },
            "required": ["raw_speech_stream"],
        },
    },
    {
        "name": "notes_delete_note",
        "description": "Delete a Markdown note file from the vault by its ID, title, or filename.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "note_id_or_title_or_path": {"type": "string", "description": "Note ID, title, or filename to delete"},
            },
            "required": ["note_id_or_title_or_path"],
        },
    },
    {
        "name": "notes_add_todo",
        "description": "Add a task item to the active To-Do checklist file in the vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Actionable task description"},
                "priority": {"type": "string", "description": "'low', 'normal', 'high', or 'urgent' (default: 'normal')"},
                "due_date": {"type": "string", "description": "Optional due date"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "notes_list_todos",
        "description": "List tasks and checklist items from active_todos.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "'active', 'completed', or 'all' (default: 'all')"},
            },
        },
    },
    {
        "name": "notes_complete_todo",
        "description": "Mark a task item as completed by task ID in active_todos.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Task ID number"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "notes_delete_todo",
        "description": "Delete a specific to-do task by task ID number or keyword from active_todos.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Optional numeric task ID to delete"},
                "keyword": {"type": "string", "description": "Optional text keyword to match and delete"},
            },
        },
    },
    {
        "name": "notes_clear_completed_todos",
        "description": "Remove/delete all completed [x] tasks from active_todos.md to keep the checklist clean.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "notes_deduplicate_todos",
        "description": "Scan active_todos.md and remove all duplicate tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "notes_summary",
        "description": "Get high-level statistics on total Markdown notes, categories, and tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

TOOL_HANDLERS = {
    "notes_add_note": handle_add_note,
    "notes_read_note": handle_read_note,
    "notes_edit_note": handle_edit_note,
    "notes_list_notes": handle_list_notes,
    "notes_search_notes": handle_search_notes,
    "notes_semantic_rag_search": handle_semantic_rag_search,
    "voice_brain_dump_processor": handle_voice_brain_dump,
    "notes_delete_note": handle_delete_note,
    "notes_add_todo": handle_add_todo,
    "notes_list_todos": handle_list_todos,
    "notes_complete_todo": handle_complete_todo,
    "notes_delete_todo": handle_delete_todo,
    "notes_clear_completed_todos": handle_clear_completed_todos,
    "notes_deduplicate_todos": handle_deduplicate_todos,
    "notes_summary": handle_notes_summary,
}


def send_response(response: dict) -> None:
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main() -> None:
    _init_vault()
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
