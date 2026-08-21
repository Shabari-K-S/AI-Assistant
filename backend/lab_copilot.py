#!/usr/bin/env python3
"""Athena Interactive CTF & Cybersecurity Lab Toolkit (Hack The Box / Lab Co-Pilot)

Provides pure-Python security utilities for authorized labs, CTFs, and defensive analysis:
1. Multi-Format Payload Decoder & Auto-Detector (Base64, Hex, URL, JWT, HTML Entities, Rot13, Binary)
2. Intelligent Hash Identifier with Hashcat & John the Ripper mode mappings
3. Educational Vulnerability & CVE Mentor (Root cause analysis & mitigations without spoiling flags)
4. Automated Lab Dossier Manager (Session logging & Markdown walkthrough generator)
"""

from __future__ import annotations

import base64
import binascii
import html
import json
import logging
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("athena.lab_copilot")

DATA_DIR = Path(__file__).resolve().parent / "data"
NOTES_VAULT = DATA_DIR / "notes"
DOSSIERS_DIR = NOTES_VAULT / "lab-dossiers"


# --------------------------------------------------------------------------- #
# 1. Multi-Format Payload Decoder & Auto-Detector
# --------------------------------------------------------------------------- #

def decode_payload(payload: str) -> str:
    """Analyze and decode a payload across multiple encoding schemes simultaneously."""
    cleaned = payload.strip()
    if not cleaned:
        return "❌ Error: Payload string is empty."

    results: dict[str, Any] = {}

    # 1. Base64 Decoding (Standard and URL-safe)
    try:
        # Pad if missing
        b64_candidate = cleaned
        missing_padding = len(b64_candidate) % 4
        if missing_padding:
            b64_candidate += "=" * (4 - missing_padding)
        decoded_bytes = base64.b64decode(b64_candidate, validate=False)
        try:
            decoded_text = decoded_bytes.decode("utf-8")
            if any(c.isprintable() for c in decoded_text) and len(decoded_text) > 0:
                results["Base64"] = decoded_text
        except UnicodeDecodeError:
            results["Base64 (Hex Dump)"] = decoded_bytes.hex()
    except Exception:
        pass

    # 2. Hexadecimal / ASCII Hex Decoding
    try:
        hex_clean = re.sub(r"[\\x0\s,:]", "", cleaned)
        if len(hex_clean) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in hex_clean) and len(hex_clean) >= 2:
            hex_bytes = bytes.fromhex(hex_clean)
            try:
                hex_text = hex_bytes.decode("utf-8")
                if any(c.isprintable() for c in hex_text):
                    results["Hex / ASCII"] = hex_text
            except UnicodeDecodeError:
                results["Hex (Raw)"] = repr(hex_bytes)
    except Exception:
        pass

    # 3. URL & Double URL Decoding
    try:
        if "%" in cleaned:
            url_decoded = urllib.parse.unquote(cleaned)
            if url_decoded != cleaned:
                results["URL Decoded"] = url_decoded
            double_url = urllib.parse.unquote(url_decoded)
            if double_url != url_decoded and double_url != cleaned:
                results["Double URL Decoded"] = double_url
    except Exception:
        pass

    # 4. HTML Entities
    try:
        if "&" in cleaned and ";" in cleaned:
            html_decoded = html.unescape(cleaned)
            if html_decoded != cleaned:
                results["HTML Entities"] = html_decoded
    except Exception:
        pass

    # 5. JWT (JSON Web Token) Header & Payload Inspector
    jwt_match = re.match(r"^([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_-]*)$", cleaned)
    if jwt_match:
        try:
            h_b64, p_b64, sig = jwt_match.groups()
            # Decode Header
            h_pad = h_b64 + "=" * ((4 - len(h_b64) % 4) % 4)
            header_json = json.loads(base64.urlsafe_b64decode(h_pad).decode("utf-8"))
            # Decode Payload
            p_pad = p_b64 + "=" * ((4 - len(p_b64) % 4) % 4)
            payload_json = json.loads(base64.urlsafe_b64decode(p_pad).decode("utf-8"))

            jwt_formatted = (
                f"**JWT Header:** `{json.dumps(header_json)}`\n"
                f"**JWT Claims / Payload:**\n```json\n{json.dumps(payload_json, indent=2)}\n```\n"
            )
            if "exp" in payload_json:
                exp_ts = payload_json["exp"]
                jwt_formatted += f"**Expires At:** `{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(exp_ts))}`\n"
            results["JWT Token Inspector"] = jwt_formatted
        except Exception:
            pass

    # 6. Rot13
    try:
        if any(c.isalpha() for c in cleaned):
            import codecs
            rot13_text = codecs.encode(cleaned, "rot_13")
            results["ROT13"] = rot13_text
    except Exception:
        pass

    # 7. Binary String Decoding (e.g. "01000001 01000010")
    bin_clean = re.sub(r"[\s,]", "", cleaned)
    if len(bin_clean) >= 8 and len(bin_clean) % 8 == 0 and all(c in "01" for c in bin_clean):
        try:
            bin_chars = [chr(int(bin_clean[i:i+8], 2)) for i in range(0, len(bin_clean), 8)]
            results["Binary (8-bit ASCII)"] = "".join(bin_chars)
        except Exception:
            pass

    if not results:
        return f"🔍 **Payload Inspection for:** `{cleaned[:100]}`\n\nNo standard encoding (Base64, Hex, URL, JWT, Rot13, Binary) could be automatically decoded. The input appears to be plain text or a proprietary format."

    lines = [f"🔓 **Athena Lab Payload Decoder Output:**", f"**Input:** `{cleaned[:120]}`\n"]
    for enc_type, val in results.items():
        if "\n" in str(val):
            lines.append(f"### 🏷️ {enc_type}\n{val}\n")
        else:
            lines.append(f"- **{enc_type}**: `{val}`")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 2. Intelligent Hash Identifier with Hashcat & John Mappings
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class HashSignature:
    name: str
    category: str
    hashcat_mode: str
    john_format: str
    regex: re.Pattern
    description: str

HASH_SIGNATURES: tuple[HashSignature, ...] = (
    # bcrypt
    HashSignature(
        name="bcrypt",
        category="Password Hash (Key Derivation)",
        hashcat_mode="3200",
        john_format="bcrypt",
        regex=re.compile(r"^\$(2[abxy]?)\$\d{2}\$[A-Za-z0-9./]{53}$"),
        description="Standard blowfish-based password hash commonly found in Linux shadow and web frameworks.",
    ),
    # Argon2
    HashSignature(
        name="Argon2 (id/i/d)",
        category="Modern Memory-Hard Password Hash",
        hashcat_mode="13400",
        john_format="argon2",
        regex=re.compile(r"^\$argon2(id|i|d)\$v=\d+\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+$"),
        description="State-of-the-art memory-hard hash designed to resist GPU/ASIC attacks.",
    ),
    # SHA-512 (Unix Shadow $6$)
    HashSignature(
        name="SHA-512 (Unix Shadow $6$)",
        category="Linux OS Password Hash",
        hashcat_mode="1800",
        john_format="sha512crypt",
        regex=re.compile(r"^\$6\$(rounds=\d+\$)?[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}$"),
        description="Default Linux /etc/shadow password hash for modern Ubuntu, Debian, and RHEL.",
    ),
    # MD5 (Unix Shadow $1$ / Apache $apr1$)
    HashSignature(
        name="MD5 (Unix / APR1)",
        category="Legacy Web & OS Hash",
        hashcat_mode="500 / 1600",
        john_format="md5crypt",
        regex=re.compile(r"^\$(1|apr1)\$[A-Za-z0-9./]{1,8}\$[A-Za-z0-9./]{22}$"),
        description="Legacy MD5 crypt used in older Unix systems and Apache .htpasswd files.",
    ),
    # WordPress / phpBB ($P$ / $H$)
    HashSignature(
        name="WordPress / phpBB ($P$ / $H$)",
        category="CMS Password Hash",
        hashcat_mode="400",
        john_format="phpass",
        regex=re.compile(r"^\$[PH]\$[A-Za-z0-9./]{31}$"),
        description="PassHash portable hash standard utilized by WordPress, Drupal 7, and phpBB.",
    ),
    # MySQL 4.1+ (41 hex starting with *)
    HashSignature(
        name="MySQL 4.1+ / MariaDB",
        category="Database Hash",
        hashcat_mode="300",
        john_format="mysql-sha1",
        regex=re.compile(r"^\*[0-9A-Fa-f]{40}$"),
        description="Double SHA-1 password hash format used by MySQL user tables.",
    ),
    # NTLM / MD5 / LM (32 Hex Characters)
    HashSignature(
        name="NTLM / MD5 / LM",
        category="32-Char Hex Digest",
        hashcat_mode="1000 (NTLM) | 0 (MD5) | 3000 (LM)",
        john_format="nt / raw-md5 / lm",
        regex=re.compile(r"^[0-9A-Fa-f]{32}$"),
        description="Common 128-bit hash format. In Windows Active Directory labs, this is almost always NTLM; in web apps, often raw MD5.",
    ),
    # SHA-1 (40 Hex Characters)
    HashSignature(
        name="SHA-1 / Git Commit / RIPEMD-160",
        category="40-Char Hex Digest",
        hashcat_mode="100 (SHA-1) | 6000 (RIPEMD-160)",
        john_format="raw-sha1",
        regex=re.compile(r"^[0-9A-Fa-f]{40}$"),
        description="160-bit cryptographic hash digest used in legacy certificates, Git commits, and token signatures.",
    ),
    # SHA-256 (64 Hex Characters)
    HashSignature(
        name="SHA-256",
        category="64-Char Hex Digest",
        hashcat_mode="1400 (Raw SHA-256)",
        john_format="raw-sha256",
        regex=re.compile(r"^[0-9A-Fa-f]{64}$"),
        description="Standard 256-bit SHA-2 cryptographic digest commonly used for API tokens, password digests, and integrity verification.",
    ),
    # SHA-512 / Whirlpool (128 Hex Characters)
    HashSignature(
        name="SHA-512 / Whirlpool",
        category="128-Char Hex Digest",
        hashcat_mode="1700 (Raw SHA-512) | 6100 (Whirlpool)",
        john_format="raw-sha512",
        regex=re.compile(r"^[0-9A-Fa-f]{128}$"),
        description="512-bit cryptographic hash digest.",
    ),
)


def identify_hash(hash_str: str) -> str:
    """Identify possible hash algorithms, Hashcat modes, and John the Ripper formats."""
    cleaned = hash_str.strip()
    if not cleaned:
        return "❌ Error: Hash string is empty."

    matches: list[HashSignature] = []
    for sig in HASH_SIGNATURES:
        if sig.regex.match(cleaned):
            matches.append(sig)

    if not matches:
        return (
            f"🔍 **Hash Identification:** `{cleaned[:80]}`\n\n"
            f"- **Length:** `{len(cleaned)}` characters\n"
            f"- **Analysis:** No specific standard hash signature matched directly. "
            f"If this is a custom salted hash (e.g. `md5($pass.$salt)`), specify the known format."
        )

    lines = [
        f"⚡ **Athena Hash Identifier Report:**",
        f"**Input Hash:** `{cleaned[:100]}`",
        f"**Character Length:** `{len(cleaned)}` | **Identified Candidates:** `{len(matches)}`\n",
    ]

    for m in matches:
        lines.append(
            f"### 🏷️ **{m.name}**\n"
            f"- **Category:** {m.category}\n"
            f"- **Hashcat Mode:** `hashcat -m {m.hashcat_mode} hash.txt wordlist.txt`\n"
            f"- **John Format:** `john --format={m.john_format} hash.txt`\n"
            f"- **Details:** {m.description}\n"
        )

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 3. Educational Vulnerability & CVE Mentor
# --------------------------------------------------------------------------- #

def explain_cve_mechanics(query: str) -> str:
    """Provide educational, first-principles explanations of vulnerability classes and CVEs."""
    cleaned = query.strip()
    if not cleaned:
        return "❌ Error: CVE or vulnerability query is empty."

    # General vulnerability classes dictionary
    VULN_PATTERNS: dict[str, dict[str, str]] = {
        "sqli": {
            "title": "SQL Injection (SQLi) Mechanics",
            "concept": "Occurs when untrusted user input is directly concatenated into a dynamic SQL query rather than being bound as a parameter.",
            "mechanics": "The database interpreter fails to distinguish between query code and data. Attackers can inject SQL syntax (like `' OR 1=1--`) to alter the query logic, bypass authentication, or dump data via UNION queries or blind boolean/time delays.",
            "remediation": "Use parameterized prepared statements (e.g., `cursor.execute('SELECT * FROM users WHERE id = %s', (uid,))`) and ORM frameworks with strict input validation.",
        },
        "ssrf": {
            "title": "Server-Side Request Forgery (SSRF) Mechanics",
            "concept": "Occurs when a server application fetches a remote resource (e.g. avatar URL, webhook, PDF generator) using a user-supplied URL without strict destination IP/scheme validation.",
            "mechanics": "Attackers provide internal loopback or cloud metadata addresses (like `http://127.0.0.1:8080/admin` or `http://169.254.169.254/latest/meta-data/`) causing the trusted server to make unauthorized internal requests on the attacker's behalf.",
            "remediation": "Enforce strict destination hostname allowlists, block private/loopback IP ranges (RFC 1918 & link-local), and disable unnecessary URL redirect following.",
        },
        "lfi": {
            "title": "Local File Inclusion (LFI) & Path Traversal",
            "concept": "Occurs when an application accepts user input to construct a local filesystem path without adequate path canonicalization.",
            "mechanics": "Using directory traversal sequences (`../../../../etc/passwd` or null-byte injections on legacy systems), attackers escape the intended directory root to read sensitive system configuration files or source code.",
            "remediation": "Use an explicit mapping/whitelist of allowed files, or validate with `os.path.abspath()` ensuring the resolved target path begins strictly with the allowed base directory.",
        },
        "deserialization": {
            "title": "Insecure Object Deserialization",
            "concept": "Occurs when untrusted serialized data (Python pickle, PHP serialize, Java ObjectInputStream, YAML) is deserialized by an application.",
            "mechanics": "The deserialization process automatically instantiates objects and executes lifecycle magic methods (e.g., `__reduce__` in Python, `__wakeup` in PHP, `readObject` in Java), allowing injected object graphs to achieve remote code execution.",
            "remediation": "Never deserialize untrusted user data with formats that permit code execution. Use safe, standard data formats like JSON or Protocol Buffers.",
        },
    }

    q_lower = cleaned.lower()
    for key, info in VULN_PATTERNS.items():
        if key in q_lower:
            return (
                f"🛡️ **Athena Lab Mentorship: {info['title']}**\n\n"
                f"- **Core Concept:** {info['concept']}\n"
                f"- **Under the Hood Mechanics:** {info['mechanics']}\n"
                f"- **Defensive Remediation:** {info['remediation']}\n\n"
                f"*Athena Note: When practicing in labs, focus on mapping the application data flow from the entry point to the vulnerable function sink.*"
            )

    # Search local exploit-db searchsploit or explain as CVE query
    return (
        f"🛡️ **Athena CVE & Vulnerability Explainer: `{cleaned}`**\n\n"
        f"- **Vulnerability Architecture:** When auditing this vulnerability, examine whether the defect originates in network parsing, memory management, authentication state, or untrusted parameter evaluation.\n"
        f"- **Lab Enumeration Advice:** Verify the exact version of the target service and check corresponding software changelogs for the security patch diff.\n"
        f"- **Defensive Guidance:** Apply least-privilege service boundaries, sandboxed execution, and upgrade to the vendor-patched release."
    )


# --------------------------------------------------------------------------- #
# 4. Automated Lab Dossier Manager (Session Logging & Markdown Walkthroughs)
# --------------------------------------------------------------------------- #

@dataclass
class LabEntry:
    timestamp: str
    milestone: str
    note: str
    command: str = ""
    output_snippet: str = ""


class LabDossierManager:
    """Manages active lab sessions and exports structured Markdown reports."""

    def __init__(self) -> None:
        self.active_machine: str = ""
        self.target_ip: str = ""
        self.platform: str = "Hack The Box"
        self.start_time: str = ""
        self.entries: list[LabEntry] = []

    def start_session(self, machine_name: str, target_ip: str, platform: str = "Hack The Box") -> str:
        """Start tracking an active lab session."""
        self.active_machine = machine_name.strip()
        self.target_ip = target_ip.strip()
        self.platform = platform.strip()
        self.start_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.entries = []

        # Add initial kickoff entry
        self.entries.append(
            LabEntry(
                timestamp=self.start_time,
                milestone="Reconnaissance",
                note=f"Lab session initiated for target {self.active_machine} ({self.target_ip}) on {self.platform}.",
            )
        )
        return f"🎯 **Lab Session Started:** Tracking **`{self.active_machine}`** (`{self.target_ip}`) on {self.platform}."

    def log_finding(
        self,
        note: str,
        milestone: str = "Enumeration",
        command_used: str = "",
        output_snippet: str = "",
    ) -> str:
        """Log a finding, command, or milestone in the active lab session."""
        if not self.active_machine:
            # Auto-kickoff default session if none active
            self.start_session("Unknown-Lab-Target", "127.0.0.1", "Lab Environment")

        entry = LabEntry(
            timestamp=time.strftime("%H:%M:%S"),
            milestone=milestone.capitalize(),
            note=note.strip(),
            command=command_used.strip(),
            output_snippet=output_snippet.strip(),
        )
        self.entries.append(entry)
        return f"📝 **Logged Finding ({entry.milestone}):** {note[:120]} (Total entries: {len(self.entries)})"

    def export_dossier(self) -> str:
        """Generate and save a publication-grade Markdown walkthrough in the Notes Vault."""
        if not self.active_machine:
            return "❌ Error: No active lab session to export."

        slug = re.sub(r"[^\w\-]", "-", self.active_machine.lower()).strip("-")
        DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
        report_file = DOSSIERS_DIR / f"{slug}.md"

        dossier_lines = [
            f"# Lab Dossier: {self.active_machine}",
            f"",
            f"**Target Machine:** `{self.active_machine}` | **Target IP:** `{self.target_ip}`  ",
            f"**Platform:** {self.platform} | **Session Started:** {self.start_time}  ",
            f"**Analyst / Co-Pilot:** Athena Autonomous Intelligence Engine  ",
            f"",
            f"---",
            f"",
            f"## 🎯 Executive Overview",
            f"This lab dossier documents the technical methodology, port reconnaissance, service enumeration, and vulnerability analysis performed against **{self.active_machine}** (`{self.target_ip}`).",
            f"",
            f"---",
            f"",
            f"## 📋 Chronological Lab Timeline & Milestones",
            f"",
        ]

        for idx, entry in enumerate(self.entries, 1):
            dossier_lines.append(f"### {idx}. [{entry.timestamp}] {entry.milestone}")
            dossier_lines.append(f"**Observation / Finding:**\n{entry.note}\n")
            if entry.command:
                dossier_lines.append(f"**Command Executed:**\n```bash\n{entry.command}\n```\n")
            if entry.output_snippet:
                dossier_lines.append(f"**Key Output Snippet:**\n```text\n{entry.output_snippet}\n```\n")
            dossier_lines.append("")

        dossier_lines.extend([
            f"---",
            f"",
            f"## 🛡️ Key Takeaways & Defensive Lessons",
            f"1. **Root Cause:** Ensure all services apply least-privilege configurations and boundary input validation.",
            f"2. **Patching:** Keep all exposed software daemons and web frameworks updated against known CVEs.",
            f"3. **Auditing:** Maintain centralized immutable logging for suspicious authentication and shell activities.",
        ])

        full_content = "\n".join(dossier_lines)

        frontmatter = {
            "id": f"lab-{slug}",
            "title": f"Lab Dossier: {self.active_machine}",
            "category": "lab-dossiers",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "machine": self.active_machine,
            "target_ip": self.target_ip,
            "platform": self.platform,
            "entries_count": len(self.entries),
            "tags": ["ctf", "lab-dossier", "hackthebox", slug],
        }

        # Write frontmatter and markdown
        fm_yaml = "---\n"
        for k, v in frontmatter.items():
            if isinstance(v, list):
                fm_yaml += f"{k}: {json.dumps(v)}\n"
            else:
                fm_yaml += f"{k}: {json.dumps(v)}\n"
        fm_yaml += "---\n\n"

        report_file.write_text(fm_yaml + full_content, encoding="utf-8")

        return (
            f"🎉 **Lab Dossier Exported Successfully!**\n\n"
            f"- **Target:** `{self.active_machine}` (`{self.target_ip}`)\n"
            f"- **Entries Recorded:** `{len(self.entries)}`\n"
            f"- **Saved to Notes Vault:** `{report_file.name}` (`data/notes/lab-dossiers/{slug}.md`)\n"
        )

    def get_status(self) -> str:
        if not self.active_machine:
            return "⚪ No active lab session. Use `lab_session_start(machine_name, target_ip)` to begin tracking."
        return (
            f"🎯 **Active Lab Session:** **`{self.active_machine}`** (`{self.target_ip}`)\n"
            f"- **Platform:** {self.platform}\n"
            f"- **Started:** {self.start_time}\n"
            f"- **Logged Milestones:** {len(self.entries)}"
        )


_global_dossier_manager: LabDossierManager | None = None

def get_dossier_manager() -> LabDossierManager:
    global _global_dossier_manager
    if _global_dossier_manager is None:
        _global_dossier_manager = LabDossierManager()
    return _global_dossier_manager
