# P10 — Condition-11 refutation attempt + re-review of the five applied fixes

**Reviewer of record** · `independent: true` · **`fresh_context: false`** — same agent as this
session's routing-hermetic, reference-triage and first P10 review. I had **not** previously seen
`completion_predicate.py`, `STRUCTURAL-CONDITION-11.md` or `_USER-PROMPTS.md:10643`. Independent of
the AUTHOR and fresh on TASK A's subject matter; not context-free about this session.

**COVERAGE — MEASURED:** all five TASK A attack surfaces, all five TASK B fixes, the four new tests
under mutation. Every finding below was executed. Nothing is unchecked.

## VERDICTS

| | |
|---|---|
| **TASK A** | **PARTIAL** — the headline sentence is **REFUTED**; the underlying finding **survives**. Confidence **almost certain (90-99%)**, executable. |
| **TST-0334** | **PASS** |
| **TST-0350** | **PASS** |

**Do NOT retract the document — RE-SCOPE it.** Retracting would discard a real finding. The correct
title is the one you already anticipated in attack 5: *the wrong manifest is named*, not *condition
11 is structurally unsatisfiable*.

---

# TASK A

## The refutation, executed

`_c11_manifest` resolves `receipt.manifest_registration.manifest_path` **as given**
(`completion_predicate.py:1026`), and the receipt schema types that field as a bare
`{"type": "string", "minLength": 1, "maxLength": 1024}` — **no enum, no const, no pattern**. Nothing
in the repo pins it to the contracted file (`git grep manifest_path -- '*.py'` outside the predicate
returns only unrelated skills). So I built a receipt and asked the real evaluator:

| manifest named | `Outcome` |
|---|---|
| `command-center/ARTIFACT-MANIFEST.json` (your premise) | `UNSATISFIED` |
| a temp manifest with an **empty** `artifacts` array (**negative control**) | `UNSATISFIED` |
| **a purpose-built manifest naming the artifact + sha256** | **`SATISFIED`** |
| same, with the **LF-normalised** digest | **`SATISFIED`** |
| purpose-built manifest but `registered: false` | `UNSATISFIED` |

The negative control is what makes this evidence rather than a green light: the detector still
fails on a manifest that omits the artifact. **Condition 11 is satisfiable.** The sentence
"unsatisfiable for EVERY work unit, so no unit can ever reach SUCCESS" is false as written.

## Attack-by-attack

**1. `_primaries()` — you were right, and it is WIDER than you assumed.** `completion_predicate.py:314`
is `primary or arts`: artifacts with `role == "primary"`, falling back to **all** artifacts when none
declares the role. It is never empty unless the receipt has no artifacts at all, so there is no
vacuous-pass hole. **This strengthens your claim.** Not refuted.

**2. The `Outcome` does block.** `evaluate()`'s docstring is explicit: *"An UNSATISFIED or NOT-CHECKED
on any condition blocks completion; NOT-APPLICABLE is never counted as a pass."* They differ in
reporting, not in gating. **Your inference was correct.** Not refuted.

**2b. I checked an escape hatch you did not mention — it is closed.** `evaluate()` consults
`_waiver(n, opts)` first, so a unit class can declare a condition inapplicable. But
`NON_WAIVABLE = {1, 2, 3, 4, 5, 11, 12}` includes **11**, and `_waiver` returns UNSATISFIED with
*"a waiver of a structural condition is a failure of that condition, never a pass"*. **Strengthens
your claim.**

**3. The manifest you missed — this is the refutation.** See the table above. Your option 1 is not a
proposal; the code and schema already permit it. What is *not* already permitted is registering a
unit artifact in the **contracted** manifest: `render.py:36` fixes it to 14 names and regenerates it,
and the on-disk file has exactly 14 entries, all `command-center/*`, all with sha256.

**4. Your census is HONEST.** Verified all three receipts: `BLD-0023`, `TST-0334`, `TST-0350` — every
one `state=BLOCKED`, `registered=false`, `manifest_path=command-center/ARTIFACT-MANIFEST.json`. And
the generalisation is **mechanism-based, not n=3**: of the 2,007 `work_units`, **0** declare an
`output_path` that is one of the 14 contracted artifacts (all 2,007 write under `command-center/`,
none to a contracted name). So *given the current convention*, no unit can satisfy C11 — which is
exactly why the finding survives even though the headline does not.

**5. The spec anchor does NOT settle it your way.** `_USER-PROMPTS.md:10643` (found at
`~/.claude/harness-restore-20260806/_USER-PROMPTS.md`, not in this repo) reads:

> `11. output was registered in the artifact manifest;`

**"the artifact manifest"** — definite article. Your hypothesis was that "a manifest" would settle
option 1; it says the opposite. **Your attack-5 expectation is inverted:** the re-scope is authorised
by the CODE and SCHEMA, not by the spec. The spec is silent on *which* file, and the implementation
deliberately made the path a free field — that gap between a definite-article spec and a free-string
implementation is the actual defect worth writing up.

## Correction to my own earlier review

In my first P10 review I read `detail["claimed_registered"] = reg.get("registered")` as record-only
and said the predicate does not gate on the flag. **That was wrong.** `_c11_manifest` ends with
`if reg.get("registered") is not True: return UNSATISFIED, "receipt itself records registered=false"`.
Both the manifest presence AND the flag are required.

## What the document should say instead

Condition 11 is satisfiable, but **unsatisfied for all 2,007 units under the current convention**,
because every receipt names a manifest that is machine-generated from a fixed 14-name tuple and no
unit produces one of those 14. Fix is a choice, not a redesign: (a) point `manifest_path` at a
per-unit or per-program manifest that receipts may append to, or (b) extend `CONTRACTED_ARTIFACTS`
/ `render.py` to carry unit outputs. Both are already legal under the schema.

---

# TASK B — all five fixes CLOSED

| # | fix | status |
|---|---|---|
| 1 | member extracted with `tarfile`, `--format=tar` pinned, false comment gone | **CLOSED** |
| 2 | `git_archive` inside the LF-normalisation control | **CLOSED** |
| 3 | per-package floors close the corpus bypass | **CLOSED** |
| 4 | CI wiring 1 scoped to `--suite command-center` | **CLOSED** |
| 5 | docstring no longer asserts the retracted `require_nonempty` claim | **CLOSED** |

**Fix 1 goes further than I asked, and corrects ME.** My review said "git archive returns the
worktree bytes". The narrower truth, which you measured on a Linux runner (29 B / 0 CRLF against a
32 B / 3 CRLF worktree), is that archive applies export-time EOL conversion **where configured** —
Windows+autocrlf yes, stock Linux no. The new test branches on measured behaviour rather than
`sys.platform`, keeping a discriminating assertion on both platforms. That is a better fix than the
one my finding implied.

**Fix 3 verified both-states, in-process, no file edit.** Healthy tree → `exit 0`,
`collected 3946 >= floor 3900 (+6 package floors)`. Corpus floor forced above its real count while
the **total stays green** → `exit 1` and the message NAMES the package:
`whole-suite total 3946 clears 3900, but package platform/corpus collected 45, below its floor …`.
Restored → `exit 0`.

**Your floors are well calibrated** — I measured slack against live counts:

| package | observed | floor | slack | files ≤ slack |
|---|---|---|---|---|
| `platform/lib` | 3132 | 3000 | 132 (4.2%) | 82 (biggest **120**) |
| `platform/plugin` | 252 | 240 | 12 (4.8%) | 0 |
| `platform/coordination` | 232 | 220 | 12 (5.2%) | 3 (biggest 12) |
| `platform/marketplace` | 164 | 155 | 9 (5.5%) | 0 |
| `platform/routing` | 121 | 115 | 6 (5.0%) | 0 |
| `platform/corpus` | 45 | 40 | 5 (11%) | 0 |

Neither nuisance-tight nor uselessly loose: a consistent ~4-5% band. My exact bypass is dead —
`corpus` now has **zero** files that fit inside its slack, so not even one file can vanish there,
let alone the package. **Disclosed residual, not a re-opened finding:** `platform/lib`'s 132-test
slack still admits one 120-test file silently. That is inherent to any floor and is an order of
magnitude smaller than a whole top-level package. Closing it would need floors one level deeper
inside `lib`; your call whether that is worth the churn.

**Fix 4 — you are right and I was wrong.** I predicted the step would go RED; CI run 31410194562
passed because earlier steps pull `jsonschema-4.26.0` in transitively. That is precisely the residual
I flagged UNVERIFIED in my own review, and it obtained. **My prediction is REFUTED; I am not pushing
back.** The fragility was real and you fixed it, and you found a sharper point I had missed: the two
jobs would otherwise validate `platform` under *different* jsonschema versions (4.26.0 transitive vs
4.25.1 pinned). Wiring now reads `python tools/measure-guard/suitefloor.py --suite command-center`.

**Discrimination: 24 baseline green, 4 new-behaviour mutations, 0 survivors.**

| mutation | result |
|---|---|
| per-package check never fires (`pkg_observed < 0`) | KILLED (1 failed) |
| per-package loop skipped entirely | KILLED (1 failed) |
| archive route stores the CONTAINER again | KILLED (3 failed) |
| `git_archive` renamed back out of the LF control | KILLED (2 failed) |

Every restore verified by sha256 **and** `git diff --quiet`. Final state: `git status --porcelain`
shows **no modification** to `tools/measure-guard/`, `.github/workflows/` or
`command-center/receipts/`, and both modules hash-match their HEAD blobs.

## What still blocks the receipts

Unchanged from my first review and independent of my PASS: `receipt_core.allOf[0]` also requires
`manifest_registration.registered == true` and no `downstream_consumers` entry with
`executed:false` / `read_ok:false`. Both receipts still carry all three. **TASK A now gives you a
legal route to the first of those** — name a manifest you can actually append to.

Nothing committed, pushed, or left modified. Probes in
`C:/Users/Prekzursil/AppData/Local/Temp/p10-c11/`.
