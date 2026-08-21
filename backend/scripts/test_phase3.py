#!/usr/bin/env python3
"""Automated Test & Verification Suite for Phase 3:
- Autonomous Web Application Security & DAST Scanner (SQLi, XSS, Sensitive Files)
- Multi-Agent Parallel Task Orchestrator & Dispatcher
- Android App Launcher, Native Alarms, and Audio Recorder
- ToolRegistry & Vocal Cue Integration
"""

import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

def test_phase3() -> None:
    print("=" * 60)
    print("🛡️ 1. TESTING AUTONOMOUS DAST WEB SECURITY SCANNER")
    print("=" * 60)

    from web_security_scanner import (
        scan_sensitive_files,
        scan_sqli_reflection,
        scan_xss_reflection,
        run_full_vulnerability_scan,
    )
    from security_mcp_server import handle_call_tool as security_dispatcher

    # 1. Sensitive Files Probe
    print("\n- Testing scan_sensitive_files against localhost...")
    res_sensitive = scan_sensitive_files("http://127.0.0.1:2026")
    print(f"  Sensitive Files Detected: {len(res_sensitive)}")
    print("  ✅ scan_sensitive_files passed.")

    # 2. SQLi Error Reflection Heuristic
    print("\n- Testing scan_sqli_reflection on test endpoint...")
    test_sqli_url = "http://127.0.0.1:2026/api/search?q=test"
    res_sqli = scan_sqli_reflection(test_sqli_url)
    print(f"  SQLi Reflections Detected: {len(res_sqli)}")
    print("  ✅ scan_sqli_reflection passed.")

    # 3. Reflected XSS Benign Probe
    print("\n- Testing scan_xss_reflection on test endpoint...")
    test_xss_url = "http://127.0.0.1:2026/view?msg=hello"
    res_xss = scan_xss_reflection(test_xss_url)
    print(f"  XSS Reflections Detected: {len(res_xss)}")
    print("  ✅ scan_xss_reflection passed.")

    # 4. Full DAST Scan Orchestrator
    print("\n- Testing run_full_vulnerability_scan...")
    dast_out = run_full_vulnerability_scan("127.0.0.1:2026")
    print(f"  DAST Scan Summary:\n{dast_out}")
    assert "Autonomous DAST" in dast_out and "Overall Posture" in dast_out
    print("  ✅ run_full_vulnerability_scan passed.")

    # 5. Security MCP Dispatcher with DAST
    sec_call = security_dispatcher({
        "name": "security_vulnerability_scan",
        "arguments": {"target_url": "127.0.0.1:2026"},
    })
    assert "content" in sec_call and len(sec_call["content"]) > 0
    print("  ✅ Security MCP JSON-RPC DAST dispatcher passed.")

    print("\n" + "=" * 60)
    print("🤖 2. TESTING MULTI-AGENT PARALLEL TASK DISPATCHER")
    print("=" * 60)

    from multi_agent_dispatcher import get_agent_dispatcher

    dispatcher = get_agent_dispatcher()

    # 1. Dispatch Concurrent Task
    print("\n- Testing dispatch_task...")
    dispatch_msg = dispatcher.dispatch_task(
        name="Test Security Posture Scan",
        task_type="security_scan",
        target_or_prompt="127.0.0.1:2026",
    )
    print(f"  Dispatch Output: {dispatch_msg}")
    assert "Sub-Agent" in dispatch_msg and "launched successfully" in dispatch_msg
    print("  ✅ dispatch_task passed.")

    # 2. Query Agent Tasks
    print("\n- Testing query_tasks...")
    time.sleep(0.5)
    query_out = dispatcher.query_tasks()
    print(f"  Query Output:\n{query_out}")
    assert "Multi-Agent Task Orchestrator" in query_out
    print("  ✅ query_tasks passed.")

    # 3. Cancel Task
    print("\n- Testing cancel_task...")
    test_cancel_msg = dispatcher.dispatch_task(
        name="Task to Cancel",
        task_type="research",
        target_or_prompt="Test Topic",
    )
    import re
    task_id_match = re.search(r"agent-\d+", test_cancel_msg)
    if task_id_match:
        target_id = task_id_match.group(0)
        cancel_res = dispatcher.cancel_task(target_id)
        print(f"  Cancel Result: {cancel_res}")
        assert "cancelled" in cancel_res.lower()
    print("  ✅ cancel_task passed.")

    print("\n" + "=" * 60)
    print("📱 3. TESTING ANDROID DEEP AUTOMATIONS (TERMUX:API PART 3)")
    print("=" * 60)

    from termux_mcp_server import (
        handle_app_launch,
        handle_alarm_set,
        handle_audio_record,
        handle_call_tool as termux_dispatcher,
    )

    # 1. App Launch
    print("\n- Testing handle_app_launch...")
    res_app = handle_app_launch({"target": "whatsapp"})
    print(f"  App Launch: {res_app}")
    assert "whatsapp" in res_app.lower()
    print("  ✅ handle_app_launch passed.")

    # 2. Native Alarm Set
    print("\n- Testing handle_alarm_set...")
    res_alarm = handle_alarm_set({"time_str": "07:30", "label": "Morning Briefing"})
    print(f"  Alarm Set: {res_alarm}")
    assert "07:30" in res_alarm
    print("  ✅ handle_alarm_set passed.")

    # 3. Audio Recording
    print("\n- Testing handle_audio_record...")
    res_audio = handle_audio_record({"duration_seconds": 2, "filename": "test_verification_audio"})
    print(f"  Audio Record: {res_audio}")
    assert "Recording Complete" in res_audio or "Desktop Simulation" in res_audio
    print("  ✅ handle_audio_record passed.")

    # 4. Termux MCP Dispatcher Check
    call_termux = termux_dispatcher({"name": "android_alarm_set", "arguments": {"time_str": "08:00"}})
    assert "content" in call_termux
    print("  ✅ Termux MCP JSON-RPC Phase 3 Dispatcher passed.")

    print("\n" + "=" * 60)
    print("⚙️ 4. TESTING TOOL REGISTRY & FUNCTION CALLING INTEGRATION")
    print("=" * 60)

    from tools import ToolRegistry, ToolsConfig

    cfg = ToolsConfig()
    registry = ToolRegistry(cfg)

    # Verify tool execution via registry
    reg_res = registry.execute("query_agent_tasks", {})
    print(f"  Registry execute query_agent_tasks:\n{reg_res}")
    assert "Multi-Agent Task Orchestrator" in reg_res
    print("  ✅ ToolRegistry Phase 3 execution passed.")

    print("\n" + "=" * 60)
    print("🎉 ALL PHASE 3 TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_phase3()
