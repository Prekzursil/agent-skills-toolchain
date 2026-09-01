# Plan Review Gate: Scope & Alignment Review
## Perplexity Computer Workflows — 40-Workflow Implementation Blueprint

- **Review Target:** `C:\Users\Prekzursil\.agents\PERPLEXITY-COMPUTER-WORKFLOWS-BLUEPRINT_2026-08-29.md`
- **Reviewer:** Product Manager Agent (Adversarial Scope & Alignment Reviewer)
- **Date:** 29.08.2026
- **Status:** COMPLETED
- **Verdict:** `PASS`
- **Cross-Checked Normative Baselines:**
  - `C:\Users\Prekzursil\.agents\AUTOMATION-SUITE-DECISIONS_2026-08-29.md` (G-1 through G-21, verified estate constraints)
  - `C:\Users\Prekzursil\.agents\PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md` (Mandatory 40-workflow census and 40-record MCP topology)
  - `C:\Users\Prekzursil\.agents\PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md` (Source authority, TTLs, privacy, safety, and risk tiers R0–R3)
  - `C:\Users\Prekzursil\.agents\PERPLEXITY-WORKFLOWS-SOURCE-CROSSCHECK_2026-08-29.md` (Visual ground-truth alignment and category mapping)
  - `C:\Users\Prekzursil\CLAUDE.md` & `C:\Users\Prekzursil\AGENTS.md` (Standing estate locks: single cursor-agent, 8GB RAM floor, Basic Memory SSOT, no credential rotation, no silent feature downgrade, fail-closed verification)

---

## 1. Executive Summary & Gate Verdict

### **Verdict: `PASS`**

The `PERPLEXITY-COMPUTER-WORKFLOWS-BLUEPRINT_2026-08-29.md` artifact is an exhaustive, mathematically rigorous, and architecturally aligned implementation plan. It fully realizes the owner's strategic intent: unifying 40 Perplexity-style computer workflows into a single, multi-model, tool-aware Cursor/CLI catalog without duplicating existing capabilities, without degrading estate features, and without breaching safety, privacy, or memory contracts.

### Key Gate Findings:
1. **Scope Integrity:** All 40 workflows (`WF-01` through `WF-40`) are specified in numerical order with zero omissions, zero extraneous additions, and zero identity drift from the authoritative specification.
2. **Action Census Reconciliation:** The blueprint adheres 100% to the census defined in `PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md`: **7 REUSE + 6 UPGRADE + 14 COMPOSE + 9 MERGE/ALIAS + 0 RECOVER + 4 NEW = 40**.
3. **Estate Locks & Safety Invariants:** Enforces mandatory per-run 3-way browser profile selection (default `b`, never silent `a`, no attachment to 1Password Chrome), fail-closed verification (`disk-verified` vs `agent-claimed`), no credential rotation, no silent model/capability downgrades, and strict draft-only boundaries for high-stakes external actions.
4. **Topology Precision:** Reconciles the 40-record MCP fleet (6 Cursor-active, 1 plugin-managed, 31 parked-preserved, 2 disabled/denied) and accurately bounds the recovered historical LinkedIn MCP source (82 offline tests passing) to owner-identity/own-feed posting, preventing invalid claims of alumni discovery.
5. **Defect Counts:** **0 Blocking Deficiencies**, **3 Actionable Enhancements / Implementation Advisories**.

---

## 2. Comprehensive Scope & Alignment Evaluation

### 2.1 Catalog Completeness & Identity Alignment
- **Requirement:** Integrate all 40 Perplexity-style computer workflows into one unified registry without dropping items or altering user intent.
- **Evaluation:** `PASS`.
- **Evidence:**
  - All 40 workflows (`WF-01` to `WF-40`) are enumerated with stable kebab-case IDs, verbatim descriptions, and verified category cross-listings matching `PERPLEXITY-WORKFLOWS-SOURCE-CROSSCHECK_2026-08-29.md`.
  - Disambiguating domain parentheticals for five workflows (WF-04 Clinical, WF-06 Medical, WF-09 Google Ads, WF-17 Investment, WF-20 Document QA) are correctly preserved in metadata to prevent collision with generic commands.
  - The 5 drafting batches (Parts 01–05, 8 workflows each) sum exactly to 40, maintaining clean domain-family boundaries.

### 2.2 Action Census & Anti-Duplication Discipline
- **Requirement:** Strict compliance with the 40-row census from `PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md`. No duplicate skills, redundant schemas, or rogue state stores.
- **Evaluation:** `PASS`.
- **Evidence:**
  - **7 REUSE:** WF-01 (`prompt-optimizer`), WF-02 (`imagegen`), WF-05 (`ui-audit`), WF-13 (`imagegen`), WF-18 (`slides`), WF-27 (`cv-studio`), WF-33 (`cv-studio`).
  - **6 UPGRADE:** WF-04 (`deep-research`), WF-16 (`nutrient-document-processing`), WF-25 (`cv-studio`), WF-26 (`cv-studio`), WF-30 (`cv-studio`), WF-34 (`cv-studio`).
  - **14 COMPOSE:** WF-06 (`deep-research` + `evidence-ledger-synthesis`), WF-07 (WF-06 + `council`), WF-10 (`deep-research` + `ui-audit`), WF-11 (`design-studio direct`), WF-12 (`design-studio audit`), WF-14 (post creator draft recipe), WF-15 (format-aware doc summary), WF-17 (`deep-research` investment memo), WF-19 (`prototype` + `design-studio`), WF-20 (format-aware final pass), WF-28 (`cv-studio` + `imagegen`), WF-29 (`cv-studio` + `grant-proposal-architecture`), WF-32 (`cv-studio` + `deep-research` + browser), WF-37 (`health-review` + `pdf-reader`).
  - **9 MERGE/ALIAS:** WF-03 (`humanizer`), WF-09 (`seo-keyword-workflow`), WF-22 (`legal-workflow`), WF-23 (`legal-workflow`), WF-24 (`imagegen`), WF-36 (`health-review`), WF-38 (`health-review`), WF-39 (`health-review`), WF-40 (`health-review`).
  - **0 RECOVER:** Zero premature recovery claims.
  - **4 NEW:** WF-08 (`seo-keyword-workflow`), WF-21 (`legal-workflow`), WF-31 (`internship-housing-finder`), WF-35 (`health-review`).

### 2.3 Justification Analysis of the 4 NEW Owners
- **Requirement:** Ensure new skill/workflow owners are created only where genuine capability gaps exist and no canonical owner can be upgraded/composed.
- **Evaluation:** `PASS`.
- **Evidence:**
  1. `seo-keyword-workflow` (WF-08): Thorough index search confirmed no dedicated SEO keyword owner with geo/language/date/match-type schemas or official GSC/Google Ads API boundaries exists. WF-09 merges directly into this owner.
  2. `legal-workflow` (WF-21): Verified absence of any jurisdiction-aware legal owner. Existing research skills lack mandatory jurisdiction ASK-gates, CELEX/ECLI/gazette pin cites, and in-force TTL validation. WF-22 (draft) and WF-23 (review) merge directly into this owner.
  3. `internship-housing-finder` (WF-31): Confirmed absence of housing domain owners. Implements short 6h listing TTLs, university-first sources, transit GTFS versioning, scam/fraud detection, and location P3 protection.
  4. `health-review` (WF-35): Existing biomedical skills focus on academic literature triage, not personal health records/intake. Creates a unified, local-only P4 intake owner with strict no-diagnosis boundaries. WF-36 (nutrition), WF-37 (labs), WF-38 (visit prep), WF-39 (fitness), and WF-40 (sleep) all consolidate into this single owner, avoiding 6 fragmented health skills.

### 2.4 Existing Capability Preservation & Anti-Downgrade
- **Requirement:** Guarantee existing skills, scripts, and formats are preserved without functional degradation.
- **Evaluation:** `PASS`.
- **Evidence:**
  - **Career & Identity SSOT:** `cv-studio` remains the single canonical owner for all career capabilities (`profile.yaml`, `x_master`, `x_metrics`). RenderCV is preserved as the ATS-compliant selectable-text standard; `design-studio`/Figma is preserved for visual portfolios.
  - **Lexical Separation:** `source-command-resume-session` is explicitly isolated from CV/resume editing (`SH-DOC-3`, WF-33 gates).
  - **Document Conversion:** `nutrient-document-processing` is upgraded as a local-first conversion dispatcher while preserving cloud capabilities and respecting the disabled state of `markitdown`.
  - **Semantic Memory:** `basic-memory` (`127.0.0.1:8765`) remains the sole semantic memory writer; raw PHI/P4 data is explicitly excluded from memory.

### 2.5 Multi-Model Breadth, Routing & Intensity Presets (G-7, G-8, G-10)
- **Requirement:** Enforce multi-model independence, adaptive execution intensity, pre-run distribution previews, and concrete model pinning.
- **Evidence:**
  - **Floor & Independence (G-7, `SH-INT-1`):** Every multi-model step requires a floor of ≥3 genuinely independent voices (tracked by `independence_group`, not model name).
  - **Intensity Presets (G-8, §14.1):** Defines `small`, `medium`, `high`, and `limitless` as situation-dependent throttles on breadth/corroboration.
  - **Distribution Preview (`SH-INT-5`):** Mandates pre-run display of resolved concrete model/provider IDs, voice roles, cost estimates, and degraded capability disclosures.
  - **No Silent Downgrade (`SH-INT-6`, `SH-INT-10`):** Prohibits silent model-family or capability downgrades; fallbacks must be visible and logged.

### 2.6 Dual-Engine Architecture & Engine Boundary (G-10, G-12)
- **Requirement:** Support simple linear pipelines and complex adaptive DAGs without altering the artifact or ledger contracts.
- **Evidence:**
  - **Engine Boundary (`SH-ARCH-4`):** Simple executor (`graph.engine: simple`, ~32 workflows) and complex graph engine (`graph.engine: complex`, ~8 workflows) consume identical `WorkflowDefinition` schemas and emit identical `RunContext` and `ArtifactManifest` artifacts.
  - **Fail-Closed Engine Availability (`SH-ARCH-5`):** If the complex graph engine is absent at deploy time, complex workflows fail closed (`FAILED_TO_RUN`, `engine_unavailable`) rather than silently degrading to linear execution.
  - **Isolation (`SH-ARCH-6`):** The graph engine is an isolated leaf dependency; orchestration, queues, budget breakers, and approval gates remain in Layer 4.

### 2.7 Tool Routing, Recoverability & MCP Topology
- **Requirement:** Accurately reflect active vs. parked MCP servers, provide non-destructive routing, and prevent credential exposure.
- **Evidence:**
  - **40-Record Partition (§7, §22):** Exactly matches the canonical registry: 6 Cursor-active (`agent-mail`, `basic-memory`, `chrome-devtools`, `context7`, `firecrawl`, `playwright`), 1 plugin-managed (`tavily`), 31 parked-preserved, 2 disabled/denied (`markitdown`, `meta-tool`).
  - **Historical LinkedIn MCP (§7.3, §23):** Reconciled as `RECOVERABLE/HEALTHY-SOURCE` with 82 passing unit tests; runtime registration and live API operation remain accurately marked `NOT-CHECKED`. Scope is strictly limited to owner OIDC identity and own-feed posting/deleting, not alumni discovery.
  - **Non-Destructive Router Contract (§7.2, `SH-TOOL-1..6`):** Shadow-first mode, run-scoped lifecycle, zero mutation of canonical files, environment variable names only (never values), and strict prohibition of credential rotation.

### 2.8 Control Plane, Command Naming & Terminal UI Direction (G-1, G-3, G-4, G-9)
- **Requirement:** Integrate with Cursor CLI/ACP, prevent command collisions, use Fabric strictly as a prompt engine, and align with the terminal strategy.
- **Evidence:**
  - **Command Namespace (G-4):** Grok is `grok`, Cursor CLI is `cursor-agent`, bridges use `cursor-grok`/`cursor-claude`/`cursor-codex`. No component claims the generic `agent` command.
  - **Headless Runtime & TUI (G-3):** Layer 4 orchestrator uses `acpx` over `cursor-agent acp`; Layer 6 supports Neovim with Avante Zen Mode as the interactive ACP TUI.
  - **Fabric Role (G-9):** Fabric is strictly a prompt pattern and strategy library under `prompts/` (`prompt_ref`). It is not an orchestrator.

### 2.9 Evidence-First Approval & Risk Governance (G-11, R0–R3)
- **Requirement:** Implement evidence-based approvals where deterministic receipts outrank opinion, LLM judges remain advisory, and high-stakes actions require human gates.
- **Evidence:**
  - **Deterministic Priority (§17.4, `SH-APR-1`):** Deterministic gates run first; any failed, missing, stale, or budget-aborted check blocks the run.
  - **Advisory LLM Judges (`SH-APR-2`):** LLM reviewers cannot approve or block on opinion alone; blocking findings require independent execution-to-confirm with a disk-verified receipt.
  - **No Outvoting Blockers (`SH-APR-3`):** One reproduced deterministic blocker cannot be overridden by panel majority.
  - **Risk Tiers (§13, `SH-RISK-1..4`):**
    - `R0`: Reversible local research/drafts (can auto-clear if receipts pass).
    - `R1`: Outward-looking drafts (owner inspects final artifact).
    - `R2`: Sensitive health/legal/finance/identity data (owner-present, required disclaimers).
    - `R3`: Irreversible external actions (send, post, apply, pay, e-sign, deploy) require explicit, separate owner action.

### 2.10 Safety Boundaries & External Action Safeguards
- **Requirement:** Prevent unauthorized external side-effects, clinical diagnosis, legal practice, financial trading, or privacy breaches.
- **Evidence:**
  - **External Actions Boundary:** Every external interaction (`browser.act`, posting, emailing, applying, paying, e-signing) requires an explicit `SafetyDecision` of `ALLOW` and owner presence (`SH-TOOL-5`, `SH-SEC-BROWSER`).
  - **Medical & Clinical Safeguards:** Workflows WF-04, WF-06, WF-07, and WF-35–40 include mandatory disclaimers (`DISC-MED-1`, `DISC-NOT-A-CLINICIAN`), strict no-diagnosis/no-prescription boundaries, and local-only P4 handling.
  - **Legal Safeguards:** Workflows WF-21–23 enforce jurisdiction ASK-gates, pin cites, in-force checks, no-e-sign gates, and legal disclaimers.
  - **Financial Safeguards:** WF-17 mandates SEC EDGAR CIK/accession grounding, delayed-quote labeling, and trading prohibitions.
  - **Browser Profile Isolation:** Mandatory 3-way profile prompt on every run; defaults to agent-persistent `(b)`; prohibits silent live-profile `(a)` selection; strictly prohibits CDP attachment to the 1Password Chrome profile.

---

## 3. Findings Matrix: Blockers & Enhancements

| ID | Severity | Category | Target / Reference | Description & Evidence | Violated Rule | Exact Repair / Implementation Guidance |
|---|---|---|---|---|---|---|
| **F-01** | `ENHANCEMENT` | Safety / Schema | Blueprint §11 / §23 | `safety/disclaimers.yaml` is referenced across Parts 03–05 but is currently absent on disk (`NOT-CHECKED` dependency). | `SH-DISC-1` | During Phase P0/P4 implementation, instantiate `safety/disclaimers.yaml` containing the canonical texts for `DISC-MED-1`, `DISC-LEGAL-1`, `DISC-FIN-1`, `DISC-CAREER-1`, `DISC-IMAGE-SYNTHETIC-1`, and `DISC-NOT-A-CLINICIAN`. |
| **F-02** | `ENHANCEMENT` | Budget Governance | Blueprint §5 / §23 (G-19) | Per-run hard budget caps (`max_cost_units`, `max_wall_clock_s`, `max_invocations`) are fully defined, but the global daily spend cap remains listed as an open estate item. | G-19 | In Phase P4 (Safety & Approval), incorporate a global daily cost accumulator in the Layer 0 substrate that trips an estate-wide circuit breaker if aggregate daily spend exceeds the owner's limit. |
| **F-03** | `ENHANCEMENT` | Verification / Schema | Blueprint §6.3 / §10 | Checksum verification for canonical IDs (PMIDs, NCT numbers, SEC accessions, CELEX numbers) is specified as an advisory regex in input validation. | Source-Risk §9.5 | In Phase P0/P2, implement deterministic checksum/luhn-style validators in the capability adapter layer so malformed or hallucinated identifiers fail closed immediately. |

*Note: None of the above findings are blocking defects for this blueprint design artifact. They are standard implementation-phase prerequisites already cataloged in the blueprint's aggregated `NOT-CHECKED` dependencies section.*

---

## 4. Scope Creep, Accidental Removal & Over-Consolidation Audit

1. **Scope Creep Detection:**
   - **Audit Result:** `CLEAN`.
   - **Verification:** No unnecessary autonomous daemons, background fleet monitors, unrequested social-media automations, or automated financial trading capabilities were introduced. All workflows operate on-demand or through an explicit serial queue.

2. **Accidental Removal Detection:**
   - **Audit Result:** `CLEAN`.
   - **Verification:** Every one of the 40 authoritative workflows from the source cross-check is present and accounted for. All existing estate tools (`cv-studio`, `slides`, `ui-audit`, `imagegen`, `deep-research`, `nutrient-document-processing`, `basic-memory`, `council`) maintain their full feature set.

3. **Over-Consolidation Risk:**
   - **Audit Result:** `CLEAN`.
   - **Verification:** Consolidation into the 4 NEW owners (`legal-workflow`, `health-review`, `seo-keyword-workflow`, `internship-housing-finder`) preserves distinct mode contracts, specialized input/output schemas, and dedicated gates for each sub-domain (e.g., nutrition vs. lab interpretation vs. sleep coaching), ensuring no loss of domain fidelity or specialized UX.

---

## 5. Metrics & Defect Summary

- **Total Workflows Reviewed:** 40 / 40
- **Action Census Verification:**
  - REUSE: 7
  - UPGRADE: 6
  - COMPOSE: 14
  - MERGE/ALIAS: 9
  - RECOVER: 0
  - NEW: 4
  - **Sum:** 40 (100% matched)
- **MCP Inventory Verification:** 40 canonical records (6 active, 1 plugin, 31 parked, 2 denied; 100% matched)
- **Blocking Deficiencies:** 0
- **Non-Blocking Enhancements:** 3
- **Final Gate Recommendation:** Approved to proceed to Work-Unit Decomposition and Phased Implementation.

---

## 6. Gate Sign-Off

```json
{
  "gate": "PLAN_REVIEW_GATE_SCOPE_AND_ALIGNMENT",
  "target_artifact": "C:\\Users\\Prekzursil\\.agents\\PERPLEXITY-COMPUTER-WORKFLOWS-BLUEPRINT_2026-08-29.md",
  "reviewer_role": "product-manager-agent",
  "verdict": "PASS",
  "census_validation": {
    "expected_workflows": 40,
    "evaluated_workflows": 40,
    "discrepancies": 0
  },
  "estate_lock_compliance": {
    "single_cursor_agent": "ENFORCED",
    "eight_gb_ram_guard": "ENFORCED",
    "basic_memory_ssot": "ENFORCED",
    "no_credential_rotation": "ENFORCED",
    "no_silent_downgrade": "ENFORCED",
    "fail_closed_verification": "ENFORCED",
    "browser_three_profile_choice": "ENFORCED"
  },
  "blockers_count": 0,
  "enhancements_count": 3
}
```
