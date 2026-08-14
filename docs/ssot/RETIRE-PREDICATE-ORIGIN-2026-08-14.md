# The retire predicate, re-based on `origin/main` — 4 commits exist nowhere else

Ranked action #7 from the synthesis lane: *"Re-run the SSOT retire-candidate predicate against
`origin/main` before retiring anything; 4 of 43 currently fail the lane's own stated criterion."*

Done. The overclaim is **CONFIRMED**, the four are now **named**, and the exposure turns out to
be much smaller and much sharper than "4 checkouts": **4 commits**, holding **3,630 insertions**
of real feature work that exists in exactly one place on this disk and in no remote.

## Why the original predicate was too weak

`classify_population.measure_unique` counts unpushed work with:

```
git rev-list --count HEAD --not --remotes
```

`--remotes` is the checkout's **own remote-tracking snapshot** — local state, whatever that
clone last fetched. A stale ref, or one pointing at a branch since deleted on the server, still
satisfies it, so commits that are *not* on the real remote can count as pushed. The criterion
the SSOT rule actually states is "no unique commits … on a pushed branch". 43 candidates were
published against the weaker test, and retiring on a false "0 unpushed" destroys the only copy.

## Method, and the three-state trap

Every candidate is a checkout of this same project, so genuinely-pushed work is reachable from
this repo's freshly-fetched `origin/main`. No fetch in 43 other repositories is needed.

`git merge-base --is-ancestor` returns **0 = yes, 1 = no, 128 = could not be asked** (the object
is not in this store at all). The inventory's round-1 defect was comparing `== 0`, filing 128 as
a plain "no". Here 128 is its own verdict — an object we cannot even name is the *strongest*
signal the work is unshared, never a soft negative.

Both detector arms were controlled before any verdict was read: a known-pushed commit must read
`PUSHED` and a fabricated sha must not. Without both, "everything is pushed" is indistinguishable
from a predicate that always says yes.

## Result: 39 of 43 safe, 4 not (+1 already gone)

| checkout | verdict | commits | **absent from canonical** |
|---|---|---:|---:|
| `.claude/harness-restore-20260806/wave3/ast-cc` | NOT-PUSHED | 297 | **0** |
| `source/_verify/v-l01` | NOT-PUSHED | 3 | **0** |
| `source/_wu2/lf2-C26` | UNKNOWN-OBJECT | 409 | **1** |
| `D:/pr-b3-clone` | UNKNOWN-OBJECT | 228 | **3** |
| `…/scratchpad/clonecheck` | GONE | — | — |

**The two NOT-PUSHED rows hold no unique content.** All 297 and all 3 of their commits are
already in the canonical store; their HEADs simply are not ancestors of `origin/main` — unmerged
side branches. Retiring them loses a *branch pointer*, not history. That distinction is invisible
to the HEAD-only gate and is why the commit census was worth running.

## CORRECTION (same day, after this document was first committed)

**The "3,630 insertions … with no remote copy" figure below is WRONG by roughly 24×, and the
error is mine.** The real content-level exposure is **at most 151 lines**, and most of that is
superseded text rather than novel work.

The commit census asked *"is this COMMIT in the canonical object store"* and answered correctly:
4 commits are absent by SHA. I then inferred that their **content** was absent. **Commit-SHA
absence is not content absence** — a commit can be rebased, squashed or re-committed downstream,
leaving the content present under a different SHA. That inference is precisely the failure
`rules/common/fan-out-contract.md` §C4 records: *a one-directional read cannot see
two-directional divergence.*

Measured with `command-center/ssot/_atrisk_content_census.py` (controls: an identical file
reports 0 unique lines, a different file reports 91):

| file | lines only in the clone | lines canonical has that the clone lacks |
|---|---:|---:|
| `.github/workflows/quality.yml` | 23 | **769** |
| `hooks/_dispatch/test_wiring.py` | 15 | **208** |
| `monitorcore/codex_tail.py` | 12 | 73 |
| `monitorcore/codex_source.py` | 10 | 72 |
| `tests/test_codex_tail.py` | 10 | **142** |
| …9 more | | |
| **total** | **151** | — |

**Every row is DIVERGED with canonical far ahead.** `D:/pr-b3-clone` is a *stale* checkout, not
a stranded one: the PR-B3 monitorcore work landed in canonical and was then developed well past
this clone. The live proof is that `mon cockpit` renders a working codex pane from canonical,
and `tools/monitorcore` passes **1,184 tests**.

**151 is an upper bound, not a count of lost work.** The differ compares by line-set membership,
so a line that was merely *reworded* upstream counts as "unique" even though its meaning is
superseded. The genuinely novel remainder is smaller still and was not separated out.

**What does NOT change:** the retire *gate* stands. `rev-list HEAD --not --remotes` really is
too weak, the corrected predicate really does fail these 4 candidates, and nothing should be
retired without checking. What changes is the **stakes** — this is stale-clone cleanup, not a
data-loss emergency. The overclaim is kept above rather than deleted, per the standing practice
that a claim wrong once will be wrong again if only its conclusion is edited.

## What would actually be destroyed (ORIGINAL TEXT — superseded by the correction above)

```
lf2-C26        76eae59  2026-07-30  "verify C26"                    16 files  +515 −67
pr-b3-clone    4320e93  2026-07-18  monitorcore codex_tail (WU1)     6 files  +2726
pr-b3-clone    b6d14eb  2026-07-18  monitorcore codex_source (WU2)   3 files  +793
pr-b3-clone    35c2650  2026-07-18  codexmon register + panel (WU3)  9 files  +111
```

`pr-b3-clone` holds **three complete PR-B3 work units of the monitorcore cockpit program** —
the Codex stream/rollout domain layer with redaction at ingest, the `CodexSource` adapter behind
the `MonitorSource` contract, and the cockpit registration/autolaunch. This is authored feature
work, not scratch, and it has no remote copy.

## Recommendation

* **Do not retire `lf2-C26` or `D:/pr-b3-clone`.** Push their branches first — that is the whole
  fix, and it converts both to ordinary safe candidates.
* **`ast-cc` and `v-l01` are content-safe**; retiring them costs only an unmerged branch pointer.
  Whether that pointer matters is an owner call, not a data-loss question.
* **The 39 remaining candidates pass** the stronger criterion.

Not pushed here: pushing another repository's branches is an outward-facing action on work this
session did not author, and `D:/pr-b3-clone` is a separate checkout with its own remote config.

Receipts: `command-center/ssot/retire_predicate_origin.py` ·
`command-center/ssot/retire-predicate-origin.json` ·
`command-center/ssot/_atrisk_commit_census.py` ·
`command-center/ssot/atrisk-commit-census.json`.
