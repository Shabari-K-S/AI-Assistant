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

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (S.A.R.A. Security Auditor)"

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
    max_res = min(20, max(1, int(args.get("max_results", 8))))

    results = []

    # 1. Try searchsploit CLI if available
    try:
        proc = subprocess.run(
            ["searchsploit", "--json", query],
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

    if port_spec in ports_map:
        target_ports = ports_map[port_spec]
    elif "," in port_spec:
        target_ports = [int(p.strip()) for p in port_spec.split(",") if p.strip().isdigit()]
    elif "-" in port_spec:
        start_p, end_p = port_spec.split("-", 1)
        target_ports = list(range(int(start_p), min(int(end_p) + 1, int(start_p) + 200)))
    else:
        target_ports = ports_map["top20"]

    # Try Nmap if available
    try:
        port_list_str = ",".join(str(p) for p in target_ports[:30])
        proc = subprocess.run(
            ["nmap", "-sV", "-T4", "-p", port_list_str, "--open", target],
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
