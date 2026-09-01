# Plan Review Gate — FEASIBILITY (adversarial, read-only)

**Artifact under review:** `C:\Users\Prekzursil\.agents\PERPLEXITY-COMPUTER-WORKFLOWS-BLUEPRINT_2026-08-29.md` (6,994 lines / 671,441 bytes)
**Reviewer lens:** Can a developer actually implement this on the stated Windows/local multi-agent estate?
**Date:** 29.08.2026
**Mode:** Read-only. No file under review was modified. No commit was made. Only this review file was written.

## VERDICT

**FAIL**

There are implementation-blocking defects. They are not stylistic: the blueprint declares capabilities that do not exist in its own capability registry, declares safety controls it never defines, cannot express in its registry schema what several of its own workflows require, merges two mutually incompatible normative taxonomies without a mapping, specifies two acceptance criteria that cannot be satisfied as written, and its duplicate-prevention gate cannot execute against the artifact it is supposed to check.

## Counts

| Category | Count |
|---|---:|
| Blocking findings (BLOCKER) | 13 |
| Non-blocking improvements (IMPROVEMENT) | 15 |
| NOT-CHECKED external dependencies newly surfaced by this review | 7 |
| NOT-CHECKED dependencies already carried by the blueprint (§"Aggregated NOT-CHECKED", lines 6982–6993) | 8 |

Severity scale used: **CRITICAL** (implementation cannot start or will produce an unusable contract), **HIGH** (a named subset of workflows cannot be built or accepted as written), **MEDIUM** (resolvable by an engineer but requires an owner/architect decision first), **LOW** (documentation integrity).

## Verification method and measured environment facts

Cross-checks were run against the four companion documents named in the task plus the live estate. Everything below was measured on 29.08.2026, not assumed.

| Probe | Result |
|---|---|
| Free physical RAM | **2.49 GB** free of 31.63 GB total (`Get-CimInstance Win32_OperatingSystem`) |
| `cursor-agent` | Present — `…\cursor-agent\versions\2026.08.28-e7f6d3b\cursor-agent.ps1` |
| `acpx` | **Absent from PATH** |
| `pandoc` (rank-1 adapter for `doc.convert`) | **Absent from PATH** |
| `magick` / ImageMagick (rank-1 adapter for `image.transform`) | **Absent from PATH** |
| `.agents\agents.json` MCP inventory | 40 servers; includes `firecrawl`, `playwright`, `chrome-devtools`, `basic-memory`, `pdf-reader`, `apify`, `scrapegraph`, `markitdown`, `tavily`. **No** `nutrient`, `openalex`, `jina`, `fal`, `linkedin`, `openai-images` |
| `.agents\safety\` (host of `disclaimers.yaml`) | **Does not exist** |
| `.agents\workflows\lifecycle.yaml`, `grill.yaml`, `agents.json`, `skills-index.md`, `local.json`, `secrets\enformation-cookies.txt` | All present |
| Canonical-owner skills named in the catalog | Present: `prompt-optimizer`, `imagegen`, `humanizer`, `deep-research`, `biomedical-paper-triage`, `scholarly-literature-review`, `institutional-literature-access`, `evidence-ledger-synthesis`, `pdf-reader`, `doc`, `slides`, `spreadsheet`, `ui-audit`, `ui-ux-pro-max`, `design-studio`, `design-system`, `prototype`, `clone-website`, `council`, `cv-studio`, `data-scraper-agent`, `browser-rail`, `nutrient-document-processing`. Absent (to be created): `legal-workflow`, `health-review`, `seo-keyword-workflow`, `internship-housing-finder` |
| `PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md` anchors | **Zero** `<a id=`, `<a name=`, or `{#…}` anchors. The file is a markdown table |
| Heading conformance (`SH-TMPL-7` / A18) | **PASSES.** 333 `####` headings = 320 workflow headings (40 × 8, exact strings, correct order) + 8 inside the §21.2 template code block + 5 legitimate Part-00 sub-headings. No renamed, reordered, extra, or missing subsection was found |
| Workflow identity set | `WF-01`…`WF-40` each appear exactly once, in numerical order, with `source_ref: user-spec:WF-NN` |
| Verdict schema fidelity | §6.9 preserves the `RESEARCH-APPROVAL-GATES_2026-08-29.md` "Workflow Verdict Schema" verbatim and only adds fields. **Conformant** |

Two things the blueprint gets right and that this review is not disputing: the eight-subsection template is mechanically clean across all 40 entries, and the fail-closed vocabulary (`NOT-CHECKED`, `FAILED_TO_RUN`, `disk-verified` vs `agent-claimed`) is applied consistently with `AGENTS.md`.

---

# BLOCKERS

## BLOCKER-01 — There is no capability for invoking an existing skill or a local script, yet the most common reconciliation action depends on it

**Severity:** CRITICAL

**Evidence.** §7.1 (lines 1046–1074) enumerates the complete capability set: eight families, none of which executes a local process, a Python script, or an existing `.agents` skill. `SH-ARCH-3` (lines 202–204) makes this exhaustive: "Capability IDs are the only names a workflow may use for tools." §21.3.2 item 7 (line 2154) makes it a lint: "Every declared capability exists in §7.1." Yet:

- §5.5.2 (line 644) defines `REUSE` as "The workflow is a thin registry entry that **routes to it**" — 8 workflows declare `REUSE` (WF-01, WF-02, WF-05, WF-13, WF-18, WF-24, WF-27, WF-33).
- WF-05 delta (line 2755): "Adds only a catalog route … **before the existing audit is invoked**."
- WF-18 delta (line 4203): "Adds only catalog metadata … **before the existing slide owner renders**," where the matrix (line 79) records the owner as `slides` plus "bundled render, overflow, montage, and font scripts."
- WF-25 execution flow node 2 (line 5206): `validate_zero_fab (discover, gate, **cv-studio validate**)`, with precondition (line 5134) "`cvstudio.py validate` **is callable**."
- A grep of the whole blueprint for `skill.invoke`, `proc.`, `script.run`, `shell.`, or `process.run` returns **zero matches**.

**Technical reason.** A `REUSE` workflow that cannot name a capability to invoke its `canonical_owner` is not implementable — it is a registry row that dead-ends. The `gate` node kind (§5.3, line 464) also has no execution binding: `capability` is required only when `kind: tool`, so a gate that must shell out to `cvstudio.py` has no defined mechanism, no `ToolInvocation` record (violating `SH-INV-1`, line 769), no timeout, no error mapping, and no side-effect classification. This is not an ambiguity an engineer can resolve by choosing; it changes L1, L2, the adapter contract, and the sandbox model.

**Exact repair.** Add to §7.1 a ninth primitive family with two capability IDs and their §7.2 adapter declarations:
- `proc.run` — execute an allowlisted local command; fields `argv_allowlist`, `cwd_root`, `env_allowlist`, `side_effects: local`, `determinism: quasi-deterministic`, `produces_untrusted_content: true` when it reads user files, plus stdout/stderr capture into `verify/`.
- `skill.invoke` — invoke a registered `.agents` skill by canonical reference and mode; fields `skill_ref`, `mode`, `input_schema`, `output_schema`, `side_effects` declared by the skill's own manifest.
Then add a `route` node kind to §5.3 for `REUSE` entries, and state in §5.5.2 exactly which capability a `REUSE` workflow uses to reach its owner.

---

## BLOCKER-02 — Every domain-data capability ID violates the pattern §7.1 defines for it

**Severity:** HIGH

**Evidence.** §7.1 line 1071 defines the family as `data.<domain>.<name>` — three dot-separated segments — and then gives five examples that are all **two** segments: `data.drug_interactions`, `data.company_filings`, `data.property_listings`, `data.job_postings`, `data.serp_metrics`. Part 00's own worked example (line 546) declares `optional: [data.drug_interactions]`. The catalog and the aggregated dependency list (line 6984, 6988, 6991) use `data.pubmed`, `data.clinical_trials`, `data.drug_labels`, `data.market_series`, `data.market_quotes`, `data.legal_instruments`, `data.case_law`, `data.occupations`, `data.labor_statistics`, `data.property_listings`, `data.job_postings` — 14 IDs, none matching the stated pattern.

**Technical reason.** §21.3.2 item 7 is a mechanical lint. Implemented literally against the §7.1 grammar, it rejects every workflow that declares a domain-data capability — which is most of Parts 03, 04, and 05. Implemented loosely, the lint is not mechanical and A19/`SH-TEST-9`'s "lints, not judgment calls" claim is false.

**Exact repair.** Change the §7.1 row to `data.<name>` with `^data\.[a-z][a-z0-9_]*$`, and add the 14 concrete IDs above as a normative enumeration in §7.1 so the lint has a closed set. If the three-segment form is genuinely wanted, rename all 14 (`data.clinical.trials`, `data.finance.company_filings`, …) and update every catalog reference and the aggregated dependency list.

---

## BLOCKER-03 — Three of the eight declared safety controls are never defined

**Severity:** CRITICAL

**Evidence.** §12.4 (lines 1404–1413) lists eight controls. §12 defines only three of them: `SH-SEC-INJ` (§12.1), `SH-SEC-SSRF` (§12.2), `SH-SEC-BROWSER` (§12.3); `SH-SEC-REDACT` and `SH-SEC-CRED` are defined in §11.2/§11.3. **`SH-SEC-PHI`, `SH-SEC-FIN`, and `SH-SEC-IDENTITY` have no definition anywhere in the document.** They are nonetheless declared as binding controls in Part 00's own example (line 611) and in 20 workflow entries — `SH-SEC-PHI` at lines 2726, 2959, 3102, 3898, 4271, 4489, 6489, 6568, 6653, 6735, 6812, 6878, 6941; `SH-SEC-FIN` at 3898, 4173, 4489; `SH-SEC-IDENTITY` at 2452, 3455, 3652, 5083, 5638.

**Technical reason.** §21.3.2 item 9 checks only that "Every safety control ID exists in §12.4" — i.e. membership in the applicability table, not the existence of a rule. So the conformance lint passes while the control is unimplementable: there is no rule text, no enforcement point, no `SafetyDecision` trigger, and no deterministic gate ID for the three controls that carry PHI handling, financial-identifier handling, and real-person likeness handling — precisely the controls guarding the highest-risk half of the catalog.

**Exact repair.** Add §12.5 `SH-SEC-PHI`, §12.6 `SH-SEC-FIN`, §12.7 `SH-SEC-IDENTITY`, each with: trigger condition, enforcement point (which node boundary), the `SafetyDecision.control` value emitted, the deterministic gate ID that verifies it (e.g. `phi_local_only`, `financial_identifier_redacted`, `identity_consent_recorded`), and the failure behavior. Then change §21.3.2 item 9 to require both membership in §12.4 **and** a resolvable definition anchor.

---

## BLOCKER-04 — The disclaimer registry that `SH-RISK-3` makes mandatory does not exist and is never enumerated

**Severity:** HIGH

**Evidence.** `SH-RISK-3` (lines 1449–1450): "Disclaimers are IDs resolved from `safety/disclaimers.yaml` and rendered verbatim. A domain part **MUST NOT** author disclaimer prose inline." Nine distinct IDs are referenced across the catalog: `DISC-MED-1`, `DISC-NOT-A-CLINICIAN`, `DISC-LEGAL-1`, `DISC-FIN-1`, `DISC-WEB-1`, `DISC-SEO-1`, `DISC-DOC-1`, `DISC-CAREER-1`, `DISC-IMAGE-SYNTHETIC-1` (lines 516, 1430–1433, 2727, 2825, 3203, 3373, 4174, 4490, 4643, 5235, 5588, 6569 among others). §13.2 names only three of the nine. No section of the blueprint contains the registry, its text, or even the closed ID list. Measured: `.agents\safety\` does not exist; the repo layout (line 1920) places `disclaimers.yaml` under `core/safety/`, a third path spelling.

**Technical reason.** Workflows are forbidden from authoring the prose and there is no source to resolve the IDs from, so no R2 workflow can render a compliant output and the disclaimer-presence assertion in `SH-TEST-7` (line 1853) cannot be written. The blueprint's own aggregated list acknowledges only three of the nine (lines 6984–6985), understating the gap.

**Exact repair.** Add a normative §13.3 table: ID → verbatim text (RO and EN per `SH-UX-5`) → triggering risk factor → required rendering position, covering all nine IDs. Fix the path to one spelling. Add to the P4 exit criteria (line 1955) a lint asserting every `risk.disclaimers[]` entry across all 40 definitions resolves to a registry row.

---

## BLOCKER-05 — The registry schema cannot express the claim-type TTLs and conditional source floors that its own workflows require

**Severity:** HIGH

**Evidence.** §5.2 defines `sources.recency_max_days` as a scalar `int | null` (line 438), `sources.min_independent` as a scalar `int` (line 437), and `cache.ttl_override_s` as a single `int` (line 440). But:
- WF-04 §3 (line 2642) specifies **seven** distinct claim-type TTLs in one workflow: PMID/DOI metadata 7 d, "latest evidence on X" 24 h, ClinicalTrials.gov status 24 h, Cochrane currency 7 d, NICE/WHO recommendation 24 h, drug-label safety communication 6 h, preprint 24 h.
- WF-17 delta (line 4044) requires "the latest-versus-immutable TTL split."
- WF-25 (line 5149) declares `min_independent` **conditionally**: "1 when T0 career page was read; 2 if only T3 boards exist."
- WF-35 (line 6524) declares `recency_max_days` as three values: "1 for 'current guideline'; 7 for PMID metadata; immutable for historical lab values."
- The governing companion, `PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md` §5.3, makes this binding: "TTL is a function of **claim type**, not only hostname."

**Technical reason.** `SH-ARCH-2` (lines 197–200) states that if a workflow needs behavior the schema cannot express, the correct fix is to extend the schema. That extension was never made. As written, at least four workflow definitions cannot be authored as valid YAML, so acceptance row A1 ("validates against the registry schema") is unreachable for them, and the cache/staleness gates cannot enforce the risk matrix's binding rule.

**Exact repair.** Extend §5.2 with:
- `sources.claim_classes[]`: `{class_id, description, min_tier, min_independent, recency_max_days, volatility_class}`, with `sources.*` scalars retained as the default for unclassified claims.
- `cache.claim_class_ttl_s`: map of `class_id → int`, and allow `cache` overrides on the §5.3 node object.
- A `Citation.claim_class` field in §6.4 so the `citation_coverage` and staleness gates can resolve which floor applies.
Bump `schema_version` to 2 and re-state A1 against it.

---

## BLOCKER-06 — Two incompatible normative taxonomies are merged with no mapping: source tiers, data classes, and injection levels

**Severity:** CRITICAL

**Evidence.** Part 00 §8.1 (lines 1154–1161) defines T0–T5 where **T3 = vendor/commercial**, **T4 = community/user-generated (forums, wikis, blogs)**, **T5 = model-internal recollection**. The source-risk matrix §3.1 defines a different T0–T5 where **T3 = commercial aggregator/platform UI**, **T4 = owner-supplied local files**, **T5 = model output, forums, SEO blogs, social posts, unlabeled preprints**. Owner-supplied files are untiered in Part 00 and are T4 in the matrix; forums are T4 in Part 00 and T5 in the matrix.

The catalog uses the matrix semantics: WF-35 line 6520 "**Owner (T4):** labs, meds, history, wearable exports"; line 6490 "every metric labeled `OWNER-T4` vs `GUIDELINE-T1`"; WF-39/WF-40 (matrix rows 100–101) "device exports are local T4."

The same split exists for data classification — Part 00 §11.1 (lines 1301–1308) uses `PUBLIC | INTERNAL | PII | PHI | FINANCIAL | SECRET`; the matrix §3.2 uses `P0–P6`. Catalog entries use both in the same paragraph (WF-35 line 6490 "P4 stays local" while its input table classifies the same data `PHI`; WF-32 matrix row "P2 minimization"). And prompt-injection exposure levels `PI-LOW / PI-MED / PI-HIGH / PI-CRIT` are used in at least 12 workflow safety sections (lines 2726, 2959, 4173, 4489, 4798, 4955, 5234, 5372, 6212, 6412, 6692, 4877) but exist **only** in the matrix §3.3 — Part 00 §12 never defines them.

**Technical reason.** §8.2 sets the `clinical-health` floor at T1. Under Part 00's table, owner lab documents tagged T4 are "community/user-generated" and fail the floor; under the matrix's table they are legitimately owner facts. A tier is a machine-checked enum feeding `citation_coverage`, `min_tier`, and corroboration counting — two conflicting definitions of the same enum value cannot both be implemented, and the blueprint's authority order (lines 80–90) does not resolve taxonomy conflicts between Part 00 and a "normative companion constraint." `SH-TMPL-4` ("Every field name used must exist in §5 or §6") is violated by every `P0–P6` and `PI-*` usage.

**Exact repair.** Pick one taxonomy and publish it once in Part 00:
1. Separate the two dimensions that are currently collapsed: `tier` (authority: T0–T5) and `provenance` (`owner-supplied | retrieved | model-internal`). Reclassify owner files as `provenance: owner-supplied` with an explicit tier, and delete the T4 collision.
2. Add to §11.1 a normative mapping table `P0…P6 ↔ {PUBLIC, INTERNAL, PII, PHI, FINANCIAL, SECRET}`, and declare which one is the machine-readable enum stored in `RunContext`/`SourceRecord`.
3. Add `PI-LOW…PI-CRIT` to §12.1 as a normative field with the control set each level triggers.
4. Re-lint all 40 entries against the chosen vocabulary.

---

## BLOCKER-07 — Two divergent `SourceRecord` schemas, both normative, both gated on

**Severity:** HIGH

**Evidence.** Part 00 §6.3 (lines 779–807) defines `SourceRecord`. The source-risk matrix §3.5 defines a *different* mandatory disk record ("Every retained source writes a disk record with at least: …") containing `domain`, `canonical_id_type`, `canonical_id`, `ttl_seconds`, `full_text_read`, `license_or_tos`, `pii_class`, `cache_ok`, `independent_of[]`, `stale_for_claim_types[]` — **none of which exist in §6.3**. The catalog gates on the matrix fields: WF-04 line 2713 "any numeric outcome without `full_text_read: true` **blocks**"; §17.3 emits `full_text_read_ratio` (line 1733) with no field to compute it from; WF-04 line 2654 and WF-21 line 4574 define `canonical_id_type` inside workflow-local schemas, duplicating what should be shared.

**Technical reason.** Acceptance row A1 and test level L1 require every schema to validate its examples. Two normative shapes for the same record means either the L1 suite is written against a schema the gates do not use, or the gates reference fields the schema rejects. The `provenance_chain` walker (`SH-OBS-3`) and the independence counter both depend on fields that exist in only one of the two.

**Exact repair.** Merge the matrix §3.5 field set into Part 00 §6.3 as the single normative `SourceRecord` (adding `canonical_id_type`, `canonical_id`, `full_text_read`, `license_or_tos`, `cache_ok`, `stale_for_claim_types[]`, and reconciling `pii_class` with the §11.1 decision from BLOCKER-06), state in §0.3 that the matrix's §3.5 is superseded by §6.3, and delete the workflow-local re-declarations of `canonical_id_type`.

---

## BLOCKER-08 — Acceptance rows A4 and A11 are impossible to satisfy as specified

**Severity:** HIGH

**Evidence.** A4 (line 1866): "Happy-path golden run reproduces **byte-identically** from cassettes." A11 (line 1873): "Checkpoint/resume verified: kill mid-run, resume, **same final artifact hash**." But every artifact by construction embeds volatile content:
- §16.1 item 1 (line 1640) — the header carries `run_id` (a ULID, §2 line 258) and the start time.
- §16.1 item 5 (line 1645) — Provenance renders "retries, fallbacks" counts, which necessarily differ between an uninterrupted run and a killed-and-resumed run.
- `SH-SRC-9` (line 1197) — every citation renders an access date.
- §6.6 (line 885) — export names embed `{YYYY-MM-DD}`.
- §18.4 (lines 1849–1854) addresses only LLM nondeterminism (recorded-response player); it says nothing about clock, ULID, or counter normalization.

**Technical reason.** A4 and A11 are required rows; `NOT-CHECKED` fails the row (line 1859) and `SH-TEST-8` explicitly calls A11 the one usually skipped and therefore mandatory. As written they can never pass, which means **no workflow can ever reach `implemented` status** — the rubric blocks its own roadmap at P7.

**Exact repair.** Add §18.4a "Deterministic render mode": frozen clock injected via `RunContext.created_at`, seeded/deterministic `run_id` derivation in test mode, and a normalization filter that masks `run_id`, timestamps, durations, retry/fallback counters, and absolute paths before diffing. Restate A4 as "byte-identical **after normalization**", and restate A11 as "the substantive-payload hash (artifact content excluding the Provenance and Header sections) is identical, and the resumed run's manifest records the interruption."

---

## BLOCKER-09 — `scheduled` execution mode and 900-second health probes have no owning component and imply a daemon the estate forbids

**Severity:** HIGH

**Evidence.** §5.2 makes `execution.modes` a required field whose enum includes `scheduled` (line 422); `scheduled` is used in 18 places across the catalog (e.g. WF-25 line 5119 permits `background`/`scheduled` re-fetch of public career pages). §7.2 declares `"health_probe": { "kind": "cheap_call", "interval_s": 900, … }` (line 1098) and `SH-TOOL-2` (lines 1109–1112) makes adapter selection depend on live health. A grep for `scheduler`, `cron`, or `Task Scheduler` across the blueprint returns **no matches**. §19's module layout (lines 1894–1935) contains no scheduler and no prober; `core/capabilities/` is described as "capability contracts + registry + health" with no runner. Meanwhile `AGENTS.md` estate locks forbid `agent worker start` below 8 GB free RAM (G-26) and the decision log's G-1 states the portfolio "is **not** an always-on daemon fleet."

**Technical reason.** A 15-minute recurring probe and a `scheduled` execution mode are, by definition, a resident process. Either the blueprint is specifying a hidden daemon (violating the estate lock and its own G-1) or these two features are undeliverable. An engineer cannot resolve this without an architectural decision, and it changes whether the run store needs cross-process locking for the "single FIFO queue" (line 236) — which is likewise never specified as in-process or on-disk.

**Exact repair.** Choose and state one:
(a) Windows Task Scheduler is the sole scheduling mechanism; each trigger launches a one-shot CLI process that re-checks the RAM guard and the single-`cursor-agent` lock before admitting a run; health probes become **lazy** (probed on first use per process, cached with a TTL, never on a timer); or
(b) remove `scheduled` from the v1 `execution.modes` enum and delete `health_probe.interval_s`, replacing it with `health_probe.ttl_s` evaluated on demand.
Either way, specify the queue's persistence medium and its cross-process mutual-exclusion mechanism (named mutex / lock file with PID + staleness) in §19 `core/orchestrator/`.

---

## BLOCKER-10 — The RAM guard is self-contradictory, inconsistently scoped, and currently refuses every run on this machine

**Severity:** HIGH

**Evidence.** `SH-ARCH-9` (lines 242–244): "No **background worker** may start while free RAM < 8 GB. The RAM guard is a precondition check **at run admission** … A run refused on RAM grounds is `FAILED_TO_RUN`, reason `resource_guard`, and is **re-queueable**." But §4.1 (line 350) lists `FAILED_TO_RUN` as **terminal** ("Terminal: yes"), and `SH-STATE-3` (lines 385–386) forbids treating it as anything but a failure. §15.1's `RESOURCE` row (line 1554) repeats "run becomes `FAILED_TO_RUN`, re-queueable."

Scope is inconsistent: the estate lock binds only background workers, but Part 00's own example applies `free_ram_gb_min: 8` to an `interactive` clinical run (lines 538–539, with `modes: [interactive, owner-present-only]` at line 519), while WF-25 uses "`free_ram_gb_min` 8 if `browser.*` else 4" (line 5134). **Measured now: 2.49 GB free of 31.63 GB.**

**Technical reason.** A terminal state cannot be re-queued — resuming requires a non-terminal state or an explicit "new run inherits the idempotency key" rule, and neither exists. Separately, with the 8 GB threshold applied at admission to interactive runs, the blueprint's own `AGENTS.md`-recorded operating condition ("chronic memory pressure … free RAM has fallen to ~1.8 GB") means **zero of the 40 workflows are admissible today**, and the failure is terminal and non-retrying.

**Exact repair.** (1) Add a non-terminal state `DEFERRED_RESOURCE` to §4.1 with transitions `VALIDATING → DEFERRED_RESOURCE → QUEUED` and a bounded wait/backoff plus an owner-visible message; reserve `FAILED_TO_RUN`/`resource_guard` for the case where the wait budget expires. (2) Replace the single 8 GB number with a per-mode table in `SH-ARCH-9`: background/fan-out ≥ 8 GB (matching estate lock G-26 verbatim), browser-using ≥ 6 GB, interactive non-browser ≥ 2 GB, and re-evaluate before each fan-out batch as already stated. (3) Make Part 00's §5.4 example consistent with that table.

---

## BLOCKER-11 — The engine boundary is asserted but never specified, the complex engine has no named technology, and acpx's ownership contradicts the module layout

**Severity:** CRITICAL

**Evidence.**
- §1.2 (line 208): "Two executors exist behind **one interface**." `SH-REPO-1` (lines 1937–1938): "access is through **the engine interface** in `core/orchestrator/`." That interface is never defined anywhere — no method set, no inputs, no abort/cancellation contract, no checkpoint callback, no error surface. §0.1 (lines 93–94) claims "an engineer can build the described contract without asking a clarifying question about shape, naming, or failure semantics"; for the engine boundary that claim is false.
- §23 (line 2210) records G-12 as **Open**: "Workflow engine: acpx-only, graph layer, or isolated leaf?" The source decision log's actual G-12 (`AUTOMATION-SUITE-DECISIONS_2026-08-29.md` line 85) reads "acpx-only, **LangGraph** layer, or LangGraph as an isolated leaf?" — the blueprint silently drops the only named candidate technology, and the word `LangGraph` appears **zero** times in the blueprint. §23's own preamble (lines 2205–2206) says these items "**MUST NOT** be silently decided," yet §1.2 and P6 build on the "isolated optional leaf" answer.
- Ownership conflict: §1.1 line 173 places "Runtime: **acpx** over `cursor-agent acp` (G-3)" at L4 ORCHESTRATION, and G-3 assigns acpx "sessions, queues, flows, permissions, JSON events, **cancellation, and resumability**." But §19 puts the state machine, queue, budget breaker, checkpoints, and cancellation in `core/orchestrator/` (line 1912) and acpx only in `surfaces/acp/` (line 1929). Two components are specified as owning the queue, cancellation, and resume.
- Measured: `acpx` is **not on PATH**, and nothing in §20's P1 ("Orchestrator, state machine, run directory, ledger, checkpoints, cancellation, budget breaker, simple engine") installs or verifies it.

**Technical reason.** P6 delivers ~8 of 40 workflows (§1.2 line 217) plus the entire `limitless` preset and every re-research loop, on an engine with no named implementation, no dependency, and no interface. Duplicate ownership of cancellation/resume between acpx and `core/orchestrator` is the classic two-writers defect that `SH-LIFE-6` invariant 1 forbids at the code level. An engineer starting P1 cannot know whether to build a queue or configure one.

**Exact repair.** (1) Write §1.4 "Engine interface" with the concrete contract: `plan(definition, context) → NodePlan`, `step(context) → NodeResult`, `checkpoint() → Checkpoint`, `cancel(reason)`, `abort_reason` enum, and the guarantee that the engine may not touch the run store, ledger, approvals, queue, or breaker (already asserted by `SH-ARCH-6`, now made checkable). (2) Escalate G-12 to the owner as a blocking decision with the LangGraph option restored verbatim; record the answer before P1 starts. (3) Add one sentence to §1.1 and §19 stating unambiguously which of acpx or `core/orchestrator/` owns each of: session lifecycle, queue admission, permissions, cancellation, resume, JSON event emission — and delete the competing claim. (4) Add "acpx installed and `cursor-agent acp` handshake proven" to the P1 exit criteria.

---

## BLOCKER-12 — R2 clearance is unsatisfiable on a single-owner estate, which structurally blocks roughly half the catalog

**Severity:** HIGH

**Evidence.** §17.4 step 6 (lines 1756–1759): "R2 adds a **second independent human** with security/separation-of-duty responsibility (author cannot self-approve)." `SH-VER-2` (lines 1036–1038): "If only one human is available where two are required, the verdict is **`ESCALATE`**." §13.2 (lines 1428–1441) sets an R2 **minimum** for `medical_advice`, `personal_health_data`, `legal_advice`, `financial_advice`, `financial_personal_data`, `image_identity`, `browser_authenticated`, and `irreversible_local`. That covers WF-04, 06, 07, 17, 20, 21, 22, 23, 28, 35, 36, 37, 38, 39, 40 at minimum, plus every workflow that escalates at run time under `SH-RISK-1`. The blueprint records the gap only as a Part-04 line item (line 6990) and asserts at line 6982 that these "do not block completion of this design artifact."

**Technical reason.** True for the document; false for the implementation. Under the stated rules those runs terminate in `ESCALATED` (a terminal state, §4.1 line 348) and can never reach `COMPLETED`, so acceptance row A15 ("risk tier and required approvals correctly enforced") can only be satisfied by proving the workflow is unusable. Building P4 and P5 to deliver ~24 and ~34 cumulative workflows (lines 1955–1956) that cannot complete is wasted work unless the policy is settled first.

**Exact repair.** Obtain an explicit owner decision before P4 and encode it in §17.4: define a **single-owner R2 mode** — for example, deterministic gates plus a time-separated owner second pass performed in an explicitly different role against the final revision hash, recorded as `human_approvals.two_party_certification: not_achieved` with the compensating deterministic control set named per risk factor. Add the corresponding `approval` field to §5.2 and state which of the R2 workflows are cleared under it and which remain permanently `planned`. Do not relabel a model panel as human independence (`SH-VER-2` and the approval-gates document both forbid it, correctly).

---

## BLOCKER-13 — Duplicate prevention is **not** executable as specified (five independent mechanical failures)

**Severity:** CRITICAL — this is the item the task asked to confirm, and it does not hold.

`SH-DUP-7` (lines 675–677) states reconciliation is checked by the deterministic gate `reconciliation_survey` and rubric row A19, and `SH-TEST-9` (lines 1886–1888) insists A18/A19 are "**mechanical** — heading equality and field presence/enum membership … lints, not judgment calls." Five defects make that impossible:

**(a) The evidence anchor every workflow cites does not exist.** `SH-DUP-1` (lines 653–657) requires the matrix anchor in `evidence_paths[]`, and `SH-DUP-6`/§5.5.1 (line 638) require "at minimum the matrix anchor `…REUSE-MCP-MATRIX_2026-08-29.md#WF-NN`". Measured: the matrix contains **zero** HTML anchors or `{#id}` attributes — it is a markdown table with rows `| WF-01 | … |`. Any lint that resolves `#WF-NN` fails for all 40. *Repair:* either add `<a id="WF-NN"></a>` rows to the matrix (it is a companion artifact whose SHA-256 is pinned at line 6955, so re-pin it) or change the required evidence form to a machine-resolvable row reference such as `…REUSE-MCP-MATRIX_2026-08-29.md#row=WF-31` with a documented table-row parser.

**(b) `canonical_owner` grammar is violated in at least eight entries.** §5.5.1 (line 634) fixes the format as `skill:<path> | mcp:<server>[/<tool>] | script:<path> | workflow:WF-NN | none`. Violations: WF-31 line 5960 `canonical owner **internship-housing-finder**`; WF-35 line 6482 `canonical owner **health-review** (modes: …)`; WF-36 line 6593 `canonical owner **health-review** nutrition mode`; WF-37 line 6678 `canonical owner **health-review labs mode + pdf-reader/local extraction leaf**`; likewise WF-38/39/40. Their `existing_assets[]` are equally ungrammatical (WF-37: "`pdf-reader` (parked), `doc.extract_text`, **biomedical skills**" — a capability ID and a prose category, not asset references), and their `evidence_paths[]` are prose (WF-35: "REUSE-MCP-MATRIX **row** WF-35; RISK D9-health/D1/WF-35"), containing no path and no anchor. *Repair:* rewrite all Part-05 and WF-31 preambles into the §5.5.1 grammar.

**(c) `NEW` has three mutually exclusive definitions and the catalog uses all three.** §5.5.1 says `none` is "only valid with `action: NEW`"; §5.5.2 (line 649) says for `NEW` the `canonical_owner` is "the new workflow." In practice: WF-08 (line 3131) uses `none`; WF-21 (line 4519) uses `skill:.agents/skills/legal-workflow` — a skill that **does not exist** (verified) and that the workflow itself will create; WF-31 uses a bare name; WF-35 uses a bare name. Four `NEW` workflows, three conventions. *Repair:* pick one rule — recommended: `NEW` **must** set `canonical_owner` to the asset it creates, in grammar, plus a new boolean `canonical_owner_exists: false`; delete the `none` option or restrict it to `action: REUSE` of an unowned capability.

**(d) `SH-DUP-3` cannot be evaluated because reconciliation has no capability dimension.** Line 661: "Two workflows **MUST NOT** both name themselves `canonical_owner` **for the same capability**." The reconciliation block (§5.5.1) has six fields, none of which binds an owner to a capability ID. §21.3.2 item 12 restates the rule as a checklist item with no computable input. *Repair:* add a seventh required field `reconciliation.owned_capabilities[]` (capability IDs from §7.1) and specify the gate as: build the global map `capability → {workflows claiming ownership}` across all 40 definitions and fail on any key with cardinality > 1.

**(e) `MERGE_ALIAS` is applied where its precondition does not hold.** §5.5.2 (line 647) defines it as "Two or more **overlapping assets exist**; one becomes canonical and the others become aliases." WF-22 (line 4673) and WF-23 (line 4828) declare `MERGE_ALIAS` into `skill:.agents/skills/legal-workflow` "(created by `WF-21`)" — nothing exists to alias. WF-36/38/39/40 do the same into `health-review`. WF-09 (line 3220) aliases into `workflow:WF-08`, itself `NEW`. *Repair:* either add an action `EXTEND_PLANNED_OWNER` for "this workflow adds a mode to an owner another workflow creates," or require `MERGE_ALIAS.aliased_assets[]` to be non-empty and existing, and reclassify these six entries.

**Consequence.** The `reconciliation_survey` gate has no specified algorithm anywhere in the blueprint, and the five defects above mean that a faithful implementation of A19 fails on at least 8 of 40 entries for grammar, 40 of 40 for anchors, and cannot evaluate `SH-DUP-3` at all. The *intent* of the reconciliation block is sound and the matrix behind it is genuinely complete (verified: 40 rows, action census 14 COMPOSE + 4 NEW + …, evidence-backed owners) — but the mechanism is not executable as written.

**Additional repair.** Write §5.5.4 "The `reconciliation_survey` gate": parse each preamble → assert the §5.5.1 grammar → resolve every `evidence_paths[]` entry on disk → assert the matrix reference resolves to exactly one row whose `action` and `canonical_owner` **equal** the definition's (currently divergent: matrix row WF-08 names owner "one thin `seo-keyword-workflow` owner", the blueprint says `none`; matrix WF-09 names "`seo-keyword-workflow` ads mode", the blueprint says `workflow:WF-08`) → assert global capability-ownership uniqueness → emit a `ValidationResult` with a receipt.

---

# NON-BLOCKING IMPROVEMENTS

| # | Severity | Finding | Evidence | Repair |
|---|---|---|---|---|
| I-01 | MEDIUM | Systematic section cross-reference drift (most §-pointers into §6–§17 are one section low). §21.3.2 item 3 requires valid cross-references, so this fails the document's own conformance check | `outputs[]` "(§7.6)" → §6.6 (line 451); `exports` "(§15)" → §16.2 (452); `telemetry.metrics` "(§16.3)" → §17.3 (454); `memory.capture` "(§16.4)" → §17.5 (456); `inputs[]` "(§11.1)" → §10.1 (426); `sources.min_tier` "(§9.1)" → §8.1 (436); `cache.policy` "(§10)" → §9 (439); "Primitive … (§8.1)" → §7.1 (264); "`ReviewVerdict`, §7.9" → §6.9 (273); "version-suffix (§15.3)" → §16.2 (1440) | Renumber all internal references; add a link-integrity lint to the P0 exit criteria |
| I-02 | MEDIUM | Two competing workflow-ID vocabularies. The schema requires `^WF-(0[1-9]\|[1-3][0-9]\|40)$` but §2, §6.1, §14.3 and the §5.4 test paths use `ch.004` | Lines 257, 407, 700, 1500, 614–616 | Replace every `ch.004` with `WF-17` (and fix `fixtures/ch.004/…` → `fixtures/WF-17/…`) |
| I-03 | LOW | The canonical §5.4 example labels `id: WF-17` as `domain_family: clinical-health` with a drug-interaction summary, but WF-17 is "Memo draft (investment)" (finance-legal) per the navigation table and line 4044 | Lines 478–484 vs 32, 4044 | Renumber the example to a real clinical workflow (WF-04 or WF-35) or change its `domain_family` and summary |
| I-04 | MEDIUM | `G-N` identifier namespace collides with the `AGENTS.md` estate-lock IDs. The blueprint's G-12 is "workflow engine"; the estate lock G-12 is "Goose extensions HTTP-only". Both are cited as binding in the same document set | Blueprint lines 2210–2216 vs `AGENTS.md` estate-locks block | Prefix decision-log IDs (`DEC-G-12`) or estate locks (`LOCK-G-12`) throughout |
| I-05 | MEDIUM | `ToolInvocation` is specified as "Written to `invocations.jsonl` **before the call returns**" but the record contains `ended_at`, `duration_ms`, and `response.result_hash` | Line 734 vs 746–750 | Specify a two-phase write: an `invocation.started` line before the call, a completion line after, joined by `invocation_id`; state that the completion line must precede any downstream consumption |
| I-06 | MEDIUM | Cache-key contradictions. `SH-CACHE-7` says "Cache is keyed per-classification" but the §9.1 key formula has no classification term; `SH-CACHE-1` says the key excludes adapter/provider but §6.5 `key_parts` contains `adapter_family`; the formula hashes canonical strings while `key_parts` stores `query_hash`/`params_hash` | Lines 1208–1219, 1221–1223, 1253–1254, 854 | Add `classification` to both the formula and `key_parts`; delete `adapter_family` from `key_parts`; make `key_parts` the literal pre-image of the hash |
| I-07 | MEDIUM | Idempotency key defined twice with different field sets; auto-resume may hijack an intentional re-run | `SH-RUN-10` (1610–1611) includes cache.policy and jurisdiction/locale; the §5.4 `idempotency.key_fields` (594) omits both. `SH-RUN-9` (1605) auto-offers resume on key match | Make `idempotency.key_fields` derived from `SH-RUN-10` rather than hand-declared, or validate the declaration against it; add `--fresh` to bypass auto-resume |
| I-08 | MEDIUM | The roadmap gives no per-phase workflow list and no dependency graph for the owner-creation chains, so `SH-ROAD-2` ("no phase before the previous exit is disk-verified") has an unverifiable exit set | Lines 1949–1958 ("~6", "~14", "~24", "~34"); chains WF-21→22/23, WF-35→36–40, WF-08→09, WF-06→07 (WF-07 requires the WF-06 brief as a precondition artifact, line 2989), WF-25 profile→27/33 | Replace the approximate counts with an explicit enabled-workflow list per phase and add a workflow dependency DAG; reconcile with `SH-ROAD-3`'s breadth-first preference |
| I-09 | MEDIUM | `cv-studio` is the canonical owner for nine workflows with mixed REUSE/UPGRADE/COMPOSE actions and nine new "modes", with no consolidated change plan — a one-writer risk under `SH-LIFE-6` invariant 1 | Lines 5108, 5264, 5399, 5529, 5666, 5806, 6102, 6240, plus WF-34 | Add a per-canonical-owner change plan (combined delta, mode list, sequencing, single owning work-unit) for `cv-studio`, `imagegen`, `deep-research`, `legal-workflow`, and `health-review` |
| I-10 | MEDIUM | WF-35 names lifecycle phases `verify` and `review`, which are not among the ten in §3.1, and never declares `lifecycle.phases_used` | Line 6555 vs 290 | Rewrite as `spec-review`/`quality-review`/`acceptance` and add the `phases_used` line; lint all 40 entries for phase-name membership |
| I-11 | LOW | WF-35 classifies the boolean `cloud_phi_consent` as `SECRET`, and §11.1 forbids `SECRET` from ever appearing in the run dir or the ledger — but `SH-SAF-1` requires the owner's approval answer to be recorded | Lines 6503, 1308, 982–983 | Classify the consent flag `INTERNAL` (it is a decision record, not a credential) and keep only credential *values* as `SECRET` |
| I-12 | LOW | A3 gates acceptance on adapters being "healthy", while `SH-TEST-1` bars live network calls in CI and says L6 "never gates a merge on third-party availability" | Lines 1865, 1802–1803 | Restate A3 as "≥1 adapter passes the cassette contract suite, and an owner-run L6 receipt exists and is not older than N days" |
| I-13 | MEDIUM | §7.3 names nine rank-1/rank-2 providers with no presence in the estate MCP registry, without the "absent/deferred" labelling the reuse matrix applies consistently | `@nutrient`, `@openalex`, `@jina-reader`, `@fal`, `@cursor-generate-image`, `@native-websearch`, `@browser-serp`, `@browser-bridge`, `@office-com`, `@institutional` (lines 1129–1142) vs measured 40-server `agents.json` | Annotate each row with `active | parked | absent/deferred | direct-API | in-session-only`, matching the matrix's vocabulary; note explicitly that Cursor's image and web-search tools are in-session facilities with no verified programmatic contract |
| I-14 | MEDIUM | No environment prerequisite inventory. Rank-1 adapters for two deterministic capabilities are not installed (measured: `pandoc` and `magick` absent), and P2's exit criteria assume their contract suites can go green | Lines 1138–1140, 1953 | Add a P0/P1 "bootstrap inventory" deliverable: required local binaries with versions, install commands, and a `wf doctor` receipt |
| I-15 | LOW | §12.2 rule 7 lists estate localhost ports as reachable "only through their dedicated capabilities", but rule 2 already denies all loopback egress; the adapter carve-out is implicit | Lines 1369–1380 | State explicitly that adapters bypass the `web.fetch` SSRF pipeline for their own pinned host:port and are themselves allowlisted |

---

# NOT-CHECKED external dependencies

## Newly surfaced by this review (not present in the blueprint's own list)

1. **Provider API credentials for the ≥3-independent-voice floor.** `SH-INT-1` (line 1472) requires three genuinely independent voices in **every** multi-model step "even at `small`", and §17.4 step 3 requires a core panel from **different provider families**. The estate's own verified baseline (`AUTOMATION-SUITE-DECISIONS_2026-08-29.md` lines 21–22) records **all four provider probes failing: OpenRouter 402, Anthropic 401, OpenAI 401, Gemini 404**. No phase in §20 contains a credential-preflight gate, and no workflow declares a `precondition` on provider auth. If serialized local Cursor turns are the intended substitute (`SH-ARCH-8`), the wall-clock budgets (e.g. WF-25 medium: 1,800 s for 3 lanes; §5.4: 2,700 s) are unvalidated. **Status: NOT-CHECKED — must be resolved before P4, since the entire approval panel depends on it.**
2. **`acpx` existence, version, and maturity.** Not on PATH (measured). No install target, version pin, or upstream reference anywhere in the blueprint.
3. **`cursor-agent acp` subcommand availability in build `2026.08.28-e7f6d3b`.** Not executed during this read-only review.
4. **Google Ads API / Search Console API access** for WF-08/WF-09 (matrix: "absent/deferred"; no account, no consent flow proven).
5. **SEC EDGAR, market-series, and delayed-quote access** for WF-17 (`data.company_filings`, `data.market_series`, `data.market_quotes` are named capabilities with no adapter).
6. **Cursor `GenerateImage` and native web search as programmatic adapters.** Both are listed as rank-1 providers (lines 1131, 1137). Both are in-session agent tools; no public programmatic contract, rate limit, or cost model was verified.
7. **fal.ai account/credentials** for the rank-2 `image.generate` path.

## Carried forward from the blueprint (lines 6982–6993), re-confirmed as still open

8. Part 03 — live health of `data.pubmed`, `data.clinical_trials`, `data.drug_labels`, `data.company_filings`, `data.market_series`, `data.market_quotes`, `data.legal_instruments`, `data.case_law`; parked `pdf-reader` MCP; `DISC-DOC-1` registration; design-only on-demand router.
9. Part 04 — `safety/disclaimers.yaml` absent (confirmed: `.agents\safety\` does not exist).
10. Part 04 — LinkedIn / Indeed / Handshake official APIs and MCP adapters absent/deferred (confirmed: not in the 40-server registry).
11. Part 04 — recovered LinkedIn MCP: source present at `…\agent-skills-toolchain\tools\mcp\linkedin-mcp` (confirmed on disk) but registration, auth, stdio integration, and live API remain unproven; it cannot search alumni.
12. Part 04 — `data.occupations`, `data.labor_statistics`, `data.job_postings` are not live registry servers.
13. Part 04 — cv-studio virtual-environment presence on a run host is an unproven precondition (relevant to BLOCKER-01).
14. Part 04 — two-party R2 human independence unavailable in a single-owner household (escalated here to **BLOCKER-12** because it terminally blocks ~15+ workflows, not merely a dependency).
15. Part 05 — live MCP health for parked `pdf-reader`, maps/transit adapters, `data.property_listings`, on-demand-router shadow mode.

**Additionally undefined, not merely unchecked:** the MCP **active/parked lifecycle** itself. The catalog references a parked `pdf-reader` that "may be activated only by approved routing" (line 3852) and "on-demand if owner approves activation" (line 6711), and an "on-demand router" appears only as a NOT-CHECKED item. There is no capability, no state machine, no adapter, and no specification for how a parked MCP server is activated **mid-run** — which in practice requires reconfiguring and restarting the MCP host, something a running workflow cannot do to itself. *Repair:* either specify activation as a pre-run precondition with an owner prompt during `PREVIEW` (recommended), or remove parked-MCP activation from the catalog and treat parked servers as unavailable capabilities that degrade visibly per `SH-TOOL-3`.

---

# What is NOT wrong (checked and cleared)

To keep the finding list honest, these were specifically probed and found sound:

- **Eight-subsection template conformance (A18 / `SH-TMPL-7`)** — exact, across all 40 entries.
- **Workflow identity set** — `WF-01`…`WF-40` once each, numerically ordered, `source_ref` grammar correct in all 40.
- **`ReviewVerdict` fidelity** — the approval-gates schema is preserved verbatim with additive fields only.
- **Reuse-matrix completeness** — 40 rows, action census sums to 40, every row carries an evidence-backed owner and a falsifiable delta. `SH-DUP-2`'s sequencing prerequisite is genuinely satisfied; the defects in BLOCKER-13 are in the citation mechanism and the grammar, not in the survey itself.
- **Canonical-owner grounding** — 23 of the named owner skills exist on disk; the four that do not (`legal-workflow`, `health-review`, `seo-keyword-workflow`, `internship-housing-finder`) are exactly the four `NEW` actions, which is internally consistent.
- **No circular dependency** was found among the workflow chains (WF-21→22/23, WF-35→36–40, WF-08→09, WF-06→07 are strictly ordered), though the ordering is unrecorded (I-08).
- **Estate-lock alignment** — never-rotate (`SH-SEC-CRED-2`), the mandatory 3-way browser profile choice (`BR-1`), no-silent-downgrade, basic-memory as sole semantic writer, background runs never commit, and one-local-`cursor-agent` are all correctly imported and not contradicted.
- **No invented external research claim** — the approval-gates and source-risk citations resolve to the companion documents as stated, and the SHA-256 companion table (lines 6952–6964) points at files that exist with the sizes expected.

---

# Summary of the gate decision

**FAIL.** Thirteen implementation-blocking defects. The three that would waste the most engineering time if unaddressed are: **BLOCKER-11** (the engine boundary and acpx ownership are undefined, so P1 cannot start with confidence), **BLOCKER-01** (the most common reconciliation action has no execution mechanism), and **BLOCKER-13** (the duplicate-prevention gate — the blueprint's headline safeguard against re-implementing the estate — cannot execute against the artifact it cites). **BLOCKER-06/07** must be settled before any schema is written, and **BLOCKER-08/12** must be settled before the acceptance rubric is trusted, because as written they make `implemented` unreachable.

The blueprint is unusually disciplined in its fail-closed vocabulary, its template mechanics, and its reuse survey. The defects above are boundary, vocabulary, and executability gaps — all repairable without redesigning the seven-layer architecture.

*Review produced read-only on 29.08.2026. No file other than this one was created or modified.*
