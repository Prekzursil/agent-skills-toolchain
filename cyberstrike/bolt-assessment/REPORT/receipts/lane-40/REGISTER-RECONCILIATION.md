# LANE-40 REGISTER RECONCILIATION PROOF

**Date:** 2026-10-02 · **Task:** work item D — reconcile 3 divergent LANE-REGISTER.md copies, then
append the lane-40 block IDENTICALLY to all three.

## Pre-reconcile state (captured before any modification)

| copy | path | lines | sha256 | mtime (UTC) |
|---|---|---|---|---|
| bolt-intel (master) | /work/bolt-intel/LANE-REGISTER.md | 148 | `a0799307950def19fe219a33f1c1db13793535fd04eb5f54b1cd9f448619c642` | 2026-10-02T16:30:37.056422+00:00 |
| REPORT | /work/bolt/REPORT/LANE-REGISTER.md | 111 | `ce274b7bb077398eec18e96b2b157ba4b5dcafb897f6f18b45460218e0380664` | 2026-10-02T16:30:37.060422+00:00 |
| intel-core (stale) | /work/intel-core/LANE-REGISTER.md | 34 | `da3ab0b9b660ebff4f36019b7565bdb6c51a7c4f829d57dd669dcda007c1e873` | 2026-10-01T17:09:38.908821+00:00 |

Divergence (flagged by lane-37): bolt-intel master carried the full measured-dead catalog +
Phase-0 close-out + subtask-75/35/38/39 blocks but LACKED Lane 30–33 narratives; the REPORT
copy had Lane 30–33 but lacked the measured-dead catalog; intel-core was a stale 34-line
2026-09-20 baseline fully subsumed by both.

## Method

union: bolt-intel master + REPORT '## Lane 30'..'## Subtask 75' narrative block backfilled before master '## Subtask 75' heading.

intel-core stale snapshot: **subsumed** — replaced with the canonical content (its unique
content was verified absent-or-contained by lane-37 lineage before overwrite; backup retained).

## Post-append identity proof

| copy | lines | sha256 |
|---|---|---|
| bolt-intel | 182 | `4c67fec58b3e801b336cfa45c4fe917fe03f4311c3a8b8f4b83004b1d5a4e2b5` |
| REPORT | 182 | `4c67fec58b3e801b336cfa45c4fe917fe03f4311c3a8b8f4b83004b1d5a4e2b5` |
| intel-core | 182 | `4c67fec58b3e801b336cfa45c4fe917fe03f4311c3a8b8f4b83004b1d5a4e2b5` |

**Identity check:** PASS — all three copies byte-identical.
Backups (pre-modification, verbatim): `register-pre-reconcile/bolt-intel-LANE-REGISTER.pre.md`
(`a0799307950def19fe219a33f1c1db13793535fd04eb5f54b1cd9f448619c642`) · `register-pre-reconcile/REPORT-LANE-REGISTER.pre.md`
(`ce274b7bb077398eec18e96b2b157ba4b5dcafb897f6f18b45460218e0380664`) · `register-pre-reconcile/intel-core-LANE-REGISTER.pre.md`
(`da3ab0b9b660ebff4f36019b7565bdb6c51a7c4f829d57dd669dcda007c1e873`).

## Lane-40 block appended (verbatim)

```markdown
## 2026-10-02 — LANE 40 EVALUATION CHECKPOINT (subtask 94; merged w/ lane-37 graph) — CLOSED (offline, ZERO network)
- Lane-37 graph (kuzu 0.11.3, 988 nodes/182 edges) queries (a)-(e): CHAIN-FEASIBLE-FROM-ONE-IDENTITY = YES — PAT sha8 4c5f245f holds BOTH legs (PII source + presigned transport link sha8 5d9d0299). Receipts lane-37/ (13 files, sealed).
- Lane-40 final scoring (I x P x R / E, 1-10 scales): CH-1 combined data-exposure end-to-end 360.0 SELECTED-PRIMARY; CH-4 bolt-delta-lake-sensitive non-destructive write-scope marker 224.0 SELECTED-SECONDARY; CH-2 saved-query corpus 252.0 DEFERRED stage-3 conditional; CH-5 volumes 243.0 / CH-3 geo sweep 220.5 / CH-6 sel_geo 126.0 / CH-7 endpoints 108.0 PARKED. Excluded: gs-gpt (DEAD 401), GitHub owner-escalation (BLOCKED), Atlassian MCP (no path), OpenRouter (REPORT-ONLY), lanes 34/36 (GATED-CLOSED).
- Lane-41 declared budgets (FUTURE, subtask 95): CH-1 <=6 + CH-4 <=6 (+CH-2 <=8 conditional) = <=20 of <=35 envelope; <=1 rps; single-attempt per (key,endpoint); two-strikes abort per primitive; NO re-burn of proven primitives (mint 5d9d0299, ng_pii row-sha8s, mixpanel counts, geo sample sha8 d8f929fd, INSERT->DELETE->COUNT=0).
- Register reconciliation executed pre-append: intel-core stale 34-line copy subsumed; Lane 30-33 narratives backfilled from REPORT copy into bolt-intel master; all 3 copies byte-identical post-append (proof in receipts/lane-40/REGISTER-RECONCILIATION.md).
```
