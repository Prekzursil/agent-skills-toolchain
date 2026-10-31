---
name: claim-verify-gate
description: Use when an answer, research finding, audit verdict, or status report
  is about to be treated as true and the next action depends on it. Decomposes the
  answer into atomic, individually-checkable claims (SAFE, arXiv 2403.18802), runs
  Chain-of-Verification (arXiv 2309.11495 - draft, plan verification questions, answer
  them independently, revise), and re-probes each claim with a MECHANICALLY DIFFERENT
  instrument than produced it (different tool, engine, shell or measured field; re-running
  the same probe never counts as CONFIRMED). Emits a per-claim CONFIRMED / REFUTED
  / UNVERIFIED table with the settling experiment, and forces an overclaim to be rewritten
  to the scope actually measured - an honestly-scoped residual does NOT block. Ships
  scripts/claim_gate.py, a deterministic 10-rule checker with a built-in both-states
  self-test. NOT for build/test/lint claims (hooks/claim-guard and verification-before-completion
  own those), NOT a test runner, NOT a trained critic - no model judge, no new runtime.
permalink: dqverify-repo-20261013/skills/claim-verify-gate/skill
---

# claim-verify-gate

Turns two rules this estate already has - `AGENTS.md` §7 honesty and
`rules/common/single-signal-verification.md` - from a habit into a **gate with a
mechanical half**.

The premise, in the repo's own words:
`agent-self/config/AGENTS.md:70` - *"Sycophancy is in model weights;
external-signal checks are the only reliable counter."* A model re-reading its
own answer is not an external signal. So the parts of this gate that a model
could fake are handed to code (`scripts/claim_gate.py`), and the model is left
with only the part code cannot do: choosing a genuinely different instrument.

## When to run it

Run it when a claim is about to become **load-bearing**:

- a research answer, briefed "ground truth", or fan-in digest another agent will build on;
- an audit / review verdict ("the hook fires", "the config took effect", "nothing is enabled");
- a status report whose next action is disruptive (a restart, a kill, a re-fix, a rollback);
- any sentence containing an absolute (`all`, `every`, `zero`, `recall = 1.0`) or a bare hedge
  ("should work", "likely fine");
- before you hand a finding to an orchestrator - `single-signal-verification.md:50`, a
  subagent's finding is itself a single signal.

## When NOT to run it - route instead

This gate owns **claims about the world**. It does not own claims about your build.

| The claim is about | Use instead | Why |
|---|---|---|
| tests / build / lint / coverage passing | `hooks/claim-guard` (automatic) + `verification-before-completion` | already mechanised: a Bash-command ledger cross-referenced per claim category, per turn |
| whether the TESTS are strong enough | `mutation-check` | probes the tests, not the prose |
| one value you have leaned on for many steps | `fresh-context-verify` | re-derivation in a clean context, not a second probe |
| which of N candidate patches to pick | `rubric-verifier` / `execution-grounded-bon` | selection, not verification |
| how much test surface to run per edit | `two-tier-verify` / `smallest-check-ladder` | scheduling, not truth |
| whether the DELIVERABLE actually runs | `packaged-artifact-smoke` | needs an artifact, not a table |

If a claim spans both (an "it works now" claim resting on a research premise),
run `claim-guard`'s lane for the functional half and this gate for the premise.

## The loop (CoVe, four steps, in this order)

Chain-of-Verification (arXiv 2309.11495) is the shape: the model
(i) drafts, (ii) plans verification questions, (iii) **answers them
independently so the answers are not biased by other responses**, (iv) generates
the verified response. Step (iii) is the whole point; do not collapse it.

### 1. DECOMPOSE - atomic, individually checkable

SAFE (arXiv 2403.18802) breaks a long-form response into a set of **individual
facts** and checks each one separately. Do the same:

- one assertion per claim; if a sentence has two verbs it is two claims;
- resolve pronouns and "it" - each claim must stand alone out of order;
- separate the **measurement** from the **interpretation** ("connect took 0.10s"
  and "therefore CDP is fast enough" are two claims with different evidence);
- keep the premise: if a recommendation rests on a fact, the fact is its own claim
  and the recommendation inherits its verdict.

Record each as a row in the ledger (schema: `references/claim-ledger.md`), with
the `source_probe` that produced it. Naming the source probe is not bookkeeping -
step 3 cannot be checked without it.

### 2. PLAN the verification questions

For each claim write the question that would **falsify** it, not the one that
would confirm it. "Does `mon` resolve on PATH?" is confirmable by the broken
detector that produced the error; "which shell was asked, and does a *different*
shell agree?" is not.

Ask, per claim: what reading would I see if this were false? If the answer is
"the same reading", the probe is worthless - pick another.

### 3. RE-PROBE independently - the mechanically-different rule

`single-signal-verification.md:34`: the two signals must be mechanically
independent - *"a different shell, a different data field, a different
measurement ... not the same query re-run. Re-running the same probe is not a
second signal."*

The discriminating axes. A verify probe must differ on **at least one**:

| axis | example difference |
|---|---|
| `tool` | `curl` vs a Playwright client; arXiv API vs an HTML page fetch |
| `engine` | one search index vs another; a differ vs an LLM read |
| `shell` | PowerShell `Get-Command` vs Git-Bash `which` (misses `.cmd` shims) |
| `field` | process CPU-delta vs file mtime vs byte-count; `whoami` vs `account_list` |

`command` is deliberately **not** an axis. A different command string on the same
tool, shell and field is the same query re-run - that is exactly the shape
`fan-out-contract.md:25` measured, where two agents "CONFIRMED" a false briefed
fact by re-running the orchestrator's own broken Git-Bash `which`, evidence tags
and all.

Two further rules that carry their own cost history:

- **Verify the detector before trusting a silence** (`single-signal-verification.md:37`).
  A "0 results / not found" reading is often a broken matcher. Confirm the probe
  can find a known-present item first.
- **Both-states** (`:40`). Before a probe's silence counts as "fixed", run it
  against the known-BROKEN state and confirm it FIRES there. A probe silent in
  both states measures nothing. `claim_gate.py --self-test` does exactly this for
  the gate's own rules; do the same for yours.

### 4. REVISE - and rewrite the overclaim, do not delete it

`fan-out-contract.md:110` measured that **5 of 8** refuted claims were overclaims,
not broken work: *"the code was correct and the sentence was wider than the
evidence."* So the default repair is to the SENTENCE:

- state the scope actually measured, inline;
- disclose the residual inline, adjacent to the claim - not in a trailing
  limitations section (`fan-out-contract.md:17`; `:18` measured 40% of real flags
  parked in the final 15% of their document, where they qualified nothing);
- name the experiment that would settle the residual;
- record that the earlier wording was REFUTED. Do not silently delete it, or the
  dead end gets re-walked.

**A residual that is honestly scoped and disclosed is NOT a refutation and MUST
NOT block.** A correctly-scoped claim is CONFIRMED. This is the rule that keeps
"round N until fully green" tractable.

## The verdict table

Every claim ends in exactly one of three states. Ship the table, not prose.

| verdict | what it asserts | mandatory fields |
|---|---|---|
| `CONFIRMED` | an independent probe agreed | `verify_probe` differing on >=1 axis, plus >=1 `file:line` or URL anchor |
| `REFUTED` | an independent probe disagreed | `verify_probe`, plus `revised_text` scoped to what was measured |
| `UNVERIFIED` | not checked, or not checkable now | `settling_experiment` naming the probe that would decide it |

Attach a Sherman-Kent band to any forward-looking or uncertain claim, and never
ship the band as a bare tag name (`fan-out-contract.md:12`): **almost certain
90-99 - very likely - likely 55-80 - roughly even 40-60 - unlikely 20-45 - very
unlikely - remote 1-10 - almost certainly not**.

## The mechanical half - `scripts/claim_gate.py`

Ten yes/no questions that a model must not be trusted to answer about its own
output. Deterministic, stdlib-only, no network, no model call
(`fan-out-contract.md:162` - if a question is answerable by an exact algorithm,
write the algorithm).

```
python .agents/skills/claim-verify-gate/scripts/claim_gate.py --claims ledger.json
python .agents/skills/claim-verify-gate/scripts/claim_gate.py --claims ledger.json --doc report.md
python .agents/skills/claim-verify-gate/scripts/claim_gate.py --claims ledger.json --format json
python .agents/skills/claim-verify-gate/scripts/claim_gate.py --self-test
```

| rule | fires when |
|---|---|
| `no-verify-probe` | CONFIRMED/REFUTED with no `verify_probe` |
| `same-probe-rerun` | `verify_probe` matches `source_probe` on every axis |
| `no-evidence-anchor` | CONFIRMED with no `file:line` / URL in `evidence` |
| `no-settling-experiment` | UNVERIFIED that names no settling experiment |
| `unscoped-absolute` | absolute wording with no `scope` |
| `unbanded-hedge` | hedged wording with no band |
| `unknown-band` | a band outside the enumerated set |
| `refuted-without-rewrite` | REFUTED with no (or an identical) `revised_text` |
| `untagged-unverified` | UNVERIFIED claim, no `UNVERIFIED` tag in `--doc` |
| `trailing-unverified` | every `UNVERIFIED` tag sits in the document's final 15% |

Exit `0` gate passed - `1` violations - `2` unusable input. Residuals are counted
and printed, and never contribute to exit 1.

`--self-test` runs every rule against a known-BROKEN ledger and fails if any rule
stays silent. Run it before trusting a clean report: a gate that cannot fire is
not a gate.

## What this gate does NOT do (inline, so it qualifies something)

- It **never decides whether a claim is true.** It decides whether the ledger is
  allowed to say so. A ledger can be internally perfect and factually wrong.
- `trailing-unverified` is a **distribution** check over the whole document, not a
  per-claim adjacency check: it catches every flag parked in a trailing
  limitations section, and does NOT prove any individual tag sits next to its own
  sentence. Settling experiment: extend the ledger with a character offset per
  claim and assert the tag lands within N characters of it.
- Probe independence is checked on **declared** axes. An author who mislabels two
  runs of one tool as different tools defeats it. It raises the cost of faking
  from zero to a deliberate lie; it does not make faking impossible.
- The absolute/hedge word lists are heuristics tuned on this estate's measured
  overclaim shapes. They will miss novel phrasings. UNVERIFIED (likely 55-80) that
  the lists generalise to another corpus; settling experiment: run the gate over
  `harness-sota-2026-07-18-corpus/` and score flagged-vs-actual overclaims.

## Composes with

- `rules/common/single-signal-verification.md` - the rule this enforces; read it, this does not restate it.
- `rules/common/fan-out-contract.md` §A2/A3/A4, §B3, §C2 - the fan-out and fan-in obligations the table satisfies.
- `agent-self/config/AGENTS.md` §4 terminal states, §7 honesty.
- `hooks/claim-guard/` - the automatic per-turn lane for build/test claims.
- `mutation-check`, `fresh-context-verify`, `simplest-probe-first` - sibling probes, different questions.

## Sources

- Wei et al., *Long-form factuality in large language models* (SAFE, LongFact, F1@K),
  arXiv:2403.18802 - decomposition into individual facts, each rated separately.
- Dhuliawala et al., *Chain-of-Verification Reduces Hallucination in Large Language Models*,
  arXiv:2309.11495 - draft, plan verification questions, answer independently, verified response.