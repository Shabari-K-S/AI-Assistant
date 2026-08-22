#!/usr/bin/env python3
"""Automated Verification Test for Athena Slash Commands, Skills (.athena/skills/), and Agents (.athena/agents/).
"""

import json
import os
import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from skills_engine import SkillsEngine, get_skills_engine
from multi_agent_dispatcher import MultiAgentDispatcher, get_agent_dispatcher


def test_skills_engine():
    print("\n--- 1. Testing Skills Engine & .athena/skills/ ---")
    engine = get_skills_engine()
    skills = engine.discover_skills()
    print(f"✅ Discovered {len(skills)} baseline skills:")
    for s in skills:
        print(f"   • {s.name} ({s.category}) — Triggers: {s.triggers}")
    assert len(skills) >= 5, "Expected at least 5 default skills"

    # Test direct rule learning
    print("\n--- Testing /learn with direct custom rule ---")
    res1 = engine.learn_skill(
        "Always execute npm run lint and python3 -m pytest before making git commits.",
        name_hint="strict_ci_validation",
        category="coding",
    )
    print(res1)
    skill = engine.get_skill("strict_ci_validation")
    assert skill is not None, "Failed to learn strict_ci_validation skill"
    print(f"✅ Skill verified on disk at: {skill.file_path}")

    # Test autonomous topic search mode
    print("\n--- Testing /learn with topic query ('GraphQL security testing') ---")
    res2 = engine.learn_skill("GraphQL security testing", category="security")
    print(res2)
    graphql_skill = engine.get_skill("graphql_security_testing")
    assert graphql_skill is not None, "Failed to learn graphql_security_testing"
    print(f"✅ Auto-researched skill saved: {graphql_skill.name}")
    print(f"   Sources ingested: {graphql_skill.sources}")


def test_agent_dispatcher():
    print("\n--- 2. Testing Sub-Agents & .athena/agents/ ---")
    dispatcher = get_agent_dispatcher()
    agents = dispatcher.discover_agents()
    print(f"✅ Discovered {len(agents)} specialized agent profiles:")
    for a in agents:
        print(f"   • {a.name} — Role: {a.role}")
    assert len(agents) >= 5, "Expected at least 5 default agent profiles"

    # Test dispatching a sub-agent by profile name
    print("\n--- Testing agent dispatch ('recon_specialist') ---")
    dispatch_msg = dispatcher.dispatch_agent_by_name("recon_specialist", "127.0.0.1")
    print(dispatch_msg)

    # Query tasks
    status_report = dispatcher.query_tasks()
    print(status_report)


def test_slash_command_execution():
    print("\n--- 3. Testing Slash Command Router ---")
    from evbridge import _Handler, Bus
    bus = Bus()
    handler = _Handler.__new__(_Handler)

    handled, reply = handler._execute_slash_command("/help", bus)
    assert handled and "ATHENA SLASH COMMANDS" in reply
    print("✅ /help handled successfully")

    handled, reply = handler._execute_slash_command("/skill list", bus)
    assert handled and "Athena Skill Registry" in reply
    print("✅ /skill list handled successfully")

    handled, reply = handler._execute_slash_command("/agent list", bus)
    assert handled and "Athena Modular Agent Registry" in reply
    print("✅ /agent list handled successfully")

    handled, reply = handler._execute_slash_command("/learn https://example.com", bus)
    assert handled and "Skill Synthesis Initiated" in reply
    print("✅ /learn <url> handled successfully (asynchronous synthesis)")

    print("\n🎉 ALL BACKEND TESTS PASSED!")


if __name__ == "__main__":
    test_skills_engine()
    test_agent_dispatcher()
    test_slash_command_execution()
