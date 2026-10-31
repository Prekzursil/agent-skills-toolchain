---
title: PROMPT-ONE-FLOOR-AUDIT
type: note
permalink: dqverify-repo-20261013/command-center/prompt-one-floor-audit
---

# PROMPT ONE FLOOR AUDIT

**Unit:** `ground/p1-floors` · **Measured:** 2026-08-09 · **Method:** mechanical counting, every
rule printed with its output so the rule itself can be audited.

**Headline:** every floor is MET, all 29 contracted artifacts exist, MD and JSON agree exactly on
all four paired artifacts — but only once the artifact set is read as the **UNION of two trees**.
Five of my own probes returned a wrong answer before a second probe corrected them; all five are
recorded below, because the credibility of this audit is the credibility of its detectors.

---

## 1. The contract being measured

| what | where |
|---|---|
| floor statement | `_USER-PROMPTS.md:6788` |
| exit criteria (restated) | `_USER-PROMPTS.md:7907-7918` |
| the 29 required artifacts | `_USER-PROMPTS.md:7827-7857` |
| anti-fork clause | `_USER-PROMPTS.md:10725` — *"Do not count trivial forks or renamed copies."* |
| MD/JSON parity clause | `_USER-PROMPTS.md:7859` — *"The Markdown and JSON must describe the same option set."* |

**Two trees, one contract.** The deliverable is the union of
`C:/Users/Prekzursil/.claude/harness-restore-20260806` and
`C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19`. Stated at
`15-IMPLEMENTATION-PRECONDITIONS.md:127-132`, corroborated independently by
`01-BLOCKER-REPRODUCTION.md:3-6`, and confirmed by direct `os.path.isfile` on all five
tree-2-only files.

---

## 2. Floor results

| # | floor | contracted | MD | JSON | self-declared | MD==JSON sets | verdict |
|---|---|---|---|---|---|---|---|
| F1 | platform options | >= 160 | **283** | **283** | 283 | yes | **CONFIRMED-MET** (177%) |
| F2 | workflow candidates | >= 160 | **284** | **284** | 284 | yes | **CONFIRMED-MET** (178%) |
| F3 | workflow blueprints | >= 96 | **108** | **108** | 108 | yes | **CONFIRMED-MET** (112%) |
| F4 | council protocols | >= 48 | **58** | **58** | 58 | yes | **CONFIRMED-MET** (121%) |
| F5 | council presets | >= 64 | **72** | **72** | 72 | yes | **CONFIRMED-MET** (113%) |
| F6 | architectures | >= 9 | **11** | n/a | n/a | n/a | **CONFIRMED-MET** (122%) |
| F7 | contracted artifacts | 29 | **29/29** | — | — | — | **CONFIRMED-MET** *(union only)* |

### Counting rules (so they can be argued with)

- **F1** — `^#### \`([A-Z]{1,3}-\d+)\`` over `07-OPTION-UNIVERSE.md`; one h4 card per option.
  JSON side: unique `id` over `options[]`. First 3 `A-01, A-02, A-03`; last 3 `M-37, M-40, M-41`.
- **F2** — `^### \`([A-Za-z0-9][A-Za-z0-9._-]*)\`` over
  `08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md`, closing backtick **anchored** so a truncated id
  cannot pass. JSON side: unique `id` over `candidates[]` in `08-WORKFLOW-CANDIDATE-REGISTRY.json`.
  First 3 `wf-saved-agentic-repair-reliability, wf-saved-bc-stage-compendium-enrichment,
  wf-saved-codex-auth-research-fanout`; last 3 `cmd-sessions, cmd-resume-session, cmd-save-session`.
- **F3** — `^### \`(BP-[A-Z]+-\d+)\` v` over `09-WORKFLOW-BLUEPRINT-LIBRARY.md`.
  First 3 `BP-RES-01..03`; last 3 `BP-XVD-04..06`.
- **F4** — `^#### (P\d+) \`` over `12-COUNCIL-PROTOCOLS-AND-PRESETS.md`. `P01..P58`.
- **F5** — `^#### (C-[A-Z]\d+) \`` over the **same file**, **different field**. `C-M01..C-H72`.
- **F6** — `^### (A\d+) —` over `13-ARCHITECTURE-CANDIDATES.md`. `A1..A11`.
- **F7** — the 29 numbered items at `_USER-PROMPTS.md:7829-7857`; `os.path.isfile` over the union.

### F5 is the floor an earlier pass got wrong — here is the guard

The prior error was taking the **max of two lists** instead of reading **two separate fields**.
Guarded three ways, all mechanical:

1. Two **different** regexes, each proven to be **silent on the other's** card
   (`#### P07 \`oxford-debate\`` must not match the preset rule and vice versa). Both controls PASS.
2. **Disjointness**: `protocol_ids ∩ preset_ids = ∅` — computed, not asserted.
3. **Sum check**: `58 + 72 = 130` and the file contains exactly **130** h4 headings. Nothing is
   double-counted, nothing is unaccounted.

### F6 has three independent probes

h3 headings = 11 · section-3 hazard-matrix **column headers** = 11 · the effort-vs-leverage
ranking sentence = 11. Three different mechanisms, same answer.

### F7 — 29/29, but only as a union

28 file-shaped items + item 29 (diagrams). **23 in tree 1, 5 in tree 2, 0 missing, 0 trivial
(<2KB).** Item 29 required 8 `@visualize` diagrams; `harness-restore-20260806/diagrams/` holds
exactly 8 `.md` files each carrying one mermaid block, one per contracted diagram.

Tree-2-only: `02-BLOCKER-ROOT-CAUSE.md`, `04-MARKETPLACE-CURRENT-STATE.md`,
`06-EXISTING-WORK-ADOPT-EXTEND-RETIRE.md`, `10-WORKFLOW-FORGE-SPEC.md`,
`12-COUNCIL-TEST-MATRIX.md`.

> **Consumption hazard, not a production gap.** Anyone reading `harness-restore-20260806` alone
> sees 23/28 and will conclude 5 artifacts were never produced. Pin the union with a per-file
> access path in any Prompt Two work-unit prompt.

---

## 3. Substance — distinct, or renamed forks?

This mattered more than the count, so it was answered over the **whole population**, not a sample.

**Metric.** Token-Jaccard nearest-neighbour over each record's semantic fields (blueprints:
`purp/task/contra/out/gates`; protocols: `problem/mech/distinct/route/tier`), stopword-filtered,
with the **`name` field excluded** so a rename cannot hide a clone. 108/108 blueprints and
58/58 protocols scanned.

| population | min | median | max | >= 0.60 | >= 0.45 |
|---|---|---|---|---|---|
| blueprints (108) | 0.049 | 0.097 | **0.243** | **0** | **0** |
| protocols (58) | 0.067 | 0.103 | **0.161** | **0** | **0** |

Closest real pairs: `BP-TST-06 Fail-First Red-Proof Certification` ~ `BP-IMP-04 TDD Red-Proof
Batch Implementation` (0.243); `P49 socratic-interrogation` ~ `P13 hostile-cross-examination`
(0.161).

**Both-states control — the metric was proven able to see a clone before its silence was trusted.**
Three synthetic mutants of a real donor were planted into the real corpus and the identical scan
re-run:

| mutant | blueprints | protocols | fires? |
|---|---|---|---|
| exact rename (new id + new name, fields byte-identical) | 1.000 | 1.000 | yes |
| light paraphrase | 0.982 | 1.000 | yes |
| trivial fork (one parameter changed) | 0.949 | 0.932 | yes |

Planted forks score **0.93-1.00**; the real corpus tops out at **0.243**. ~4-6x separation.
**CONTROL: PASS** — "zero clones" is a measurement, not a blind detector.

### Seeded random sample (seed `20260809`, reproducible)

**Blueprints:** `BP-BRN-01` Two-Peer Cross-Vendor Idea Fan-out · `BP-CRV-01` Split-Role Reviewer
Panel · `BP-RES-04` Claim-Decomposition Verification Pass · `BP-BRN-02` Diverge-then-Converge
Brainstorm · `BP-SEC-04` Supply-Chain Alert Campaign with Fail-Closed Gate

**Protocols:** `P06` nominal-group-technique · `P55` shadow-council · `P25` blind-reevaluation ·
`P02` round-robin · `P07` oxford-debate

**Verdict: 10 of 10 materially distinct.** The reason is structural rather than stylistic — every
card carries a `distinct` field that **names its nearest siblings by id** and states the
differentiator. The anti-fork rule is enforced per-record inside the artifact, not asserted once in
a preamble:

- `P06` — *"Generation is silent AND ranking is independent; P26 swarm is loud, P22 brainwriting
  passes drafts around, P20 Delphi iterates estimates not idea lists."*
- `P25` — *"It is a re-run with amnesia, not another round; P54 mirrors across vendors but both
  runs are live, this one is deliberately posterior."*
- `BP-RES-04` — gates: *"a CONFIRMED or REFUTED verdict with an empty `source_probe` is a
  VIOLATION"*, with a `contra` forbidding self-application.

**Executable? Executable-SHAPED, not executed.** Every sampled card carries a typed `out{}`, gates,
`contra`, `deps`, `conflicts` and a stopping rule. But the artifacts self-declare their status:
`09-WORKFLOW-BLUEPRINT-LIBRARY.json` sets `discovery_only: true` and
`12-COUNCIL-PROTOCOLS-AND-PRESETS.json` sets
`status: "DISCOVERY - no protocol here has been executed"`. **Zero of the 166 items carry an
execution receipt.** "Exists" must not be read as "works".

### Extrapolation, with bands

- *No exact duplicates, renamed copies, or one-parameter trivial forks exist among the 108
  blueprints and 58 protocols* — **almost-certain (90-99%)**. The scan is exhaustive over the
  population and its control fires at 0.93-1.00 against a corpus max of 0.243.
- *The items are executable-shaped but unexecuted* — **almost-certain (90-99%)**; self-declared by
  the artifacts and no receipt exists in either tree.
- **UNVERIFIED:** a *deep semantic paraphrase* — same mechanism, fully rewritten vocabulary — would
  score low on token-Jaccard and evade this metric. **Settling experiment:** embed all 166 records
  with a sentence-transformer and re-run the nearest-neighbour scan on cosine similarity; a pair
  far in Jaccard but near in embedding space is the evasion case. **NOT RUN.**

---

## 4. My own detector failures (5)

Every one produced a confident wrong answer that survived until an independent probe disagreed.

| # | probe | wrong reading | cause | corrected |
|---|---|---|---|---|
| 1 | option regex `[A-Z]-\d+` | 230 MD vs 283 JSON — "parity breach" | single-letter family class; `EV`/`PR`/`RT` are two letters (21+17+15=53) | 283 == 283, sets identical |
| 2 | candidate regex, lowercase-only | 282 MD vs 284 JSON — "2 candidates missing" | ids with an uppercase segment silently **truncated** (`…-A1.4-feature-vector` → `exec-bc-mega-build-`); no closing-backtick anchor | 284 == 284, sets identical |
| 3 | section-3 table **row** scan | "only 6 architectures compared" | read the wrong axis — architectures are **columns**, rows are hazards | 11 |
| 4 | diagram search, top level only | "0 diagrams, item 29 unfulfilled" | scoped to one directory; diagrams live in `ROOT/diagrams/` | 8 of 8 present |
| 5 | artifact presence, **one tree** | "5 of 28 artifacts ABSENT" | the deliverable is the **union** of two trees | 28/28, 0 missing |

Failures 4 and 5 would each have been reported as a P1 program gap. Both were false.

---

## 5. Incidental findings

**IF-1 (P1) — the pinned KNOWN BLOCKER F-B-02 has been remediated. CONFIRMED.**
The pinned ground truth says *"31 option IDs resolve to TWO UNRELATED MEANINGS"*. Measured today:
`13-ARCHITECTURE-CANDIDATES.md` carries **38 distinct `MECH-NN` ids** and only **2** bare `M-NN`
strings, both inside `adopt-after-M-16` (line 1159) and `adopt-after-M-21` (line 1193).
`07-OPTION-UNIVERSE.json` records the fix: *"sec-4 mechanisms, re-prefixed M-NN -> MECH-NN on
2026-08-07 (finding F-B-02). Re-prefix only, never renumbered: old M-NN == new MECH-NN."*
**Collision surface is now 2 stale text references, not 31 ids.** Update the pinned ground truth;
do not re-plan around a 31-way collision that no longer exists. Fix the 2 strings.

**IF-2 (P2) — the 7 "absent" doc-13 ids are absorbed-by-merge, not dangling. CONFIRMED.**
`id_namespace.absorbed_not_dangling` lists `M-12/16/17/19/28/30/38/39` as pre-dedup
`07-OPTIONS-LM.md` ids folded into a canonical option. `merges[]` has 50 entries and the arithmetic
reconciles: `283 final + 55 collapsed + 3 removed = 341 pre-dedup`.

**IF-3 (P2) — stale family labels in the JSON.** `counts.per_family_final` still keys on
`E -`/`F -`/`G -` (21/15/17) while the actual ids are `EV-NN`/`RT-NN`/`PR-NN` (21/15/17). Counts
match, so it is display-label drift, not a count error — but any consumer joining on the family
label rather than the id prefix will fail.

**IF-4 (P2) — the F-B-02 remediation record is one regeneration from deletion.**
`07-OPTION-UNIVERSE.md`'s ID-NAMESPACE paragraph and the JSON's `id_namespace` key are both
hand-added; the JSON says so: *"Not emitted by `_uni_build.py`; a regeneration drops this key."*
Fold it into the generator before anyone re-runs the build.

---

## 6. Bottom line for Prompt Two

Prompt One's floors are **not** the risk. Every floor is exceeded (112%-178% of floor), MD and JSON
agree exactly on all four paired artifacts, and 29/29 artifacts exist. The two real hazards are
consumption-side:

1. the artifact set is a **union of two directories** and a one-tree read under-counts by 5;
2. all 166 blueprints/protocols are **DISCOVERY-only with zero execution receipts** — "exists" is
   not "works".

---

### Reproduce

```
python C:/Users/Prekzursil/.claude/harness-restore-20260806/_p1floor_count.py      # floors 1-7
python C:/Users/Prekzursil/.claude/harness-restore-20260806/_p1floor_substance.py  # near-dup scan + sample
python C:/Users/Prekzursil/.claude/harness-restore-20260806/_p1floor_control.py    # both-states control
```
Machine-readable results: `PROMPT-ONE-FLOOR-AUDIT.json` (this directory).