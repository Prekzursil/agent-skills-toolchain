# Perplexity-Class Workflow Suite — Part 05: Personal Health & Adjacent Life Planning

Date: 29.08.2026  
Status: DESIGN — documentation only; no implementation, no commits  
Scope: `WF-31`, `WF-34`, `WF-35`, `WF-36`, `WF-37`, `WF-38`, `WF-39`, `WF-40`  
Owner: Miky (Marius Valentin Visalon)  
Normative foundation: `PERPLEXITY-WORKFLOWS-PART-00-SHARED_2026-08-29.md` (cite `SH-*` IDs; do not restate)

---

## Part-level notes

- **Batch:** Part 05 per `SH-DOC-1` / `SH-DOC-2`.
- **Domain families spanned:** `careers-housing` (WF-31, WF-34) and `clinical-health` (WF-35–WF-40).
- **Health owner architecture:** One thin `health-review` owner (`WF-35`, action **NEW**) exposes modes `review` | `nutrition` | `labs` | `visit-prep` | `fitness` | `sleep`. `WF-36`–`WF-40` are **MERGE/ALIAS** or **COMPOSE** into those modes — not six duplicate skills (`SH-DUP-3`, reuse matrix §8).
- **P4 default:** All `clinical-health` workflows declare `execution.locality: local-only`; `PHI` never enters shared cache (`SH-CACHE-7`); remote model egress of `PHI` requires per-run owner approval recorded on the distribution preview (`SH-INT-5`, `SH-SEC-PHI`).
- **Non-clinical boundaries:** No diagnosis, prescribing, dosing directives, emergency routing substitution, or portal send without explicit R3 owner action (`SH-RISK-1`, source-risk D9-health prohibited claims).

---

### WF-31 — Internship housing finder

<!-- PREAMBLE (not a subsection; nothing else may live outside the eight) -->
**Source ref:** `user-spec:WF-31` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 5 · **Domain family:** careers-housing  
**Risk tier:** R2 (factors: `browser_authenticated`, `personal_health_data` not triggered; escalates to R3 on pay/sign/message) · **Engine:** complex · **Default intensity:** medium  
**Reconciliation:** action `NEW` · canonical owner `internship-housing-finder` · existing assets `deep-research`, `browser-rail`, `playwright`, `firecrawl` · duplicate surfaces avoided `general housing scraper`, `board-specific skills`, `payment/messaging capability` · delta `Add 6h listing/rent TTL, university-first sources, listing ID/hash, map/transit version, fraud flags, P3 location controls, and pay/sign R3 gate` · evidence `REUSE-MCP-MATRIX row WF-31; RISK D6/WF-31; INDEX housing search no owner`

#### 1. Purpose and user story
- Job-to-be-done: find short-term internship housing in a target city by matching city, dates, budget, commute tolerance, and preferences against university housing, licensed rental platforms, student housing, community boards, and map/transit context — producing a ranked shortlist with fraud flags, pros/cons, verified links, and **draft** outreach text the owner has not sent.
- User story: "As an intern relocating for a term, I want a verified shortlist of housing options near my site so that I can contact hosts myself without the assistant paying, signing, or messaging on my behalf."
- Boundary: not tenancy legal advice (`WF-21`/`WF-22`), not long-term lease negotiation, not roommate matching as a dossier service (`WF-32`), not general job search (`WF-25`). Not medical or safety inspection of units.
- Routing: trigger phrases — `internship housing`, `short-term rental near`, `student housing city`, `commute from campus`, `summer sublet`; negative triggers — `buy property` → finance workflows; `legal lease review` → `WF-23`; `job housing stipend tax` → `WF-17`; slash aliases — `/housing-intern`, `/internship-housing`.
- Execution modes: `interactive`, `owner-present-only` when `browser.session` is authenticated or messaging is drafted; `background` prohibited when browser is required (`SH-SEC-BROWSER` BR-4, `SH-RISK-2`).
- Success criterion: every presented listing carries `listing_id`, `retrieved_at`, `content_hash`, re-fetch status within 6h TTL, commute evidence with map/transit snapshot date, and explicit `OWNER-ACTION` for contact/pay/sign.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `target_city` | string | yes | 2–80 chars; locale NFC | INTERNAL | — |
| `country_region` | enum | yes | `RO` \| `EU` \| `US` \| `UK` \| other ISO region | INTERNAL | `RO` |
| `start_date` | date | yes | ISO; ≥ today | INTERNAL | — |
| `end_date` | date | yes | after `start_date` | INTERNAL | — |
| `monthly_budget` | number | yes | currency + amount; min 0 | INTERNAL | — |
| `currency` | enum | yes | ISO 4217 | INTERNAL | `RON` |
| `internship_site` | string | no | address or landmark; precision capped P3 | PII/P3 | — |
| `max_commute_minutes` | integer | no | 5–120 | INTERNAL | 45 |
| `commute_modes` | list\<enum\> | no | `walk` \| `transit` \| `bike` \| `drive` | INTERNAL | `["transit","walk"]` |
| `preferences` | object | no | furnished, private room, pets, quiet, etc. | INTERNAL | `{}` |
| `university_affiliation` | string | no | for official dorm eligibility | PII | — |
| `source_allowlist` | list\<url\> | no | SSRF-validated (`SH-SEC-SSRF`) | INTERNAL | university + owner-named platforms |
| `browser_profile` | enum | yes | `a` \| `b` \| `c` per `SH-SEC-BROWSER` BR-1 | INTERNAL | `b` |
| `include_community_boards` | bool | no | T5/T3 leads only | INTERNAL | true |

- Preconditions: RAM ≥ 8 GB for browser queue (`SH-ARCH-9`); `browser_profile` recorded before first navigation (`SH-SEC-BROWSER`); free RAM check before `browser.session`.
- Intensity profile — numbers only; preset meanings fixed by §14.1:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 3 | 6 | 2 | 3 | 1 | 0 |
| medium | 6 | 14 | 5 | 3 | 2 | 1 |
| high | 12 | 30 | 12 | 5 | 2 | 2 |
| limitless | until saturation | until saturation | all load-bearing | 5+ | 3 | up to `max_loops` |

- Budget: `max_invocations` 80 / `max_wall_clock_s` 2400 / `max_cost_units` 18 (medium baseline).
- Deviations: listing availability TTL tightened to **6 hours** (source-risk D6); overrides `recency_max_days` for price/availability claims.

#### 3. Data sources and knowledge bases
- **Primary (T0/T1):** university/employer official housing pages; licensed platform listings with stable listing ID; OpenStreetMap / official GTFS static feeds for commute (`OSM` way/node ID, GTFS `feed_info` version); municipal/university dorm regulations when cited.
- **Secondary (T3):** rental platforms (Idealista, Imobiliare.ro, Airbnb, Facebook groups) — leads only; community boards T5 for discovery, never load-bearing availability.
- `sources.min_tier`: T1/T2 per §8.2 `careers-housing`; rent/availability load-bearing claims require platform listing ID + re-fetch.
- `sources.min_independent`: 2 for rent figures (`SH-SRC-2`).
- `sources.recency_max_days`: 0.25 (6h) for listing availability; 7 for static campus maps.
- Domain capabilities: `data.property_listings` (absent/deferred — compose `web.search` + `web.fetch` + `browser.session`); `data.transit_gtfs` when feed available.
- Basic Memory: `memory.capture: decisions` — capture search strategy and fraud-pattern notes only; **no** P3 addresses or host PII (`SH-OBS-8`).
- Cache: `cache.policy: fresh-only` for listing availability (`SH-CACHE-3`); `medium` class 24h for university policy pages; never cache full ToS-restricted platform HTML (source-risk §4.3).
- Paywall/institutional: not typical; public university pages via `web.fetch` or browser (c).
- Deviations: 6h TTL for `fast` listing claims — tighter than §9.2 default 15m floor for volatile class because housing fraud risk dominates.

#### 4. Tool chain and mechanisms
- Required: `web.search`, `web.fetch`, `browser.session`, `llm.extract`, `llm.summarize`, `fs.read`, `fs.write`.
- Optional: `web.map` (site enumeration on university domains); if absent, degrade to owner-supplied URLs only (`SH-TOOL-3`).
- Provider hints: `@firecrawl` search/scrape; `@playwright` or `@browser-bridge` for JS listings; maps/transit via direct HTTPS/API adapters (absent from MCP registry — direct provider path, `NOT-CHECKED` live health).
- Mechanism: university-first discovery lane → platform search lane (owner-present browser, profile recorded) → listing normalize/extract → commute snapshot node (map + GTFS) → fraud heuristic pass → rank/score → draft outreach templates (not sent).
- Reuse: thin `internship-housing-finder` recipe sequences `deep-research` discovery patterns and `browser-rail` profile gate — does not duplicate search or browser logic (`SH-DUP-5`).

#### 5. Internal data structures / schemas
- `HousingListingRecord`: `{listing_id, platform, url, title, rent_amount, currency, charges, term, address_precision, geo, retrieved_at, expires_at, content_hash, availability_status, source_tier, fraud_flags[], independence_group}`.
- `CommuteSnapshot`: `{origin_hash, destination_hash, mode, duration_minutes, distance_m, map_source_id, transit_feed_version, retrieved_at}`.
- `HousingShortlist`: `{run_id, city, dates, budget, listings: HousingListingRecord[], ranked: [{listing_id, score, pros[], cons[], stale_after}]}`.
- Shared schemas consumed: `RunContext`, `SourceRecord`, `Citation`, `ArtifactManifest`, `SafetyDecision` (§6).
- Declared artifacts:
  - `housing-shortlist.json` (required) — ranked listings + commute evidence.
  - `housing-shortlist.md` (required) — human brief with citations `[n]` per `SH-SRC-9`.
  - `outreach-drafts.md` (optional) — unsent message templates; footer `NOT SENT`.
- Schema example:

```json
{
  "listing_id": "idealista-987654321",
  "platform": "idealista",
  "url": "https://www.idealista.com/...",
  "rent_amount": 450,
  "currency": "EUR",
  "retrieved_at": "2026-08-29T10:00:00Z",
  "expires_at": "2026-08-29T16:00:00Z",
  "content_hash": "sha256:ab12...",
  "availability_status": "verified_same_day",
  "source_tier": "T3",
  "fraud_flags": ["wire_before_viewing"],
  "commute": { "duration_minutes": 28, "mode": "transit", "transit_feed_version": "2026-08" }
}
```

#### 6. Step-by-step execution flow
- Engine: `complex` — bounded re-search when stale listings exceed 30% of shortlist (`max_loops: 2`).
- Phases: `intake`, `discover`, `retrieve`, `normalize`, `verify`, `synthesize`, `validate`, `review` (subset per §3.1).
- Walkthrough:
  1. `intake_profile` (`intake`, `llm.extract`) → validate dates/budget → emit `SearchBrief`.
  2. `browser_gate` (`intake`, policy) → record `browser_profile` (`SH-SEC-BROWSER` BR-1) → abort if live profile needed but not chosen.
  3. `uni_housing_search` (`discover`, `web.search` + `web.fetch`) → official dorm/affiliate URLs.
  4. `platform_search` (`discover`, `browser.session`) → owner-present; extract listing cards with IDs.
  5. `listing_revalidate` (`verify`, `web.fetch`/`browser.session`) → re-fetch each finalist; mark `STALE` past 6h.
  6. `commute_calc` (`normalize`, deterministic + map adapter) → `CommuteSnapshot` per listing.
  7. `fraud_screen` (`verify`, rules + `llm.classify`) → wire-first, off-platform payment, duplicate photos flags.
  8. `rank_shortlist` (`synthesize`, `llm.summarize`) → pros/cons with source vs inference labels.
  9. `draft_outreach` (`synthesize`, `llm.rewrite`) → templates only; `side_effects: none`.
  10. `validate_outputs` (`validate`, deterministic) → citation coverage, TTL, reconciliation survey.
  11. `owner_review` (`review`, human) → R1 display; R3 gate if owner requests send (`external_action`).
- Approval: deterministic gates in `validate`; `human_required: true` before any `browser.act` or export to shared folders; `panel_required: false`.
- Resume: re-run `listing_revalidate` for unexpired checkpoints; never auto-replay outreach send (`SH-RUN-12`).

#### 7. Output format and UX behavior
- Deliverable sections (§16.1 skeleton): Header → **Ranked shortlist table** (rent, commute, freshness, fraud flags) → Evidence (listing URLs, map/transit cites) → Uncertainty (stale/unverified) → Provenance → Artifacts → Gates → Next actions (owner contact/pay only).
- Exports: `housing-shortlist_{YYYY-MM-DD}.md` + `.json` → `active_project_docs`; language `ro` for owner-facing prose, `en` for machine JSON (`SH-UX-5`).
- Citations: `[n] Title — Platform, accessed DD.MM.YYYY (T3)`; commute cites map/GTFS version.
- Source vs owner fact: table columns `claim`, `source_tier`, `owner_input` — budget/preferences labeled `OWNER-T4`.
- Degradation: if `browser.session` unhealthy → "Platform JS listings unavailable; showing university + static fetch results only" (`SH-INT-6`).
- Deviations: none.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, `SH-SEC-REDACT`, `SH-SEC-CRED` (§12.4).
- Disclaimers: none in §13.2 factor table; render §16.1 Uncertainty with listing-fraud notice reference (resolved via `safety/disclaimers.yaml` when implemented — not inline prose per `SH-RISK-3`).
- Risk: R2 with `browser_authenticated`; R3 if `external_action` requested.
- Classifications: `PII`/`P3` for addresses; minimize precision in exports (`SH-UX-13`).
- Deterministic gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, `listing_ttl_check`, `browser_profile_recorded`.
- Validation: rent numeric range; date order; listing `expires_at` in future at emit time.
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Listing past 6h TTL | POLICY | Mark `STALE`, exclude from "available" | "Listing not re-verified within 6h; treat as unconfirmed." |
| Owner requests pay/sign | POLICY | `REQUIRE_APPROVAL` R3 | "Payment and signing are owner-only actions." |
| Silent live profile needed | POLICY | `BLOCKED` | "Live browser profile (a) not chosen; cannot proceed." (`SH-SEC-BROWSER`) |
| Platform scrape ToS block | AUTH/POLICY | Degrade to official sources | "Platform browsing unavailable; university sources only." |

- Tests: happy (3 listings, 1 stale), degraded (no browser), safety (wire-fraud flag, pay attempt blocked) — `SH-TEST-5`.
- Deviations: none.

---

### WF-34 — Behavioral story generator

<!-- PREAMBLE -->
**Source ref:** `user-spec:WF-34` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 5 · **Domain family:** careers-housing  
**Risk tier:** R1 (factors: none beyond base; no `external_action` until owner sends) · **Engine:** simple · **Default intensity:** small  
**Reconciliation:** action `UPGRADE` · canonical owner `cv-studio` `stories` mode · existing assets `cv-studio` `x_master`, `x_metrics`, validate/zero-fabrication scripts · duplicate surfaces avoided `separate behavioral-story database`, `invented impact numbers` · delta `Add STAR/CAR story rendering strictly from x_master and x_metrics, linked to target JD competencies; unverified facts stay prompts` · evidence `REUSE-MCP-MATRIX row WF-34; skills/cv-studio/SKILL.md; RISK WF-34/D5`

#### 1. Purpose and user story
- Job-to-be-done: turn verified career facts in `profile.yaml` into 3–5 versatile STAR/CAR behavioral stories mapped to target competencies, with practice questions and phrasing variants — prompting for missing facts instead of inventing them.
- User story: "As a job seeker preparing interviews, I want coached stories grounded in my real achievements so that I can answer behavioral questions credibly."
- Boundary: not resume rewriting (`WF-33`), not cover letters (`WF-27`), not company research (`WF-26`), not health or personal narrative outside career facts.
- Routing: `STAR stories`, `behavioral interview`, `CAR examples`, `competency stories`; negative — `rewrite my CV` → `WF-33`; `mock interview company research` → `WF-26`; aliases `/behavioral-stories`, `/star-stories`.
- Execution modes: `interactive` only; no browser required.
- Success criterion: zero fabricated metrics; every number traces to `x_metrics`; every story bullet traces to `x_master`; gaps become explicit owner prompts.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `profile_path` | file | yes | `profile.yaml` under project; JSON Resume superset | PII | `profile.yaml` |
| `target_jd` | string | no | pasted JD text | INTERNAL | — |
| `competency_list` | list\<string\> | no | max 12 | INTERNAL | derived from JD |
| `story_count` | integer | no | 3–5 | INTERNAL | 4 |
| `framework` | enum | no | `STAR` \| `CAR` \| `both` | INTERNAL | `STAR` |
| `locale` | enum | no | `en` \| `ro` | INTERNAL | `en` |

- Preconditions: `cvstudio.py validate profile.yaml` passes or emits fixable warnings; `x_master` non-empty for selected roles.
- Intensity profile:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 0 | 0 | 1 (`profile.yaml`) | 3 | 1 | 0 |
| medium | 0 | 0 | 1 | 3 | 1 | 0 |
| high | 2 | 4 (JD only) | 1 | 3 | 1 | 1 |
| limitless | 2 | 6 | 1 | 5 | 2 | 1 |

- Budget: `max_invocations` 25 / `max_wall_clock_s` 600 / `max_cost_units` 4.
- Deviations: none.

#### 3. Data sources and knowledge bases
- **Primary (T4):** `profile.yaml` — `x_master` achievement bank, `x_metrics` verified numbers, `x_targets` JD context.
- **Secondary:** pasted JD text (untrusted, `PI-HIGH`); no web required at default intensity.
- `sources.min_tier`: T4 for biographical claims; JD competencies T4/untrusted wrapper.
- `sources.min_independent`: 1 (owner profile only for load-bearing career facts).
- `sources.recency_max_days`: null (owner facts until file hash changes).
- Basic Memory: `memory.capture: none` — stories stay in project artifacts; no achievement bank in vault (`SH-DUP-3`).
- Cache: `cache.policy: standard` on JD extract only; profile always read fresh by hash.
- Deviations: none.

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `llm.extract`, `llm.rewrite`, `llm.classify`, `fs.write`.
- Optional: `web.fetch` for public job posting URL if owner supplies (not invented).
- Mechanism: load profile → zero-fabrication lint → map JD competencies → select `x_master` entries → render STAR/CAR → generate practice Q&A → flag gaps as `OWNER_PROMPT_REQUIRED`.
- Reuse: routes into `cv-studio` `stories` mode; no parallel story database (`SH-DUP-3`, matrix §7).

#### 5. Internal data structures / schemas
- `BehavioralStory`: `{story_id, framework, competency_tags[], situation, task, action, result, metrics_refs[], x_master_keys[], confidence: verified|prompt_needed}`.
- `StoryBankOutput`: `{stories: BehavioralStory[], practice_questions[], phrasing_variants[], gaps[], profile_hash}`.
- Artifacts: `behavioral-stories_{YYYY-MM-DD}.md`, `behavioral-stories_{YYYY-MM-DD}.json`.
- Example:

```json
{
  "story_id": "s1",
  "framework": "STAR",
  "competency_tags": ["leadership", "stakeholder_management"],
  "result": "Delivered milestone 2 weeks early",
  "metrics_refs": ["metric:on_time_delivery_2024"],
  "x_master_keys": ["Acme Corp|Project Lead"],
  "confidence": "verified"
}
```

#### 6. Step-by-step execution flow
- Engine: `simple`; phases: `intake`, `normalize`, `synthesize`, `validate`, `review`.
- Nodes: `load_profile` → `validate_zero_fab` (shell `cvstudio.py validate`) → `extract_competencies` → `select_stories` → `render_star_car` → `practice_pack` → `gap_prompts` → `validate_outputs`.
- Approval: `human_required: true` before export; no panel.
- Resume: deterministic nodes memoized on profile hash (`SH-RUN-11`).

#### 7. Output format and UX behavior
- Sections: Header → Story cards (STAR/CAR) → Competency map → Practice questions → Phrasing variants → **Gaps to fill** (owner prompts) → Provenance (`profile_hash`, `x_metrics` keys used).
- Export: `behavioral-stories_{YYYY-MM-DD}.md` → `active_project_docs`; English default.
- Source vs owner: columns `Fact`, `Source` (`x_master` key / `x_metrics` id / `OWNER_PROMPT`).
- Deviations: none.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ` (JD text), `SH-SEC-REDACT`.
- Disclaimers: none required §13.2.
- Risk: R1; classifications `PII` in profile.
- Gates: `zero_fabrication_lint`, `metrics_traceability`, `reconciliation_survey`.
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Metric not in `x_metrics` | VALIDATION | Block story; add gap prompt | "Number not in x_metrics; provide verified value or remove." |
| Empty `x_master` for role | VALIDATION | Prompt owner | "No achievements banked for role; add x_master first." |
| JD injection in posting | POLICY | Quarantine per INJ-5 | "Untrusted JD content quarantined." |

- Tests: happy (4 verified stories), degraded (missing metrics), safety (invented number blocked).
- Deviations: none.

---

### WF-35 — Health review

<!-- PREAMBLE -->
**Source ref:** `user-spec:WF-35` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 5 · **Domain family:** clinical-health  
**Risk tier:** R2 (factors: `medical_advice`, `personal_health_data`) · **Engine:** complex · **Default intensity:** medium  
**Reconciliation:** action `NEW` · canonical owner `health-review` (modes: `review` | `nutrition` | `labs` | `visit-prep` | `fitness` | `sleep`) · existing assets `deep-research`, `evidence-ledger-synthesis`, `pdf-reader`, biomedical skills · duplicate surfaces avoided `six separate health skills`, `cloud PHI fan-out`, `model-as-clinician` · delta `Create local-P4 intake, document-vs-clinical-evidence separation, D1 source adapter, R2/R3 gates, required disclaimers, no-diagnosis boundary` · evidence `REUSE-MCP-MATRIX row WF-35; RISK D9-health/D1/WF-35`

#### 1. Purpose and user story
- Job-to-be-done: aggregate owner labs, history, medications, lifestyle, and goals with guideline-backed context into a comprehensive, time-normalized health review — identifying patterns, risk flags, and clinician discussion points without providing medical advice or diagnosis.
- User story: "As an owner tracking my health data locally, I want an organized review with sourced context so that I can discuss informed questions with my clinician."
- Boundary: not nutrition meal plans (`WF-36` mode), not single-panel lab parse (`WF-37`), not visit one-pager (`WF-38`), not exercise prescription (`WF-39`), not sleep disorder diagnosis (`WF-40`). **Not emergency care** — urgent symptoms route to emergency services messaging, not triage substitution.
- Routing: `health review`, `overall health picture`, `longitudinal labs`, `medication list review`; negative — `meal plan` → `WF-36`; `interpret this CBC` → `WF-37`; `/health-review`, `/health-review review`.
- Execution modes: `interactive`, `owner-present-only`; `background`/`scheduled` prohibited for `PHI` (`SH-SEC-PHI`).
- Success criterion: every clinical claim has D1 T0/T1 citation; every metric labeled `OWNER-T4` vs `GUIDELINE-T1`; disclaimers rendered by ID; P4 stays local.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `mode` | enum | yes | `review` \| `nutrition` \| `labs` \| `visit-prep` \| `fitness` \| `sleep` | INTERNAL | `review` |
| `health_bundle_path` | dir | yes | encrypted local project dir | PHI | — |
| `labs_paths` | list\<file\> | no | PDF/CSV; macros disabled | PHI | [] |
| `history_notes` | string | no | owner narrative | PHI | — |
| `medications` | list\<object\> | no | name, dose, schedule — owner asserted | PHI | [] |
| `allergies` | list\<string\> | no | | PHI | [] |
| `goals` | list\<string\> | no | | INTERNAL | [] |
| `jurisdiction` | enum | no | default RO+EU | INTERNAL | `RO` |
| `cloud_phi_consent` | bool | no | required for remote LLM on PHI | SECRET flag | false |
| `retain_bundle` | bool | no | encrypt at rest if true | PHI | true |

- Preconditions: `execution.locality: local-only`; `cloud_phi_consent` recorded on preview if remote; RAM guard (`SH-ARCH-9`).
- Intensity profile:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 3 | 6 | 2 | 3 | 2 | 0 |
| medium | 6 | 14 | 5 | 3 | 2 | 1 |
| high | 12 | 30 | 12 | 5 | 2 | 2 |
| limitless | saturation | saturation | all load-bearing | 5+ | 3 | 2 |

- Budget: `max_invocations` 100 / `max_wall_clock_s` 3600 / `max_cost_units` 22.
- Deviations: `cache.policy: fresh-only` mandatory for PHI paths (`SH-CACHE-3`, `SH-CACHE-7`).

#### 3. Data sources and knowledge bases
- **Owner (T4):** labs, meds, history, wearable exports — facts about what documents say, not clinical truth alone.
- **Clinical (D1 T0/T1):** PubMed/PMID, ClinicalTrials.gov NCT, WHO IRIS, NICE NG/CG, EMA/ANMDMR labels, specialty society guidelines (ESC, IDSA, etc.) with DOI/year; Cochrane CD when applicable.
- `sources.min_tier`: T1 per §8.2 `clinical-health`; T0 for dosing/contraindications if ever cited.
- `sources.min_independent`: 2 distinct groups for load-bearing recommendations (`SH-SRC-2`).
- `sources.recency_max_days`: 1 for "current guideline"; 7 for PMID metadata; immutable for historical lab values on report date.
- Domain: `data.drug_interactions` absent/deferred — narrative only from guideline text extraction.
- Basic Memory: `memory.capture: none` for raw labs; optional `decisions` without PHI values.
- Cache: `fresh-only`; PHI never in shared cache (`SH-CACHE-7`); D1 literature `slow` 7d in run `sources/` only.
- Institutional: `SH-SRC-8` for paywalled full text when needed; queries generalized (no raw lab values in telemetry).
- Deviations: P4 local-only default — tighter than generic `remote-allowed`.

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `doc.extract_text`, `llm.extract`, `llm.summarize`, `web.search.scholar`, `web.fetch`, `fs.write`.
- Optional: `web.search` (guideline discovery), `memory.search` (non-PHI decisions only).
- Mode routing: `mode` dispatches to same owner — `WF-36`–`WF-40` are aliases into `nutrition` | `labs` | `visit-prep` | `fitness` | `sleep` subgraphs (matrix §8).
- Mechanism: ingest encrypted bundle → normalize metrics timeline → extract owner facts (T4) → literature adapter for context → pattern/risk flag pass (non-diagnostic) → discussion-point synthesis → owner review gate.
- Reuse: composes `deep-research` clinical-update patterns + `evidence-ledger-synthesis` claim ledger; no sixth skill (`SH-DUP-3`).

#### 5. Internal data structures / schemas
- `HealthFact`: `{fact_id, kind: owner|source, class: PHI, text, provenance: T4|Tx, source_record_id?, collected_at}`.
- `MetricPoint`: `{name, value, unit, ref_range_printed, lab_id, collected_at, page, content_hash}`.
- `RiskFlag`: `{code, severity: discuss|urgent_screening, basis: owner_pattern|guideline, citation_ids[], not_diagnosis: true}`.
- `HealthReviewReport`: `{mode, metrics_timeline[], patterns[], risk_flags[], discussion_points[], conflicts[], owner_facts[], guideline_cites[]}`.
- Artifacts: `health-review_{YYYY-MM-DD}.md`, `health-review_{YYYY-MM-DD}.json`, `health-bundle.manifest.json` (hashes only).
- Storage: retained bundles encrypted (OS DPAPI or project AES key in gitignored `local.json`); minimized fields in exports (`SH-UX-13`).
- Example:

```json
{
  "metric": { "name": "LDL-C", "value": 4.2, "unit": "mmol/L", "collected_at": "2026-06-01", "provenance": "OWNER-T4" },
  "discussion_point": { "text": "Trend rising over 3 draws", "citations": ["pmid:12345678"], "not_diagnosis": true }
}
```

#### 6. Step-by-step execution flow
- Engine: `complex`; phases through `verify` + `review`; max_loops 2 on new literature gaps.
- Nodes: `decrypt_bundle` → `extract_metrics` → `timeline_normalize` → `owner_fact_ledger` → `guideline_search` (D1) → `pattern_analysis` → `risk_flags` (urgent → screen message, not diagnose) → `synthesize_review` → `disclaimer_inject` (IDs) → `validate` → `owner_approval`.
- Mode `review` is default; other modes delegate to specialized subgraphs documented in `WF-36`–`WF-40` without separate owners.
- Approval: R2 `human_required`; `panel_required: false`; R3 for care changes or external share.
- Resume: re-verify bundle hash; re-run literature if TTL expired (`SH-RUN-7`).

#### 7. Output format and UX behavior
- Deliverable: Executive summary → Metrics timeline table → Patterns → Risk flags (labeled **for clinician discussion**) → Owner facts vs guideline context (two-column) → Evidence → Uncertainty → Disclaimers (`DISC-MED-1`, `DISC-NOT-A-CLINICIAN` via `SH-RISK-3`).
- Export: `health-review_{YYYY-MM-DD}.md` → project `docs/` or owner health project folder; Romanian or English per `exports.language`.
- Emergency red-flag UX: banner "Seek emergency care locally if you have chest pain, stroke symptoms, or other emergency signs — this tool does not provide emergency services."
- Deviations: none.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-PHI`, `SH-SEC-REDACT`, `SH-SEC-SSRF` (literature fetch only).
- Disclaimers: `DISC-MED-1`, `DISC-NOT-A-CLINICIAN`.
- Gates: `citation_coverage`, `provenance_chain`, `phi_local_only`, `no_diagnosis_language`, `cloud_phi_consent_if_remote`.
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Remote without PHI consent | POLICY | BLOCKED | "PHI egress requires explicit cloud_phi_consent." |
| Diagnosis wording detected | VALIDATION | BLOCK rewrite | "Output blocked: diagnostic language not permitted." |
| Urgent red-flag pattern | POLICY | Allow report + emergency banner | "Discuss urgently with clinician or emergency services." |
| Missing guideline for claim | VALIDATION | Mark `unsourced-model-inference` | "Claim removed or labeled uncited." |

- Tests: happy review, degraded (no literature adapter), safety (diagnosis block, PHI egress block).
- Deviations: none.

---

### WF-36 — Nutrition planner

<!-- PREAMBLE -->
**Source ref:** `user-spec:WF-36` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 5 · **Domain family:** clinical-health  
**Risk tier:** R2 (factors: `medical_advice`, `personal_health_data`) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `MERGE_ALIAS` · canonical owner `health-review` `nutrition` mode · existing assets `health-review` owner, `deep-research` clinical sources · duplicate surfaces avoided `standalone nutrition-coach skill`, `treatment diet prescribing` · delta `Add dietary preferences/contraindication intake, source-labeled general planning, escalation for medical diets/eating-disorder/pregnancy context` · evidence `REUSE-MCP-MATRIX row WF-36; RISK WF-36; WF-35 reconciliation`

#### 1. Purpose and user story
- Job-to-be-done: produce general meal plans with macros, key nutrients, grocery list, and prep notes aligned to preferences, restrictions, goals, and labs — tying suggestions cautiously to lab trends and escalating medical-diet, eating-disorder, or pregnancy contexts.
- User story: "As an owner with dietary goals and lab context, I want a practical meal plan grounded in official nutrition data so that I can discuss changes safely with my clinician or dietitian."
- Boundary: not disease diagnosis (`WF-35`), not therapeutic diet prescription, not supplement dosing directives, not eating-disorder treatment. Routes through `health-review` `nutrition` mode only.
- Routing: `meal plan`, `nutrition planner`, `macros and groceries`, `diet for my labs`; negative — `interpret ferritin` → `WF-37`; `diabetes insulin plan` → escalate clinician; `/health-review nutrition`.
- Execution modes: `interactive`, `owner-present-only`; local-only PHI.
- Success criterion: nutrient targets cite official databases/guidelines; lab links labeled cautious/secondary; medical contexts trigger escalation not meal plans.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `mode` | enum | yes | fixed `nutrition` | INTERNAL | `nutrition` |
| `preferences` | object | yes | diet pattern, cuisines, cooking time | INTERNAL | — |
| `restrictions` | list\<string\> | no | allergies, intolerances, religious | PHI | [] |
| `goals` | list\<string\> | no | weight, energy, sport | INTERNAL | [] |
| `labs_context` | file | no | recent labs bundle | PHI | — |
| `pregnancy_status` | enum | no | `no` \| `yes` \| `possible` | PHI | `no` |
| `eating_disorder_history` | bool | no | if true → escalate | PHI | false |
| `medical_diet_orders` | bool | no | if true → escalate | PHI | false |
| `health_bundle_path` | dir | yes | shared with WF-35 | PHI | — |

- Intensity: medium default; small sufficient for single-week plan without new literature.
- Budget: `max_invocations` 60 / `max_wall_clock_s` 1800 / `max_cost_units` 12.
- Deviations: screening gates tighten intake — owner decision recorded if override.

#### 3. Data sources and knowledge bases
- **T0/T1 nutrition:** USDA FoodData Central, EU/RO official dietary guidelines (MS/ANSES/WHO healthy diet), national food composition tables; DRI/UL references with publication date.
- **Owner T4:** preferences, restrictions, labs (for cautious linkage only).
- `sources.min_tier`: T1 for nutrient reference values; T4 for owner restrictions.
- `sources.min_independent`: 2 for load-bearing nutrient adequacy claims.
- TTL: guidelines `slow` 7d; food DB nutrient rows `static` 90d; lab linkage session-only.
- Cache: `fresh-only` for PHI; literature standard in run dir only.
- Deviations: none.

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `llm.extract`, `llm.summarize`, `web.fetch`, `fs.write`; routes via `health-review` dispatcher.
- Mechanism: screen pregnancy/ED/medical-diet → if clear, fetch guideline/DRI → map labs to nutrients (non-prescriptive) → plan meals → grocery/prep → validate nutrient sums against DB.
- Reuse: MERGE into `health-review`; no `nutrition-coach` skill (`SH-DUP-3`).

#### 5. Internal data structures / schemas
- `MealPlan`: `{days[], meals[], macros_daily[], key_nutrients[], grocery_list[], prep_steps[], lab_links: CautiousLink[], sources[]}`.
- `CautiousLink`: `{lab_metric, nutrient, strength: weak|moderate, citation_id, not_prescription: true}`.
- `EscalationRecord`: `{reason, blocked_plan: true, clinician_prompt}`.
- Artifacts: `nutrition-plan_{YYYY-MM-DD}.md`, `nutrition-plan_{YYYY-MM-DD}.json`, `grocery-list_{YYYY-MM-DD}.md`.
- Example: `{"day": 1, "meals": [{"name": "Breakfast", "kcal": 520}], "sources": ["usda-fdc:12345"]}`

#### 6. Step-by-step execution flow
- `screen_contraindications` → if hit, `escalate` and stop plan → `load_labs` → `guideline_fetch` → `meal_compose` → `macro_validate` → `owner_review`.
- Approval: R2 human before export; escalation bypasses meal generation.
- Resume: standard `SH-RUN-7`.

#### 7. Output format and UX behavior
- Sections: Weekly overview → Daily meals → Macros/micros table → Grocery → Prep → **Cautious lab links** → Escalation (if any) → Disclaimers (`DISC-MED-1`, `DISC-NOT-A-CLINICIAN`).
- Export: `nutrition-plan_{YYYY-MM-DD}.md` + grocery list; `ro` default for meal names if owner locale RO.
- Source vs owner: nutrients `GUIDELINE-T1`; preferences `OWNER-T4`.
- Deviations: none.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-PHI`, `SH-SEC-INJ`, `SH-SEC-REDACT`.
- Disclaimers: `DISC-MED-1`, `DISC-NOT-A-CLINICIAN`.
- Red flags: pregnancy, ED history, renal/diabetes medical diet orders → `ESCALATE`, no plan.
- Gates: `medical_diet_screen`, `nutrient_source_coverage`, `no_dosing_directives`.
- Failure table:

| Scenario | Error class | Behavior | Message |
|---|---|---|---|
| Eating disorder flagged | POLICY | ESCALATE | "Specialist support needed; no automated meal plan." |
| Therapeutic diet requested | POLICY | ESCALATE | "Medical nutrition therapy requires clinician/dietitian." |
| Nutrient claim without DB cite | VALIDATION | BLOCK | "Nutrient value lacks FoodData/guideline cite." |

- Tests: happy week plan, escalation paths, PHI local-only.
- Deviations: none.

---

### WF-37 — Lab results interpreter

<!-- PREAMBLE -->
**Source ref:** `user-spec:WF-37` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 5 · **Domain family:** clinical-health  
**Risk tier:** R2 (factors: `medical_advice`, `personal_health_data`) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `COMPOSE` · canonical owner `health-review` `labs` mode + `pdf-reader`/local extraction leaf · existing assets `pdf-reader` (parked), `doc.extract_text`, biomedical skills · duplicate surfaces avoided `new lab-reader skill`, `enabling macros`, `invented ranges` · delta `Extract value/unit/range/flag/page before commentary; hash report; clinical thresholds require D1 cites; OCR uncertainty visible` · evidence `REUSE-MCP-MATRIX row WF-37; RISK WF-37/D9; REG pdf-reader parked`

#### 1. Purpose and user story
- Job-to-be-done: parse lab panels from PDF/image exports, reproduce each value/unit/reference range/date/page faithfully, then explain possibilities, limitations, trends, and clinician questions — with urgent red-flag routing and no diagnosis.
- User story: "As an owner with a new lab report, I want a structured interpretation tied to my report's printed ranges so that I can prepare informed questions for my clinician."
- Boundary: not whole-health synthesis (`WF-35` review mode), not meal planning (`WF-36`), not visit brief (`WF-38`). Not a substitute for the laboratory or emergency care.
- Routing: `interpret labs`, `CBC results`, `lipid panel`, `lab PDF`; negative — `full health review` → `WF-35`; `/health-review labs`.
- Execution modes: `interactive`, local-only; no browser required default.
- Success criterion: 100% extracted values match report OCR/extract pass; reference ranges from report text, not invented; D1 cites for clinical threshold context only.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `mode` | enum | yes | fixed `labs` | INTERNAL | `labs` |
| `lab_report` | file | yes | PDF/PNG; no macros (`PI-CRIT`) | PHI | — |
| `prior_reports` | list\<file\> | no | for trends | PHI | [] |
| `collection_date` | date | no | override if OCR unclear | PHI | from report |
| `sex_age_context` | object | no | for printed range selection only | PHI | — |
| `ocr_confidence_min` | number | no | 0–1 | INTERNAL | 0.85 |

- Preconditions: local parser available; `pdf-reader` parked — use `doc.extract_text` local-first (`SH-TOOL-6`).
- Intensity: small often sufficient; medium adds D1 literature for flagged analytes.
- Budget: `max_invocations` 45 / `max_wall_clock_s` 1200 / `max_cost_units` 10.

#### 3. Data sources and knowledge bases
- **T4 primary:** the lab report (values, units, ranges, flags, dates, lab name).
- **D1 secondary:** guideline/lab interpretation context (PMID, NICE, society guidance) — never overrides printed range.
- TTL: report content immutable until hash changes; guideline queries 24h.
- Cache: `fresh-only`; PHI run-dir only (`SH-CACHE-7`).
- Deviations: none.

#### 4. Tool chain and mechanisms
- Required: `doc.extract_text`, `image.analyze` (OCR fallback), `llm.extract`, `web.search.scholar`, `fs.write`.
- Optional: parked `pdf-reader` MCP on-demand if owner approves activation — visible fallback (`SH-TOOL-3`).
- Compose: `health-review` `labs` mode owns sequencing; extraction leaf deterministic-first.
- Mechanism: hash report → extract table → validate units/ranges → trend vs priors → flag abnormal → narrative with limitations → urgent flags → clinician questions.

#### 5. Internal data structures / schemas
- `LabAnalyteRow`: `{analyte, value, unit, ref_low, ref_high, flag_printed, page, bbox?, ocr_confidence, extraction_hash}`.
- `LabPanel`: `{lab_name, collection_at, rows[], report_hash, provenance: OWNER-T4}`.
- `InterpretationBlock`: `{analyte, status: high|low|normal|uncertain, possibilities[], limitations[], trend?, citations[], not_diagnosis: true}`.
- `UrgentFlag`: `{code, rationale, action: seek_emergency|contact_clinician_soon, not_diagnosis: true}`.
- Artifacts: `lab-interpretation_{YYYY-MM-DD}.md`, `lab-interpretation_{YYYY-MM-DD}.json`, `lab-extract_{YYYY-MM-DD}.json`.
- Example row: `{"analyte": "HbA1c", "value": 6.4, "unit": "%", "ref_high": 5.6, "page": 2, "ocr_confidence": 0.93}`

#### 6. Step-by-step execution flow
- `hash_input` → `extract_panel` → `validate_rows` (`SH-VAL-6`) → `trend_compare` → `urgent_screen` → `context_literature` (D1, optional) → `synthesize_interpretation` → `owner_review`.
- Approval: R2; urgent banner does not auto-call services.
- Resume: re-extract if report hash changes.

#### 7. Output format and UX behavior
- Sections: Panel table (values from report) → Flagged analytes → Trends → Possibilities & limitations → Questions for clinician → Urgent flags → Disclaimers.
- Export: `lab-interpretation_{YYYY-MM-DD}.md`; English technical default.
- OCR uncertainty: footnote per row below confidence threshold.
- Deviations: none.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ` (PI-CRIT PDF), `SH-SEC-PHI`, `SH-SEC-REDACT`.
- Disclaimers: `DISC-MED-1`, `DISC-NOT-A-CLINICIAN`.
- Gates: `extract_match_report`, `no_invented_ranges`, `citation_coverage` (for clinical context claims), `urgent_flag_routing`.
- Failure table:

| Scenario | Error class | Behavior | Message |
|---|---|---|---|
| OCR below threshold | VALIDATION | Mark `uncertain` | "Value uncertain — confirm on printed report." |
| Macro detected in PDF | POLICY | DENY | "Macro-blocked; provide export without macros." |
| Invented reference range | VALIDATION | BLOCK | "Range not on report; not inferred." |
| Critical value pattern | POLICY | Urgent banner | "Seek urgent clinical care per local guidance." |

- Tests: happy CBC, OCR degrade, critical flag banner, macro block.
- Deviations: none.

---

### WF-38 — Visit prep assistant

<!-- PREAMBLE -->
**Source ref:** `user-spec:WF-38` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 5 · **Domain family:** clinical-health  
**Risk tier:** R2 (factors: `medical_advice`, `personal_health_data`, `browser_authenticated` if portal) · **Engine:** simple · **Default intensity:** small  
**Reconciliation:** action `MERGE_ALIAS` · canonical owner `health-review` `visit-prep` mode · existing assets `health-review`, evidence-ledger question-list pattern · duplicate surfaces avoided `separate visit-prep skill`, `silent patient-portal login`, `sending records` · delta `Turn owner facts into prioritized questions/timeline; no diagnosis; portal upload/send remains R3 and explicit profile (a) only` · evidence `REUSE-MCP-MATRIX row WF-38; RISK WF-38; global browser policy`

#### 1. Purpose and user story
- Job-to-be-done: compile a one-page clinician briefing from health data and prior workflow outputs — timeline, medications, allergies, concerns, questions, and source distinctions — for owner review before any share; no portal send.
- User story: "As a patient preparing for an appointment, I want a concise briefing I can verify so that I use my visit time effectively with my clinician."
- Boundary: not diagnosis (`WF-35`/`WF-37`), not automated portal upload (R3), not emergency triage.
- Routing: `doctor visit prep`, `appointment briefing`, `questions for clinician`; negative — `interpret labs only` → `WF-37`; `/health-review visit-prep`.
- Execution modes: `interactive`, `owner-present-only`; portal browser only with explicit profile choice.
- Success criterion: one-page brief with owner-approved revision hash; send/upload not performed.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `mode` | enum | yes | fixed `visit-prep` | INTERNAL | `visit-prep` |
| `appointment_date` | date | yes | | INTERNAL | — |
| `visit_type` | string | no | specialist/GP/follow-up | INTERNAL | — |
| `health_bundle_path` | dir | yes | | PHI | — |
| `prior_artifacts` | list\<file\> | no | WF-35/37 outputs | PHI | [] |
| `concerns` | list\<string\> | no | owner priorities | PHI | [] |
| `portal_fetch` | bool | no | if true → browser + profile gate | PHI | false |
| `browser_profile` | enum | if portal | `a`/`b`/`c` | INTERNAL | `b` |

- Budget: `max_invocations` 35 / `max_wall_clock_s` 900 / `max_cost_units` 6.

#### 3. Data sources and knowledge bases
- **T4:** owner bundle, meds, allergies, prior workflow artifacts (hash-verified).
- **D1 (optional):** condition-specific question frameworks from guidelines — cited, not diagnostic.
- Cache: `fresh-only`; no PHI cache.
- Deviations: none.

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `llm.summarize`, `llm.extract`, `fs.write`.
- Optional: `browser.session` for portal read — owner-present, profile recorded (`SH-SEC-BROWSER`); never `browser.act` send.
- MERGE into `health-review` `visit-prep` mode.

#### 5. Internal data structures / schemas
- `VisitBrief`: `{appointment_date, timeline[], medications[], allergies[], concerns[], questions_prioritized[], source_map: OwnerFact|WorkflowArtifact|Guideline, artifact_hashes[]}`.
- Artifacts: `visit-brief_{YYYY-MM-DD}.md` (one page target), `visit-brief_{YYYY-MM-DD}.json`.
- Example: `{"questions_prioritized": [{"q": "Ask about repeat lipid panel timing", "source": "WF-37 artifact hash ab12..."}]}`

#### 6. Step-by-step execution flow
- `load_bundle` → `ingest_prior_outputs` → `build_timeline` → `prioritize_questions` → `render_one_pager` → `owner_review` → **stop** (no portal send).
- R3 separate action if owner explicitly requests upload after reviewing (`SH-RUN-12`).
- Approval: `human_required` with `final_revision_covered` before any share (`SH-VER-1`).

#### 7. Output format and UX behavior
- Single-page brief: Header (appointment) → Timeline → Meds/allergies → Concerns → Top questions → Source footnotes.
- Export: `visit-brief_{YYYY-MM-DD}.md`; Romanian default for clinician-facing owner copy.
- Footer: "Owner reviewed: pending/approved" + revision hash.
- Deviations: none.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-PHI`, `SH-SEC-BROWSER` (if portal), `SH-SEC-INJ`, `SH-SEC-REDACT`.
- Disclaimers: `DISC-MED-1`, `DISC-NOT-A-CLINICIAN`.
- Gates: `no_portal_send`, `owner_revision_hash`, `one_page_limit`.
- Failure: portal send attempt → POLICY DENY R3.
- Tests: happy brief, portal read degrade, send blocked.
- Deviations: none.

---

### WF-39 — Fitness coach

<!-- PREAMBLE -->
**Source ref:** `user-spec:WF-39` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 5 · **Domain family:** clinical-health  
**Risk tier:** R2 (factors: `medical_advice`, `personal_health_data`) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `MERGE_ALIAS` · canonical owner `health-review` `fitness` mode · existing assets `health-review`, evidence-ledger, telemetry intake · duplicate surfaces avoided `standalone fitness-coach profile`, `medical clearance claims` · delta `Separate telemetry, guideline evidence, and suggestions; screen injury/condition red flags; retain P4 locally` · evidence `REUSE-MCP-MATRIX row WF-39; RISK WF-39/D9`

#### 1. Purpose and user story
- Job-to-be-done: build a phased FITT-VP exercise plan from baseline, goals, equipment, schedule, injuries, and conditions using ACSM/WHO/exercise guidelines — with progression, deload, tracking, safety caveats, and medical clearance prompts where appropriate.
- User story: "As an owner with known constraints, I want a structured, source-backed activity plan so that I can discuss suitability with my clinician before starting."
- Boundary: not physical therapy prescription, not cardiac rehab protocol, not diagnosis. MERGE into `health-review` `fitness` mode.
- Routing: `workout plan`, `FITT plan`, `exercise schedule`; negative — `sleep plan` → `WF-40`; `/health-review fitness`.
- Execution modes: `interactive`, local-only telemetry.
- Success criterion: FITT-VP table with guideline cites; injury/condition screens documented; no "cleared for exercise" medical claims.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `mode` | enum | yes | fixed `fitness` | INTERNAL | `fitness` |
| `baseline` | object | yes | activity level, experience | PHI | — |
| `goals` | list\<string\> | yes | | INTERNAL | — |
| `equipment` | list\<string\> | no | | INTERNAL | [] |
| `schedule` | object | yes | days/week, minutes | INTERNAL | — |
| `injuries` | list\<string\> | no | | PHI | [] |
| `conditions` | list\<string\> | no | cardiac, metabolic, etc. | PHI | [] |
| `wearable_export` | file | no | T4 telemetry | PHI | — |

- Budget: `max_invocations` 50 / `max_wall_clock_s` 1500 / `max_cost_units` 10.

#### 3. Data sources and knowledge bases
- **T0/T1:** WHO physical activity guidelines; ACSM position stands; CDC activity recommendations; peer-reviewed exercise prescription references (PMID).
- **T4:** owner baseline, wearable exports (device estimates labeled).
- `sources.min_independent`: 2 for load-bearing intensity recommendations.
- TTL: guidelines 7d; wearable session-only.
- Deviations: none.

#### 4. Tool chain and mechanisms
- `fs.read` → screen red flags → `guideline_fetch` → `plan_fitt_vp` → `progression_deload` → `owner_review`.
- MERGE `health-review` `fitness` mode; no standalone fitness skill.

#### 5. Internal data structures / schemas
- `FITTPlan`: `{phase, frequency, intensity, time, type, volume, progression[], deload_weeks[], tracking_metrics[], clearance_caveats[], citations[]}`.
- `RedFlagScreen`: `{trigger, action: escalate_clinician|modify_plan, source}`.
- Artifacts: `fitness-plan_{YYYY-MM-DD}.md`, `fitness-plan_{YYYY-MM-DD}.json`.

#### 6. Step-by-step execution flow
- Screen cardiac/acute injury → if fail, escalate → else compose plan → validate cites → owner approval.
- No claim of medical clearance.

#### 7. Output format and UX behavior
- Phased plan table, tracking sheet, clearance caveats ("Confirm with clinician if…"), disclaimers.
- Export: `fitness-plan_{YYYY-MM-DD}.md`; English default.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-PHI`, `SH-SEC-REDACT`.
- Disclaimers: `DISC-MED-1`, `DISC-NOT-A-CLINICIAN`.
- Gates: `red_flag_screen`, `no_medical_clearance_claim`, `citation_coverage`.
- Failure: high-risk condition without clearance note → BLOCK until caveat added.
- Tests: happy plan, red-flag escalate, wearable labeled estimate.
- Deviations: none.

---

### WF-40 — Sleep & recovery coach

<!-- PREAMBLE -->
**Source ref:** `user-spec:WF-40` · **Status:** planned · **Version:** 0.1.0  
**Part (batch):** 5 · **Domain family:** clinical-health  
**Risk tier:** R2 (factors: `medical_advice`, `personal_health_data`) · **Engine:** simple · **Default intensity:** medium  
**Reconciliation:** action `MERGE_ALIAS` · canonical owner `health-review` `sleep` mode · existing assets `health-review`, evidence-ledger, telemetry intake · duplicate surfaces avoided `standalone sleep profile/skill`, `diagnosis or treatment claims` · delta `Record export time, distinguish device estimates from clinical facts, flag suspected disorder for clinician review, keep P4 local` · evidence `REUSE-MCP-MATRIX row WF-40; RISK WF-40/D9`

#### 1. Purpose and user story
- Job-to-be-done: analyze schedule, environment, habits, and wearable exports against AASM/CDC/sleep/circadian sources — identifying patterns, interventions, tracking/follow-up, distinguishing wearable estimates, and flagging suspected disorders for clinician discussion (not diagnosis).
- User story: "As an owner improving sleep, I want personalized hygiene and schedule suggestions grounded in official guidance so that I can discuss persistent problems with a sleep clinician."
- Boundary: not sleep apnea diagnosis, not CPAP prescription, not medication sleep aids dosing. MERGE `health-review` `sleep` mode.
- Routing: `sleep coach`, `recovery plan`, `circadian habits`, `wearable sleep data`; negative — `fitness plan` → `WF-39`; `/health-review sleep`.
- Execution modes: `interactive`, local-only.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `mode` | enum | yes | fixed `sleep` | INTERNAL | `sleep` |
| `schedule` | object | yes | bed/wake targets, shifts | PHI | — |
| `environment` | object | no | light, noise, temperature | INTERNAL | {} |
| `habits` | object | no | caffeine, alcohol, screens | PHI | {} |
| `wearable_export` | file | no | CSV/JSON export | PHI | — |
| `wearable_export_at` | datetime | if wearable | required provenance | INTERNAL | — |
| `suspected_disorder` | bool | no | owner concern | PHI | false |

- Budget: `max_invocations` 50 / `max_wall_clock_s` 1500 / `max_cost_units` 10.

#### 3. Data sources and knowledge bases
- **T0/T1:** AASM clinical practice guidelines; CDC sleep hygiene; NIH/NHLBI sleep health; circadian research via PMID.
- **T4:** wearable staging (labeled `DEVICE-ESTIMATE`, not polysomnography).
- TTL: wearable analysis session-only; guidelines 7d.
- Deviations: none.

#### 4. Tool chain and mechanisms
- Ingest wearable with `export_at` → hygiene/circadian pattern extract → guideline-backed interventions → disorder suspicion flags → tracking plan → owner review.
- MERGE `health-review` `sleep` mode.

#### 5. Internal data structures / schemas
- `SleepProfile`: `{schedule, environment, habits, wearable_summary?, estimate_disclaimer: true}`.
- `Intervention`: `{topic, suggestion, evidence_citation, strength}`.
- `DisorderFlag`: `{pattern, discuss_with_clinician, not_diagnosis: true}`.
- Artifacts: `sleep-plan_{YYYY-MM-DD}.md`, `sleep-tracking_{YYYY-MM-DD}.json`.

#### 6. Step-by-step execution flow
- `parse_wearable` → label estimates → `pattern_find` → `interventions` → `disorder_screen` → `tracking_setup` → `owner_review`.

#### 7. Output format and UX behavior
- Sections: Current patterns → Wearable note (estimate) → Interventions → Tracking → Disorder discussion prompts → Disclaimers.
- Export: `sleep-plan_{YYYY-MM-DD}.md`.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-PHI`, `SH-SEC-REDACT`.
- Disclaimers: `DISC-MED-1`, `DISC-NOT-A-CLINICIAN`.
- Gates: `wearable_estimate_label`, `no_sleep_diagnosis`, `disorder_flag_clinician_route`.
- Failure: treating wearable as clinical fact → VALIDATION BLOCK.
- Tests: happy plan, wearable disclaimer, disorder flag text.
- Deviations: none.

---

## Part 05 verification summary

| Check | Result |
|---|---|
| Workflow count | **8** (`WF-31`, `WF-34`, `WF-35`, `WF-36`, `WF-37`, `WF-38`, `WF-39`, `WF-40`) |
| Heading count | **64** (8 workflows × 8 §21.2 headings) |
| Heading lint (`SH-TMPL-7`) | PASS — exact strings, order per workflow |
| Global ID coverage | PASS — each `WF-NN` once in Part 05; no extras |
| `source_ref` | PASS — all `user-spec:WF-NN` |
| Reconciliation | PASS — fields copied from reuse matrix rows |
| Health owner unity | PASS — one `health-review` owner; WF-36–40 modes/compose, not duplicate skills |
| P4 local-only default | PASS — WF-35–40 `execution.locality: local-only`; `SH-CACHE-7` cited |
| Non-clinical boundaries | PASS — no diagnosis/prescribing/emergency substitution documented |
| Blockers | **None** for documentation draft |

**Output path:** `C:\Users\Prekzursil\.agents\PERPLEXITY-WORKFLOWS-PART-05-PERSONAL-HEALTH_2026-08-29.md`

**NOT-CHECKED (implementation):** live MCP health for `pdf-reader` (parked), maps/transit adapters, `data.property_listings`, on-demand router shadow mode — do not block this design artifact.

---

*End of Part 05. Cross-cutting contracts remain in Part 00; cite `SH-*` IDs rather than restating.*
