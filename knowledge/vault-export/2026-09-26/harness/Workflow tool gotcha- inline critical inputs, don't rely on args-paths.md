---
title: 'Workflow tool gotcha: inline critical inputs, don''t rely on args-paths'
type: note
permalink: main/harness/workflow-tool-gotcha-inline-critical-inputs-dont-rely-on-args-paths
tags:
- workflow
- harness
- gotcha
- orchestration
---

# Workflow tool: agent prompts interpolating ${args.X} can reach subagents as literal "undefined"

**valid_as_of: 2026-06-21.** Bit me twice in one session.

## Symptom
A Workflow `agent()` prompt that interpolates `${args.planPath}` / `${args.auditPath}` can reach the subagent with the value as the **literal string "undefined"** — the arg isn't bound when the script body runs. The subagent then hunts for a nonexistent file (often in the wrong cwd, e.g. the project dir not `~/.claude`) and either fails or is tempted to fabricate.
- Failure 1: `best-of-best-harmony` resume threw `undefined is not an object (evaluating 'args.auditPath')` — **resume does NOT re-bind args; you must re-pass `args` on every `Workflow({scriptPath, resumeFromRunId, args})`**.
- Failure 2: fresh `best-of-best-harmony` launch WITH args passed still delivered `planPath="undefined"` to the select-bets agent → whole run degraded into analyzing its own missing input.

## Fix (proven)
**Inline critical inputs directly into the script string** (the data, the bets list, a compact inventory) instead of passing file paths via `args` and having agents read them. The `harmony-v2` re-run inlined the 7 bets + the harness inventory as JS consts → ran clean. 
Secondary: if you must use args, (a) re-pass `args` on resume, (b) validate at the top of the script and fail-closed on missing/`"undefined"`/empty before any `agent()` dispatch (this IS one of the discovered capability levers — input-contract validation at the fan-out boundary).
See [[Skill/MCP router hook — fixes "only uses skills/MCPs when explicitly invoked"]] for the broader harness-capability work this is part of.
