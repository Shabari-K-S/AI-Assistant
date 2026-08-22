---
name: termux_mobile_ops
description: Android Termux environment optimization, package management, and rootless network operations.
category: sysadmin
triggers: ["/termux", "termux", "android", "pkg", "rootless"]
tools: ["lab_env_check", "terminal_command", "battery_status"]
created_at: 2026-08-22 08:19:55
is_builtin: true
---

# Android Termux Mobile Operations Skill

## 📱 Execution Rules for Non-Rooted Android
1. **Network Scans:** Non-rooted Android kernels block raw ICMP and SYN packets. Always use TCP Connect `-sT` and skip ping `-Pn` in Nmap.
2. **Package Toolchain:** Prefer lightweight ARM-compiled binaries (`nmap`, `curl`, `python`, `git`).
3. **Power Efficiency:** Minimize continuous background polling; use reactive event streams and wakelocks judiciously.
