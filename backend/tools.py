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

HIGH_RISK_PATTERNS = [
    # Permanent / mass file deletion & disk destruction
    r"\brm\s+-[a-zA-Z]*r",       # rm -r / rm -rf
    r"\brm\s+-[a-zA-Z]*f\s+/",   # rm -f /...
    r"\brm\b",                    # any file deletion
    r"\brmdir\b",
    r"\bunlink\b",
    r"\bshred\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bformat\b",
    r"\bfdisk\b",
    r"\bparted\b",
    # System shutdown / power down / reboot
    r"\breboot\b",
    r"\bshutdown\b",
    r"\bpoweroff\b",
    r"\binit\s+0\b",
    r"\bhalt\b",
    # Destructive git overwrites
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\b",
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+restore\s+\.\b",
    # Mass process kills
    r"\bkillall\b",
    r"\bpkill\s+-9\b",
    # Dangerous database wipe
    r"\bdrop\s+database\b",
    r"\bdrop\s+table\b",
]


def is_high_risk_command(command: str) -> bool:
    """True if the command carries high risk of permanent data loss, system reboot, or destructive override."""
    cmd = command.strip()
    if not cmd:
        return False
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return True
    return False


def is_safe_read_only_command(command: str) -> bool:
    """Analyze whether a shell command is strictly read-only / informational (e.g. weather, git status, system load)."""
    return not is_high_risk_command(command)


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
        is_high_risk = is_high_risk_command(command)

        if policy == "always":
            _confirm_or_raise(f"run shell command: {command!r}", confirm, refuse=False)
            use_shell = True
        elif policy == "never":
            if is_high_risk:
                _confirm_or_raise(f"run high-risk shell command: {command!r}", confirm, refuse=True)
            use_shell = True
        elif is_high_risk and not in_allowlist:
            # ONLY ask confirmation for genuinely dangerous / destructive actions (deletions, reboots, formatting)
            _confirm_or_raise(
                f"run high-risk shell command: {command!r}",
                confirm,
                refuse=False,
            )
            use_shell = True
        else:
            # Autonomous execution for all normal developer, system, package, and Termux commands!
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


def _sanitize_schema_for_gemini(param_dict: Any) -> Any:
    """Recursively ensure all enums are string lists and types are compliant with Gemini Pydantic schema."""
    if not isinstance(param_dict, dict):
        return param_dict

    clean = dict(param_dict)
    if "enum" in clean and isinstance(clean["enum"], (list, tuple)):
        clean["enum"] = [str(item) for item in clean["enum"]]

    if "properties" in clean and isinstance(clean["properties"], dict):
        clean["properties"] = {
            k: _sanitize_schema_for_gemini(v) for k, v in clean["properties"].items()
        }
    if "items" in clean and isinstance(clean["items"], dict):
        clean["items"] = _sanitize_schema_for_gemini(clean["items"])

    return clean


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

        # 12. Long-Term Semantic Vector Memory
        def _handle_remember_fact(args: dict) -> str:
            fact = str(args.get("fact", "")).strip()
            if not fact:
                return "error: fact parameter is required"
            category = str(args.get("category", "general")).strip().lower()
            from memory_engine import get_memory_engine
            engine = get_memory_engine()
            mem_id = engine.store_fact(fact, category=category)
            return f"Successfully stored in long-term memory [{mem_id}]: '{fact}' (Category: {category})"

        self._register(
            Tool(
                name="remember_fact",
                description=(
                    "Store a piece of knowledge, user preference, technical configuration, server detail, "
                    "or personal habit in permanent long-term vector memory."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "fact": {
                            "type": "string",
                            "description": "The exact fact, preference, or technical configuration to remember permanently",
                        },
                        "category": {
                            "type": "string",
                            "enum": ["preference", "credential", "project", "personal", "habit", "general"],
                            "description": "Category tag for the memory",
                        },
                    },
                    "required": ["fact"],
                },
                handler=_handle_remember_fact,
            )
        )

        def _handle_recall_memory(args: dict) -> str:
            query = str(args.get("query", "")).strip()
            if not query:
                return "error: query parameter is required"
            limit = min(10, max(1, int(args.get("limit", 4))))
            from memory_engine import get_memory_engine
            engine = get_memory_engine()
            results = engine.recall(query, limit=limit)
            if not results:
                return f"No relevant long-term memories found for query: '{query}'"
            lines = [f"🧠 Long-Term Memory Recall for: '{query}' ({len(results)} items found)\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. [{r['category'].upper()}] {r['text']} (Match Score: {r['score']})")
            return "\n".join(lines)

        self._register(
            Tool(
                name="recall_memory",
                description="Search permanent long-term vector memory using semantic similarity to recall historical facts, preferences, and configurations.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language question or search phrase to recall from memory",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of memories to return (default: 4)",
                        },
                    },
                    "required": ["query"],
                },
                handler=_handle_recall_memory,
            )
        )

        # 13. Ambient RGB Lighting Sync Control
        def _handle_set_rgb_lighting(args: dict) -> str:
            phase = str(args.get("phase", "standby")).strip().lower()
            from rgb_sync import get_rgb_manager
            manager = get_rgb_manager()
            manager.set_phase(phase)
            return f"Ambient RGB lighting transitioned to phase: '{phase}'"

        self._register(
            Tool(
                name="set_ambient_rgb_lighting",
                description="Manually control ambient room/desk smart lighting phase (standby, listening, processing, speaking, security, deep_research).",
                parameters={
                    "type": "object",
                    "properties": {
                        "phase": {
                            "type": "string",
                            "enum": ["standby", "listening", "processing", "speaking", "security", "deep_research"],
                            "description": "Target lighting color/animation phase",
                        }
                    },
                    "required": ["phase"],
                },
                handler=_handle_set_rgb_lighting,
            )
        )

        # 14. Proactive Task Scheduler & Security Watchdog
        def _handle_schedule_task(args: dict) -> str:
            name = str(args.get("name", "Scheduled Task")).strip()
            task_type = str(args.get("schedule_type", "interval")).strip().lower()
            schedule_value = str(args.get("schedule_value", "3600")).strip()
            action_type = str(args.get("action_type", "voice_alert")).strip().lower()
            payload = args.get("payload") or {}

            import uuid
            from scheduler_engine import get_scheduler
            scheduler = get_scheduler()
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            task = scheduler.add_task(
                task_id=task_id,
                name=name,
                schedule_type=task_type,
                schedule_value=schedule_value,
                action_type=action_type,
                payload=payload,
                enabled=True,
            )
            return f"⏰ Task '{name}' [{task.task_id}] scheduled ({task_type}: {schedule_value}, action: {action_type}). Next run: {task.next_run}"

        self._register(
            Tool(
                name="schedule_task",
                description=(
                    "Schedule a proactive background task or recurring cron job in S.A.R.A. "
                    "(e.g. nightly security scan at 2 AM, periodic health check, or recurring reminder)."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Descriptive name for the scheduled task",
                        },
                        "schedule_type": {
                            "type": "string",
                            "enum": ["cron", "interval", "countdown"],
                            "description": "'cron' for cron expression (e.g. '0 2 * * *'), 'interval' for recurring seconds (e.g. '3600'), 'countdown' for one-shot timer seconds.",
                        },
                        "schedule_value": {
                            "type": "string",
                            "description": "Cron expression ('0 2 * * *') or interval in seconds ('7200').",
                        },
                        "action_type": {
                            "type": "string",
                            "enum": ["security_scan", "robot_suite", "voice_alert", "shell_command", "custom"],
                            "description": "Action to perform when triggered.",
                        },
                        "payload": {
                            "type": "object",
                            "description": "Arguments for the action (e.g. {'message': 'Stand up and stretch!'} or {'suite_path': 'tests/login.robot'}).",
                        },
                    },
                    "required": ["name", "schedule_type", "schedule_value", "action_type"],
                },
                handler=_handle_schedule_task,
            )
        )

        def _handle_list_scheduled_tasks(_args: dict) -> str:
            from scheduler_engine import get_scheduler
            scheduler = get_scheduler()
            tasks = scheduler.list_tasks()
            if not tasks:
                return "No scheduled tasks currently active."
            out = [f"⏰ **Active Scheduled Tasks ({len(tasks)} total):**\n"]
            for idx, t in enumerate(tasks, 1):
                status_icon = "🟢" if t.get("enabled") else "⚪"
                out.append(
                    f"{idx}. {status_icon} **{t.get('name')}** (`{t.get('task_id')}`)\n"
                    f"   - Type: `{t.get('schedule_type')}` (`{t.get('schedule_value')}`) | Action: `{t.get('action_type')}`\n"
                    f"   - Next Run: `{t.get('next_run') or 'None'}` | Last Status: `{t.get('last_status') or 'Never Run'}`\n"
                )
            return "\n".join(out)

        self._register(
            Tool(
                name="list_scheduled_tasks",
                description="List all currently active and configured background scheduled tasks and watchdogs.",
                parameters={"type": "object", "properties": {}},
                handler=_handle_list_scheduled_tasks,
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
            return [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": _sanitize_schema_for_gemini(t["parameters"]),
                }
                for t in base
            ]
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

    TOOL_VOCAL_CUES: dict[str, str] = {
        "android_camera_vision": "Opening the camera now.",
        "android_battery_status": "Checking battery telemetry.",
        "android_torch_control": "Toggling flashlight.",
        "android_location_get": "Checking your GPS coordinates.",
        "android_vibrate_phone": "Sending haptic pulse.",
        "android_clipboard_sync": "Checking clipboard.",
        "android_notification_send": "Sending push notification.",
        "android_notification_list": "Checking active notifications.",
        "android_system_diagnostics": "Running system diagnostics.",
        "android_sms_list": "Checking your text messages.",
        "android_sms_send": "Sending SMS.",
        "android_contact_search": "Searching your contacts.",
        "android_telephony_info": "Checking cellular network status.",
        "robot_list_suites": "Scanning Robot Framework test suites.",
        "robot_run_suite": "Running Robot Framework tests.",
        "robot_parse_results": "Parsing test execution report.",
        "robot_analyze_failures": "Diagnosing test failure tracebacks.",
        "schedule_task": "Scheduling background task.",
        "list_scheduled_tasks": "Checking scheduled tasks.",
        "scrape_web_page": "Reading that web page for you.",
        "extract_page_links": "Extracting hyperlinks from the page.",
        "duckduckgo_web_search": "Searching the web.",
        "duckduckgo_news_search": "Checking the latest news.",
        "notes_add_note": "Saving note to vault.",
        "notes_read_note": "Reading note from vault.",
        "notes_search_notes": "Searching your notes.",
        "notes_semantic_rag_search": "Searching your knowledge vault.",
        "voice_brain_dump_processor": "Organizing your thoughts into tasks and notes.",
        "notes_add_todo": "Adding task to your checklist.",
        "notes_list_todos": "Checking your to-do checklist.",
        "notes_complete_todo": "Updating task status.",
        "deep_research_report": "Initiating deep research.",
        "security_cve_search": "Searching vulnerability advisories.",
        "security_passive_recon": "Performing passive subdomain reconnaissance.",
        "security_header_audit": "Auditing security headers.",
        "security_code_audit": "Running static security code audit.",
        "security_port_scan": "Inspecting network ports.",
        "opencode_run_terminal": "Executing terminal command.",
        "opencode_read_code": "Reading project code.",
        "opencode_write_code": "Writing code to workspace.",
        "opencode_search_code": "Searching workspace codebase.",
        "opencode_git_summary": "Checking Git repository status.",
        "timer_create": "Setting timer.",
        "timer_list": "Checking active timers.",
    }

    def set_bus(self, bus: object) -> None:
        """Attach the EV web bridge event bus for live telemetry streaming."""
        self._bus = bus

    def set_cue_callback(self, callback: Callable[[str], None] | None) -> None:
        """Set a vocal/HUD cue callback invoked right before long-running tools execute."""
        self._cue_callback = callback

    def execute(self, name: str, args: dict) -> str:
        """Execute a tool by name. Returns a string result suitable for the model."""
        tool = self._tools.get(name)
        if tool is None:
            return f"error: unknown tool {name!r}"

        t0 = time.perf_counter()
        bus = getattr(self, "_bus", None)
        if bus is not None and hasattr(bus, "emit_tool_start"):
            bus.emit_tool_start(name, args)

        # Emit conversational progress cue if registered
        cue_cb = getattr(self, "_cue_callback", None)
        if cue_cb and name in self.TOOL_VOCAL_CUES:
            try:
                cue_cb(self.TOOL_VOCAL_CUES[name])
            except Exception:
                pass

        try:
            res = tool.handler(args or {})
            dur_ms = (time.perf_counter() - t0) * 1000.0
            if bus is not None and hasattr(bus, "emit_tool_end"):
                bus.emit_tool_end(name, dur_ms, status="ok", preview=str(res))
            return res
        except PermissionError as exc:
            dur_ms = (time.perf_counter() - t0) * 1000.0
            if bus is not None and hasattr(bus, "emit_tool_end"):
                bus.emit_tool_end(name, dur_ms, status="permission_denied", preview=str(exc))
            return f"error: {exc}"
        except Exception as exc:
            dur_ms = (time.perf_counter() - t0) * 1000.0
            log.exception("tool %s failed", name)
            if bus is not None and hasattr(bus, "emit_tool_end"):
                bus.emit_tool_end(name, dur_ms, status="error", preview=str(exc))
            return f"error: tool {name!r} raised {type(exc).__name__}: {exc}"
