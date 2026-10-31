---
title: P2NEXT-GROUNDING
type: note
permalink: dqverify-repo-20261013/command-center/p2-next/p2-next-grounding
---

# P2NEXT — GROUNDING lane: the 48 blocked units, split by what they actually demand

**Measured 2026-08-12** against `ast-integrate` @ `ae8205a4` (worktree of `agent-skills-toolchain`,
branch `main`). Lane wrote **no production code**: three measurement scripts under
`command-center/p2-next/` and this document.

COVERAGE: sections 1-6 MEASURED and executed. Section 7 (external SOTA) is fetched, URLs cited.
Section 8 is a plan, not a measurement. Two claims carry inline UNVERIFIED tags with their settling
experiments named. Nothing here is recalled — every number was produced by a command in §9.

---

## 0. Headline — three corrections to the brief, all measured

| Briefed | Measured | Why it moved |
|---|---|---|
| **48** units self-declared BLOCKED | **51** | The corpus grew since the brief. Confirmed by two mechanically independent probes (§2). |
| **43 of 47** name a cross-vendor gate | **41 of 51** are genuinely rail-blocked | Not the same computation. The briefed figure came from a line that sums *tag occurrences*, not units (§1). |
| the satisfiable subset is "several" | **10** units, of which **7** need only a review | The other 3 carry a second, non-review blocker (§4). |

**The one thing that must not happen** is the thing I nearly shipped: an intermediate version of my
own resolver said **32 satisfiable / 19 rail-blocked**, and it was wrong in the dangerous direction.
See §3 — it would have dispatched same-vendor Claude reviewers at 22 units whose own receipts
disqualify a Claude reviewer *by name*.

---

## 1. The briefed "43" is a tag-sum, not a unit count

`command-center/blocker_census.py` is good prior art and its structured pass is correct. Its
**headline line is not**:

```python
review = sum(n for c, n in structured.items() if "review" in c.lower() or "refut" in c.lower())
print(f"  tags naming an independent/cross-vendor REVIEW gate: {review}")
```

It sums how many times review-ish tags *occur*; a receipt carrying three of them contributes three.
Run today it prints `51` directly beneath `BLOCKED/FAILED receipts found: 51`, which reads as
"every receipt is review-gated" and is not what was computed. Measured separately:

```
tag OCCURRENCES : 137
distinct UNITS  :  51
```

A suspiciously equal pair of numbers on two sides is usually a collection-level mistake rather than
real parity, and that is what this is. The census is still the right tool for *why* units are
blocked — it is simply not a unit counter. `command-center/p2-next/split_review_gate.py` counts
units, once each.

---

## 2. There are 51, not 48 — two independent probes

| probe | mechanism | result |
|---|---|---|
| catalog-driven | walk `WORK-UNIT-CATALOG.json` `work_units[].output_path`, read `state` | **51** |
| disk walk | `rglob('*.json')`, keep files carrying both `unit_id` and `state` — never consults the catalog | **52 distinct**, of which 1 is `ZZZ-9999` |

`ZZZ-9999` is not a work unit: it exists only as
`command-center/p2-wave/_r2_tmp/{cc0002,selftest}-m3-unit-id-not-in-catalog.json`, a
deliberately-broken detector fixture whose filename states its purpose. Excluding it, both probes
land on the same 51 ids with **zero** set difference in either direction.

The disk walk also found 60 BLOCKED/FAILED *files* for those 52 ids. All 8 extras are accounted for
and none is a real unit: `TST-0334` ×4 and `ADV-0031` ×1 are mutation/selftest fixtures under
`_r2_tmp/` and `_av_tmp/`; `ADV-0021` and `ADV-0022` have a `casualty/` twin of the `adversarial/`
original. Counting files instead of catalog-resolved units would have inflated the answer by 9.

---

## 3. The measurement that inverted — record it, do not bury it

**REFUTED: my own v1 result of "32 SATISFIABLE / 19 RAIL_BLOCKED". Do not cite it.**

v1 resolved "cross-vendor" against the catalog's `assigned_model_vendor_role.vendor` and found 22
blocked units assigned to `openai`. For those, cross-vendor appears to resolve to an *Anthropic*
reviewer — available right now, rail or no rail. That looked like the highest-value finding of the
lane.

It is the wrong field. The catalog records the vendor a unit was **assigned** to; the receipt's
`produced_by.vendor` records who **actually built it**. They diverge for exactly 22 units — and they
diverge *because* the rail has been down, so work planned for Codex was executed by Claude.

`ADV-0003` states the trap in its own artifact, in plain language
(`command-center/adversarial/ADV-0003-exit-zero-missing-artifact-injection.json`, `reviewer.notes`):

> "The catalog also assigns this unit to openai/gpt-5-codex; **it was in fact produced by
> anthropic/claude-opus-5, which makes an Anthropic reviewer SAME-vendor and therefore
> non-qualifying by the unit's own rule.** A qualifying refuter is openai/gpt-5-codex."

Measured across all 51: `produced_by` is `anthropic` for **49**, and absent on 2 (`TST-0334`,
`TST-0350` — assumed anthropic, disclosed in the output). Zero were produced by Codex. So the
assignment field inverts the answer on precisely the units where it matters, and acting on v1 would
have satisfied the gate's letter while defeating its purpose — the single outcome this lane was told
not to produce. The regression is pinned by a selftest case in the shipped script.

### 3b. Sixteen units carry a self-contradictory requirement

16 blocked units share this exact `reviewer_requirement`:

> "one **cross-vendor Anthropic (opus) refuter** who re-derives the counterexample from the raw
> artifact and NOT from this unit's report; **a same-vendor reviewer shares this unit's blind spots
> and does not satisfy the requirement**"

All 16 were produced by Anthropic. The two clauses cannot both hold: an Anthropic refuter *is* the
same vendor. The sentence is coherent only under the assignment that never happened.

13 of the 16 receipts reasoned this out and wrote an openai refuter into `failure.blocked_on`. Three
— `ADV-0010`, `ADV-0011`, `ADV-0016` — merely echoed the catalog text, and on prose alone would
classify as satisfiable. Identical requirement plus identical producer must not yield two different
answers because of receipt writing style, so the 13 that carry the *argument* govern the 3 that
carry only a restatement. All 16 resolve to **openai / RAIL_BLOCKED**.

---

## 4. THE SPLIT

**51 blocked · 41 RAIL-BLOCKED · 10 SATISFIABLE BY AN INDEPENDENT CLAUDE REVIEWER**

### 4a. Satisfiable now — 10 units, and the receipt text that says so

Seven of these ask for a same-vendor reviewer **explicitly**, so a fresh-context Claude agent that
did not build the unit is not a substitution — it is the thing the receipt names.

| unit | quoted `reviewer_requirement` / `blocked_on` | second blocker |
|---|---|---|
| `AUD-0006` | "one **fresh-context Claude reviewer** who has not seen this unit's transcript; the reviewer must try to FALSIFY the headline count before PASS" | none |
| `AUD-0020` | same requirement; `blocked_on`: "fresh-context Claude reviewer (reviewer_requirement)" | none |
| `AUD-0021` | same requirement; `blocked_on`: "one fresh-context Claude reviewer who never saw this transcript" | none |
| `AUD-0030` | same requirement | none |
| `AUD-0041` | same requirement | none |
| `AUD-0051` | same requirement | none |
| `CC-0002` | "**One independent reviewer** who writes a fifth mutant the author did not anticipate and confirms it is rejected." — no vendor constraint | none |
| `IMP-0440` | "**independent-claude-reviewer** re-measures the three-route comparison on a DIFFERENT file" | **cross-tree edit authority** (T5 FAIL) |
| `TST-0334` | "One independent reviewer who re-runs the probe under a SECOND Windows shell (pwsh7 and Git Bash)" | **needs a committed consumer of `blobread`** |
| `TST-0350` | "One independent adversarial reviewer in a fresh context who did not author the harness under test and who must reproduce the both-states control" | **first CI execution of the wired step** |

**7 units are review-only.** 3 need a review *and* a separate concrete thing, so a reviewer alone
will not move them to DELIVERED.

All 10 also carry `manifest_registration: false`, and that is **not** a review problem:
`ARTIFACT-MANIFEST.json` is a DERIVED file generated by `tools/command-center/render.py` from the
catalog, gated in CI at `.github/workflows/quality.yml:437` (`render.py --check`). It is a
one-command mechanical step. Open defects on all 10: **zero**, P0/P1: **zero**.

### 4b. Rail-blocked — 41 units

`ADV-0001 ADV-0003…ADV-0037 ADV-0039 ADV-0040 ADV-0042` (39 ADV) + `BLD-0023` + `IMP-0433`.

Decided by: 16 the self-contradictory requirement (§3b) · 9 requirement names a vendor differing
from the producer · 8 `blocked_on` names the refuter vendor outright · 8 undirected cross-vendor.

**This is the number to price `codex login` against: 41.**

---

## 5. Prior art — what already exists, so nothing gets rebuilt

| artifact | what it already establishes | status |
|---|---|---|
| `command-center/CROSS-VENDOR-RAIL-STATUS.md` | The rail is down; `claude mcp list` says Connected while a real call fails at `auth.openai.com/api/accounts/v1/agent/register`. Read-only credential diagnosis already done (`~/.codex/auth.json`, 215 B, key *names* only). Fix is `codex login` = owner-only. Already names the two paths and already warns against silent same-vendor substitution. | **Authoritative. Do not re-derive.** Its "43 units" figure needs the §1 correction. |
| `command-center/blocker_census.py` | Why units are blocked, by structured `classification` rather than prose. Documents the use-vs-mention correction it already made. | **Keep.** Headline line is a tag-sum (§1). |
| `command-center/D5-VENDOR-ROLE-CANONICAL.md` | `assigned_model_vendor_role` is canonical object form on all 2007 units; 497 distinct `reviewer_requirement` values, so the field is per-unit and not boilerplate. | Confirms my classifier reads real data. |
| `tools/command-center/render.py` | `STATUS.md`, `OWNER-DECISIONS.md`, `ARTIFACT-MANIFEST.json` are DERIVED; `--check` is a CI gate. | Answers the `manifest_registration` question mechanically. |
| `command-center/CODEX-STUB-RETIREMENT-LANE.md` | The nine `codex-*` skill stubs are ROUTED-BUT-BROKEN; the live rail is `mcp__codex__codex` only. | Rules out the stubs as an alternate review route. |

New this lane: `split_review_gate.py`, `vendor_satisfiability.py`, `REVIEW-GATE-SPLIT.json`,
`VENDOR-SATISFIABILITY.json`.

---

## 6. Detector discipline applied

Both shipped scripts refuse to run unless a selftest discriminates in **both** directions first, and
exit non-zero if it regresses:

- `split_review_gate.py` — 4 cases (cross-vendor tag, plain-independent tag, catalog-vendor
  requirement, no-gate).
- `vendor_satisfiability.py` — 5 cases, one of which is **the v1 bug itself**: an
  anthropic-named requirement on an anthropic-produced unit must resolve to `openai`. If a future
  edit reintroduces the assignment-field reading, that case fires.

---

## 7. External SOTA — and it partly undercuts the gate's own premise

Fetched 2026-08-12.

1. **Self-preference is real and large.** LLM judges score their own outputs higher — ~10% for
   GPT-4o, ~25% for earlier Claude models — driven by perplexity/familiarity rather than quality
   ([arXiv 2410.21819](https://arxiv.org/html/2410.21819v1)). This *supports* the receipts'
   refusal to self-certify.

2. **But cross-vendor is not independence.** "Nine Judges, Two Effective Votes"
   ([arXiv 2605.29800](https://arxiv.org/html/2605.29800v1)) measures a 9-judge panel at
   **n_eff ≈ 2.2 effective independent votes**, mean pairwise error correlation **φ̄ = 0.391**, a
   22-point Condorcet gap. Critically: **cross-family pairs can be as correlated as same-family
   ones** — Claude × Gemini φ = 0.603 versus OpenAI-internal φ = 0.437. Corroborated by
   [Correlated Errors in LLMs](https://arxiv.org/html/2506.07962v1) (PMLR v267): models agree ~60%
   of the time *when both are wrong*, and larger/more accurate models have **more** correlated
   errors even across providers.

**What this means for the owner's decision.** The vendor label is the *weaker* half of these gates.
The load-bearing half is the clause most of these receipts already carry — *"re-derives the
counterexample **from the raw artifact** and NOT from this unit's report"*. Re-derivation by
execution is mechanically independent; a vendor swap alone buys less than the receipts assume.
`codex login` is still worth doing (it is one command and unblocks 41 units on their own stated
terms), but it should be priced as *satisfying the recorded contract*, not as *achieving
independence*.

---

## 8. RANKED PLAN

**R1 — Review the 7 review-only units now. No rail, no owner, no ambiguity.**
`AUD-0006 · AUD-0020 · AUD-0021 · AUD-0030 · AUD-0041 · AUD-0051 · CC-0002`. Six of the seven ask
for a "fresh-context Claude reviewer" in those words; `CC-0002` sets no vendor constraint and asks
the reviewer to author an unanticipated fifth mutant. One fresh-context agent per unit, none of
which may have built it. This is the whole no-regret subset.

**R2 — Run `python tools/command-center/render.py` once.** Clears `manifest_registration: false`
across all 10 and is already CI-gated at `quality.yml:437`. Mechanical; not a review.

**R3 — Put the exact number in front of the owner: 41 units, one command.**
`CROSS-VENDOR-RAIL-STATUS.md` already carries the diagnosis and the `codex login` recommendation;
this lane supplies the price tag and the §7 caveat that cross-vendor ≠ independent. Owner action —
do not attempt the credential write.

**R4 — Clear the second blocker on the 3 partials, then review them.** `IMP-0440` needs cross-tree
edit authority; `TST-0334` needs a committed consumer of `blobread`; `TST-0350` needs its wired CI
step to execute once. Each is a small, separately-ownable unit of work.

**R5 — Fix the two counting defects so the next lane inherits correct numbers.** Correct
`blocker_census.py`'s headline to report units (or delete the line), and correct the "43" in
`CROSS-VENDOR-RAIL-STATUS.md` to 41-of-51 with the §3 reasoning.

**R6 — Owner decision, explicitly labelled: interim execution-grounded review for the 41.** §7 says
the vendor label buys less independence than assumed, while *re-derivation from the raw artifact by
execution* buys real independence. A fresh-context Claude reviewer who **re-runs each unit's probe
scripts** and re-derives the counterexample would satisfy the load-bearing clause while failing the
vendor clause. **I am not recommending this be done silently, and it must not be recorded as
satisfying a cross-vendor gate.** It is offered as an owner-visible partial with its own receipt
classification, because 41 units sitting behind one credential write is a real cost. Confidence that
it is *weaker but non-zero* evidence: **likely (55-80%)**, on the §7 correlation numbers.

**DO NOT: build more READY units.** 449 are READY and the same gate awaits each one — building adds
artifacts to a queue that cannot drain.

### Residuals

- **UNVERIFIED [likely, 55-80%]** — `TST-0334` and `TST-0350` have no `produced_by` field; I assumed
  `anthropic` (the program default) and the assumption is printed in the script output. Both landed
  in the *satisfiable* bucket via a no-vendor-constraint requirement, so the assumption does not
  change their verdict. *Settling experiment:* read the two units' transcripts, or add
  `produced_by` and re-run — a one-line change to the count if either was Codex-produced.
- **UNVERIFIED [uncertain, 20-55%]** — that all 41 rail-blocked units would actually reach DELIVERED
  after a Codex review. I measured what each receipt *demands*, not whether a review would PASS.
  Open defects were checked only on the 10. *Settling experiment:* run the open-defect and
  `completion_sentinel` check across the 41 before pricing `codex login` as a 41-unit unblock.
- **NOT-CHECKED** — whether `codex login` actually fixes the `agent/register` failure.
  `CROSS-VENDOR-RAIL-STATUS.md` rates that *likely (55-80%)* against a competing
  entitlement explanation; I did not re-probe, and a credential write is owner-only regardless.

---

## 9. Reproduce

```
python command-center/blocker_census.py                        # prior art: why blocked
python command-center/p2-next/split_review_gate.py             # units, counted once each
python command-center/p2-next/vendor_satisfiability.py         # the 41/10 split, with selftests
```

Outputs: `command-center/p2-next/REVIEW-GATE-SPLIT.json`,
`command-center/p2-next/VENDOR-SATISFIABILITY.json`.