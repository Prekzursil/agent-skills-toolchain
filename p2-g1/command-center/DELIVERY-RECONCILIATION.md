# Delivery reconciliation — what the 2,007 declared work units actually produced

- **Derivation:** `tools/command-center/reconcile_delivery.py` (deterministic; no agent judgement)
- **Data:** `command-center/DELIVERY-RECONCILIATION.json` — one row per unit
- **Controls:** `tools/command-center/tests/test_reconcile_delivery.py`, 8 passing
- **Date:** 2026-08-10

## Why this exists

`P13-BLINDSPOT-REVIEW.md` measured that **1 of 2,007 catalogued work units produced the
artifact it declared**, with two mechanically independent probes agreeing. That measurement is
sound. Read alone it implies almost nothing was built — which the same review's own text
contradicts: 8,911 tracked files, a green suite, and shipped plugin, marketplace, routing and
coordination phases.

Both statements are true because **the plan and the delivery live in different path
namespaces, and nothing in the repo mapped between them.** This file is that map.

## Result

| disposition | units | what it means |
|---|---:|---|
| `DELIVERED-AT-DECLARED-PATH` | **2** | the declared `output_path` exists and is non-empty |
| `DELIVERED-ELSEWHERE-EXACT` | 0 | identical basename tracked at another path |
| `DELIVERED-ELSEWHERE-STEM` | 28 | stem matches case/separator-folded — all 28 ambiguous |
| `UNIT-ID-REFERENCED` | 779 | worked on, artifact **not** located |
| `NOT-PRODUCED` | **1,198** | no evidence of either |

**Bounds, not a number.** Lower bound on delivery is **2** (verified on disk). Upper bound is
**30 / 2,007 = 1.49%**, and that upper bound counts *filename* evidence only — a basename match
proves an artifact of that name exists somewhere tracked, never that it satisfies the unit's
`evidence_requirement` or `completion_sentinel`. `UNIT-ID-REFERENCED` is in **neither** bound,
deliberately: folding "the id is mentioned somewhere" into a delivered count is exactly how a
program talks itself into a completion figure it did not earn.

### Reconciling the 2 against the review's 1

Not a contradiction. The two are `WFA-0001` (the one the review found) and `BLD-0023` — the
receipt **the review itself emitted while running**. Their count was true when measured.

## By phase

| phase | NOT-PRODUCED | ID-REFERENCED | STEM | AT-PATH |
|---|---:|---:|---:|---:|
| 0 | 63 | 59 | 0 | 0 |
| 1 | 15 | 20 | 0 | 1 |
| 2 | 154 | 39 | 0 | 0 |
| 2A / 2B / 2C | 69 / 46 / 99 | 16 / 20 / 29 | 0 | 0 |
| 3 | 25 | 24 | 28 | 0 |
| 4 | 38 | 53 | 0 | 0 |
| 5 | 31 | 48 | 0 | 0 |
| 6 | 46 | 18 | 0 | 0 |
| 7 | 125 | 3 | 0 | 0 |
| 7A | 107 | 8 | 0 | 0 |
| 8 | **1** | 25 | 0 | 0 |
| 9 | 8 | 21 | 0 | 0 |
| 10 | **236** | 59 | 0 | 0 |
| 11 | 53 | 133 | 0 | 0 |
| 12 | 59 | 70 | 0 | 0 |
| 13 | 6 | 57 | 0 | 1 |
| 14 | 3 | 48 | 0 | 0 |
| 15 | 5 | 26 | 0 | 0 |
| 16 | 9 | 3 | 0 | 0 |

Phase 8 is the most thoroughly worked (1 not-produced); **phase 10 is the largest single gap
at 236**, followed by phase 2 (154), phase 7 (125) and phase 7A (107).

## Detector honesty

The first run of this tool scored `UNIT-ID-REFERENCED` on 1,977 units — **100% of every unit
that reached that branch**. That is a self-measuring detector, not a finding:
`WORK-UNIT-CATALOG.json` is itself tracked and contains all 2,007 ids by construction, so "the
id appears in tracked content" meant "the id appears in the plan that declares it". The
declaring documents are now excluded (`DECLARING_DOCS`) and the distribution discriminates
(1,198 / 779). Both states were observed directly; the regression is pinned at
`test_reconcile_delivery.py::test_the_plan_restating_its_own_id_is_NOT_delivery`.

## What this does NOT establish

- **UNVERIFIED:** whether any `DELIVERED-ELSEWHERE-STEM` candidate actually satisfies its
  unit's evidence requirement. All 28 are ambiguous (>1 candidate) and none were opened.
  Settling experiment: for each, validate the candidate against the unit's `output_schema` and
  check its `completion_sentinel`.
- **UNVERIFIED:** whether the 1,198 `NOT-PRODUCED` units are genuinely undone or were
  superseded by work under a different plan. The catalog carries **no** status, disposition or
  receipt field on any of the 2,007 units, so no ledger exists to distinguish the two.
- This file reconciles *paths*. It does not judge whether delivered work is **good**.

## Consequence for the program stopping rule

Any stopping condition phrased as "N of 2,048 work units complete" is **not computable** from
the catalog as it stands, and any figure of that shape produced so far should be treated as
unsourced. The computable statements are the two bounds above. Closing this properly requires
a disposition field on the work units — the 103-item register already has that machinery
(`close.py` + `render.py`); the 2,007-unit catalog has never used it.
