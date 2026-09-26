---
name: Status badge as inline operator documentation
description: Status-badge string text doubles as inline operator documentation — references
  exact CLI commands, env-var names, and constraints so operator never has to leave
  the current tab to figure out what to do next.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-status-badge-as-inline-docs
---

When a UI surface shows a derived "status" string (badge, text block, label), use the badge text itself to embed actionable hints — exact CLI commands operator should run, env-var names, constraints they need to know. Cost is ~15 LoC of string literals per badge. Benefit is reduced support burden and faster operator self-service.

**Why:** Operators reading a status badge are usually at a decision point ("what should I do next?"). A vague badge like `(unset)` forces them to leave the tab, find docs, and figure out the next step. A specific badge like `(unset — set this or SWFOC_EXTRACTED_DDS_ROOT env var to see unit icons)` answers the question inline. Same text effort, dramatically better UX.

**How to apply:**
- Each distinct status state should have a distinct badge string — don't reuse the same string across states
- Embed the EXACT next step: CLI command name + most common args (e.g. "run python tools/asset_extractor/meg_parser.py")
- Include env-var names and feature-flag names operators might know about (e.g. "SWFOC_EXTRACTED_DDS_ROOT")
- Surface constraints operators need to act on (e.g. "restart editor for changes to take effect")
- Use parenthetical hints for non-obvious states (e.g. "(directory not found)" not just "Error")
- Don't overdo it — 1-2 sentences per state, not a paragraph
- For happy path, lead with the count/result then the constraint (e.g. "Found 47 icons (restart editor for changes to take effect)")

**Instances (3 — codification trigger reached at iter-310):**
- iter-301: `ModPickerStatus` — `"(unknown)"` / `"Bridge not connected. Mod picker requires a live bridge connection."` / `"Found N mods"` / `"Bridge call failed: <details>"` / `"Opened: <path>"`
- iter-309: `IconsRootStatus` (initial) — referenced env-var fallback `SWFOC_EXTRACTED_DDS_ROOT` in unset state
- iter-310: `IconsRootStatus` (full 3-state) — embedded `python tools/asset_extractor/meg_parser.py` CLI command name + restart-required note + 5-relpath aggregation count

**Edge cases:**
- **Don't embed secrets or tokens** in status text — operators may screenshot for support tickets
- **Avoid time-sensitive references** ("last updated 2026-05-07") unless you mean it — these rot
- **Match what operators search for** — use exact CLI binary names, not paraphrased versions ("meg_parser.py" not "the MEG extractor script")
- **Test the badge strings** — pin specific phrases in tests so future refactors can't silently lose the actionable hint
- **For long badges, set `TextWrapping="Wrap"`** in WPF — narrow Settings tab columns will truncate otherwise

**Cost-benefit:**
- Cost: ~15 LoC of string literals per badge (split across 3-4 states)
- Benefit: operator self-service; no doc lookup needed for common state transitions
- Anti-pattern cost: vague badges → support tickets → docs → CI for docs → drift between docs and badge → operator confusion

**Cross-link:** Combines well with `feedback_operator_trust_pattern.md` (the existing capability-status pattern). Where capability badges convey "is this LIVE or PHASE 2 PENDING," status badges answer "what should I do right now to make progress." Both target the same operator audience.