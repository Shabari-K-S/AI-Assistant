---
name: security_dast_audit
description: Autonomous DAST security auditing, SQLi/XSS testing, and triage report generation.
category: security
triggers: ["/recon", "security_scan", "dast", "vulnerability"]
tools: ["web_security_scanner", "security_compile_triage_report", "ssl_inspect"]
created_at: 2026-08-22 08:19:55
is_builtin: true
---

# Dynamic Security (DAST) Assessment Skill

## 🛡️ Audit Methodology
1. Probe for sensitive configuration exposures (`.env`, `.git/HEAD`, `backup.sql`).
2. Test parameters for SQL syntax reflection and benign XSS probe reflection.
3. Inspect SSL/TLS certificate validity and encryption cipher suites.
4. Compile findings into a structured triage report saved into Notes Vault (`notes/security-reports/`).
