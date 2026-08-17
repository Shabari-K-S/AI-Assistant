"""EV & S.A.R.A. Smart Timers, Pomodoro & Spoken Reminders Engine.

Manages background countdown timers, Pomodoro focus/break sessions, and scheduled spoken reminders
with audio chimes and voice notifications.
"""

from __future__ import annotations

import datetime
import logging
import re
import threading
import time
from typing import Any, Callable

log = logging.getLogger("ev.timers")


def parse_duration_seconds(duration_str: str) -> int:
    """Parse natural language duration string into seconds.
    
    Supports:
    - '25m', '25 min', '25 minutes'
    - '1h', '1 hour', '2 hours'
    - '30s', '30 sec', '45 seconds'
    - '1h 30m', '1 hour 15 minutes'
    - 'pomodoro' (1500s / 25m)
    - 'short break' (300s / 5m)
    - 'long break' (900s / 15m)
    """
    raw = duration_str.strip().lower()
    if not raw:
        return 0

    if "pomodoro" in raw or "focus" in raw:
        return 25 * 60
    if "short break" in raw or "quick break" in raw:
        return 5 * 60
    if "long break" in raw:
        return 15 * 60

    total_seconds = 0
    # Hours
    hr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)", raw)
    if hr_match:
        total_seconds += int(float(hr_match.group(1)) * 3600)

    # Minutes
    min_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)", raw)
    if min_match:
        total_seconds += int(float(min_match.group(1)) * 60)

    # Seconds
    sec_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)", raw)
    if sec_match:
        total_seconds += int(float(sec_match.group(1)))

    # Raw single number (assume minutes if >= 1 and <= 120, else seconds)
    if total_seconds == 0:
        num_match = re.match(r"^(\d+)$", raw)
        if num_match:
            num = int(num_match.group(1))
            total_seconds = num * 60 if num <= 120 else num

    return total_seconds


def parse_target_time(at_time_str: str) -> float | None:
    """Parse absolute time string like '15:30', '3:30 pm', '9:00 am' into unix timestamp."""
    raw = at_time_str.strip().lower()
    now = datetime.datetime.now()

    # Try 24-hour format HH:MM
    match_24 = re.search(r"(\d{1,2}):(\d{2})", raw)
    if match_24:
        hr = int(match_24.group(1))
        mn = int(match_24.group(2))
        is_pm = "pm" in raw
        is_am = "am" in raw

        if is_pm and hr < 12:
            hr += 12
        elif is_am and hr == 12:
            hr = 0

        target_dt = now.replace(hour=hr, minute=mn, second=0, microsecond=0)
        if target_dt <= now:
            # Schedule for tomorrow if time already passed today
            target_dt += datetime.timedelta(days=1)
        return target_dt.timestamp()

    # Try 12-hour format with am/pm like '9 am', '3 pm'
    match_12 = re.search(r"(\d{1,2})\s*(am|pm)", raw)
    if match_12:
        hr = int(match_12.group(1))
        if match_12.group(2) == "pm" and hr < 12:
            hr += 12
        elif match_12.group(2) == "am" and hr == 12:
            hr = 0
        target_dt = now.replace(hour=hr, minute=0, second=0, microsecond=0)
        if target_dt <= now:
            target_dt += datetime.timedelta(days=1)
        return target_dt.timestamp()

    return None


class TimerEngine:
    """Singleton background daemon managing countdown timers and reminders."""

    def __init__(self, bus: Any = None) -> None:
        self.bus = bus
        self.on_expiry: Callable[[dict[str, Any]], None] | None = None
        self._lock = threading.Lock()
        self._timers: dict[str, dict[str, Any]] = {}
        self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="TimerEngine-Daemon")
        self._thread.start()
        log.info("TimerEngine initialized and background scheduler started")

    def set_bus(self, bus: Any) -> None:
        self.bus = bus

    def set_on_expiry(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self.on_expiry = callback

    def add_timer(self, duration_str: str, label: str = "", timer_type: str = "timer") -> dict[str, Any]:
        """Create and start a countdown timer."""
        seconds = parse_duration_seconds(duration_str)
        if seconds <= 0:
            return {"ok": False, "error": f"Invalid duration format: '{duration_str}'"}

        now = time.time()
        timer_id = f"tmr-{int(now * 1000) % 1000000}"
        expires_at = now + seconds

        if not label:
            if timer_type == "pomodoro":
                label = "Pomodoro Focus Session"
            elif timer_type == "break":
                label = "Break Time"
            else:
                label = f"{duration_str.strip()} timer"

        timer_record = {
            "id": timer_id,
            "label": label,
            "timer_type": timer_type,
            "total_seconds": seconds,
            "expires_at": expires_at,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "status": "running",
            "is_reminder": False,
        }

        with self._lock:
            self._timers[timer_id] = timer_record

        log.info("Timer started: [%s] '%s' (%ds)", timer_id, label, seconds)
        if self.bus is not None:
            self.bus.log("INFO", f"⏰ Timer set: '{label}' for {duration_str} ({seconds}s)")
            self.bus.event("timer_created", **timer_record)

        return {
            "ok": True,
            "id": timer_id,
            "label": label,
            "seconds": seconds,
            "duration_str": duration_str,
            "expires_at": expires_at,
            "message": f"Timer set for {label} ({duration_str}). I will alert you with voice and sound when it expires.",
        }

    def add_reminder(self, reminder_text: str, in_time: str = "", at_time: str = "") -> dict[str, Any]:
        """Schedule a spoken voice reminder."""
        reminder_clean = reminder_text.strip()
        if not reminder_clean:
            return {"ok": False, "error": "Reminder text cannot be empty."}

        now = time.time()
        expires_at: float | None = None
        duration_desc = ""

        if in_time:
            secs = parse_duration_seconds(in_time)
            if secs > 0:
                expires_at = now + secs
                duration_desc = f"in {in_time}"
        elif at_time:
            expires_at = parse_target_time(at_time)
            if expires_at:
                duration_desc = f"at {at_time}"

        if not expires_at:
            # Fallback: check if reminder_clean contains 'in X minutes'
            match_in = re.search(r"\bin\s+(\d+\s*(?:min|mins|minutes|hour|hours|sec|secs|seconds))\b", reminder_clean, re.I)
            if match_in:
                in_str = match_in.group(1)
                secs = parse_duration_seconds(in_str)
                if secs > 0:
                    expires_at = now + secs
                    duration_desc = f"in {in_str}"
                    reminder_clean = re.sub(r"\bin\s+" + re.escape(in_str) + r"\b", "", reminder_clean, flags=re.I).strip()

        if not expires_at:
            return {"ok": False, "error": "Could not determine reminder time. Specify 'in 20 minutes' or 'at 15:30'."}

        timer_id = f"rem-{int(now * 1000) % 1000000}"
        total_seconds = int(expires_at - now)

        reminder_record = {
            "id": timer_id,
            "label": reminder_clean,
            "timer_type": "reminder",
            "total_seconds": total_seconds,
            "expires_at": expires_at,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "status": "running",
            "is_reminder": True,
        }

        with self._lock:
            self._timers[timer_id] = reminder_record

        log.info("Reminder scheduled: [%s] '%s' (%s)", timer_id, reminder_clean, duration_desc)
        if self.bus is not None:
            self.bus.log("INFO", f"🔔 Reminder scheduled: '{reminder_clean}' ({duration_desc})")
            self.bus.event("reminder_created", **reminder_record)

        return {
            "ok": True,
            "id": timer_id,
            "label": reminder_clean,
            "seconds": total_seconds,
            "duration_desc": duration_desc,
            "message": f"Reminder scheduled: '{reminder_clean}' {duration_desc}. I will remind you with voice when the time arrives.",
        }

    def cancel_timer(self, timer_id: str) -> dict[str, Any]:
        """Cancel a running timer or reminder."""
        with self._lock:
            if timer_id in self._timers:
                t = self._timers.pop(timer_id)
                log.info("Timer cancelled: [%s] '%s'", timer_id, t.get("label"))
                if self.bus is not None:
                    self.bus.log("INFO", f"Timer cancelled: '{t.get('label')}'")
                    self.bus.event("timer_cancelled", id=timer_id, label=t.get("label"))
                return {"ok": True, "message": f"Cancelled timer '{t.get('label')}'"}

            # Search by label if id not matched
            for tid, t in list(self._timers.items()):
                if timer_id.lower() in t.get("label", "").lower():
                    self._timers.pop(tid)
                    log.info("Timer cancelled by label: [%s] '%s'", tid, t.get("label"))
                    if self.bus is not None:
                        self.bus.event("timer_cancelled", id=tid, label=t.get("label"))
                    return {"ok": True, "message": f"Cancelled timer '{t.get('label')}'"}

        return {"ok": False, "error": f"No active timer found with ID or name '{timer_id}'"}

    def list_timers(self) -> list[dict[str, Any]]:
        """Return list of active timers with current remaining seconds."""
        now = time.time()
        active = []
        with self._lock:
            for tid, t in list(self._timers.items()):
                if t["status"] == "running":
                    rem = max(0, int(t["expires_at"] - now))
                    active.append({
                        **t,
                        "remaining_seconds": rem,
                        "progress_percent": int(((t["total_seconds"] - rem) / max(1, t["total_seconds"])) * 100),
                    })
        return active

    def _scheduler_loop(self) -> None:
        """Background thread checking deadlines every second."""
        while self._running:
            try:
                now = time.time()
                expired: list[dict[str, Any]] = []

                with self._lock:
                    for tid, t in list(self._timers.items()):
                        if t["status"] == "running" and now >= t["expires_at"]:
                            t["status"] = "expired"
                            expired.append(dict(t))
                            del self._timers[tid]

                for exp in expired:
                    self._trigger_expiry(exp)

                # Send tick update every 2 seconds if timers are active
                if self.bus is not None and len(self._timers) > 0:
                    self.bus.event("timer_tick", timers=self.list_timers())

            except Exception as exc:
                log.exception("Error in timer scheduler loop: %s", exc)

            time.sleep(1.0)

    def _trigger_expiry(self, timer_data: dict[str, Any]) -> None:
        """Handle timer expiry: log, broadcast event, and trigger spoken alert."""
        label = timer_data.get("label", "Timer")
        is_rem = timer_data.get("is_reminder", False)
        t_type = timer_data.get("timer_type", "timer")

        if is_rem:
            spoken_text = f"Reminder alert: {label}!"
        elif t_type == "pomodoro":
            spoken_text = f"Your Pomodoro focus session '{label}' is complete! Time for a 5-minute break."
        elif t_type == "break":
            spoken_text = f"Your break time is up! Ready to resume your focus session?"
        else:
            spoken_text = f"Attention, your timer for {label} is complete!"

        timer_data["spoken_text"] = spoken_text
        log.info("⏰ TIMER EXPIRED: %s", spoken_text)

        if self.bus is not None:
            self.bus.log("INFO", f"⏰ 🔔 {spoken_text}")
            self.bus.event("timer_expired", **timer_data)

        if self.on_expiry is not None:
            try:
                self.on_expiry(timer_data)
            except Exception as exc:
                log.exception("Error in timer on_expiry callback: %s", exc)


_global_timer_engine: TimerEngine | None = None


def get_timer_engine(bus: Any = None) -> TimerEngine:
    global _global_timer_engine
    if _global_timer_engine is None:
        _global_timer_engine = TimerEngine(bus=bus)
    elif bus is not None and _global_timer_engine.bus is None:
        _global_timer_engine.set_bus(bus)
    return _global_timer_engine
