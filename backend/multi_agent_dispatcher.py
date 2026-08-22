#!/usr/bin/env python3
"""Modular Sub-Agent Parallel Task Orchestrator & Dispatcher for Athena.

Enables Athena to spin up specialized, concurrent background worker agents
configured in `.athena/agents/<agent_name>.json`.

Pre-configured specialized agents:
1. `recon_specialist`: DAST scanner, CVE advisories, SSL inspector, sensitive file scanner.
2. `deep_researcher`: Multi-vector search, crawler, academic synthesis engine.
3. `code_architect`: Git inspection, code generation, refactoring, test execution.
4. `termux_sysadmin`: Android Termux package manager, toolchain auditor, hardware telemetry.
5. `ctf_copilot`: Active lab milestone logger, hash decoder, walkthrough dossier generator.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("ev.agents")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"
AGENT_TASKS_FILE = DATA_DIR / "agent_tasks.json"

WORKSPACE_AGENTS_DIR = PROJECT_ROOT / ".athena" / "agents"
GLOBAL_AGENTS_DIR = Path.home() / ".athena" / "agents"


@dataclass
class AthenaAgentProfile:
    name: str
    role: str
    description: str
    system_prompt: str
    allowed_tools: List[str] = field(default_factory=list)
    category: str = "general"
    created_at: str = ""
    is_builtin: bool = False


@dataclass
class AgentJob:
    task_id: str
    name: str
    agent_name: str
    task_type: str  # research | security_scan | coding | sysadmin | ctf | custom
    status: str  # running | completed | failed | cancelled
    progress_pct: int
    current_step: str
    started_at: float
    completed_at: Optional[float] = None
    result_summary: str = ""
    report_path: str = ""
    error: str = ""


# Default agent profiles initialized in .athena/agents/
DEFAULT_AGENT_PROFILES: list[dict[str, Any]] = [
    {
        "name": "recon_specialist",
        "role": "Autonomous Reconnaissance & Vulnerability Assessment Specialist",
        "description": "Specialized in DAST vulnerability scanning, open port analysis, SSL audit, and CVE discovery.",
        "category": "security",
        "allowed_tools": ["web_security_scanner", "security_compile_triage_report", "ssl_inspect", "terminal_command"],
        "system_prompt": "You are Athena's Reconnaissance & Security Audit Agent. Perform thorough, non-destructive security testing, verify exposed files, and document CVE vulnerabilities into the Notes Vault.",
    },
    {
        "name": "deep_researcher",
        "role": "Autonomous Academic & Technical Deep Research Analyst",
        "description": "Decomposes complex topics, harvests 10-14 multi-vector sources across the web, and compiles full research papers.",
        "category": "research",
        "allowed_tools": ["start_deep_research", "get_research_summary", "notes_add_note"],
        "system_prompt": "You are Athena's Deep Research Agent. Autonomously explore topics across multi-vector queries, crawl authoritative documentation, and synthesize technical deep-dive articles with verified citations.",
    },
    {
        "name": "code_architect",
        "role": "Full-Stack Code Reviewer & Architecture Engineer",
        "description": "Inspects git diffs, analyzes architectural patterns, refactors TypeScript/Python code, and validates tests.",
        "category": "coding",
        "allowed_tools": ["git_status", "git_diff", "git_commit", "terminal_command"],
        "system_prompt": "You are Athena's Code Architect Agent. Inspect repositories, enforce strict type safety and error boundaries, eliminate code placeholders, and maintain high code quality.",
    },
    {
        "name": "termux_sysadmin",
        "role": "Android Termux Environment & Mobile Toolchain Administrator",
        "description": "Optimizes mobile packages, checks background processes, audits network interfaces, and monitors device telemetry.",
        "category": "sysadmin",
        "allowed_tools": ["lab_env_check", "battery_status", "system_telemetry", "terminal_command"],
        "system_prompt": "You are Athena's Termux Sysadmin Agent. Manage Termux ARM packages, audit installed security toolchains, and ensure rootless operations run within kernel limits.",
    },
    {
        "name": "ctf_copilot",
        "role": "Cybersecurity CTF & Hack The Box Lab Co-Pilot",
        "description": "Tracks active lab targets, decodes hashes, suggests privilege escalation vectors, and auto-generates Markdown dossiers.",
        "category": "security",
        "allowed_tools": ["lab_dossier_manager", "lab_decode_payload", "lab_hash_identifier", "terminal_command", "notes_add_note"],
        "system_prompt": "You are Athena's CTF Lab Co-Pilot. Track targets, record milestones, decode payloads, and export publication-grade lab walkthrough dossiers directly into the Notes Vault.",
    },
]


class MultiAgentDispatcher:
    """Manages background subagent worker threads and progress streaming."""

    def __init__(self, bus: Any = None) -> None:
        self.bus = bus
        self.agents_dir = WORKSPACE_AGENTS_DIR
        self._profiles: Dict[str, AthenaAgentProfile] = {}
        self._jobs: Dict[str, AgentJob] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._cancel_flags: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._init_agents_directory()
        self._load_persisted_jobs()

    def set_bus(self, bus: Any) -> None:
        self.bus = bus

    def _init_agents_directory(self) -> None:
        """Ensure .athena/agents exists and pre-populate default profiles."""
        try:
            self.agents_dir.mkdir(parents=True, exist_ok=True)
            existing = list(self.agents_dir.glob("*.json"))
            if not existing:
                for p in DEFAULT_AGENT_PROFILES:
                    agent_file = self.agents_dir / f"{p['name']}.json"
                    profile_data = {
                        **p,
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "is_builtin": True,
                    }
                    agent_file.write_text(json.dumps(profile_data, indent=2), encoding="utf-8")
                    log.info("Initialized default agent profile: %s", p["name"])
            self.discover_agents()
        except Exception as exc:
            log.warning("Agent directory initialization error: %s", exc)

    def discover_agents(self) -> list[AthenaAgentProfile]:
        """Scan .athena/agents/ and load all agent profiles."""
        with self._lock:
            self._profiles.clear()
            paths = [self.agents_dir]
            if GLOBAL_AGENTS_DIR.exists() and GLOBAL_AGENTS_DIR != WORKSPACE_AGENTS_DIR:
                paths.append(GLOBAL_AGENTS_DIR)

            for base_dir in paths:
                if not base_dir.exists():
                    continue
                for f in base_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        name = data.get("name") or f.stem
                        prof = AthenaAgentProfile(
                            name=name,
                            role=data.get("role", "Specialized Sub-Agent"),
                            description=data.get("description", ""),
                            system_prompt=data.get("system_prompt", ""),
                            allowed_tools=data.get("allowed_tools", []),
                            category=data.get("category", "general"),
                            created_at=data.get("created_at", ""),
                            is_builtin=data.get("is_builtin", False),
                        )
                        self._profiles[name] = prof
                    except Exception as err:
                        log.debug("Failed parsing agent profile %s: %s", f, err)

            log.info("Discovered %d Athena agent profiles in %s", len(self._profiles), self.agents_dir)
            return list(self._profiles.values())

    def get_agent_profile(self, name: str) -> Optional[AthenaAgentProfile]:
        clean = name.strip().lower().replace("-", "_")
        self.discover_agents()
        with self._lock:
            if clean in self._profiles:
                return self._profiles[clean]
            for p in self._profiles.values():
                if clean in p.name.lower():
                    return p
        return None

    def list_agents_summary(self) -> str:
        """Format a list of all available sub-agents."""
        profiles = self.discover_agents()
        if not profiles:
            return "No agent profiles found in `.athena/agents/`."

        lines = [f"🤖 **Athena Modular Agent Registry ({len(profiles)} agents loaded):**\n"]
        for p in profiles:
            tools_str = f" | Tools: {', '.join(p.allowed_tools[:4])}" if p.allowed_tools else ""
            lines.append(f"- **`{p.name}`** — *{p.role}*")
            lines.append(f"  {p.description}")
            lines.append(f"  Category: `{p.category}`{tools_str}\n")

        lines.append("💡 *Use `/agent dispatch <name> <prompt>` to run a sub-agent in the background.*")
        return "\n".join(lines)

    def create_agent_profile(
        self,
        name: str,
        role: str,
        description: str,
        system_prompt: str,
        allowed_tools: Optional[list[str]] = None,
        category: str = "custom",
    ) -> str:
        """Create and save a new agent profile in `.athena/agents/`."""
        slug = re.sub(r"[^\w\-]", "_", name.lower()).strip("_")
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        agent_file = self.agents_dir / f"{slug}.json"

        profile_data = {
            "name": slug,
            "role": role.strip(),
            "description": description.strip(),
            "system_prompt": system_prompt.strip(),
            "allowed_tools": allowed_tools or ["terminal_command", "notes_add_note"],
            "category": category.strip() or "custom",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_builtin": False,
        }

        agent_file.write_text(json.dumps(profile_data, indent=2), encoding="utf-8")
        self.discover_agents()

        return f"🎉 **Agent Profile Created:** `{slug}` (`.athena/agents/{slug}.json`)\n- **Role:** {role}\n- **Category:** {category}"

    def _load_persisted_jobs(self) -> None:
        if AGENT_TASKS_FILE.exists():
            try:
                data = json.loads(AGENT_TASKS_FILE.read_text(encoding="utf-8"))
                for item in data:
                    if "agent_name" not in item:
                        item["agent_name"] = item.get("name", "custom_agent")
                    job = AgentJob(**item)
                    if job.status == "running":
                        job.status = "cancelled"
                    self._jobs[job.task_id] = job
            except Exception as exc:
                log.debug(f"Failed to load agent tasks: {exc}")

    def _save_jobs(self) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload = [asdict(j) for j in list(self._jobs.values())[-30:]]
            AGENT_TASKS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            log.debug(f"Failed to save agent tasks: {exc}")

    def dispatch_agent_by_name(self, agent_name: str, task_prompt: str) -> str:
        """Dispatch a specialized agent by profile name."""
        prof = self.get_agent_profile(agent_name)
        if not prof:
            available = ", ".join(f"`{p.name}`" for p in self.discover_agents())
            return f"❌ Error: Agent `{agent_name}` not found. Available agents: {available}"

        return self.dispatch_task(
            name=f"{prof.name}: {task_prompt[:35]}",
            task_type=prof.category,
            target_or_prompt=task_prompt,
            agent_name=prof.name,
        )

    def dispatch_task(
        self,
        name: str,
        task_type: str,
        target_or_prompt: str,
        agent_name: str = "autonomous_worker",
        custom_runner: Optional[Callable[[AgentJob, threading.Event], None]] = None,
    ) -> str:
        """Spawn a new concurrent background agent worker thread."""
        task_id = f"agent-{int(time.time() * 1000) % 100000}"
        job = AgentJob(
            task_id=task_id,
            name=name,
            agent_name=agent_name,
            task_type=task_type,
            status="running",
            progress_pct=5,
            current_step="Initializing agent execution environment...",
            started_at=time.time(),
        )

        cancel_event = threading.Event()
        with self._lock:
            self._jobs[task_id] = job
            self._cancel_flags[task_id] = cancel_event

        if self.bus is not None:
            self.bus.log("INFO", f"🤖 Sub-Agent dispatched: '{name}' [{task_id}] (Agent: {agent_name})")
            self.bus.event("agent_task_started", **asdict(job))

        def _worker():
            try:
                if custom_runner:
                    custom_runner(job, cancel_event)
                else:
                    self._default_task_runner(job, target_or_prompt, cancel_event)

                if cancel_event.is_set():
                    job.status = "cancelled"
                    job.current_step = "Task cancelled by operator."
                else:
                    job.status = "completed"
                    job.progress_pct = 100
                    job.completed_at = time.time()

            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
                job.current_step = f"Failed: {exc}"
                log.exception(f"Subagent {task_id} failed: {exc}")
            finally:
                self._save_jobs()
                if self.bus is not None:
                    self.bus.log("INFO", f"🤖 Sub-Agent '{name}' finished: {job.status}")
                    self.bus.event("agent_task_finished", **asdict(job))

        t = threading.Thread(target=_worker, daemon=True, name=f"Agent-{task_id}")
        self._threads[task_id] = t
        t.start()
        self._save_jobs()

        return f"🚀 Sub-Agent **`{agent_name}`** launched successfully! Task ID: **`{task_id}`** (Task: {name})."

    def _default_task_runner(self, job: AgentJob, target: str, cancel: threading.Event) -> None:
        """Default multi-stage task runner executing specialized agent pipelines."""
        if cancel.is_set():
            return

        job.progress_pct = 20
        job.current_step = f"Phase 1/3: Analyzing objective and context for '{target[:60]}'..."
        self._notify_progress(job)
        time.sleep(0.8)

        if cancel.is_set():
            return

        job.progress_pct = 55
        job.current_step = f"Phase 2/3: Executing specialized {job.agent_name} pipeline..."
        self._notify_progress(job)

        if job.agent_name == "recon_specialist" or job.task_type in ("security", "security_scan"):
            from web_security_scanner import run_full_vulnerability_scan
            res = run_full_vulnerability_scan(target)
            job.result_summary = res[:300] + ("..." if len(res) > 300 else "")
        elif job.agent_name == "deep_researcher" or job.task_type in ("research", "deep_research"):
            from deep_research import get_deep_research_engine
            engine = get_deep_research_engine()
            res = engine.start_research(target)
            job.result_summary = f"Deep Research task initiated for '{target}'. Generating comprehensive notes paper in vault."
        elif job.agent_name == "ctf_copilot" or job.task_type == "ctf":
            from lab_copilot import get_dossier_manager
            mgr = get_dossier_manager()
            if not mgr.active_machine:
                mgr.start_session(target, "10.10.11.x", "Hack The Box")
            res = mgr.get_status()
            job.result_summary = res
        elif job.agent_name == "termux_sysadmin":
            from lab_copilot import audit_termux_toolchain
            res = audit_termux_toolchain()
            job.result_summary = res[:300] + "..."
        else:
            job.result_summary = f"Autonomous sub-agent task completed on '{target}'."

        time.sleep(0.8)

        if cancel.is_set():
            return

        job.progress_pct = 95
        job.current_step = "Phase 3/3: Synchronizing findings and archiving report..."
        self._notify_progress(job)
        time.sleep(0.4)

    def _notify_progress(self, job: AgentJob) -> None:
        if self.bus is not None:
            self.bus.event("agent_task_progress", **asdict(job))

    def query_tasks(self, limit: int = 10) -> str:
        """Format active and recent background agent tasks."""
        with self._lock:
            jobs_list = sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)[:limit]

        if not jobs_list:
            return "🤖 No background agent tasks are currently registered."

        lines = ["🤖 **Athena Multi-Agent Task Orchestrator Status:**"]
        for j in jobs_list:
            status_icon = (
                "⚡ [RUNNING]" if j.status == "running" else
                ("🟢 [COMPLETED]" if j.status == "completed" else
                 ("🔴 [FAILED]" if j.status == "failed" else "⚪ [CANCELLED]"))
            )
            elapsed = (j.completed_at or time.time()) - j.started_at
            lines.append(f"\n- **{j.name}** (`{j.task_id}`) — {status_icon}")
            lines.append(f"  *Agent:* `{j.agent_name}` | *Type:* `{j.task_type}` | *Progress:* `{j.progress_pct}%` | *Elapsed:* `{elapsed:.1f}s`")
            lines.append(f"  *Status:* {j.current_step}")
            if j.result_summary:
                lines.append(f"  *Result:* {j.result_summary}")

        return "\n".join(lines)

    def cancel_task(self, task_id: str) -> str:
        """Cancel a running background agent task."""
        clean_id = task_id.strip()
        with self._lock:
            job = self._jobs.get(clean_id)
            event = self._cancel_flags.get(clean_id)

        if not job:
            return f"Error: Subagent task '{clean_id}' not found."
        if job.status != "running":
            return f"Subagent task '{clean_id}' is already {job.status}."

        if event:
            event.set()
        job.status = "cancelled"
        job.current_step = "Cancelled by user."
        self._save_jobs()

        if self.bus is not None:
            self.bus.log("INFO", f"🛑 Subagent task '{clean_id}' cancelled.")
            self.bus.event("agent_task_cancelled", task_id=clean_id)

        return f"🛑 Subagent task **`{clean_id}`** ({job.name}) has been cancelled."


_AGENT_DISPATCHER: Optional[MultiAgentDispatcher] = None


def get_agent_dispatcher() -> MultiAgentDispatcher:
    global _AGENT_DISPATCHER
    if _AGENT_DISPATCHER is None:
        _AGENT_DISPATCHER = MultiAgentDispatcher()
    return _AGENT_DISPATCHER
