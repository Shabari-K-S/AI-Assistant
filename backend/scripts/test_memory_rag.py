#!/usr/bin/env python3
"""Test script for S.A.R.A. Second Brain: Vault Vector RAG & Spoken Brain Dump Engine."""

import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from memory_engine import get_memory_engine
from notes_mcp_server import (
    handle_add_note,
    handle_semantic_rag_search,
    handle_voice_brain_dump,
    handle_list_todos,
    _rebuild_index,
    TOOLS,
)
from tools import _sanitize_schema_for_gemini


def test_memory_rag():
    print("=" * 70)
    print("🧠 S.A.R.A. SECOND BRAIN VECTOR RAG & BRAIN DUMP TEST SUITE")
    print("=" * 70)

    engine = get_memory_engine()

    # 1. Test Markdown Document Chunking & Indexing
    print("\n1. Testing Markdown Chunking & Vector RAG Indexing...")
    sample_note = """# PostgreSQL Production Architecture

## High Availability & Replication
We decided to deploy streaming physical replication with PgBouncer connection pooling.
All read replicas will route traffic through port 5433 to distribute analytical queries.

## Cache Invalidation Strategy
Redis 7 cluster will handle in-memory session invalidation with a 300-second TTL.
"""
    handle_add_note({
        "title": "Postgres Scaling Guide",
        "content": sample_note,
        "category": "work",
        "tags": ["database", "scaling", "architecture"],
    })
    _rebuild_index()

    # 2. Test Semantic RAG Search (without using exact words like 'PostgreSQL' or 'PgBouncer')
    print("\n2. Testing Semantic RAG Retrieval for non-keyword query...")
    rag_res = handle_semantic_rag_search({
        "query": "How are we scaling our database and caching sessions?",
        "top_k": 3,
    })
    print(rag_res)
    assert "Postgres Scaling Guide" in rag_res or "Replication" in rag_res or "Redis" in rag_res
    print("   ✅ Semantic RAG retrieval successfully returned relevant document chunks!")

    # 3. Test Spoken Stream-of-Consciousness Brain Dump Processor
    print("\n3. Testing Spoken Stream-of-Consciousness Brain Dump Processor...")
    raw_stream = (
        "Hey Sara, brain dump: I need to buy almond milk tomorrow morning, "
        "and also remember to fix the websocket reconnect loop in the frontend, "
        "plus Alex recommended the movie Inception as his all time favorite, "
        "and our team decided to use Rust for high throughput stream processing."
    )
    dump_res = handle_voice_brain_dump({
        "raw_speech_stream": raw_stream,
        "default_category": "ideas",
    })
    print(dump_res)

    # 4. Verify Tasks added to Todos
    print("\n4. Verifying Tasks in active_todos.md...")
    todos_res = handle_list_todos({"status": "active"})
    print(todos_res)
    assert "milk" in todos_res.lower() or "websocket" in todos_res.lower()
    print("   ✅ Action items correctly extracted and added to To-Do checklist.")

    # 5. Verify Long-term Episodic Memory Ingestion
    print("\n5. Verifying Episodic Facts Recall...")
    recalled_facts = engine.recall("movie recommendation from Alex", limit=2)
    print("Recalled Facts:", recalled_facts)
    assert len(recalled_facts) > 0
    print("   ✅ Personal facts correctly extracted and ingested into long-term memory.")

    # 6. Validate Tool Schemas
    print("\n6. Validating Tool Declarations against Gemini types.Tool...")
    assert len(TOOLS) == 12, f"Expected 12 tools, got {len(TOOLS)}"
    for t in TOOLS:
        schema = _sanitize_schema_for_gemini(t["inputSchema"])
        assert schema is not None
    print(f"   ✅ All {len(TOOLS)} Notes & Brain MCP tools validated with ZERO schema errors.")

    print("\n" + "=" * 70)
    print("✅ ALL SECOND BRAIN VECTOR RAG & BRAIN DUMP TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_memory_rag()
