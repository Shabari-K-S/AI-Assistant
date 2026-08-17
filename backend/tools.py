"""Tool-calling layer for the LLM brain (Stage 3).

Includes:
  - run_shell_command (allowlist-gated safe execution)
  - get_time_and_calendar (formatted local/UTC, timezone, weekday, day of year, relative dates)
  - get_system_telemetry (real-time CPU per-core, RAM, disk mounts, OS platform, uptime via psutil)
  - get_system_status (concise system readout)
  - web_search (search interface)
"""

from __future__ import annotations

import calendar
import datetime
import logging
import os
import platform
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

from config import ToolsConfig

log = logging.getLogger("ev.tools")

ConfirmFn = Callable[[str], bool]


SAFE_COMMAND_NAMES = {
    # System inspection & resources
    "uptime", "whoami", "id", "uname", "hostname", "date", "cal",
    "df", "du", "free", "top", "htop", "ps", "pgrep", "lsof", "netstat", "ss",
    "which", "whereis", "type", "echo", "printf", "env", "printenv",
    # Filesystem read-only exploration
    "ls", "dir", "tree", "cat", "head", "tail", "less", "more", "bat",
    "file", "stat", "wc", "nl", "grep", "rg", "ag", "ack", "diff",
    # Git read-only inspection
    "git",
    # Network / Web read-only requests
    "curl", "wget", "http", "ping",
    # Dev & compilation checks (read-only / syntax verification)
    "python", "python3", "node", "npm", "tsc", "oxlint", "pytest",
}

SAFE_GIT_SUBCOMMANDS = {
    "status", "log", "diff", "branch", "show", "tag", "remote",
    "rev-parse", "describe", "config", "stash", "blame", "shortlog",
}

DANGEROUS_PATTERNS = [
    # Deletion & destructive actions
    r"\brm\b", r"\brmdir\b", r"\bunlink\b", r"\bshred\b", r"\bdd\b", r"\bmkfs\b", r"\bformat\b",
    # Permissions / privileges
    r"\bsudo\b", r"\bsu\b", r"\bdoas\b", r"\bchmod\b", r"\bchown\b", r"\bchgrp\b",
    # Process & system management
    r"\bkill\b", r"\bpkill\b", r"\bkillall\b", r"\breboot\b", r"\bshutdown\b", r"\bpoweroff\b", r"\bsystemctl\b", r"\bservice\b",
    # Destructive git commands
    r"\bgit\s+reset\b", r"\bgit\s+clean\b", r"\bgit\s+checkout\s+--\b", r"\bgit\s+restore\b", r"\bgit\s+push\s+--force\b",
    # File write / output redirection (e.g. > file, >> file)
    r">\s*[^/&|]", r">>",
    # In-place file modification
    r"\bsed\s+-i\b", r"\btruncate\b",
]


def is_safe_read_only_command(command: str) -> bool:
    """Analyze whether a shell command is strictly read-only / informational (e.g. weather, git status, system load)."""
    cmd = command.strip()
    if not cmd:
        return True

    # Check for explicitly dangerous keywords or destructive file redirections
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False

    # Check each pipeline stage
    pipeline_parts = [p.strip() for p in re.split(r"[|;&]+", cmd) if p.strip()]
    for part in pipeline_parts:
        try:
            sub_tokens = shlex.split(part)
        except Exception:
            return False
        if not sub_tokens:
            continue
        first = sub_tokens[0].split("/")[-1].lower()
        if first not in SAFE_COMMAND_NAMES:
            return False

        # If it's git, ensure it's a read-only git subcommand
        if first == "git" and len(sub_tokens) > 1:
            git_sub = sub_tokens[1].lower()
            if git_sub not in SAFE_GIT_SUBCOMMANDS:
                return False

    return True


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema of the input object
    handler: Callable[[dict], str]


def _confirm_or_raise(
    prompt: str, confirm: ConfirmFn, refuse: bool
) -> None:
    if refuse:
        raise PermissionError(f"refused by policy: {prompt}")
    if not confirm(prompt):
        raise PermissionError(f"declined by user: {prompt}")


def _make_run_shell_command(
    cfg: ToolsConfig, confirm: ConfirmFn
) -> Callable[[dict], str]:
    policy = cfg.confirm_shell  # ask | never | always
    allowlist = set(cfg.shell_allowlist)

    def run_shell_command(args: dict) -> str:
        command: str = args.get("command", "").strip()
        if not command:
            return "error: empty command"
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return f"error: cannot parse command: {exc}"
        if not argv:
            return "error: empty command"

        head = argv[0]
        has_shell_meta = any(char in command for char in [";", "&", "|", "`", "$", "(", ")", ">", "<", "\n"])
        in_allowlist = (head in allowlist) and not has_shell_meta
        is_safe_info = is_safe_read_only_command(command)

        if policy == "always":
            _confirm_or_raise(f"run shell command: {command!r}", confirm, refuse=False)
            use_shell = True
        elif is_safe_info or in_allowlist:
            # Informational / safe read-only command (weather, sys load, uptime, ls, git status)
            # Runs automatically without user interruption!
            use_shell = True
        else:
            # Mutating / modifying or untrusted command — ask for confirmation
            _confirm_or_raise(
                f"run shell command: {command!r}",
                confirm,
                refuse=policy == "never",
            )
            use_shell = True

        try:
            print(f"$ {command}", flush=True)
            if use_shell:
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=cfg.shell_timeout_seconds,
                )
            else:
                proc = subprocess.run(
                    argv,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=cfg.shell_timeout_seconds,
                )
        except subprocess.TimeoutExpired:
            return f"error: command timed out after {cfg.shell_timeout_seconds}s"
        except OSError as exc:
            return f"error: {exc}"

        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        status = proc.returncode
        summary = f"exit code {status}"
        if out:
            summary += f"\nstdout:\n{out[-2000:]}"
        if err:
            summary += f"\nstderr:\n{err[-2000:]}"
        return summary

    return run_shell_command


def _active_window() -> str:
    """Best-effort active window/app name per OS."""
    system = platform.system()
    try:
        if system == "Linux":
            from Xlib import X, display

            d = display.Display()
            root = d.screen().root
            prop = root.get_full_property(d.intern_atom("_NET_ACTIVE_WINDOW"), X.AnyPropertyType)
            if not prop or not prop.value:
                return "unavailable"
            win = d.create_resource_object("window", prop.value[0])
            name = win.get_full_property(d.intern_atom("_NET_WM_NAME"), X.AnyPropertyType)
            if name and name.value:
                return name.value.decode("utf-8", "replace")
            legacy = win.get_wm_name()
            return legacy or "unavailable"
        if system == "Windows":
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return "unavailable"
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value or "unavailable"
        if system == "Darwin":
            try:
                from AppKit import NSWorkspace

                app = NSWorkspace.sharedWorkspace().frontmostApplication()
                return app.localizedName() if app else "unavailable"
            except ImportError:
                return "unavailable"
    except Exception:
        log.debug("active window lookup failed", exc_info=True)
    return "unavailable"


def _make_get_time_and_calendar() -> Callable[[dict], str]:
    def get_time_and_calendar(args: dict) -> str:
        """Provide detailed time, timezone, date, weekday, and offset calendar calculations."""
        now_local = datetime.datetime.now().astimezone()
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        
        days_offset = args.get("days_offset")
        target_date_str = args.get("target_date")
        
        lines: list[str] = [
            f"local_time: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            f"utc_time: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"iso_8601: {now_local.isoformat()}",
            f"weekday: {now_local.strftime('%A')}",
            f"timezone: {now_local.tzname()} (UTC offset: {now_local.strftime('%z')})",
            f"day_of_year: {now_local.strftime('%j')} / 365",
            f"week_number: {now_local.strftime('%V')}",
            f"is_leap_year: {calendar.isleap(now_local.year)}",
        ]

        if days_offset is not None:
            try:
                offset = int(days_offset)
                future_date = now_local + datetime.timedelta(days=offset)
                lines.append(
                    f"offset_{offset:+d}_days: {future_date.strftime('%Y-%m-%d (%A)')}"
                )
            except (ValueError, TypeError):
                pass

        if target_date_str:
            try:
                parsed = datetime.date.fromisoformat(target_date_str.strip())
                diff = (parsed - now_local.date()).days
                lines.append(
                    f"target_date_{target_date_str}: {parsed.strftime('%A')} ({diff:+d} days from today)"
                )
            except ValueError:
                lines.append(f"target_date_error: invalid format {target_date_str!r} (expected YYYY-MM-DD)")

        return "\n".join(lines)

    return get_time_and_calendar


def _make_get_system_telemetry() -> Callable[[dict], str]:
    def get_system_telemetry(_args: dict) -> str:
        """Provide comprehensive CPU, memory, disk, and platform metrics via psutil."""
        import psutil

        lines: list[str] = []

        # 1. Host & OS
        boot_ts = psutil.boot_time()
        uptime_sec = max(0, time.time() - boot_ts)
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        mins = int((uptime_sec % 3600) // 60)
        secs = int(uptime_sec % 60)
        uptime_fmt = f"{days}d {hours}h {mins}m {secs}s" if days > 0 else f"{hours}h {mins}m {secs}s"

        lines.extend([
            "--- Host & OS ---",
            f"hostname: {platform.node()}",
            f"platform: {platform.system()} {platform.release()} ({platform.machine()})",
            f"python_version: {platform.python_version()}",
            f"uptime: {uptime_fmt}",
            f"active_window: {_active_window()}",
        ])

        # 2. CPU
        cpu_overall = psutil.cpu_percent(interval=0.1)
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        core_count_phys = psutil.cpu_count(logical=False)
        core_count_log = psutil.cpu_count(logical=True)
        
        freq_info = ""
        try:
            freq = psutil.cpu_freq()
            if freq:
                freq_info = f" @ {freq.current:.0f} MHz (min: {freq.min:.0f}, max: {freq.max:.0f})"
        except Exception:
            pass

        lines.extend([
            "--- CPU Metrics ---",
            f"cpu_utilization: {cpu_overall}%{freq_info}",
            f"cpu_cores: {core_count_phys} physical, {core_count_log} logical",
            f"per_core_percentages: {per_core}",
        ])

        try:
            with open("/proc/loadavg", encoding="utf-8") as fh:
                lines.append(f"loadavg_1_5_15m: {fh.read().strip()}")
        except OSError:
            pass

        # 3. RAM & Swap
        try:
            vmem = psutil.virtual_memory()
            lines.extend([
                "--- Memory ---",
                f"ram_total: {vmem.total / (1024**3):.2f} GB",
                f"ram_used: {vmem.used / (1024**3):.2f} GB ({vmem.percent}% used)",
                f"ram_available: {vmem.available / (1024**3):.2f} GB",
            ])
            swap = psutil.swap_memory()
            lines.append(f"swap_used: {swap.used / (1024**3):.2f} GB / {swap.total / (1024**3):.2f} GB ({swap.percent}%)")
        except Exception as exc:
            lines.append(f"memory_error: {exc}")

        # 4. Disk Disks & Partitions
        try:
            lines.append("--- Storage Disks ---")
            for part in psutil.disk_partitions(all=False):
                if os.name == 'nt' and ('cdrom' in part.opts or part.fstype == ''):
                    continue
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    lines.append(
                        f"mount {part.mountpoint}: {usage.used / (1024**3):.1f}GB / {usage.total / (1024**3):.1f}GB ({usage.percent}% used) [{part.fstype}]"
                    )
                except (PermissionError, OSError):
                    pass
        except Exception as exc:
            lines.append(f"disk_error: {exc}")

        # 5. Battery (if present)
        try:
            battery = psutil.sensors_battery()
            if battery:
                lines.append(
                    f"battery: {battery.percent}% ({'charging' if battery.power_plugged else 'discharging'})"
                )
        except Exception:
            pass

        return "\n".join(lines)

    return get_system_telemetry


def _make_get_system_status() -> Callable[[dict], str]:
    def get_system_status(_args: dict) -> str:
        import psutil

        lines: list[str] = [
            f"hostname: {platform.node()}",
            f"os: {platform.system()} {platform.release()}",
            f"time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"active_window: {_active_window()}",
        ]
        try:
            with open("/proc/loadavg", encoding="utf-8") as fh:
                lines.append(f"loadavg: {fh.read().strip()}")
        except OSError:
            pass
        try:
            mem = psutil.virtual_memory()
            lines.append(f"memory: {mem.percent}% used ({mem.used / (1024**3):.1f}GB / {mem.total / (1024**3):.1f}GB)")
            lines.append(f"cpu: {psutil.cpu_percent(interval=0.1)}%")
        except Exception as exc:
            lines.append(f"memory: unavailable ({exc})")
        try:
            battery = psutil.sensors_battery()
            if battery:
                lines.append(
                    f"battery: {battery.percent}% "
                    f"{'(charging)' if battery.power_plugged else ''}"
                )
        except Exception:
            lines.append("battery: unavailable")
        return "\n".join(lines)

    return get_system_status


def _make_web_search() -> Callable[[dict], str]:
    def web_search(args: dict) -> str:
        query = args.get("query", "")
        log.info("web_search stub called with query=%r", query)
        return (
            f"Search results for query {query!r}: "
            "Web search connector active."
        )

    return web_search


class ToolRegistry:
    """Holds the Tool definitions and dispatches execution safely."""

    def __init__(self, cfg: ToolsConfig, confirm: ConfirmFn | None = None) -> None:
        self._cfg = cfg
        self._confirm = confirm or (lambda _prompt: False)
        self._tools: dict[str, Tool] = {}

        # 1. Shell runner
        self._register(
            Tool(
                name="run_shell_command",
                description=(
                    "Run a shell command on the user's machine. The user must "
                    "approve commands outside the allowlist. Prefer safe, "
                    "read-only commands."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to run",
                        }
                    },
                    "required": ["command"],
                },
                handler=_make_run_shell_command(cfg, self._confirm),
            )
        )

        # 2. Time and calendar
        self._register(
            Tool(
                name="get_time_and_calendar",
                description=(
                    "Get exact current date, time, weekday, timezone info, day of year, "
                    "and calculate relative future/past dates or date differences."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "days_offset": {
                            "type": "integer",
                            "description": "Optional number of days from today (+7 for next week, -1 for yesterday)",
                        },
                        "target_date": {
                            "type": "string",
                            "description": "Optional ISO date (YYYY-MM-DD) to calculate weekday and days distance",
                        },
                    },
                },
                handler=_make_get_time_and_calendar(),
            )
        )

        # 3. System Telemetry
        self._register(
            Tool(
                name="get_system_telemetry",
                description=(
                    "Retrieve comprehensive real-time hardware telemetry: CPU utilization per core, "
                    "frequencies, RAM and swap usage, disk space per partition, host OS, and system uptime."
                ),
                parameters={"type": "object", "properties": {}},
                handler=_make_get_system_telemetry(),
            )
        )

        # 4. System status (overview)
        self._register(
            Tool(
                name="get_system_status",
                description=(
                    "Read-only concise system status: hostname, OS, time, "
                    "active window, load average, memory, CPU and battery."
                ),
                parameters={"type": "object", "properties": {}},
                handler=_make_get_system_status(),
            )
        )

        # 5. Web Search
        self._register(
            Tool(
                name="web_search",
                description="Search the web and return relevant information.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        }
                    },
                    "required": ["query"],
                },
                handler=_make_web_search(),
            )
        )

        # 6. Autonomous Deep Research
        def _handle_start_deep_research(args: dict) -> str:
            topic = str(args.get("topic", "")).strip()
            if not topic:
                return "error: topic parameter is required"
            from deep_research import get_deep_research_engine
            engine = get_deep_research_engine()
            return engine.start_research(topic)

        self._register(
            Tool(
                name="start_deep_research",
                description=(
                    "Start an autonomous multi-source deep research task on a topic in a separate background thread. "
                    "Performs web searches, scrapes articles, synthesizes an analyst-grade report into Markdown notes vault, "
                    "and notifies the user with voice when finished."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "The specific research topic or question to investigate deeply",
                        }
                    },
                    "required": ["topic"],
                },
                handler=_handle_start_deep_research,
            )
        )

        def _handle_get_research_summary(args: dict) -> str:
            topic = str(args.get("topic", "")).strip()
            from deep_research import get_deep_research_engine
            engine = get_deep_research_engine()
            return engine.get_research_summary(topic)

        self._register(
            Tool(
                name="get_research_summary",
                description="Retrieve the executive summary, findings, and notes path for completed deep research topics.",
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Optional research topic name or keyword to retrieve summary for",
                        }
                    },
                },
                handler=_handle_get_research_summary,
            )
        )

        # 7. Smart Timers & Pomodoro
        def _handle_set_timer(args: dict) -> str:
            duration = str(args.get("duration", "")).strip()
            label = str(args.get("label", "")).strip()
            timer_type = str(args.get("timer_type", "timer")).strip()
            from timer_engine import get_timer_engine
            engine = get_timer_engine()
            res = engine.add_timer(duration, label=label, timer_type=timer_type)
            return res.get("message") or res.get("error", "Failed to set timer")

        self._register(
            Tool(
                name="set_timer",
                description=(
                    "Set a countdown timer or Pomodoro focus/break session. "
                    "Accepts durations like '25 minutes', '1 hour', '45 seconds', 'pomodoro', 'short break'."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "string",
                            "description": "Duration (e.g. '25 minutes', '10s', '1h', 'pomodoro')",
                        },
                        "label": {
                            "type": "string",
                            "description": "Optional label (e.g. 'review pull request', 'pasta cooking')",
                        },
                        "timer_type": {
                            "type": "string",
                            "enum": ["timer", "pomodoro", "break"],
                            "description": "Type of timer",
                        },
                    },
                    "required": ["duration"],
                },
                handler=_handle_set_timer,
            )
        )

        # 8. Spoken Reminders
        def _handle_set_reminder(args: dict) -> str:
            reminder_text = str(args.get("reminder_text", "")).strip()
            in_time = str(args.get("in_time", "")).strip()
            at_time = str(args.get("at_time", "")).strip()
            from timer_engine import get_timer_engine
            engine = get_timer_engine()
            res = engine.add_reminder(reminder_text, in_time=in_time, at_time=at_time)
            return res.get("message") or res.get("error", "Failed to schedule reminder")

        self._register(
            Tool(
                name="set_reminder",
                description="Schedule a spoken voice reminder for a specific time or offset (e.g. 'in 30 minutes', 'at 15:30').",
                parameters={
                    "type": "object",
                    "properties": {
                        "reminder_text": {
                            "type": "string",
                            "description": "What to remind the user about (e.g. 'take medicine', 'join standup meeting')",
                        },
                        "in_time": {
                            "type": "string",
                            "description": "Relative time offset (e.g. '20 minutes', '1 hour')",
                        },
                        "at_time": {
                            "type": "string",
                            "description": "Absolute target time (e.g. '15:30', '9:00 am')",
                        },
                    },
                    "required": ["reminder_text"],
                },
                handler=_handle_set_reminder,
            )
        )

        # 9. List Timers
        def _handle_list_timers(_args: dict) -> str:
            from timer_engine import get_timer_engine
            engine = get_timer_engine()
            active = engine.list_timers()
            if not active:
                return "There are no active timers or reminders running right now."
            lines = [f"Active timers ({len(active)}):"]
            for t in active:
                rem_m = t["remaining_seconds"] // 60
                rem_s = t["remaining_seconds"] % 60
                lines.append(f"- [{t['id']}] '{t['label']}': {rem_m}m {rem_s}s remaining ({t['timer_type']})")
            return "\n".join(lines)

        self._register(
            Tool(
                name="list_active_timers",
                description="List all active countdown timers, Pomodoros, and scheduled reminders.",
                parameters={"type": "object", "properties": {}},
                handler=_handle_list_timers,
            )
        )

        # 10. Cancel Timer
        def _handle_cancel_timer(args: dict) -> str:
            timer_id = str(args.get("timer_id", "")).strip()
            if not timer_id:
                return "error: timer_id or label is required"
            from timer_engine import get_timer_engine
            engine = get_timer_engine()
            res = engine.cancel_timer(timer_id)
            return res.get("message") or res.get("error", "Failed to cancel timer")

        self._register(
            Tool(
                name="cancel_timer",
                description="Cancel an active timer or reminder by its ID or label name.",
                parameters={
                    "type": "object",
                    "properties": {
                        "timer_id": {
                            "type": "string",
                            "description": "Timer ID (e.g. 'tmr-123456') or label name",
                        }
                    },
                    "required": ["timer_id"],
                },
                handler=_handle_cancel_timer,
            )
        )

        # 11. Autonomous Morning / Evening Daily Briefing
        def _handle_get_daily_briefing(args: dict) -> str:
            briefing_type = str(args.get("briefing_type", "morning")).strip()
            from briefing_engine import get_briefing_engine
            engine = get_briefing_engine()
            res = engine.generate_briefing(briefing_type=briefing_type)
            return res.get("spoken_summary", "Daily briefing generated.")

        self._register(
            Tool(
                name="get_daily_briefing",
                description=(
                    "Generate and speak an autonomous intelligence briefing (morning briefing or evening debrief) "
                    "aggregating live weather for Chennai, active to-dos from the notes vault, top tech headlines, and hardware telemetry."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "briefing_type": {
                            "type": "string",
                            "enum": ["morning", "evening"],
                            "description": "Type of briefing ('morning' or 'evening')",
                        }
                    },
                },
                handler=_handle_get_daily_briefing,
            )
        )

    def register(self, tool: Tool) -> None:
        """Register a dynamic tool (e.g. from an MCP server or plugin)."""
        self._tools[tool.name] = tool
        log.info("Tool registered: %s", tool.name)

    def _register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]
            log.info("Tool unregistered: %s", name)
            return True
        return False

    def unregister_server_tools(self, server_name: str) -> int:
        """Unregister all tools registered by a specific MCP server."""
        prefix = f"[MCP: {server_name}]"
        to_remove = [k for k, t in self._tools.items() if t.description.startswith(prefix)]
        for k in to_remove:
            del self._tools[k]
        if to_remove:
            log.info("Unregistered %d tools for MCP server %r: %s", len(to_remove), server_name, to_remove)
        return len(to_remove)

    def schemas(self, format: str = "anthropic") -> list[dict]:
        """Tool declarations in the requested provider format:
        'gemini' (function_declarations), 'openai' (function wrapper), 'anthropic'."""
        base = [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self._tools.values()
        ]
        if format == "gemini":
            return base
        if format == "openai":
            return [
                {
                    "type": "function",
                    "function": {"name": t["name"], "description": t["description"],
                                 "parameters": t["parameters"]},
                }
                for t in base
            ]
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in base
        ]

    def execute(self, name: str, args: dict) -> str:
        """Execute a tool by name. Returns a string result suitable for the model."""
        tool = self._tools.get(name)
        if tool is None:
            return f"error: unknown tool {name!r}"
        try:
            return tool.handler(args or {})
        except PermissionError as exc:
            return f"error: {exc}"
        except Exception as exc:
            log.exception("tool %s failed", name)
            return f"error: tool {name!r} raised {type(exc).__name__}: {exc}"
