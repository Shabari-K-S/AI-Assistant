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
import queue
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
            "since": 0.0,
        }
        self._rev = 0  # increments on every snapshot change
        self._subs: set[queue.Queue] = set()
        self._controls: dict[str, object] = {}
        self._boot_lines: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self._prompts: queue.Queue[str] = queue.Queue()
        self._mcp_manager: object | None = None

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
        with self._lock:
            self._snapshot.update(fields)
            self._rev += 1

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
        origin = self.headers.get("Origin")
        if origin and origin in self.ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        elif not origin:
            # Same-origin or non-browser local requests
            self.send_header("Access-Control-Allow-Origin", "http://localhost:2026")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
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
                "updated_at": frontmatter.get("updated_at"),
                "tags": frontmatter.get("tags", []),
                "content": body,
            }, 200)
            return
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
            bus.log("INFO", f"terminal uplink: {prompt}")
            self._json({"ok": True, "prompt": prompt})
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

        self.send_response(404)
        self._cors()
        self.end_headers()

    # -- internals --------------------------------------------------------- #
    def _stream(self, bus: Bus) -> None:
        q = bus.subscribe()
        last_rev = -1
        last_beat = time.monotonic()
        # Immediately write initial snapshot on connect
        self._write_event("snapshot", bus.get())
        try:
            while True:
                try:
                    line = q.get(timeout=0.25)
                except queue.Empty:
                    rev = bus.get_rev()
                    if rev != last_rev:
                        last_rev = rev
                        self._write_event("snapshot", bus.get())
                    elif time.monotonic() - last_beat > 12:
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
            server = ThreadingHTTPServer(("127.0.0.1", self.port), _Handler)
        except OSError as exc:
            log.warning("web bridge unavailable on :%d — %s", self.port, exc)
            return False
        server.bus = self.bus  # type: ignore[attr-defined]
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever, daemon=True, name="ev-bridge"
        )
        self._thread.start()
        log.info("web bridge on http://localhost:%d", self.port)
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
