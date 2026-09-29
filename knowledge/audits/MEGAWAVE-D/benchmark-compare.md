# MEGAWAVE-D — Benchmark compare: cache_lens post-wave vs E2E baseline (2026-09-28)

Lane: D · Written 2026-09-28 · Executed by: main loop (lane-D subagent spawned without fs/shell tools; delegated execution — see needsMainLoop receipt).

## Method
- Current run cmd: `python C:/Users/Prekzursil/.agents/scripts/cache_lens.py --json` (exit 0, SUCCESS:cache_lens)
- Baseline ref: `C:/Users/Prekzursil/.agents/knowledge/audits/E2E-BASELINE-2026-09-28/baseline.txt`
- Prior expectation (task spec): the megawave's changes affect FUTURE sessions only → historical cache_lens numbers should be ~unchanged vs baseline. **CONFIRMED — every cold metric is byte-identical (cold_cost, cold_rewrites, cache_creation totals unchanged); the only movement is hit_rate 94.28→94.29 (+0.01) and corpus growth (+107 files), both from session lines written after the baseline snapshot, not from wave changes.**
- Baseline provenance caveat (VERIFIED by timeline): the baseline job's cache_lens half ran ~01:55 (pre-wave), but its settings-snapshot half executed minutes later, AFTER the security_digest + PostModelSwitch wiring — so baseline's hooks list already shows PostModelSwitch and SECURITY_DIGEST_ENABLE=1. The cache_lens comparison below is strictly pre-vs-post; the settings snapshot is not.

## Comparison table
| metric | baseline | current | delta | label |
|---|---|---|---|---|
| files | 18445 | 18552 | +107 | VERIFIED (cache_lens --json both runs) |
| raw_usage_lines | 1132915 | 1137272 | +4357 | VERIFIED (same cmd) |
| deduped_messages | 463528 | 465432 | +1904 | VERIFIED (same cmd) |
| dedupe_factor | 2.444 | 2.443 | -0.001 | VERIFIED (same cmd) |
| hit_rate_pct | 94.28 | 94.29 | +0.01 | VERIFIED (same cmd) |
| cold_rewrites | 8266 | 8266 | 0 | VERIFIED (same cmd) |
| cold_cost | 1244871411 | 1244871411 | 0 | VERIFIED (same cmd) |
| totals.cc (cache_creation) | 5214538655 | 5214538655 | 0 | VERIFIED (same cmd) |
| harness-bench instrument tests | 37 passed (1.34s) | UNMEASURED (not re-run post-wave this lane; gate re-run scheduled with the audit phase) | — | per-label rule |

## Raw current JSON (cache_lens.py --json)
Totals block VERBATIM (exit 0, stderr empty):
```json
{
  "root": "C:\\Users\\Prekzursil\\.claude\\projects",
  "files": 18552,
  "raw_usage_lines": 1137272,
  "deduped_messages": 465432,
  "dedupe_factor": 2.443,
  "totals": { "in": 338329803, "cr": 91639309514, "cc": 5214538655, "out": 179243876 },
  "hit_rate_pct": 94.29,
  "cold_rewrites": 8266,
  "cold_cost": 1244871411
}
```
`flagged_sessions` array (130 entries, sorted by cold_cost desc): head byte-identical to baseline's head (30bd50d4… 99,770,965 / dea94f05… 75,043,646 / d219bc39… 73,478,726 …); the array's full body is reproducible with the cmd above and is preserved verbatim in this session's transcript — omitted here only to keep the audit file reviewable. New low-hit entries (agent-* subagent sessions at 10–50% hit rate) are post-baseline subagent traffic, consistent with the cold-cache-per-subagent doctrine (context-reduction rule 7).

## Raw baseline (verbatim)
Preserved at the baseline ref path; cache_lens block totals: files 18445 · hit_rate 94.28 · cold_rewrites 8266 · cold_cost 1244871411 · cc 5214538655 (see table; the file's own text is authoritative). harness-bench: `37 passed in 1.34s`. Settings snapshot: skillListingBudgetFraction 0.04 · ENABLE_TOOL_SEARCH auto:5 · ANTHROPIC_BASE_URL z.ai (GLM plane) · CLAUDE_CODE_SUBAGENT_MODEL_FORCE (unset) · SECURITY_DIGEST_ENABLE 1 · PostModelSwitch present (see provenance caveat).

## What a FRESH session must beat
(Forward-looking gates — the wave is judged on THESE, not on cache_lens history:)
- hook-fire latency via harness-bench: **37 passed / baseline.json gate live** (baseline value; post-wave gate re-run = the audit phase's action) — VERIFIED present in baseline
- skill-listing budget: **skillListingBudgetFraction = 0.04** — VERIFIED in baseline settings snapshot

## Reconciliation record
- sota-2026-09.md Tier-3: `C:/Users/Prekzursil/.agents/skills/recover-from-false-positive/references/sota-2026-09.md`, "### Tier 3 — fleet/workflow resilience". Tier-3 text specifies: attempt-1 normal → attempt-2 FRESH agent reframed (defensive-inventory prompt: structured JSON verdicts to disk, no echoing bodies, ≤3 tasks/agent), pinned model → else record REFUSED_BY_SAFEGUARD and CONTINUE; respawn never continue. **No TIER-3 DIVERGENCE** — the implemented semantics (respawn+reframe from ORIGINAL, non-fatal recorded exhaustion, fresh agent per attempt, max 2 retries) match; the spec's specific "defensive-inventory prompt" shape is ONE instance of the generic reframe the wrapper provides.
- **GENUINE DEFECT RECORDED (not fixed, per the no-papering rule):** selftest **7/8 — T5 FAILED**: `classifyFailure('Error: connect ECONNREFUSED 127.0.0.1:7870', null)` returned 'REFUSAL', expected 'ERROR'. Root cause: `REFUSAL_RE` contains bare `refus`, which substring-matches ECONN**REFUS**ED — transport-level connection-refused (the estate's canonical NON-refusal failure, per the MCP connect banner) would mis-classify as a safeguard refusal and burn the retry budget reframing at a dead port instead of failing fast. Proposed follow-up fix (owner/lane-owner call, NOT applied): tighten to `\brefus(?:ed|al)\b` (or negative lookahead for `ECONN?REFUSED`) in BOTH the snippet and its verbatim test copy (T8 drift-guard requires both change together). Until fixed: consumers must treat wrapper-REFUSAL outcomes with low-char-attempt counts on infra-heavy tasks as suspect.

## Claim ledger
- EXPECT-NO-CHANGE: **VERIFIED** (was INFERRED high ~90%) — cold_cost/cold_rewrites/cc byte-identical pre/post; only corpus growth moved.
- Every numeric row in the table: VERIFIED, source = the two cache_lens runs cited in Method.
- Baseline settings-provenance caveat: VERIFIED (job ordering: cache_lens walk precedes the settings read in the same background script).
- 7/8 selftest + defect description: VERIFIED (node run output captured verbatim in the session transcript; files unmodified after write).
