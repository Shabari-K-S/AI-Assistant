#!/usr/bin/env python3
"""A.T.H.E.N.A. Terminal Bridge — WebSocket PTY Server for Integrated Terminal.

Provides a real-time, bidirectional pseudo-terminal (PTY) session over WebSockets
connecting the Athena Holographic HUD to Android Termux or the host Linux/WSL shell.
Supports ANSI escape sequences, full interactive programs (htop, nano, vim), and
dynamic terminal window resizing (TIOCSWINSZ).
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import pty
import shutil
import signal
import struct
import sys
import termios
import threading
import time
from pathlib import Path
from typing import Any

import websockets

log = logging.getLogger("athena.terminal")

DEFAULT_PORT = 2028


def is_android_termux() -> bool:
    """Detect whether current runtime is Android Termux."""
    return (
        "TERMUX_VERSION" in os.environ
        or "com.termux" in os.environ.get("PREFIX", "")
        or os.path.exists("/data/data/com.termux")
        or os.path.exists("/data/data/com.termux/files/usr/bin/bash")
        or shutil.which("termux-battery-status") is not None
    )


def detect_shell(custom_shell: str = "") -> str:
    """Locate the best interactive shell binary."""
    if custom_shell and shutil.which(custom_shell):
        return custom_shell

    # 1. Termux candidate paths
    termux_candidates = [
        os.environ.get("SHELL", ""),
        "/data/data/com.termux/files/usr/bin/bash",
        "/data/data/com.termux/files/usr/bin/zsh",
        "/data/data/com.termux/files/usr/bin/sh",
    ]
    for candidate in termux_candidates:
        if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # 2. Host Linux / WSL candidates
    host_candidates = [
        os.environ.get("SHELL", ""),
        shutil.which("bash"),
        shutil.which("zsh"),
        shutil.which("sh"),
        "/bin/bash",
        "/usr/bin/bash",
        "/bin/sh",
    ]
    for candidate in host_candidates:
        if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return "/bin/sh"


class TerminalSession:
    """Manages a single interactive PTY process and its WebSocket lifecycle."""

    def __init__(self, websocket: Any, shell_path: str) -> None:
        self.websocket = websocket
        self.shell_path = shell_path
        self.master_fd: int | None = None
        self.pid: int | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    def spawn(self) -> None:
        """Spawn the child process with a dedicated pseudo-terminal pair."""
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd

        pid = os.fork()
        if pid == 0:
            # --- CHILD PROCESS ---
            try:
                os.close(master_fd)
                os.setsid()
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

                # Duplicate slave PTY to standard IO streams
                os.dup2(slave_fd, 0)
                os.dup2(slave_fd, 1)
                os.dup2(slave_fd, 2)
                if slave_fd > 2:
                    os.close(slave_fd)

                # Set up environment
                env = os.environ.copy()
                env["TERM"] = "xterm-256color"
                env["COLORTERM"] = "truecolor"
                env["LANG"] = env.get("LANG", "en_US.UTF-8")

                if is_android_termux():
                    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
                    env["PREFIX"] = prefix
                    env["PATH"] = f"{prefix}/bin:/data/data/com.termux/files/usr/bin:" + env.get("PATH", "")
                    env["LD_LIBRARY_PATH"] = f"{prefix}/lib:/data/data/com.termux/files/usr/lib:" + env.get("LD_LIBRARY_PATH", "")
                    home = os.environ.get("HOME", "/data/data/com.termux/files/home")
                    if os.path.isdir(home):
                        os.chdir(home)
                else:
                    # Linux / WSL workspace or HOME
                    cwd = os.environ.get("PWD", os.getcwd())
                    try:
                        os.chdir(cwd)
                    except Exception:
                        pass

                shell_name = Path(self.shell_path).name
                os.execvpe(self.shell_path, [f"-{shell_name}"], env)
            except Exception as e:
                # Fatal child spawn error
                sys.stderr.write(f"\r\n[Fatal] Failed to spawn shell {self.shell_path}: {e}\r\n")
                os._exit(1)

        # --- PARENT PROCESS ---
        os.close(slave_fd)
        self.pid = pid
        # Set master_fd non-blocking
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def set_winsize(self, rows: int, cols: int) -> None:
        """Set terminal dimensions in the kernel PTY driver."""
        if self.master_fd is None or self._closed:
            return
        try:
            rows = max(1, min(rows, 400))
            cols = max(1, min(cols, 600))
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
        except Exception as exc:
            log.debug("Failed to set winsize %dx%d: %s", rows, cols, exc)

    def on_pty_read(self) -> None:
        """Read pending raw bytes from PTY master and forward to WebSocket."""
        if self.master_fd is None or self._closed or self.loop is None:
            return
        try:
            data = os.read(self.master_fd, 8192)
            if data:
                asyncio.run_coroutine_threadsafe(self.websocket.send(data), self.loop)
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            # Shell exited or EOF
            self.close()

    def close(self) -> None:
        """Terminate child process, remove event loop reader, and close PTY."""
        if self._closed:
            return
        self._closed = True

        if self.loop is not None and self.master_fd is not None:
            try:
                self.loop.remove_reader(self.master_fd)
            except Exception:
                pass

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except Exception:
                pass
            self.master_fd = None

        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGHUP)
                time.sleep(0.05)
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, os.WNOHANG)
            except Exception:
                pass
            self.pid = None


class TerminalServer:
    """Manages WebSocket connections and Terminal sessions."""

    def __init__(self, port: int = DEFAULT_PORT, custom_shell: str = "") -> None:
        self.port = port
        self.custom_shell = custom_shell
        self.shell_path = detect_shell(custom_shell)
        self._server: Any = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event = threading.Event()

    async def _handle_connection(self, websocket: Any) -> None:
        """Handle individual WebSocket connection."""
        log.info("New terminal client connected from %s", getattr(websocket, "remote_address", "unknown"))
        session = TerminalSession(websocket, self.shell_path)
        session.loop = asyncio.get_running_loop()

        try:
            session.spawn()
        except Exception as exc:
            log.error("Failed to spawn PTY session: %s", exc)
            err_msg = f"\r\n\x1b[31m[A.T.H.E.N.A.] Failed to spawn terminal: {exc}\x1b[0m\r\n"
            try:
                await websocket.send(err_msg.encode())
            except Exception:
                pass
            return

        # Add PTY file descriptor reader to asyncio event loop
        if session.master_fd is not None:
            session.loop.add_reader(session.master_fd, session.on_pty_read)

        try:
            async for message in websocket:
                if session._closed or session.master_fd is None:
                    break

                if isinstance(message, bytes):
                    try:
                        os.write(session.master_fd, message)
                    except OSError:
                        break
                elif isinstance(message, str):
                    # Check for JSON control messages (e.g. resize)
                    if message.startswith("{") and message.endswith("}"):
                        try:
                            payload = json.loads(message)
                            if payload.get("type") == "resize":
                                cols = int(payload.get("cols", 80))
                                rows = int(payload.get("rows", 24))
                                session.set_winsize(rows, cols)
                                continue
                            elif payload.get("type") == "ping":
                                await websocket.send(json.dumps({"type": "pong"}))
                                continue
                        except Exception:
                            pass
                    # Standard text keystrokes
                    try:
                        os.write(session.master_fd, message.encode("utf-8", errors="replace"))
                    except OSError:
                        break
        except websockets.exceptions.ConnectionClosed:
            log.info("Terminal client disconnected")
        except Exception as exc:
            log.warning("Terminal WebSocket error: %s", exc)
        finally:
            session.close()

    def _run_loop(self) -> None:
        """Dedicated thread event loop for WebSocket terminal server."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def _serve() -> None:
            try:
                async with websockets.serve(
                    self._handle_connection,
                    "0.0.0.0",
                    self.port,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=2**20,  # 1MB max frame
                ) as server:
                    self._server = server
                    log.info(
                        "Terminal WebSocket bridge online on ws://0.0.0.0:%d (shell: %s)",
                        self.port,
                        self.shell_path,
                    )
                    while not self._stop_event.is_set():
                        await asyncio.sleep(0.5)
            except Exception as exc:
                log.warning("Terminal server error on port %d: %s", self.port, exc)

        try:
            self._loop.run_until_complete(_serve())
        except Exception as exc:
            log.error("Terminal event loop stopped: %s", exc)
        finally:
            self._loop.close()

    def start(self) -> bool:
        """Start the terminal server in a background daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="athena-terminal-bridge",
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop the terminal server and release resources."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None


_terminal_server: TerminalServer | None = None


def start(port: int = DEFAULT_PORT, custom_shell: str = "") -> TerminalServer | None:
    """Start the process-wide terminal server (idempotent)."""
    global _terminal_server
    if _terminal_server is not None:
        return _terminal_server
    server = TerminalServer(port=port, custom_shell=custom_shell)
    if server.start():
        _terminal_server = server
        return _terminal_server
    return None


def stop() -> None:
    """Stop the process-wide terminal server."""
    global _terminal_server
    if _terminal_server is not None:
        _terminal_server.stop()
        _terminal_server = None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    print(f"Starting standalone terminal bridge on ws://localhost:{port} (Termux={is_android_termux()})...")
    srv = start(port)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping terminal bridge...")
        stop()
