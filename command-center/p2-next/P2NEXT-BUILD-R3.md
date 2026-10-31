---
title: P2NEXT-BUILD-R3
type: note
permalink: dqverify-repo-20261013/command-center/p2-next/p2-next-build-r3
---

# P2NEXT — BUILD lane, round 3: the deferred anchor hole, closed

COVERAGE: every claim below is measured by an executed probe named beside it. Two things are
NOT measured and say so inline: whether the 42 rail-blocked units would PASS a Codex review,
and whether `codex login` clears agent-identity registration (owner-only credential write).

## 0. Headline: my own brief was stale, and the plan it carried was already built

The grounding I was handed ranks "build the C5 content floor, but close the claim_gate hole
first" as the only genuinely unbuilt rail-independent work. **Both halves were already
committed at `00d0a311`** ("two gates certified reviews they never read -- close both, with
both-states proof"), which shipped the `no-source-probe` rule, the C5 notes floor, 5 new tests
and 7 new self-test cases. Re-deriving it would have rebuilt a delivered, CI-wired result.

The lane brief is stale on its two headline numbers as well, and this remains true this round:

| brief says | committed truth | what the brief's figure actually counted |
|---|---|---|
| 48 self-declared BLOCKED | **52** | round-1 framing; no committed derivation holds 48 |
| 43 of 47 name cross-vendor | **42 of 52** | TAG OCCURRENCES — a receipt with three review tags counted three times |

Both are already marked superseded in `command-center/CROSS-VENDOR-RAIL-STATUS.md`.

## 1. Definition of Done — verified this round, not cited

Re-derived from COMMITTED BLOBS by `rail_count_gate.py`, which fails on disagreement:

```
FRESH DERIVATION: 52 blocked units, 42 rail-blocked, 10 satisfiable now, 10 of those reviewed;
                  catalog carries 2007 units, 449 of them READY
```

| DoD item | State | Evidence |
|---|---|---|
| the blocked set split cross-vendor vs any-independent-reviewer | **PASS** | `VENDOR-SATISFIABILITY.json` @ HEAD: 52 rows, `Counter({'RAIL_BLOCKED': 42, 'SATISFIABLE_NOW': 10})` |
| receipt text quoted per unit | **PASS** | 52/52 rows carry a verbatim `reviewer_requirement`; 43/52 also carry a verbatim `blocked_on` [1] |
| satisfiable subset reviewed and receipted | **PASS** | 10 of 10, each `verdict=PASS, independent=true`, notes 1027-2092 chars |
| rail-blocked remainder counted exactly | **PASS** | 42, gate-enforced against the published doc |

No same-vendor review was substituted anywhere a receipt demands cross-vendor. The 42/10 split
is unchanged by this round's work.

> [1] **REFUTED — round 2.** This row originally read *"every row carries verbatim
> `reviewer_requirement` + `blocked_on`"*. Measured: **9** of the 52 rows carry an EMPTY
> `blocked_on` — ADV-0001, -0006, -0007, -0014, -0015, -0020, -0021, -0022, -0036. Reading all
> nine receipts shows every one has `failure.blocked_on` = null, so the extraction is faithful with
> **0 data loss** and the DoD item still PASSES. The code was right and the sentence was wider than
> its evidence.

## 2. What this round shipped: a timestamp was a valid evidence anchor

`00d0a311` disclosed one hole it deliberately did not fix — claim_gate's evidence-anchor rule
was `https?://\S+|\S+:\d+`, and `\S+:\d+` is satisfied by anything with a colon and a digit.
Its stated reason for deferring: "one behaviour change to a shared skill per round, and that one
has no measured false-negative yet." This round supplies the measurement and closes it.

### The false negative was wider than the disclosed timestamp

`_d1_anchor_corpus.py` section A — the CURRENT rule accepted **9 of 9** non-references:

```
current=PASS  candidate=fire  '2026-08-12T05:15:00'      <- the disclosed case
current=PASS  candidate=fire  '05:15'                     clock time
current=PASS  candidate=fire  'ratio 3:1'                 a ratio
current=PASS  candidate=fire  'v1.2:3'                    a version number
current=PASS  candidate=fire  'measured at 2026-08-12T05:15:00 by the reviewer'
-> current accepts 9/9 non-references; candidate accepts 0/9
```

A CONFIRMED verdict could satisfy its evidence requirement by carrying the time it was written.

### The obvious fix is wrong in the other direction — measured before shipping

The strict shape already in-tree at `rail_count_gate.py:133` requires a file extension. Section
B measured what that costs:

```
-> ext-required would REJECT 3 real anchors: ['Makefile:12', 'Dockerfile:5', 'LICENSE:3']
-> CANDIDATE      would REJECT 0 real anchors: []
```

So the shipped rule tests whether the head names a **path** (contains a separator, or carries an
extension with at least one letter, or is a known extension-less filename), not whether it has a
dot. `C:\...\claim_gate.py:113` is covered explicitly — this estate is Windows.

> **SUPERSEDED — round 2.** "An extension with at least one letter" was REFUTED by an independent
> auditor: `.com` and `.io` carry letters, so `example.com:443` still passed. The letter clause is
> gone; a separator-less head must now carry a KNOWN FILE extension, dotfiles are recognised
> structurally, and a path separator still short-circuits everything. Measured over 2,568
> mechanically-verified real anchors: 0 regressions. `P2NEXT-BUILD-R4.md` §2.

### Both-states proof at the CLI, one unmodified probe (`_d3_timestamp_anchor.py`)

```
  ok    A real file:line anchor:          old exit 0 (want 0), new exit 0 (want 0)
  ok    B obvious non-evidence (control): old exit 1 (want 1), new exit 1 (want 1)
  ok    C bare timestamp (the defect):    old exit 0 (want 0), new exit 1 (want 1)
```

**B is the load-bearing control.** Without it, C flipping would be indistinguishable from "the
old gate did nothing at all". B fires in BOTH states, so the anchor rule was demonstrably live
while it was silent on C — a real hole, not a dead instrument.

### The fix is mutation-covered, including the old bug re-injected

`test_claim_gate_mutations.py` 6 -> 8 mutations, **8/8 killed**, among them:

```
KILLED   anchor head need not name a file (the pre-fix `\S+:\d+` behaviour)
KILLED   extension need not contain a letter (a version reads as a filename)
```

The first re-injects exactly the behaviour this round removed and requires the suite to go RED.
Tests 35 -> 39; the `no-evidence-anchor` self-test fixture was changed from "I recall seeing it"
to the timestamp, because a fixture that fires under the old AND new rule proves the instrument
runs, not that it discriminates.

## 3. My own probe was wrong first, and its control caught it

`_d1` initially reported "4436 evidence strings, 0 anchored". That shape is self-contradicting,
so `_d2_registry_shape.py` was written to read the registries directly: `evidence` is a **string**
in `command-center/CLAIM-REGISTRY.json` and a **list** in claim_gate's fixtures. Iterating the
string form yields CHARACTERS — the 4436 were 4436 single characters, none of which can contain
`file:line`. Fixed, and section C now reports 24 evidence strings, 3 anchored, **0 newly
rejected** by the shipped rule.

`_d2` deliberately re-implements `git_show` rather than importing `_d1`'s (the dup-guard hook
flagged it): a control that shares its subject's reader inherits the defect it exists to catch.
`_d1`'s first run did carry a reader bug — a cp1252 decode that silently dropped files.

## 4. Honest residuals — disclosed, not blocking

- **The corpus control is small.** Section C rests on **3** anchored strings in 2 committed
  ledgers. Section B (10 hand-built anchors) carries the false-positive verdict, not section C.
  Settling experiment: run the shipped rule over a corpus of real EVIDENCE blocks once more
  ledgers exist. [likely 55-80%] that no further false positive exists.

  > **SETTLED — round 2, in the direction of the code.** The named experiment was run with
  > mechanical ground truth (`_e3_anchor_corpus.py`: a head is a real anchor when it resolves to a
  > path `git ls-files` tracks). Over **2,568** real anchors from 4,972 committed markdown blobs:
  > **0 regressions**, and one PRE-EXISTING false positive fixed (`.gitattributes:2`, whose
  > 13-character extension overflowed the length window while the shorter `.gitignore` passed by
  > accident). The 55-80% band was an UNDER-claim; it is [almost certain, 90-99%] for a
  > separator-less head whose extension is in the allowlist, or any head containing a path
  > separator. The residual moved rather than vanished — the corpus is markdown-only, and the
  > allowlist is now a maintenance surface. Both are carried in `P2NEXT-BUILD-R4.md` §5.
  >
  > The same run REFUTED this round's own rule as sufficient: `example.com:443` and `site.io:8080`
  > still passed, because `.com` and `.io` carry letters. Closed in round 2.
- **`CLAIM-REGISTRY.json` uses `verifier_probe`; claim_gate reads `verify_probe`.** Found while
  measuring, NOT fixed here — it is a schema question for that registry's owner, not an anchor
  question, and claim_gate is not run over it in CI. UNVERIFIED whether this is drift or two
  deliberate schemas.
- **C5's resolvable-anchor half stays ADVISORY.** 0 of 10 receipts carry a resolving anchor;
  enforcing it would turn CI red on every existing receipt and the only fix would be rewriting
  ten reviews this lane did not perform. Unchanged from `00d0a311`.
- **Windows-local green is not CI green.** ~9 of ~25 steps run here.

## 5. BLOCKER found by running the gate I did not expect to matter

`ci/check_skill_dual_write.py --strict-parity` is **RED** for this round's commit:

```
D-001 DUAL-WRITE VIOLATION
  - claim-verify-gate  [canonical-divergent]
      .agents/skills/claim-verify-gate/scripts/claim_gate.py
      canonical side: final counterpart: skills/claim-verify-gate/scripts/claim_gate.py
```

**It is pre-existing and systemic, not introduced here.** The same command reds on the commit
that CREATED this skill and on the previous round, both already in `origin/main`:

| commit | strict-parity verdict |
|---|---|
| `d34b74a7` created claim-verify-gate | VIOLATIONS: 1 |
| `00d0a311` previous round, same files | VIOLATIONS: 1 |
| `1b1e1e4e` this round | VIOLATIONS: 1 |

Cause: `.agents/skills/` holds **347 skill directories** and `skills/` projects **339** (counting
`SKILL.md` files instead gives 352 and 338 — five nested `SKILL.md` under `microsoft-foundry/**`
and one template are the difference, which is also why an SKILL.md-path diff mis-files the
published `microsoft-foundry` as canonical-only). **Eleven** directories are deliberately
canonical-only — claim-verify-gate, the nine `codex-*` skills, and qdx-rush — and the index agrees
with that
(`gen_skill_index.py --check` reports `canonical NOT declared: 0`, `INDEX DRIFT: no`;
`gen_skills_manifest.py --check` reports `skills_tracked=337 manifest_rows=337`). The
strict-parity rule does not accommodate that convention: it reds whenever a canonical-only skill
is TOUCHED, so the condition is invisible until someone edits one.

Why main is not already red: `skill-dual-write.yml` triggers on **`pull_request` only**, while
this lane's commits reach `origin/main` by direct push. The gate has therefore never run on the
two historical violations. It would run on a PR.

**Deliberately NOT remediated here, and the reason matters.** The two available fixes are both
worse than reporting:

1. *Mirror the 3 changed scripts into `skills/`* — satisfies the gate (it compares changed paths
   only) but creates a `scripts/`-without-`SKILL.md` half-skill: an incoherent published surface.
2. *Mirror the whole skill* — publishes a skill the repo deliberately kept unpublished, and
   cascades into `gen_skills_manifest --check` (337 -> 338 rows), the marketplace index, and the
   description ratchet. That is a skill-surface POLICY decision, not a p2-next decision.

Editing the checker to accept canonical-only skills is the third option and the worst one to take
unilaterally: weakening a gate so my own commit passes is the anti-pattern the gate exists to
prevent. Escalated as an owner/orchestrator call. [almost certain 90-99%] on the measurement;
the right remedy is a judgement I do not own.

## 6. The two owner decisions still price together

Unchanged and still the decisive fact: all 10 reviewed units remain blocked on completion
condition 11, which `receipt_schema_gate.py:515-527` hard-rejects while nothing in production
sets `manifest_registration.registered`. **`codex login` buys review capacity for 42 units and
delivers zero of them.** Pricing it alone overstates its value. Neither was attempted: the first
is a credential write (AGENTS.md §9), the second a contract collision.

No READY units were built.

> **REFUTED — round 2.** This paragraph originally read *"all 449 name a cross-vendor reviewer, so
> building them manufactures more un-reviewable work behind the same two blockers."* That is false,
> and it is false in the owner-facing paragraph used to price `codex login`. The wording is kept
> rather than deleted because the same sentence is in the permanent commit message of `1b1e1e4e`
> and cannot be corrected there without a history rewrite.
>
> Measured (`_e2_ready_vendor.py`, committed blobs at `5423de0f`, 6/6 detector controls passing):
> **95** of the 449 name a Codex reviewer outright; **49** carry a cross-vendor clause naming only
> Anthropic; **20** carry an undirected cross-vendor clause; and **285 carry no cross-vendor demand
> at all**. A regex-free floor needing no predicate: **33** READY units carry a
> `reviewer_requirement` byte-identical to text this lane itself ruled `SATISFIABLE_NOW`, with a
> 0-overlap control between the two classes.
>
> The ACTION was correct and lane-mandated — the spec forbids building READY units into a dead rail
> — but the REASON was not. Corrected statement, and the caveat that cuts the other way, in
> `P2NEXT-BUILD-R4.md` §1.