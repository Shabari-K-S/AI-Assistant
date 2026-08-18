"""Stage 3: the LLM "brain" — Gemma 4 via Google's Gemini API (default) or a
local Ollama server, with tool use.

The engine streams the response token-by-token so the TTS stage (stage 4) can
start on the first completed sentence.

Design notes
------------
* `stream_response` yields text deltas as they arrive. Internally it runs the
  provider tool-calling loop: when the model requests a tool, the registry
  executes it and the conversation continues — any number of tool rounds per
  user turn — until the model produces a final text response. The caller never
  sees the tool boundaries unless it wants to.
* Conversation is a rolling in-memory window of whole user turns (trimming is
  turn-aware so a tool_result can never be orphaned from its tool_use).
  Messages are stored in a provider-neutral shape (Gemini-style parts) and
  serialized per provider by each engine.
* Latency is logged in the same style as `stt.py`:
  `llm: ttft=<time to first streamed token> total=<time to final response>`.

Providers
---------
* gemini (default): Google AI Studio API, model `gemma-4-31b-it` (free tier).
  Needs GOOGLE_API_KEY. SDK: google-genai.
* ollama: local OpenAI-compatible `/v1/chat/completions` endpoint (default
  http://localhost:11434). No API key; needs `ollama pull gemma4:e4b` (or
  another tag) on the machine.

v2 extension points
-------------------
- Persistent memory: swap `Conversation` for a store-backed history (SQLite /
  vector store) behind the same `messages()` contract.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Callable, Iterator

from config import LLMConfig

log = logging.getLogger("ev.llm")

ToolExecutor = Callable[[str, dict], str]


class Conversation:
    """Rolling in-memory message history (the system prompt is injected separately).

    Messages are stored as provider-neutral Gemini-style dicts:
        {"role": "user", "parts": [{"text": "..."}]}                (plain turn)
        {"role": "user", "parts": [{"functionResponse": {...}}]}    (tool result)
        {"role": "model", "parts": [{"text": ...}, {"functionCall": {...}}]}
    """

    def __init__(self, max_turns: int = 20) -> None:
        self._max_turns = max_turns
        self._messages: deque[dict] = deque()

    def add_user(self, text: str) -> None:
        self._messages.append({"role": "user", "parts": [{"text": text}]})

    def add_assistant(self, text: str) -> None:
        """Shortcut for a plain text-only assistant message."""
        self._messages.append({"role": "model", "parts": [{"text": text}]})

    def add_assistant_content(self, parts: list[dict]) -> None:
        """Full assistant turn: text and/or functionCall parts. The API requires
        the functionCall parts to be present in the assistant message so the
        follow-up functionResponse messages reference them."""
        self._messages.append({"role": "model", "parts": parts})

    def add_tool_result(
        self, tool_call_id: str | None, name: str, result: str
    ) -> None:
        self._messages.append(
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": tool_call_id,
                            "name": name,
                            "response": {"result": result},
                        }
                    }
                ],
            }
        )

    @staticmethod
    def _is_plain_user(message: dict) -> bool:
        """A user turn that is just text (not a tool-result feedback message)."""
        if message["role"] != "user":
            return False
        return all("text" in part for part in message.get("parts", []))

    def messages(self) -> list[dict]:
        """Windowed history. Trimming only ever drops WHOLE user turns
        (including their tool exchanges): tool_result messages (role 'user'
        with functionResponse parts) are never counted as turns, so an in-flight
        tool exchange can't be split, and the window always starts on a plain
        user message."""
        msgs = list(self._messages)
        if len(msgs) <= self._max_turns * 2:
            return msgs
        total_users = sum(1 for m in msgs if self._is_plain_user(m))
        to_drop = total_users - self._max_turns
        cut = 0
        seen = 0
        for idx, m in enumerate(msgs):
            if self._is_plain_user(m):
                seen += 1
                if seen > to_drop:
                    cut = idx
                    break
        return msgs[cut:]

    def pop_last_user(self) -> dict | None:
        """Roll back the most recent user turn — pops the user message plus
        everything appended after it (assistant functionCall + tool_result
        rounds) so a failed turn can be dropped while keeping the history
        valid."""
        while self._messages:
            last = self._messages.pop()
            if self._is_plain_user(last):
                return last
        return None

    def clear(self) -> None:
        self._messages.clear()


class LLMEngine(ABC):
    @abstractmethod
    def stream_response(
        self,
        conversation: Conversation,
        tools: list[dict],
        system_prompt: str,
    ) -> Iterator[str]:
        """Yield response text deltas. Tool calls are executed internally."""


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _is_tool_call_part(part: dict) -> bool:
    return "functionCall" in part


def _serialize_openai(messages: list[dict]) -> list[dict]:
    """Convert the neutral Conversation format to OpenAI-compatible messages
    (used by the Ollama endpoint)."""
    out: list[dict] = []
    for msg in messages:
        parts = msg.get("parts", [])
        if msg["role"] == "user":
            if all("text" in p for p in parts):
                out.append({"role": "user", "content": "".join(
                    p["text"] for p in parts
                )})
            else:
                for part in parts:
                    fr = part.get("functionResponse", {})
                    out.append({
                        "role": "tool",
                        "tool_call_id": fr.get("id") or f"call_{fr.get('name', 'tool')}",
                        "content": (fr.get("response") or {}).get("result", ""),
                    })
            continue
        # role == model
        text = "".join(p["text"] for p in parts if "text" in p)
        calls = [
            {
                "id": p["functionCall"].get("id") or f"call_{p['functionCall'].get('name', 'tool')}",
                "type": "function",
                "function": {
                    "name": p["functionCall"].get("name", ""),
                    "arguments": json.dumps(p["functionCall"].get("args") or {}),
                },
            }
            for p in parts
            if "functionCall" in p
        ]
        if calls:
            out.append({
                "role": "assistant",
                "content": text or None,
                "tool_calls": calls,
            })
        else:
            out.append({"role": "assistant", "content": text})
    return out


def _run_tool_round(
    conversation: Conversation,
    parts: list[dict],
    tool_calls: list[dict],
    tool_executor: ToolExecutor | None,
    request_t0: float,
) -> None:
    """Append the assistant turn (text + functionCall parts) and the executed
    tool results, so the model can continue. Tool failures are fed back to
    the model as error text rather than raising."""
    conversation.add_assistant_content(parts)

    for call in tool_calls:
        elapsed = time.perf_counter() - request_t0
        try:
            result = (
                tool_executor(call["name"], call.get("args") or {})
                if tool_executor
                else f"error: no tool executor configured for {call['name']}"
            )
            status = "ok"
        except Exception as exc:  # noqa: BLE001 - executor must never break the loop
            result = f"error: {type(exc).__name__}: {exc}"
            status = "error"
        log.info(
            "llm: tool %s(%s) called at %.3fs -> %s",
            call["name"], json.dumps(call.get("args"))[:120], elapsed, status,
        )
        conversation.add_tool_result(call.get("id"), call["name"], result)


# --------------------------------------------------------------------------- #
# Provider 1: Gemini API (default)
# --------------------------------------------------------------------------- #
class GeminiGemmaLLM(LLMEngine):
    """Gemma 4 via Google's Gemini API (google-genai SDK)."""

    def __init__(self, config: LLMConfig, tool_executor: ToolExecutor | None = None) -> None:
        if not config.api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set (see .env / .env.example)")
        from google import genai
        from google.genai import types

        self._client = genai.Client(
            api_key=config.api_key,
            # NOTE: HttpOptions.timeout is in MILLISECONDS (not seconds!)
            http_options=types.HttpOptions(timeout=config.timeout_s * 1000),
        )
        self._config = config
        self._tool_executor = tool_executor
        self._max_tool_iterations = 4  # cap on tool rounds per user turn

    def _config_dict(self, tools: list[dict], system_prompt: str):
        from google.genai import types

        # gemma-4-31b-it always does a short reasoning pass; hide the thought
        # text so responses are clean. EV_GEMINI_THINKING exposes it (and asks
        # for HIGH thinking where the model supports thinking levels).
        if self._config.gemini_thinking:
            thinking_config = types.ThinkingConfig(
                include_thoughts=True,
                thinking_level=types.ThinkingLevel.HIGH,
            )
        else:
            thinking_config = types.ThinkingConfig(include_thoughts=False)
        return types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self._config.temperature,
            max_output_tokens=self._config.max_tokens,
            tools=[types.Tool(function_declarations=tools)] if tools else None,
            # The SDK auto-executes tool calls (AFC) by default — we run our
            # own safety-gated tool loop, so disable it explicitly.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
            thinking_config=thinking_config,
        )

    def _stream(self, contents: list[dict], tools: list[dict], system_prompt: str):
        """Lazy chunk iterator; retries on 429 rate limit and cascades across model tiers automatically."""
        from google.genai import errors

        # Multi-tier fallback cascade priority queue
        models_to_try = [self._config.model]
        cascade_models = [
            "gemma-4-31b-it",
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-pro",
        ]
        for m in cascade_models:
            if m not in models_to_try:
                models_to_try.append(m)

        last_exc = None
        # Attempt 2 full passes across the entire cascade (allows per-minute TPM buckets to reset)
        for cycle in range(2):
            for i, model_name in enumerate(models_to_try):
                try:
                    stream = self._client.models.generate_content_stream(
                        model=model_name,
                        contents=contents,
                        config=self._config_dict(tools, system_prompt),
                    )
                    for chunk in stream:
                        yield chunk
                    return
                except errors.ClientError as exc:
                    last_exc = exc
                    if exc.code == 429:
                        log.warning(
                            "llm: HTTP 429 (rate limit / TPM quota) on model '%s' — cascading to next model in tier",
                            model_name,
                        )
                        time.sleep(1.0)
                        continue  # immediately cascade to next model!
                    if exc.code in (404, 400):
                        log.warning(
                            "llm: model '%s' unavailable (HTTP %s) — cascading",
                            model_name,
                            exc.code,
                        )
                        continue
                    log.warning("llm client error with '%s': %s — cascading", model_name, exc)
                    continue
                except Exception as exc:
                    last_exc = exc
                    log.warning("llm stream failed on model '%s' (%s) — cascading to fallback", model_name, exc)
                    continue

            # If all models exhausted in cycle 0, pause briefly before cycle 1
            if cycle == 0:
                log.warning("llm: All models in cascade rate-limited; pausing 4s before second pass...")
                time.sleep(4.0)

        if last_exc:
            raise last_exc

    def stream_response(
        self,
        conversation: Conversation,
        tools: list[dict],
        system_prompt: str,
    ) -> Iterator[str]:
        t0 = time.perf_counter()
        ttft: float | None = None  # time from request send to first streamed token

        contents = conversation.messages()
        for _ in range(self._max_tool_iterations + 1):
            parts: list[dict] = []
            seen_calls: dict[str, dict] = {}
            finish_reason: str | None = None

            for chunk in self._stream(contents, tools, system_prompt):
                candidate = chunk.candidates[0] if chunk.candidates else None
                if candidate and candidate.finish_reason:
                    finish_reason = candidate.finish_reason.name
                if not (candidate and candidate.content and candidate.content.parts):
                    continue
                for part in candidate.content.parts:
                    if getattr(part, "thought", False):
                        continue  # reasoning pass — never stream it
                    if part.text:
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                        parts.append({"text": part.text})
                        yield part.text
                    elif part.function_call:
                        call = part.function_call
                        key = call.id or call.name or f"fc{len(seen_calls)}"
                        existing = seen_calls.get(key)
                        if existing:
                            existing["functionCall"]["args"].update(call.args or {})
                        else:
                            entry = {
                                "functionCall": {
                                    "name": call.name,
                                    "args": call.args or {},
                                }
                            }
                            if call.id:
                                entry["functionCall"]["id"] = call.id
                            seen_calls[key] = entry
                            parts.append(entry)

            tool_calls = [p["functionCall"] for p in parts if _is_tool_call_part(p)]
            if tool_calls:
                _run_tool_round(conversation, parts, tool_calls, self._tool_executor, t0)
                contents = conversation.messages()
                continue  # model continues with tool results in context

            # final text response — persist it to history
            text = "".join(p["text"] for p in parts)
            if text.strip():
                conversation.add_assistant(text)
            total = time.perf_counter() - t0
            log.info(
                "llm: ttft=%.3fs total=%.3fs chars=%d model=%s stop=%s",
                ttft or total, total, len(text), self._config.model, finish_reason,
            )
            return

        log.warning(
            "llm: tool loop exceeded %d iterations; stopping", self._max_tool_iterations
        )


# --------------------------------------------------------------------------- #
# Provider 2: local Ollama (OpenAI-compatible)
# --------------------------------------------------------------------------- #
class OllamaGemmaLLM(LLMEngine):
    """Gemma 4 via a local Ollama server's OpenAI-compatible endpoint."""

    def __init__(self, config: LLMConfig, tool_executor: ToolExecutor | None = None) -> None:
        import httpx

        self._client = httpx.Client(timeout=config.timeout_s)
        self._base_url = config.ollama_base_url.rstrip("/")
        self._config = config
        self._tool_executor = tool_executor
        self._max_tool_iterations = 4

    def _open_stream(
        self, messages: list[dict], tools: list[dict], system_prompt: str
    ):
        """POST /v1/chat/completions; returns the streaming response (retries
        once on HTTP 429)."""
        body: dict = {
            "model": self._config.ollama_model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": True,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        if tools:
            body["tools"] = tools

        url = f"{self._base_url}/v1/chat/completions"
        for attempt in (1, 2):
            response = self._client.post(url, json=body)
            if response.status_code == 200:
                return response
            if response.status_code == 429 and attempt == 1:
                log.warning("llm: ollama HTTP 429 — retrying in 5s")
                time.sleep(5)
                continue
            detail = "unknown"
            try:
                detail = response.json().get("error", str(response.text))
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(
                f"ollama request failed (HTTP {response.status_code}): {detail}"
            )
        raise RuntimeError("unreachable")

    def stream_response(
        self,
        conversation: Conversation,
        tools: list[dict],
        system_prompt: str,
    ) -> Iterator[str]:
        t0 = time.perf_counter()
        ttft: float | None = None

        for _ in range(self._max_tool_iterations + 1):
            messages = _serialize_openai(conversation.messages())
            response = self._open_stream(messages, tools, system_prompt)

            text_deltas: list[str] = []
            tool_calls: dict[int, dict] = {}
            finish_reason: str | None = None

            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw_data = line[len("data:"):].strip()
                if raw_data == "[DONE]":
                    break
                try:
                    payload = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue
                choices = payload.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    if ttft is None:
                        ttft = time.perf_counter() - t0
                    text_deltas.append(delta["content"])
                    yield delta["content"]
                for call in delta.get("tool_calls") or []:
                    idx = call.get("index", 0)
                    entry = tool_calls.setdefault(idx, {"id": None, "name": "", "args": ""})
                    fn = call.get("function") or {}
                    if call.get("id"):
                        entry["id"] = call["id"]
                    if fn.get("name"):
                        entry["name"] = fn["name"]
                    if fn.get("arguments"):
                        entry["args"] += fn["arguments"]

            calls = [
                {
                    "id": entry["id"],
                    "name": entry["name"],
                    "args": json.loads(entry["args"]) if entry["args"] else {},
                }
                for entry in tool_calls.values()
            ]
            if calls:
                parts: list[dict] = []
                if text_deltas:
                    parts.append({"text": "".join(text_deltas)})
                parts += [
                    {
                        "functionCall": {
                            "id": c["id"],
                            "name": c["name"],
                            "args": c["args"],
                        }
                    }
                    for c in calls
                ]
                _run_tool_round(conversation, parts, calls, self._tool_executor, t0)
                continue

            text = "".join(text_deltas)
            if text.strip():
                conversation.add_assistant(text)
            total = time.perf_counter() - t0
            log.info(
                "llm: ttft=%.3fs total=%.3fs chars=%d model=%s stop=%s",
                ttft or total, total, len(text), self._config.model, finish_reason,
            )
            return

        log.warning(
            "llm: tool loop exceeded %d iterations; stopping", self._max_tool_iterations
        )


# --------------------------------------------------------------------------- #
# Provider 3: Pure-Python Gemini REST (Zero C/Rust/pydantic dependencies)
# --------------------------------------------------------------------------- #
class GeminiRestLLM(LLMEngine):
    """Pure-Python REST SSE streaming client for Google's Gemini / Gemma models.
    Directly communicates with Google AI Studio over HTTP.
    Does NOT require google-genai, pydantic, or any compiled C/Rust extensions.
    Guarantees 100% reliability on Android Termux, Python 3.14, and edge devices.
    """

    def __init__(self, config: LLMConfig, tool_executor: ToolExecutor | None = None) -> None:
        if not config.api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set (see .env / .env.example)")
        import httpx

        self._config = config
        self._tool_executor = tool_executor
        self._max_tool_iterations = 4
        self._client = httpx.Client(timeout=config.timeout_s)

    def _prepare_payload(self, contents: list[dict], tools: list[dict], system_prompt: str) -> dict:
        rest_contents = []
        for msg in contents:
            role = "user" if msg.get("role") == "user" else "model"
            parts = []
            for p in msg.get("parts", []):
                if "text" in p:
                    parts.append({"text": str(p["text"])})
                elif "functionCall" in p:
                    fc = p["functionCall"]
                    parts.append({
                        "functionCall": {
                            "name": fc.get("name"),
                            "args": fc.get("args", {})
                        }
                    })
                elif "functionResponse" in p:
                    fr = p["functionResponse"]
                    parts.append({
                        "functionResponse": {
                            "name": fr.get("name"),
                            "response": fr.get("response", {})
                        }
                    })
            if parts:
                rest_contents.append({"role": role, "parts": parts})

        payload: dict = {
            "contents": rest_contents,
            "generationConfig": {
                "temperature": self._config.temperature,
                "maxOutputTokens": self._config.max_tokens,
            }
        }
        if system_prompt:
            payload["system_instruction"] = {
                "parts": [{"text": system_prompt}]
            }
        if tools:
            payload["tools"] = [
                {
                    "function_declarations": tools
                }
            ]
        return payload

    def _stream_model(self, model_name: str, payload: dict) -> Iterator[dict]:
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={self._config.api_key}"
        with self._client.stream("POST", url, json=payload, headers={"Content-Type": "application/json"}) as resp:
            if resp.status_code == 429:
                raise httpx.HTTPStatusError("Rate limit 429", request=resp.request, response=resp)
            if resp.status_code != 200:
                body = resp.read().decode("utf-8", "replace")
                raise RuntimeError(f"Gemini API returned HTTP {resp.status_code}: {body}")

            for line in resp.iter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if not data_str:
                    continue
                try:
                    chunk = json.loads(data_str)
                    yield chunk
                except Exception:
                    continue

    def stream_response(
        self,
        conversation: Conversation,
        tools: list[dict],
        system_prompt: str,
    ) -> Iterator[str]:
        import httpx

        t0 = time.perf_counter()
        ttft: float | None = None

        cascade_models = [
            self._config.model,
            "gemma-4-31b-it",
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-pro",
        ]
        unique_models: list[str] = []
        for m in cascade_models:
            if m not in unique_models:
                unique_models.append(m)

        for _ in range(self._max_tool_iterations + 1):
            contents = conversation.messages()
            payload = self._prepare_payload(contents, tools, system_prompt)

            parts: list[dict] = []
            seen_calls: dict[str, dict] = {}
            success = False
            last_err = None

            for cycle in range(2):
                if success:
                    break
                for model_name in unique_models:
                    try:
                        for chunk in self._stream_model(model_name, payload):
                            candidates = chunk.get("candidates", [])
                            if not candidates:
                                continue
                            cand = candidates[0]
                            content = cand.get("content", {})
                            for part in content.get("parts", []):
                                if part.get("thought"):
                                    continue
                                if "text" in part and part["text"]:
                                    text_val = part["text"]
                                    if ttft is None:
                                        ttft = time.perf_counter() - t0
                                    parts.append({"text": text_val})
                                    yield text_val
                                elif "functionCall" in part:
                                    fc = part["functionCall"]
                                    key = fc.get("name") or f"fc{len(seen_calls)}"
                                    existing = seen_calls.get(key)
                                    if existing:
                                        existing["functionCall"]["args"].update(fc.get("args") or {})
                                    else:
                                        entry = {
                                            "functionCall": {
                                                "name": fc.get("name"),
                                                "args": fc.get("args") or {},
                                            }
                                        }
                                        seen_calls[key] = entry
                                        parts.append(entry)
                        success = True
                        break
                    except httpx.HTTPStatusError as exc:
                        last_err = exc
                        if exc.response.status_code == 429:
                            log.warning("REST llm: 429 rate limit on '%s' — cascading to next model", model_name)
                            time.sleep(1.0)
                            continue
                        log.warning("REST llm: HTTP %s on '%s' — cascading", exc.response.status_code, model_name)
                        continue
                    except Exception as exc:
                        last_err = exc
                        log.warning("REST llm stream error on '%s': %s — cascading", model_name, exc)
                        continue

                if not success and cycle == 0:
                    time.sleep(3.0)

            if not success:
                if last_err:
                    raise last_err
                raise RuntimeError("All models in REST cascade failed.")

            tool_calls = [p["functionCall"] for p in parts if _is_tool_call_part(p)]
            if tool_calls:
                _run_tool_round(conversation, parts, tool_calls, self._tool_executor, t0)
                continue

            text = "".join(p["text"] for p in parts if "text" in p)
            if text.strip():
                conversation.add_assistant(text)
            total = time.perf_counter() - t0
            log.info("REST llm: ttft=%.3fs total=%.3fs chars=%d model=%s", ttft or total, total, len(text), self._config.model)
            return

        log.warning("llm: tool loop exceeded %d iterations; stopping", self._max_tool_iterations)


def build_llm(config: LLMConfig, tool_executor: ToolExecutor | None = None) -> LLMEngine:
    """Factory: pick the engine from EV_LLM_PROVIDER (gemini | rest | ollama).
    Automatically falls back to pure-Python GeminiRestLLM if google-genai or pydantic
    encounters import/dlopen issues on Android Termux."""
    if config.provider == "ollama":
        return OllamaGemmaLLM(config, tool_executor=tool_executor)
    if config.provider == "rest":
        return GeminiRestLLM(config, tool_executor=tool_executor)

    try:
        return GeminiGemmaLLM(config, tool_executor=tool_executor)
    except (ImportError, Exception) as exc:
        log.info("google-genai SDK unavailable (%s); automatically using pure-Python GeminiRestLLM", exc)
        return GeminiRestLLM(config, tool_executor=tool_executor)