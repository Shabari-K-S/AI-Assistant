#!/usr/bin/env python3
"""Test script for S.A.R.A. Human-Like Speech Sanitizer & Symbol Eliminator."""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from main import clean_for_speech
from tts import chunk_sentences, clean_speech_text


def test_speech_cleaner():
    print("=" * 70)
    print("🗣️ S.A.R.A. HUMAN-LIKE SPEECH SANITIZER TEST SUITE")
    print("=" * 70)

    # Test 1: Markdown, Symbols, Emojis, URLs, Code Blocks
    input_text = """
    ### 🧠 1. S.A.R.A. Status & Battery **Report**:
    - Battery: 95% (Charging) at 32.5°C
    - Status: ✅ ONLINE & Active!
    - Check out [Documentation](http://example.com/docs)
    - Target: 10.10.11.23 -> In Scope
    ```python
    print("hello world")
    ```
    | Service | Port |
    | HTTP | 8080 |
    """

    cleaned = clean_for_speech(input_text)
    print("\n1. Original Input Text:\n", input_text)
    print("\n2. Sanitized Speech Output:\n", cleaned)

    # Assertions
    assert "🧠" not in cleaned
    assert "✅" not in cleaned
    assert "###" not in cleaned
    assert "**" not in cleaned
    assert "```" not in cleaned
    assert "|" not in cleaned
    assert "http" not in cleaned
    assert "%" not in cleaned and "percent" in cleaned
    assert "&" not in cleaned and "and" in cleaned
    assert "degrees Celsius" in cleaned
    assert "->" not in cleaned and "to" in cleaned

    print("\n   ✅ Zero emojis, zero markdown symbols, and natural conversational conversions verified.")

    # Test 2: Sentence chunking for TTS
    chunks = chunk_sentences(cleaned)
    print(f"\n3. Sentence Chunks for Neural TTS ({len(chunks)} chunks):")
    for i, c in enumerate(chunks, 1):
        print(f"   Chunk {i}: '{c}'")
        assert not any(sym in c for sym in ["*", "#", "`", "[", "]", "{", "}", "\\", "=", "|", "🧠", "✅"])

    print("\n" + "=" * 70)
    print("✅ ALL SPEECH SANITIZATION & HUMAN-LIKE VOCAL TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_speech_cleaner()
