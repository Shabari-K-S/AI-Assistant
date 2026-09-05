#!/usr/bin/env python3
"""Session & Multi-Conversation History Manager for ATHENA.

Provides persistent multi-session conversation storage using a thread-safe SQLite database
(backend/data/sessions/sessions.db). Allows creating new sessions, listing sessions with
previews and timeline metadata, appending turns, renaming, and deleting conversations.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("athena.sessions")

DATA_DIR = Path(__file__).resolve().parent / "data" / "sessions"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "sessions.db"

_LOCK = threading.Lock()
_ACTIVE_SESSION_ID: str | None = None


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_db() -> None:
    with _LOCK:
        with _get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    is_pinned INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    tool_data TEXT DEFAULT NULL,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, timestamp)"
            )
            conn.commit()


_init_db()


class SessionManager:
    """Thread-safe Multi-Session Conversation Controller."""

    def __init__(self) -> None:
        self._ensure_default_session()

    def _ensure_default_session(self) -> str:
        """Ensure at least one session exists."""
        global _ACTIVE_SESSION_ID
        with _LOCK:
            with _get_connection() as conn:
                cur = conn.execute("SELECT id FROM sessions ORDER BY updated_at DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    _ACTIVE_SESSION_ID = row["id"]
                    return row["id"]

                # Create initial default session
                sid = str(uuid.uuid4())[:8]
                now = time.time()
                title = "Main Intelligence Session"
                conn.execute(
                    "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (sid, title, now, now),
                )
                # Seed with welcome greeting
                mid = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO messages (id, session_id, role, text, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (mid, sid, "assistant", "A.T.H.E.N.A. Neural Core online. All systems synchronized.", now),
                )
                conn.commit()
                _ACTIVE_SESSION_ID = sid
                return sid

    def get_active_session_id(self) -> str:
        global _ACTIVE_SESSION_ID
        if _ACTIVE_SESSION_ID is None:
            return self._ensure_default_session()
        return _ACTIVE_SESSION_ID

    def set_active_session_id(self, session_id: str) -> bool:
        global _ACTIVE_SESSION_ID
        with _LOCK:
            with _get_connection() as conn:
                cur = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
                if cur.fetchone():
                    _ACTIVE_SESSION_ID = session_id
                    return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return all sessions sorted by updated_at descending."""
        with _LOCK:
            with _get_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT s.id, s.title, s.created_at, s.updated_at, s.is_pinned,
                           COUNT(m.id) as message_count,
                           (SELECT text FROM messages WHERE session_id = s.id ORDER BY timestamp DESC LIMIT 1) as last_message,
                           (SELECT role FROM messages WHERE session_id = s.id ORDER BY timestamp DESC LIMIT 1) as last_role
                    FROM sessions s
                    LEFT JOIN messages m ON s.id = m.session_id
                    GROUP BY s.id
                    ORDER BY s.is_pinned DESC, s.updated_at DESC
                    """
                )
                results = []
                for row in cur.fetchall():
                    results.append({
                        "id": row["id"],
                        "title": row["title"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "is_pinned": bool(row["is_pinned"]),
                        "message_count": row["message_count"] or 0,
                        "last_message": (row["last_message"] or "")[:120],
                        "last_role": row["last_role"] or "assistant",
                    })
                return results

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get full session history and metadata."""
        with _LOCK:
            with _get_connection() as conn:
                cur = conn.execute(
                    "SELECT id, title, created_at, updated_at, is_pinned FROM sessions WHERE id = ?",
                    (session_id,),
                )
                s_row = cur.fetchone()
                if not s_row:
                    return None

                m_cur = conn.execute(
                    "SELECT id, role, text, tool_data, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
                    (session_id,),
                )
                messages = []
                for m in m_cur.fetchall():
                    tool_obj = None
                    if m["tool_data"]:
                        try:
                            tool_obj = json.loads(m["tool_data"])
                        except Exception:
                            pass
                    messages.append({
                        "id": m["id"],
                        "role": m["role"],
                        "text": m["text"],
                        "tool_data": tool_obj,
                        "timestamp": m["timestamp"],
                    })

                return {
                    "id": s_row["id"],
                    "title": s_row["title"],
                    "created_at": s_row["created_at"],
                    "updated_at": s_row["updated_at"],
                    "is_pinned": bool(s_row["is_pinned"]),
                    "messages": messages,
                }

    def create_session(self, title: str | None = None) -> dict[str, Any]:
        """Create and return a new conversation session."""
        global _ACTIVE_SESSION_ID
        sid = str(uuid.uuid4())[:8]
        now = time.time()
        session_title = title.strip() if (title and title.strip()) else time.strftime("Session %b %d, %H:%M")

        with _LOCK:
            with _get_connection() as conn:
                conn.execute(
                    "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (sid, session_title, now, now),
                )
                conn.commit()

        _ACTIVE_SESSION_ID = sid
        log.info("Created new session: %s ('%s')", sid, session_title)
        return {
            "id": sid,
            "title": session_title,
            "created_at": now,
            "updated_at": now,
            "is_pinned": False,
            "message_count": 0,
            "last_message": "",
        }

    def add_message(
        self,
        session_id: str | None,
        role: str,
        text: str,
        tool_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a message turn to a session."""
        if not session_id:
            session_id = self.get_active_session_id()

        mid = str(uuid.uuid4())
        now = time.time()
        tool_json = json.dumps(tool_data) if tool_data else None

        with _LOCK:
            with _get_connection() as conn:
                # Ensure session exists
                cur = conn.execute("SELECT id, title, (SELECT COUNT(*) FROM messages WHERE session_id = ?) as cnt FROM sessions WHERE id = ?", (session_id, session_id))
                row = cur.fetchone()
                if not row:
                    # Create on the fly
                    now_str = time.strftime("Session %b %d, %H:%M")
                    conn.execute(
                        "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (session_id, now_str, now, now),
                    )
                    cnt = 0
                    current_title = now_str
                else:
                    cnt = row["cnt"]
                    current_title = row["title"]

                # Auto-generate meaningful session title from first user prompt
                if role == "user" and cnt <= 1:
                    clean_title = text.strip()
                    if len(clean_title) > 36:
                        clean_title = clean_title[:33] + "..."
                    if clean_title:
                        conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (clean_title, session_id))

                conn.execute(
                    "INSERT INTO messages (id, session_id, role, text, tool_data, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (mid, session_id, role, text, tool_json, now),
                )
                conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
                conn.commit()

        return {
            "id": mid,
            "session_id": session_id,
            "role": role,
            "text": text,
            "tool_data": tool_data,
            "timestamp": now,
        }

    def rename_session(self, session_id: str, new_title: str) -> bool:
        """Rename an existing session."""
        title = new_title.strip()
        if not title:
            return False
        with _LOCK:
            with _get_connection() as conn:
                cur = conn.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                    (title, time.time(), session_id),
                )
                conn.commit()
                return cur.rowcount > 0

    def toggle_pin_session(self, session_id: str) -> bool:
        """Toggle pinned status for a session."""
        with _LOCK:
            with _get_connection() as conn:
                cur = conn.execute("SELECT is_pinned FROM sessions WHERE id = ?", (session_id,))
                row = cur.fetchone()
                if not row:
                    return False
                new_pinned = 0 if row["is_pinned"] else 1
                conn.execute("UPDATE sessions SET is_pinned = ? WHERE id = ?", (new_pinned, session_id))
                conn.commit()
                return bool(new_pinned)

    def delete_session(self, session_id: str) -> bool:
        """Delete session and all its messages."""
        global _ACTIVE_SESSION_ID
        with _LOCK:
            with _get_connection() as conn:
                cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                conn.commit()
                deleted = cur.rowcount > 0

        if deleted and _ACTIVE_SESSION_ID == session_id:
            self._ensure_default_session()
        return deleted


_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
