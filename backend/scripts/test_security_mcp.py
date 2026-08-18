#!/usr/bin/env python3
"""Test script for S.A.R.A. Security & Bug Bounty MCP Server."""

import json
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from security_mcp_server import (
    handle_cve_search,
    handle_passive_recon,
    handle_header_audit,
    handle_code_audit,
    handle_port_scan,
    handle_report_export,
    _is_target_in_scope,
)


def test_security_mcp():
    print("=" * 70)
    print("🛡️ S.A.R.A. CYBERSECURITY & BUG BOUNTY MCP SERVER TEST SUITE")
    print("=" * 70)

    # 1. Test Target Scope Validation
    print("\n1. Testing Scope Boundary Validation...")
    assert _is_target_in_scope("127.0.0.1") is True, "127.0.0.1 should be in scope"
    assert _is_target_in_scope("localhost") is True, "localhost should be in scope"
    assert _is_target_in_scope("192.168.1.50") is True, "192.168.1.50 should be in scope"
    assert _is_target_in_scope("unauthorized-victim.com") is False, "unauthorized-victim.com should be OUT of scope"
    print("   ✅ In-scope targets allowed, out-of-scope targets blocked successfully.")

    # 2. Test CVE & Advisory Search (Tier 1: Auto-Run)
    print("\n2. Testing CVE & Advisory Search (searchsploit / NVD fallback)...")
    cve_res = handle_cve_search({"query": "Apache 2.4.49", "max_results": 4})
    print(f"   CVE Search Output Length: {len(cve_res)} characters")
    assert "CVE" in cve_res or "Advisories" in cve_res
    print("   ✅ CVE lookup returned structured advisories.")

    # 3. Test HTTP Header Audit (Tier 1: Auto-Run)
    print("\n3. Testing HTTP Security Header Auditor...")
    header_res = handle_header_audit({"url": "https://example.com"})
    print(f"   Header Audit Output Length: {len(header_res)} characters")
    assert "HTTP Security Header Audit" in header_res or "Security Header" in header_res
    print("   ✅ Header auditor evaluated security controls.")

    # 4. Test SAST Code Audit (Tier 1: Auto-Run)
    print("\n4. Testing SAST Code Security Audit...")
    code_res = handle_code_audit({"path": "backend/duckduckgo_mcp_server.py"})
    print(f"   SAST Output: {code_res[:160]}...")
    assert "SAST" in code_res
    print("   ✅ SAST code inspection ran successfully.")

    # 5. Test Active Port Scan Confirmation Gate (Tier 2: Confirmation Required)
    print("\n5. Testing Port Scan Permission Gate...")
    unconfirmed_scan = handle_port_scan({"target": "127.0.0.1", "confirmed": False})
    assert "CONFIRMATION REQUIRED" in unconfirmed_scan
    print("   ✅ Unconfirmed scan correctly halted with [CONFIRMATION REQUIRED].")

    out_of_scope_scan = handle_port_scan({"target": "malicious-unauthorized.com", "confirmed": True})
    assert "PERMISSION DENIED - OUT OF SCOPE" in out_of_scope_scan
    print("   ✅ Out-of-scope scan blocked even when confirmed=True.")

    confirmed_scan = handle_port_scan({"target": "127.0.0.1", "port_range": "2026,2027,80,443", "confirmed": True})
    assert "Port" in confirmed_scan or "Nmap" in confirmed_scan
    print("   ✅ Confirmed in-scope scan executed successfully.")

    # 6. Test Security Report Export to Notes Vault (Tier 1: Auto-Run)
    print("\n6. Testing Security Report Export to Notes Vault...")
    rep_res = handle_report_export({
        "title": "Automated Security Assessment Test",
        "target": "127.0.0.1",
        "findings": "- **Finding 1**: Missing HSTS header on local staging port\n- **Finding 2**: Clean code baseline",
        "severity": "Low",
    })
    print(f"   Export result: {rep_res}")
    assert "successfully generated and saved into Notes Vault" in rep_res
    print("   ✅ Security triage report generated and saved into Notes Vault.")

    print("\n" + "=" * 70)
    print("✅ ALL CYBERSECURITY MCP SERVER TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    test_security_mcp()
