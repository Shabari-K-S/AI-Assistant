#!/usr/bin/env python3
"""Test script for LlamaCppLLM engine."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import LLMConfig, load_config
from llm import Conversation, LlamaCppLLM, build_llm


class TestLlamaCppLLM(unittest.TestCase):
    def test_config_defaults(self):
        cfg = load_config()
        self.assertTrue(hasattr(cfg.llm, "llama_cpp_base_url"))
        self.assertTrue(hasattr(cfg.llm, "llama_cpp_model"))
        self.assertTrue(hasattr(cfg.llm, "llama_cpp_ctx_size"))
        self.assertTrue(hasattr(cfg.llm, "llama_cpp_threads"))

    def test_factory_builder(self):
        cfg = LLMConfig(
            api_key="",
            provider="llama_cpp",
            llama_cpp_base_url="http://127.0.0.1:8080",
            llama_cpp_model="qwen2.5-1.5b-instruct",
        )
        engine = build_llm(cfg)
        self.assertIsInstance(engine, LlamaCppLLM)
        self.assertEqual(engine._base_url, "http://127.0.0.1:8080")
        self.assertFalse(engine.is_healthy())  # Server not running yet, should return False gracefully

    def test_offline_connection_error(self):
        cfg = LLMConfig(
            api_key="",
            provider="llama_cpp",
            llama_cpp_base_url="http://127.0.0.1:9999",  # non-existent port
            timeout_s=1,
        )
        engine = LlamaCppLLM(cfg)
        conv = Conversation()
        conv.add_user("Hello")

        with self.assertRaises(RuntimeError) as ctx:
            list(engine.stream_response(conv, [], "System prompt"))
        self.assertIn("Cannot connect to llama.cpp server", str(ctx.exception))

    @patch("httpx.Client.stream")
    def test_mock_streaming_response(self, mock_stream):
        # Mock SSE streaming response context manager from llama-server
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world!"}}]}',
            'data: [DONE]',
        ]
        mock_stream.return_value.__enter__.return_value = mock_response

        cfg = LLMConfig(
            api_key="",
            provider="llama_cpp",
            llama_cpp_base_url="http://127.0.0.1:8080",
        )
        engine = LlamaCppLLM(cfg)
        conv = Conversation()
        conv.add_user("Hi")

        chunks = list(engine.stream_response(conv, [], "System prompt"))
        self.assertEqual("".join(chunks), "Hello world!")
        # Verify conversation history updated
        messages = conv.messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[1]["role"], "model")
        self.assertEqual(messages[1]["parts"][0]["text"], "Hello world!")


if __name__ == "__main__":
    unittest.main()
