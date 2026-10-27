# Phase 8 — Skill and Capability Routing

**Unit:** `build/phase8-routing` · **Spec:** `_USER-PROMPTS.md:10948-10963` · **Root:** `platform/routing/`

Every number below is reproducible with `python platform/routing/cli.py all` and is captured
verbatim in `MEASUREMENTS.json`. Where a claim is not measured it says `NOT-CHECKED` and names
the experiment that would settle it.

---

## 1. What was built

| Module | Spec clause | Lines |
|---|---|---|
| `index.py` | "index all skills/plugins/workflows/tools" | discovery of **912** routable units, 9 classes |
| `descriptions.py` | "improve descriptions for routing" | routing-quality scoring + synthesized structural aliases |
| `rules.py` | "rule-based matching" | 9 explainable lanes, IDF-gated, anti-trigger demotion |
| `semantic.py` | "semantic matching" | hermetic BM25 + char-4-gram, no network |
| `router.py` | top-k, confidence, conflicts, overrides, explanation, fallback | AND-gate selection |
| `budget.py` | the anti-flooding measurement | injected bytes at k=1,3,5,10 |
| `metrics.py` | "measurement of skill-use breadth and task success" | P/R, breadth, ablation, both-states controls |
| `queries.py` | the labelled query set + its labelling disclosure | 60 queries, 4 tiers |
| `tuning.py` | derivation of the two selection constants | 88-point sweep, declared criterion |
| `cli.py` | the gate surface | 7 subcommands, terminal markers |

Schemas: `schema/capability-record.schema.json` (the 912 indexed records) and
`schema/routing-decision.schema.json` (the auditable decision payload, including a
conditional branch asserting that an abstention costs **zero** bytes).

Tests: **114 passing** in 3m57s — `test_index.py` · `test_descriptions.py` ·
`test_semantic.py` · `test_router.py` · `test_schema.py` ·
**`test_regression_no_flood.py`** (the suite the spec's final clause demands).
Every "validates" / "passes" assertion is paired with a mutation or counterfactual that
must FAIL, so no gate in this unit is silent in both states.

### Reconciliation with the existing router — built on, not rebuilt

`hooks/semantic-router/` already routes the LIVE trees: measured **358** rows
(238 skill / 65 command / 39 mcp / 16 agent) in `hooks/semantic-router/index/meta.json`. It
indexes **zero** of the platform inventory and it requires a live Ollama endpoint, so it
fails open when the network is absent and cannot back a gate.

This unit is the superset index over both, with no network dependency. It **reuses** the
estate's curated `hooks/semantic-router/mcp_hints.py` rather than re-authoring it, and it does
not edit, unregister, or replace the hook — that stays the live `UserPromptSubmit` path.

---

## 2. The inventory (`cli.py index` → `SUCCESS:routing-index units=912`)

| class | n | class | n |
|---|---|---|---|
| skill | 328 | preset | 69 |
| candidate | 164 | protocol | 48 |
| workflow | **102** | agent | 18 |
| plugin | 98 | mcp | 14 |
| command | 71 | | |

`floor_violations: []` — every source cleared its committed floor. The floor gate is
**both-states verified**: it FIRES on a deficient index (`test_verify_floors_FIRES_...`) and
passes on the live one.

**Independent corroboration of the pinned blueprint count.** The 102 workflow records
decompose as 89 `workflow` + 4 `meta-workflow` + 4 `subworkflow` = **97 top-level**, plus 3
distinct `forged/` ids and 2 `_shared/` subworkflows. 97 reproduces the pinned "97 materially
distinct blueprints" and 102 reproduces sibling D4's measured "102 distinct ids" — two
different pinned facts, both recovered by a walk that knew neither.

---

## 3. Context cost — the load-bearing measurement

Bytes injected per query, measured (`len(payload.encode())`) over all 60 queries, 240 priced
selections, `within_cap: 240/240`:

| k | mean card bytes | peak | mean if full descriptions injected instead | saving |
|---|---|---|---|---|
| 1 | **161.9** | 219 | 1,268.6 | **7.8x** |
| 3 | **389.6** | 657 | 3,188.2 | **8.2x** |
| 5 | **494.4** | 1,043 | 4,181.6 | **8.5x** |
| 10 | **530.2** | 1,322 | 4,501.5 | **8.5x** |

Two properties worth reading carefully:

* **Sublinear in k.** k=10 costs 530 B against k=1's 162 B — 3.3x for 10x the budget, because
  mean selected saturates at 2.9. The router stops when nothing else clears the bar instead of
  padding to fill k. A linear curve here would be flooding with extra steps.
* **The saving comes from the card projection, not from selecting less.** The comparison column
  prices the *same picks* with their full routing text.

**Against the real alternative.** Always-loaded skill descriptions cost **111,980 B** every
turn for all 328 skills, whether or not any is relevant. On-demand cards cost 494 B for the
2.7 that are — a ~227x difference in what a turn pays.

### Re-probe of a briefed estate fact

Briefed: *"one skill description measured 1,750 characters, 5.9x the median."*
Mechanically different probe (walk the 328 indexed `SKILL.md` frontmatter `description`
fields directly, rather than re-reading the original skill-listing audit):

* max = **1,750 chars** — **CONFIRMED, exact**.
* ratio = **6.97x** (median 251) — **PARTIAL**: the multiple differs because the population
  differs (328 frontmatter descriptions here vs the session's skill listing there). The
  briefed 5.9x is not reproduced on this population; the absolute length is.

---

## 4. Selection quality (`cli.py metrics`)

Router built from the **held-out** index. 60 queries; strict exact-id scoring.

| tier | n | hit@1 | hit@5 | recall@5 | precision@1 | query↔gold lexical overlap |
|---|---|---|---|---|---|---|
| **L1** held-out (all) | 28 | 0.500 | **0.750** | 0.750 | 0.500 | 0.650 |
| L1a held-out *trigger* | 2 | 0.500 | **1.000** | 1.000 | — | — |
| L1b held-out *description* | 26 | 0.500 | **0.731** | 0.731 | — | — |
| **L2** author paraphrase | 21 | 0.333 | **0.429** | 0.357 | 0.333 | **0.029** |
| **L4** multi-label | 5 | 0.400 | **0.600** | 0.200 | 0.400 | 0.036 |
| **L3** negative (no fit) | 6 | — | abstain **0.667** | — | — | — |

`unresolved_gold: []` — every authored gold id resolves, so a renamed capability breaks the
test rather than being silently charged to the router.

**How the set was labelled — the disclosure the task requires.**

* **L1 (28, mechanical).** Query = a sentence from the capability's own text; that sentence is
  then **REMOVED from the record** before routing (`holdout_index`). Verified by
  `test_the_holdout_is_real_not_decorative`, which asserts the withheld string is absent from
  the record the router sees. This converts a circular test into a leave-one-out retrieval
  test. L1a (declared trigger) and L1b (declared description) are reported **separately**
  because L1b is documentation-phrased, not conversational — averaging them would let easy
  retrieval mask weak paraphrase handling.
* **L2 / L4 (26, author-labelled).** I wrote the queries and picked the gold. The leakage
  meter is therefore published: mean Jaccard overlap between query tokens and the gold
  record's own description is **0.029** (L2) and **0.036** (L4) — these are genuine
  paraphrases, not keyword restatements. Asserted as a bar in the regression suite.
* **L3 (6, negatives).** Gold = ∅, testing the fallback.
* **8 L1 candidates were EXCLUDED and the exclusions are published** (`excluded_unanswerable`).
  Holding out an `mcp` record's description leaves 3–17 tokens, so the query is unanswerable by
  construction — a defect in the experiment, not the router. Because "we removed the queries we
  failed" and "we removed the queries that were impossible" look identical without the count
  and reason, both are printed. MCP routing is then measured properly by three added L2
  queries instead of left unmeasured.

**Honest scope of these numbers.** 60 queries over one estate, authored by the same agent that
wrote the router. Their defensible uses are regression (same set, after a change) and ablation
(same set, component disabled) — comparisons against itself where author bias cancels.
The absolute figures are **not** a general claim about routing quality. Settling experiment:
an independently authored query set. **NOT-CHECKED** — this unit does not have one.

---

## 5. Breadth — "do not prune capabilities merely because they were rarely used"

The spec's opening constraint, made falsifiable.

* **tail reachability = 0.9815 (53/54).** Walking the corpus at a fixed stride and asking
  whether each sampled capability can be selected by a query from its own description. A
  capability that cannot win even then is effectively pruned whatever the docs say. The single
  miss is `skill:source-command-instinct-export` — a mirror duplicate that was *correctly*
  suppressed in favour of its twin, so it is reachable as a capability.
* **144 distinct capabilities selected** across 60 queries, spanning **all 9 classes**:
  skill 50/328 · workflow 26/102 · candidate 14/164 · preset 12/69 · protocol 11/48 ·
  command 11/71 · plugin 11/98 · agent 6/18 · mcp 3/14.
* **Per-class caps** are what make this possible: without them 328 skill records swamp every
  query and the 102 blueprints become unreachable — the exact failure the spec names.
* **Conflict resolution demotes, never deletes.** Superseded tombstones (×0.35) and
  registry-REJECTED records (×0.55) stay candidates and are still returned when nothing better
  fits. `test_conflict_resolution_demotes_but_never_deletes` asserts a rejected blueprint
  remains reachable.

---

## 6. The controls — why any number above is worth reading

A metric that cannot be made to fail measures nothing. Both run in `cli.py metrics` and both
are asserted in the regression suite.

| control | result | verdict |
|---|---|---|
| **shuffled gold labels** | real recall 0.546 → **0.000** | `DETECTOR VALID` — the metric reads the selection |
| **EVERYTHING router** | recall **1.000** at **147,272 B/query** = **298x** | `ANTI-FLOOD METRIC VALID` |
| **query-blind top-k** | 1,076 B — comparable cost, no relevance | bytes alone can never certify a router |

The flood control is what gives *"without flooding context"* operational meaning: the
perfect-recall router exists, and it costs 298x. `test_quality_and_cost_bars_are_not_satisfiable_by_the_same_degenerate_router`
asserts directly that no single degenerate strategy passes both families of bars.

---

## 7. Selection is a two-signal AND-gate (derived, not guessed)

`cli.py tune` sweeps 88 points against the labelled set with the criterion **declared before
the grid is read**, and **fails closed** when nothing satisfies it.

A single threshold cannot work, and the sweep proves it monotonically:

| threshold | gold-hit@5 | abstain (L3) |
|---|---|---|
| 0.06 | 0.706 | **0.000** — finds things, injects on nonsense |
| 0.15 | 0.647 | 0.500 |
| 0.34 | **0.255** | 0.833 — stays quiet, finds almost nothing |

The two requirements ask different questions: *"is anything relevant AT ALL"* is **absolute**,
*"which one"* is **relative**. So a candidate must clear both `SCORE_FLOOR = 0.18` and
`mu + 4.0*sd` over the query's own score distribution — the same conclusion
`hooks/semantic-router/route.py:188` reached independently on this estate.

**Anti-overfitting is mechanical, not discretionary.** 88 grid points against 54 scored
queries means the argmax is untrustworthy to better than 1/54 = 0.019 — a "win" of 0.019 is one
query changing. So points within one query of the best are declared **TIED**, and the tie
breaks toward the **grid interior**, because a point on the grid edge cannot be shown to be a
local optimum at all. Without this the sweep selected `z=2.0`, the lowest value evaluated, on a
0.019 margin over a broad flat region.

---

## 8. Ablation — including two components that did not earn their keep

Measured recall@5 delta vs the shipped configuration:

| arm | delta | disposition |
|---|---|---|
| `no_char_ngram` | **−0.051** | KEPT — the morphology lane earns its place |
| `no_structural_enrichment` | −0.009 | KEPT — small but real contribution |
| `with_concept_expansion` | **−0.019** | **DEFAULTED OFF** — it measurably HURTS |

The concept-expansion lexicon (60 hand-authored task→inventory bridges) is net-negative: each
expansion raises the BM25 ceiling for every candidate while only some gain matching mass, so it
dilutes the records that were already right. It is kept in the tree as the ablation's control
arm and re-enablable per call, but shipping it ON because the effort was already spent is
exactly the decorative-feature failure this program keeps finding.

---

## 9. Task success — NOT-CHECKED, deliberately

`task_success()` returns `verdict: NOT-CHECKED` with the reason, **not `0.0`**. Real task
success needs to know whether the agent invoked the injected capability and whether the task
then succeeded — an outcome routing a query corpus cannot produce. An unpopulated log and a
router that never helps are different findings and collapsing them would be a lie.

The plumbing is `record_outcome()` (append-only JSONL) and the guard is both-states tested:
`test_task_success_becomes_MEASURED_once_outcomes_exist` proves the NOT-CHECKED branch is
falsifiable. The live collector for this signal already exists at
`hooks/semantic-router/success.py` (suggested-vs-acted counters).

---

## 10. Description quality — the actionable finding

**Trigger prose exists for 251/328 skills and 4/18 agents, and for ZERO of the 454
platform-authored records** (102 workflows, 48 protocols, 69 presets, 164 candidates,
71 commands). Those records are reachable only through descriptions written as titles and
objectives, with no authored statement of *when* to use them. Asserted by
`test_the_platform_authored_inventory_declares_NO_trigger_prose` so it cannot silently stop
being true.

Two description defects were **fixed** rather than merely reported, because both were
routing-fatal and both were fixable from data already on disk:

1. **98/98 plugins** carried a synthesized `"Installed plugin X from marketplace Y"`. Every
   plugin ships a real manifest at `<installPath>/.claude-plugin/plugin.json`; reading it gave
   **82/98** real descriptions. The symptom was not merely low plugin recall — `plugin:data`
   was a 6-token document, so BM25 length normalization handed it a huge score for any query
   containing "data".
2. **9/14 MCP servers** had no domain vocabulary at all, and the breadth probe selected
   **0 of 14**. Fixed by reusing the estate's curated hints map plus a 9-entry supplement for
   servers it predates. Now 3/14 selected on this query set.

Combined effect: L2 gold-hit@5 rose **0.278 → 0.429** and the derived threshold's hit@5 rose
0.545 → 0.611. Improving descriptions beat every matcher change attempted in this unit.

`descriptions.report()` emits the ranked per-capability improvement list. It does **not**
rewrite the 328 live `SKILL.md` files: that would be an unreviewable mass mutation of trees
this unit does not own, and `harness-vcs-hygiene.md` makes the repo their source of truth.

---

## 11. Defects found and fixed in this unit (all caught by its own probes)

| # | defect | how it surfaced |
|---|---|---|
| 1 | `kind == "workflow"` dropped 8 real blueprints incl. every meta-workflow | `SOURCE_FLOORS` fired `workflow: 89 < 97` |
| 2 | card cap off-by-3 — `"…"` appended after budgeting (221 B for a 220 cap) | `index.main()` over-cap gate |
| 3 | `id-fragment` fired on corpus-common words; a *research* skill won a *reframing* query | first smoke run |
| 4 | trigger overlap normalized by the PHRASE → long triggers could never fire | same smoke run |
| 5 | `exact-name` at full weight for common-word names (`plugin:data` beat `mcp:cloud-hub`) | L2-20 |
| 6 | redundant-sibling used bare substring (`doc` ⊂ `docker-*`) → 40+ bogus demotions/query, O(n²) | conflict log was unreadable |
| 7 | **per-query max-normalization made abstention impossible** — L3 abstain measured 0.0/6 | negative tier |
| 8 | anti-trigger prose mined as a POSITIVE trigger, inverting authorial scope | L1a-skill-02 failure |
| 9 | `blueprint-subsub` from chained `str.replace` | `test_all_three_workflow_kinds_are_indexed` |
| 10 | `KeyError: slice(None, 10, None)` — registry `tools` is a dict in some rows, a list in others | first index run |
| 11 | tuning harness reported grid point [0] as "BEST" when NOTHING satisfied the constraint | scoring every row −1 |
| 12 | my own edit script asserted a string absent that its own inserted fixture contains | self-contradicting detector |

\#7 is the most consequential: the router confidently injected a capability for *"what is the
capital of Mongolia"* every time, and the cause was a normalization choice I had documented as
a feature ("comparable across queries").

---

## 12. Residual limitations — stated, not buried

* **The semantic lane is lexical, not neural.** BM25 + char-n-gram + no network. This is a
  deliberate trade for a gateable, hermetic suite (`ci-hygiene.md` §2). A neural lane would
  **likely (55-80%)** beat it on pure-paraphrase queries where the user shares no vocabulary
  with the capability — the L2 tier at 0.429 is where that shows. Settling experiment: run
  `metrics.evaluate()` over the same labelled set with `hooks/semantic-router/embed.py`
  supplying the recall lane and compare recall@5 on L2 specifically. **NOT RUN** — it needs
  Ollama, which this unit must not depend on. The two lanes are complementary: this one gates,
  that one serves live traffic.
* **L2-20 is a CONFIRMED miss with a named cause.** *"spin up a rented GPU box for a few hours
  and copy my data onto it"* shares exactly ONE discriminative token with `mcp:cloud-hub`
  ("gpu"). The correct `skill:cloud-infra-toolchain` ranks 3rd but below the abstention floor.
  Not tuned away: winning one query by moving a derived constant is overfitting to my own set.
* **L3 abstain is 0.667, and one of the two fires is a labelling disagreement.** L3-04
  *"translate this sentence into French"* → `skill:subtitle-translate` is arguably a defensible
  route; L3-05 *"what did I have for lunch yesterday"* → `skill:cost-tracking` is a genuine
  false fire. The label stands — relabelling L3-04 to improve the number would be tuning the
  test set.
* **precision@k for k>1 is structurally misleading here** and is reported but not optimized.
  Most queries have one gold while a decision returns several, so precision@5 is capped at
  1/|selected| and *falls* as the router surfaces more useful context.
* **The 18 cross-class same-name records** (`mcp:figma` / `skill:figma` / `plugin:figma`) are
  deliberately NOT merged — a server, a how-to and a plugin are related but not
  interchangeable, and collapsing them would be the pruning the spec forbids. Consequence:
  class precedence puts `skill:` first, so a same-named MCP server can lose to its skill.
* **`ROUTING_HOME`-dependent.** Live-tree counts (328 skills, 98 plugins, 14 servers) are this
  machine's. The platform counts are repo-fixed and portable.

---

## 13. Suite baseline — and a correction to the pinned number

| capture | result |
|---|---|
| **my own pre-edit baseline** (before any file was written) | **3,071 passed / 14 skipped / 0 failed** |
| **final, whole `platform/` tree** | **3,829 passed / 14 skipped / 0 failed** |
| routing suite alone | **114 passed** in 3m57s |

The final run is **zero-failure**, which also settles the marketplace question below: that test
passes once the sibling's tree is quiescent.

**The pinned 2,767 baseline is STALE** — corroborating siblings D1 (2,812 / 3,067) and D3
(2,812). At my capture time the tree was already at 3,071, so the pinned figure should not be
used as a regression bar by anything downstream.

A full-suite run mid-way through this unit reported two failures; both are accounted for and
neither is a regression from this unit:

1. `platform/routing/test_descriptions.py` — my own assertion, since narrowed (see §10).
   It fired *because* this unit started reading real vendor manifests. Fixed by scoping the
   claim, not by reverting the improvement.
2. `platform/marketplace/mkt/test_cli.py::test_export_import_round_trip` — **a concurrent
   sibling's in-flight work, established on three independent signals**: `platform/marketplace`
   is **untracked** (0 files under `git ls-files`); its newest file mtime is **75 minutes after**
   my baseline capture; and `pytest platform/marketplace platform/routing` together is
   **261 passed / 0 failed**. This unit writes nothing outside `platform/routing/`.

## 14. Reproduce

```
python platform/routing/cli.py all          # every gate -> SUCCESS:routing-all gates=5/5
python platform/routing/cli.py metrics --out platform/routing/MEASUREMENTS.json
#   ^ ALWAYS use --out, never `> file`: a shell redirect appends the terminal marker
#     after the closing brace and the .json stops parsing (caught by its own test).
python platform/routing/cli.py tune         # re-derive SCORE_FLOOR / Z_THRESHOLD
python platform/routing/cli.py index        # inventory census, fail-closed floors
python platform/routing/cli.py route "the panel converged before anyone argued the other side"
python -m pytest platform/routing -q        # 114 tests
```

Lint/format: `ruff check` and `ruff format --check` clean under CI's **pinned 0.15.17**
(not the ambient version — a local green against the wrong version verifies nothing), and every
file in this tree is **LF** in the working tree so the bytes CI checks out are the bytes
measured here.
