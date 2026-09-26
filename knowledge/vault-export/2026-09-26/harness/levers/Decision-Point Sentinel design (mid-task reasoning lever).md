---
title: Decision-Point Sentinel design (mid-task reasoning lever)
type: report
permalink: main/harness/levers/decision-point-sentinel-design-mid-task-reasoning-lever
tags:
- harness
- hooks
- decision-sentinel
- claude-code
- research
---

# Decision-Point Sentinel — design

**Lever:** detect genuine decision forks (go/no-go, ambiguity, multi-option, "which approach") that surface MID-task (in assistant text between/after tool calls), route to council/grill-me/blueprint/brainstorm. Window NO UserPromptSubmit-only hook covers.

## SOTA (cited)
- **Wink** (MS Research, arXiv 2602.17037): async observer at fixed step interval inspects trajectory, injects plain-text DOs/DONTs in `<system-reminder>` tags; can nudge agent to END turn and seek user input on spec drift. Hierarchical nudge->plan-revision escalation.
- **Metacog** (houtini-ai): paired PostToolUse "nervous system" + UserPromptSubmit; silent when normal (0 tokens), escalating signals when abnormal; persists rules that strengthen on success (inverse decay).
- **Devin 2.1**: confidence expressed at start / after plan / after code-question; asks clarifying Qs only when not-green; "decision surface" pattern (frame options, hand choice back).
- **LangGraph** `interrupt()`: dynamic interrupt fires only when state crosses a risk threshold — interrupt-on-action is the sweet spot.
- **Cursor 2.1**: clarifying Qs fire only at plan time when multiple valid approaches exist (pre-exec), NOT mid-act (AskQuestion unstable mid-act).
- CC mechanics confirmed: Stop hook `reason` is fed back to keep agent working; Stop + PostToolUse both inject `additionalContext`; PreToolUse can `defer`.

## Best design — EXTEND, don't recreate (0 or 1 net-new hook)
Primary seam = **Stop hook** (the one moment the full final assistant text is parsed). Add `decision-sentinel/sentinel-check.py` as a Stop hook sibling of claim-check.py, REUSING claim-check's `_get_final_assistant_text()` transcript parser.
- Detect: regex bands FORK_RE (go/no-go, "which approach", "option A vs B", "two ways", "should I", "not sure whether") AND an OPEN-ENDED end (turn ends on a question / unresolved fork, not on a completed action). EVPI gate: must be a genuine multi-valid-path fork, not a rhetorical aside.
- Route by shape: ambiguity->clarify-requirements; multi-option tradeoff->council; go/no-go risk->grill-me; greenfield/expansion->brainstorm; multi-session build->blueprint.
- Inject ONE Stop `additionalContext`: "[decision-sentinel] You ended on an unresolved decision fork (<shape>). Before continuing, invoke /<skill>." Stop reason feeds back -> agent continues into the skill.
- **Mid-loop escalation** (optional, no new hook): extend anti-degen/fingerprint.py PostToolUse — when stuck-loop fires AND the loop is choice-thrash (alternating two tool/arg sets), append a "this looks like an unresolved fork; surface options via /council" line.
- **MCP-routing fix** (bonus, addresses 40 invisible MCPs): the fork router can name the relevant MCP via an expanded hint table, partly closing the MCP_HINTS gap.

## Risks/mitigations
- Nag/false-positive -> high EVPI gate + only-fires-on-open-ended-end + mode env (off/warn) + cooldown ledger (1 fire per session per shape).
- Loop: Stop reason re-fires Stop -> honor `stop_hook_active` like claim-check.
- Wrong skill routed -> name 2 candidates, let model pick.
- Hook-law: advisory => fail-OPEN, never exit 2.

## Measurement
- eval.py-style harness (skill-router already has one): labeled transcript corpus of fork vs non-fork turn-ends; target precision >=0.8, recall >=0.6. A/B: % of forks where agent invoked a reasoning skill vs silently picked. Shadow-log fires for 1 week before enabling inject.
