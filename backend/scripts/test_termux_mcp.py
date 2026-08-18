#!/usr/bin/env python3
"""Test script for Android Termux Mobile Superpowers MCP Server."""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from termux_mcp_server import (
    is_android_termux,
    handle_battery_status,
    handle_torch_control,
    handle_vibrate_phone,
    handle_clipboard_sync,
    handle_notification_send,
    handle_camera_vision,
    handle_location_get,
    handle_server_check,
    TOOLS,
)


def test_termux_mcp():
    print("=" * 70)
    print("📱 S.A.R.A. ANDROID TERMUX MOBILE SUPERPOWERS TEST SUITE")
    print("=" * 70)

    is_android = is_android_termux()
    print(f"\n1. Runtime Environment Detection: {'🤖 Android (Termux)' if is_android else '💻 Desktop (Cross-Platform Fallback)'}")

    # 2. Test Battery Telemetry
    print("\n2. Testing Battery Status Handler...")
    bat_res = handle_battery_status({})
    print(f"   Output:\n{bat_res}")
    assert "Battery" in bat_res or "Level" in bat_res
    print("   ✅ Battery telemetry handler passed.")

    # 3. Test Torch Control
    print("\n3. Testing Torch / Flashlight Control...")
    torch_on = handle_torch_control({"state": "on"})
    print(f"   Torch ON: {torch_on}")
    torch_off = handle_torch_control({"state": "off"})
    print(f"   Torch OFF: {torch_off}")
    assert "ON" in torch_on and "OFF" in torch_off
    print("   ✅ Torch control handler passed.")

    # 4. Test Phone Haptic Vibration
    print("\n4. Testing Phone Haptic Vibration...")
    vib_res = handle_vibrate_phone({"duration_ms": 600})
    print(f"   Vibrate output: {vib_res}")
    assert "vibration" in vib_res.lower()
    print("   ✅ Haptic vibration handler passed.")

    # 5. Test Clipboard Sync (Set & Get)
    print("\n5. Testing Phone Clipboard Sync...")
    clip_set = handle_clipboard_sync({"action": "set", "text": "Secret Token 12345"})
    print(f"   Clipboard Set: {clip_set}")
    clip_get = handle_clipboard_sync({"action": "get"})
    print(f"   Clipboard Get: {clip_get}")
    assert "clipboard" in clip_set.lower() and "clipboard" in clip_get.lower()
    print("   ✅ Clipboard sync handler passed.")

    # 6. Test Android Notification Posting
    print("\n6. Testing Android Push Notification...")
    notif_res = handle_notification_send({
        "title": "S.A.R.A. Test Alert",
        "content": "Deep research report compilation completed successfully!",
        "priority": "high",
    })
    print(f"   Notification output: {notif_res}")
    assert "notification" in notif_res.lower()
    print("   ✅ Android push notification handler passed.")

    # 7. Test Camera Pocket Vision
    print("\n7. Testing Camera Pocket Vision Handler...")
    cam_res = handle_camera_vision({"camera_id": 0, "prompt": "Analyze desk setup."})
    print(f"   Camera output: {cam_res}")
    assert "camera" in cam_res.lower() or "vision" in cam_res.lower() or "photo" in cam_res.lower()
    print("   ✅ Camera pocket vision handler passed.")

    # 8. Test GPS Location
    print("\n8. Testing Android GPS Location Handler...")
    loc_res = handle_location_get({"provider": "network"})
    print(f"   Location output: {loc_res}")
    assert "location" in loc_res.lower() or "lat" in loc_res.lower()
    print("   ✅ GPS location handler passed.")

    # 9. Test Pocket DevOps Server Check
    print("\n9. Testing Pocket DevOps Server & Port Check...")
    devops_res = handle_server_check({"host": "127.0.0.1", "port": 80, "timeout_seconds": 1.0})
    print(f"   DevOps output: {devops_res}")
    assert "Pocket DevOps" in devops_res
    print("   ✅ Pocket DevOps server check passed.")

    print(f"\n10. Total Registered Android Tools in MCP Schema: {len(TOOLS)}")
    assert len(TOOLS) == 8
    print("   ✅ All 8 tools defined in JSON Schema.")

    print("\n" + "=" * 70)
    print("✅ ALL ANDROID TERMUX MOBILE SUPERPOWERS TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    test_termux_mcp()
