# LANE SSOT — BUILD round 2 (re-entry after a CONFIRMED defect)

STATUS: **MILESTONE 1 of 2 measured** — the rc=128 defect is fixed and proven both-states.
Milestone 2 (classify the full corrected population) is `UNKNOWN - not yet measured`.

COVERAGE: §1–§4 below are measured, each naming the command that produced it. §5 is not.

If §5 still reads `UNKNOWN`, the unit died before measuring it and no verdict there may be
cited.

## 1. The CONFIRMED defect, reproduced independently

    command-center/ssot/identity_by_ancestry.py:71   (round 1)
    return rc(["git", "merge-base", "--is-ancestor", root, "HEAD"], path) == 0

`--is-ancestor` answers with three codes: 0 ancestor, 1 genuinely-not, **128 fatal — the
root object is not in this store, so the question could not be asked**. `== 0` folds 1 and
128 into one `False`, so an error is recorded as a confident negative.

`command-center/ssot/rc128_redproof.py` — control requires all three codes to occur or it
fails closed:

    distinct candidates : 295      no HEAD : 2
      rc=0    rows=168
      rc=1    rows=105
      rc=128  rows=20
    CONTROL distinct rc codes observed: [0, 1, 128]  three-way=True

    rc   OLD (== 0)    NEW (3-way)
    0    True          ancestor
    1    False         not-ancestor
    128  False         undecidable
    OLD conflates rc=1 with rc=128 : True   <- the defect
    NEW separates them             : True   <- the fix

**105 + 20 = 125 — exactly round 1's published "REJECTED (store held the object) : 125".**
The arithmetic closes, so the 20 rows were provably inside that bucket.

## 2. What the 20 undecidable rows actually are

rc=128 has two causes with opposite verdicts, so the shallow flag alone is not the answer:
a shallow clone of THIS repo (history truncated past our root) versus an unrelated repo
whose store never held our root. Measured: 20 rows, 10 shallow, 4 with `origin` = this repo.

## 3. My own first fix was defect 2 again — caught before shipping

First rule tried: `origin_match OR census >= 0.5`, justified by error direction (an
inclusive error inflates a count; an exclusive one can drop a checkout holding the only copy
of something). It printed **12 disagreeing rows**, and they were vendored third-party clones
— the exact failure `identity_by_ancestry.py`'s own defect 2 already records:

| row | census | truth |
|---|---|---|
| `dsifry/metaswarm` ×3 | 95–96% | this repo VENDORS metaswarm |
| `Prekzursil/openmm-md-mcp` | 67% | this repo vendors its skill |
| `blader/humanizer` | 50% | likewise |

Printing the disagreement is what caught it. Measured over all 22 residual rows, **the blob
census alone is wrong 8 times, every one in the inflating direction.**

The rule chosen from that measurement (`resolve_identity`): origin naming this repo wins ·
origin naming another REMOTE is an authoritative negative · a LOCAL-path origin resolves
transitively · only where there is no origin does a root-marker test decide. Origin outranks
markers because a genuine clone of this repo scores **3/10** markers while a vendored
metaswarm clone scores **4/10** — markers cannot stand alone, and that is a printed control.

## 4. A second control save: the marker threshold

At `MARKER_MIN = 3` the both-states control **FAILED and refused to run** — the known-
vendored negative scores 4/10 and would have been admitted. The threshold is therefore set
by the control (above the measured negative 4, below the lowest true positive 6), not by
fitting rows. At 5 the control passes and every verdict on this population is unchanged.

    CONTROL positive (real checkout)  : 10/10
    CONTROL negative (vendored clone) :  4/10   discriminates: True
    CONTROL genuine-but-old clone     :  3/10 vs vendored 4/10 -> markers usable alone: False

## 5. The corrected count

| figure | value |
|---|---|
| ancestry-confirmed (rc=0) | 168 |
| 0-commit working copies confirmed | 2 |
| rc=128 rows resolved as checkouts | 8 |
| **CORRECTED TOTAL** | **178** |
| round 1 published (rc=128 silently dropped) | 170 |
| the old name-based test still reports | 26 |
| the inventory / CLAUDE.md still publish | 25 |

REFUTED, recorded not deleted: round 1's "the real count is 170, not 25". 170 was measured
over a population that had silently dropped 20 undecidable rows.

## 6. Classification of the corrected population — `UNKNOWN - not yet measured`

## Definition of Done (lane), re-scored

| DoD item | status |
|---|---|
| every clone classified worktree-vs-clone by measurement | UNKNOWN |
| unique-content measured per clone | UNKNOWN |
| inbound-reference measured per clone | UNKNOWN |
| a one-sentence SSOT rule written | PASS (unchanged; gate green) |
| nothing deleted | PASS so far — every probe read-only |
