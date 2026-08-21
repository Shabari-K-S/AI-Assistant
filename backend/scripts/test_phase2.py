#!/usr/bin/env python3
"""Automated Test & Verification Suite for Phase 2:
- Deep Android Hardware & Sensor Controls (Volume, Wi-Fi, Sensors)
- Advanced Cybersecurity & Network Reconnaissance (SSL/TLS, DNS, WHOIS, Network Diagnostics)
- Autonomous Git Copilot & Robot QA Auto-Repair Loop
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

def test_phase2() -> None:
    print("=" * 60)
    print("📱 1. TESTING DEEP ANDROID HARDWARE & SENSOR CONTROLS")
    print("=" * 60)

    from termux_mcp_server import (
        handle_volume_control,
        handle_wifi_info,
        handle_sensor_telemetry,
        handle_call_tool as termux_dispatcher,
    )

    # 1. Volume Control
    print("\n- Testing handle_volume_control (Query)...")
    res_vol = handle_volume_control({})
    print(f"  Volume Query:\n{res_vol}")
    assert "Volume" in res_vol or "media" in res_vol.lower()
    print("  ✅ handle_volume_control (Query) passed.")

    print("\n- Testing handle_volume_control (Set)...")
    res_vol_set = handle_volume_control({"stream": "music", "volume": 8})
    print(f"  Volume Set: {res_vol_set}")
    assert "volume" in res_vol_set.lower()
    print("  ✅ handle_volume_control (Set) passed.")

    # 2. Wi-Fi Connection Info
    print("\n- Testing handle_wifi_info...")
    res_wifi = handle_wifi_info({})
    print(f"  Wi-Fi Telemetry:\n{res_wifi}")
    assert "Wi-Fi" in res_wifi or "SSID" in res_wifi
    print("  ✅ handle_wifi_info passed.")

    # 3. Hardware Sensors
    print("\n- Testing handle_sensor_telemetry...")
    res_sensor = handle_sensor_telemetry({"sensor_type": "all"})
    print(f"  Sensor Telemetry:\n{res_sensor}")
    assert "Sensor" in res_sensor or "Light" in res_sensor
    print("  ✅ handle_sensor_telemetry passed.")

    # 4. Dispatcher Check
    call_res = termux_dispatcher({"name": "android_wifi_info", "arguments": {}})
    assert "content" in call_res and len(call_res["content"]) > 0
    print("  ✅ Termux MCP JSON-RPC Dispatcher passed.")

    print("\n" + "=" * 60)
    print("🔒 2. TESTING ADVANCED CYBERSECURITY & NETWORK RECON")
    print("=" * 60)

    from security_mcp_server import (
        handle_ssl_inspect,
        handle_dns_recon,
        handle_whois_lookup,
        handle_network_diagnostic,
        handle_call_tool as security_dispatcher,
    )

    # 1. SSL/TLS Inspector
    print("\n- Testing handle_ssl_inspect against google.com:443...")
    res_ssl = handle_ssl_inspect({"host": "google.com", "port": 443})
    print(f"  SSL Inspection Output:\n{res_ssl}")
    assert "SSL/TLS" in res_ssl and ("VALID" in res_ssl or "Google" in res_ssl or "Expires" in res_ssl)
    print("  ✅ handle_ssl_inspect passed.")

    # 2. DNS & Email Security Recon
    print("\n- Testing handle_dns_recon against cloudflare.com...")
    res_dns = handle_dns_recon({"domain": "cloudflare.com"})
    print(f"  DNS Recon Output:\n{res_dns}")
    assert "DNS" in res_dns and ("IPv4" in res_dns or "SPF" in res_dns)
    print("  ✅ handle_dns_recon passed.")

    # 3. WHOIS / RDAP Directory Lookup
    print("\n- Testing handle_whois_lookup against 8.8.8.8...")
    res_whois = handle_whois_lookup({"target": "8.8.8.8"})
    print(f"  WHOIS Output:\n{res_whois}")
    assert "WHOIS" in res_whois or "RDAP" in res_whois or "Handle" in res_whois
    print("  ✅ handle_whois_lookup passed.")

    # 4. Network Latency & Diagnostic
    print("\n- Testing handle_network_diagnostic against 1.1.1.1:443...")
    res_net = handle_network_diagnostic({"host": "1.1.1.1", "port": 443, "count": 3})
    print(f"  Network Diagnostic Output:\n{res_net}")
    assert "Network" in res_net and ("Latency" in res_net or "Probed" in res_net)
    print("  ✅ handle_network_diagnostic passed.")

    # 5. Security Dispatcher Check
    call_sec = security_dispatcher({"name": "security_ssl_inspect", "arguments": {"host": "google.com"}})
    assert "content" in call_sec
    print("  ✅ Security MCP JSON-RPC Dispatcher passed.")

    print("\n" + "=" * 60)
    print("🌿 3. TESTING AUTONOMOUS GIT COPILOT & QA AUTO-FIX LOOP")
    print("=" * 60)

    from git_mcp_server import (
        handle_git_status,
        handle_git_diff,
        handle_git_apply_patch,
        handle_call_tool as git_dispatcher,
    )

    # 1. Git Status
    print("\n- Testing handle_git_status...")
    res_status = handle_git_status({})
    print(f"  Git Status:\n{res_status}")
    assert "Git Repository Status" in res_status
    print("  ✅ handle_git_status passed.")

    # 2. Git Diff
    print("\n- Testing handle_git_diff...")
    res_diff = handle_git_diff({})
    print(f"  Git Diff Preview:\n{res_diff[:200]}...")
    assert "Git Diff" in res_diff or "No code differences" in res_diff
    print("  ✅ handle_git_diff passed.")

    # 3. Git Apply Patch
    print("\n- Testing handle_git_apply_patch...")
    test_file = "data/test_patch_sample.txt"
    test_content = "S.A.R.A. Autonomous QA Patch Verification: OK"
    res_patch = handle_git_apply_patch({"file_path": test_file, "content": test_content})
    print(f"  Patch Result: {res_patch}")
    assert "Successfully updated" in res_patch

    # Verify file content
    written_path = BACKEND_DIR.parent / test_file
    assert written_path.exists()
    assert written_path.read_text(encoding="utf-8") == test_content
    # Cleanup test artifact
    written_path.unlink()
    print("  ✅ handle_git_apply_patch passed.")

    # 4. Git Dispatcher Check
    call_git = git_dispatcher({"name": "git_status", "arguments": {}})
    assert "content" in call_git
    print("  ✅ Git Copilot MCP JSON-RPC Dispatcher passed.")

    print("\n" + "=" * 60)
    print("🎉 ALL PHASE 2 TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_phase2()
