---
title: OPTION-ID-RESOLUTION
type: note
permalink: dqverify-repo-20261013/command-center/option-id-resolution
---

# OPTION-ID-RESOLUTION — mechanical resolution of F-B-02

**Unit:** `ground/option-ids` · **Date:** 2026-08-09 · **Status:** MEASURED (all 7 sections)
**Machine-readable twin:** `OPTION-ID-RESOLUTION.json` (32 KB, same generator run)
**Extractors:** `~/.claude/harness-restore-20260806/_optid_{extract,control,residual,adjudicate,emit}.py`
**Method:** honesty rule 7 — every set below is produced by an algorithm, none by reading.

---

## 0. HEADLINE — the pinned blocker is STALE

| claim | verdict | evidence |
|---|---|---|
| F-B-02's **arithmetic** (33 / 38 / 31 / 7 / 2) | **CONFIRMED** | an independently written extractor reproduced all five numbers exactly |
| F-B-02 as a **LIVE blocker** | **REFUTED** | the `M-NN → MECH-NN` re-prefix was already applied to `13-ARCHITECTURE-CANDIDATES.md` on 2026-08-07 by `_fb02_apply.py` (**107 substitutions**, gated by `_fb02_gate.py`). Literal shared-id count between doc 07 and doc 13 **today = 0** |
| the 107-substitution figure itself | **CONFIRMED, second independent signal** | not the script's own assertion — a byte-count of the untouched pre-fix backup: `backups/13-ARCHITECTURE-CANDIDATES.md.pre-fb02` holds **107** bare `M-NN` tokens; the live file holds **0** bare `M-NN` and **108** `MECH-NN` (107 substituted + 1 introduced by the hand-added namespace paragraph). The arithmetic closes exactly |
| the residual blocker | **CONFIRMED** | `17-DECISION-LOG.md` contains **zero** `MECH` tokens. Line 175 still states the collision in the present tense and says *"Queued as P2-09"*. Anyone pinning ground truth from the decision log inherits a fixed problem as an open one — which is exactly what happened to this program |

**Consequence for Prompt Two:** the `[PASTE SELECTED OPTION IDS HERE]` slot is **not blocked**.
`M-NN` now has exactly one meaning in the option universe. What still needs doing is listed in §7.

*Confidence: almost-certain (90-99%) on the literal-collision-is-0 claim — two mechanically
independent signals (regex extraction of both documents, and the pre-existing `_fb02_gate.py`
postcondition set).*

---

## 1. ID namespaces present in each document, with counts per family

### `07-OPTION-UNIVERSE.json` `options[]` — 283 cards, 13 prefixes

| prefix | n | prefix | n | prefix | n |
|---|---|---|---|---|---|
| `A-` | 28 | `H-` | 18 | `M-` | **33** |
| `B-` | 28 | `I-` | 17 | `PR-` | 17 |
| `C-` | 31 | `J-` | 15 | `RT-` | 15 |
| `D-` | 22 | `K-` | 15 | | |
| `EV-` | 21 | `L-` | 23 | **total** | **283** |

`07-OPTION-UNIVERSE.md` cards: **identical set**. Symmetric difference **0**, title mismatches **0**
(D-P-13's single-generator claim holds).

**Family-letter ≠ prefix for three families** (F-B-03, independently reconfirmed here): the doc
declares families `E`, `F`, `G` but the ids are `EV-`, `RT-`, `PR-`. Declared per-family counts
(21 / 15 / 17) match the observed prefix counts exactly, so the mapping is E→EV, F→RT, G→PR.

### `13-ARCHITECTURE-CANDIDATES.md`

| section | namespace | n |
|---|---|---|
| §2 architecture candidates | `A1`…`A11` (no hyphen-digit form) | 11 |
| §4 mechanism options | **`MECH-01`…`MECH-38`** | **38** |
| §4 residual bare `M-NN` | — | **0** |
| §5 owner-decision flags | 6× `A<n>` + 7× `MECH-NN` | 13 |

### `17-DECISION-LOG.md`

id-token frequency by prefix: `A` 12 · `B` 6 · `C` 1 · `G` 13 · **`M` 10** · `O` 6 · `P` 18 ·
`R` 12 · `U` 4.
*Detector disclosure (INLINE):* the tokenizer's `\b` boundary splits compound ids, so `D-P-13`
counts as `P-13` and `F-B-02` as `B-02`. The `M-` row is unaffected (no compound `?-M-NN` form
exists). **UNVERIFIED** that no other compound form is mis-split; settling experiment: re-run with
`(?:[A-Z]{1,4}-)?[A-Z]{1,4}-\d{1,3}` and diff the two frequency tables.

---

## 2. The colliding set — 31 ids, both titles side by side

Reconstructed by stripping the `MECH-` prefix from doc 13 §4 (the fix was declared
*"re-prefix only, never renumbered"*, so `MECH-NN ≡ old M-NN`). **Titles identical in 0 of 31 cases** —
every one is a genuine semantic collision, not a duplicate.

| id | `07-OPTION-UNIVERSE` family-M option | `13-…§4` mechanism (now `MECH-NN`) |
|---|---|---|
| M-01 | Salvage, index and tombstone the surviving executed workflow corpus | EVENTS as data + generator-completeness test |
| M-02 | Reverse specification: run record plus script to a typed workflow spec | Reachability oracle (declared ∧ registered ∧ observed) |
| M-03 | Component-graph extraction across the corpus | Typed silence protocol (`FINDING\|CLEAN\|NOT-CHECKED\|RAISED\|DEGRADED`) |
| M-04 | Stage library (typed, deduped, best-variant) | Fail-open dependency receipts |
| M-05 | Role / lens library with per-role evidence standards | Deployed-copy write-guard |
| M-06 | Gate library with enumerated verdicts and a mandatory override path | Content-addressed deploy manifest + boot verify |
| M-07 | Stopping-rule library with mandatory pre-cap synthesis | `install.py`: merge-not-replace, `--source`, non-zero on empty |
| M-15 | Council-selected fusion for non-executable judgement calls | Extend `sync-from-live.ps1`'s tree map |
| **M-18** | **Workflow benchmark harness (small, deterministic oracles)** | **Workflow certification harness** |
| M-26 | Generation from traces (session transcript to workflow draft) | Catalogue-tax reduction (user-scope disable + orphan marketplace removal) |
| M-29 | Deploy the dark cross-vendor council and invoke suite | Role→model-tier routing table |
| M-32 | External prior-art sweep with a hard native-vs-build verdict | Junction-aware traversal policy + INV-3 gate |

*(12 of 31 shown; the complete 31-row table with both titles is
`OPTION-ID-RESOLUTION.json → 2_colliding_set.rows`.)*

**Full colliding set (exact):**
`M-01 M-02 M-03 M-04 M-05 M-06 M-07 M-08 M-09 M-10 M-11 M-13 M-14 M-15 M-18 M-20 M-21 M-22 M-23
M-24 M-25 M-26 M-27 M-29 M-31 M-32 M-33 M-34 M-35 M-36 M-37`

---

## 3. Doc-13-only set — 7 ids, absent from the universe

`M-12` `M-16` `M-17` `M-19` `M-28` `M-30` `M-38` — exactly the seven F-B-02 names.

| historic | current | doc-13 title |
|---|---|---|
| M-12 | `MECH-12` | Env-injection order fix |
| M-16 | `MECH-16` | Vendor-neutral YAML as the workflow SSOT |
| M-17 | `MECH-17` | Snapshot + index the executed-workflow corpus |
| M-19 | `MECH-19` | Adopt the `fanout-schema` hardening module |
| M-28 | `MECH-28` | MCP lazy-mount / shared-host consolidation |
| M-30 | `MECH-30` | Cross-vendor verification lane (Claude builds, Codex verifies) |
| M-38 | `MECH-38` | Provenance stamp on every generated artifact |

These same seven numbers **also** exist as pre-dedup lane ids in `07-OPTIONS-LM.md` that were
absorbed by a merge (`07-OPTION-UNIVERSE.json → merges[].absorbed`). So an `M-16` in a third
document is three-ways ambiguous, not two — see §5.

---

## 4. Universe-only set — 2 ids

| id | doc-07 title |
|---|---|
| M-40 | Privacy / redaction gate before any publish or share |
| M-41 | Archaeology beyond the main ref: branches, worktrees, PRs and unregistered trees |

33 family-M cards = 31 colliding + 2 universe-only. 38 mechanisms = 31 colliding + 7 doc-13-only.
Both reconcile exactly.

---

## 5. The owner-decided set — the number is **70**, triple-corroborated

Three **mechanically independent** signals inside the same artifact pair agree, symmetric
difference **0** on every pair:

| signal | n |
|---|---|
| `07-OPTION-UNIVERSE.json` → `owner_decisions[]` array | **70** |
| `07-OPTION-UNIVERSE.md` §7 bullet list | **70** |
| count of `options[].owner == true` | **70** |

All 70 exist as real cards in the universe (set difference against `options[]` = ∅).

By prefix: `A` 11 · `B` 16 · `C` 6 · `D` 2 · `EV` 3 · `H` 3 · `I` 2 · `J` 6 · `K` 3 · `L` 7 ·
**`M` 6** · `PR` 1 · `RT` 4.

**The 70:**
`A-01 A-03 A-12 A-13 A-17 A-18 A-20 A-22 A-23 A-26 A-29 B-01 B-04 B-06 B-10 B-12 B-13 B-14 B-15
B-17 B-20 B-23 B-24 B-27 B-28 B-29 B-31 C-01 C-03 C-10 C-17 C-29 C-32 D-15 D-22 EV-04 EV-06 EV-07
RT-01 RT-12 RT-19 RT-21 PR-20 H-10 H-13 H-15 I-02 I-05 J-01 J-03 J-09 J-15 J-17 J-18 K-04 K-06
K-09 L-02 L-04 L-16 L-25 L-28 L-29 L-32 M-18 M-22 M-29 M-31 M-36 M-37`

> **Decision-relevant:** **all six** family-M owner decisions (`M-18 M-22 M-29 M-31 M-36 M-37`)
> sit inside the 31-id colliding set. Before the fix, six of the seventy owner decisions could be
> read as the wrong card. After the fix they are unambiguous **inside doc 07** — but a citation of
> one of them in any *other* artifact is still ambiguous (§7).

### 5b. Doc 13's own owner-decision table — F-B-02 undercounts by one

Doc 13 §5 has 13 rows: 6 architecture (`A2 A3 A6 A7 A9 A11`) + 7 mechanism
(`MECH-07 MECH-15 MECH-16 MECH-26 MECH-28 MECH-29 MECH-32`). In their historic `M-NN` form:

- **5 collide** to a different, real doc-07 card: `M-07 M-15 M-26 M-29 M-32`
- **2 resolve to absent**: `M-16 M-28`
- **total mis-resolving = 7 of 7**

F-B-02 says *"Six of the seven ids in doc 13's own owner-decision table mis-resolve."*
**REFUTED — the correct figure is seven of seven.** The rest of F-B-02's arithmetic is exact; this
one prose number is an undercount of one. Overclaim class per AGENTS.md — the code was right, the
sentence was wrong in the safe direction.

---

## 6. Extractor control (honesty rule 6 — detector proven before any absence is claimed)

| control | result |
|---|---|
| **Positive, 9 ids read BY EYE then transcribed** — `07…md`: A-01, D-14, M-01 · `07…json`: A-01, M-01, B-01 · `13…md`: MECH-01, MECH-02, MECH-05 | **9/9 found with the exact eyeballed title** |
| **Negative** — `M-99`, `MECH-99`, `ZZ-01` must be found nowhere | **3/3 correctly absent** |
| **Both-states (rule 3b)** — feed the detector the reconstructed **known-BROKEN** namespace | fires: **31 collisions** |
| **Both-states** — same detector on the **current FIXED** state | silent: **0 collisions** |

Verdict: **the detector discriminates the two states.** A silence here means something.

**Self-caught detector defect, disclosed INLINE:** the *loose* classifier in `_optid_residual.py`
labelled 10 of doc-18's 14 references `DOC13-MECHANISM` on a coarse `mechanism` keyword match. The
*strict* adjudicator (`_optid_adjudicate.py`, which only settles on absent-from-one-namespace or an
exclusive title-word match) settles **3**. **Every count in §7 uses the strict adjudicator.** The
loose numbers are an upper bound and are retained in the JSON only as such.

---

## 7. PROPOSAL (not applied) — finish the disambiguation

The scheme F-B-02 needed is **already the right one and already half-applied**: doc-07 family M
keeps `M-NN`; doc-13 §4/§5 mechanisms are `MECH-NN`, re-prefix only, never renumbered, so any old
citation maps 1:1. Nothing below renumbers anything.

### 7a. Reference census — counted, not estimated

**117** `M-NN` tokens across **31 files** outside the doc-07 option family (lane docs, universe
md+json, `_uni_*` builders, `_sa_cards.json`, backups, e2e transcripts and the `_fb02_`/`_optid_`
tooling are excluded as legitimate option-namespace territory).

| artifact | refs | mechanically settled | proposed action |
|---|---|---|---|
| `13-ARCHITECTURE-CANDIDATES.md` | **107 — ALREADY DONE** | 107 | no action (applied 2026-08-07 18:41, gate green) |
| wave-3 `deep-research` skill (**16 files, 2 duplicated trees**) | **20** | 20 | **third namespace** — rename to a wave-3 prefix (`W3-16` / `RH-01`), *not* `MECH-` |
| `16-GRILL-QUEUE-PHASE2.md` | 37 | 21 (14 mech / 7 option) | **22 of 37 sit in the L340-400 write-up OF the finding — rewriting them destroys the evidence.** Only the 15 outside that block are candidates |
| `18-OPEN-UNKNOWNS-AND-PROBES.md` | 14 | **3** (`L224 M-16`, `L234 M-17`, `L291 M-17`) | rewrite the 3; the other 11 `BLOCKS:` fields need the author to say which namespace each meant |
| `19-SUBSTANCE-AUDIT-OPTIONS.md` | 12 | 7 (5 mech / 2 option) | rewrite the 5 |
| `17-DECISION-LOG.md` | 10 | 0 | **all 10 are MENTIONS inside F-B-02's own text — do NOT blind-rewrite.** Append a `REMEDIATED` row + fix 6→7 |
| `diagrams/07-option-dependency-map.md` | 5 | 3 | 3 settle as options — no rewrite |
| `wave1/REGISTER.md` | 4 | 2 | 2 settle as options; `M-1`/`M-3` at L304 are *"Prompt-Two mission grades"* — a **fourth** single-digit namespace |
| `32-OWNER-DECISIONS.md` | 3 | 3 | all 3 settle as doc-07 options — **no rewrite needed** |
| `_sa_*` / `_verify_*` / `_p1floor_*` probe scripts | 12 | 0 | scratch tooling, out of scope |

**Totals: 117 residual refs · 59 mechanically settled · 58 require author adjudication.**
The 58 are genuinely undecidable from the text — reporting them as settled would be the exact
overclaim class this program keeps hitting.

### 7b. NEW — a **third** `M-NN` namespace nobody has recorded

`M-16` currently means **three** different things on disk:

1. `07-OPTIONS-LM.md:657` — *"M-16 — Expert-curated packs with preset entry points"* (pre-dedup lane
   option, absorbed into `C-10`)
2. `13-…§4` — `MECH-16` *"Vendor-neutral YAML as the workflow SSOT"*
3. **`wave3/ast-cc/skills/deep-research/SKILL.md:16` — *"Research Harness (M-16)"***, a wave-3
   deliverable id, baked into **7 module docstrings × 2 duplicated trees + 2 `SKILL.md` × 3 refs = 20
   references across 16 files**

This is **live deployed skill text**, not a program artifact. F-B-02 measured two namespaces; there
are at least three, arguably four (`wave1/REGISTER.md:304`'s single-digit `M-1`/`M-3` mission grades).
*Confidence: almost-certain (90-99%) — three distinct on-disk definitions read directly.*

### 7c. NEW — `M-18` is a **near**-collision, the most dangerous shape

`M-18` doc-07 = *"Workflow **benchmark** harness (small, deterministic oracles)"*
`MECH-18` doc-13 = *"Workflow **certification** harness"*

Both are plausible in almost any context, so a mis-resolution here produces no visible error.
`M-18` is also **one of the 70 owner decisions**. Live site:
`18-OPEN-UNKNOWNS-AND-PROBES.md:224` — *"**BLOCKS:** A6 beyond its snapshot step; M-16, M-18"*.
`M-16` in that same list is mechanically settled as `MECH-16`, which makes `MECH-18` the likely
reading — but that is an inference from adjacency, **UNSETTLED**. Settling experiment: ask the
author of doc 18, or check whether U-13's blocked work is the benchmark or the certification harness.

### 7d. Regression risk — the fix will silently un-apply

**CONFIRMED, two signals.** Both namespace declarations are hand-written and the artifacts say so
themselves: `07-OPTION-UNIVERSE.md` — *"(This paragraph is hand-added and will be lost if
`_uni_build.py` re-emits this file — fold it into the generator.)"*; the JSON's `id_namespace` key
carries *"hand_added: Not emitted by `_uni_build.py`; a regeneration drops this key."*
Independent probe run today: `grep -c MECH _uni_build.py` → **0**. A single regeneration reopens F-B-02.

**Recommended order (owner decides; nothing applied by this unit):**

1. **Append** a `REMEDIATED 2026-08-07` row to `17-DECISION-LOG.md` F-B-02 and correct 6→7. *(unblocks
   Prompt Two by removing the stale pin; 0 rewrites, append-only)*
2. **Fold** the namespace note into `_uni_build.py` so regeneration cannot drop it. *(closes 7d)*
3. **Rename** the wave-3 `M-16` to `W3-16`/`RH-01` across the 20 refs / 16 files. *(closes the third
   namespace; note the 2× duplicated tree)*
4. **Rewrite** the 3 settled refs in doc 18 and the 5 in doc 19.
5. **Adjudicate** the 58 unsettled refs with the authors — or leave them and accept the ambiguity.

---

## 8. What this unit did NOT do

- It **applied nothing**. No artifact outside `command-center/OPTION-ID-RESOLUTION.*` and the
  `_optid_*.py` extractors was modified. Nothing staged, nothing committed.
- It did **not** read the 283 option card bodies — only ids and titles. A collision of *content*
  under different ids would not be visible here. **NOT-CHECKED.**
- It did **not** verify that `_fb02_gate.py` still passes today; the 107-substitution figure is read
  from that script's own assertion plus my independent count of 38 `MECH-` cards / 0 bare `M-NN` in
  doc 13. Settling experiment: `python _fb02_gate.py`.
- It did **not** adjudicate the 58 unsettled references. Doing so by LLM judgement is exactly the
  86%-accurate / 100%-of-errors-point-at-loss failure mode recorded on this estate.