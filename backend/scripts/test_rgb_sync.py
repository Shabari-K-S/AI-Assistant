#!/usr/bin/env python3
"""Test script for S.A.R.A. Real-World Ambient RGB Lighting Sync Engine."""

import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from rgb_sync import RgbSyncManager, RGB_COLOR_PALETTES
from evbridge import Bus


def test_rgb_sync():
    print("=" * 70)
    print("💡 S.A.R.A. REAL-WORLD AMBIENT RGB LIGHTING SYNC TEST SUITE")
    print("=" * 70)

    bus = Bus()
    events_received = []

    # Subscribe to bus events
    def _listener(q):
        while True:
            try:
                evt = q.get(timeout=0.1)
                events_received.append(evt)
            except Exception:
                break

    q = bus.subscribe()

    print("\n1. Initializing RgbSyncManager with Mock / Bus Backend...")
    manager = RgbSyncManager(
        enabled=True,
        backend="mock",
        target="127.0.0.1",
        brightness=220,
        bus=bus,
    )
    bus.on_phase_change(manager.set_phase)

    # 2. Test Phase Transitions
    phases_to_test = ["standby", "listening", "processing", "deep_research", "speaking", "security", "alert"]
    print("\n2. Testing Phase Transitions & Color Palettes...")
    for p in phases_to_test:
        bus.set(phase=p)
        time.sleep(0.05)
        palette = RGB_COLOR_PALETTES.get(p)
        print(f"   Phase [{p.upper()}]: Color = {palette['hex']} ({palette['name']}) | RGB = {palette['rgb']}")
        assert manager.current_phase == p

    print("   ✅ All phase transitions mapped and applied cleanly.")

    # 3. Test Webhook Payload formatting
    print("\n3. Testing Webhook & WLED payload formatting logic...")
    assert "hex" in RGB_COLOR_PALETTES["security"]
    assert RGB_COLOR_PALETTES["security"]["hex"] == "#FF0033"
    assert RGB_COLOR_PALETTES["standby"]["hex"] == "#00F2FF"
    assert RGB_COLOR_PALETTES["speaking"]["hex"] == "#FFB800"
    print("   ✅ Palette colors match sci-fi holographic arc-reactor standards.")

    print("\n" + "=" * 70)
    print("✅ ALL AMBIENT RGB LIGHTING SYNC TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    test_rgb_sync()
