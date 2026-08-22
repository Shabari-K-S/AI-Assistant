#!/usr/bin/env python3
"""Cybersecurity & Bug Bounty Audit MCP Server for S.A.R.A.

Implements JSON-RPC 2.0 stdio Model Context Protocol (2024-11-05 spec) providing
risk-tiered security tools:
- Tier 1 (Zero/Low Risk - Auto-Run):
  * security_cve_search: Offline searchsploit & CVE advisory lookup
  * security_passive_recon: Passive subdomain enumeration via crt.sh & certificate logs
  * security_header_audit: HTTP security header & CORS/cookie compliance auditor
  * security_code_audit: SAST code scanner for secrets, SQLi, command injection, path traversal
  * security_report_export: Generates structured Markdown security reports in Notes Vault
- Tier 2 (Medium/High Risk - Permission Confirmation Required):
  * security_port_scan: Scoped network port & service inspection on allowlisted targets
"""

from __future__ import annotations

import html
import ipaddress
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Athena Security Auditor)"

# Allowed target network scopes (defaults to localhost & private subnets)
DEFAULT_ALLOWLIST = "localhost,127.0.0.1,::1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12"
RAW_ALLOWLIST = os.environ.get("SECURITY_TARGET_ALLOWLIST", DEFAULT_ALLOWLIST)
ALLOWED_TARGETS = [t.strip().lower() for t in RAW_ALLOWLIST.split(",") if t.strip()]

DATA_DIR = Path(__file__).resolve().parent / "data"
NOTES_VAULT = DATA_DIR / "notes"

TOOLS = [
    {
        "name": "security_cve_search",
        "description": "Search local Exploit-DB (searchsploit) and public vulnerability feeds for CVEs, advisories, and mitigations on specific software versions (e.g. 'Apache 2.4.49', 'OpenSSH 8.2'). (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Software name and version to search (e.g. 'Apache 2.4.49', 'Log4j 2.14').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of advisories to return (default: 8).",
                    "default": 8,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "security_passive_recon",
        "description": "Perform 100% passive subdomain and asset reconnaissance using public Certificate Transparency logs (crt.sh) without sending packets to the target server. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Target root domain to passively enumerate (e.g. 'example.com').",
                },
                "max_subdomains": {
                    "type": "integer",
                    "description": "Maximum number of unique subdomains to return (default: 30).",
                    "default": 30,
                },
            },
            "required": ["domain"],
        },
    },
    {
        "name": "security_header_audit",
        "description": "Connect to an HTTP/HTTPS endpoint and audit security response headers (CSP, HSTS, X-Frame-Options, CORS, Cookie flags) against OWASP best practices. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The HTTP or HTTPS URL to audit (e.g. 'http://localhost:2026' or 'https://example.com').",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "security_code_audit",
        "description": "Run Static Application Security Testing (SAST) on local workspace source files to detect hardcoded secrets/API keys, SQL injection, command execution, path traversal, and insecure deserialization. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative or absolute file or directory path within workspace to scan (e.g. 'backend' or 'backend/main.py').",
                },
                "scan_type": {
                    "type": "string",
                    "enum": ["all", "secrets", "sqli", "command_injection", "path_traversal"],
                    "description": "Type of vulnerability patterns to look for (default: 'all').",
                    "default": "all",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "security_port_scan",
        "description": "Perform scoped TCP port & service detection on in-scope target hosts. (Risk: Medium / Requires Operator Permission Confirmation)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target IP address or hostname to scan (must be within allowed security scope).",
                },
                "port_range": {
                    "type": "string",
                    "description": "Port range to check (e.g. 'top20', 'common', '80,443,8080,2026,2027', or '1-1000'). Default: 'top20'.",
                    "default": "top20",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Flag indicating operator has explicitly approved this active network scan.",
                    "default": False,
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "security_report_export",
        "description": "Compile security audit findings into a structured Markdown triage report saved directly into the Notes Vault (backend/data/notes/security-reports/). (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Report title (e.g. 'Security Audit Report: Authentication Service').",
                },
                "target": {
                    "type": "string",
                    "description": "Target host, domain, or repository audited.",
                },
                "findings": {
                    "type": "string",
                    "description": "Detailed markdown findings, descriptions, and mitigation recommendations.",
                },
                "severity": {
                    "type": "string",
                    "enum": ["Critical", "High", "Medium", "Low", "Informational"],
                    "description": "Overall risk severity rating.",
                    "default": "Medium",
                },
            },
            "required": ["title", "target", "findings"],
        },
    },
    {
        "name": "security_ssl_inspect",
        "description": "Inspect SSL/TLS certificate validity, expiration date countdown, Subject Alternative Names (SANs), cipher suites, and protocol version for an HTTPS/TLS service. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target hostname or domain to inspect (e.g. 'google.com' or 'localhost').",
                },
                "port": {
                    "type": "integer",
                    "description": "Target TLS port (default: 443).",
                    "default": 443,
                },
            },
            "required": ["host"],
        },
    },
    {
        "name": "security_dns_recon",
        "description": "Enumerate DNS records (A, AAAA, MX, TXT, NS, CNAME) and audit email security posture (SPF, DMARC, DKIM policies) for a target domain. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Target domain to inspect (e.g. 'example.com').",
                },
            },
            "required": ["domain"],
        },
    },
    {
        "name": "security_whois_lookup",
        "description": "Query domain registrar, creation/expiration dates, ASN, and organization ownership via standard RDAP / WHOIS directory. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Target domain or IP address (e.g. 'github.com' or '8.8.8.8').",
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "security_network_diagnostic",
        "description": "Run network latency, round-trip TCP ping, and connectivity diagnostics against target host or service. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Target hostname or IP address.",
                },
                "port": {
                    "type": "integer",
                    "description": "Target port (default: 443).",
                    "default": 443,
                },
                "count": {
                    "type": "integer",
                    "description": "Number of latency probe rounds to measure (default: 4).",
                    "default": 4,
                },
            },
            "required": ["host"],
        },
    },
    {
        "name": "security_vulnerability_scan",
        "description": "Perform comprehensive DAST web vulnerability audit (sensitive file exposure, SQL injection error reflection, reflected XSS, open redirects). (Risk: Low / Safe Auto-Run on allowlisted targets)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_url": {
                    "type": "string",
                    "description": "Target base URL or endpoint to scan (e.g. 'http://localhost:2026' or 'https://example.com').",
                },
            },
            "required": ["target_url"],
        },
    },
    {
        "name": "lab_decode_payload",
        "description": "Multi-format payload decoder and auto-detector for CTF and cybersecurity labs. Decodes Base64, Hex/ASCII, URL, JWT tokens (header & payload claims), HTML entities, Rot13, and binary strings. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "payload": {
                    "type": "string",
                    "description": "The encoded string, hash, or token to inspect and decode.",
                },
            },
            "required": ["payload"],
        },
    },
    {
        "name": "lab_identify_hash",
        "description": "Intelligent cryptographic hash identifier with Hashcat modes and John the Ripper formats for CTF challenges and authorized lab password audits. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hash_str": {
                    "type": "string",
                    "description": "The hash digest to identify (e.g. MD5, SHA-256, NTLM, bcrypt, Argon2, Unix shadow).",
                },
            },
            "required": ["hash_str"],
        },
    },
    {
        "name": "lab_cve_explainer",
        "description": "Educational cybersecurity vulnerability and CVE mentor. Explains root causes, underlying mechanics, and defensive remediations without spoiling lab challenge flags. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "CVE ID or vulnerability class (e.g. 'CVE-2021-44228', 'SSRF', 'Insecure Deserialization', 'LFI').",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "lab_dossier_manager",
        "description": "Automated CTF & Cybersecurity Lab Dossier manager. Start sessions, log findings, and export comprehensive Markdown walkthrough reports to Notes Vault. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "log", "export", "status"],
                    "description": "Action to perform ('start', 'log', 'export', 'status').",
                },
                "machine_name": {
                    "type": "string",
                    "description": "Lab target name (e.g. 'HTB-Sau', 'THM-RootMe').",
                },
                "target_ip": {
                    "type": "string",
                    "description": "Target IP address of the machine.",
                },
                "milestone": {
                    "type": "string",
                    "enum": ["recon", "enumeration", "foothold", "privesc", "notes"],
                    "description": "Lab phase/milestone for this entry.",
                    "default": "enumeration",
                },
                "note": {
                    "type": "string",
                    "description": "Finding, observation, or technique description.",
                },
                "command_used": {
                    "type": "string",
                    "description": "Terminal command executed in lab.",
                },
                "output_snippet": {
                    "type": "string",
                    "description": "Key terminal output or response snippet.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "lab_vpn_status",
        "description": "Check whether an active OpenVPN tunnel (tun0 interface) is connected to Hack The Box or TryHackMe labs. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "lab_env_check",
        "description": "Audit installed security tools (nmap, gobuster, hydra, sqlmap, openvpn, proot-distro) and SecLists wordlists in the Termux environment. (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "lab_command_helper",
        "description": "Synthesize compliant non-root commands tailored for Android Termux (e.g. forcing TCP connect scan '-sT' and local SecLists paths). (Risk: Low / Safe Auto-Run)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool": {
                    "type": "string",
                    "description": "Tool to generate command for (e.g. 'nmap', 'gobuster', 'whatweb', 'hydra').",
                },
                "target": {
                    "type": "string",
                    "description": "Target hostname or IP address.",
                },
                "wordlist": {
                    "type": "string",
                    "description": "Optional custom wordlist path.",
                },
                "extra_args": {
                    "type": "string",
                    "description": "Optional additional command flags.",
                },
            },
            "required": ["tool", "target"],
        },
    },
]


def _is_target_in_scope(target: str) -> bool:
    """Verify if a target hostname or IP address is allowed by the security policy."""
    t_clean = target.strip().lower()
    if not t_clean:
        return False

    # Strip port or scheme if present
    if "://" in t_clean:
        t_clean = urllib.parse.urlparse(t_clean).netloc.split(":")[0]
    elif ":" in t_clean and not t_clean.startswith("["):
        t_clean = t_clean.split(":")[0]

    for allowed in ALLOWED_TARGETS:
        if allowed == "*" or allowed == "all":
            return True
        if allowed == t_clean:
            return True
        if allowed.startswith("*.") and t_clean.endswith(allowed[1:]):
            return True
        if t_clean.endswith("." + allowed):
            return True

        # Check CIDR / IP range
        try:
            target_ip = ipaddress.ip_address(t_clean)
            if "/" in allowed:
                net = ipaddress.ip_network(allowed, strict=False)
                if target_ip in net:
                    return True
            elif ipaddress.ip_address(allowed) == target_ip:
                return True
        except ValueError:
            pass

    return False


# --------------------------------------------------------------------------- #
# Tool Handlers
# --------------------------------------------------------------------------- #

def handle_cve_search(args: dict[str, Any]) -> str:
    """Search for known CVEs and public vulnerability advisories."""
    query = str(args.get("query", "")).strip()
    if not query:
        return "Error: query parameter is required."
    
    # Strip any leading hyphens to prevent CLI option injection
    query = re.sub(r"^-+", "", query).strip()
    if not query:
        return "Error: query parameter is invalid."

    max_res = min(20, max(1, int(args.get("max_results", 8))))
    results = []

    # 1. Try searchsploit CLI if available
    try:
        proc = subprocess.run(
            ["searchsploit", "--json", "--", query],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            raw_items = data.get("RESULTS_EXPLOIT", []) + data.get("RESULTS_PAPER", [])
            for item in raw_items[:max_res]:
                title = item.get("Title", "Unknown advisory")
                edb = item.get("EDB-ID", "")
                t_type = item.get("Type", "remote")
                platform = item.get("Platform", "multiple")
                cve_match = re.search(r"CVE-\d{4}-\d{4,7}", title, re.IGNORECASE)
                cve_id = cve_match.group(0).upper() if cve_match else f"EDB-{edb}" if edb else "Advisory"
                results.append({
                    "cve": cve_id,
                    "title": title,
                    "type": t_type,
                    "platform": platform,
                    "source": "Exploit-DB",
                    "url": f"https://www.exploit-db.com/exploits/{edb}" if edb else "",
                })
    except Exception:
        pass

    # 2. Online NVD / Advisory search fallback via DuckDuckGo / NIST CVE search
    if len(results) < max_res:
        try:
            from duckduckgo_mcp_server import perform_ddg_search
            cve_query = f"{query} CVE vulnerability advisory mitigation NIST"
            web_hits = perform_ddg_search(cve_query, max_results=max_res - len(results) + 2)
            for hit in web_hits:
                t = hit.get("title", "")
                u = hit.get("url", "")
                s = hit.get("snippet", "")
                cve_match = re.search(r"CVE-\d{4}-\d{4,7}", t + " " + s, re.IGNORECASE)
                cve_id = cve_match.group(0).upper() if cve_match else "Advisory"
                results.append({
                    "cve": cve_id,
                    "title": t,
                    "type": "Web Advisory",
                    "platform": "General",
                    "source": hit.get("domain", "NVD / Security Feed"),
                    "url": u,
                    "snippet": s[:200],
                })
        except Exception:
            pass

    if not results:
        return f"No public CVE advisories found for '{query}'."

    out = [f"🛡️ Security CVE & Vulnerability Advisories for: `{query}` ({len(results)} items found)\n"]
    for i, r in enumerate(results[:max_res], 1):
        out.append(f"{i}. **[{r['cve']}]** {r['title']}")
        out.append(f"   - **Source / Type:** {r.get('source')} ({r.get('type')}) | **Platform:** {r.get('platform')}")
        if r.get("url"):
            out.append(f"   - **Reference Link:** {r['url']}")
        if r.get("snippet"):
            out.append(f"   - **Summary:** {r['snippet']}")
        out.append("")

    return "\n".join(out).strip()


def handle_passive_recon(args: dict[str, Any]) -> str:
    """Passively query Certificate Transparency logs for subdomains."""
    domain = str(args.get("domain", "")).strip().lower()
    if not domain:
        return "Error: domain parameter is required."
    max_subs = min(100, max(5, int(args.get("max_subdomains", 30))))

    # Clean domain
    domain = re.sub(r"^https?://", "", domain).split("/")[0].split(":")[0]

    subdomains = set()
    try:
        url = f"https://crt.sh/?q=%.{urllib.parse.quote(domain)}&output=json"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                entries = json.loads(raw)
                for entry in entries:
                    name_value = entry.get("name_value", "")
                    for sub in name_value.split("\n"):
                        sub = sub.strip().lower()
                        if sub and domain in sub and not sub.startswith("*."):
                            subdomains.add(sub)
            except Exception:
                pass
    except Exception as exc:
        return f"Error performing passive reconnaissance on '{domain}': {exc}"

    if not subdomains:
        return f"No passive subdomains discovered in public certificate transparency logs for: '{domain}'"

    sorted_subs = sorted(list(subdomains))[:max_subs]
    out = [
        f"🌐 Passive Reconnaissance Results for: `{domain}`",
        f"📌 Total Unique Subdomains Discovered: **{len(subdomains)}** (showing top {len(sorted_subs)})\n",
        "| Index | Discovered Subdomain | In-Scope Status |",
        "|---|---|---|",
    ]
    for i, sub in enumerate(sorted_subs, 1):
        in_scope = "✅ In-Scope" if _is_target_in_scope(sub) else "⚠️ Verify Scope"
        out.append(f"| {i} | `{sub}` | {in_scope} |")

    return "\n".join(out)


def handle_header_audit(args: dict[str, Any]) -> str:
    """Audit HTTP security headers and cookie security flags."""
    raw_url = str(args.get("url", "")).strip()
    if not raw_url:
        return "Error: url parameter is required."

    # SSRF Protection: Block cloud instance metadata addresses
    blocked_patterns = ["169.254.169.254", "metadata.google.internal", "100.100.100.200", "fd00:ec2::254"]
    if any(b in raw_url.lower() for b in blocked_patterns):
        return "🚫 [PERMISSION DENIED - SSRF]: Probing cloud instance metadata endpoints is strictly blocked."

    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        raw_url = "http://" + raw_url

    try:
        parsed = urllib.parse.urlparse(raw_url)
        req = urllib.request.Request(raw_url, headers={"User-Agent": USER_AGENT})
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, timeout=8, context=ctx) as response:
            headers = {k.lower(): v for k, v in response.headers.items()}
            status_code = response.status
    except Exception as exc:
        return f"Error connecting to '{raw_url}' for header audit: {exc}"

    # Evaluate essential security headers
    checks = [
        {
            "name": "Strict-Transport-Security (HSTS)",
            "header": "strict-transport-security",
            "expected": "max-age=31536000; includeSubDomains",
            "present": "strict-transport-security" in headers,
            "value": headers.get("strict-transport-security", "Missing"),
            "severity": "High" if raw_url.startswith("https") else "Informational",
            "desc": "Enforces secure HTTPS connections and prevents SSL stripping.",
        },
        {
            "name": "Content-Security-Policy (CSP)",
            "header": "content-security-policy",
            "expected": "default-src 'self' ...",
            "present": "content-security-policy" in headers,
            "value": headers.get("content-security-policy", "Missing")[:80] + ("..." if len(headers.get("content-security-policy", "")) > 80 else ""),
            "severity": "High",
            "desc": "Prevents Cross-Site Scripting (XSS) and data injection attacks.",
        },
        {
            "name": "X-Frame-Options (Clickjacking)",
            "header": "x-frame-options",
            "expected": "DENY or SAMEORIGIN",
            "present": "x-frame-options" in headers,
            "value": headers.get("x-frame-options", "Missing"),
            "severity": "Medium",
            "desc": "Protects against UI redress / clickjacking attacks.",
        },
        {
            "name": "X-Content-Type-Options",
            "header": "x-content-type-options",
            "expected": "nosniff",
            "present": "x-content-type-options" in headers and headers.get("x-content-type-options", "").lower() == "nosniff",
            "value": headers.get("x-content-type-options", "Missing"),
            "severity": "Low",
            "desc": "Prevents MIME-type confusion sniffing.",
        },
        {
            "name": "Referrer-Policy",
            "header": "referrer-policy",
            "expected": "strict-origin-when-cross-origin or no-referrer",
            "present": "referrer-policy" in headers,
            "value": headers.get("referrer-policy", "Missing"),
            "severity": "Low",
            "desc": "Controls leakage of referrer information across origins.",
        },
        {
            "name": "Permissions-Policy",
            "header": "permissions-policy",
            "expected": "camera=(), microphone=(), geolocation=()",
            "present": "permissions-policy" in headers,
            "value": headers.get("permissions-policy", "Missing")[:60],
            "severity": "Low",
            "desc": "Restricts browser feature access.",
        },
    ]

    passed = sum(1 for c in checks if c["present"])
    score = int((passed / len(checks)) * 100)
    grade = "A+" if score >= 90 else "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "F"

    out = [
        f"🔒 HTTP Security Header Audit for: `{raw_url}`",
        f"📌 HTTP Status: `{status_code}` | Security Score: **{score}% (Grade: {grade})**",
        f"🛡️ Passed: **{passed}/{len(checks)}** security controls\n",
        "| Header / Security Control | Status | Severity | Actual Value | Impact |",
        "|---|---|---|---|---|",
    ]

    for c in checks:
        status_icon = "✅ PASS" if c["present"] else "❌ MISSING"
        out.append(f"| **{c['name']}** | {status_icon} | `{c['severity']}` | `{c['value']}` | {c['desc']} |")

    # Check CORS
    cors_origin = headers.get("access-control-allow-origin")
    if cors_origin:
        out.append("\n⚠️ **CORS Configuration Detected:**")
        out.append(f"- `Access-Control-Allow-Origin`: `{cors_origin}`" + (" (⚠️ Wildcard '*' allows any domain!)" if cors_origin == "*" else ""))

    return "\n".join(out)


def handle_code_audit(args: dict[str, Any]) -> str:
    """Static Application Security Testing (SAST) for source files."""
    path_str = str(args.get("path", "")).strip()
    if not path_str:
        return "Error: path parameter is required."

    target_path = Path(path_str).expanduser()
    if not target_path.is_absolute():
        # Look in workspace
        workspace = Path(os.environ.get("WORKSPACE_ROOT", "/home/shabari/projects/AI assistant")).resolve()
        target_path = (workspace / target_path).resolve()

    if not target_path.exists():
        return f"Error: Target path '{target_path}' does not exist."

    # Patterns for SAST inspection
    patterns = [
        (
            "Hardcoded API Key / Private Token",
            r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|private[_-]?key|aws_access_key_id|bearer\s+token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
            "High",
            "CWE-798: Use of Hard-coded Credentials. Store secrets in environment variables or vault.",
        ),
        (
            "SQL Injection (String Concatenation)",
            r"(?i)(execute|cursor\.execute|query)\s*\(\s*(f['\"].*?SELECT|f['\"].*?INSERT|['\"].*?SELECT.*?\+|.*?%\s*\(.*?\))",
            "Critical",
            "CWE-89: SQL Injection. Use parameterized prepared statements instead of string formatting.",
        ),
        (
            "Command Injection (Shell Subprocess)",
            r"(?i)(os\.system|subprocess\.(Popen|run|call))\s*\(\s*(f['\"].*?|.*?\+.*?|.*?\%.*?),\s*shell\s*=\s*True",
            "Critical",
            "CWE-78: OS Command Injection. Avoid shell=True and pass argument lists directly.",
        ),
        (
            "Insecure Deserialization",
            r"(?i)(pickle\.loads|yaml\.load\s*\([^,)]*\)|marshal\.loads)",
            "High",
            "CWE-502: Deserialization of Untrusted Data. Use safe loaders (e.g. yaml.safe_load) or JSON.",
        ),
        (
            "Insecure Direct File Open (Path Traversal Risk)",
            r"(?i)open\s*\(\s*(f['\"].*?\{.*?\}|.*?\+.*?)\s*,\s*['\"][rwab+]+['\"]",
            "Medium",
            "CWE-22: Path Traversal. Validate and resolve canonical paths using resolve() or a boundary check.",
        ),
    ]

    files_to_scan: list[Path] = []
    if target_path.is_file():
        files_to_scan.append(target_path)
    else:
        for ext in ("*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.go", "*.java", "*.php"):
            files_to_scan.extend(target_path.glob(f"**/{ext}"))

    # Limit to 60 files to avoid unbounded scan
    files_to_scan = [f for f in files_to_scan if "node_modules" not in str(f) and ".venv" not in str(f)][:60]

    findings = []
    for file_p in files_to_scan:
        try:
            content = file_p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            for line_idx, line in enumerate(lines, 1):
                if len(line.strip()) == 0 or line.strip().startswith("#") or line.strip().startswith("//"):
                    continue
                for rule_name, regex, severity, mitigation in patterns:
                    if re.search(regex, line):
                        # Mask any secret in snippet
                        snippet = line.strip()[:100]
                        if "api" in rule_name.lower() or "secret" in rule_name.lower():
                            snippet = re.sub(r"['\"][A-Za-z0-9_\-]{16,}['\"]", "'[REDACTED_SECRET]'", snippet)
                        findings.append({
                            "file": str(file_p.name),
                            "line": line_idx,
                            "rule": rule_name,
                            "severity": severity,
                            "snippet": snippet,
                            "mitigation": mitigation,
                        })
        except Exception:
            pass

    if not findings:
        return f"✅ SAST Code Audit Completed: Clean. Scanned {len(files_to_scan)} files across '{target_path.name}'. Zero high-risk vulnerability patterns detected."

    out = [
        f"🚨 SAST Code Security Audit Results for: `{target_path.name}`",
        f"📌 Scanned Files: **{len(files_to_scan)}** | Vulnerability Patterns Detected: **{len(findings)}**\n",
        "| Severity | File:Line | Vulnerability Type | Code Excerpt | Remediation Recommendation |",
        "|---|---|---|---|---|",
    ]

    for f in findings[:25]:
        out.append(f"| `{f['severity']}` | `{f['file']}:{f['line']}` | **{f['rule']}** | `{f['snippet']}` | {f['mitigation']} |")

    return "\n".join(out)


def handle_port_scan(args: dict[str, Any]) -> str:
    """Scoped port & service inspection with permission validation."""
    target = str(args.get("target", "")).strip()
    if not target:
        return "Error: target parameter is required."

    # Validate target character set and prevent CLI option injection (starts with '-')
    if not re.match(r"^[a-zA-Z0-9\.\:\-]+$", target) or target.startswith("-"):
        return f"Error: Invalid target format '{target}'. Hostnames or IP addresses only."

    # Validate Scope Boundary
    if not _is_target_in_scope(target):
        return (
            f"🚫 [PERMISSION DENIED - OUT OF SCOPE]: Target '{target}' is not in the allowed security scope "
            f"({RAW_ALLOWLIST}). To scan this target, add it to SECURITY_TARGET_ALLOWLIST in configuration."
        )

    confirmed = bool(args.get("confirmed", False))
    if not confirmed:
        # Require confirmation
        return (
            f"⚠️ [CONFIRMATION REQUIRED]: Active network port scan requested for target `{target}`. "
            f"This is an active Tier-2 security tool. Operator permission is required to proceed. "
            f"(Please ask the user to confirm via voice or UI before setting confirmed=True)."
        )

    port_spec = str(args.get("port_range", "top20")).strip().lower()

    # Common port presets
    ports_map = {
        "top20": [21, 22, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 2026, 2027, 3000, 3306, 5432, 8000, 8080, 8443],
        "web": [80, 443, 8000, 8080, 8443, 8888, 3000, 5000, 2026, 2027],
        "common": [21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445, 993, 995, 1723, 3306, 3389, 5432, 5900, 8080],
    }

    try:
        if port_spec in ports_map:
            target_ports = ports_map[port_spec]
        elif "," in port_spec:
            target_ports = [int(p.strip()) for p in port_spec.split(",") if p.strip().isdigit() and 1 <= int(p.strip()) <= 65535]
            if not target_ports:
                target_ports = ports_map["top20"]
        elif "-" in port_spec:
            start_p, end_p = port_spec.split("-", 1)
            if start_p.strip().isdigit() and end_p.strip().isdigit():
                s_val = int(start_p.strip())
                e_val = int(end_p.strip())
                target_ports = list(range(max(1, s_val), min(65535, min(e_val + 1, s_val + 200))))
            else:
                target_ports = ports_map["top20"]
        else:
            target_ports = ports_map["top20"]
    except Exception:
        target_ports = ports_map["top20"]

    # Try Nmap if available (with '--' separator to guarantee target is treated positionally)
    try:
        port_list_str = ",".join(str(p) for p in target_ports[:30])
        proc = subprocess.run(
            ["nmap", "-sV", "-T4", "-p", port_list_str, "--open", "--", target],
            capture_output=True,
            text=True,
            timeout=25,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return f"🛡️ Nmap Scoped Port Scan Report for `{target}`:\n\n```text\n{proc.stdout.strip()}\n```"
    except Exception:
        pass

    # High-speed native Python socket scanner fallback
    open_ports = []
    for port in target_ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.35)
        try:
            res = s.connect_ex((target, port))
            if res == 0:
                # Try banner grab
                banner = ""
                try:
                    s.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
                    banner = s.recv(128).decode("utf-8", errors="replace").splitlines()[0]
                except Exception:
                    pass
                service_name = socket.getservbyport(port, "tcp") if port < 1024 else "custom"
                open_ports.append({
                    "port": port,
                    "service": service_name,
                    "banner": banner,
                })
        except Exception:
            pass
        finally:
            s.close()

    if not open_ports:
        return f"🛡️ Port Scan for `{target}`: Checked {len(target_ports)} ports. Zero open ports detected (Host is closed or filtered)."

    out = [
        f"🛡️ Scoped Port & Service Scan for: `{target}`",
        f"📌 Checked: **{len(target_ports)} ports** | Open Services Detected: **{len(open_ports)}**\n",
        "| Port | Service | Status | Banner / Service Info |",
        "|---|---|---|---|",
    ]
    for op in open_ports:
        out.append(f"| `{op['port']}/TCP` | **{op['service']}** | 🟢 OPEN | `{op['banner'] or 'Responsive socket'}` |")

    return "\n".join(out)


def handle_report_export(args: dict[str, Any]) -> str:
    """Export security audit findings into the Markdown Notes Vault."""
    title = str(args.get("title", "Security Audit Report")).strip()
    target = str(args.get("target", "Target System")).strip()
    findings = str(args.get("findings", "")).strip()
    severity = str(args.get("severity", "Medium")).strip()

    if not findings:
        return "Error: findings parameter is required."

    slug = re.sub(r"[^\w\s-]", "", title.lower()).strip().replace(" ", "_") or "security_audit_report"
    rep_dir = NOTES_VAULT / "security-reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    report_file = rep_dir / f"{slug}.md"

    frontmatter = {
        "id": f"sec-{int(time.time() * 1000) % 1000000}",
        "title": title,
        "category": "security-reports",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target": target,
        "severity": severity,
        "tags": ["security-audit", "bug-bounty", "triage-report", severity.lower()],
    }

    report_body = f"""# {title}

**Target Scope:** `{target}`  
**Overall Risk Severity:** **{severity.upper()}**  
**Audit Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Auditor:** S.A.R.A. Autonomous Security Engine  

---

## 📌 Executive Summary
This document summarizes the technical findings, vulnerabilities, and hardening recommendations identified during the security assessment of **{target}**.

---

## 🔍 Detailed Security Findings & Evidence

{findings}

---

## 🛠️ Remediation & Patching Roadmap
1. Address all **Critical** and **High** severity vulnerabilities immediately by implementing boundary parameterization and input sanitization.
2. Enforce strict HTTP security response headers (`CSP`, `HSTS`, `X-Frame-Options`).
3. Rotate any sensitive keys or credentials detected in source repositories.
"""

    from notes_mcp_server import _write_markdown_file, _rebuild_index
    _write_markdown_file(report_file, frontmatter, report_body)
    _rebuild_index()

    return f"✅ Security report successfully generated and saved into Notes Vault: `{report_file.relative_to(DATA_DIR)}`"


def handle_ssl_inspect(args: dict[str, Any]) -> str:
    """Inspect SSL/TLS certificate validity, expiry, SANs, cipher suites, and protocol version."""
    raw_host = str(args.get("host", "")).strip()
    port = int(args.get("port", 443))

    if not raw_host:
        return "Error: host parameter is required."

    # Clean domain
    host = raw_host
    if "://" in host:
        host = urllib.parse.urlparse(host).netloc.split(":")[0]
    elif ":" in host and not host.startswith("["):
        host = host.split(":")[0]

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

        with socket.create_connection((host, port), timeout=6.0) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                tls_version = ssock.version()

                # Extract Subject & Issuer
                subject_dict = dict(x[0] for x in cert.get("subject", ()))
                issuer_dict = dict(x[0] for x in cert.get("issuer", ()))

                cn = subject_dict.get("commonName", host)
                issuer_o = issuer_dict.get("organizationName", issuer_dict.get("commonName", "Unknown Issuer"))

                # Extract SANs
                sans = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
                sans_preview = ", ".join(sans[:6]) + (f" (+{len(sans)-6} more)" if len(sans) > 6 else "")

                # Expiry Calculation
                not_after_str = cert.get("notAfter", "")
                not_before_str = cert.get("notBefore", "")

                try:
                    expiry_time = time.mktime(time.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z"))
                    now = time.time()
                    days_remaining = int((expiry_time - now) / 86400)
                except Exception:
                    days_remaining = 999

                # Status Badge
                if days_remaining < 0:
                    status_badge = "🔴 **EXPIRED**"
                elif days_remaining <= 30:
                    status_badge = f"🟡 **EXPIRING SOON ({days_remaining} days)**"
                else:
                    status_badge = f"🟢 **VALID ({days_remaining} days remaining)**"

                lines = [
                    f"🔒 **SSL/TLS Certificate Inspection: `{host}:{port}`**",
                    f"- **Status:** {status_badge}",
                    f"- **Common Name (CN):** `{cn}`",
                    f"- **Certificate Authority (Issuer):** `{issuer_o}`",
                    f"- **Valid From:** `{not_before_str}`",
                    f"- **Expires On:** `{not_after_str}`",
                    f"- **SAN Domains ({len(sans)}):** `{sans_preview or 'None'}`",
                    f"- **Negotiated Protocol:** `{tls_version}` ({'Modern' if tls_version in ('TLSv1.3', 'TLSv1.2') else 'Legacy/Insecure'})",
                    f"- **Active Cipher Suite:** `{cipher[0] if cipher else 'Unknown'}` ({cipher[2] if cipher else 0} bits)",
                ]

                # Security Assessment
                if days_remaining <= 14:
                    lines.append("\n⚠️ **Security Warning:** Certificate expires in less than 2 weeks. Immediate renewal recommended.")
                if tls_version not in ("TLSv1.2", "TLSv1.3"):
                    lines.append("\n🚨 **Critical Security Risk:** Obsolete TLS protocol detected. Upgrade server to TLS 1.3.")

                return "\n".join(lines)

    except ssl.SSLCertVerificationError as exc:
        return (
            f"🚨 **SSL Certificate Verification FAILED for `{host}:{port}`:**\n"
            f"- **Error:** `{exc.verify_message or exc}`\n"
            f"- **Risk:** Potential Self-Signed Certificate, Expired Chain, or Man-in-the-Middle (MitM) condition."
        )
    except Exception as exc:
        return f"Error connecting to `{host}:{port}` over TLS: {exc}"


def handle_dns_recon(args: dict[str, Any]) -> str:
    """Enumerate DNS records (A, AAAA, MX, TXT, NS) and audit SPF/DMARC email security."""
    raw_domain = str(args.get("domain", "")).strip().lower()
    if not raw_domain:
        return "Error: domain parameter is required."

    domain = raw_domain
    if "://" in domain:
        domain = urllib.parse.urlparse(domain).netloc.split(":")[0]

    lines = [f"🌐 **DNS & Email Security Reconnaissance: `{domain}`**"]

    # 1. Standard A / AAAA resolution
    try:
        addr_info = socket.getaddrinfo(domain, None)
        ips = sorted(list(set(item[4][0] for item in addr_info if item[4])))
        ipv4 = [ip for ip in ips if ":" not in ip]
        ipv6 = [ip for ip in ips if ":" in ip]

        lines.append(f"- **IPv4 Addresses (A):** `{', '.join(ipv4) if ipv4 else 'None'}`")
        if ipv6:
            lines.append(f"- **IPv6 Addresses (AAAA):** `{', '.join(ipv6)}`")
    except Exception as exc:
        lines.append(f"- **IP Resolution:** Error ({exc})")

    # 2. DNS-over-HTTPS (DoH) for MX, TXT, NS records (Zero 3rd-party dependencies)
    def _query_doh(name: str, record_type: str) -> list[str]:
        url = f"https://cloudflare-dns.com/dns-query?name={name}&type={record_type}"
        req = urllib.request.Request(url, headers={"Accept": "application/dns-json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read().decode())
                answers = data.get("Answer", [])
                return [a.get("data", "").strip('"') for a in answers if "data" in a]
        except Exception:
            return []

    mx_records = _query_doh(domain, "MX")
    if mx_records:
        lines.append(f"- **Mail Exchanges (MX):** `{', '.join(mx_records[:4])}`")

    ns_records = _query_doh(domain, "NS")
    if ns_records:
        lines.append(f"- **Name Servers (NS):** `{', '.join(ns_records[:4])}`")

    txt_records = _query_doh(domain, "TXT")
    spf_record = next((r for r in txt_records if r.lower().startswith("v=spf1")), None)
    dmarc_records = _query_doh(f"_dmarc.{domain}", "TXT")
    dmarc_record = next((r for r in dmarc_records if r.lower().startswith("v=dmarc1")), None)

    # 3. Email Security Audit
    lines.append("\n📧 **Email Spoofing & Phishing Defense Audit:**")
    if spf_record:
        spf_status = "🟢 Enforced" if "-all" in spf_record else ("🟡 SoftFail (~all)" if "~all" in spf_record else "🔴 Permissive (+all)")
        lines.append(f"- **SPF Record:** `{spf_record}` ({spf_status})")
    else:
        lines.append("- **SPF Record:** 🔴 **MISSING** (Vulnerable to email forgery)")

    if dmarc_record:
        policy = "reject" if "p=reject" in dmarc_record else ("quarantine" if "p=quarantine" in dmarc_record else "none (reporting only)")
        dmarc_status = "🟢 Strict Rejection" if policy == "reject" else ("🟡 Quarantine" if policy == "quarantine" else "🟠 Monitoring Only (No active drop)")
        lines.append(f"- **DMARC Policy:** `{dmarc_record}` ({dmarc_status})")
    else:
        lines.append("- **DMARC Policy:** 🔴 **MISSING** (Critical: Domain can be spoofed in executive phishing attacks)")

    return "\n".join(lines)


def handle_whois_lookup(args: dict[str, Any]) -> str:
    """Query domain registrar, ASN, and ownership via standard RDAP directory."""
    raw_target = str(args.get("target", "")).strip().lower()
    if not raw_target:
        return "Error: target parameter is required."

    target = raw_target
    if "://" in target:
        target = urllib.parse.urlparse(target).netloc.split(":")[0]

    # Check if target is IPv4
    is_ip = re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", target)
    endpoint = f"https://rdap.org/ip/{target}" if is_ip else f"https://rdap.org/domain/{target}"

    req = urllib.request.Request(endpoint, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode())

            handle = data.get("handle", "Unknown")
            name = data.get("name", target)
            status_list = data.get("status", [])

            # Extract events (Registration, Expiration)
            events = {e.get("eventAction"): e.get("eventDate", "")[:10] for e in data.get("events", [])}
            created = events.get("registration") or events.get("last changed") or "Unknown"
            expires = events.get("expiration") or "Unknown"

            # Extract registrar / entities
            entities = data.get("entities", [])
            registrar_name = "Unknown Registrar"
            for ent in entities:
                roles = ent.get("roles", [])
                if "registrar" in roles or "registrant" in roles:
                    vcard = ent.get("vcardArray", [])
                    if len(vcard) > 1 and isinstance(vcard[1], list):
                        for prop in vcard[1]:
                            if prop[0] == "fn" and len(prop) > 3:
                                registrar_name = prop[3]
                                break

            # Nameservers
            ns_list = [ns.get("ldhName", "") for ns in data.get("nameservers", []) if "ldhName" in ns]

            lines = [
                f"📋 **WHOIS / RDAP Intelligence: `{target}`**",
                f"- **Entity Handle:** `{handle}`",
                f"- **Organization / Domain Name:** `{name}`",
                f"- **Registrar:** `{registrar_name}`",
                f"- **Registered On:** `{created}`",
                f"- **Expires On:** `{expires}`",
                f"- **Status Flags:** `{', '.join(status_list[:3]) if status_list else 'active'}`",
                f"- **Authoritative Nameservers:** `{', '.join(ns_list[:4]) if ns_list else 'N/A'}`",
            ]
            return "\n".join(lines)
    except urllib.error.HTTPError as exc:
        return f"WHOIS/RDAP query for `{target}` returned HTTP {exc.code} (Record may be private or unassigned)."
    except Exception as exc:
        return f"Error executing WHOIS/RDAP lookup for `{target}`: {exc}"


def handle_network_diagnostic(args: dict[str, Any]) -> str:
    """Run low-latency round-trip TCP ping and connectivity metrics."""
    raw_host = str(args.get("host", "")).strip()
    port = int(args.get("port", 443))
    count = max(1, min(10, int(args.get("count", 4))))

    if not raw_host:
        return "Error: host parameter is required."

    host = raw_host
    if "://" in host:
        host = urllib.parse.urlparse(host).netloc.split(":")[0]

    latencies: list[float] = []
    successes = 0

    for _ in range(count):
        t_start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=3.0):
                elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                latencies.append(elapsed_ms)
                successes += 1
        except Exception:
            pass
        time.sleep(0.15)

    if not latencies:
        return f"🔴 **Network Diagnostic Failed:** Unable to establish TCP connection to `{host}:{port}` (Host unreachable or port closed)."

    min_l = min(latencies)
    avg_l = sum(latencies) / len(latencies)
    max_l = max(latencies)
    jitter = max_l - min_l

    loss_pct = int(((count - successes) / count) * 100)

    # Health Rating
    if avg_l < 50:
        health = "🟢 Excellent (Ultra-low latency)"
    elif avg_l < 150:
        health = "🟢 Good"
    elif avg_l < 300:
        health = "🟡 Moderate Latency"
    else:
        health = "🔴 High Latency / Network Jitter"

    lines = [
        f"⚡ **Network Connectivity Diagnostic: `{host}:{port}`**",
        f"- **Packets Probed:** `{count}` | **Success:** `{successes}/{count}` (`{100 - loss_pct}% reachable`)",
        f"- **Latency (Min / Avg / Max):** `{min_l:.1f}ms` / `{avg_l:.1f}ms` / `{max_l:.1f}ms`",
        f"- **Jitter Variance:** `{jitter:.1f}ms`",
        f"- **Network Health Rating:** {health}",
    ]
    return "\n".join(lines)


def handle_call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name", "")
    args = params.get("arguments", {})

    if name == "security_cve_search":
        out = handle_cve_search(args)
    elif name == "security_passive_recon":
        out = handle_passive_recon(args)
    elif name == "security_header_audit":
        out = handle_header_audit(args)
    elif name == "security_code_audit":
        out = handle_code_audit(args)
    elif name == "security_port_scan":
        out = handle_port_scan(args)
    elif name == "security_report_export":
        out = handle_report_export(args)
    elif name == "security_ssl_inspect":
        out = handle_ssl_inspect(args)
    elif name == "security_dns_recon":
        out = handle_dns_recon(args)
    elif name == "security_whois_lookup":
        out = handle_whois_lookup(args)
    elif name == "security_network_diagnostic":
        out = handle_network_diagnostic(args)
    elif name == "security_vulnerability_scan":
        from web_security_scanner import run_full_vulnerability_scan
        out = run_full_vulnerability_scan(str(args.get("target_url", "")))
    elif name == "lab_decode_payload":
        from lab_copilot import decode_payload
        out = decode_payload(str(args.get("payload", "")))
    elif name == "lab_identify_hash":
        from lab_copilot import identify_hash
        out = identify_hash(str(args.get("hash_str", "")))
    elif name == "lab_cve_explainer":
        from lab_copilot import explain_cve_mechanics
        out = explain_cve_mechanics(str(args.get("query", "")))
    elif name == "lab_dossier_manager":
        from lab_copilot import get_dossier_manager
        mgr = get_dossier_manager()
        act = str(args.get("action", "status")).lower()
        if act == "start":
            out = mgr.start_session(
                machine_name=str(args.get("machine_name", "Unknown-Target")),
                target_ip=str(args.get("target_ip", "127.0.0.1")),
                platform=str(args.get("platform", "Hack The Box")),
            )
        elif act == "log":
            out = mgr.log_finding(
                note=str(args.get("note", "")),
                milestone=str(args.get("milestone", "enumeration")),
                command_used=str(args.get("command_used", "")),
                output_snippet=str(args.get("output_snippet", "")),
            )
        elif act == "export":
            out = mgr.export_dossier(
                machine_name=str(args.get("machine_name", "")),
                target_ip=str(args.get("target_ip", "")),
            )
        else:
            out = mgr.get_status()
    elif name == "lab_vpn_status":
        from lab_copilot import check_lab_vpn_status
        out = check_lab_vpn_status()
    elif name == "lab_env_check":
        from lab_copilot import audit_termux_toolchain
        out = audit_termux_toolchain()
    elif name == "lab_command_helper":
        from lab_copilot import generate_rootless_command
        out = generate_rootless_command(
            tool=str(args.get("tool", "nmap")),
            target=str(args.get("target", "127.0.0.1")),
            wordlist=str(args.get("wordlist", "")),
            extra_args=str(args.get("extra_args", "")),
        )
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
                        "name": "security-audit-mcp-server",
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
