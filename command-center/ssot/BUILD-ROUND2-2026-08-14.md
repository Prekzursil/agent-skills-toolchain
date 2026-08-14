# LANE SSOT — BUILD round 2 (re-entry after a CONFIRMED defect)

STATUS: **both milestones measured.** Every claim below names the command that produced it.

If any row still reads `UNKNOWN - not yet measured`, the unit died before measuring it and no
verdict there may be cited. (None does.)

---

## 1. The CONFIRMED defect, reproduced independently

    command-center/ssot/identity_by_ancestry.py:71   (round 1)
    return rc(["git", "merge-base", "--is-ancestor", root, "HEAD"], path) == 0

`--is-ancestor` answers with three codes: 0 ancestor, 1 genuinely-not, **128 fatal — the root
object is not in this store, so the question could not be asked**. `== 0` folds 1 and 128 into
one `False`: an error recorded as a confident negative.

`rc128_redproof.py` — control fails closed unless all three codes occur:

    distinct candidates : 295      no HEAD : 2
      rc=0 rows=168 | rc=1 rows=105 | rc=128 rows=20
    CONTROL distinct rc codes observed: [0, 1, 128]  three-way=True

    rc   OLD (== 0)    NEW (3-way)
    0    True          ancestor
    1    False         not-ancestor
    128  False         undecidable
    OLD conflates rc=1 with rc=128 : True   <- the defect
    NEW separates them             : True   <- the fix

**105 + 20 = 125 — exactly round 1's published "REJECTED : 125".** The arithmetic closes, so
those 20 rows were provably inside that bucket with no identity ever determined.

This is the lane's own recorded lesson, unapplied one file over: `salvage_atrisk.py:24-28`
already documents the identical shape and its fix ("prints the query's return code so the silence
cannot be mistaken for an answer again"). The fixed file now prints an rc histogram, not verdicts.

## 2. My own first fix was defect 2 again — caught before shipping

First rule tried: `origin_match OR census >= 0.5`, justified on error direction (inclusive errors
inflate a count; exclusive ones drop a checkout holding the only copy of something). It printed
**12 disagreeing rows**, and they were vendored third-party clones — the failure
`identity_by_ancestry.py`'s own defect 2 already records:

| row | census | truth |
|---|---|---|
| `dsifry/metaswarm` ×3 | 95–96% | this repo VENDORS metaswarm |
| `Prekzursil/openmm-md-mcp` | 67% | this repo vendors its skill |
| `blader/humanizer` | 50% | likewise |

**Printing the disagreement is what caught it.** Over all 22 residual rows the blob census alone
is wrong 8 times, every one inflating. `resolve_identity` now records the census and never lets it
decide: origin naming this repo wins · origin naming another REMOTE is an authoritative negative ·
a LOCAL-path origin resolves transitively · only with no origin does a root-marker test decide.

Origin outranks markers because it was **measured** to: a genuine clone of this repo scores 3/10
markers while a vendored metaswarm clone scores 4/10. Printed as a control, not asserted.

## 3. A second control save: the marker threshold

At `MARKER_MIN = 3` the both-states control **FAILED and the probe refused to run** — the known-
vendored negative scores 4/10 and would have been admitted. The threshold is set by the control
(above the measured negative 4, below the lowest true positive 6), not by fitting rows. At 5 the
control passes and no verdict on this population changes.

    CONTROL positive (real checkout)  : 10/10
    CONTROL negative (vendored clone) :  4/10   discriminates: True
    CONTROL genuine-but-old clone     :  3/10 vs vendored 4/10 -> markers usable alone: False

## 4. The corrected count

| figure | value |
|---|---|
| ancestry-confirmed (rc=0) | 168 |
| 0-commit working copies confirmed | 2 |
| rc=128 rows resolved as checkouts | 8 |
| **CORRECTED TOTAL** | **178** |
| round 1 published (rc=128 silently dropped) | 170 |
| the old name-based test still reports | 26 |
| the inventory / CLAUDE.md published (now corrected) | 25 |

REFUTED, recorded not deleted: round 1's "the real count is 170, not 25". 170 was measured over a
population that had silently dropped 20 undecidable rows.

---

## 5. The full 178, classified — `classify_population.py`

Round 1 made the count honest and thereby created the lane's largest gap: 27 of 170 classified.
This closes it over all 178. An algorithm, not a fan-out — every axis is file-vs-directory, set
membership or counting, and `fan-out-contract.md` §C4 measured that class handed to LLM judgement
at 86% accuracy with **100% of errors pointing at data loss**.

| axis | measured |
|---|---|
| population | **178**, all still on disk |
| linked worktrees | 9 |
| independent clones | 168 |
| kind signals disagree | 1 |
| distinct object stores | 168 |
| named by live harness config | **3** |
| unpushed / dirty / staged | **132** |
| no remote at all | 5 |
| clean + referenced by nothing + has remote | **43** ← retire candidates |

Three both-states controls, all passing: known worktree FILE/outside vs known main checkout
DIR/inside · dirty counter 315 on a known-dirty tree, 2 on the other · known-referenced path found
(12), fabricated path not found (0).

**The 132 is the number that matters, not the 178** — the fleet's uncommitted-work surface, 5.3×
the population this lane was originally scoped to.

## 6. The finding that changes a verdict

`~/source/ast-harness-reconcile` is named by `.codex/.codex-global-state.json` at
`local-projects.<uuid>.rootPaths[0]` — a field Codex **reads** to resolve a registered local
project. The inventory's §4 lists that path as a RETIRE candidate and §5's rule says "no
config/task/hook/skill may reference one". A live tool is registered against a checkout the
document calls disposable. Second time this same path has broken a §4 verdict (the `refs/stash`
correction was the first).

**Detector honesty:** the first version of the inbound scan reported 5 referenced checkouts. Two
were artifacts of the naive "executable extension ⇒ dependency" rule the inventory itself warns
about — `.codex/plugins/cache/**` audit JSON naming worktree paths, and a plugin-cache copy of
this repo whose `tools/crcp/**` test fixtures name their own directory. Splitting hits by whether
the naming file lives inside the population removed both; a both-states control confirms the
filter does not also remove canonical's real hits.

---

## Definition of Done (lane), re-scored

| DoD item | status |
|---|---|
| every clone classified worktree-vs-clone by measurement | **PASS** — 178/178, two agreeing signals, 1 row reported as disagreeing rather than guessed |
| unique-content measured per clone | **PASS** — unpushed + dirty + staged for all 178; `null` with a reason for the 5 remote-less, never a false 0 |
| inbound-reference measured per clone | **PASS with a named residual** — all 178 scanned, 3 hits; field-level key resolved by hand for 2 of 3, `Documents/Playground` not re-resolved |
| a one-sentence SSOT rule written | **PASS** — unchanged; gate green (6/6 wires, 16/16 tests) |
| nothing deleted | **PASS** — every probe read-only; 178/178 still on disk, measured after |

## Residuals

1. `Documents/Playground`'s 6 hits not resolved key-by-key. Settling: resolve each to its TOML key.
2. The 5 remote-less checkouts report `unpushed = null`. Settling: test each commit's presence in
   canonical's store.
3. A fork of this repo that re-pointed its origin would be misfiled `not-ours` by the
   other-remote branch. Not observed. Settling: fetch each other-remote row and test ancestry there.
4. 43 retire candidates identified; **nothing retired, nothing deleted.** `git worktree remove`
   follows junctions and deletes their targets (measured 2026-08-10, not re-verified). Prefer
   moving a directory aside.
5. Never run a `worktree` subcommand from `.codex/plugins/cache/**` — `git worktree repair`
   rewrites links bidirectionally and would repoint the real worktrees at the cache.
6. Not pushed. Local `main` is ahead of `origin/main`.
