# Perplexity-Class Workflow Suite — Part 02: Marketing and Web

Date: 29.08.2026  
Status: NORMATIVE design specification only — no implementation, deployment, or commits  
Scope: WF-05, WF-08, WF-09, WF-10, WF-11, WF-12, WF-18, WF-19. Shared contracts are inherited by ID from Part 00.

### WF-05 — Website audit

**Source ref:** `user-spec:WF-05` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 2 · **Domain family:** marketing-seo-product  
**Risk tier:** R1 (factors: public_web_content, owner_property_context) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `REUSE` · canonical owner `skill:.agents/skills/ui-audit/SKILL.md` · existing assets `skill:.agents/skills/ui-audit/SKILL.md`, `skill:.agents/skills/design-studio/SKILL.md`, `mcp:playwright`, `mcp:chrome-devtools`, `mcp:firecrawl` · duplicate surfaces avoided `new website-audit skill`, `second browser crawler`, `duplicate deterministic UI gates` · delta `Adds only a catalog route that records owner-site scope and browser-profile selection before the existing audit is invoked.` · evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-05`, `.agents/skills/ui-audit/SKILL.md`, `.agents/skills/design-studio/SKILL.md`

#### 1. Purpose and user story
- Audit a supplied marketing URL against its stated target, named competitors, and selected marketing benchmarks; produce a ranked, evidence-linked improvement backlog rather than make changes.
- User story: “As a marketer, I want a snapshot-based audit of my website so that I can prioritize the changes most likely to clarify value and improve conversion.”
- Boundary: no penetration test, CMS mutation, or campaign build; keyword-market planning belongs to WF-08 and implementation/deployment planning to WF-19.
- Routing: `audit my website`, `review this landing page`, `website conversion audit`, `check my CTA`, `marketing site review`; negative triggers: `find SEO keywords` → WF-08, `build a website` → WF-19, `optimize a product listing` → WF-12. Alias: `/website-audit`.
- Modes: interactive and background for public URLs; owner-present-only when authenticated staging/production requires a session. Success means every priority names page evidence, expected user effect, effort, and confidence.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| url | url | yes | https; SSRF validation | PUBLIC | — |
| target_audience | string | no | ≤500 chars | INTERNAL | `unspecified` |
| conversion_goal | enum | yes | lead, demo, sale, signup, awareness | INTERNAL | — |
| competitors | list<url> | no | 0–5 public URLs | PUBLIC | `[]` |
| benchmark_set | enum | no | saas, ecommerce, services, custom | INTERNAL | `custom` |
| browser_profile | enum | yes | a, b, c; record choice | INTERNAL | `b` |

- Preconditions: `web.fetch` healthy; `browser.session` healthy for rendered evidence; free-RAM guard for background work; authenticated pages require an owner-present profile decision under `SH-SEC-BROWSER`.
- Intensity profile — numbers only:
| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 3 | 0 | 0 | 1 | 0 |
| medium | 0 | 8 | 0 | 0 | 2 | 0 |
| high | 0 | 16 | 0 | 0 | 2 | 0 |
| limitless | 0 | 30 | 0 | 0 | 2 | 0 |
- Budget: `80 / 1200 / 12`. Deviations from shared input/intensity defaults: None.

#### 3. Data sources and knowledge bases
- Primary evidence is the audited live URL and its reachable key pages; competitors and benchmark pages are dated observational comparators. Capture canonical URL, HTTP status, viewport, content hash, retrieval time, and screenshot ID.
- `sources.min_tier: T2`; `min_independent: 2` for comparative claims; `recency_max_days: 1`. The owner URL is authoritative only for what it served at retrieval; competitor pages are T3 and labeled vendor-interested under `SH-SRC-6`.
- Capabilities: `web.fetch` obtains public HTML and policy pages; `browser.session` renders responsive layout and screenshots; `web.search` is not required.
- `memory.capture: decisions`; persist only owner-approved reusable audit decisions, never page copies. `cache.policy: standard`; owner/competitor pages are `medium`, while price/offer claims are `fast` and rechecked before rendering.
- No paywall path. Deviations from the §8.2 domain floor: tighter 24-hour current-page window, because findings describe current UI.

#### 4. Tool chain and mechanisms
- Required capabilities: `web.fetch`, `browser.session`, `llm.extract`, `llm.summarize`. Optional `web.search` supplies named public benchmark references; without it the report says “Benchmark discovery unavailable; audit uses supplied comparators only.”
- Provider hints may prefer rendered browser evidence after static fetch. Do not use a browser to evade robots, login walls, or rate limits; do not use active-test/security capabilities.
- Fetch robots and the entry page, derive a capped same-host path set (home, primary conversion page, pricing, product/service, about/contact), then collect desktop/mobile screenshots. Analyze copy clarity, proposition, CTA hierarchy, IA, title/meta/heading basics, visible performance/accessibility signals, and comparator patterns. All page content remains untrusted per `SH-SEC-INJ`; browser profile and egress controls are `SH-SEC-BROWSER` and `SH-SEC-SSRF`.
- Route into `ui-audit`; this recipe contributes sequencing and evidence presentation only.

#### 5. Internal data structures / schemas
- Defines `AuditFinding`: `finding_id`, `category`, `page_url`, `evidence_refs`, `observation`, `recommendation`, `impact`, `effort`, `confidence`, `priority_score`, `priority_reason`, `status`.
- Defines `ScreenshotManifestEntry`: `screenshot_id`, `url`, `viewport`, `captured_at`, `content_hash`, `artifact_path`, `pii_class`.
- Consumes unchanged `RunContext`, `SourceRecord`, `Citation`, `ArtifactManifest`, `ValidationResult`, and `SafetyDecision`.
- Declared artifacts: `website_audit` (markdown, required) → analysis and citations; `screenshots_manifest` (JSON, required) → capture references; `findings_export` (CSV, required) → sortable backlog.
```json
{"finding_id":"wf05-cta-01","category":"cta","page_url":"https://example.com/pricing","evidence_refs":["shot-03","src-07"],"observation":"Two equal-weight primary CTAs compete above the fold.","recommendation":"Make the trial CTA primary and retain demo as secondary.","impact":4,"effort":2,"confidence":4,"priority_score":32,"priority_reason":"4×2×4; conversion-page evidence","status":"proposed"}
```

#### 6. Step-by-step execution flow
- Engine: simple. Phases: `validate`, `discover`, `plan`, `execute`, `quality-review`, `acceptance`, `capture`.
1. `validate_request` (validate, gate) → validates URL/profile/scope → validation receipt.
2. `fetch_rules` (discover, tool, `web.fetch`) → reads robots and entry metadata → source records.
3. `map_pages` (plan, llm) → selects capped key paths and comparator pages → page plan artifact.
4. `render_pages` (execute, tool, `browser.session`) → captures declared viewports → screenshot manifest checkpoint.
5. `extract_signals` (execute, llm) → produces evidence-bound findings → findings schema.
6. `score_findings` (quality-review, llm) → calculates visible `impact × confidence × (6 − effort)` priority → ranked backlog.
7. `verify_audit` (acceptance, gate) → validates citations, manifests, and reconciliation → verdict.
- Missing optional benchmarks do not block the supplied-site audit. Approval: deterministic gates only; `human_required: 0`, `panel_required: false`; production changes remain outside this workflow. Resume reuses hash-valid fetches/screenshots within TTL and reruns expired pages per `SH-RUN-7` and `SH-RUN-11`.

#### 7. Output format and UX behavior
- The owner sees executive summary; target/goal assumptions; page-by-page findings; screenshot references; competitor/benchmark observations; a prioritized recommendation table; quick wins; uncertainty; and bracketed citations such as `[1] [Pricing](https://example.com/pricing) — Example, accessed 29.08.2026 (T0)`.
- Export `md`, `csv`, `json` to `active_project_docs`, named `website-audit_{YYYY-MM-DD}`, language `en`. The preview states URL scope, selected profile, pages, comparators, metrics, and budget.
- Progress reports page counts and screenshot completion; no live-profile screenshot is exported without its classification handling under `SH-SEC-BROWSER`.
- Missing optional benchmark capability: “Benchmark comparison unavailable; findings and scores cover the supplied pages only.” Deviations from §16 output/export defaults: None.

#### 8. Logging, validation, and safety
- Applies `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, `SH-SEC-REDACT`, and `SH-SEC-CRED`; owner-site scope and robots outcome are recorded.
- Required disclaimers: `DISC-WEB-1` under `SH-RISK-3`. Effective R1; data classes PUBLIC and, for any authenticated capture, PII.
- Required deterministic gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, screenshot-manifest completeness, robots/scope check, and `AuditFinding` schema validation.
| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| robots disallows crawl | POLICY | restrict to permitted pages | “Crawl restricted by site rules; only permitted evidence was used.” |
| browser unavailable | CAPABILITY_UNAVAILABLE | static-only audit; mark visual checks absent | “Rendered layout checks are unavailable; this is a static-content audit.” |
| page changed or TTL expired | STALE | re-fetch or omit current claim | “Page evidence changed or expired; affected finding was revalidated or withheld.” |
| injection signal | SAFETY | quarantine source | “A page contained suspicious instructions; it was excluded from analysis.” |
- Ledger adds page count, rendered/static split, robots decision, screenshot hashes, finding-score distribution, and fallback events. Tests: happy public site; degraded browser; safety hostile HTML fixture; contracts `web.fetch`, `browser.session`; golden `golden/wf05/audit.md`. Deviations: None.

### WF-08 — SEO keyword research

**Source ref:** `user-spec:WF-08` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 2 · **Domain family:** marketing-seo-product  
**Risk tier:** R1 (factors: seo_estimates, owner_property_data) · **Engine:** complex · **Default intensity:** medium  
**Reconciliation:** action `NEW` · canonical owner `none` · existing assets `skill:.agents/skills/deep-research/SKILL.md`, `mcp:firecrawl`, `skill:.agents/skills/data-scraper-agent/SKILL.md` · duplicate surfaces avoided `separate SERP skill`, `second keyword cache`, `stealth SERP scraper` · delta `Creates one official-data-first SEO owner with geo/language/date/match-type normalization and an adapter boundary for GSC and Keyword Planner.` · evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-08`, `.agents/skills/deep-research/SKILL.md`

#### 1. Purpose and user story
- Turn a site, seed themes, competitors, market, and language into a defensible keyword/content opportunity map with explicitly labeled source quality.
- User story: “As an SEO lead, I want clustered keyword opportunities tied to pages so that I can select content work by opportunity rather than intuition.”
- Boundary: no paid-campaign setup or spend; ad-group output belongs to WF-09. No direct page implementation; that belongs to WF-19 or the owner’s CMS process.
- Routing: `SEO keyword research`, `keyword gaps`, `content keyword map`, `cluster my keywords`, `find search opportunities`; negative triggers: `Google Ads campaign keywords` → WF-09, `audit my site UX` → WF-05. Alias: `/seo-keywords`.
- Modes: interactive, background, scheduled for owner-verified GSC refresh only. Success means each priority is reproducible by keyword, market, language, source/date, intent, cluster, mapped URL, and score.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| site_url | url | yes | owner or public site; https | PUBLIC | — |
| seeds | list<string> | yes | 1–50 normalized themes | INTERNAL | — |
| competitors | list<url> | no | 0–10 public domains | PUBLIC | `[]` |
| market | string | yes | ISO country/region | INTERNAL | — |
| language | string | yes | BCP-47 | INTERNAL | — |
| owner_gsc_property | string | no | verified property only | PII | — |
| browser_profile | enum | conditional | a,b,c if SERP browser is needed | INTERNAL | `b` |

- Preconditions: `web.search` and `web.fetch` healthy; official account adapters require owner authorization and must expose only consented property data; browser SERP inspection is owner-present and `SH-SEC-BROWSER` governed.
- Intensity profile — numbers only:
| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 8 | 40 | 0 | 0 | 1 | 1 |
| medium | 20 | 150 | 0 | 0 | 2 | 2 |
| high | 50 | 500 | 0 | 0 | 2 | 2 |
| limitless | 100 | 2000 | 0 | 0 | 2 | 3 |
- Budget: `300 / 3600 / 45`. Deviations: `recency` tightens for SERP snapshots in §3.

#### 3. Data sources and knowledge bases
- Primary: owner-authorized Google Search Console query/page rows and Google Ads Keyword Planner metrics where available; official Google documentation supports policy/feature claims. Public SERP snapshots and competitor pages establish observed intent and gaps. SEOData/vendor records are T3 estimates.
- Every row carries keyword, geo, language, device if applicable, date, source URL/ID, `metric_source`, and canonical source identifier: GSC property URL, Keyword Planner market pull, SERP query snapshot ID, or competitor URL.
- `sources.min_tier: T2`; `min_independent: 2` for competitor-gap claims; `recency_max_days: 7`, tightened to 1 day for SERP/current-ranking claims. GSC/Planner planning metrics TTL 7 days; “current” metrics TTL 24h under D4 and `SH-CACHE-3`.
- `memory.capture: decisions+sources`; retain approved clusters/content decisions and source references, never OAuth values. `cache.policy: standard`; SERP is `medium`; metrics asserting current conditions use `fresh-only`.
- No institutional route. Deviations: T3 estimates remain allowed only as `VENDOR-ESTIMATE` as required by D4 and `SH-SRC-6`.

#### 4. Tool chain and mechanisms
- Required: `web.search`, `web.fetch`, `llm.extract`, `llm.classify`, `llm.cluster`, `llm.summarize`. Optional: `data.seo.keyword_metrics`, `data.seo.gsc_performance`, `browser.session`.
- If account metrics are absent, the report says “Official account metrics unavailable; volume, difficulty, and CPC are vendor estimates or unavailable, not Google values.” If browser is absent, “SERP-derived intent and feature observations are unavailable; clustering uses supplied and fetched pages only.”
- Normalize seed expansion; retrieve owner property and public competitor pages; obtain official metrics only within consent; classify intent with page/SERP evidence; cluster semantic variants; detect near-duplicate target-page conflicts; map clusters to existing/new content; score transparent opportunity. Complex re-research is bounded to three loops for unresolved high-priority evidence gaps.
- This is the single proposed `seo-keyword-workflow` owner; no separate crawler or metric store. Use only public/authorized data and honor D4 ToS; untrusted page/SERP content is handled through `SH-SEC-INJ` and URLs through `SH-SEC-SSRF`.

#### 5. Internal data structures / schemas
- Defines `KeywordRecord`: `keyword`, `market`, `language`, `intent`, `volume`, `difficulty`, `cpc`, `metric_source`, `metric_date`, `serp_snapshot_id`, `cluster_id`, `target_url`, `content_action`, `cannibalization_group`, `priority_score`, `citations`.
- Defines `KeywordCluster`: `cluster_id`, `primary_keyword`, `members`, `intent`, `funnel_stage`, `recommended_page`, `gap_type`, `score_components`, `rationale`.
- Consumes `RunContext`, `SourceRecord`, `Citation`, `ArtifactManifest`, `ValidationResult`; no shared-schema extension.
- Declared artifacts: `keyword_strategy` (markdown, required); `keyword_table` (CSV/XLSX, required); `keyword_dataset` (JSON, required); `serp_manifest` (JSON, conditional).
```json
{"keyword":"solar roof tiles","market":"RO","language":"ro","intent":"commercial","volume":480,"difficulty":42,"cpc":3.1,"metric_source":"VENDOR-ESTIMATE:SEOData","metric_date":"2026-08-29","serp_snapshot_id":"serp-12","cluster_id":"cl-04","target_url":"/acoperis-solar","content_action":"refresh","cannibalization_group":null,"priority_score":61,"citations":["src-12","src-31"]}
```

#### 6. Step-by-step execution flow
- Engine: complex because gaps in high-value clusters can require bounded re-querying. Phases: `validate`, `discover`, `recall`, `plan`, `execute`, `spec-review`, `quality-review`, `acceptance`, `capture`; `max_depth: 2`, `max_loops: 3`.
1. `validate_scope` (validate, gate) → validates market, property consent, and profile need → receipt.
2. `collect_site` (discover, tool, `web.fetch`) → maps owned URLs/content → page source set.
3. `expand_seeds` (plan, llm) → builds normalized candidate set → candidate dataset.
4. `pull_metrics` (execute, tool, `data.seo.keyword_metrics`) → obtains authorized/estimated metrics → dated metric rows.
5. `inspect_serps` (execute, foreach, `browser.session`) → records bounded query observations → SERP manifest.
6. `classify_cluster_map` (execute, join, `llm.cluster`) → intent, clusters, gaps, cannibalization, content mapping → strategy dataset checkpoint.
7. `resolve_gaps` (spec-review, branch) → rechecks only evidence-deficient high-score rows → amended source set.
8. `validate_strategy` (acceptance, gate) → verifies citations, labels, scores, and schema → verdict.
- Approval: deterministic gates; `human_required: 0`, `panel_required: false`; spending or account changes are excluded. Resume reuses unexpired source hashes and recomputes derived scores when input version changes.

#### 7. Output format and UX behavior
- Output starts with assumptions and data availability, then narrative opportunity themes, a sortable table, intent/cluster map, competitor gap list, cannibalization warnings, content roadmap, and an uncertainty section. Score is visible: `priority_score = 0.35*normalized_volume + 0.25*intent_value + 0.20*gap_strength + 0.20*business_fit − cannibalization_penalty`, scaled 0–100 with components shown.
- Export `md`, `csv`, `xlsx`, `json` to `research`, named `seo-keyword-research_{YYYY-MM-DD}`, language `en`.
- Preview shows source mix, markets/languages, account connection state, cluster count, and whether numbers are official or estimates. Citations use `SH-SRC-9` brackets; SERP snapshots show timestamp, geo, language, and device.
- Degradation messages are those in §4. Deviations: None.

#### 8. Logging, validation, and safety
- Applies `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER` when used, `SH-SEC-REDACT`, `SH-SEC-CRED`. D4 rules forbid unauthorized SERP/GSC/Ads access.
- Required disclaimers: `DISC-SEO-1` under `SH-RISK-3`. R1, escalating to R2 for authenticated live-account access; classifications PUBLIC, PII for identifiable GSC queries, SECRET for credentials.
- Gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, metric-label/date/geo completeness, property-authorization check, cluster uniqueness, and score formula validation.
| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Keyword Planner unavailable | CAPABILITY_UNAVAILABLE | omit official metrics; retain labeled estimates | “Official keyword metrics unavailable; no Google values are shown.” |
| SERP access disallowed | POLICY | omit SERP inspection | “SERP observation was not permitted; intent confidence is reduced.” |
| GSC property not verified | AUTH | exclude property data | “The requested Search Console property is not authorized.” |
| stale metric row | STALE | re-pull or label stale/exclude | “A metric expired before export and was revalidated or omitted.” |
- Ledger adds source-tier mix, metric-source counts, query/cluster counts, score distribution, profile choice, and fallback provenance. Tests: official-metric fixture; vendor-only degraded fixture; hostile competitor HTML fixture; contracts `data.seo.keyword_metrics`, `web.fetch`; golden `golden/wf08/strategy.md`. Deviations: None.

### WF-09 — Keyword generator (Google Ads)

**Source ref:** `user-spec:WF-09` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 2 · **Domain family:** marketing-seo-product  
**Risk tier:** R2 (factors: authenticated_ads_account, potential_spend) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `MERGE_ALIAS` · canonical owner `workflow:WF-08` · existing assets `workflow:WF-08`, `skill:.agents/skills/deep-research/SKILL.md`, `mcp:firecrawl` · duplicate surfaces avoided `separate Google-Ads keyword skill`, `campaign-launch code`, `invented CPC/volume` · delta `Adds an ads-mode seed-to-campaign draft behind explicit account consent while preserving draft-only output.` · evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-09`, `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-08`

#### 1. Purpose and user story
- Generate campaign-ready keyword drafts from authorized account metrics, public competitor ads/landing pages, ad libraries, and seeds, without creating, editing, or launching a campaign.
- User story: “As a paid-search manager, I want a reviewable keyword and negative-keyword CSV so that I can build campaigns faster without delegating spend.”
- Boundary: SEO content strategy belongs to WF-08; media buying, billing, and campaign activation are explicitly R3 and out of scope.
- Routing: `Google Ads keywords`, `create ad groups`, `negative keyword list`, `PPC keyword generator`, `keyword planner draft`; negative triggers: `launch campaign` → external owner action, `SEO roadmap` → WF-08. Alias: `/ads-keywords`.
- Modes: interactive and owner-present-only for authenticated data. Success means every row states theme, match type, source/date/market, metric provenance, bid range if available, and review status.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| landing_pages | list<url> | yes | 1–20 public/owned URLs | PUBLIC | — |
| seeds | list<string> | yes | 1–100 terms | INTERNAL | — |
| market | string | yes | ISO country/region | INTERNAL | — |
| language | string | yes | BCP-47 | INTERNAL | — |
| ads_account_ref | secret_ref | no | env/native reference; consent required | SECRET | — |
| competitor_ads | list<url> | no | public-library or public pages | PUBLIC | `[]` |
| match_types | list<enum> | no | broad, phrase, exact | INTERNAL | `[phrase,exact]` |

- Preconditions: account adapter health and explicit owner authorization when `ads_account_ref` exists; no capability that writes campaigns may be selected.
- Intensity profile — numbers only:
| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 5 | 30 | 0 | 0 | 1 | 0 |
| medium | 15 | 120 | 0 | 0 | 2 | 0 |
| high | 30 | 400 | 0 | 0 | 2 | 0 |
| limitless | 60 | 1200 | 0 | 0 | 2 | 0 |
- Budget: `220 / 2700 / 35`. Deviations: None.

#### 3. Data sources and knowledge bases
- Primary: owner-authorized Google Ads/Keyword Planner metrics and Auction Insights where available; public Google Ads Transparency Center or other public ad-library ad IDs; public competitor landing pages. SEOData is an explicitly labeled T3 fallback.
- Rows carry ad-library ID/URL, landing URL, pull date, geo, language, match type, and account-metric label. Customer IDs and tokens never enter artifacts.
- `sources.min_tier: T2`; `min_independent: 2` for competitor claims; `recency_max_days: 7`, tightened to 1 day for live-ad status. Planner metrics TTL 7 days for drafts, 24 hours when rendered as current; ad state TTL 24 hours.
- `memory.capture: decisions`; preserve approved taxonomy/negative-term rationale only. `cache.policy: standard`; account data is owner-scoped and never shared; current-state data is `fresh-only` when feeding a spend decision.
- No institutional access. Deviations: no claim of competitor spend, targeting, or private account data.

#### 4. Tool chain and mechanisms
- Required: `web.fetch`, `llm.extract`, `llm.classify`, `llm.cluster`, `fs.write`. Optional: `data.seo.keyword_metrics`, `data.ads.auction_insights`, `browser.session`.
- Without official metrics: “Account metrics unavailable; bid, CPC, and volume are estimates or blank.” Without public ad-library access: “Competitor creative evidence unavailable; themes use supplied landing pages.”
- Parse public creative/page themes, expand and de-duplicate terms, pull authorized metrics, label commercial intent, propose match types and negatives, group into ad themes, and compute bid ranges only from available metric fields. The export has no API mutation node and no side-effect capability.
- Reuses WF-08’s owner and normalized SEO schemas; no rival ads provider wrapper. Public content remains untrusted (`SH-SEC-INJ`); browser flows require `SH-SEC-BROWSER`.

#### 5. Internal data structures / schemas
- Defines `AdKeywordRow`: `campaign_theme`, `ad_group`, `keyword`, `match_type`, `intent`, `volume`, `competition`, `cpc_low`, `cpc_high`, `bid_range`, `metric_source`, `negative_reason`, `source_refs`, `review_status`.
- Defines `NegativeKeyword`: `term`, `scope`, `reason`, `evidence_refs`, `confidence`.
- Consumes WF-08 `KeywordRecord` plus shared `RunContext`, `SourceRecord`, `Citation`, and `ArtifactManifest`.
- Declared artifacts: `campaign_keyword_draft` (CSV, required); `ads_keyword_report` (markdown, required); `negative_keywords` (CSV, required).
```json
{"campaign_theme":"roof solar","ad_group":"purchase intent","keyword":"solar roof tiles","match_type":"exact","intent":"commercial","volume":480,"competition":"medium","cpc_low":2.4,"cpc_high":4.2,"bid_range":"2.40-4.20 RON","metric_source":"GOOGLE_KEYWORD_PLANNER","negative_reason":null,"source_refs":["src-04"],"review_status":"owner_review_required"}
```

#### 6. Step-by-step execution flow
- Engine: simple. Phases: `validate`, `discover`, `plan`, `execute`, `quality-review`, `acceptance`, `capture`.
1. `validate_ads_scope` (validate, gate) → checks consent and draft-only invariant → receipt.
2. `collect_public_evidence` (discover, foreach, `web.fetch`) → captures public ads/pages → source set.
3. `expand_and_group` (plan, `llm.cluster`) → creates themes and candidate groups → taxonomy artifact.
4. `pull_authorized_metrics` (execute, tool, `data.seo.keyword_metrics`) → obtains bounded account metrics → metric rows.
5. `compose_draft` (execute, llm) → assigns types, negatives, and ranges → CSV schema checkpoint.
6. `validate_no_launch` (acceptance, gate) → checks no external action/campaign ID mutation and citations → verdict.
- Approval: deterministic plus human gate before any use in a live account; `human_required: 1`, `panel_required: false`. Resume reuses only valid cache and never replays authorization.

#### 7. Output format and UX behavior
- The report includes account-data status, themes/ad groups, keyword table, negatives, bid/metric provenance, competitor observations, exclusions, and an owner checklist before import. Every estimate is visibly labeled.
- Export `csv`, `md`, `json` to `output`, named `google-ads-keyword-draft_{YYYY-MM-DD}`, language `en`; CSV columns are stable and import-oriented, but no auto-import occurs.
- Preview explicitly states “draft only; no campaign will be created or launched,” selected market/language, source mix, and account authorization state.
- Optional capability messages are defined in §4. Deviations: None.

#### 8. Logging, validation, and safety
- Applies `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER` when needed, `SH-SEC-CRED`, `SH-SEC-REDACT`, and `SH-TOOL-5`.
- Required disclaimers: `DISC-SEO-1` under `SH-RISK-3`. Effective R2 when account data is connected; SECRET, PII, and PUBLIC handling is recorded.
- Gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, account-consent receipt, metric provenance/completeness, match-type enum validation, negative-term collision check, and no-external-side-effect assertion.
| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| consent missing | REQUIRE_APPROVAL | stop account pull | “Google Ads data needs explicit owner authorization; no account data was read.” |
| account adapter unavailable | CAPABILITY_UNAVAILABLE | generate estimate/blank draft | “Campaign draft created without official account metrics.” |
| request to launch | SAFETY | deny and retain draft | “Launching campaigns is outside this workflow; review the CSV and act manually.” |
| public ad source blocked | POLICY | omit source | “Public ad evidence was unavailable under source rules; no substitute was inferred.” |
- Ledger adds only redacted account state, source IDs, metric labels, draft hash, and no-launch receipt. Tests: authorized metrics; no-account degraded; prompt requesting launch; contracts `data.seo.keyword_metrics`, `fs.write`; golden `golden/wf09/keywords.csv`. Deviations: None.

### WF-10 — Product teardown

**Source ref:** `user-spec:WF-10` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 2 · **Domain family:** marketing-seo-product  
**Risk tier:** R1 (factors: public_web_content, competitor_observation) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `COMPOSE` · canonical owner `workflow:WF-10` · existing assets `skill:.agents/skills/deep-research/SKILL.md`, `skill:.agents/skills/ui-audit/SKILL.md`, `skill:.agents/skills/design-studio/SKILL.md`, `mcp:firecrawl`, `mcp:playwright` · duplicate surfaces avoided `standalone teardown crawler`, `copied UI audit`, `security testing` · delta `Composes public-product research and UI-audit evidence into a dated teardown.` · evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-10`

#### 1. Purpose and user story
- Capture and explain how a named product presents pricing, features, onboarding, positioning, differentiation, and objection handling using public evidence and screenshots.
- User story: “As a product strategist, I want a structured competitor teardown so that I can learn patterns without mistaking them for unverified facts.”
- Boundary: no copying UI/code/brand assets and no offensive testing; owner-site audit is WF-05 and inspiration synthesis is WF-11.
- Routing: `tear down this product`, `analyze competitor onboarding`, `competitor pricing analysis`, `product positioning review`; negative triggers: `brand inspiration deck` → WF-11, `website audit` → WF-05. Alias: `/product-teardown`.
- Modes: interactive/background public research; owner-present-only for ToS-restricted surfaces. Success means each conclusion links to dated page/screenshot evidence and separates observed fact from inference.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| product_url | url | yes | public https URL | PUBLIC | — |
| app_store_urls | list<url> | no | 0–5 official listings | PUBLIC | `[]` |
| review_sources | list<url> | no | public/lawful sources | PUBLIC | `[]` |
| comparison_focus | list<enum> | no | pricing, features, onboarding, positioning, objections | INTERNAL | all |
| browser_profile | enum | conditional | a,b,c for rendered flows | INTERNAL | `c` |

- Preconditions: source and browser health; profile decision before browser use; accessible public scope only.
- Intensity profile — numbers only:
| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 3 | 8 | 0 | 0 | 1 | 0 |
| medium | 8 | 20 | 0 | 0 | 2 | 0 |
| high | 16 | 45 | 0 | 0 | 2 | 0 |
| limitless | 30 | 100 | 0 | 0 | 2 | 0 |
- Budget: `160 / 2400 / 24`. Deviations: None.

#### 3. Data sources and knowledge bases
- Primary records are public product, pricing, documentation, terms, app-store pages, and allowed review pages. Each has URL/ID, publisher, retrieval timestamp, hash, screenshot reference, and page type.
- `sources.min_tier: T2`; `min_independent: 2` for comparative assertions; `recency_max_days: 1` for current pricing/features. Product/vendor pages and reviews are T3/T4 and rendered as such.
- `memory.capture: decisions+sources`; retain a concise, source-linked pattern record, not proprietary page copies. `cache.policy: standard`; pricing and plans are `fast`; screenshots/page snapshots `medium`.
- No paywall route. Deviations: current price and availability claims use six-hour TTL per D7.

#### 4. Tool chain and mechanisms
- Required: `web.search`, `web.fetch`, `browser.session`, `llm.extract`, `llm.summarize`. Optional `image.analyze` annotates screenshots; absence yields unannotated references.
- Static fetch establishes facts; browser captures public flow states; review text is sampled only within ToS and never treated as product truth. The narrative follows evidence categories and keeps observation, interpretation, and hypothesis distinct.
- Reuses `deep-research` for factual collection and `ui-audit` for visual capture; it does not create a crawler. Apply `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, and D7 ToS boundaries.

#### 5. Internal data structures / schemas
- Defines `TeardownSection`: `section`, `observations`, `evidence_refs`, `interpretation`, `confidence`, `unknowns`.
- Defines `ProductScreenshot`: `screenshot_id`, `journey_step`, `url`, `viewport`, `captured_at`, `artifact_path`, `annotation_refs`.
- Consumes `SourceRecord`, `Citation`, `RunContext`, `ArtifactManifest`.
- Declared artifacts: `product_teardown` (markdown, required); `screenshots_manifest` (JSON, required); `teardown_data` (JSON, required).
```json
{"section":"pricing","observations":["Three plans are displayed with monthly and annual toggles."],"evidence_refs":["src-05","shot-02"],"interpretation":"Annual framing likely targets commitment-sensitive buyers.","confidence":"medium","unknowns":["Checkout discounts were not inspected."]}
```

#### 6. Step-by-step execution flow
- Engine: simple. Phases: `validate`, `discover`, `plan`, `execute`, `quality-review`, `acceptance`, `capture`.
1. `validate_target` (validate, gate) → validates public scope/profile → receipt.
2. `collect_product_sources` (discover, foreach, `web.fetch`) → retrieves named source types → source set.
3. `plan_journey` (plan, llm) → selects public pages/flow stops → journey map.
4. `capture_evidence` (execute, tool, `browser.session`) → screenshots public states → manifest checkpoint.
5. `synthesize_teardown` (execute, llm) → produces structured sections → teardown schema.
6. `verify_separation` (quality-review, gate) → checks fact/inference labels → receipt.
7. `accept_teardown` (acceptance, gate) → citation and manifest gates → verdict.
- Approval: deterministic only; `human_required: 0`, `panel_required: false`. Resume reuses unexpired hashes and recaptures changed pages.

#### 7. Output format and UX behavior
- Deliverable sections: positioning snapshot; screenshots/journey; pricing; features; onboarding; differentiation; objections; review signals; transferable lessons; uncertainty. Screenshot references use manifest IDs rather than embedded copyrighted mirrors.
- Export `md`, `json` to `research`, named `product-teardown_{YYYY-MM-DD}`, language `en`. Preview shows source count, page types, screenshot plan, profile, and excluded gated areas.
- Citations are bracketed under `SH-SRC-9`; vendor/review material is visibly labeled. Missing screenshot analysis: “Screenshots were captured but automated annotation is unavailable.”
- Deviations: None.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, `SH-SEC-REDACT`. Required disclaimer: `DISC-WEB-1` under `SH-RISK-3`.
- R1; PUBLIC/P1 only. Gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, screenshot manifest, observation/inference separation, and source TTL check.
| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| login wall | AUTH | stop at public boundary | “This product area requires authentication and was not inspected.” |
| robots/ToS restriction | POLICY | omit restricted content | “Restricted pages were excluded; no bypass was attempted.” |
| review source unavailable | CAPABILITY_UNAVAILABLE | omit review section | “No lawful review evidence was available for this teardown.” |
| suspicious page content | SAFETY | quarantine | “Suspicious page instructions were excluded from the evidence set.” |
- Ledger: URLs/IDs/hashes, screenshots, excluded pages, TTL outcomes, source tiers. Tests: public SaaS fixture; login-wall degradation; hidden-text injection; contracts `web.fetch`, `browser.session`; golden `golden/wf10/teardown.md`. Deviations: None.

### WF-11 — Brand inspiration

**Source ref:** `user-spec:WF-11` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 2 · **Domain family:** marketing-seo-product  
**Risk tier:** R1 (factors: copyright_provenance, public_web_content) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `COMPOSE` · canonical owner `workflow:WF-11` · existing assets `skill:.agents/skills/design-studio/SKILL.md`, `skill:.agents/skills/ui-ux-pro-max/SKILL.md`, `skill:.agents/skills/design-system/SKILL.md`, `skill:.agents/skills/imagegen/SKILL.md` · duplicate surfaces avoided `brand-inspiration skill`, `copied competitor kit`, `generated brand SSOT` · delta `Composes annotated public references with provenance and an explicit no-clone boundary.` · evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-11`

#### 1. Purpose and user story
- Assemble a rights-aware visual reference deck from selected competitors and pattern libraries, explaining transferable patterns in heroes, CTAs, typography, imagery, and layout.
- User story: “As a brand designer, I want annotated references so that I can make original design decisions informed by recognizable patterns.”
- Boundary: it does not reproduce a competitor identity or build a site; site plans belong to WF-19 and image generation belongs to existing `imagegen`.
- Routing: `brand inspiration`, `reference deck`, `analyze hero sections`, `CTA examples`, `design pattern references`; negative triggers: `clone this site` → denied/WF-19 boundary, `build website` → WF-19. Alias: `/brand-inspiration`.
- Modes: interactive/background for public references. Success means every example has provenance, rights status, explanation, and a transformation note that prevents direct copying.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| reference_urls | list<url> | yes | 1–20 public pages | PUBLIC | — |
| pattern_libraries | list<url> | no | licensed/public sources | PUBLIC | `[]` |
| owner_brand_guidelines | file | no | owner-granted path; hash | INTERNAL | — |
| focus | list<enum> | no | hero, cta, type, imagery, layout | INTERNAL | all |
| browser_profile | enum | conditional | a,b,c for captures | INTERNAL | `c` |

- Preconditions: URL and rights-metadata validation; browser profile choice before capture; source licenses are recorded, not inferred.
- Intensity profile — numbers only:
| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 0 | 6 | 0 | 0 | 1 | 0 |
| medium | 0 | 15 | 0 | 0 | 2 | 0 |
| high | 0 | 35 | 0 | 0 | 2 | 0 |
| limitless | 0 | 75 | 0 | 0 | 2 | 0 |
- Budget: `120 / 1800 / 18`. Deviations: None.

#### 3. Data sources and knowledge bases
- Sources are supplied competitor URLs, licensed pattern libraries, owner brand guidelines (T4 authoritative only for the owner brand), and source terms/URLs. Each visual has URL, capture date, viewport, hash, license/ToS status, and usage classification.
- `sources.min_tier: T2`; `min_independent: 2` for claims that a pattern is widespread; `recency_max_days: 30`. `memory.capture: decisions`; persist approved original design directions, not reference images.
- `cache.policy: standard`; public visual pages are `medium`; owner guidelines remain valid until hash changes. No institutional path.
- Deviations: rights/provenance is a required source attribute even where §8.2 would otherwise allow a general marketing source.

#### 4. Tool chain and mechanisms
- Required: `web.fetch`, `browser.session`, `image.analyze`, `llm.summarize`. Optional `image.generate` is for clearly distinct mood exploration after an owner decision; absence removes generated exploration only.
- Capture bounded screenshots; extract visual/copy patterns; annotate why a pattern may aid clarity, hierarchy, or trust; contrast it with owner guidelines; produce an originality transformation note. Never download or redistribute asset packs.
- Reuses `design-studio` and `ui-ux-pro-max`; no new design system or asset repository. Apply `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`; D7/D8 provenance and likeness rules apply where relevant.

#### 5. Internal data structures / schemas
- Defines `ReferenceCard`: `reference_id`, `source_url`, `source_name`, `captured_at`, `screenshot_id`, `pattern_type`, `observed_pattern`, `why_it_works`, `adaptation_note`, `rights_status`, `citation_refs`.
- Defines `DeckOutline`: `slide_number`, `title`, `cards`, `speaker_note`.
- Consumes shared `SourceRecord`, `Citation`, `ArtifactManifest`, `RunContext`.
- Declared artifacts: `brand_reference_deck_outline` (markdown, required); `reference_manifest` (JSON, required); `reference_cards` (JSON, required).
```json
{"reference_id":"ref-07","source_url":"https://example.com","source_name":"Example","captured_at":"2026-08-29T10:00:00Z","screenshot_id":"shot-07","pattern_type":"hero","observed_pattern":"Outcome-led headline with one primary CTA.","why_it_works":"The hierarchy makes the intended next step unambiguous.","adaptation_note":"Use an original message, layout, and assets.","rights_status":"reference-only; source terms unverified","citation_refs":["src-07"]}
```

#### 6. Step-by-step execution flow
- Engine: simple. Phases: `validate`, `discover`, `plan`, `execute`, `quality-review`, `acceptance`, `capture`.
1. `validate_references` (validate, gate) → validates URLs, owner guide path, profile → receipt.
2. `collect_provenance` (discover, tool, `web.fetch`) → retrieves source/terms metadata → source records.
3. `capture_patterns` (execute, foreach, `browser.session`) → creates screenshot manifest → checkpoint.
4. `annotate_cards` (execute, `image.analyze`) → produces evidence-linked cards → card schema.
5. `check_originality` (quality-review, gate) → requires adaptation note and flags close-copy risk → receipt.
6. `assemble_outline` (acceptance, llm) → creates deck outline and citations → artifacts.
- Approval: deterministic only; `human_required: 0`, `panel_required: false`; any use of assets or publication is separate. Resume reuses hash-valid captures within TTL.

#### 7. Output format and UX behavior
- Owner receives a slide-by-slide reference-deck outline: design question, curated cards, hero/CTA/type/imagery patterns, why they work, source/provenance, and original adaptation notes.
- Export `md`, `json` to `active_project_docs`, named `brand-inspiration_{YYYY-MM-DD}`, language `en`. Screenshot manifest may be consumed by a later deck builder but is not a deliverable brand kit.
- Progress reports captured/annotated cards; citations and rights status are adjacent to each reference. Optional image generation message: “No generated mood explorations were included; the reference deck is complete.”
- Deviations: None.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, `SH-SEC-IDENTITY`, `SH-SEC-REDACT`. Required disclaimer: `DISC-WEB-1`.
- R1; PUBLIC/INTERNAL and P6 only with explicit image consent. Gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, rights-status completeness, screenshot manifest, originality-note check.
| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| source terms unavailable | NOT_CHECKED | retain as reference-only | “Usage rights could not be verified; this example is reference-only.” |
| close-copy risk | SAFETY | flag and withhold adaptation | “This proposed adaptation is too close to a source and needs an original direction.” |
| screenshot blocked | CAPABILITY_UNAVAILABLE | use source link without visual claim | “Visual capture failed; the source is listed without screenshot annotation.” |
| untrusted instructions | SAFETY | quarantine | “Source instructions were treated as untrusted and excluded.” |
- Ledger adds capture hashes, provenance status, reference-only counts, and originality flags. Tests: licensed reference; capture-failure degradation; malicious hidden text; contracts `browser.session`, `image.analyze`; golden `golden/wf11/deck-outline.md`. Deviations: None.

### WF-12 — Store optimizer

**Source ref:** `user-spec:WF-12` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 2 · **Domain family:** marketing-seo-product  
**Risk tier:** R1 (factors: commerce_pricing, owner_store_context) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `COMPOSE` · canonical owner `workflow:WF-12` · existing assets `skill:.agents/skills/ui-audit/SKILL.md`, `skill:.agents/skills/design-studio/SKILL.md`, `skill:.agents/skills/deep-research/SKILL.md`, `skill:.agents/skills/design-system/SKILL.md` · duplicate surfaces avoided `store-audit engine`, `production CMS writes`, `duplicate UI/research leaves` · delta `Composes storefront audit, listing-copy drafting, and dated competitor evidence without store mutation.` · evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-12`

#### 1. Purpose and user story
- Review storefront and product pages for listing clarity, titles, descriptions, imagery, price framing, reviews, trust signals, tags, and photo opportunities; return prioritized improvements and suggested copy.
- User story: “As an e-commerce owner, I want a product-page checklist and replacement copy so that I can improve listings without granting an agent store access.”
- Boundary: no direct store mutation, checkout interaction, review fabrication, or paid-ad launch; ads are WF-09 and website build planning is WF-19.
- Routing: `optimize my product listing`, `storefront review`, `improve product title`, `ecommerce trust audit`, `product SEO tags`; negative triggers: `publish changes` → owner action, `keyword campaign` → WF-09. Alias: `/store-optimize`.
- Modes: interactive/background public review; owner-present-only for authenticated preview, still read-only. Success means copy is traceable to supplied facts and every recommendation has user impact/effort/priority.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| storefront_url | url | yes | https | PUBLIC | — |
| product_urls | list<url> | yes | 1–50 URLs | PUBLIC | — |
| product_facts | file | no | owner path; facts only | INTERNAL | — |
| competitor_urls | list<url> | no | 0–10 public listings | PUBLIC | `[]` |
| market | string | no | ISO country/region | INTERNAL | — |
| browser_profile | enum | conditional | a,b,c | INTERNAL | `b` |

- Preconditions: owner-property scope for authenticated pages; no `browser.act`; product fact file hash validation.
- Intensity profile — numbers only:
| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 3 | 8 | 0 | 0 | 1 | 0 |
| medium | 8 | 25 | 0 | 0 | 2 | 0 |
| high | 15 | 60 | 0 | 0 | 2 | 0 |
| limitless | 30 | 150 | 0 | 0 | 2 | 0 |
- Budget: `180 / 2700 / 26`. Deviations: None.

#### 3. Data sources and knowledge bases
- Primary: owner storefront/product pages and owner product facts; competitor listings and SEOData are comparison/estimate sources. Source records include product URL/SKU when public, price/currency, retrieved time, hash, and image screenshot ID.
- `sources.min_tier: T2`; `min_independent: 2` for competitor comparisons; `recency_max_days: 1`, with product price TTL tightened to 6 hours. `memory.capture: decisions`; retain owner-approved listing decisions, not customer data.
- `cache.policy: standard`; product pages are `medium`, prices/reviews/stock are `fast`. SEOData data stays T3 and labeled.
- No institutional access. Deviations: product claims not present in owner facts/page must be rendered as a question, never invented copy.

#### 4. Tool chain and mechanisms
- Required: `web.fetch`, `browser.session`, `image.analyze`, `llm.extract`, `llm.rewrite`, `fs.write`. Optional `data.seo.keyword_metrics` supports tag suggestions; absence says “Tag suggestions are page-derived; no keyword metrics were available.”
- Audit pages and captured imagery; distinguish product facts from persuasive hypotheses; compare public competitors; produce rewrite variants marked `draft`; calculate a visible recommendation score using impact, confidence, effort, and evidence freshness.
- Reuses audit/design/research leaves and never calls a commerce/CMS write adapter. `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, and `SH-TOOL-5` constrain all paths.

#### 5. Internal data structures / schemas
- Defines `ListingRecommendation`: `recommendation_id`, `product_url`, `area`, `current_evidence`, `proposed_copy`, `fact_refs`, `impact`, `effort`, `confidence`, `freshness`, `priority_score`, `review_required`.
- Defines `ProductPageSnapshot`: `product_url`, `sku`, `price`, `currency`, `retrieved_at`, `content_hash`, `screenshot_ids`.
- Consumes shared schemas unchanged.
- Declared artifacts: `store_optimization_report` (markdown, required); `listing_copy_drafts` (CSV/JSON, required); `product_snapshot_manifest` (JSON, required).
```json
{"recommendation_id":"rec-14","product_url":"https://example.com/p/widget","area":"title","current_evidence":"Current title omits material and primary use.","proposed_copy":"Stainless Steel Travel Widget — Leak-Resistant Daily Carry","fact_refs":["src-02","ownerfact-01"],"impact":4,"effort":1,"confidence":4,"freshness":"fresh","priority_score":80,"review_required":true}
```

#### 6. Step-by-step execution flow
- Engine: simple. Phases: `validate`, `discover`, `plan`, `execute`, `quality-review`, `acceptance`, `capture`.
1. `validate_store_scope` (validate, gate) → validates URLs/facts/read-only invariant → receipt.
2. `snapshot_products` (discover, foreach, `web.fetch`) → collects structured page facts → snapshot manifest.
3. `render_visuals` (execute, tool, `browser.session`) → captures image/trust/checkout-adjacent signals without acting → screenshots.
4. `compare_and_extract` (execute, join, `llm.extract`) → identifies gaps and evidence → findings.
5. `draft_copy` (execute, `llm.rewrite`) → makes fact-bound titles/descriptions/tags → copy schema checkpoint.
6. `score_check` (quality-review, gate) → computes ranking and rejects unsupported claims → receipt.
7. `accept_export` (acceptance, export) → writes report/drafts/manifests → verdict.
- Approval: deterministic gates; `human_required: 0`, `panel_required: false`; publishing remains owner/R3. Resume reuses valid product snapshots and rechecks price/stock freshness.

#### 7. Output format and UX behavior
- Report contains storefront overview, per-product checklist, priority table, improved copy, image/photo tips, trust/review observations, tags, comparator evidence, and an owner review checklist. Priority is `impact × confidence × (6 − effort)`, with freshness downgrade shown.
- Export `md`, `csv`, `json` to `output`, named `store-optimizer_{YYYY-MM-DD}`, language `en`.
- Preview states product count, source freshness, profile, no-mutation guarantee, and metric availability. Citations sit next to claims and `VENDOR-ESTIMATE` labels.
- Missing metric capability message is in §4. Deviations: None.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, `SH-SEC-REDACT`, `SH-TOOL-5`. Required disclaimer: `DISC-WEB-1`.
- R1; PUBLIC/INTERNAL, escalating PII/P3 handling if authenticated commerce surfaces reveal customer data, which must be excluded. Gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, fact-to-copy coverage, stale-price check, no-write capability assertion, schema/score validation.
| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| customer data visible | SAFETY | stop/omit customer-bearing view | “Customer data was detected; it was excluded from this store review.” |
| product price stale | STALE | re-fetch or remove price observation | “A product-price observation expired and was revalidated or removed.” |
| CMS action requested | SAFETY | deny | “This workflow drafts improvements only and cannot change the store.” |
| image analysis unavailable | CAPABILITY_UNAVAILABLE | text-only photo checklist | “Visual image analysis is unavailable; photo guidance is based on page evidence only.” |
- Ledger records product hashes, fact coverage, score distribution, excluded PII, and no-write receipt. Tests: public product page; image-tool degradation; customer-data fixture; contracts `web.fetch`, `llm.rewrite`; golden `golden/wf12/report.md`. Deviations: None.

### WF-18 — Slide creation

**Source ref:** `user-spec:WF-18` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 2 · **Domain family:** marketing-seo-product  
**Risk tier:** R1 (factors: factual_presentation, owner_content) · **Engine:** complex · **Default intensity:** medium  
**Reconciliation:** action `REUSE` · canonical owner `skill:.agents/skills/slides/SKILL.md` · existing assets `skill:.agents/skills/slides/SKILL.md`, `script:bundled slide render/overflow/montage/font validators` · duplicate surfaces avoided `new slide-builder skill`, `python-pptx generation fork`, `unvalidated deck` · delta `Adds only catalog metadata requiring research citations and structured slide schema before the existing slide owner renders.` · evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-18`, `.agents/skills/slides/SKILL.md`

#### 1. Purpose and user story
- Research an owner-selected topic from authoritative domain sources, form a story arc, and return slide content plus a machine-readable deck specification consumable by the existing slide builder.
- User story: “As a presenter, I want an evidence-backed slide outline and notes so that I can communicate a complex topic clearly and verify the claims.”
- Boundary: does not publish or present on the owner’s behalf; visual brand exploration is WF-11 and website planning is WF-19.
- Routing: `make slides about`, `research presentation`, `presentation outline`, `speaker notes`, `slide deck`; negative triggers: `brand reference deck` → WF-11, `convert a file` → WF-16. Alias: `/slides`.
- Modes: interactive/background for public sources; owner-present-only when source material is sensitive. Success means every factual slide point has a citation or is marked as owner input/inference, and every slide has a purpose and visual recommendation.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| topic | string | yes | 3–500 chars | INTERNAL | — |
| audience | string | yes | ≤300 chars | INTERNAL | — |
| objective | enum | yes | inform, persuade, teach, decision | INTERNAL | — |
| slide_count | integer | no | 5–30 | INTERNAL | 10 |
| source_files | list<file> | no | granted paths; MIME/size validation | INTERNAL | `[]` |
| language | enum | no | ro, en | INTERNAL | `en` |

- Preconditions: topic/audience/objective present; source files pass containment; factual topic requires `web.search`/`web.fetch` health.
- Intensity profile — numbers only:
| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 4 | 6 | 2 | 0 | 1 | 1 |
| medium | 10 | 16 | 6 | 0 | 2 | 2 |
| high | 24 | 36 | 14 | 0 | 2 | 2 |
| limitless | 50 | 80 | 30 | 0 | 2 | 3 |
- Budget: `260 / 3600 / 38`. Deviations: None.

#### 3. Data sources and knowledge bases
- Authorities are selected by topic domain using `SH-SRC-1`/`SH-SRC-2`: official institutions, standards, primary records, and peer-reviewed sources where applicable. Owner files are T4 for their contents and are not promoted to external authority.
- `sources.min_tier: T2`; `min_independent: 2` for load-bearing slide claims; `recency_max_days: 365` unless the topic domain tightens it. `memory.capture: decisions+sources`; preserve approved storyline and citations.
- `cache.policy: standard`; static papers/standards use shared volatility; time-sensitive subjects declare `fresh-only` before research. Paywall access, if lawful and needed, follows `SH-SRC-8`.
- Deviations: domain-specific floors/risk tiers override this generic presentation entry when topic content requires them.

#### 4. Tool chain and mechanisms
- Required: `web.search`, `web.fetch`, `llm.extract`, `llm.summarize`, `llm.structure`, `fs.write`. Optional `image.generate` suggests original visuals only; optional `doc.extract_text` ingests owner files. Existing `slides` renders and validates when the owner requests a deck artifact.
- Build a claim ledger first, cluster evidence into a narrative arc, constrain each slide to one takeaway, then produce titles, bullets, speaker notes, visual directions, and citations. Complex engine permits bounded re-research for unsupported load-bearing slides.
- Reuses the `slides` owner and its render/overflow validators. Citations, untrusted-source handling, and sensitive-file controls remain `SH-SRC-*`, `SH-SEC-INJ`, and `SH-SEC-REDACT`.

#### 5. Internal data structures / schemas
- Defines `SlideSpec`: `slide_number`, `title`, `takeaway`, `bullets`, `speaker_notes`, `visual_suggestion`, `layout_hint`, `citations`, `claim_ids`, `status`.
- Defines `DeckSpec`: `topic`, `audience`, `objective`, `story_arc`, `slides`, `source_manifest_id`, `language`.
- Consumes `SourceRecord`, `Citation`, `RunContext`, `ArtifactManifest`; no shared extension.
- Declared artifacts: `slide_outline` (markdown, required); `slide_schema` (JSON, required); `source_manifest` (JSON, required); `rendered_deck` (pptx/pdf, optional through existing owner).
```json
{"slide_number":3,"title":"Why the problem persists","takeaway":"The bottleneck is process variability, not demand.","bullets":["Variation creates rework.","Standardization reduces handoffs."],"speaker_notes":"Contrast current-state examples with the cited benchmark.","visual_suggestion":"Simple before/after flow diagram using original shapes.","layout_hint":"two-column","citations":["src-03","src-08"],"claim_ids":["clm-04"],"status":"draft"}
```

#### 6. Step-by-step execution flow
- Engine: complex because unsupported high-importance claims must re-enter research. Phases: `validate`, `discover`, `recall`, `plan`, `execute`, `spec-review`, `quality-review`, `acceptance`, `capture`; `max_depth: 2`, `max_loops: 3`.
1. `validate_brief` (validate, gate) → checks topic, files, and risk → receipt.
2. `research_sources` (discover, fanout, `web.search`) → finds domain authorities → source candidates.
3. `verify_claims` (execute, tool, `web.fetch`) → retrieves/hashes support → source manifest checkpoint.
4. `shape_story` (plan, `llm.structure`) → makes narrative arc → story artifact.
5. `draft_slides` (execute, llm) → emits `DeckSpec` → schema checkpoint.
6. `repair_unsupported_claims` (spec-review, branch) → re-researches or removes unsupported priority claims → amended deck.
7. `render_validate` (quality-review, tool, existing slides owner) → optional render/overflow checks → validation receipt.
8. `accept_deck` (acceptance, gate) → citation/source/schema checks → verdict.
- Approval: deterministic gates; `human_required: 0`, `panel_required: false`, unless topic elevation triggers a stricter domain gate. Resume retains source records and reruns changed/expired claims only.

#### 7. Output format and UX behavior
- Deliverable is an executive brief, story arc, slide outline, per-slide bullets/notes/visual suggestions, bracketed citations, uncertainty list, and a machine-readable JSON deck schema. Rendered PPTX/PDF is optional and never claimed if render validation did not run.
- Export `md`, `json`, optional `pptx`, `pdf` to `active_project_docs`, named `slide-creation_{YYYY-MM-DD}`, language from input.
- Preview shows slide count, source plan, research intensity, optional render state, and distribution/budget. Long research sends phase heartbeats.
- Missing render capability: “Slide schema and outline are complete; no rendered deck was produced because the slide renderer is unavailable.” Deviations: None.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-REDACT`, and `SH-SEC-PHI` if health files are supplied. Required disclaimers follow the topic’s `SH-RISK-3` domain, not a generic presentation disclaimer.
- Base R1; data classes PUBLIC/INTERNAL/PII as applicable, with topic-specific escalation. Gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, slide-schema validation, claim-to-slide coverage, and render/overflow validation when rendered output is requested.
| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| source retrieval fails | FAILED_TO_RUN | omit unsupported claim or stop if load-bearing | “A required source could not be verified; the affected slide was withheld.” |
| source file injection | SAFETY | quarantine file text | “A supplied file contained untrusted instructions and was excluded.” |
| renderer unavailable | CAPABILITY_UNAVAILABLE | return validated schema/outline only | “No rendered deck is available; use the exported slide schema.” |
| high-risk topic gate | REQUIRE_APPROVAL | escalate to domain protocol | “This topic requires the applicable domain review before release.” |
- Ledger includes deck/source hashes, claim coverage, render receipts, slide count, and fallback events. Tests: evidence-backed deck; no-render degradation; hostile source-file fixture; contracts `web.fetch`, `fs.write`; golden `golden/wf18/deck.json`. Deviations: None.

### WF-19 — Website builder

**Source ref:** `user-spec:WF-19` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 2 · **Domain family:** marketing-seo-product  
**Risk tier:** R1 (factors: user_facing_site, deployment_boundary) · **Engine:** complex · **Default intensity:** medium  
**Reconciliation:** action `COMPOSE` · canonical owner `workflow:WF-19` · existing assets `skill:.agents/skills/prototype/SKILL.md`, `skill:.agents/skills/design-studio/SKILL.md`, `skill:.agents/skills/ui-ux-pro-max/SKILL.md`, `skill:.agents/skills/clone-website/SKILL.md`, `mcp:playwright`, `mcp:firecrawl` · duplicate surfaces avoided `mega website-builder skill`, `competitor cloning`, `silent deployment` · delta `Composes guided planning, owner requirements, design validation, and an explicit gate separating planning, code generation, and deployment.` · evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-19`, `.agents/skills/prototype/SKILL.md`

#### 1. Purpose and user story
- Convert guided owner requirements into an implementation-ready website plan: sitemap, component/content model, technology recommendation, wireframe descriptions, scaffold specifications, validation plan, and gated deployment plan.
- User story: “As a site owner, I want a structured build plan so that I can approve scope and design before anyone generates code or deploys infrastructure.”
- Boundary: this workflow does not generate production code, alter a repository, purchase domains, configure credentials, or deploy. WF-05 audits an existing site; WF-11 provides references without cloning.
- Routing: `plan a website`, `website requirements`, `sitemap and components`, `web app scaffold spec`, `deployment plan`; negative triggers: `deploy site` → R3 owner action, `clone competitor website` → denied, `audit URL` → WF-05. Alias: `/website-builder`.
- Modes: interactive only for requirement decisions; background may research public framework documentation after an approved brief. Success means code generation and deployment are visibly blocked until specified gates and owner approval occur.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---:|---|---|---|
| business_goal | string | yes | ≤1000 chars | INTERNAL | — |
| target_users | string | yes | ≤1000 chars | INTERNAL | — |
| required_pages | list<string> | no | 0–50 names | INTERNAL | `[]` |
| content_assets | list<file> | no | granted paths; hash | INTERNAL | `[]` |
| inspiration_urls | list<url> | no | reference-only public pages | PUBLIC | `[]` |
| framework_preference | enum | no | none, static, react, next, aspnet, other | INTERNAL | `none` |
| deployment_target | string | no | plan only; no credentials | INTERNAL | `unspecified` |

- Preconditions: requirements completeness ASK-gate; inspiration scope/right-to-reference confirmation; framework documentation capability health; code/deployment capability intentionally absent from this definition.
- Intensity profile — numbers only:
| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---:|---:|---:|---:|---:|---:|
| small | 4 | 6 | 2 | 0 | 1 | 1 |
| medium | 10 | 15 | 5 | 0 | 2 | 2 |
| high | 20 | 30 | 10 | 0 | 2 | 2 |
| limitless | 40 | 60 | 20 | 0 | 2 | 3 |
- Budget: `240 / 3600 / 36`. Deviations: `execution.modes` excludes deployment by design.

#### 3. Data sources and knowledge bases
- Primary: owner requirement answers, owner brand/content assets, and official framework/deployment documentation selected for the chosen stack. Inspiration pages are observational references with URL, date, screenshot ID, and rights/provenance; they are never implementation source material.
- `sources.min_tier: T2`; `min_independent: 2` for framework tradeoff claims; `recency_max_days: 365`, tightened to 30 days for deployment/platform feature claims. `memory.capture: decisions`; retain approved requirements, architecture choices, and unresolved decisions.
- `cache.policy: standard`; official docs are `slow`, platform/deployment status is `medium`. No paywall path. `clone-website` is permitted only for licensed/reference extraction when an owner explicitly grants it, never as default.
- Deviations: stack/deployment advice must name documentation version/date, and no source supports a claim that deployment has occurred.

#### 4. Tool chain and mechanisms
- Required: `web.search`, `web.fetch`, `browser.session` for inspiration captures, `doc.extract_text`, `llm.extract`, `llm.structure`, `fs.write`. Optional `image.analyze` improves reference annotations; missing it leaves text wireframes intact.
- Start with requirements interview and constraints; build information architecture and content model; compare only official framework docs; write component contracts and textual wireframes; produce code-scaffold specifications, test/acceptance plan, and an explicit future deployment runbook. Planning output contains a `next_gate` rather than executable code or deployment instructions with secrets.
- Reuses `prototype`, `design-studio`, and `ui-ux-pro-max`. Apply `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, `SH-SEC-REDACT`; inspiration HTML cannot select tools, profile, stack, or deployment target.

#### 5. Internal data structures / schemas
- Defines `WebsitePlan`: `requirements`, `sitemap`, `content_model`, `component_specs`, `wireframes`, `tech_stack`, `scaffold_spec`, `validation_plan`, `deployment_plan`, `open_decisions`, `next_gate`.
- Defines `ComponentSpec`: `component_id`, `purpose`, `inputs`, `states`, `accessibility_requirements`, `content_fields`, `acceptance_criteria`.
- Defines `DeploymentGate`: `status`, `required_approvals`, `blocked_actions`, `prerequisites`, `owner_action`.
- Consumes shared `RunContext`, `SourceRecord`, `Citation`, `ArtifactManifest`, `SafetyDecision`.
- Declared artifacts: `website_plan` (markdown, required); `website_plan_schema` (JSON, required); `wireframe_descriptions` (markdown, required); `deployment_gate` (JSON, required).
```json
{"requirements":{"business_goal":"Capture qualified consultation leads","target_users":"Romanian residential owners","constraints":["no account required"]},"sitemap":["/","/services","/pricing","/contact"],"content_model":["service","testimonial","faq"],"component_specs":[{"component_id":"hero","purpose":"State outcome and route to contact","inputs":["headline","proof","cta"],"states":["default"],"accessibility_requirements":["one h1","visible focus"],"content_fields":["headline","cta_label"],"acceptance_criteria":["CTA is keyboard reachable"]}],"wireframes":["Home: hero, proof, services, FAQ, CTA"],"tech_stack":{"framework":"next","reason_citations":["src-04"]},"scaffold_spec":{"status":"planned-only"},"validation_plan":["responsive","accessibility","content review"],"deployment_plan":{"status":"not authorized"},"open_decisions":["hosting provider"],"next_gate":"owner approves plan before code generation"}
```

#### 6. Step-by-step execution flow
- Engine: complex because unresolved requirements or conflicting stack evidence may re-enter bounded discovery. Phases: `validate`, `discover`, `recall`, `plan`, `spec-review`, `quality-review`, `acceptance`, `capture`; `max_depth: 2`, `max_loops: 3`.
1. `validate_brief` (validate, gate) → asks bounded requirements questions and validates assets → receipt.
2. `capture_references` (discover, foreach, `web.fetch`) → records inspiration provenance and official docs → source manifest.
3. `model_information_architecture` (plan, `llm.structure`) → sitemap/content model → IA artifact.
4. `specify_components` (plan, llm) → components, states, accessibility, wireframes → component schema checkpoint.
5. `select_stack` (spec-review, llm) → documents alternatives against official docs → decision record.
6. `define_gates` (quality-review, gate) → separates plan, code generation, and deployment; prohibits action nodes → deployment gate.
7. `accept_plan` (acceptance, gate) → validates citations, scope, schema, and owner-ready decision list → verdict.
- Approval: deterministic gates plus `human_required: 1` before a plan can advance to any code-generation workflow; `panel_required: false`. Deployment requires a separate R3 accountable owner action. Resume reuses valid docs/reference records but reopens unresolved owner decisions.

#### 7. Output format and UX behavior
- The owner receives requirements/assumptions; sitemap; content model; component catalog; wireframe descriptions; stack decision and cited tradeoffs; scaffold specification; validation checklist; deployment plan; open decisions; and a clearly highlighted “Planning complete — code generation and deployment remain blocked” gate.
- Export `md`, `json` to `active_project_docs`, named `website-builder-plan_{YYYY-MM-DD}`, language `en`. No source code, infrastructure configuration, or deployment artifact is exported by this workflow.
- Preview shows requirements coverage, reference provenance, selected framework alternatives, design scope, and next gate. Missing image analysis: “Textual wireframes are complete; reference-image annotations are unavailable.”
- Deviations: planning-only boundary is a deliberate tightening; no owner decision may loosen it inside this workflow.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, `SH-SEC-REDACT`, `SH-TOOL-5`. Required disclaimer: `DISC-WEB-1`.
- R1 while planning; any production changes/deployment are R3 and not admitted. PUBLIC/INTERNAL/PII owner-content classification is recorded.
- Gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, requirements completeness, component-schema validation, inspiration provenance/originality check, no-code/no-deploy action assertion, and deployment-gate completeness.
| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| incomplete requirements | REQUIRE_APPROVAL | retain open decisions; no scaffold sign-off | “The plan needs owner decisions before it can advance to code generation.” |
| request to clone or deploy | SAFETY | deny action; preserve compliant plan | “This workflow plans an original site only; cloning and deployment require separate authorization.” |
| official docs unavailable | CAPABILITY_UNAVAILABLE | present no stack recommendation | “Framework documentation could not be verified; stack selection remains open.” |
| inspiration injection | SAFETY | quarantine reference | “An inspiration page contained untrusted instructions and was excluded.” |
- Ledger adds requirement-decision IDs, cited doc versions, reference manifests, code/deploy denial receipts, plan hash, and gate state. Tests: complete brief; documentation-unavailable degradation; clone/deploy request fixture; contracts `web.fetch`, `fs.write`; golden `golden/wf19/plan.json`. Deviations: None.
