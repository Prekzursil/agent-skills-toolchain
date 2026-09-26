---
title: C16 failure-taxonomy module BUILT (2026-07-24)
type: project
permalink: main/projects/platform-redesign/c16-failure-taxonomy-module-built-2026-07-24
tags:
- C16
- harness
- platform-redesign
- failure-taxonomy
- two-strikes
- built
---

Built 2026-07-24 during the forced C16/H-20 build (owner overrode the cap-wait). Main-session solo build (subagents were capped, reset 12:10 Bucharest).

## Observations

- [decision] C16's work-list framing was WRONG. #reframe — The grounding synthesis said C16 = "error-taxonomy handlers on hooks/_shared/completion.py". The VERBATIM spec (07-OPTIONS-C.md:481-507) shows C16 is a SELF-CONTAINED failure-taxonomy module, NOT a modification of the load-bearing completion.py classifier. Reading the real spec before building avoided touching load-bearing code.

- [milestone] C16 module BUILT + TDD-verified. #built — `hooks/_shared/failure_taxonomy.py` (new): classify_failure() into the named taxonomy (win-arg-limit/429/schema-invalid/severed-stream/timeout/codex-exit/unclassified); per-class HandlerPolicy (retry-once-with--ignore-user-config / backoff+jitter / one-reask / redispatch-then-UNKNOWN / kill / fail — NOT blanket retry); require_timeout_s() C12-T0 lint (missing/0/negative/bool/non-numeric raises); TwoStrikesBreaker (refuses 3rd consecutive same-fingerprint attempt, escalates). 31 tests, 100% line+branch, ruff-0.15.17 clean, 2 mutations killed. Committed 858d0d6 on branch w2-c16-error-taxonomy (worktree ast-c16-taxonomy, off origin/main d262fdf). PROPOSE-ONLY — not pushed (token read-only), NOT adversarially reviewed (subagents capped).

- [decision] Built SHADOW-FIRST + not-yet-wired. #shadow — It's a library the fan-out barrier would import; no behavior change until wired. The "wire into parallel()/the barrier" step is deliberately separate + owner-gated (touches the live runtime). Honest status = "built + self-verified + review-pending", NOT "done".

- [gotcha] The 5h session cap is REAL (confirmed via workflow <failures> block: "session limit resets 12:10pm Bucharest"), kills SPAWNED SUBAGENTS, but the MAIN loop keeps running. #cap — So a forced build proceeds via the main session solo (sequential, no fan-out, no adversarial review) — slower + un-reviewed but real. My flip-flop (capped→not-capped→confirmed-capped) was single-signal thrashing; the failures block is the authoritative signal.

## Relations
- relates_to [[Statusline rebuild — process/meta learnings (2026-07-24)]]
- part_of [[Post-gate execution 2026-07-23]]
