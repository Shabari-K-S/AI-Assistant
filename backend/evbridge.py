"""EV Web bridge — live status feed + controls for the web HUD.

A tiny stdlib-only HTTP server (default port 2027) that streams the
assistant's live state to the browser via Server-Sent Events and accepts
small control commands:

    GET  /stream   SSE: snapshot every ~250ms + discrete log/event lines
    GET  /state    one-shot JSON snapshot
    POST /config   {"threshold": 0.8} or {"muted": true}  -> control callbacks

`main.py` wires the Bus into the assistant loop; everything here is optional —
if the bridge is disabled or fails, the assistant still runs normally.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import threading
import time
import urllib.parse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("ev.bridge")

DEFAULT_PORT = 2027
SNAPSHOT_INTERVAL = 0.25  # seconds between snapshot refreshes on SSE
MAX_LOG_LINES = 400


class Bus:
    """Thread-safe event hub + latest-state snapshot."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot: dict[str, object] = {
            "online": False,
            "phase": "standby",  # standby | listening | processing | speaking
            "wake_score": 0.0,
            "threshold": 0.5,
            "noise_floor": 0.0,
            "muted": False,
            "wake_word": "-",
            "stt_model": "-",
            "llm_model": "-",
            "tts": "-",
            "transcript": "",
            "reply": "",
            "active_tool": None,
            "last_tool_result": None,
            "last_inference": None,
            "memory_stats": None,
            "since": 0.0,
        }
        self._rev = 0  # increments on every snapshot change
        self._subs: set[queue.Queue] = set()
        self._controls: dict[str, object] = {}
        self._boot_lines: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self._prompts: queue.Queue[str] = queue.Queue()
        self._mcp_manager: object | None = None
        self._phase_callbacks: list[Any] = []

    # -- phase callbacks --------------------------------------------------- #
    def on_phase_change(self, callback: Any) -> None:
        with self._lock:
            self._phase_callbacks.append(callback)

    # -- mcp manager attachment -------------------------------------------- #
    def set_mcp_manager(self, manager: object) -> None:
        with self._lock:
            self._mcp_manager = manager

    def get_mcp_manager(self) -> object | None:
        with self._lock:
            return self._mcp_manager

    # -- prompt injection -------------------------------------------------- #
    def inject_prompt(self, text: str) -> None:
        if text.strip():
            self._prompts.put(text.strip())

    def get_injected_prompt(self, timeout: float = 0.0) -> str | None:
        try:
            if timeout > 0:
                return self._prompts.get(timeout=timeout)
            return self._prompts.get_nowait()
        except queue.Empty:
            return None

    # -- snapshot ---------------------------------------------------------- #
    def set(self, **fields: object) -> None:
        callbacks = []
        phase_val = fields.get("phase")
        with self._lock:
            self._snapshot.update(fields)
            self._rev += 1
            if phase_val and self._phase_callbacks:
                callbacks = list(self._phase_callbacks)

        if phase_val and callbacks:
            for cb in callbacks:
                try:
                    cb(str(phase_val))
                except Exception:
                    pass

        if phase_val:
            self.publish({"type": "phase", "phase": str(phase_val), "t": time.time()})

    def get(self) -> dict[str, object]:
        with self._lock:
            return dict(self._snapshot)

    def get_rev(self) -> int:
        with self._lock:
            return self._rev

    # -- event log --------------------------------------------------------- #
    def log(self, level: str, msg: str) -> None:
        self._boot_lines.append(msg)
        self.publish({"type": "log", "level": level, "msg": msg, "t": time.time()})

    # -- pub/sub ----------------------------------------------------------- #
    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=120)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subs.discard(q)

    def publish(self, event: dict[str, object]) -> None:
        line = json.dumps(event)
        with self._lock:
            for q in list(self._subs):
                try:
                    q.put_nowait(line)
                except queue.Full:  # slow client — drop rather than block
                    pass

    def event(self, type_: str, **data: object) -> None:
        self.publish({"type": type_, "t": time.time(), **data})

    def emit_tool_start(self, name: str, args: dict) -> None:
        """Notify HUD that a tool has started execution."""
        clean_args = {k: (str(v)[:120] if len(str(v)) > 120 else v) for k, v in (args or {}).items()}
        self.set(active_tool={"name": name, "args": clean_args, "started_at": time.time()})
        self.publish({
            "type": "tool_start",
            "name": name,
            "args": clean_args,
            "t": time.time(),
        })

    def emit_tool_end(self, name: str, duration_ms: float, status: str = "ok", preview: str = "") -> None:
        """Notify HUD that a tool execution has finished."""
        res_summary = {"name": name, "duration_ms": round(duration_ms, 1), "status": status, "preview": preview[:160]}
        self.set(active_tool=None, last_tool_result=res_summary)
        self.publish({
            "type": "tool_end",
            "name": name,
            "duration_ms": round(duration_ms, 1),
            "status": status,
            "preview": preview[:160],
            "t": time.time(),
        })

    def emit_memory_recall(self, query: str, facts: list, notes: list) -> None:
        """Notify HUD of long-term memory facts and Markdown RAG note retrieval."""
        stats = {
            "query": query,
            "facts_count": len(facts),
            "notes_count": len(notes),
            "recalled_items": [
                *(f"Fact: {f.get('text', '')[:60]}" for f in facts if isinstance(f, dict)),
                *(f"Note: {n.get('title', '')} ({int(n.get('score', 0) * 100)}%)" for n in notes if isinstance(n, dict)),
            ],
        }
        self.set(memory_stats=stats)
        self.publish({
            "type": "memory_recall",
            "query": query,
            "facts": facts,
            "notes": notes,
            "t": time.time(),
        })

    def emit_llm_metrics(self, model: str, ttft_ms: float, total_ms: float, char_count: int) -> None:
        """Notify HUD of LLM streaming latency and character count metrics."""
        metrics = {
            "model": model,
            "ttft_ms": round(ttft_ms, 1),
            "total_ms": round(total_ms, 1),
            "chars": char_count,
        }
        self.set(last_inference=metrics)
        self.publish({
            "type": "llm_metrics",
            "model": model,
            "ttft_ms": round(ttft_ms, 1),
            "total_ms": round(total_ms, 1),
            "chars": char_count,
            "t": time.time(),
        })

    # -- controls ---------------------------------------------------------- #
    def on_control(self, key: str, handler: object) -> None:
        with self._lock:
            self._controls[key] = handler

    def _call_control(self, key: str, value: float | bool) -> bool:
        with self._lock:
            handler = self._controls.get(key)
        if handler is None:
            return False
        try:
            handler(value)
            return True
        except Exception:  # noqa: BLE001 - a broken control must not kill the server
            log.exception("control %s failed", key)
            return False


class _Handler(BaseHTTPRequestHandler):
    # `bus` is attached to the server instance (BridgeServer.start); handlers
    # reach it via `self.server.bus`.
    bus: Bus  # annotation kept for IDE support only

    ALLOWED_ORIGINS = {
        "http://localhost:2026",
        "http://127.0.0.1:2026",
        "http://localhost:2027",
        "http://127.0.0.1:2027",
    }

    @property
    def _bus(self) -> "Bus":
        return self.server.bus  # type: ignore[attr-defined]

    def log_message(self, *args: object) -> None:  # keep console quiet
        pass

    # -- CORS -------------------------------------------------------------- #
    def _cors(self) -> None:
        origin = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-goog-api-key")
        self.send_header("Cache-Control", "no-store")

    def do_OPTIONS(self) -> None:  # noqa: N802 - http.server API
        self.send_response(204)
        self._cors()
        self.end_headers()

    # -- endpoints --------------------------------------------------------- #
    def do_GET(self) -> None:  # noqa: N802 - http.server API
        bus = self._bus
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")

        if path == "/state":
            body = json.dumps(bus.get()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "keep-alive")
            self._cors()
            self.end_headers()
            self._stream(bus)
            return
        if path == "/mcp":
            mgr = bus.get_mcp_manager()
            if mgr and hasattr(mgr, "get_all_status"):
                status_data = mgr.get_all_status()
            else:
                from mcp_client import MCPManager
                status_data = MCPManager().get_all_status()
            self._json(status_data, 200)
            return
        if path == "/mcp/search":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            q = query_params.get("q", [""])[0].strip()
            from mcp_client import discover_mcp
            res = discover_mcp(q)
            self._json(res, 200 if res.get("ok") else 400)
            return
        if path == "/notes":
            from notes_mcp_server import _load_index
            index_data = _load_index()
            self._json(index_data, 200)
            return
        if path == "/notes/read":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            target = query_params.get("target", [""])[0].strip()
            if not target:
                self._json({"ok": False, "error": "target parameter is required"}, 400)
                return
            from notes_mcp_server import _find_note_file, _parse_markdown_frontmatter, DATA_DIR
            file_path, meta = _find_note_file(target)
            if not file_path or not file_path.exists():
                self._json({"ok": False, "error": f"Note '{target}' not found in vault"}, 404)
                return
            frontmatter, body = _parse_markdown_frontmatter(file_path)
            title = frontmatter.get("title") or (meta.get("title") if meta else file_path.stem.replace("_", " ").title())
            category = frontmatter.get("category") or file_path.parent.name
            created_at = frontmatter.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
            self._json({
                "ok": True,
                "id": frontmatter.get("id") or (meta.get("id") if meta else file_path.stem),
                "title": title,
                "category": category,
                "path": str(file_path.relative_to(DATA_DIR)),
                "created_at": created_at,
                "tags": frontmatter.get("tags", []),
                "sources_count": frontmatter.get("sources_count") or (meta.get("sources_count") if meta else None),
                "model_used": frontmatter.get("model_used") or (meta.get("model_used") if meta else None),
                "content": body,
            }, 200)
            return
        if path == "/timers":
            from timer_engine import get_timer_engine
            engine = get_timer_engine(bus)
            self._json({"ok": True, "timers": engine.list_timers()}, 200)
            return
        if path == "/briefing":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            b_type = query_params.get("type", ["morning"])[0].strip()
            from briefing_engine import get_briefing_engine
            b_engine = get_briefing_engine(bus)
            res = b_engine.generate_briefing(briefing_type=b_type)
            self._json(res, 200)
            return

        # Static Web App serving from frontend/dist (Zero npm run dev required)
        from pathlib import Path
        import mimetypes
        dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
        if dist_dir.exists():
            rel_path = path.lstrip("/")
            file_path = dist_dir / rel_path if rel_path else dist_dir / "index.html"
            if not file_path.exists() or file_path.is_dir():
                file_path = dist_dir / "index.html"

            if file_path.exists() and file_path.is_file():
                mime_type, _ = mimetypes.guess_type(str(file_path))
                if file_path.suffix == ".woff2":
                    mime_type = "font/woff2"
                elif file_path.suffix == ".woff":
                    mime_type = "font/woff"
                elif file_path.suffix == ".js":
                    mime_type = "application/javascript"
                elif file_path.suffix == ".css":
                    mime_type = "text/css"
                elif file_path.suffix == ".html":
                    mime_type = "text/html"

                try:
                    content = file_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", mime_type or "application/octet-stream")
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Expires", "0")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(content)
                    return
                except Exception:
                    pass

        self.send_response(404)
        self._cors()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        bus = self._bus
        path = self.path.rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json({"ok": False, "error": "bad json"}, 400)
            return

        if path == "/prompt":
            prompt = str(body.get("text") or "").strip()
            if not prompt:
                self._json({"ok": False, "error": "empty prompt"}, 400)
                return
            bus.inject_prompt(prompt)
            bus.set(phase="processing", transcript=prompt)
            bus.log("INFO", f"terminal uplink: {prompt}")
            self._json({"ok": True, "prompt": prompt})
            return

        if path == "/ask":
            prompt = str(body.get("text") or "").strip()
            if not prompt:
                self._json({"ok": False, "error": "empty prompt"}, 400)
                return

            # Subscribe to bus events to wait synchronously for assistant reply
            q = bus.subscribe()
            bus.inject_prompt(prompt)
            bus.set(phase="processing", transcript=prompt)
            bus.log("INFO", f"android uplink: {prompt}")

            reply_text = ""
            start_t = time.monotonic()
            try:
                while time.monotonic() - start_t < 30.0:
                    try:
                        line = q.get(timeout=0.25)
                        event = json.loads(line)
                        if event.get("type") == "reply":
                            reply_text = str(event.get("text", "")).strip()
                            if reply_text:
                                break
                    except (queue.Empty, json.JSONDecodeError):
                        continue
            finally:
                bus.unsubscribe(q)

            if reply_text:
                self._json({"ok": True, "reply": reply_text})
            else:
                last_reply = str(bus.get().get("reply", "")).strip()
                self._json({"ok": bool(last_reply), "reply": last_reply or "I processed your request.", "timeout": True})
            return

        if path == "/transcribe":
            audio_b64 = str(body.get("audio_b64") or "").strip()
            mime_type = str(body.get("mime_type") or "audio/webm").strip()
            if not audio_b64:
                self._json({"ok": False, "error": "audio_b64 required"}, 400)
                return

            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                self._json({"ok": False, "error": "GEMINI_API_KEY not configured for audio STT"}, 400)
                return

            try:
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": mime_type,
                                        "data": audio_b64,
                                    }
                                },
                                {
                                    "text": "Transcribe the exact spoken words in this audio clip. Return ONLY the plain transcribed text without commentary or quotes."
                                }
                            ]
                        }
                    ]
                }
                transcribed_text = ""
                models_to_try = [
                    "gemini-2.5-flash",
                    "gemini-3.5-flash",
                    "gemini-3.1-flash-lite",
                    "gemini-3.5-flash-lite",
                    "gemini-flash-latest",
                    "gemini-flash-lite-latest",
                ]

                for model_name in models_to_try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=15.0) as resp:
                            res_data = json.loads(resp.read().decode("utf-8"))
                            
                        candidates = res_data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            transcribed_text = "".join(p.get("text", "") for p in parts).strip()
                            if transcribed_text:
                                break  # Success!
                    except urllib.error.HTTPError as e:
                        logger.warning(f"Transcription failed with model {model_name}: {e.code} {e.reason}")
                        continue
                    except Exception as e:
                        logger.warning(f"Transcription exception with model {model_name}: {e}")
                        continue

                if not transcribed_text:
                    self._json({"ok": False, "error": "No speech detected"}, 200)
                    return

                # Wake word gating (supports Athena, Atina, Adina, Athina, Atena, etc.)
                wake_pattern = re.compile(
                    r"\b(?:hey\s+|hi\s+|ok\s+|okay\s+|hello\s+)?(a[td]h?e?i?n[ae]|ath?ee?n[ae]|atena|atina|adina|adena|edina|ethina|alexa|assistant)\b",
                    re.IGNORECASE,
                )
                match = wake_pattern.search(transcribed_text)
                if not match:
                    bus.log("DEBUG", f"👂 Ignored background speech (no wake word): '{transcribed_text}'")
                    self._json({"ok": False, "reason": "no_wake_word", "text": transcribed_text}, 200)
                    return

                # Extract command following the wake word
                start_pos = match.end()
                command = transcribed_text[start_pos:].strip(" ,.!?")

                if not command:
                    # User said only the wake word (e.g. "Athena")
                    prompt = "Hello Athena, acknowledge you are listening."
                    bus.inject_prompt(prompt)
                    bus.log("INFO", f"🎯 Wake word detected: '{transcribed_text}'")
                    self._json({"ok": True, "wake_hit": True, "text": transcribed_text, "command": ""})
                else:
                    bus.inject_prompt(command)
                    bus.log("INFO", f"🎯 Wake word hit! Command: '{command}'")
                    self._json({"ok": True, "wake_hit": True, "text": transcribed_text, "command": command})
                return
            except Exception as exc:
                log.exception("Silent audio transcription failed")
                self._json({"ok": False, "error": str(exc)}, 500)
                return

        if path == "/ptt":
            state = str(body.get("state") or "").lower().strip()
            if state == "press":
                bus._call_control("ptt_press", True)
                bus.set(phase="listening")
                bus.log("INFO", "web PTT: voice capture activated")
                self._json({"ok": True, "state": "press"})
                return
            elif state == "release":
                bus._call_control("ptt_release", True)
                bus.log("INFO", "web PTT: voice capture released")
                self._json({"ok": True, "state": "release"})
                return
            self._json({"ok": False, "error": "state must be 'press' or 'release'"}, 400)
            return

        if path == "/config":
            applied: list[str] = []
            if "threshold" in body:
                thr = float(body["threshold"])
                thr = min(1.0, max(0.1, thr))
                if bus._call_control("threshold", thr):
                    bus.set(threshold=thr)
                    bus.log("INFO", f"threshold set to {thr:.2f}")
                    applied.append("threshold")
            if "muted" in body:
                muted = bool(body["muted"])
                if bus._call_control("muted", muted):
                    bus.set(muted=muted)
                    bus.log("INFO", f"speech {'muted' if muted else 'unmuted'}")
                    applied.append("muted")
            self._json({"ok": True, "applied": applied})
            return

        if path == "/mcp/toggle":
            name = str(body.get("name", "")).strip()
            enabled = bool(body.get("enabled", True))
            mgr = bus.get_mcp_manager()
            if not mgr:
                from mcp_client import MCPManager
                mgr = MCPManager()
            res = mgr.toggle_server(name, enabled)
            if res.get("ok"):
                bus.log("INFO", f"MCP: server '{name}' {'enabled' if enabled else 'disabled'}")
                bus.publish({"type": "mcp_changed", "server": name, "enabled": enabled})
            self._json(res, 200 if res.get("ok") else 400)
            return

        if path == "/mcp/save":
            name = str(body.get("name", "")).strip()
            mgr = bus.get_mcp_manager()
            if not mgr:
                from mcp_client import MCPManager
                mgr = MCPManager()
            res = mgr.save_server(name, body)
            if res.get("ok"):
                bus.log("INFO", f"MCP: server '{name}' config updated")
                bus.publish({"type": "mcp_changed", "server": name})
            self._json(res, 200 if res.get("ok") else 400)
            return

        if path == "/mcp/update":
            name = str(body.get("name", "")).strip()
            mgr = bus.get_mcp_manager()
            if not mgr:
                from mcp_client import MCPManager
                mgr = MCPManager()
            res = mgr.update_server(name, body)
            if res.get("ok"):
                bus.log("INFO", f"MCP: server '{name}' updated and reloaded")
                bus.publish({"type": "mcp_changed", "server": name})
            self._json(res, 200 if res.get("ok") else 400)
            return

        if path == "/mcp/delete":
            name = str(body.get("name", "")).strip()
            mgr = bus.get_mcp_manager()
            if not mgr:
                from mcp_client import MCPManager
                mgr = MCPManager()
            res = mgr.delete_server(name)
            if res.get("ok"):
                bus.log("INFO", f"MCP: server '{name}' deleted")
                bus.publish({"type": "mcp_changed", "server": name})
            self._json(res, 200 if res.get("ok") else 400)
            return

        if path == "/mcp/restart":
            name = str(body.get("name", "")).strip()
            mgr = bus.get_mcp_manager()
            if not mgr:
                from mcp_client import MCPManager
                mgr = MCPManager()
            res = mgr.restart_server(name)
            if res.get("ok"):
                bus.log("INFO", f"MCP: server '{name}' restarted")
                bus.publish({"type": "mcp_changed", "server": name})
            self._json(res, 200 if res.get("ok") else 400)
            return

        if path == "/notes/save":
            title = str(body.get("title", "")).strip()
            content = str(body.get("content", "")).strip()
            category = str(body.get("category", "general")).strip() or "general"
            tags = body.get("tags", [])
            target = str(body.get("target", "")).strip()
            append = bool(body.get("append", False))

            if not content and not title:
                self._json({"ok": False, "error": "Content or title is required"}, 400)
                return

            from notes_mcp_server import handle_add_note, handle_edit_note
            if target:
                res_text = handle_edit_note({"note_id_or_title_or_path": target, "content": content, "append": append})
            else:
                res_text = handle_add_note({"title": title, "content": content, "category": category, "tags": tags})

            bus.log("INFO", f"Notes Vault updated: {title or target}")
            bus.publish({"type": "notes_changed"})
            self._json({"ok": True, "result": res_text}, 200)
            return

        if path == "/notes/delete":
            target = str(body.get("target", "")).strip()
            if not target:
                self._json({"ok": False, "error": "target note identifier is required"}, 400)
                return
            from notes_mcp_server import handle_delete_note
            res_text = handle_delete_note({"note_id_or_title_or_path": target})
            bus.log("INFO", f"Note deleted: {target}")
            bus.publish({"type": "notes_changed"})
            self._json({"ok": True, "result": res_text}, 200)
            return

        if path == "/timers/create":
            duration = str(body.get("duration", "")).strip()
            label = str(body.get("label", "")).strip()
            t_type = str(body.get("type", "timer")).strip()
            from timer_engine import get_timer_engine
            engine = get_timer_engine(bus)
            res = engine.add_timer(duration, label=label, timer_type=t_type)
            self._json(res, 200 if res.get("ok") else 400)
            return

        if path == "/timers/cancel":
            timer_id = str(body.get("id", "")).strip()
            from timer_engine import get_timer_engine
            engine = get_timer_engine(bus)
            res = engine.cancel_timer(timer_id)
            self._json(res, 200 if res.get("ok") else 400)
            return

        self.send_response(404)
        self._cors()
        self.end_headers()

    # -- internals --------------------------------------------------------- #
    def _stream(self, bus: Bus) -> None:
        q = bus.subscribe()
        last_rev = -1
        last_beat = time.monotonic()
        # Immediately write initial snapshot on connect
        last_rev = bus.get_rev()
        self._write_event("snapshot", bus.get())
        try:
            while True:
                rev = bus.get_rev()
                if rev != last_rev:
                    last_rev = rev
                    self._write_event("snapshot", bus.get())

                try:
                    line = q.get(timeout=0.1)
                except queue.Empty:
                    if time.monotonic() - last_beat > 12:
                        last_beat = time.monotonic()
                        self._write_event("ping", {})
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "snapshot":
                    continue  # snapshots handled via rev checks
                self._write_event(data.get("type", "event"), data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            bus.unsubscribe(q)

    def _write_event(self, type_: str, data: object) -> None:
        try:
            payload = json.dumps({"type": type_, **({} if data is None else data)})
            self.wfile.write(f"event: {type_}\ndata: {payload}\n\n".encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            raise  # ends the stream loop

    def _json(self, obj: object, status: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)


class BridgeServer:
    """Owns the HTTP server thread; `start()` is non-blocking."""

    def __init__(self, bus: Bus, port: int = DEFAULT_PORT) -> None:
        self.bus = bus
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        if self._server is not None:
            return True
        try:
            ThreadingHTTPServer.allow_reuse_address = True
            server = ThreadingHTTPServer(("0.0.0.0", self.port), _Handler)
        except OSError as exc:
            log.warning("web bridge unavailable on :%d — %s", self.port, exc)
            return False
        server.bus = self.bus  # type: ignore[attr-defined]
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever, daemon=True, name="ev-bridge"
        )
        self._thread.start()
        log.info("web bridge on http://0.0.0.0:%d (local: http://localhost:%d)", self.port, self.port)
        return True

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None


# -- process-wide singleton (one bridge per assistant process) ------------- #
_bus: Bus | None = None
_server: BridgeServer | None = None


def get_bus() -> Bus:
    global _bus
    if _bus is None:
        _bus = Bus()
    return _bus


def start(port: int = DEFAULT_PORT) -> BridgeServer | None:
    """Start the bridge (idempotent). Returns the server or None on failure."""
    global _server
    if _server is not None:
        return _server
    _server = BridgeServer(get_bus(), port=port)
    if not _server.start():
        _server = None
    return _server
