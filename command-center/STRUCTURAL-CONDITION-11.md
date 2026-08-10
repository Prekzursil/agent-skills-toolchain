# Condition 11: satisfiable, but unsatisfied for all 2,007 units under the current convention

- **First written:** 2026-08-10, while trying to move TST-0334 / TST-0350 off `BLOCKED`
- **CORRECTED:** same day, after an independent refutation attempt. The original headline was FALSE.
- **Status:** the finding survives in a narrower form. Needs an OWNER choice, not a redesign.

## RETRACTION — read this first

The first version of this document asserted:

> Condition 11 is unsatisfiable for EVERY work unit, so no unit in the 2,007-unit catalog can ever
> reach receipt state `SUCCESS`.

**That sentence is REFUTED.** It is left quoted rather than deleted so the correction has lineage.

`_c11_manifest` resolves `receipt.manifest_registration.manifest_path` **as given**
(`completion_predicate.py:1026`), and `receipt_core` types that field as a bare
`{"type": "string", "minLength": 1, "maxLength": 1024}` — no enum, no const, no pattern. Nothing pins
it to the contracted file. Asked of the real evaluator rather than reasoned about:

| manifest named | `Outcome` |
|---|---|
| `command-center/ARTIFACT-MANIFEST.json` (the original premise) | `UNSATISFIED` |
| a temp manifest with an **empty** `artifacts` array (negative control) | `UNSATISFIED` |
| **a purpose-built manifest naming the artifact + sha256** | **`SATISFIED`** |
| same, with the LF-normalised digest | **`SATISFIED`** |
| purpose-built manifest but `registered: false` | `UNSATISFIED` |

The negative control is what makes that evidence rather than a green light: the detector still fails
on a manifest that omits the artifact. **Condition 11 is satisfiable.**

I had also written that "`manifest_path` is already a free field, so a receipt can name a per-unit
manifest" as *option 1, a proposal*. It is not a proposal. The code and schema already permit it, and
I did not check before framing it as future work.

## What survives, and it is still worth acting on

**Condition 11 is unsatisfied for all 2,007 units under the current convention.** Measured: of the
2,007 `work_units`, **zero** declare an `output_path` that is one of the 14 contracted artifacts —
they all write under `command-center/` but none to a contracted name. Every existing receipt names
`command-center/ARTIFACT-MANIFEST.json`, which `render.py:36` regenerates from a fixed 14-name tuple
and which holds exactly 14 entries, all `command-center/*`.

So the ceiling is real but it is a CONVENTION, not a structural impossibility. That distinction is
the whole correction.

Census, verified independently: `BLD-0023`, `TST-0334`, `TST-0350` — all three `state=BLOCKED`,
`registered=false`, `manifest_path=command-center/ARTIFACT-MANIFEST.json`. The generalisation to
2,007 rests on the output-path mechanism above, not on n=3.

## Three inferences of mine were STRENGTHENED, not merely confirmed

Recorded because they were the parts I was least sure of and explicitly asked to have attacked:

1. **`_primaries()` is WIDER than I assumed.** `completion_predicate.py:314` is `primary or arts` —
   artifacts with `role == "primary"`, falling back to ALL artifacts when none declares the role. It
   is never empty unless the receipt has no artifacts, so there is no vacuous-pass hole.
2. **`UNSATISFIED` does gate.** `evaluate()`'s docstring: *"An UNSATISFIED or NOT-CHECKED on any
   condition blocks completion; NOT-APPLICABLE is never counted as a pass."* UNSATISFIED and
   NOT-CHECKED differ in reporting, not in gating.
3. **The waiver escape hatch is closed**, which I had not thought to check. `evaluate()` consults
   `_waiver(n, opts)` first, but `NON_WAIVABLE = {1, 2, 3, 4, 5, 11, 12}` includes 11 and `_waiver`
   returns UNSATISFIED with *"a waiver of a structural condition is a failure of that condition,
   never a pass"*.

## My expectation about the spec anchor was INVERTED

I flagged `_USER-PROMPTS.md:10643` UNVERIFIED and predicted that if it said "a manifest" it would
authorise the per-unit route. It reads:

> `11. output was registered in the artifact manifest;`

**Definite article.** The spec does not authorise the re-scope; the CODE and SCHEMA do, by making the
path a free string. **That gap — a definite-article spec against a free-string implementation — is
the actual defect worth recording**, and it is a different defect from the one this document
originally claimed. A future reader could satisfy condition 11 by pointing at any file they like,
which the spec sentence plainly does not intend.

## Options for the owner

Both are already legal under the schema; this is a choice, not a redesign.

1. **Point `manifest_path` at a per-unit or per-program manifest** that receipts may append to.
   Cheapest, and already permitted — but see the definite-article gap above: doing this without
   tightening the field leaves condition 11 satisfiable by naming an arbitrary file.
2. **Extend `CONTRACTED_ARTIFACTS` / `render.py`** to carry unit outputs. Keeps one manifest, honours
   the spec's definite article, and changes the scope of a contracted artifact and therefore what
   `cc-render --check` gates.

Whichever is chosen, **tightening `manifest_path`** (an enum, or a pattern restricting it to a known
set) is worth doing alongside it, or condition 11 remains satisfiable by construction.

## Correction the reviewer made to its own prior review

Its first review said `_c11_manifest` records `registered` without gating on it. That was wrong:
the function ends with `if reg.get("registered") is not True: return UNSATISFIED, "receipt itself
records registered=false"`. **Both** manifest presence and the flag are required.

## Residual

- The 2,007-unit output-path census was run by the reviewer, not re-derived by me. **UNVERIFIED by a
  second party.** Settling experiment: intersect every `work_units[].output_path` with
  `render.CONTRACTED_ARTIFACTS` and assert the intersection is empty.
- Evidence: `command-center/P10-REREVIEW-AND-C11-REFUTATION.md`.
