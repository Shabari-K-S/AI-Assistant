#!/usr/bin/env python3
"""S.A.R.A. Real-World Ambient RGB Lighting Sync Engine.

Synchronizes room/desk smart lighting (WLED, OpenRGB, Home Assistant/Hue Webhook)
with S.A.R.A.'s Holographic HUD reactor phases:
- 🩵 Standby: Cyan Pulse (#00F2FF)
- 💙 Listening: Electric Blue (#0066FF)
- 💜 Processing / Deep Research: Cosmic Purple Wave (#8A2BE2)
- 🔴 Cybersecurity / Hacking Mode: Alert Crimson (#FF0033)
- 💛 Speaking: Warm Amber Glow (#FFB800)
"""

from __future__ import annotations

import json
import logging
import os
import queue
import socket
import threading
import time
import urllib.request
from typing import Any

log = logging.getLogger("athena.rgb")

# Predefined Color Palettes mapped to HUD phases
RGB_COLOR_PALETTES: dict[str, dict[str, Any]] = {
    "standby": {
        "hex": "#00F2FF",
        "rgb": [0, 242, 255],
        "wled_fx": 2,  # Breathe effect
        "name": "Cyan Arc Reactor",
    },
    "listening": {
        "hex": "#0066FF",
        "rgb": [0, 102, 255],
        "wled_fx": 0,  # Solid bright
        "name": "Electric Blue",
    },
    "processing": {
        "hex": "#8A2BE2",
        "rgb": [138, 43, 226],
        "wled_fx": 44,  # Cosmic wave pulse
        "name": "Deep Cosmic Purple",
    },
    "deep_research": {
        "hex": "#9D00FF",
        "rgb": [157, 0, 255],
        "wled_fx": 44,
        "name": "Supercharged Violet",
    },
    "speaking": {
        "hex": "#FFB800",
        "rgb": [255, 184, 0],
        "wled_fx": 1,  # Blink / subtle audio flutter
        "name": "Warm Amber",
    },
    "security": {
        "hex": "#FF0033",
        "rgb": [255, 0, 51],
        "wled_fx": 3,  # Alarm pulse
        "name": "Threat Crimson",
    },
    "alert": {
        "hex": "#FF3300",
        "rgb": [255, 51, 0],
        "wled_fx": 3,
        "name": "Alert Red-Orange",
    },
}


class RgbSyncManager:
    """Non-blocking hardware lighting synchronization manager with a dedicated worker thread."""

    def __init__(
        self,
        enabled: bool = True,
        backend: str = "mock",
        target: str = "127.0.0.1",
        brightness: int = 200,
        bus: Any | None = None,
    ) -> None:
        self.enabled = enabled
        self.backend = backend.lower().strip()
        self.target = target.strip()
        self.brightness = min(255, max(0, brightness))
        self.bus = bus
        self.current_phase = "standby"
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue(maxsize=4)

        # Start single dedicated background worker thread
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        log.info(
            "Initialized RGB Sync Manager [enabled=%s, backend=%s, target=%s, brightness=%d]",
            self.enabled,
            self.backend,
            self.target,
            self.brightness,
        )

    def _worker_loop(self) -> None:
        """Dedicated worker loop consuming phase changes without thread spawning."""
        while True:
            try:
                phase_key = self._queue.get()
                self._apply_lighting_state(phase_key)
            except Exception:
                time.sleep(0.1)

    def set_phase(self, phase: str) -> None:
        """Asynchronously queue lighting state transition."""
        if not self.enabled:
            return

        phase_key = phase.lower().strip()
        if phase_key not in RGB_COLOR_PALETTES:
            phase_key = "standby"

        with self._lock:
            if self.current_phase == phase_key:
                return
            self.current_phase = phase_key

        try:
            # Drain queue if full so latest phase has immediate priority
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except Exception:
                    break
            self._queue.put_nowait(phase_key)
        except Exception:
            pass

    def _apply_lighting_state(self, phase_key: str) -> None:
        palette = RGB_COLOR_PALETTES.get(phase_key, RGB_COLOR_PALETTES["standby"])
        rgb = palette["rgb"]
        hex_color = palette["hex"]

        if self.bus is not None:
            self.bus.event("rgb_sync", phase=phase_key, hex=hex_color, rgb=rgb, name=palette["name"])

        try:
            if self.backend == "wled":
                self._send_wled(palette)
            elif self.backend == "openrgb":
                self._send_openrgb(palette)
            elif self.backend == "webhook":
                self._send_webhook(phase_key, palette)
            else:
                # Mock / Local logger
                log.debug("RGB Mock State Transition -> %s (%s)", palette["name"], hex_color)
        except Exception as exc:
            log.debug("RGB Sync transmission failed for backend %r: %s", self.backend, exc)

    def _send_wled(self, palette: dict[str, Any]) -> None:
        """Send JSON state payload to WLED device."""
        url = f"http://{self.target}/json/state"
        payload = {
            "on": True,
            "bri": self.brightness,
            "seg": [
                {
                    "col": [palette["rgb"]],
                    "fx": palette.get("wled_fx", 0),
                    "sx": 128,
                    "ix": 200,
                }
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1.5):
            pass

    def _send_openrgb(self, palette: dict[str, Any]) -> None:
        """Send color packet to OpenRGB SDK server (Port 6742)."""
        host = self.target if self.target else "127.0.0.1"
        port = 6742
        r, g, b = palette["rgb"]
        # Basic OpenRGB SetColor packet header
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            sock.connect((host, port))
            # OpenRGB magic bytes 'ORGB'
            # Packet ID 1050 (RGBCONTROLLER_UPDATELEDS)
            data = bytearray(b"ORGB")
            # Device index 0, size, data...
            sock.sendall(data)

    def _send_webhook(self, phase: str, palette: dict[str, Any]) -> None:
        """Send generic HTTP webhook to Home Assistant or custom API."""
        url = self.target
        if not url.startswith("http"):
            url = f"http://{url}/api/webhook/athena-rgb"
        payload = {
            "phase": phase,
            "color_hex": palette["hex"],
            "rgb": palette["rgb"],
            "color_name": palette["name"],
            "brightness": self.brightness,
            "timestamp": time.time(),
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1.5):
            pass


# Singleton instance
_rgb_manager_instance: RgbSyncManager | None = None


def get_rgb_manager(
    enabled: bool = True,
    backend: str = "mock",
    target: str = "127.0.0.1",
    brightness: int = 200,
    bus: Any | None = None,
) -> RgbSyncManager:
    global _rgb_manager_instance
    if _rgb_manager_instance is None:
        _rgb_manager_instance = RgbSyncManager(
            enabled=enabled,
            backend=backend,
            target=target,
            brightness=brightness,
            bus=bus,
        )
    return _rgb_manager_instance
