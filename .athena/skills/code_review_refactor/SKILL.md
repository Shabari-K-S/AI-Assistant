---
name: code_review_refactor
description: Automated code review, TypeScript/Python lint checking, and architectural refactoring.
category: coding
triggers: ["/review", "code_review", "refactor", "lint"]
tools: ["git_status", "git_diff", "terminal_command"]
created_at: 2026-08-22 08:19:55
is_builtin: true
---

# Code Review & Refactoring Standard

## 📋 Inspection Checklist
1. **Safety & Typings:** Verify strict TypeScript types (avoid `any`) and Python type hints.
2. **Asynchronous Handlers:** Ensure all promises and async threads have proper try/catch and error boundaries.
3. **No Placeholders:** All UI components and logic must be complete and fully functional.
4. **Performance:** Check for memory leaks, unclosed listeners, or redundant re-renders.
