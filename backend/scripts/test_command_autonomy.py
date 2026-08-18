#!/usr/bin/env python3
"""Test script for Command Autonomy & Risk Classifier in S.A.R.A."""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from tools import is_high_risk_command, ToolRegistry, Tool
from config import ToolsConfig


def test_command_autonomy():
    print("=" * 70)
    print("⚡ S.A.R.A. COMMAND AUTONOMY & RISK CLASSIFICATION TEST SUITE")
    print("=" * 70)

    # 1. Test Autonomous Safe / Developer / Termux commands (Must NOT be high-risk)
    autonomous_cmds = [
        "pkg install python",
        "apt update",
        "pip install requests",
        "npm run build",
        "git status",
        "git add .",
        "git commit -m 'feat: add feature'",
        "mkdir -p src/components",
        "touch test.py",
        "python3 script.py",
        "node app.js",
        "termux-torch on",
        "termux-battery-status",
        "curl -s https://wttr.in/Chennai",
        "echo 'hello world' > file.txt",
        "cat output.log | grep -i error",
    ]

    print("\n1. Testing Autonomous Developer & Termux Commands (Should NOT prompt)...")
    for cmd in autonomous_cmds:
        high_risk = is_high_risk_command(cmd)
        print(f"   Command: '{cmd}' -> High Risk: {high_risk}")
        assert not high_risk, f"Command '{cmd}' should run autonomously!"
    print("   ✅ All developer & Termux commands classified as AUTONOMOUS.")

    # 2. Test High-Risk Destructive Commands (Must be flagged as high risk)
    destructive_cmds = [
        "rm -rf /data/data/com.termux/files/home/app",
        "rm test.py",
        "rmdir old_dir",
        "mkfs.ext4 /dev/sdb1",
        "dd if=/dev/zero of=/dev/sda",
        "shutdown -h now",
        "reboot",
        "poweroff",
        "git reset --hard HEAD~1",
        "git clean -fd",
        "git push origin main --force",
        "killall -9 python",
        "pkill -9 -f server",
    ]

    print("\n2. Testing High-Risk Destructive Commands (Should REQUIRE confirmation)...")
    for cmd in destructive_cmds:
        high_risk = is_high_risk_command(cmd)
        print(f"   Destructive Command: '{cmd}' -> High Risk: {high_risk}")
        assert high_risk, f"Destructive command '{cmd}' MUST be flagged as high-risk!"
    print("   ✅ All destructive commands correctly flagged as HIGH RISK.")

    # 3. Test ToolRegistry execution with 'ask' policy
    print("\n3. Testing ToolRegistry execution with 'ask' policy...")
    confirmed_calls = []

    def mock_confirm(prompt: str) -> bool:
        confirmed_calls.append(prompt)
        return True

    cfg = ToolsConfig(confirm_shell="ask")
    registry = ToolRegistry(cfg, confirm=mock_confirm)

    # Safe autonomous command execution
    res = registry.execute("run_shell_command", {"command": "echo 'SARA Autonomy Active'"})
    print(f"   Safe execution output: '{res}'")
    assert "SARA Autonomy Active" in res
    assert len(confirmed_calls) == 0, "Autonomous command should NOT have triggered mock_confirm!"
    print("   ✅ Safe command ran autonomously with 0 confirmation interruptions.")

    # Destructive command execution (triggers confirm)
    res_danger = registry.execute("run_shell_command", {"command": "rm -rf /tmp/nonexistent_sara_test_dir"})
    assert len(confirmed_calls) == 1, "Destructive command MUST trigger confirm!"
    print(f"   ✅ Destructive command correctly triggered confirmation: '{confirmed_calls[0]}'")

    print("\n" + "=" * 70)
    print("✅ ALL COMMAND AUTONOMY & RISK CLASSIFIER TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    test_command_autonomy()
