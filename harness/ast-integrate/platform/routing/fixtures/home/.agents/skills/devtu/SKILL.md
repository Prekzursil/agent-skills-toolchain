---
name: devtu
description: >
  ToolUniverse (mims-harvard/ToolUniverse) development toolkit — one skill, eight sub-command
  modes. Use when working on ToolUniverse tools: create a new scientific/API tool, fix a failing
  or erroring tool, optimize tool JSON descriptions for clarity, optimize research skills (evidence
  grading, report quality), auto-discover life-science APIs and generate integration PRs, run the
  full self-improvement / debug-test-round loop, apply tool-code quality patterns, or safely push
  and fix CI on GitHub. Pick the mode from intent; each mode's full playbook lives under modes/.
---

# DevTU — ToolUniverse Development Toolkit

One consolidated skill for the entire ToolUniverse (`mims-harvard/ToolUniverse`) development
lifecycle. Read the **mode** from the user's intent and open that mode's playbook under
`modes/<mode>/README.md` (progressive disclosure — the full former per-skill content, references,
and templates are preserved there unchanged).

## Sub-command modes

| Mode | Use when | Playbook |
|------|----------|----------|
| **self-evolve** | "run the self-improvement loop", "do a debug/test round", evolve ToolUniverse end-to-end (orchestrates the other modes) | [modes/self-evolve/README.md](modes/self-evolve/README.md) |
| **auto-discover-apis** | expand coverage — gap analysis, web-search for life-science APIs, batch discover + create + validate + PR | [modes/auto-discover-apis/README.md](modes/auto-discover-apis/README.md) |
| **create-tool** | add a new tool: Python tool class + JSON config + registration + real test examples | [modes/create-tool/README.md](modes/create-tool/README.md) |
| **fix-tool** | a tool fails tests / returns errors / has schema-validation issues — diagnose root cause, fix, validate | [modes/fix-tool/README.md](modes/fix-tool/README.md) |
| **code-optimization** | writing/refactoring tool Python: reusable code patterns, per-API bug fixes, schema/pre-commit checklist | [modes/code-optimization/README.md](modes/code-optimization/README.md) |
| **optimize-descriptions** | make tool JSON descriptions clear (prerequisites, abbreviations, required-vs-optional params, usage) | [modes/optimize-descriptions/README.md](modes/optimize-descriptions/README.md) |

### The cycle (self-evolve orchestration)
### Shared rules (all modes) — CRITICAL
