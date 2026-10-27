# D4 CLOSE — workflow id uniqueness over platform/workflows/

STATUS: CLOSED and MEASURED. Nothing below is unmeasured.

COVERAGE: root cause, equivalence proof, removal, the new gate, both-states controls (synthetic AND
real-bytes), the widened collision search, lint at the pinned ruff, the blast-radius suite, and two
full-platform runs with per-failure attribution.

## 1. Why there were two files — ROOT CAUSE (CONFIRMED)

`platform/lib/foundry/_regen_forged.py` runs two different forge commands over the same source
pair `(bp-cnc-07-probe-wins-split-verdict-resolver, bp-arc-05.vendor-neutral-workflow-spec-emission)`:

| run | command | `--out` |
|---|---|---|
| 1 | `forge fuse --strategy best-of-breed` | `forged/fused.cnc07-arc05.workflow.json` |
| 4 | `forge tournament` | `forged/fused.cnc07-arc05.TOURNAMENT-WINNER.workflow.json` |

`fused.cnc07-arc05.TOURNAMENT.json` records `winner.strategy = "best-of-breed"`. The tournament's
winning entrant IS the standalone fusion, so both commands emitted the same document.

`forge._fused_id` (`platform/lib/foundry/forge.py:159-187`) is content-addressed *by design* —
its own docstring says a re-run with identical content "deliberately keeps the same id". So:

**The id derivation is NOT the bug.** Same content -> same id is correct. The defect is at the
corpus level: one document was shipped at two paths, so `id -> path` resolution is ambiguous, and
`platform/routing/index.py:445-450` absorbed it with a silent `continue` on an already-seen id.

## 2. The two files were byte-identical — CONFIRMED by 3 independent signals

| signal | mechanism | result |
|---|---|---|
| raw sha256 | CRLF working-tree bytes | both `07c55377dae307c0…` |
| git blob OID | SHA-1 over LF-normalised stored bytes | both `6751430648c5c36bcc1347e1d1f823b75d933497` |
| canonical digest | sha256 over key-sorted parsed JSON | both `39a19bfb4ad9…` |

Mechanically independent (different hash, different normalisation), and they agree.

## 3. Which file was kept, and why

**KEPT** `platform/workflows/forged/fused.cnc07-arc05.workflow.json`
**REMOVED** `platform/workflows/forged/fused.cnc07-arc05.TOURNAMENT-WINNER.workflow.json`

Removal, not renaming: renaming would mint a second id for one document, which is the opposite of
what a content-addressed scheme should do. Five measured reasons for that direction:

1. A shipped test asserts on the KEPT path — `test_foundry.py:1234-1250`
   `test_the_shipped_certified_workflow_still_validates`. It guards with
   `if not p.exists(): pytest.skip(...)`, so removing the kept path instead would have converted a
   real assertion into a **silent skip** — a false green.
2. `fused.cnc07-arc05.REPORT.json:816` records `emitted_to` = the KEPT path. Removing it would
   orphan the CERTIFIED certification report.
3. `platform/lib/foundry/FOUNDRY-STATUS.json:61` cites the KEPT path as evidence.
4. Nothing downstream needs the removed path: re-running `forge decompose` against the kept path
   reproduces `fused.cnc07-arc05.DECOMPOSITION.json` **byte-identically**
   (`e0b015eb504123ec…` both ways), so the removed file was not load-bearing for it.
5. Nothing is lost: the tournament's own deliverable is its ledger
   `fused.cnc07-arc05.TOURNAMENT.json`, which still records the full entrant table and
   `winner.strategy = "best-of-breed"` — and that winner is exactly the kept document.

## 4. Before / after, read off disk

| | documents | distinct ids | ids at >1 path |
|---|---|---|---|
| BEFORE | 103 | 102 | **1** |
| AFTER | 102 | 102 | **0** |

Routing non-regression: the dedupe was collapsing 103 docs -> 102 records; it is now 102 -> 102, so
the "102 blueprints" the routing tests pin is unchanged. Verified by running the suites, not
inferred: `platform/routing/ platform/lib/foundry/` = **269 passed**.

## 5. The new gate

* `platform/lib/workflows/workflow_id_index.py` — public module owning the invariant
  **an id must resolve to EXACTLY ONE path**, with `violations()` fail-closed on an empty walk and
  on unparsable JSON, plus a `main()` CLI gate emitting a terminal `SUCCESS:`/`FAILED:` marker.
* `platform/lib/workflows/test_workflow_id_uniqueness.py` — 17 tests.

Why a new module rather than widening the existing foundry gate: the shipped
`test_no_workflow_id_resolves_to_two_different_documents` asserts `divergent_ids == {}`, which only
fires when the two documents DIFFER. It is structurally blind to the identical-content case that
actually shipped. `test_the_shipped_gate_is_blind_to_an_identical_content_duplicate` **measures**
that blind spot (imports the shipped scanner, runs it on the same seeded tree, asserts it reports
clean while the new gate fires) instead of asserting it in prose — so if the foundry gate is ever
widened, that test fails and the redundancy gets re-litigated rather than silently kept.

## 6. Both-states controls — the gate fires on broken, is silent on clean

Synthetic (inside the test suite): clean tree silent; identical-content duplicate FIRES;
divergent duplicate FIRES; empty tree FIRES (fail-closed); unparsable JSON FIRES; CLI exits 0 clean
/ 1 seeded.

Real bytes (`platform/lib/workflows/_d4_bothstates_real.py`) — materialises the whole
`platform/workflows` tree at git HEAD via `git cat-file -p` (never `git archive`, which returns
CRLF here) into a temp dir OUTSIDE the measured tree:

```
[KNOWN-BROKEN (git HEAD)]   101 docs, 100 distinct ids, GATE FIRED: True
[POST-FIX (working tree)]   102 docs, 102 distinct ids, GATE FIRED: False
SUCCESS:d4-both-states-real fires_on_broken=True silent_on_fixed=True
```

(HEAD shows 101 vs the working tree's 102 because two `_shared/*.subworkflow.json` documents are
still untracked — another lane's uncommitted work, not part of this change.)

## 7. Any OTHER id colliding? — measured, scope stated

`platform/lib/workflows/_d4_scope_probe.py` widens the search past the shipped gate's shape filter:

```
json files scanned           : 126
files carrying a top-level id: 102
distinct ids (any shape)     : 102
workflow-document ids        : 102
A. ids at >1 path (any shape): 0
B. sidecar ids shadowing a workflow id: 0
```

**Search scope: every `*.json` under `platform/workflows/` recursively, 126 files.** Within it, the
D4 pair was the ONLY collision — zero others, and no report/status sidecar id shadows a workflow
id. Ids outside this tree (protocols, presets, catalog units, the register) were NOT scanned; that
is a different namespace and a different lane.

## 8. Reintroduction closed at the source

`_regen_forged.py` run 4 now writes the tournament winner to a scratch path OUTSIDE the indexed
corpus and asserts its canonical content equals the kept certified fusion
(`SUCCESS:winner-identity tournament_winner==certified_fusion=True`). A full regen is
byte-reproducible — all 9 remaining `forged/*.json` digests identical before and after — and does
not recreate the duplicate.

## 9. Non-regression — and why the pinned 3,026 baseline is NOT reproducible right now

**Blast-radius suite (the decisive number for this change).** Every test directory that reads
`platform/workflows/`, run together:

```
platform> python -m pytest lib/workflows/ lib/foundry/ lib/wfdsl/ routing/ corpus/ -q
2644 passed, 14 skipped in 455.75s
```

Zero failures. All 14 skips of the pinned baseline live in this set.

**Two full-platform runs, and the pinned baseline could not be matched — honestly, not silently:**

| run | result |
|---|---|
| full run 1 | 4 failed, **3843** passed, 14 skipped |
| full run 2 | 3 failed, **3919** passed, 14 skipped |

The pinned baseline is 3,026 passed / 14 skipped. The tree currently holds ~900 more tests than
that, and it grew by **76 more passing tests between my own two runs 10 minutes apart**. Other
lanes are building into this working tree concurrently, so the pinned figure is not a comparison
this unit can make. What is measurable, and is the honest claim: **my change's blast radius is
0-failure across two independent full runs plus a dedicated 2,644-test run.**

**All 7 full-run failures attributed to other lanes — 4 independent signals, not one:**

| failure | attribution evidence |
|---|---|
| `lib/test_vendor_identity.py` ×3 | failure text names a mismatch between `receipt.schema.json` and `VENDOR-REGISTRY.json` — BOTH modified by the D1 lane after this unit started, NEITHER touched by this change; all 3 pass on re-run |
| `lib/test_completion_predicate.py::test_cli_exits_zero_on_complete_and_one_on_incomplete` | `completion_predicate.py:47-48` imports `vendor_identity`, and the test passes `--require-cross-vendor-review` which resolves against `VENDOR-REGISTRY.json` (`:933`) — same in-flight lane; passes on re-run |
| `lib/test_schema_resolver.py` ×2 | those two test functions **no longer exist**: the D1 lane replaced them between the run and the re-run (`test_the_authorized_delta_guard_fires_on_an_unauthorized_edit` -> `test_the_generated_vendor_layer_guard_fires_on_an_unauthorized_edit`, and the "differs from HEAD ONLY by the authorized d1 delta" test is gone). That guard is the known moving-reference anti-pattern HEAD `29f4c72a` was already titled after |
| `coordination/test_oslock.py::test_probe_discriminates_alive_from_dead` | a process-liveness discrimination probe; 144 python processes were live during the run. `7 passed` in isolation |

Two structural cross-checks: (a) `grep` for `workflows`, `workflow_id_index`, `TOURNAMENT-WINNER`,
`fused.cnc07` in every failing file returns **0** — no overlap with this change's surface; (b) the
two runs' failure sets are **disjoint**, and a deterministic regression from deleting a file would
fail in the same place every run.

## 10. Residual / left for the owner

| item | verdict |
|---|---|
| `routing/index.py:445-450` still silently `continue`s on an already-seen id | NOT CHANGED. It is a latent false-green of the "guard that converts a bug into a green" shape: a genuinely divergent duplicate would also be swallowed there. Left alone because that file belongs to the routing lane. The new gate is the positive N-of-N assertion that makes the silent dedupe non-load-bearing, but the dedupe itself should become an assert-or-raise. **Owner/routing-lane decision.** |
| the comment at `routing/index.py:446-450` ("the foundry writes a fused blueprint twice") | now STALE — it documents the state this change removed |
| ids outside `platform/workflows/` (protocols, presets, the 2,007-unit catalog, the 103-item register) | NOT-CHECKED. Different namespace, different lane. The uniqueness gate here is scoped to `platform/workflows/**/*.json` and says so. |
| `_regen_forged.py`, `_d4_*.py` | untracked scratch (`_` prefix). The durable protection is the test, not these scripts. |
