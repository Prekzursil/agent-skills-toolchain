---
title: cursor-provider-followup-2026-09-02
type: note
permalink: dqverify-repo-20261013/reconcile-flags/cursor-provider-followup-2026-09-02
---

# FOLLOW-UP: no Cursor provider in the hook harness (filed, not built)

Filed 2026-09-02 during the harness lineage reunion
(`harness-lineage-reunion-2026-09-02.md`). This records the gap as a work item for the
owner; **nothing about Cursor was built here**, by instruction.

## What is true after the reunion

- `adapters.SUPPORTED_PROVIDERS == {"claude", "codex", "grok"}` and
  `dispatcher.py --provider` accepts the same three. `grok` arrived from the live tree
  as an attribution fix (its hooks had run as `--provider claude`); it rides the claude
  render branch because its output vocabulary has no `systemMessage`.
- `rg -i cursor agent-self/harness/*.py agent-self/harness/tests/*.py` returns
  **zero** matches (source AND tests, re-measured 2026-09-02 after the reunion). The
  reunited `.agents/harness` mirror is byte-identical, so the same holds for what gets
  deployed.
- What Cursor has instead (unchanged since Wave B, 2026-08-27): `~/.cursor/hooks.json`
  calling two standalone PowerShell scripts, `.agents/scripts/cursor-hooks/shell-guard.ps1`
  and `cursor-hook-log.ps1`, both observe-only (`failClosed: false`), neither routing
  into `harness/dispatcher.py`. A Cursor session therefore gets the shared skills,
  the behaviour contract and the MCP registry, but **none** of the lifecycle
  enforcement (ledger, goal re-injection, recall/digest gate, register gate, receipt
  gate, secret guard).

## What building it would take (scoping only)

1. `adapters.py`: add `"cursor"` to `SUPPORTED_PROVIDERS`; a `normalize_event`
   mapping from Cursor's hook payload (its field names for session, cwd, tool name and
   tool input are not the claude ones — measure them from a real `hooks.json` run
   before writing the aliases); a `render_output` branch that emits only fields Cursor's
   hook protocol accepts (Cursor's output vocabulary must be measured the way Grok's was
   — do not assume `hookSpecificOutput` or `systemMessage`).
2. `registration.py`: a `build_hooks("cursor")` shape for `~/.cursor/hooks.json`
   (different document layout from `settings.json`), with its own PreToolUse matcher
   built from Cursor tool names — never `_CLAUDE_PRETOOLUSE_MATCHER` (the grok lesson:
   that constant misses 12 of 13 Grok tools).
3. `install.py`: a third registration document only if the owner wants the harness to
   OWN `~/.cursor/hooks.json`; otherwise leave Cursor's file to the owner as Grok's is.
4. Tests: a `test_contract` twin of the grok test, a wire test through the real
   `dispatcher.py` subprocess with `--provider cursor`, and a host-union replica for
   Cursor's output schema in `test_native_events.py`.

## Gate the council already placed on it

The enforce / `failClosed` flip for Cursor was gated on ~1 week of
`cursor-shell-guard.jsonl` latency evidence (measured 4806 ms under RAM pressure
against Cursor's 2 s hook timeout — see `harness-lineage-2026-09-01.md` §5). The
reunited dispatcher now runs its fan-out under a wall-clock budget derived from the
registered host timeout, which is the mechanism that would make a 2 s Cursor deadline
survivable — but the budget table (`registration._TIMEOUTS`) has no Cursor events yet,
so a Cursor adapter would fall back to the flat 5 s default until one is added.

## Decision needed (owner)

Whether a read-only (observe, `failClosed: false`) Cursor adapter is wanted at all,
and if so whether it replaces or sits beside the two PowerShell hooks. Not done here.