#!/usr/bin/env python3
"""Generalized Skills Engine for A.T.H.E.N.A.

Discovers, parses, synthesizes, and executes modular agentic skills stored in
`.athena/skills/<skill_name>/SKILL.md`.

Supports:
1. Dynamic skill discovery and YAML frontmatter parsing.
2. Multi-mode `/learn`:
   - URL Mode: Scrapes and converts documentation into a structured skill.
   - Autonomous Search Mode: Searches DuckDuckGo for topic guides, crawls top sources,
     and synthesizes a technical playbook.
   - Direct Rule Mode: Formats custom user rules/workflows into a persistent skill.
3. On-demand skill injection into LLM system prompt / tool registry.
4. Pre-populated baseline security, research, code, and termux skills.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("ev.skills")

# Base directory for Athena skills
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ATHENA_DIR = PROJECT_ROOT / ".athena"
GLOBAL_ATHENA_DIR = Path.home() / ".athena"

# Prefer workspace .athena/skills, fallback to global ~/.athena/skills
SKILLS_DIR = WORKSPACE_ATHENA_DIR / "skills"


@dataclass
class AthenaSkill:
    name: str
    description: str
    category: str = "general"
    triggers: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    file_path: str = ""
    instructions: str = ""
    created_at: str = ""
    is_builtin: bool = False


# Default baseline skills to initialize if .athena/skills is empty
DEFAULT_SKILLS: list[dict[str, Any]] = [
    {
        "name": "ctf_exploit_playbook",
        "description": "Tactical methodology for Hack The Box, TryHackMe, and CTF binary/web exploitation.",
        "category": "security",
        "triggers": ["/ctf", "ctf", "hackthebox", "privesc", "exploit"],
        "tools": ["lab_dossier_manager", "terminal_command", "notes_add_note"],
        "instructions": """# CTF & Lab Exploitation Playbook

## 🎯 Reconnaissance Phase
1. Fast TCP port scan: `nmap -sT -sV -Pn --top-ports 1000 <target_ip>`
2. Web enumeration: Identify tech stack, headers, hidden parameters, and endpoints.
3. Check version vulnerabilities against Exploit-DB and CVE databases.

## ⚔️ Foothold & Exploitation
1. Prioritize unauthenticated RCE, default credentials, or injection points.
2. In request basket / proxy services, test for SSRF forwarding to internal ports (e.g. `127.0.0.1:80`).
3. Stabilize reverse shells immediately: `python3 -c 'import pty; pty.spawn("/bin/bash")'`.

## 🛡️ Privilege Escalation & Walkthrough Logging
1. Enumerate `sudo -l`, SUID binaries (`find / -perm -4000 2>/dev/null`), and internal cron jobs.
2. Automatically record all steps and commands into the Lab Dossier via `lab_dossier_manager`.
""",
    },
    {
        "name": "code_review_refactor",
        "description": "Automated code review, TypeScript/Python lint checking, and architectural refactoring.",
        "category": "coding",
        "triggers": ["/review", "code_review", "refactor", "lint"],
        "tools": ["git_status", "git_diff", "terminal_command"],
        "instructions": """# Code Review & Refactoring Standard

## 📋 Inspection Checklist
1. **Safety & Typings:** Verify strict TypeScript types (avoid `any`) and Python type hints.
2. **Asynchronous Handlers:** Ensure all promises and async threads have proper try/catch and error boundaries.
3. **No Placeholders:** All UI components and logic must be complete and fully functional.
4. **Performance:** Check for memory leaks, unclosed listeners, or redundant re-renders.
""",
    },
    {
        "name": "termux_mobile_ops",
        "description": "Android Termux environment optimization, package management, and rootless network operations.",
        "category": "sysadmin",
        "triggers": ["/termux", "termux", "android", "pkg", "rootless"],
        "tools": ["lab_env_check", "terminal_command", "battery_status"],
        "instructions": """# Android Termux Mobile Operations Skill

## 📱 Execution Rules for Non-Rooted Android
1. **Network Scans:** Non-rooted Android kernels block raw ICMP and SYN packets. Always use TCP Connect `-sT` and skip ping `-Pn` in Nmap.
2. **Package Toolchain:** Prefer lightweight ARM-compiled binaries (`nmap`, `curl`, `python`, `git`).
3. **Power Efficiency:** Minimize continuous background polling; use reactive event streams and wakelocks judiciously.
""",
    },
    {
        "name": "deep_research_synthesis",
        "description": "Multi-vector autonomous web research, academic paper compilation, and source curation.",
        "category": "research",
        "triggers": ["/research", "deep_research", "academic_paper", "literature_review"],
        "tools": ["start_deep_research", "get_research_summary", "notes_add_note"],
        "instructions": """# Deep Research & Academic Synthesis Skill

## 🔬 Multi-Vector Pipeline
1. Decompose research topic into 8 distinct exploratory queries.
2. Harvest verified sources from DuckDuckGo and scholarly domains.
3. Extract verified data points, empirical benchmarks, and architectural trade-offs.
4. Synthesize an authoritative technical deep-dive and save directly to Notes Vault (`notes/deep-research/`).
""",
    },
    {
        "name": "security_dast_audit",
        "description": "Autonomous DAST security auditing, SQLi/XSS testing, and triage report generation.",
        "category": "security",
        "triggers": ["/recon", "security_scan", "dast", "vulnerability"],
        "tools": ["web_security_scanner", "security_compile_triage_report", "ssl_inspect"],
        "instructions": """# Dynamic Security (DAST) Assessment Skill

## 🛡️ Audit Methodology
1. Probe for sensitive configuration exposures (`.env`, `.git/HEAD`, `backup.sql`).
2. Test parameters for SQL syntax reflection and benign XSS probe reflection.
3. Inspect SSL/TLS certificate validity and encryption cipher suites.
4. Compile findings into a structured triage report saved into Notes Vault (`notes/security-reports/`).
""",
    },
]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\-]", "_", text.lower()).strip("_")
    return re.sub(r"_+", "_", slug) or "custom_skill"


def _parse_frontmatter(file_content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML-like frontmatter from markdown file."""
    if file_content.startswith("---"):
        parts = file_content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2].strip()
            meta: dict[str, Any] = {}
            for line in fm_text.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    val = val.strip()
                    # Handle json lists/strings
                    if val.startswith("[") and val.endswith("]"):
                        try:
                            meta[key] = json.loads(val.replace("'", '"'))
                        except Exception:
                            meta[key] = [x.strip(" '\"") for x in val[1:-1].split(",") if x.strip()]
                    elif val.lower() in ("true", "false"):
                        meta[key] = val.lower() == "true"
                    else:
                        meta[key] = val.strip(" '\"")
            return meta, body
    return {}, file_content.strip()


def _format_frontmatter(meta: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}: {json.dumps(v)}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body.strip())
    lines.append("")
    return "\n".join(lines)


class SkillsEngine:
    """Central engine for discovering, creating, executing, and learning skills."""

    def __init__(self) -> None:
        self.skills_dir = SKILLS_DIR
        self._skills: Dict[str, AthenaSkill] = {}
        self._lock = threading.Lock()
        self._init_skills_directory()

    def _init_skills_directory(self) -> None:
        """Ensure skills directory exists and default skills are pre-populated."""
        try:
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            # Check if any skill files exist
            existing = list(self.skills_dir.glob("**/*.md"))
            if not existing:
                for s in DEFAULT_SKILLS:
                    skill_folder = self.skills_dir / s["name"]
                    skill_folder.mkdir(parents=True, exist_ok=True)
                    skill_file = skill_folder / "SKILL.md"
                    meta = {
                        "name": s["name"],
                        "description": s["description"],
                        "category": s.get("category", "general"),
                        "triggers": s.get("triggers", []),
                        "tools": s.get("tools", []),
                        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "is_builtin": True,
                    }
                    content = _format_frontmatter(meta, s["instructions"])
                    skill_file.write_text(content, encoding="utf-8")
                    log.info("Initialized default skill: %s", s["name"])
            self.discover_skills()
        except Exception as exc:
            log.warning("Skills directory initialization error: %s", exc)

    def discover_skills(self) -> list[AthenaSkill]:
        """Scan .athena/skills/ and return all loaded skills."""
        with self._lock:
            self._skills.clear()
            # 1. Scan workspace .athena/skills/
            paths_to_scan = [self.skills_dir]
            if GLOBAL_ATHENA_DIR.exists() and GLOBAL_ATHENA_DIR != WORKSPACE_ATHENA_DIR:
                paths_to_scan.append(GLOBAL_ATHENA_DIR / "skills")

            for base_path in paths_to_scan:
                if not base_path.exists():
                    continue
                # Support both .athena/skills/<name>/SKILL.md and .athena/skills/<name>.md
                for md_file in base_path.glob("**/*.md"):
                    try:
                        raw = md_file.read_text(encoding="utf-8")
                        meta, body = _parse_frontmatter(raw)
                        name = meta.get("name") or (md_file.parent.name if md_file.name == "SKILL.md" else md_file.stem)
                        name = _slugify(name)
                        desc = meta.get("description") or f"Athena skill for {name.replace('_', ' ')}"
                        cat = meta.get("category") or "general"
                        triggers = meta.get("triggers") or [f"/{name}", name.replace("_", " ")]
                        tools = meta.get("tools") or []
                        sources = meta.get("sources") or []
                        created = meta.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(md_file.stat().st_ctime))
                        is_builtin = meta.get("is_builtin", False)

                        skill = AthenaSkill(
                            name=name,
                            description=desc,
                            category=cat,
                            triggers=triggers,
                            tools=tools,
                            sources=sources,
                            file_path=str(md_file),
                            instructions=body,
                            created_at=created,
                            is_builtin=is_builtin,
                        )
                        self._skills[name] = skill
                    except Exception as err:
                        log.debug("Failed parsing skill file %s: %s", md_file, err)

            log.info("Discovered %d Athena skills in %s", len(self._skills), self.skills_dir)
            return list(self._skills.values())

    def get_skill(self, name_or_trigger: str) -> Optional[AthenaSkill]:
        """Lookup a skill by exact name, slug, or trigger keyword."""
        clean = name_or_trigger.strip().lower().lstrip("/")
        self.discover_skills()
        with self._lock:
            # 1. Exact name match
            if clean in self._skills:
                return self._skills[clean]
            # 2. Trigger or partial match
            for s in self._skills.values():
                if clean == s.name or clean in [t.lower().lstrip("/") for t in s.triggers]:
                    return s
                if clean in s.name.lower():
                    return s
        return None

    def list_skills_summary(self) -> str:
        """Format a human-readable list of all discovered skills."""
        skills = self.discover_skills()
        if not skills:
            return "No skills currently registered in `.athena/skills/`."

        lines = [f"⚡ **Athena Skill Registry ({len(skills)} skills loaded):**\n"]
        for s in skills:
            triggers_str = ", ".join(f"`{t}`" for t in s.triggers[:3])
            tools_str = f" | Tools: {', '.join(s.tools[:3])}" if s.tools else ""
            lines.append(f"- **`{s.name}`** [Category: `{s.category}`]")
            lines.append(f"  *{s.description}*")
            lines.append(f"  Triggers: {triggers_str}{tools_str}")
            lines.append(f"  Path: `{s.file_path}`\n")

        lines.append("💡 *Use `/learn <url or topic>` to create new skills, or `/skill run <name>` to execute.*")
        return "\n".join(lines)

    def learn_skill(
        self,
        input_query: str,
        name_hint: str = "",
        category: str = "custom",
    ) -> str:
        """Learn a new skill from a URL, web search topic, or direct instructions.
        
        Saves the structured skill into `.athena/skills/<skill_name>/SKILL.md`.
        """
        raw = input_query.strip()
        if not raw:
            return "❌ Error: Please provide a URL, topic name, or instructions to learn."

        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # Check if input contains a URL
        url_match = re.search(r"https?://[^\s]+", raw)
        sources = []

        if url_match:
            # 1. URL Mode
            target_url = url_match.group(0)
            sources.append(target_url)
            log.info("Learning skill from URL: %s", target_url)
            scraped_title, scraped_content = self._scrape_url(target_url)
            
            skill_name = name_hint or _slugify(scraped_title or urllib.parse.urlparse(target_url).netloc)
            description = f"Autonomous skill learned from {target_url}"
            instructions = (
                f"# {scraped_title or skill_name}\n\n"
                f"**Source URL:** {target_url}  \n"
                f"**Learned On:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n\n"
                f"## 📖 Knowledge & Methodology\n"
                f"{scraped_content[:4000]}\n"
            )
        elif len(raw.split()) <= 12 and not raw.startswith("Always") and not raw.startswith("Rule:"):
            # 2. Autonomous Web Search Mode (e.g. topic name like "GraphQL security testing")
            topic = raw.strip("\"'")
            log.info("Learning skill via autonomous web search on topic: '%s'", topic)
            search_summary, crawled_sources = self._search_and_crawl_topic(topic)
            sources = [s["url"] for s in crawled_sources]
            skill_name = name_hint or _slugify(topic)
            description = f"Autonomous skill and playbook for {topic} synthesized from web research."
            
            instructions = (
                f"# {topic.title()} Playbook & Skill Guide\n\n"
                f"**Learned On:** {time.strftime('%Y-%m-%d %H:%M:%S')} | **Sources Consulted:** {len(crawled_sources)}  \n\n"
                f"## 🎯 Objective & Overview\n"
                f"Provides specialized methodology, commands, and workflows for **{topic}**.\n\n"
                f"## 🛠️ Step-by-Step Technical Execution\n"
                f"{search_summary}\n\n"
                f"## 📚 Verified Knowledge References\n"
            )
            for s in crawled_sources:
                instructions += f"- [{s['title']}]({s['url']}) — *{s['domain']}*\n"
        else:
            # 3. Direct Custom Rule / Instruction Mode
            first_words = raw.split()[:4]
            skill_name = name_hint or _slugify(" ".join(first_words))
            description = f"User-defined custom skill for {skill_name.replace('_', ' ')}"
            instructions = (
                f"# {skill_name.replace('_', ' ').title()}\n\n"
                f"**Created On:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n\n"
                f"## 📋 Rules & Execution Workflow\n"
                f"{raw}\n"
            )

        # Build frontmatter
        skill_folder = self.skills_dir / skill_name
        skill_folder.mkdir(parents=True, exist_ok=True)
        skill_file = skill_folder / "SKILL.md"

        meta = {
            "name": skill_name,
            "description": description,
            "category": category or "learned",
            "triggers": [f"/{skill_name}", skill_name.replace("_", " ")],
            "tools": ["terminal_command", "notes_add_note"],
            "sources": sources,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_builtin": False,
        }

        content = _format_frontmatter(meta, instructions)
        skill_file.write_text(content, encoding="utf-8")
        self.discover_skills()

        # Broadcast real-time SSE event to UI
        try:
            from evbridge import get_bus
            bus = get_bus()
            if bus:
                bus.publish({
                    "type": "skill_learned",
                    "skill": {
                        "name": skill_name,
                        "description": description,
                        "category": category,
                        "path": str(skill_file.relative_to(PROJECT_ROOT) if skill_file.is_relative_to(PROJECT_ROOT) else skill_file),
                    },
                })
                bus.log("INFO", f"⚡ New Skill Learned & Saved: '{skill_name}' (.athena/skills/{skill_name}/SKILL.md)")
        except Exception:
            pass

        return (
            f"🎉 **Skill Learned & Saved Successfully!**\n\n"
            f"- **Skill Name:** `{skill_name}`\n"
            f"- **Category:** `{category}`\n"
            f"- **Storage Path:** `.athena/skills/{skill_name}/SKILL.md`\n"
            f"- **Trigger:** Type `/{skill_name}` or ask Athena to execute `{skill_name}`\n"
            f"- **Sources Ingested:** {len(sources)}"
        )

    def _scrape_url(self, url: str) -> tuple[str, str]:
        """Fetch and extract markdown/text content from a web page."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AthenaSkills/2.0"},
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                raw_html = resp.read().decode("utf-8", "replace")
                # Extract title
                title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else url
                # Strip scripts and styles
                clean = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
                # Strip tags
                clean = re.sub(r"<[^>]+>", " ", clean)
                # Collapse whitespace
                clean = re.sub(r"\s+", " ", clean).strip()
                return title, clean
        except Exception as exc:
            log.warning("Scraping URL %s failed: %s", url, exc)
            return url, f"Could not fetch live content from {url} ({exc}). Generated fallback skill placeholder."

    def _search_and_crawl_topic(self, topic: str) -> tuple[str, list[dict[str, str]]]:
        """Search DuckDuckGo and crawl top pages to build a multi-source skill."""
        crawled_sources = []
        try:
            from duckduckgo_mcp_server import handle_search
            res_json = handle_search({"query": f"{topic} tutorial guide best practices documentation", "max_results": 4})
            data = json.loads(res_json) if isinstance(res_json, str) and res_json.startswith("{") else {}
            results = data.get("results", [])
            for r in results[:3]:
                url = r.get("url", "")
                if url:
                    t, content = self._scrape_url(url)
                    crawled_sources.append({
                        "url": url,
                        "title": r.get("title") or t,
                        "domain": urllib.parse.urlparse(url).netloc,
                        "snippet": content[:800],
                    })
        except Exception as exc:
            log.debug("DuckDuckGo skill search failed: %s", exc)

        if crawled_sources:
            summary_sections = []
            for idx, s in enumerate(crawled_sources, 1):
                summary_sections.append(f"### Core Concept {idx}: {s['title']}\n{s['snippet']}...\n")
            return "\n".join(summary_sections), crawled_sources

        return f"Specialized execution guidelines and automated rules for {topic}.", []


_SKILLS_ENGINE: Optional[SkillsEngine] = None


def get_skills_engine() -> SkillsEngine:
    global _SKILLS_ENGINE
    if _SKILLS_ENGINE is None:
        _SKILLS_ENGINE = SkillsEngine()
    return _SKILLS_ENGINE
