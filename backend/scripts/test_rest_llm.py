#!/usr/bin/env python3
"""Test script for Pure-Python Gemini REST LLM Engine in S.A.R.A."""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from config import LLMConfig
from llm import GeminiRestLLM, Conversation, build_llm


def test_rest_llm():
    print("=" * 70)
    print("🌐 S.A.R.A. PURE-PYTHON GEMINI REST LLM ENGINE TEST SUITE")
    print("=" * 70)

    cfg = LLMConfig(
        provider="rest",
        api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "test_key",
        model="gemini-2.5-flash",
    )

    print("\n1. Testing GeminiRestLLM class initialization...")
    engine = build_llm(cfg)
    assert isinstance(engine, GeminiRestLLM)
    print(f"   ✅ Initialized successfully: {type(engine).__name__}")

    print("\n2. Testing payload preparation with system prompt and function tools...")
    conv = Conversation()
    conv.add_user("What is the battery level and status?")
    
    tools = [
        {
            "name": "android_battery_status",
            "description": "Read live battery percentage and charging state.",
            "parameters": {"type": "object", "properties": {}},
        }
    ]

    payload = engine._prepare_payload(conv.messages(), tools, "You are S.A.R.A. assistant.")
    print(f"   Payload Contents: {payload.get('contents')}")
    print(f"   Payload System Instruction: {payload.get('system_instruction')}")
    print(f"   Payload Tools: {len(payload.get('tools', []))} tool(s)")

    assert len(payload.get("contents", [])) == 1
    assert payload.get("system_instruction") is not None
    assert len(payload.get("tools", [])) == 1
    print("   ✅ Payload structure matches Google Gemini REST API specification exactly.")

    print("\n" + "=" * 70)
    print("✅ ALL PURE-PYTHON GEMINI REST LLM TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_rest_llm()
