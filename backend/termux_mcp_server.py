#!/usr/bin/env python3
"""Android Termux Mobile Superpowers MCP Server for S.A.R.A.

Implements JSON-RPC 2.0 stdio Model Context Protocol (2024-11-05 spec) providing
Android hardware control via Termux:API:
- Battery status & charging telemetry
- Flashlight / Torch control
- Haptic phone vibrations
- Phone clipboard synchronization
- Android pull-down tray notifications
- Camera photo snapshot & multimodal vision analysis
- GPS location queries for local context
- Pocket DevOps remote host & server health checks
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("sara.termux")


def is_android_termux() -> bool:
    """Detect whether the current runtime environment is Android Termux."""
    return (
        "TERMUX_VERSION" in os.environ
        or "com.termux" in os.environ.get("PREFIX", "")
        or os.path.exists("/data/data/com.termux")
        or shutil.which("termux-battery-status") is not None
    )


def _run_termux_cmd(cmd: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
    """Execute a termux-api CLI command with timeout and output capture."""
    binary = cmd[0]
    if not shutil.which(binary):
        return (
            127,
            "",
            f"Termux command '{binary}' not found. Please install via 'pkg install termux-api' in Termux.",
        )
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Command '{' '.join(cmd)}' timed out after {timeout}s."
    except Exception as exc:
        return 1, "", str(exc)


TOOLS = [
    {
        "name": "android_battery_status",
        "description": "Read live Android phone battery percentage, health, temperature, and charging state via Termux:API.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "android_torch_control",
        "description": "Turn the phone's physical LED flashlight / torch ON or OFF.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["on", "off", "toggle"],
                    "description": "Desired torch state ('on' or 'off').",
                }
            },
            "required": ["state"],
        },
    },
    {
        "name": "android_vibrate_phone",
        "description": "Trigger a physical haptic vibration pulse on the Android phone for alarms, timers, or completion alerts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "duration_ms": {
                    "type": "integer",
                    "description": "Vibration duration in milliseconds (default: 500ms).",
                    "default": 500,
                },
                "force": {
                    "type": "boolean",
                    "description": "Force vibration even in silent mode.",
                    "default": False,
                },
            },
        },
    },
    {
        "name": "android_clipboard_sync",
        "description": "Read from or copy text directly to the Android phone clipboard.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "set"],
                    "description": "'get' to read clipboard, 'set' to copy text to clipboard.",
                },
                "text": {
                    "type": "string",
                    "description": "Text content to copy when action is 'set'.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "android_notification_send",
        "description": "Post a rich push notification to the Android pull-down notification shade.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Notification title header.",
                },
                "content": {
                    "type": "string",
                    "description": "Notification body message.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "default", "low", "max"],
                    "description": "Notification priority level (default: 'high').",
                    "default": "high",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "android_camera_vision",
        "description": "Snap a real-time photo from rear (0) or front/selfie (1) camera and analyze what is visible with multimodal AI vision.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "camera_id": {
                    "type": "integer",
                    "enum": [0, 1],
                    "description": "0 for back/rear camera, 1 for front/selfie camera (default: 0).",
                    "default": 0,
                },
                "prompt": {
                    "type": "string",
                    "description": "What specific question to ask or analyze about the captured image.",
                    "default": "Describe this image in detail and identify key objects, text, or errors.",
                },
            },
        },
    },
    {
        "name": "android_location_get",
        "description": "Fetch current GPS / network location coordinates on Android for accurate local weather and geographical context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["network", "gps", "passive"],
                    "description": "Location provider (default: 'network' for speed and battery efficiency).",
                    "default": "network",
                }
            },
        },
    },
    {
        "name": "pocket_devops_server_check",
        "description": "Check remote server / VPS status, ping latency, and port availability directly from mobile Termux.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Remote server hostname or IP address to check.",
                },
                "port": {
                    "type": "integer",
                    "description": "Target port (e.g. 22, 80, 443, 8080). Default: 80.",
                    "default": 80,
                },
                "timeout_seconds": {
                    "type": "number",
                    "description": "Connection timeout in seconds (default: 3.0s).",
                    "default": 3.0,
                },
            },
            "required": ["host"],
        },
    },
]


# --------------------------------------------------------------------------- #
# Tool Handlers
# --------------------------------------------------------------------------- #

def handle_battery_status(_args: dict[str, Any]) -> str:
    """Read Android phone battery percentage and charging state."""
    if not is_android_termux():
        return (
            "📱 [Desktop Environment]: Battery telemetry simulated — "
            "Level: 95% | Status: Charging | Health: Good | Temperature: 32.5°C\n"
            "(On Android Termux, this tool queries live hardware status via termux-battery-status)."
        )

    code, stdout, stderr = _run_termux_cmd(["termux-battery-status"])
    if code != 0 or not stdout:
        return f"Error reading battery status: {stderr or 'No output from termux-battery-status'}"

    try:
        data = json.loads(stdout)
        percentage = data.get("percentage", "unknown")
        status = data.get("status", "unknown")
        health = data.get("health", "unknown")
        temp = data.get("temperature", 0.0)
        plugged = data.get("plugged", "UNPLUGGED")

        lines = [
            "🔋 Android Phone Battery Telemetry:",
            f"- **Level:** {percentage}%",
            f"- **Charging Status:** {status} ({plugged})",
            f"- **Battery Health:** {health}",
            f"- **Temperature:** {temp}°C",
        ]
        return "\n".join(lines)
    except Exception as exc:
        return f"Battery telemetry parsed output: {stdout} (error: {exc})"


def handle_torch_control(args: dict[str, Any]) -> str:
    """Control phone flashlight."""
    state = str(args.get("state", "toggle")).strip().lower()
    if state not in ("on", "off"):
        state = "on"

    if not is_android_termux():
        return f"📱 [Desktop Simulation]: Flashlight toggled {state.upper()} successfully."

    code, _stdout, stderr = _run_termux_cmd(["termux-torch", state])
    if code != 0:
        return f"Error toggling flashlight: {stderr}"
    return f"🔦 Phone flashlight has been turned **{state.upper()}**."


def handle_vibrate_phone(args: dict[str, Any]) -> str:
    """Trigger phone haptic vibration."""
    duration = min(5000, max(50, int(args.get("duration_ms", 500))))
    force = bool(args.get("force", False))

    if not is_android_termux():
        return f"📱 [Desktop Simulation]: Haptic vibration pulse ({duration}ms) triggered."

    cmd = ["termux-vibrate", "-d", str(duration)]
    if force:
        cmd.append("-f")

    code, _stdout, stderr = _run_termux_cmd(cmd)
    if code != 0:
        return f"Error triggering vibration: {stderr}"
    return f"📳 Haptic vibration pulse ({duration}ms) sent to phone."


def handle_clipboard_sync(args: dict[str, Any]) -> str:
    """Read or write to Android clipboard."""
    action = str(args.get("action", "get")).strip().lower()
    text = str(args.get("text", "")).strip()

    if action == "set":
        if not text:
            return "Error: text parameter is required when action is 'set'."

        if not is_android_termux():
            return f"📋 [Desktop Simulation]: Copied {len(text)} characters to clipboard:\n`{text[:100]}...`"

        cmd = ["termux-clipboard-set", text]
        code, _stdout, stderr = _run_termux_cmd(cmd)
        if code != 0:
            return f"Error setting clipboard: {stderr}"
        return f"📋 Successfully copied to Android clipboard ({len(text)} characters)."

    # Action: get
    if not is_android_termux():
        return "📋 [Desktop Simulation]: Clipboard contents: (Simulated clipboard buffer)"

    code, stdout, stderr = _run_termux_cmd(["termux-clipboard-get"])
    if code != 0:
        return f"Error reading clipboard: {stderr}"
    return f"📋 Current Android Clipboard Content:\n\n```text\n{stdout}\n```"


def handle_notification_send(args: dict[str, Any]) -> str:
    """Post an Android pull-down notification."""
    title = str(args.get("title", "S.A.R.A. Assistant")).strip()
    content = str(args.get("content", "")).strip()
    priority = str(args.get("priority", "high")).strip().lower()
    if not content:
        return "Error: content parameter is required."

    if not is_android_termux():
        return f"🔔 [Desktop Simulation]: Posted notification: **{title}** — {content}"

    cmd = [
        "termux-notification",
        "--title",
        title,
        "--content",
        content,
        "--priority",
        priority,
        "--id",
        "sara_alert",
    ]
    code, _stdout, stderr = _run_termux_cmd(cmd)
    if code != 0:
        return f"Error posting notification: {stderr}"
    return f"🔔 Android push notification posted: **{title}**"


def handle_camera_vision(args: dict[str, Any]) -> str:
    """Snap a photo from phone camera and perform vision analysis."""
    camera_id = int(args.get("camera_id", 0))
    prompt = str(args.get("prompt", "Describe this image in detail.")).strip()

    photo_dir = Path(__file__).resolve().parent / "data" / "camera"
    photo_dir.mkdir(parents=True, exist_ok=True)
    photo_path = photo_dir / f"snap_{int(time.time())}.jpg"

    if not is_android_termux():
        return (
            f"📸 [Desktop Simulation]: Captured frame from camera ID {camera_id}.\n"
            f"Vision Analysis for prompt '{prompt}':\n"
            f"Simulation: Workspace desk setup with monitor, keyboard, and terminal running S.A.R.A."
        )

    cmd = ["termux-camera-photo", "-c", str(camera_id), str(photo_path)]
    code, _stdout, stderr = _run_termux_cmd(cmd, timeout=12.0)
    if code != 0 or not photo_path.exists():
        return f"Error capturing camera photo: {stderr or 'File not created'}"

    # Analyze with Gemini Vision if API key is present
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            with open(photo_path, "rb") as f:
                img_bytes = f.read()

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
            )
            analysis = response.text.strip() if response.text else "No description generated."
            return f"📸 **Pocket Vision Analysis (Camera {camera_id}):**\n\n{analysis}\n\n*(Image saved: `{photo_path.name}`)*"
        except Exception as exc:
            return f"📸 Photo captured to `{photo_path.name}`. Vision API analysis encountered: {exc}"

    return f"📸 Photo successfully captured and saved to: `{photo_path}`"


def handle_location_get(args: dict[str, Any]) -> str:
    """Query current GPS coordinates on Android."""
    provider = str(args.get("provider", "network")).strip().lower()

    if not is_android_termux():
        return (
            "📍 [Desktop Simulation]: Location telemetry — "
            "Lat: 13.0827° N, Lon: 80.2707° E (Chennai, India) | Accuracy: 15.0m"
        )

    cmd = ["termux-location", "-p", provider, "-r", "once"]
    code, stdout, stderr = _run_termux_cmd(cmd, timeout=10.0)
    if code != 0 or not stdout:
        return f"Error retrieving GPS location: {stderr or 'No location output'}"

    try:
        data = json.loads(stdout)
        lat = data.get("latitude")
        lon = data.get("longitude")
        acc = data.get("accuracy")
        prov = data.get("provider", provider)

        return (
            f"📍 **Current Android GPS Coordinates:**\n"
            f"- **Latitude:** `{lat}`\n"
            f"- **Longitude:** `{lon}`\n"
            f"- **Accuracy:** `{acc}m` (via {prov})"
        )
    except Exception as exc:
        return f"Location output: {stdout} (error: {exc})"


def handle_server_check(args: dict[str, Any]) -> str:
    """Ping / socket test a remote server or port from mobile."""
    host = str(args.get("host", "")).strip()
    port = min(65535, max(1, int(args.get("port", 80))))
    timeout = min(15.0, max(0.5, float(args.get("timeout_seconds", 3.0))))

    if not host:
        return "Error: host parameter is required."

    t0 = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        res = s.connect_ex((host, port))
        latency = (time.time() - t0) * 1000.0
        if res == 0:
            return f"🟢 **Pocket DevOps:** `{host}:{port}` is **ONLINE & REACHABLE** (Latency: `{latency:.1f}ms`)."
        return f"🔴 **Pocket DevOps:** `{host}:{port}` is **OFFLINE or UNREACHABLE** (Error code: {res}, Latency: `{latency:.1f}ms`)."
    except Exception as exc:
        return f"🔴 **Pocket DevOps:** Connection to `{host}:{port}` failed: {exc}"
    finally:
        s.close()


def handle_call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name", "")
    args = params.get("arguments", {})

    if name == "android_battery_status":
        out = handle_battery_status(args)
    elif name == "android_torch_control":
        out = handle_torch_control(args)
    elif name == "android_vibrate_phone":
        out = handle_vibrate_phone(args)
    elif name == "android_clipboard_sync":
        out = handle_clipboard_sync(args)
    elif name == "android_notification_send":
        out = handle_notification_send(args)
    elif name == "android_camera_vision":
        out = handle_camera_vision(args)
    elif name == "android_location_get":
        out = handle_location_get(args)
    elif name == "pocket_devops_server_check":
        out = handle_server_check(args)
    else:
        out = f"error: unknown tool '{name}'"

    return {
        "content": [
            {
                "type": "text",
                "text": out,
            }
        ]
    }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "android-termux-mcp-server",
                        "version": "1.0.0",
                    },
                },
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS},
            }
        elif method == "tools/call":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": handle_call_tool(params),
            }
        elif req_id is not None:
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found"},
            }
        else:
            continue

        sys.stdout.write(json.dumps(res) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
