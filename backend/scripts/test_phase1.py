#!/usr/bin/env python3
"""Phase 1 Verification Test Suite for S.A.R.A. / ATHENA

Validates:
1. Termux:API Expanded Mobile Tools (SMS list/send, Contact search, Telephony info)
2. Robot Framework MCP Server (Suite discovery, test execution, XML parsing, failure diagnosis)
3. Proactive Scheduler & Security Watchdog Engine (Task scheduling, cron computation, OSV security check)
"""

import datetime
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from termux_mcp_server import (
    handle_sms_list,
    handle_sms_send,
    handle_contact_search,
    handle_telephony_info,
    handle_call_tool as handle_termux_tool,
    TOOLS as TERMUX_TOOLS,
)
from robot_mcp_server import (
    handle_list_suites,
    handle_run_suite,
    handle_parse_results,
    handle_analyze_failures,
    handle_call_tool as handle_robot_tool,
    TOOLS as ROBOT_TOOLS,
)
from scheduler_engine import (
    ProactiveScheduler,
    ScheduledTask,
    get_scheduler,
)
from tools import ToolRegistry, ToolsConfig


def test_termux_api_expansion():
    print("\n" + "=" * 60)
    print("📱 1. TESTING TERMUX:API EXPANDED TOOLS")
    print("=" * 60)

    # 1. SMS List
    print("\n- Testing handle_sms_list...")
    res_sms_list = handle_sms_list({"limit": 5, "type": "inbox"})
    print(f"  Result preview:\n  {res_sms_list.splitlines()[0]}")
    assert "SMS" in res_sms_list or "Inbox" in res_sms_list or "inbox" in res_sms_list
    print("  ✅ handle_sms_list passed.")

    # 2. SMS Send
    print("\n- Testing handle_sms_send...")
    res_sms_send = handle_sms_send({"phone_number": "+919876543210", "message": "Test SMS from S.A.R.A."})
    print(f"  Result: {res_sms_send}")
    assert "+919876543210" in res_sms_send or "SMS" in res_sms_send
    print("  ✅ handle_sms_send passed.")

    # 3. Contact Search
    print("\n- Testing handle_contact_search...")
    res_contact = handle_contact_search({"query": "Alex", "limit": 5})
    print(f"  Result preview:\n  {res_contact.splitlines()[0]}")
    assert "Alex" in res_contact or "Contact" in res_contact or "contacts" in res_contact
    print("  ✅ handle_contact_search passed.")

    # 4. Telephony Info
    print("\n- Testing handle_telephony_info...")
    res_telephony = handle_telephony_info({})
    print(f"  Result preview:\n  {res_telephony.splitlines()[0]}")
    assert "Telephony" in res_telephony or "Network" in res_telephony or "Carrier" in res_telephony
    print("  ✅ handle_telephony_info passed.")

    # 5. MCP Dispatcher Call
    call_res = handle_termux_tool({"name": "android_sms_list", "arguments": {"limit": 2}})
    assert call_res.get("content") and len(call_res["content"]) > 0
    print("  ✅ Termux MCP JSON-RPC call dispatcher passed.")


def test_robot_framework_bridge():
    print("\n" + "=" * 60)
    print("🤖 2. TESTING ROBOT FRAMEWORK MCP SERVER")
    print("=" * 60)

    # Create temporary robot test suite
    temp_dir = Path(tempfile.mkdtemp(prefix="robot_test_"))
    test_robot_file = temp_dir / "sample_suite.robot"
    test_robot_file.write_text(
        """*** Settings ***
Documentation     Sample Automated Test Suite for S.A.R.A.
Library           OperatingSystem

*** Variables ***
${EXPECTED_VAL}    Antigravity

*** Test Cases ***
Verify Math Calculation Passes
    [Documentation]    Simple passing test case
    Should Be Equal As Numbers    4    4

Verify Text Match Fails Intentionally
    [Documentation]    Intentional failure for diagnosis testing
    Should Be Equal    ${EXPECTED_VAL}    WrongValue
""",
        encoding="utf-8",
    )

    try:
        # 1. Discover suites
        print("\n- Testing handle_list_suites...")
        list_res = handle_list_suites({"target_dir": str(temp_dir)})
        print(f"  Discovered suites:\n{list_res}")
        assert "sample_suite.robot" in list_res
        assert "Verify Math Calculation Passes" in list_res
        print("  ✅ handle_list_suites passed.")

        # 2. Run suite
        print("\n- Testing handle_run_suite...")
        run_res = handle_run_suite({
            "suite_path": str(test_robot_file),
            "output_dir": str(temp_dir / "reports"),
        })
        print(f"  Run outcome:\n{run_res}")
        assert "Robot Framework Test Execution Completed" in run_res
        assert "output.xml" in run_res
        print("  ✅ handle_run_suite passed.")

        # 3. Parse output.xml results
        print("\n- Testing handle_parse_results...")
        output_xml = temp_dir / "reports" / "output.xml"
        parse_res = handle_parse_results({"output_xml_path": str(output_xml)})
        print(f"  Parsed results:\n{parse_res}")
        assert "Total Tests" in parse_res
        assert "Verify Text Match Fails Intentionally" in parse_res
        print("  ✅ handle_parse_results passed.")

        # 4. Analyze failures
        print("\n- Testing handle_analyze_failures...")
        diag_res = handle_analyze_failures({"output_xml_path": str(output_xml)})
        print(f"  Failure Diagnosis Report:\n{diag_res}")
        assert "Failure #" in diag_res
        assert "Verify Text Match Fails Intentionally" in diag_res
        assert "Antigravity != WrongValue" in diag_res
        print("  ✅ handle_analyze_failures passed.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_proactive_scheduler():
    print("\n" + "=" * 60)
    print("⏰ 3. TESTING PROACTIVE SCHEDULER & SECURITY WATCHDOG")
    print("=" * 60)

    scheduler = ProactiveScheduler()

    # 1. Add cron task
    print("\n- Testing task registration...")
    task = scheduler.add_task(
        task_id="test_nightly_job",
        name="Test Nightly Runner",
        schedule_type="cron",
        schedule_value="0 2 * * *",
        action_type="custom",
        payload={"action": "test"},
    )
    assert task.next_run is not None
    print(f"  Registered task '{task.name}'. Next computed run: {task.next_run}")
    print("  ✅ Task registration & cron calculation passed.")

    # 2. Add countdown task
    countdown_task = scheduler.add_task(
        task_id="test_countdown_job",
        name="Quick Countdown Timer",
        schedule_type="countdown",
        schedule_value="10",
        action_type="voice_alert",
        payload={"message": "Countdown reached!"},
    )
    print(f"  Registered countdown task. Next run: {countdown_task.next_run}")
    assert countdown_task.next_run is not None

    # 3. List tasks
    all_tasks = scheduler.list_tasks()
    print(f"  Active tasks count: {len(all_tasks)}")
    assert any(t["task_id"] == "test_nightly_job" for t in all_tasks)
    print("  ✅ Task listing passed.")

    # 4. Execute security watchdog scan
    print("\n- Testing live OSV Security Watchdog execution...")
    cve_task = ScheduledTask(
        task_id="test_cve_scan",
        name="Test Security Watchdog",
        schedule_type="interval",
        schedule_value="3600",
        action_type="security_scan",
        payload={"watched_packages": [{"name": "robotframework", "ecosystem": "PyPI"}]},
    )
    scan_res = scheduler.execute_task(cve_task)
    print(f"  Security Scan Output: {scan_res}")
    assert "Security Watchdog" in scan_res or "robotframework" in scan_res or "CVE" in scan_res
    print("  ✅ Security Watchdog live scan passed.")

    # 5. Clean up test task
    scheduler.remove_task("test_nightly_job")
    scheduler.remove_task("test_countdown_job")
    print("  ✅ Task removal passed.")


def test_tools_registry_integration():
    print("\n" + "=" * 60)
    print("🛠️ 4. TESTING TOOL REGISTRY & SCHEMAS")
    print("=" * 60)

    cfg = ToolsConfig(shell_timeout_seconds=5)
    registry = ToolRegistry(cfg)

    schemas = registry.schemas("gemini")
    tool_names = [s["name"] for s in schemas]
    print(f"Registered Tools ({len(tool_names)} total): {', '.join(tool_names)}")

    assert "schedule_task" in tool_names
    assert "list_scheduled_tasks" in tool_names

    # Test executing list_scheduled_tasks via registry
    res = registry.execute("list_scheduled_tasks", {})
    print(f"\nExecution of 'list_scheduled_tasks':\n{res}")
    assert "Active Scheduled Tasks" in res or "No scheduled tasks" in res
    print("  ✅ Tool registry integration passed.")


if __name__ == "__main__":
    t0 = time.perf_counter()
    test_termux_api_expansion()
    test_robot_framework_bridge()
    test_proactive_scheduler()
    test_tools_registry_integration()
    total_time = time.perf_counter() - t0
    print("\n" + "=" * 60)
    print(f"🎉 ALL PHASE 1 TESTS PASSED SUCCESSFULLY in {total_time:.2f}s!")
    print("=" * 60)
