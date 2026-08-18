#!/usr/bin/env python3
"""Test script for S.A.R.A. Long-Term Vector Memory & Knowledge Graph Engine."""

import os
import sys
import tempfile
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from memory_engine import MemoryEngine


def test_memory_engine():
    print("=" * 70)
    print("🧠 S.A.R.A. LONG-TERM VECTOR MEMORY & KNOWLEDGE GRAPH TEST SUITE")
    print("=" * 70)

    # Use a temporary SQLite database for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = Path(tmp_db.name)

    try:
        engine = MemoryEngine(db_path=tmp_db_path)

        # 1. Store Test Facts
        print("\n1. Storing diverse personal and technical facts...")
        id1 = engine.store_fact("The user prefers TypeScript with strict mode and Tailwind CSS v4", category="preference")
        id2 = engine.store_fact("Staging backend runs on port 8080 using PostgreSQL database", category="project")
        id3 = engine.store_fact("Production server IP is 192.168.1.150 and SSH user is deploy_admin", category="credential")
        id4 = engine.store_fact("The user listens to synthwave and lofi beats while coding", category="habit")
        id5 = engine.store_fact("Hack The Box machine active target is 10.10.11.23 named Surveillance", category="project")

        print(f"   Stored 5 distinct memory records: [{id1}, {id2}, {id3}, {id4}, {id5}]")
        assert len(engine.list_all_memories()) == 5

        # 2. Test Semantic & Keyword Recall
        print("\n2. Testing Semantic Recall queries...")

        # Query 1: Staging port query
        q1 = "what port is staging running on?"
        res1 = engine.recall(q1, limit=2)
        print(f"   Query: '{q1}'")
        for r in res1:
            print(f"   -> [{r['category']}] {r['text']} (Score: {r['score']})")
        assert len(res1) > 0
        assert "8080" in res1[0]["text"]
        print("   ✅ Accurately retrieved staging port 8080 fact.")

        # Query 2: Coding preference query
        q2 = "which frontend styling and language does the user like?"
        res2 = engine.recall(q2, limit=2)
        print(f"\n   Query: '{q2}'")
        for r in res2:
            print(f"   -> [{r['category']}] {r['text']} (Score: {r['score']})")
        assert len(res2) > 0
        assert "TypeScript" in res2[0]["text"] or "Tailwind" in res2[0]["text"]
        print("   ✅ Accurately retrieved TypeScript & Tailwind preference.")

        # Query 3: Music preference query
        q3 = "what songs or background music to play?"
        res3 = engine.recall(q3, limit=2)
        print(f"\n   Query: '{q3}'")
        for r in res3:
            print(f"   -> [{r['category']}] {r['text']} (Score: {r['score']})")
        assert len(res3) > 0
        assert "synthwave" in res3[0]["text"] or "lofi" in res3[0]["text"]
        print("   ✅ Accurately retrieved music habits.")

        # 3. Test Knowledge Graph Triples
        print("\n3. Testing Knowledge Graph Entity Triples...")
        staging_graph = engine.query_graph("staging")
        print(f"   Knowledge graph links for 'staging': {len(staging_graph)} triples")
        for g in staging_graph:
            print(f"   -> ({g['subject']}) --[{g['predicate']}]--> ({g['object']})")
        assert len(staging_graph) > 0
        print("   ✅ Knowledge graph entity relations verified.")

        # 4. Test Prompt Context Formatting
        print("\n4. Testing Prompt Injection Context Block...")
        prompt_block = engine.get_relevant_context_prompt("check staging server port")
        print(f"   Formatted Prompt Block:\n{prompt_block}")
        assert "8080" in prompt_block
        print("   ✅ Context block generated cleanly for LLM injection.")

        # 5. Test Memory Deletion
        print("\n5. Testing Memory Deletion...")
        deleted = engine.delete_memory(id4)
        assert deleted is True
        assert len(engine.list_all_memories()) == 4
        print("   ✅ Memory deletion verified.")

        print("\n" + "=" * 70)
        print("✅ ALL LONG-TERM VECTOR MEMORY & KNOWLEDGE GRAPH TESTS PASSED!")
        print("=" * 70)

    finally:
        if tmp_db_path.exists():
            tmp_db_path.unlink()


if __name__ == "__main__":
    test_memory_engine()
