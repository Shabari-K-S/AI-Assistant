#!/usr/bin/env python3
"""S.A.R.A. Long-Term Vector Memory & Knowledge Graph Engine.

Provides permanent semantic episodic recall and entity-relation graph storage
using a local zero-latency SQLite vector/text database (backend/data/memory/memory.db).
Automatically indexes user preferences, technical configurations, project details,
and life habits, injecting relevant context into reasoning turns.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("athena.memory")

DATA_DIR = Path(__file__).resolve().parent / "data" / "memory"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "memory.db"


STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "which", "this", "that", "these", "those", "then", "just", "so", "than",
    "such", "both", "through", "about", "for", "is", "of", "while", "during",
    "to", "from", "in", "out", "on", "off", "over", "under", "again", "further",
    "when", "where", "why", "how", "all", "any", "each", "few", "more", "most",
    "other", "some", "no", "nor", "not", "only", "own", "same", "too", "very",
    "can", "will", "should", "now", "user", "i", "me", "my", "we", "our", "you",
    "your", "he", "she", "it", "they", "them", "his", "her", "their", "does", "do", "did", "with"
}


SEMANTIC_ONTOLOGY: dict[str, list[str]] = {
    "typescript": ["language", "frontend", "code", "programming", "js", "ts"],
    "javascript": ["language", "frontend", "code", "programming", "js"],
    "python": ["language", "backend", "code", "programming", "py"],
    "rust": ["language", "systems", "code", "programming"],
    "tailwind": ["css", "styling", "frontend", "ui", "design", "styles"],
    "css": ["styling", "frontend", "ui", "design", "styles"],
    "react": ["frontend", "framework", "ui", "component"],
    "postgres": ["database", "backend", "sql", "db", "storage"],
    "postgresql": ["database", "backend", "sql", "db", "storage"],
    "mysql": ["database", "backend", "sql", "db"],
    "sqlite": ["database", "storage", "db", "file"],
    "port": ["network", "server", "endpoint", "connection"],
    "server": ["backend", "network", "host", "infrastructure"],
    "synthwave": ["music", "songs", "audio", "track", "background"],
    "lofi": ["music", "songs", "audio", "track", "beats"],
    "prefer": ["preference", "likes", "favorite", "choice"],
    "prefers": ["preference", "likes", "favorite", "choice"],
    "favourite": ["preference", "likes", "favorite", "choice"],
    "favorite": ["preference", "likes", "favorite", "choice"],
}


def _tokenize(text: str, expand: bool = False) -> list[str]:
    """Normalize text into lowercase alphanumeric tokens with optional semantic expansion."""
    raw_tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())
    clean_tokens = [t for t in raw_tokens if t not in STOP_WORDS]
    if not expand:
        return clean_tokens

    expanded = list(clean_tokens)
    for tok in clean_tokens:
        if tok in SEMANTIC_ONTOLOGY:
            expanded.extend(SEMANTIC_ONTOLOGY[tok])
    return expanded


def _compute_tf_idf_vector(text: str, vocab: dict[str, int], idf: dict[str, float]) -> list[float]:
    """Compute a normalized TF-IDF vector against a dynamic vocabulary and IDF map."""
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * len(vocab)

    tf: dict[str, int] = {}
    for tok in tokens:
        tf[tok] = tf.get(tok, 0) + 1

    vec = [0.0] * len(vocab)
    for word, idx in vocab.items():
        if word in tf:
            tf_val = float(tf[word]) / len(tokens)
            idf_val = idf.get(word, 1.0)
            vec[idx] = tf_val * idf_val

    # Normalize vector to unit length
    mag = math.sqrt(sum(v * v for v in vec))
    if mag > 1e-6:
        vec = [v / mag for v in vec]
    return vec


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two unit vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    return sum(a * b for a, b in zip(vec1, vec2))


class MemoryEngine:
    """Zero-dependency local hybrid vector memory and knowledge graph manager."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags TEXT,
                    importance REAL DEFAULT 1.0,
                    access_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_triples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    context TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE(subject, predicate, object)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vault_chunks (
                    id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    note_title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    heading TEXT,
                    content TEXT NOT NULL,
                    tags TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_category ON episodic_memories(category)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_triples_sub_pred ON knowledge_triples(subject, predicate)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_file ON vault_chunks(file_path)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_cat ON vault_chunks(category)
                """
            )
            conn.commit()

    def store_fact(
        self,
        text: str,
        category: str = "general",
        tags: list[str] | None = None,
        importance: float = 1.0,
    ) -> str:
        """Store a new fact or user preference in long-term memory."""
        # Sanitize and cap length to prevent database inflation / DoS
        text = text.strip()[:2000]
        if not text:
            return ""

        mem_id = f"mem-{int(time.time() * 1000)}-{abs(hash(text)) % 10000}"
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        tags_str = ",".join(tags) if tags else ""

        with self._get_conn() as conn:
            # Check for exact duplicate
            cur = conn.execute("SELECT id FROM episodic_memories WHERE text = ?", (text,))
            existing = cur.fetchone()
            if existing:
                conn.execute(
                    "UPDATE episodic_memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                    (now, existing["id"]),
                )
                conn.commit()
                mem_id = existing["id"]
            else:
                conn.execute(
                    """
                    INSERT INTO episodic_memories (id, text, category, tags, importance, access_count, created_at, last_accessed_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (mem_id, text, category, tags_str, importance, now, now),
                )
                conn.commit()

        # Automatically extract knowledge graph entity triples
        self._extract_and_store_triples(text)
        log.info("Stored long-term memory [%s]: %s", mem_id, text[:60])
        return mem_id

    def recall(self, query: str, limit: int = 4, category: str | None = None) -> list[dict[str, Any]]:
        """Perform hybrid semantic and keyword search across long-term memories."""
        query = query.strip()
        if not query:
            return []

        query_tokens = set(_tokenize(query, expand=True))
        if not query_tokens:
            return []

        with self._get_conn() as conn:
            if category:
                cur = conn.execute(
                    "SELECT id, text, category, tags, importance, created_at FROM episodic_memories WHERE category = ?",
                    (category,),
                )
            else:
                cur = conn.execute(
                    "SELECT id, text, category, tags, importance, created_at FROM episodic_memories"
                )
            rows = cur.fetchall()

        if not rows:
            return []

        # Build dynamic vocabulary and document frequency from all memory texts with semantic expansion
        all_docs = [_tokenize(r["text"] + " " + (r["tags"] or "") + " " + r["category"], expand=True) for r in rows]
        vocab: dict[str, int] = {}
        df: dict[str, int] = {}
        num_docs = len(all_docs)

        for doc_tokens in all_docs + [_tokenize(query, expand=True)]:
            unique_doc_tokens = set(doc_tokens)
            for tok in doc_tokens:
                if tok not in vocab:
                    vocab[tok] = len(vocab)
            for tok in unique_doc_tokens:
                df[tok] = df.get(tok, 0) + 1

        idf: dict[str, float] = {}
        for word, count in df.items():
            idf[word] = math.log((num_docs + 1) / (count + 0.5)) + 1.0

        query_vec = _compute_tf_idf_vector(query, vocab, idf)

        scored_results: list[tuple[float, dict[str, Any]]] = []
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        matched_ids = []

        for r, r_tokens_list in zip(rows, all_docs):
            r_text = r["text"]
            r_tokens = set(r_tokens_list)

            # 1. Cosine similarity
            r_vec = _compute_tf_idf_vector(r_text, vocab, idf)
            cosine_score = _cosine_similarity(query_vec, r_vec)

            # 2. Token overlap ratio (Jaccard / Keyword matching on filtered content words)
            overlap = len(query_tokens & r_tokens) / max(1, len(query_tokens))

            # 3. Exact discriminative keyword match
            shared_rare = [t for t in query_tokens & r_tokens if idf.get(t, 1.0) > 1.1]
            rare_boost = 0.40 if shared_rare else 0.0

            # Composite hybrid score
            final_score = (cosine_score * 0.45) + (overlap * 0.35) + rare_boost + (r["importance"] * 0.10)

            if final_score > 0.18:
                item = {
                    "id": r["id"],
                    "text": r_text,
                    "category": r["category"],
                    "tags": r["tags"].split(",") if r["tags"] else [],
                    "score": round(final_score, 3),
                    "created_at": r["created_at"],
                }
                scored_results.append((final_score, item))
                matched_ids.append(r["id"])

        # Update access count for matched memories
        if matched_ids:
            with self._get_conn() as conn:
                for m_id in matched_ids[:limit]:
                    conn.execute(
                        "UPDATE episodic_memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                        (now, m_id),
                    )
                conn.commit()

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_results[:limit]]

    def delete_memory(self, memory_id: str) -> bool:
        """Remove a specific memory by its ID."""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM episodic_memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cur.rowcount > 0

    def list_all_memories(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all stored memories ordered by recency."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT id, text, category, tags, importance, access_count, created_at, last_accessed_at FROM episodic_memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    # ----------------------------------------------------------------------- #
    # Knowledge Graph Operations
    # ----------------------------------------------------------------------- #

    def store_triple(self, subject: str, predicate: str, obj: str, confidence: float = 1.0, context: str = "") -> None:
        """Store an entity-relationship-entity triple in the knowledge graph."""
        sub = subject.strip()
        pred = predicate.strip().lower()
        obj = obj.strip()
        if not sub or not pred or not obj:
            return

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_triples (subject, predicate, object, confidence, context, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject, predicate, object) DO UPDATE SET
                    confidence = excluded.confidence,
                    context = excluded.context,
                    updated_at = excluded.updated_at
                """,
                (sub, pred, obj, confidence, context, now),
            )
            conn.commit()

    def query_graph(self, entity: str) -> list[dict[str, str]]:
        """Find all relationships connected to a specific entity."""
        e_clean = entity.strip().lower()
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT subject, predicate, object, confidence, context FROM knowledge_triples
                WHERE LOWER(subject) LIKE ? OR LOWER(object) LIKE ?
                ORDER BY confidence DESC
                """,
                (f"%{e_clean}%", f"%{e_clean}%"),
            )
            return [dict(r) for r in cur.fetchall()]

    def _extract_and_store_triples(self, text: str) -> None:
        """Extract entity relationships using heuristic semantic patterns."""
        patterns = [
            # "User prefers TypeScript" -> (User, prefers, TypeScript)
            r"(?i)\b(user|i|we)\s+(prefer|likes?|uses?|wants?)\s+([^,.;]+)",
            # "Staging server uses port 8080" -> (Staging server, uses_port, 8080)
            r"(?i)\b([a-zA-Z0-9_\-\s]+?)\s+(?:uses|runs on|is on)\s+(?:port\s+)?(\d{2,5})",
            # "Production database is Postgres" -> (Production database, is, Postgres)
            r"(?i)\b([a-zA-Z0-9_\-\s]+?)\s+(is|uses|configured with)\s+([a-zA-Z0-9_\-]+)",
        ]

        for pat in patterns:
            matches = re.finditer(pat, text)
            for m in matches:
                groups = m.groups()
                if len(groups) == 3:
                    sub, pred, obj = groups[0].strip(), groups[1].strip().lower(), groups[2].strip()
                    self.store_triple(sub, pred, obj, confidence=0.9, context=text[:100])
                elif len(groups) == 2:
                    sub, port = groups[0].strip(), groups[1].strip()
                    self.store_triple(sub, "runs_on_port", port, confidence=0.95, context=text[:100])

    def _chunk_markdown(self, body: str, title: str = "") -> list[tuple[str, str]]:
        """Split a markdown document into semantic sections based on headings and paragraph boundaries."""
        if not body.strip():
            return []

        lines = body.splitlines()
        chunks: list[tuple[str, str]] = []
        current_heading = title or "Overview"
        current_lines: list[str] = []

        for line in lines:
            header_match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
            if header_match:
                if current_lines:
                    text_block = "\n".join(current_lines).strip()
                    if text_block:
                        chunks.append((current_heading, text_block))
                    current_lines = []
                current_heading = header_match.group(2).strip()
            else:
                current_lines.append(line)
                if len("\n".join(current_lines)) > 800 and not line.strip():
                    text_block = "\n".join(current_lines).strip()
                    if text_block:
                        chunks.append((current_heading, text_block))
                    current_lines = []

        if current_lines:
            text_block = "\n".join(current_lines).strip()
            if text_block:
                chunks.append((current_heading, text_block))

        return chunks

    def index_vault_file(self, rel_path: str, frontmatter: dict[str, Any], body: str) -> int:
        """Chunk and index a markdown vault file into the vector search database."""
        title = str(frontmatter.get("title") or Path(rel_path).stem.replace("_", " ").title())
        category = str(frontmatter.get("category") or Path(rel_path).parent.name or "general")
        tags = frontmatter.get("tags", [])
        tags_str = ",".join(tags) if isinstance(tags, list) else str(tags)
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        chunks = self._chunk_markdown(body, title=title)
        if not chunks:
            chunks = [(title, body.strip() or title)]

        with self._get_conn() as conn:
            # Delete old chunks for this file
            conn.execute("DELETE FROM vault_chunks WHERE file_path = ?", (rel_path,))

            for idx, (heading, content) in enumerate(chunks):
                chunk_id = f"vchunk-{abs(hash(rel_path)) % 1000000}-{idx}"
                conn.execute(
                    """
                    INSERT INTO vault_chunks (id, file_path, note_title, category, heading, content, tags, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (chunk_id, rel_path, title, category, heading, content, tags_str, now),
                )
            conn.commit()

        log.debug("Indexed %d vector chunks for vault file '%s'", len(chunks), rel_path)
        return len(chunks)

    def remove_vault_file(self, rel_path: str) -> None:
        """Remove a deleted vault file from the vector search index."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM vault_chunks WHERE file_path = ?", (rel_path,))
            conn.commit()

    def search_vault(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Perform semantic hybrid vector search across all notes in the Markdown vault."""
        query = query.strip()
        if not query:
            return []

        query_tokens = set(_tokenize(query, expand=True))
        if not query_tokens:
            return []

        with self._get_conn() as conn:
            if category:
                cur = conn.execute(
                    "SELECT id, file_path, note_title, category, heading, content, tags FROM vault_chunks WHERE category = ?",
                    (category,),
                )
            else:
                cur = conn.execute(
                    "SELECT id, file_path, note_title, category, heading, content, tags FROM vault_chunks"
                )
            rows = cur.fetchall()

        if not rows:
            return []

        # Build dynamic vocabulary and document frequency
        all_docs = [_tokenize(r["note_title"] + " " + (r["heading"] or "") + " " + r["content"] + " " + (r["tags"] or ""), expand=True) for r in rows]
        vocab: dict[str, int] = {}
        df: dict[str, int] = {}
        num_docs = len(all_docs)

        for doc_tokens in all_docs + [_tokenize(query, expand=True)]:
            unique_tokens = set(doc_tokens)
            for tok in doc_tokens:
                if tok not in vocab:
                    vocab[tok] = len(vocab)
            for tok in unique_tokens:
                df[tok] = df.get(tok, 0) + 1

        idf: dict[str, float] = {}
        for word, count in df.items():
            idf[word] = math.log((num_docs + 1) / (count + 0.5)) + 1.0

        query_vec = _compute_tf_idf_vector(query, vocab, idf)

        scored: list[tuple[float, dict[str, Any]]] = []
        for row, doc_tokens in zip(rows, all_docs):
            doc_text = row["note_title"] + " " + (row["heading"] or "") + " " + row["content"] + " " + (row["tags"] or "")
            doc_vec = _compute_tf_idf_vector(doc_text, vocab, idf)
            cos_sim = _cosine_similarity(query_vec, doc_vec)

            # Keyword overlap boost
            overlap = len(query_tokens.intersection(doc_tokens))
            keyword_score = float(overlap) / max(1, len(query_tokens))

            # Exact title or heading matching boost
            title_boost = 0.25 if any(q in row["note_title"].lower() for q in query_tokens) else 0.0
            heading_boost = 0.15 if row["heading"] and any(q in row["heading"].lower() for q in query_tokens) else 0.0

            final_score = (0.55 * cos_sim) + (0.30 * keyword_score) + title_boost + heading_boost
            if final_score > 0.08:
                scored.append((
                    final_score,
                    {
                        "id": row["id"],
                        "file_path": row["file_path"],
                        "title": row["note_title"],
                        "category": row["category"],
                        "heading": row["heading"],
                        "content": row["content"],
                        "tags": [t.strip() for t in (row["tags"] or "").split(",") if t.strip()],
                        "score": round(final_score, 4),
                    },
                ))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def get_relevant_context_prompt(self, user_prompt: str, limit: int = 4) -> str:
        """Search memory and return formatted context block for LLM prompt injection."""
        text_clean = user_prompt.strip().lower()
        if len(text_clean.split()) <= 2 and text_clean in {
            "hi", "hello", "hey", "sup", "yo", "good morning", "good evening", "how are you", "what's up", "who are you"
        }:
            return ""

        memories = self.recall(user_prompt, limit=limit)
        vault_hits = self.search_vault(user_prompt, top_k=2)

        if not memories and not vault_hits:
            return ""

        lines = ["\n[🧠 Long-Term Memory Recall]:"]
        for m in memories:
            lines.append(f"- ({m['category'].upper()}) {m['text']}")
        for v in vault_hits:
            lines.append(f"- (NOTE: {v['title']} > {v['heading']}) {v['content'][:200]}...")
        lines.append("")
        return "\n".join(lines)


# Singleton memory engine instance
_memory_engine_instance: MemoryEngine | None = None


def get_memory_engine() -> MemoryEngine:
    global _memory_engine_instance
    if _memory_engine_instance is None:
        _memory_engine_instance = MemoryEngine()
    return _memory_engine_instance

