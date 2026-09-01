# Plan Review Gate — Completeness

**Artifact reviewed:** `C:\Users\Prekzursil\.agents\PERPLEXITY-COMPUTER-WORKFLOWS-BLUEPRINT_2026-08-29.md`  
**Lens:** Completeness — every user requirement covered with implementation-level specificity; all 40 workflows, not a sample.  
**Mode:** Read-only adversarial review. No files edited except this review. No commits.  
**Date:** 29.08.2026  

## Verdict

**FAIL**

Blocking omissions remain. A cold-start implementer cannot compile the catalog to `WorkflowDefinition` YAML, shared `SourceRecord`/tier semantics, or the eight-subsection node contract for a material subset of workflows.

**Re-read:** Blueprint lines 1–6994 and the four cross-check artifacts were inspected. After this file was written, it was re-read: verdict **FAIL**, blockers **12**, majors **9**, minors **8**, grades **OK 24 / ENUM 9 / SKELETON 7**, path below. WF-11 `validate` phase confirmed at blueprint line 3439 (census cell corrected on re-read).

**Path:** `C:\Users\Prekzursil\.agents\PERPLEXITY-BLUEPRINT-REVIEW-COMPLETENESS_2026-08-29.md`

## Counts

| Check | Result |
|---|---|
| Workflows inspected | **40 / 40** |
| Exact titles vs SOURCE-CROSSCHECK §4 | **40 / 40 match** |
| Mechanical eight `####` headings, verbatim, in order | **40 / 40 present** |
| Reconciliation actions vs REUSE-MCP census (7/6/14/9/0/4) | **40 / 40 action-class match** |
| Implementation-ready (legal phases, legal capability IDs, numbered nodes with emit contracts, intensity table, failure table) | **24** |
| Compile-blocked (illegal phase enum, undefined capability, illegal risk-factor enum, or uninhabited NEW owner) | **9** |
| Outcome-prose / skeleton (nodes not implementable) | **7** |
| Blockers | **12** |
| Major improvements | **9** |
| Minor improvements | **8** |
| Implementation NOT-CHECKED items | **14** (plus blueprint’s own aggregated list) |

## Cross-check inputs (read)

- `PERPLEXITY-WORKFLOWS-SOURCE-CROSSCHECK_2026-08-29.md` — 40 names + card intent
- `PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md` — action/owner/MCP
- `PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md` — D1–D9 floors, TTL, PII, disclaimers
- `RESEARCH-APPROVAL-GATES_2026-08-29.md` — R0–R3, receipts outrank votes, verdict schema

Required eight subsections (blueprint §21.2 / SH-TMPL-1): (1) Purpose and user story (2) Inputs and configuration options (3) Data sources and knowledge bases (4) Tool chain and mechanisms (5) Internal data structures / schemas (6) Step-by-step execution flow (7) Output format and UX behavior (8) Logging, validation, and safety.

---

## Blockers

Each item is independently sufficient to keep this gate at FAIL.

### B1 — Dual source-tier SSOT: Part 00 T4/T5 ≠ RISK T4/T5

**Evidence**

- Blueprint §8.1 (lines 1153–1161): **T4** = “Community / user-generated” (forums, social, wikis); **T5** = “Model-internal recollection”.
- RISK §3.1: **T4** = “Owner-supplied local files”; **T5** = “Model output, untitled web, forums, SEO blogs, social posts, preprints without label”.
- Catalog uses RISK T4 for owner files: WF-18 line 4233 (“Owner files are T4”); WF-31 line 6070 (`OWNER-T4`); WF-34 line 6411 (`profile.yaml` T4); WF-35–40 owner labs/wearables as T4.

**Why blocking:** `SourceRecord.tier` cannot be coded. An owner CV would be T4 under RISK and is not a defined Part 00 source class; a forum post is T4 under Part 00 and T5 under RISK.

**Repair:** Add a Part 00 erratum that **adopts RISK §3.1 as the catalog source-tier SSOT** (or publish a 1:1 mapping table). Rewrite §8.1. Relabel every `T4`/`T5` mention in WF-01–WF-40 to the chosen enum. Do not leave both definitions live.

### B2 — Dual `SourceRecord` contracts; identifier/TTL/full-text fields missing from the shared schema

**Evidence**

- RISK §3.5 requires `canonical_id_type`, `canonical_id`, `ttl_seconds`, `expires_at`, `full_text_read`, `jurisdiction`, `pii_class`, `license_or_tos`, `cache_ok`, `stale_for_claim_types`, `domain`.
- Blueprint §6.3 example (lines 780–807) has none of those. It has `url_canonical`, `independence_group`, `trust.injection_scan`, `accessed_at`.
- WF-04 success criterion (line 2606) and D1 overlay require `full_text_read: true` and PMID/NCT/DOI on every study. WF-06/WF-07/WF-17/WF-21 consume “unchanged `SourceRecord`” while depending on those fields.
- P0 (line 1951) claims “All ten JSON Schemas” but §6 only gives JSON *examples*; `registry/schema/workflow-definition.schema.json` and `schemas/cap/*.json` are named, not specified.

**Why blocking:** Identifier gates (`identifier_shape_check`), claim-type TTL, and `citation_coverage` cannot be implemented on the shared record. RISK and Part 00 both claim to be normative.

**Repair:** Extend §6.3 `SourceRecord` with the RISK §3.5 fields (or an explicit `extensions.d1`/`d2`/`d3` object). Publish the ten draft-2020-12 schema files in-repo, including capability I/O schemas. Add a field-mapping appendix RISK→Part 00. WF-04/06/07/17/21 must stop saying “consumed unchanged” until the shared record can hold `canonical_id` and `full_text_read`.

### B3 — Illegal lifecycle phases (`validate` and Part 05 invented phases)

**Evidence**

- §3.1 (line 290) phases: `discover → recall → grill → plan → plan-review → execute → spec-review → quality-review → acceptance → capture`. **SH-LIFE-1** (line 292): every node MUST declare exactly one of these.
- **WF-05** line 2807, **WF-08** 3184, **WF-09** 3273, **WF-10** 3356, **WF-12** 3522, **WF-18** 4253, **WF-19** 4340: `Phases: validate, …` and node `1. … (validate, gate)`.
- **WF-31** lines 6050–6061: `intake, discover, retrieve, normalize, verify, synthesize, validate, review` claimed as “subset per §3.1” — **false**.
- **WF-34** line 6445: `intake, normalize, synthesize, validate, review`.
- **WF-35–40** node lists use no legal phase enum (see B4).

**Why blocking:** `graph.nodes[].phase` will fail L1 schema validation. Resume/checkpoints keyed by phase cannot run.

**Repair:** Map `validate` → `discover` or a `kind: gate` node in `plan-review`/`spec-review`. Map WF-31/34 phases onto the ten names. Rewrite every node line to `N. node_id (phase, kind, capability) → does → emits`.

### B4 — WF-34 through WF-40 describe outcomes without implementable nodes

**Evidence (not a sample — all seven):**

| ID | Lines | Defect |
|---|---|---|
| WF-34 | 6444–6448 | Arrow chain `load_profile → validate_zero_fab → …`; phases illegal; no per-node emit; no `graph.edges` |
| WF-35 | 6554–6559 | Arrow chain; `complex` engine with no loop edge, no `max_depth`, no numbered emits |
| WF-36 | 6616–6644 | **No intensity table** (SH-TMPL §21.2 slot 2 required); no numbered nodes; incomplete failure table |
| WF-37 | 6699–6726 | No intensity table; arrow chain; optional D1 literature not a node |
| WF-38 | 6782–6816 | No intensity table; no `sources.min_tier` / `min_independent` / `recency_max_days`; one-line failure “portal send → DENY” not a table |
| WF-39 | 6851–6871 | No intensity table; §6 is outcome prose: “Screen cardiac/acute injury → if fail, escalate → else compose plan” |
| WF-40 | 6915–6934 | No intensity table; arrow chain; no capability IDs on nodes; no heartbeat/preview/degradation UX |

Template §21.2 slot 6 (lines 2082–2091) requires engine+bounds, `lifecycle.phases_used`, numbered `N. node_id (phase, kind, capability) → … → emits`, branches/foreach/joins, artifact-emitting nodes, approval points, resume.

**Repair:** Rewrite WF-34–WF-40 to the density of WF-06 (lines 2923–2947) or WF-25 (lines 5201–5223). Restore intensity tables. Add failure tables with Error class / Behavior / User-visible message. Declare `graph.edges[]`. For MERGE_ALIAS modes (36, 38–40), either inline the subgraph nodes or `$ref` a named node list inside WF-35 with **copied** node IDs — a sentence “routes via health-review dispatcher” is not a graph.

### B5 — Undefined capability IDs: `llm.cluster`, `llm.structure`

**Evidence**

- §7.1 LLM IDs (lines 1067–1070): `llm.rewrite`, `llm.summarize`, `llm.extract`, `llm.classify`, `llm.judge` only.
- `llm.cluster`: WF-08 lines 3169, 3190; WF-09 lines 3258, 3276.
- `llm.structure`: WF-18 lines 4239, 4257; WF-19 lines 4325, 4343.

**SH-TMPL** checklist item 7 (line 2156): every declared capability must exist in §7.1.

**Repair:** Add `llm.cluster` and `llm.structure` to §7.1 **or** replace usages with `llm.extract` + named `output_schema` (`KeywordCluster`, `DeckSpec`, `WebsitePlan`).

### B6 — Invented §13.2 risk-factor enums on Part 02 (and WF-18/19)

**Evidence:** §13.2 (lines 1428–1440) closed set: `medical_advice`, `personal_health_data`, `legal_advice`, `financial_advice`, `financial_personal_data`, `image_identity`, `image_rights`, `browser_authenticated`, `external_action`, `public_publication`, `irreversible_local`.

Invented factors:

| ID | Line | Illegal factors |
|---|---|---|
| WF-05 | 2754 | `public_web_content`, `owner_property_context` |
| WF-08 | 3130 | `seo_estimates`, `owner_property_data` |
| WF-09 | 3219 | `authenticated_ads_account`, `potential_spend` |
| WF-10 | 3306 | `public_web_content`, `competitor_observation` |
| WF-11 | 3389 | `copyright_provenance`, `public_web_content` |
| WF-12 | 3471 | `commerce_pricing`, `owner_store_context` |
| WF-18 | 4202 | `factual_presentation`, `owner_content` |
| WF-19 | 4287 | `user_facing_site`, `deployment_boundary` |

Checklist item 8 (line 2157): every risk factor must exist in §13.2.

**Repair:** Map onto the closed set (`image_rights`, `browser_authenticated`, `external_action`, `public_publication`, plus `SH-RISK-1` runtime escalation) **or** extend §13.2 with these names, minimum tiers, and disclaimer IDs. Until then `risk.factors` cannot validate.

### B7 — Disclaimer IDs cited with no registry body (SH-RISK-3)

**Evidence:** SH-RISK-3 (line 1449): IDs resolve from `safety/disclaimers.yaml`; domain parts MUST NOT author prose. Part 00 never lists YAML keys or verbatim strings except the YAML example `DISC-MED-1`, `DISC-NOT-A-CLINICIAN` (line 516).

Cited but undefined in Part 00: `DISC-WEB-1` (WF-05/10/11/12/19), `DISC-SEO-1` (WF-08/09), `DISC-DOC-1` (WF-20 lines 4480–4490 — self-notes registration is missing), `DISC-CAREER-1` (WF-25–33), `DISC-IMAGE-SYNTHETIC-1` (WF-28), `DISC-LEGAL-1`, `DISC-FIN-1`. WF-31 lines 6076–6077: housing fraud notice “when implemented” — **no ID**.

RISK matrix already has the verbatim D1–D9 disclaimer paragraphs. They are not bound to IDs in Part 00.

**Repair:** Add Part 00 §13.3 (or the YAML contents) with **every** ID → exact text copied from RISK. Bind D6 listing-fraud text to `DISC-HOUSING-1` and cite it from WF-31. Do not leave “register later” as the catalog contract.

### B8 — `SH-SEC-PHI` / `SH-SEC-FIN` / `SH-SEC-IDENTITY` are matrix rows, not rules

**Evidence:** §12.4 (lines 1409–1411) lists the IDs. §12.1–12.3 define only INJ, SSRF, BROWSER. PHI handling is scattered in §11.1 (egress denied by default). Clinical workflows (WF-04, 06, 07, 35–40) require `SH-SEC-PHI` as if it had INJ-style SHALL statements (local-only, no shared cache, `cloud_phi_consent`, query hashing).

**Repair:** Write **SH-SEC-PHI-1…n**, **SH-SEC-FIN-1…n**, **SH-SEC-IDENTITY-1…n** with the RISK D8/D9 controls (P4 local-only, no extra-vendor PHI, no face templates, hash-chain). Point §12.4 at those IDs.

### B9 — NEW owner uninhabited: WF-08 `canonical_owner: none` breaks WF-09 MERGE_ALIAS

**Evidence**

- Matrix WF-08: NEW → one thin `seo-keyword-workflow` owner.
- Blueprint WF-08 line 3131: `action NEW · canonical owner none`.
- Blueprint WF-09 line 3220: `MERGE_ALIAS · canonical owner workflow:WF-08`.
- §5.5.1: `none` is valid only with `NEW`. §5.5.2 MERGE_ALIAS: canonical owner is “the surviving asset”.

**Why blocking:** Ads mode aliases to a workflow whose owner is explicitly nothing. Implementer cannot decide skill vs workflow vs adapter package.

**Repair:** Set WF-08 `canonical_owner` to `skill:.agents/skills/seo-keyword-workflow` (matrix) **or** `workflow:WF-08` if the recipe *is* the owner. Point WF-09 at that same owner’s `ads` mode. Do not use `none` when another workflow MERGE_ALIASes to it.

Same pattern (weaker): WF-31 line 5960 `canonical_owner internship-housing-finder` and WF-35 line 6482 `health-review` omit the required `skill:` / `workflow:` / `mcp:` prefix (§5.5.1). **Repair:** `workflow:WF-31` / `skill:.agents/skills/health-review`.

### B10 — `graph.edges[]` required in the registry schema, absent from all 40 catalog entries

**Evidence:** §5.2 (line 435) `graph.edges[]` is required. Catalog workflows give prose node lists only. Class A (e.g. WF-06, WF-25) is recoverable by a mechanical translator. Class C is not (B4). Complex-engine cycle edges (WF-06 line 2944, WF-07 line 3086, WF-08 line 3171) are described in English, not `{from, to, when}`.

**Repair:** For every workflow, emit `graph.nodes[]` and `graph.edges[]` YAML (appendix or per-WF block) including `when` predicates and loop bounds. P0 cannot exit on “ratified schemas” while the catalog has zero edges.

### B11 — Approval-gates / RISK inheritance is incomplete on skeleton health/housing UX

**Evidence:** RESEARCH-APPROVAL-GATES requires deterministic receipts, `FAILED_TO_RUN` not green, and the verdict schema. WF-07 (lines 3037, 3105) implements this correctly (`no_vote_as_truth`, reproduce-then-veto). WF-35–40 and WF-31 do not name `ReviewVerdict` fields, `missing_or_aborted`, or `human_approvals.final_revision_covered` except WF-38’s one-liner. WF-36 escalation for ED/pregnancy is policy prose without a gate node or receipt shape.

**Repair:** Every R2 workflow must list deterministic `check_id`s, panel yes/no, `human_required`, and the exact `ReviewVerdict.verdict` values on fail — copy WF-06 §8 (lines 2958–2977) and WF-07 §8 (lines 3101–3119).

### B12 — Source floors / claim-type TTLs missing or non-binding on several workflows

**Evidence**

- Template slot 3 requires `sources.min_tier`, `min_independent`, `recency_max_days`, cache policy, volatility class.
- **WF-36** lines 6620–6627: TTL as “guidelines `slow` 7d” but no `min_tier` numeric floor in the required triple; USDA/DRI named but no identifier pattern (`fdc_id`).
- **WF-38** §3 (lines 6784–6788): no min_tier / min_independent / recency_max_days.
- **WF-39/40** §3: guidelines named; no `recency_max_days`; wearable TTL “session-only” not a claim-type table.
- **WF-31** listing TTL 6h is present (good) but `sources.recency_max_days: 0.25` (line 6006) is not a valid `int \| null` per §5.2 line 438.
- Part 00 cache classes (15 min `fast`) vs RISK D6 6h listing TTL vs WF-31 “tighter than §9.2 default 15m” (line 6011) — **internally contradictory** (6h is looser than 15m, not tighter).

**Repair:** Every workflow §3 must set the three `sources.*` fields with types that match §5.2. Add claim-type TTL tables by reference to RISK domain rows (D1 table lines 254–264, D6 525–533, D9 633–640). Fix WF-31’s 6h vs 15m sentence. Use `ttl_override_s: 21600` for listings instead of `recency_max_days: 0.25`.

---

## Major improvements (non-blocking if blockers are fixed, still required before implementation)

### M1 — SH index omits live IDs

§22 (line 2198) lists `SH-ROAD-1 … SH-ROAD-3`; **SH-ROAD-4** exists at line 1970 and is cited at line 6968. Index lists `SH-TEST-1 … SH-TEST-8`; **SH-TEST-9** exists at line 1886. Index omits `SH-SEC-PHI` / `SH-SEC-FIN` / `SH-SEC-IDENTITY` as first-class IDs.

**Repair:** Regenerate §22 from a mechanical scan of `**SH-` definitions.

### M2 — MERGE/ALIAS vs `MERGE_ALIAS`

Matrix uses `MERGE/ALIAS`. Schema enum is `MERGE_ALIAS` (line 633). WF-03/WF-24 document both; WF-09/22/23/36/38–40 do not.

**Repair:** One enum in all four artifacts. Prefer `MERGE_ALIAS` with a matrix footnote.

### M3 — WF-20 `domain_family: prompt-content` (line 4374)

Batch is Part 03 (evidence-professional). Effective class “inherited from document” is not a `domain_family` enum value. Floor selection (§8.2) will use prompt-content (weak) for a QA pass that can inherit clinical/legal/finance.

**Repair:** `domain_family: prompt-content` plus a required `sources.floor_from: document.domain` field, **or** `finance-legal` with runtime SH-RISK-1 (already described). Encode it in §5, not a parenthetical.

### M4 — SH-INT-1 voice floor vs Part 02 intensity tables

SH-INT-1 (line 1472): every **multi-model** step ≥3 independent voices. WF-05/08–12/18/19 set Voices = 0. That is legal only if those workflows declare **no** `llm.judge` fan-out. Several still use `llm.extract` as the sole model. State `multi_model: false` in the preamble so A19 does not fail the voice floor.

### M5 — Browser default `(b)` vs teardown default `(c)`

RISK §4.1 / BR-1: default **(b)**. WF-10 line 3323 defaults `browser_profile` to `c`. Allowed as a tightening if labeled a deviation; currently not.

**Repair:** Add Deviations line: default ephemeral for third-party product sites (RISK D7 “(c) default for third-party”).

### M6 — Part 02 node lines omit `kind` and often omit capability on llm nodes

Example WF-05 line 2812: `extract_signals (execute, llm)` — missing `kind` enum (`llm` is used as kind, OK) but capability is implicit. WF-08 line 3190: `classify_cluster_map (execute, join, llm.cluster)` — `join` is a kind; capability on a join is undefined in §5.3.

**Repair:** Join nodes: `kind: join`, no capability, `inputs` from named upstream node_ids. LLM nodes: `kind: llm`, `prompt_ref`, `capability` omitted per §5.3 (capability required when `kind: tool` only). Make that explicit in each line.

### M7 — Cache reuse specified unevenly

Strong: WF-04 (fresh-only on guideline currency), WF-06 (D1 TTLs), WF-08 (SERP 24h / metrics 7d), WF-31 (fresh-only listings). Weak: WF-36–40 (PHI fresh-only one-liner, no serve-from-cache predicate). RISK §3.5 serve-from-cache rule (`cache_ok` ∧ `expires_at` ∧ hash ∧ ToS) is not cited in most §3 blocks.

**Repair:** One shared sentence per WF §3: “Serve cache iff SH-CACHE-1…7 and RISK §3.5 predicates; else refetch.” Name the volatility class of the **primary** claim type.

### M8 — Duplicate-capability residual: `health-review` modes vs six catalog IDs

Matrix requires one owner with six modes (good). WF-35 line 6534 says WF-36–40 “are aliases into subgraphs” but those subgraphs are not specified (B4). Until B4 is fixed, implementers will create six skills — exactly the duplicate surface the matrix forbids.

**Repair:** After B4, add a single `health-review.yaml` mode dispatch table: `mode → entry_node_id`.

### M9 — Roadmap P0 is not cold-start complete

§20 P0 requires ratified JSON Schemas + matrix. Schemas are examples. Disclaimer YAML absent (blueprint itself says so at 6984–6985). G-19 daily cap undefined (line 2215). Engine G-12 still Open (line 2210) while catalog already assigns `simple`/`complex` per WF.

**Repair:** Close G-12 in the decision log **or** mark every `graph.engine: complex` workflow as `blocked_until: G-12`. Ship schema files. Define daily cap or `NOT-CHECKED` it on every budget line.

---

## Minor improvements

1. **§2 terminology** (line 257): example `id` is `ch.004`; catalog IDs are `WF-NN`. Fix the example.
2. **WF-01 small Voices = 1** (line 2275): if critique lanes are skipped at small, say so; else it contradicts SH-INT-1.
3. **Canonical owner path style mixed:** `skill:.agents/skills/ui-audit/SKILL.md` (WF-05) vs `skill:.agents/skills/prompt-optimizer` (WF-01). Pick one.
4. **WF-32 LinkedIn MCP** correctly bounded (not alumni search). Add the same one-liner to WF-25 so job-board discovery cannot “recover” the MCP as a people API.
5. **WF-04 recency loosening** (line 2634) is correctly labeled owner-authorized. Repeat that pattern wherever RISK TTL is changed.
6. **Golden path casing:** `golden/WF-06/...` vs `golden/wf05/audit.md`. Normalize.
7. **WF-08 score formula** (line 3196) is implementable; extract it into the `KeywordCluster` schema as required fields so it cannot drift in prose.
8. **Companion SHA-256 table** (lines 6952–6964) is useful; completeness of those hashes was **not** re-computed in this review (NOT-CHECKED).

---

## Forty-workflow completeness census

Legend: **OK** = eight headings + legal phases + legal capability IDs + numbered nodes with emits + intensity table + §3 floors + §7/§8 shape sufficient to author YAML after B1–B2/B7–B10 shared fixes. **ENUM** = content exists but illegal phase/capability/factor/owner. **SKELETON** = outcomes without implementable nodes or missing required slots.

| ID | Title (matches CROSSCHECK) | Action (matches matrix) | Eight headings | §3 sources / TTL / cache | §5 schema example | §6 implementable nodes | MCP/reuse explicit | Grade |
|---|---|---|---|---|---|---|---|---|
| WF-01 | Prompt refinement | REUSE | yes | yes (T1 guides, 90d) | yes | yes (legal phases) | prompt-optimizer; no MCP | **OK** |
| WF-02 | Background removal | REUSE | yes | D8 rights/hash (Part 01 density) | yes (Part 01) | yes | imagegen; no MCP | **OK** |
| WF-03 | Message polish | MERGE_ALIAS | yes | D9-docs | yes | yes | humanizer | **OK** |
| WF-04 | Research update (clinical) | UPGRADE | yes | D1 map, PMID/NCT, claim TTLs | yes | yes (complex, bounds) | deep-research; firecrawl | **OK** |
| WF-05 | Website audit | REUSE | yes | T2, 24h, cache medium/fast | yes | nodes exist; **illegal `validate`**; illegal factors | ui-audit; playwright/chrome/firecrawl | **ENUM** |
| WF-06 | Evidence brief (medical) | COMPOSE | yes | D1 inverted order, CD/PMID | yes | yes | compose leaves; pdf-reader parked | **OK** |
| WF-07 | Medical evidence council | COMPOSE | yes | D1 + stance T2 bar | yes | yes; gates match approval-gates | WF-06 + council | **OK** |
| WF-08 | SEO keyword research | NEW | yes | D4 TTLs, VENDOR-ESTIMATE | yes | **`validate`; `llm.cluster`; owner `none`** | firecrawl; GSC/Ads absent | **ENUM** |
| WF-09 | Keyword generator (Google Ads) | MERGE_ALIAS | yes | D4; no customer ID | yes | **`validate`; `llm.cluster`; aliases empty owner** | same | **ENUM** |
| WF-10 | Product teardown | COMPOSE | yes | D7 6h price TTL | yes | **`validate`** | deep-research + ui-audit | **ENUM** |
| WF-11 | Brand inspiration | COMPOSE | yes | rights/no-clone | yes | **`validate` (line 3439)**; illegal factors | design-studio + imagegen | **ENUM** |
| WF-12 | Store optimizer | COMPOSE | yes | 6h price; no CMS write | yes | **`validate`**; illegal factors | compose; no Shopify MCP | **ENUM** |
| WF-13 | Product photos | REUSE | yes | D8 | yes | yes | imagegen | **OK** |
| WF-14 | Post creator | COMPOSE | yes | draft-only; R3 publish | yes | yes | humanizer + imagegen; no social MCP | **OK** |
| WF-15 | Document summary | COMPOSE | yes | span grounding; P4→R2 | yes | yes | format leaf; markitdown denied | **OK** |
| WF-16 | Filetype converter | UPGRADE | yes | no overwrite `_v2` | yes | yes | nutrient; local-first | **OK** |
| WF-17 | Memo draft (investment) | COMPOSE | yes | D3 accession/TTL split | yes | yes | EDGAR HTTPS; no finance MCP | **OK** |
| WF-18 | Slide creation | REUSE | yes | T2; domain override note | yes | **`validate`; `llm.structure`**; illegal factors | slides owner | **ENUM** |
| WF-19 | Website builder | COMPOSE | yes | no clone; deploy gated | yes | **`validate`; `llm.structure`**; illegal factors | prototype + design-studio | **ENUM** |
| WF-20 | Final pass (document QA) | COMPOSE | yes | D9; original hash | yes | yes | format leaves; DISC-DOC-1 unregistered | **OK** (blocked by B7 ID only) |
| WF-21 | Legal research | NEW | yes | D2 CELEX/ECLI; 24h in-force | yes | yes | `legal-workflow`; no legal MCP | **OK** |
| WF-22 | Draft a contract | MERGE_ALIAS | yes | clause provenance | yes | yes | legal-workflow draft | **OK** |
| WF-23 | Contract review | MERGE_ALIAS | yes | PI-CRIT; no auto-sign | yes | yes | legal-workflow review | **OK** |
| WF-24 | Thumbnail creator | MERGE_ALIAS | yes | D8 | yes | yes | imagegen preset | **OK** |
| WF-25 | Job finder | UPGRADE | yes | D5 12h vacancy; career-page T0 | yes | yes | cv-studio jobs; boards absent | **OK** |
| WF-26 | Interview prep | UPGRADE | yes | zero-fab | yes | yes (Part 04 density) | cv-studio interview | **OK** |
| WF-27 | Cover letter generator | REUSE | yes | T4 facts only | yes | yes | cv-studio cover | **OK** |
| WF-28 | LinkedIn headshot | COMPOSE | yes | D8 P6; AI disclose | yes | yes | cv-studio + imagegen | **OK** |
| WF-29 | Scholarship finder | COMPOSE | yes | funder T0; 24h deadline | yes | yes | cv-studio + grant skill | **OK** |
| WF-30 | Career explorer | UPGRADE | yes | ESCO/ISCO/COR | yes | yes | cv-studio career; `data.occupations` NOT-CHECKED | **OK** |
| WF-31 | Internship housing finder | NEW | yes | D6 sources named; **bad `recency_max_days: 0.25`**; TTL math wrong | yes | **illegal phases**; no DISC-HOUSING | NEW owner unprefixed; maps MCP absent | **ENUM** |
| WF-32 | Alumni finder | COMPOSE | yes | no dossier; MCP not search | yes | yes | cv-studio alumni; LinkedIn MCP NOT-CHECKED | **OK** |
| WF-33 | Resume editor | REUSE | yes | one profile.yaml | yes | yes | cv-studio ATS; not resume-session | **OK** |
| WF-34 | Behavioral story generator | UPGRADE | yes | T4 profile; no web default | partial | **SKELETON** | cv-studio stories | **SKELETON** |
| WF-35 | Health review | NEW | yes | D1+D9 named; P4 local | partial JSON | **SKELETON**; owner unprefixed | NEW health-review | **SKELETON** |
| WF-36 | Nutrition planner | MERGE_ALIAS | yes | USDA named; **no intensity table**; weak floors | partial | **SKELETON** | alias into missing subgraph | **SKELETON** |
| WF-37 | Lab results interpreter | COMPOSE | yes | report T4; no invented ranges | yes-ish | **SKELETON**; no intensity table | pdf-reader parked | **SKELETON** |
| WF-38 | Visit prep assistant | MERGE_ALIAS | yes | **no min_tier triple** | partial | **SKELETON** | portal (a) only explicit — good intent, no nodes | **SKELETON** |
| WF-39 | Fitness coach | MERGE_ALIAS | yes | ACSM/WHO named | field list only | **SKELETON / outcome prose** | alias | **SKELETON** |
| WF-40 | Sleep & recovery coach | MERGE_ALIAS | yes | AASM/CDC named | field list only | **SKELETON** | alias | **SKELETON** |

**Grade totals:** OK 24 · ENUM 9 · SKELETON 7.

Part 01 (WF-02, 03, 13, 14, 15, 16, 24) was inspected via heading grep plus preamble/reconciliation/risk-factor lines and, for WF-01, full §1–§8. Those eight follow the WF-01 node template (legal phases). Residual risk: if any Part 01 body used `validate` or undefined `llm.*`, it would move to ENUM; none appeared in capability greps except the Part 02 IDs in B5.

---

## Shared contracts and roadmap — cold-start sufficiency

**Sufficient as design intent:** layer stack (§1), state machine (§4), WorkflowDefinition field table (§5.2), node object (§5.3), capability family table (§7.1 minus B5), SH-SEC-INJ/SSRF/BROWSER bodies, SH-CACHE-1…7, SH-RUN-1…15, §16 UX skeleton, §17.4 seven-step protocol matching RESEARCH-APPROVAL-GATES, §18 tests, §20 phase order.

**Not sufficient to implement without the blockers:**

1. No JSON Schema documents on disk (P0 false-complete).
2. Source tier + SourceRecord conflict with RISK (B1, B2).
3. No `disclaimers.yaml` contents (B7).
4. No `graph.edges[]` instances (B10).
5. Complex engine optional but eight catalog workflows already require it (WF-04, 06, 07, 08, 17, 18, 19, 31, 35) — G-12 Open.
6. On-demand MCP router is design-only (matrix §5–§6); catalog correctly does not assume it. Adapters for `data.pubmed`, Keyword Planner, listings, GTFS remain NOT-CHECKED.

Roadmap text at lines 6966–6993 is honest that this file is not implemented capability. Honesty does not clear completeness: Parts 05 WF-34–40 are not “validated source definitions” at the same specificity as Parts 01/03/04 despite the companion SHA table claiming Part 05 is validated.

---

## MCP / reuse / no-duplicate-capability

**Pass:** Action census matches the matrix. Duplicate surfaces to avoid are named on every preamble. Career family keeps `cv-studio` + one `profile.yaml`. Legal family is one owner with three modes. LinkedIn MCP is not used as alumni search (WF-32). MarkItDown stays denied. Parked `pdf-reader` is not silently activated.

**Fail (completeness, not census):** WF-08 `none` (B9); unprefixed NEW owners (WF-31, WF-35); health modes without graphs (B4/M8). Those are how duplicates get built.

---

## Implementation NOT-CHECKED

Do not treat these as documentation PASS. They are runtime/provider gaps the blueprint already flags plus gaps this review did not independently re-verify.

From the blueprint’s own list (lines 6984–6991), still open:

1. Live health of `data.pubmed`, `data.clinical_trials`, `data.drug_labels`, `data.company_filings`, `data.market_series`, `data.market_quotes`, `data.legal_instruments`, `data.case_law`
2. Parked `pdf-reader` MCP
3. `DISC-DOC-1` (and all other DISC_*) registration
4. On-demand MCP router (shadow mode)
5. LinkedIn / Indeed / Handshake APIs absent
6. Recovered LinkedIn MCP: registration, auth, stdio live, live API
7. `data.occupations` / `data.labor_statistics` / `data.job_postings`
8. cv-studio venv on a run host
9. Two-party R2 human independence (single-owner household)
10. Maps/transit adapters, `data.property_listings`

Added by this review (not claimed live, not disproven):

11. Existence/byte-identity of the ten JSON Schema files referenced in P0
12. SHA-256 companion hashes (lines 6954–6964) — **not recomputed**
13. Whether Part 01 bodies (WF-02/03/13–16/24) contain any illegal phase not caught by the `llm.cluster`/`(validate,` greps
14. G-19 daily cap; G-12 engine packaging; capability I/O schemas under `schemas/cap/`

---

## Exact repair sequence (minimum to re-present this gate)

1. Reconcile §8.1 tiers and §6.3 `SourceRecord` to RISK §3.1/§3.5 (B1, B2). Publish JSON Schemas.
2. Add disclaimer YAML + SH-SEC-PHI/FIN/IDENTITY rule bodies (B7, B8).
3. Rewrite WF-34–WF-40 (and tighten WF-31 phases) to the WF-06/WF-25 node contract; add intensity tables (B3, B4, B12).
4. Replace `validate` / `llm.cluster` / `llm.structure` / illegal risk factors / `canonical_owner: none` (B3, B5, B6, B9).
5. Emit `graph.nodes` + `graph.edges` for all 40 (B10).
6. Re-run this completeness gate on the new blueprint revision. Do not sample.

Until that lands: **FAIL**.
