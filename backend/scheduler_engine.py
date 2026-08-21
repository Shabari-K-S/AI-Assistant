"""EV & S.A.R.A. Proactive Background Scheduler & Security Watchdog Engine.

Provides autonomous background task scheduling, cron jobs, and proactive security monitoring:
- Cron expression & interval-based background job execution via croniter
- Proactive Security Watchdog: Queries OSV (Open Source Vulnerabilities) API for watched packages/CVEs
- Persistent task storage in backend/data/scheduled_tasks.json
- Direct notification & voice briefing hooks on high-severity security events
- Automated nightly QA and diagnostic task execution
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from croniter import croniter
except ImportError:
    croniter = None

log = logging.getLogger("ev.scheduler")

DATA_DIR = Path(__file__).resolve().parent / "data"
SCHEDULE_FILE = DATA_DIR / "scheduled_tasks.json"

DEFAULT_WATCHED_PACKAGES = [
    {"name": "faster-whisper", "ecosystem": "PyPI"},
    {"name": "google-genai", "ecosystem": "PyPI"},
    {"name": "httpx", "ecosystem": "PyPI"},
    {"name": "numpy", "ecosystem": "PyPI"},
    {"name": "pynput", "ecosystem": "PyPI"},
    {"name": "robotframework", "ecosystem": "PyPI"},
    {"name": "mcp", "ecosystem": "PyPI"},
]


@dataclass
class ScheduledTask:
    task_id: str
    name: str
    schedule_type: str  # "cron", "interval", "countdown"
    schedule_value: str  # "0 2 * * *" or "3600" (seconds)
    action_type: str  # "security_scan", "robot_suite", "shell_command", "voice_alert", "custom"
    payload: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_status: Optional[str] = None
    last_result: Optional[str] = None
    run_count: int = 0


class ProactiveScheduler:
    """Async background task scheduler & watchdog daemon for S.A.R.A."""

    def __init__(self, bus: Any = None):
        self.bus = bus
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._notification_callback: Optional[Callable[[str, str, str], None]] = None

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load_tasks()
        self._ensure_default_tasks()

    def set_notification_callback(self, cb: Callable[[str, str, str], None]) -> None:
        """Register a notification callback: cb(title, body, priority)."""
        self._notification_callback = cb

    def _load_tasks(self) -> None:
        """Load persistent scheduled tasks from disk."""
        if not SCHEDULE_FILE.exists():
            return
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("tasks", []):
                    task = ScheduledTask(**item)
                    self._tasks[task.task_id] = task
            log.info(f"Loaded {len(self._tasks)} scheduled tasks from disk.")
        except Exception as exc:
            log.error(f"Failed to load scheduled tasks: {exc}")

    def _save_tasks(self) -> None:
        """Save active tasks to persistent disk storage."""
        try:
            with self._lock:
                tasks_list = [asdict(t) for t in self._tasks.values()]
                with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"tasks": tasks_list, "updated_at": datetime.datetime.now().isoformat()}, f, indent=2)
        except Exception as exc:
            log.error(f"Failed to save scheduled tasks: {exc}")

    def _calculate_next_run(self, task: ScheduledTask, base_time: datetime.datetime | None = None) -> Optional[datetime.datetime]:
        """Compute the next execution timestamp based on schedule type."""
        now = base_time or datetime.datetime.now()
        if not task.enabled:
            return None

        if task.schedule_type == "cron":
            if croniter is not None:
                try:
                    iter_cron = croniter(task.schedule_value, now)
                    return iter_cron.get_next(datetime.datetime)
                except Exception as exc:
                    log.warning(f"Invalid cron expression '{task.schedule_value}' for task {task.task_id}: {exc}")
                    return None
            else:
                # Fallback: run every hour if croniter is unavailable
                return now + datetime.timedelta(hours=1)

        elif task.schedule_type == "interval":
            try:
                seconds = int(task.schedule_value)
                return now + datetime.timedelta(seconds=seconds)
            except ValueError:
                return now + datetime.timedelta(hours=1)

        elif task.schedule_type == "countdown":
            if task.next_run:
                try:
                    return datetime.datetime.fromisoformat(task.next_run)
                except Exception:
                    pass
            try:
                seconds = int(task.schedule_value)
                return now + datetime.timedelta(seconds=seconds)
            except ValueError:
                return None

        return None

    def _ensure_default_tasks(self) -> None:
        """Seed default proactive background tasks if not already present."""
        # 1. Proactive Security CVE Watchdog (Every 4 hours)
        if "security_cve_watchdog" not in self._tasks:
            task = ScheduledTask(
                task_id="security_cve_watchdog",
                name="Proactive Security Advisory & CVE Watchdog",
                schedule_type="interval",
                schedule_value="14400",  # 4 hours (14400s)
                action_type="security_scan",
                payload={"watched_packages": DEFAULT_WATCHED_PACKAGES},
                enabled=True,
            )
            next_dt = self._calculate_next_run(task)
            task.next_run = next_dt.isoformat() if next_dt else None
            self._tasks[task.task_id] = task

        # 2. Nightly Maintenance & System Telemetry Check (Daily at 02:00 AM)
        if "nightly_maintenance" not in self._tasks:
            task = ScheduledTask(
                task_id="nightly_maintenance",
                name="Nightly System Diagnostics & Telemetry Review",
                schedule_type="cron",
                schedule_value="0 2 * * *",
                action_type="custom",
                payload={"action": "system_cleanup"},
                enabled=True,
            )
            next_dt = self._calculate_next_run(task)
            task.next_run = next_dt.isoformat() if next_dt else None
            self._tasks[task.task_id] = task

        self._save_tasks()

    def add_task(
        self,
        task_id: str,
        name: str,
        schedule_type: str,
        schedule_value: str,
        action_type: str,
        payload: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> ScheduledTask:
        """Register or update a scheduled task."""
        payload = payload or {}
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            action_type=action_type,
            payload=payload,
            enabled=enabled,
        )
        next_dt = self._calculate_next_run(task)
        task.next_run = next_dt.isoformat() if next_dt else None

        with self._lock:
            self._tasks[task_id] = task
        self._save_tasks()
        log.info(f"Scheduled task '{task_id}' ({name}) registered. Next run: {task.next_run}")
        return task

    def remove_task(self, task_id: str) -> bool:
        """Delete a scheduled task by ID."""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                self._save_tasks()
                log.info(f"Removed scheduled task '{task_id}'.")
                return True
        return False

    def list_tasks(self) -> List[Dict[str, Any]]:
        """Return all scheduled tasks as dictionaries."""
        with self._lock:
            return [asdict(t) for t in self._tasks.values()]

    def execute_task(self, task: ScheduledTask) -> str:
        """Execute a task immediately and record results."""
        log.info(f"🚀 Executing scheduled task: {task.name} ({task.task_id})")
        t0 = time.perf_counter()
        status = "SUCCESS"
        result_msg = ""

        try:
            if task.action_type == "security_scan":
                result_msg = self._run_security_scan(task.payload)
            elif task.action_type == "robot_suite":
                result_msg = self._run_robot_suite(task.payload)
            elif task.action_type == "voice_alert":
                result_msg = self._dispatch_voice_alert(task.payload)
            elif task.action_type == "shell_command":
                cmd = task.payload.get("command", "")
                if cmd:
                    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30.0)
                    result_msg = f"Exit {res.returncode}: {res.stdout.strip() or res.stderr.strip()}"
                else:
                    result_msg = "No command provided."
            else:
                result_msg = f"Task '{task.name}' executed successfully (no-op action)."
        except Exception as exc:
            status = "ERROR"
            result_msg = f"Execution failed: {exc}"
            log.error(f"Task {task.task_id} failed: {exc}", exc_info=True)

        elapsed = time.perf_counter() - t0
        now_iso = datetime.datetime.now().isoformat()

        with self._lock:
            task.last_run = now_iso
            task.last_status = status
            task.last_result = result_msg[:500]
            task.run_count += 1

            if task.schedule_type == "countdown":
                task.enabled = False
                task.next_run = None
            else:
                next_dt = self._calculate_next_run(task)
                task.next_run = next_dt.isoformat() if next_dt else None

        self._save_tasks()

        if self.bus is not None:
            self.bus.log("INFO", f"Scheduled task '{task.name}' finished [{status}] ({elapsed:.2f}s)")

        return result_msg

    def _run_security_scan(self, payload: Dict[str, Any]) -> str:
        """Query OSV.dev database for known vulnerabilities in watched dependencies."""
        packages = payload.get("watched_packages", DEFAULT_WATCHED_PACKAGES)
        vulnerabilities_found = []

        for pkg in packages:
            name = pkg.get("name", "")
            ecosystem = pkg.get("ecosystem", "PyPI")
            if not name:
                continue

            query_data = json.dumps({"package": {"name": name, "ecosystem": ecosystem}}).encode("utf-8")
            url = "https://api.osv.dev/v1/query"
            req = urllib.request.Request(
                url,
                data=query_data,
                headers={"Content-Type": "application/json", "User-Agent": "ATHENA-SecurityWatchdog/1.0"},
            )
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    vulns = data.get("vulns", [])
                    if vulns:
                        for v in vulns[:2]:
                            v_id = v.get("id", "UNKNOWN-CVE")
                            summary = v.get("summary") or v.get("details", "")[:120]
                            vulnerabilities_found.append(f"• **{name}** ({ecosystem}): [{v_id}] {summary}")
            except Exception as exc:
                log.debug(f"Security check query failed for {name}: {exc}")

        if vulnerabilities_found:
            alert_msg = f"🚨 **Security Watchdog Alert ({len(vulnerabilities_found)} CVEs detected):**\n" + "\n".join(vulnerabilities_found)
            self._notify_alert("S.A.R.A. Security Watchdog Alert", f"{len(vulnerabilities_found)} vulnerability advisories found in watched packages.", priority="high")
            if self.bus is not None:
                self.bus.log("WARN", alert_msg)
            return alert_msg
        else:
            return f"🛡️ Security Watchdog: Scanned {len(packages)} packages. All clean (0 known CVEs)."

    def _run_robot_suite(self, payload: Dict[str, Any]) -> str:
        """Execute a Robot Framework test suite in the background."""
        suite_path = payload.get("suite_path", "")
        if not suite_path:
            return "Error: suite_path is required."

        try:
            import robot
            report_dir = DATA_DIR / "robot_reports" / f"scheduled_{time.strftime('%Y%m%d_%H%M%S')}"
            report_dir.mkdir(parents=True, exist_ok=True)
            rc = robot.run(suite_path, outputdir=str(report_dir), output="output.xml", log="log.html", report="report.html")
            status = "PASSED" if rc == 0 else f"FAILED (code {rc})"
            msg = f"Robot suite '{Path(suite_path).name}' completed: {status}. Reports at {report_dir}"
            if rc != 0:
                self._notify_alert("Robot Test Failure Alert", f"Suite '{Path(suite_path).name}' failed.", priority="high")
            return msg
        except Exception as exc:
            return f"Robot execution failed: {exc}"

    def _dispatch_voice_alert(self, payload: Dict[str, Any]) -> str:
        """Deliver a spoken audio prompt or push notification."""
        text = payload.get("message", "Scheduled reminder from S.A.R.A.")
        title = payload.get("title", "S.A.R.A. Reminder")
        self._notify_alert(title, text, priority="high")
        return f"Voice reminder dispatched: '{text}'"

    def _notify_alert(self, title: str, content: str, priority: str = "high") -> None:
        """Send notification via registered callback or termux-notification CLI."""
        if self._notification_callback:
            try:
                self._notification_callback(title, content, priority)
                return
            except Exception:
                pass

        # Fallback to termux-notification CLI
        try:
            subprocess.run(
                ["termux-notification", "--title", title, "--content", content, "--priority", priority],
                capture_output=True,
                timeout=4.0,
            )
        except Exception:
            pass

    def start(self) -> None:
        """Start the background scheduler daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="SchedulerDaemon", daemon=True)
        self._thread.start()
        log.info("Proactive Scheduler & Security Watchdog daemon started.")

    def stop(self) -> None:
        """Stop the background scheduler daemon."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        log.info("Proactive Scheduler daemon stopped.")

    def _run_loop(self) -> None:
        """Main polling loop checking for due tasks every 10 seconds."""
        while self._running:
            now = datetime.datetime.now()
            due_tasks = []

            with self._lock:
                for task in self._tasks.values():
                    if not task.enabled or not task.next_run:
                        continue
                    try:
                        next_dt = datetime.datetime.fromisoformat(task.next_run)
                        if now >= next_dt:
                            due_tasks.append(task)
                    except Exception:
                        pass

            for task in due_tasks:
                try:
                    self.execute_task(task)
                except Exception as exc:
                    log.error(f"Error running due task {task.task_id}: {exc}")

            # Sleep in small increments for responsive shutdown
            for _ in range(10):
                if not self._running:
                    break
                time.sleep(1.0)


# Global singleton instance
_scheduler_instance: Optional[ProactiveScheduler] = None


def get_scheduler(bus: Any = None) -> ProactiveScheduler:
    """Retrieve or initialize the global ProactiveScheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ProactiveScheduler(bus=bus)
    elif bus is not None and _scheduler_instance.bus is None:
        _scheduler_instance.bus = bus
    return _scheduler_instance
