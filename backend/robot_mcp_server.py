#!/usr/bin/env python3
"""Robot Framework Automated QA & Test Diagnostic MCP Server for S.A.R.A.

Implements JSON-RPC 2.0 stdio Model Context Protocol (2024-11-05 spec) providing
structured automation test execution and failure analysis:
- Discover test suites and test cases (.robot files)
- Run specific suites / tags via Robot Framework Python API
- Parse output.xml into actionable test metrics (passed, failed, skipped, timing)
- Extract failing keywords, error traces, and prepare diagnosis context for the LLM
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# Configure logger
log = logging.getLogger("athena.robot_qa")

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/home/shabari/projects/AI assistant")).resolve()
DEFAULT_REPORT_DIR = WORKSPACE_ROOT / "backend" / "data" / "robot_reports"


TOOLS = [
    {
        "name": "robot_list_suites",
        "description": "Discover and list all Robot Framework (.robot) test suites, test cases, and tags in a directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_dir": {
                    "type": "string",
                    "description": "Directory path to search for .robot files (default: workspace root).",
                }
            },
        },
    },
    {
        "name": "robot_run_suite",
        "description": "Execute a Robot Framework test suite or directory with custom tags, variables, and output logging.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "suite_path": {
                    "type": "string",
                    "description": "Path to the .robot test file or folder containing tests.",
                },
                "include_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tags to include in the test execution (e.g. ['smoke', 'api']).",
                },
                "exclude_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tags to exclude from execution.",
                },
                "variables": {
                    "type": "object",
                    "description": "Key-value dictionary of Robot Framework variables (e.g. {'BASE_URL': 'http://localhost:8000'}).",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Directory to store output.xml, log.html, and report.html.",
                },
            },
            "required": ["suite_path"],
        },
    },
    {
        "name": "robot_parse_results",
        "description": "Parse a Robot Framework output.xml file and extract summary statistics, passed/failed test cases, and failure details.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_xml_path": {
                    "type": "string",
                    "description": "Path to output.xml file (default: latest report in backend/data/robot_reports).",
                }
            },
        },
    },
    {
        "name": "robot_analyze_failures",
        "description": "Extract full failure tracebacks, failed keyword hierarchy, and error messages from the latest or specified test run to generate code fixes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_xml_path": {
                    "type": "string",
                    "description": "Path to output.xml (optional: defaults to latest test execution).",
                }
            },
        },
    },
]


def _find_latest_output_xml(report_dir: Path | None = None) -> Path | None:
    """Find the most recently modified output.xml file."""
    search_dir = report_dir or DEFAULT_REPORT_DIR
    if not search_dir.exists():
        return None
    xml_files = list(search_dir.glob("**/output*.xml"))
    if not xml_files:
        return None
    return max(xml_files, key=lambda f: f.stat().st_mtime)


def handle_list_suites(args: dict[str, Any]) -> str:
    """Scan directory for .robot test files and parse test case names."""
    raw_dir = args.get("target_dir", "")
    target_dir = Path(raw_dir).resolve() if raw_dir else WORKSPACE_ROOT

    if not target_dir.exists():
        return f"Error: Target directory '{target_dir}' does not exist."

    robot_files = sorted(target_dir.rglob("*.robot"))
    if not robot_files:
        return f"🔍 No Robot Framework test suites (.robot) found in `{target_dir}`."

    out = [f"🤖 **Robot Framework Test Suites Found ({len(robot_files)} files):**\n"]

    for file_path in robot_files:
        rel_path = file_path.relative_to(target_dir) if file_path.is_relative_to(target_dir) else file_path
        test_cases = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                in_test_cases = False
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("***") and "test cases" in stripped.lower():
                        in_test_cases = True
                        continue
                    elif stripped.startswith("***") and in_test_cases:
                        in_test_cases = False
                        break
                    if in_test_cases and line and not line.startswith(" ") and not line.startswith("\t") and not stripped.startswith("#"):
                        if stripped:
                            test_cases.append(stripped)
        except Exception:
            pass

        tc_count = len(test_cases)
        out.append(f"📁 **`{rel_path}`** ({tc_count} test{'s' if tc_count != 1 else ''})")
        if test_cases:
            for tc in test_cases[:6]:
                out.append(f"   - {tc}")
            if len(test_cases) > 6:
                out.append(f"   - ... and {len(test_cases) - 6} more")
        out.append("")

    return "\n".join(out)


def handle_run_suite(args: dict[str, Any]) -> str:
    """Execute a Robot Framework test suite."""
    suite_raw = str(args.get("suite_path", "")).strip()
    if not suite_raw:
        return "Error: 'suite_path' is required."

    suite_path = Path(suite_raw)
    if not suite_path.is_absolute():
        suite_path = (WORKSPACE_ROOT / suite_path).resolve()

    if not suite_path.exists():
        return f"Error: Test suite path '{suite_path}' does not exist."

    include_tags = args.get("include_tags") or []
    exclude_tags = args.get("exclude_tags") or []
    variables_dict = args.get("variables") or {}
    
    # Setup report directory
    custom_out = args.get("output_dir")
    run_timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_dir = Path(custom_out).resolve() if custom_out else (DEFAULT_REPORT_DIR / f"run_{run_timestamp}")
    report_dir.mkdir(parents=True, exist_ok=True)

    try:
        import robot
    except ImportError:
        return "Error: Robot Framework is not installed in the current environment. Please install with 'pip install robotframework'."

    # Build variable CLI list: ["KEY:VALUE", ...]
    var_list = [f"{k}:{v}" for k, v in variables_dict.items()]

    t0 = time.perf_counter()
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        run_kwargs: dict[str, Any] = {
            "outputdir": str(report_dir),
            "output": "output.xml",
            "log": "log.html",
            "report": "report.html",
            "stdout": stdout_capture,
            "stderr": stderr_capture,
        }
        if include_tags:
            run_kwargs["include"] = include_tags
        if exclude_tags:
            run_kwargs["exclude"] = exclude_tags
        if var_list:
            run_kwargs["variable"] = var_list

        # Run robot suite programmatically
        return_code = robot.run(str(suite_path), **run_kwargs)
    except Exception as exc:
        return f"Error executing Robot Framework test suite: {exc}"

    elapsed = time.perf_counter() - t0
    output_xml = report_dir / "output.xml"

    status_icon = "🟢" if return_code == 0 else "🔴"
    status_text = "PASSED (All tests passed)" if return_code == 0 else f"FAILED (Exit code {return_code})"

    # Automatically parse output.xml for quick summary
    summary_str = ""
    if output_xml.exists():
        summary_str = _parse_robot_xml(output_xml, detailed=False)

    lines = [
        f"{status_icon} **Robot Framework Test Execution Completed:** `{status_text}`",
        f"- **Suite Path:** `{suite_path}`",
        f"- **Elapsed Time:** `{elapsed:.2f}s`",
        f"- **Report Directory:** `{report_dir}`",
        f"- **Artifacts:** `log.html`, `report.html`, `output.xml`",
        "",
        summary_str,
    ]
    return "\n".join(lines)


def _parse_robot_xml(xml_path: Path, detailed: bool = True) -> str:
    """Parse output.xml and extract statistics and failure traces."""
    if not xml_path.exists():
        return f"Error: XML file '{xml_path}' not found."

    try:
        from robot.result import ExecutionResult, ResultVisitor
    except ImportError:
        return f"Error: robot.result module unavailable. XML file at `{xml_path}`."

    try:
        result = ExecutionResult(str(xml_path))
    except Exception as exc:
        return f"Error parsing Robot XML '{xml_path}': {exc}"

    stats = result.statistics
    total = stats.total.total
    passed = stats.total.passed
    failed = stats.total.failed
    skipped = stats.total.skipped
    elapsed_ms = result.suite.elapsed_time.total_seconds() if hasattr(result.suite, "elapsed_time") else 0.0

    lines = [
        f"📊 **Test Execution Metrics:**",
        f"- **Total Tests:** {total} | 🟢 **Passed:** {passed} | 🔴 **Failed:** {failed} | ⚪ **Skipped:** {skipped}",
        f"- **Duration:** {elapsed_ms:.2f}s",
    ]

    if failed == 0 and not detailed:
        return "\n".join(lines)

    # Collect failure details
    failures = []
    
    class FailureCollector(ResultVisitor):
        def visit_test(self, test):
            if test.status == "FAIL":
                failures.append({
                    "name": test.name,
                    "suite": test.parent.name if test.parent else "Unknown Suite",
                    "message": test.message,
                    "tags": list(test.tags),
                    "elapsed": test.elapsed_time.total_seconds() if hasattr(test, "elapsed_time") else 0.0,
                })

    result.visit(FailureCollector())

    if failures:
        lines.append(f"\n🚨 **Failed Test Cases ({len(failures)}):**")
        for idx, f in enumerate(failures, 1):
            lines.append(f"\n{idx}. **Test:** `{f['name']}` (Suite: `{f['suite']}`)")
            if f.get("tags"):
                lines.append(f"   - **Tags:** `{', '.join(f['tags'])}`")
            lines.append(f"   - **Error Message:**\n   ```text\n   {f['message']}\n   ```")

    return "\n".join(lines)


def handle_parse_results(args: dict[str, Any]) -> str:
    """Parse a specific or latest output.xml."""
    raw_path = args.get("output_xml_path")
    if raw_path:
        xml_path = Path(raw_path).resolve()
    else:
        xml_path = _find_latest_output_xml()
        if not xml_path:
            return "No previous Robot Framework test output.xml found. Run a test suite first."

    return _parse_robot_xml(xml_path, detailed=True)


def handle_analyze_failures(args: dict[str, Any]) -> str:
    """Provide deep diagnostic context for failing Robot Framework test cases."""
    raw_path = args.get("output_xml_path")
    if raw_path:
        xml_path = Path(raw_path).resolve()
    else:
        xml_path = _find_latest_output_xml()
        if not xml_path:
            return "No previous Robot Framework test output.xml found to analyze."

    try:
        from robot.result import ExecutionResult, ResultVisitor
        result = ExecutionResult(str(xml_path))
    except Exception as exc:
        return f"Error loading Robot Framework results from '{xml_path}': {exc}"

    if result.statistics.total.failed == 0:
        return f"🎉 **All tests passed!** No test failures to analyze in `{xml_path}`."

    failures_detailed = []

    class DeepFailureAnalyzer(ResultVisitor):
        def visit_test(self, test):
            if test.status == "FAIL":
                failing_kws = []
                # Traverse keywords in the test to find the exact failed step
                for kw in getattr(test, "body", []):
                    if getattr(kw, "status", None) == "FAIL":
                        failing_kws.append({
                            "keyword": getattr(kw, "name", "Unknown Keyword"),
                            "args": getattr(kw, "args", ()),
                            "doc": getattr(kw, "doc", ""),
                        })

                failures_detailed.append({
                    "test_name": test.name,
                    "suite_name": test.parent.name if test.parent else "Unknown Suite",
                    "suite_source": getattr(test.parent, "source", "") if test.parent else "",
                    "error_message": test.message,
                    "failing_steps": failing_kws,
                })

    result.visit(DeepFailureAnalyzer())

    report = [
        f"🔬 **Athena Robot Framework Failure Diagnosis Report**",
        f"Target Report: `{xml_path}`\n",
    ]

    for idx, item in enumerate(failures_detailed, 1):
        report.append(f"### Failure #{idx}: `{item['test_name']}`")
        report.append(f"- **Suite File:** `{item['suite_source'] or item['suite_name']}`")
        report.append(f"- **Error Summary:**\n```text\n{item['error_message']}\n```")
        if item["failing_steps"]:
            report.append("- **Failing Keyword Chain:**")
            for step in item["failing_steps"]:
                args_str = ", ".join(f"'{a}'" for a in step["args"])
                report.append(f"  - `{step['keyword']}({args_str})`")
        report.append("\n💡 **Recommended AI Action:** Inspect the failing keyword arguments, verify target endpoint/DOM selector availability, and check test precondition setup.\n")

    return "\n".join(report)


def handle_call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name", "")
    args = params.get("arguments", {})

    if name == "robot_list_suites":
        out = handle_list_suites(args)
    elif name == "robot_run_suite":
        out = handle_run_suite(args)
    elif name == "robot_parse_results":
        out = handle_parse_results(args)
    elif name == "robot_analyze_failures":
        out = handle_analyze_failures(args)
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
                        "name": "robot-qa-mcp-server",
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
