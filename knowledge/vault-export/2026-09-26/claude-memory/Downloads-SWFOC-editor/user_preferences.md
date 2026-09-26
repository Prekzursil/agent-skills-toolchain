---
name: User preferences and working style
description: Core preferences about how user wants to collaborate — terseness, autonomy,
  learning, persistence
type: user
permalink: main/claude-memory/downloads-swfoc-editor/user-preferences
---

- Prefers **terse, direct responses**. No filler, no preamble, no trailing summaries.
- Wants Claude to **auto-chain skills** rather than invoking one at a time. Sees explicit invocation as friction.
- Wants **persistent learning** — patterns learned once should auto-apply forever without re-explanation.
- Maintains a personal cheatsheet on Desktop (`C:\Users\Prekzursil\Desktop\claude-cheatsheets\`) and expects Claude to read it on demand instead of re-deriving from scratch.
- Project gate logic lives in `CLAUDE.md` at project root — that file is the source of truth for gates/thresholds/rules. Do not duplicate elsewhere.
- For SWFOC editor work specifically: 100% line + branch coverage is the law (`.coverage-thresholds.json`), TDD mandatory, no suppressions ever, no `--no-verify`.
- Comfortable with Codex delegation when Claude is stuck (`codex:rescue`, `codex-fix`).