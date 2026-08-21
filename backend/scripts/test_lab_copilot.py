#!/usr/bin/env python3
"""Automated Test Suite for Athena Interactive CTF & Cybersecurity Lab Toolkit:
- Multi-format Payload Decoder (Base64, Hex, URL, JWT, HTML Entities, Rot13, Binary)
- Intelligent Hash Identifier (bcrypt, Argon2, NTLM, MD5, SHA-256, Unix shadow)
- Vulnerability & CVE Explainer
- Automated Lab Dossier Manager & Walkthrough Exporter
- MCP & ToolRegistry Function Calling Dispatchers
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

def test_lab_copilot() -> None:
    print("=" * 65)
    print("🔓 1. TESTING MULTI-FORMAT PAYLOAD DECODER")
    print("=" * 65)

    from lab_copilot import decode_payload

    # 1. Base64
    b64_sample = "QVRIRU5BIExBQiBDT1BJTE9UIDIwMjY="
    res_b64 = decode_payload(b64_sample)
    print(f"\n- Base64 Decode Output:\n{res_b64}")
    assert "ATHENA LAB COPILOT 2026" in res_b64
    print("  ✅ Base64 decoding passed.")

    # 2. Hex / ASCII
    hex_sample = "415448454e412d435446"
    res_hex = decode_payload(hex_sample)
    print(f"\n- Hex Decode Output:\n{res_hex}")
    assert "ATHENA-CTF" in res_hex
    print("  ✅ Hex / ASCII decoding passed.")

    # 3. URL Encoding
    url_sample = "admin%27%20OR%201%3D1--%20"
    res_url = decode_payload(url_sample)
    print(f"\n- URL Decode Output:\n{res_url}")
    assert "admin' OR 1=1--" in res_url
    print("  ✅ URL decoding passed.")

    # 4. JWT Token Header & Claims
    jwt_sample = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMzg0MiIsIm5hbWUiOiJTaGFiYXJpIiwiYWRtaW4iOnRydWUsImV4cCI6MTg5MzQ1NjAwMH0.dummy_signature"
    res_jwt = decode_payload(jwt_sample)
    print(f"\n- JWT Decode Output:\n{res_jwt}")
    assert "Shabari" in res_jwt and "HS256" in res_jwt
    print("  ✅ JWT token inspection passed.")

    # 5. Rot13
    rot_sample = "nguran"
    res_rot = decode_payload(rot_sample)
    print(f"\n- Rot13 Decode Output:\n{res_rot}")
    assert "athena" in res_rot
    print("  ✅ Rot13 decoding passed.")

    # 6. Binary String
    bin_sample = "01000001 01010100 01001000 01000101 01001110 01000001"
    res_bin = decode_payload(bin_sample)
    print(f"\n- Binary Decode Output:\n{res_bin}")
    assert "ATHENA" in res_bin
    print("  ✅ Binary string decoding passed.")

    print("\n" + "=" * 65)
    print("⚡ 2. TESTING INTELLIGENT HASH IDENTIFIER")
    print("=" * 65)

    from lab_copilot import identify_hash

    # 1. bcrypt
    bcrypt_sample = "$2a$12$R9h/cIPz0gi.URNNXRkh2OPST9/PgBkqquzi.Ss7KIUgO2t0jWMUW"
    res_bcrypt = identify_hash(bcrypt_sample)
    print(f"\n- bcrypt Identification:\n{res_bcrypt}")
    assert "bcrypt" in res_bcrypt and "3200" in res_bcrypt
    print("  ✅ bcrypt identification passed.")

    # 2. SHA-256
    sha256_sample = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    res_sha256 = identify_hash(sha256_sample)
    print(f"\n- SHA-256 Identification:\n{res_sha256}")
    assert "SHA-256" in res_sha256 and "1400" in res_sha256
    print("  ✅ SHA-256 identification passed.")

    # 3. NTLM / MD5
    md5_sample = "5d41402abc4b2a76b9719d911017c592"
    res_md5 = identify_hash(md5_sample)
    print(f"\n- MD5/NTLM Identification:\n{res_md5}")
    assert "1000 (NTLM)" in res_md5 or "0 (MD5)" in res_md5
    print("  ✅ MD5/NTLM identification passed.")

    print("\n" + "=" * 65)
    print("🧠 3. TESTING VULNERABILITY & CVE EXPLAINER")
    print("=" * 65)

    from lab_copilot import explain_cve_mechanics

    res_ssrf = explain_cve_mechanics("SSRF")
    print(f"\n- SSRF Explanation:\n{res_ssrf}")
    assert "Server-Side Request Forgery" in res_ssrf
    print("  ✅ Vulnerability mechanics explainer passed.")

    print("\n" + "=" * 65)
    print("📝 4. TESTING AUTOMATED LAB DOSSIER MANAGER")
    print("=" * 65)

    from lab_copilot import get_dossier_manager

    mgr = get_dossier_manager()
    start_msg = mgr.start_session("HTB-Sau", "10.10.11.224", "Hack The Box")
    print(f"\n- Session Start: {start_msg}")
    assert "HTB-Sau" in start_msg

    log_msg1 = mgr.log_finding(
        note="Nmap scan revealed open ports: 22 (SSH), 80 (HTTP), 55555 (Request Baskets 1.2.1)",
        milestone="recon",
        command_used="nmap -sC -sV -p- 10.10.11.224",
    )
    print(f"- Log Finding 1: {log_msg1}")

    log_msg2 = mgr.log_finding(
        note="Identified SSRF in Request Baskets 1.2.1 forwarding to internal port 80 (Maltrail 0.53)",
        milestone="foothold",
        command_used="curl -X POST http://10.10.11.224:55555/api/baskets/test",
    )
    print(f"- Log Finding 2: {log_msg2}")

    export_msg = mgr.export_dossier()
    print(f"\n- Dossier Export:\n{export_msg}")
    assert "Exported Successfully" in export_msg
    print("  ✅ Lab Dossier export passed.")

    print("\n" + "=" * 65)
    print("🌐 5. TESTING TERMUX & ROOTLESS HTB LAB HELPERS")
    print("=" * 65)

    from lab_copilot import check_lab_vpn_status, audit_termux_toolchain, generate_rootless_command

    # 1. VPN Status
    vpn_res = check_lab_vpn_status()
    print(f"\n- VPN Telemetry Status:\n{vpn_res}")
    assert "VPN Telemetry" in vpn_res
    print("  ✅ VPN status inspection passed.")

    # 2. Toolchain Audit
    toolchain_res = audit_termux_toolchain()
    print(f"\n- Toolchain Audit:\n{toolchain_res}")
    assert "Toolchain Audit" in toolchain_res
    print("  ✅ Termux toolchain audit passed.")

    # 3. Rootless Command Helper
    nmap_cmd = generate_rootless_command("nmap", "10.10.11.224")
    print(f"\n- Rootless Nmap Command:\n{nmap_cmd}")
    assert "-sT" in nmap_cmd and "-Pn" in nmap_cmd
    print("  ✅ Rootless Nmap command generation passed.")

    gobuster_cmd = generate_rootless_command("gobuster", "10.10.11.224")
    print(f"\n- Rootless Gobuster Command:\n{gobuster_cmd}")
    assert "gobuster dir" in gobuster_cmd
    print("  ✅ Rootless Gobuster command generation passed.")

    print("\n" + "=" * 65)
    print("⚙️ 6. TESTING SECURITY MCP & TOOLREGISTRY DISPATCHERS")
    print("=" * 65)

    from security_mcp_server import handle_call_tool as security_dispatcher
    from tools import ToolRegistry, ToolsConfig

    # 1. MCP Calls
    mcp_call = security_dispatcher({
        "name": "lab_decode_payload",
        "arguments": {"payload": "YWRtaW46cGFzc3dvcmQ="},
    })
    print(f"\n- MCP Call lab_decode_payload: {mcp_call['content'][0]['text']}")
    assert "admin:password" in mcp_call["content"][0]["text"]

    mcp_vpn = security_dispatcher({
        "name": "lab_vpn_status",
        "arguments": {},
    })
    assert "VPN" in mcp_vpn["content"][0]["text"]
    print("  ✅ Security MCP Lab VPN status passed.")

    # 2. ToolRegistry Calls
    cfg = ToolsConfig()
    registry = ToolRegistry(cfg)
    reg_out = registry.execute("lab_identify_hash", {"hash_str": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"})
    assert "SHA-256" in reg_out

    reg_cmd = registry.execute("lab_command_helper", {"tool": "nmap", "target": "10.10.11.224"})
    assert "-sT" in reg_cmd
    print("  ✅ ToolRegistry lab_command_helper passed.")

    print("\n" + "=" * 65)
    print("🎉 ALL CTF & LAB CO-PILOT TESTS (INCLUDING TERMUX HTB HELPERS) PASSED 100%!")
    print("=" * 65)

if __name__ == "__main__":
    test_lab_copilot()
