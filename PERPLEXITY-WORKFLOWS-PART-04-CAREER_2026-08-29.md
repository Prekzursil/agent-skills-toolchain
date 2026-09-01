# Perplexity-Class Workflow Suite — Part 04: Career

Date: 29.08.2026
Status: DESIGN — documentation only; no skill, MCP, router, script, registry, or commit changes
Scope: `WF-25`, `WF-26`, `WF-27`, `WF-28`, `WF-29`, `WF-30`, `WF-32`, `WF-33` (exactly these eight; `WF-31` and `WF-34` belong in Part 05)
Inherits: `PERPLEXITY-WORKFLOWS-PART-00-SHARED_2026-08-29.md` by shared-rule ID (`SH-TMPL-2`)
Reconciliation SSOT: `PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md`
Source-risk SSOT: `PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md` domain D5 (jobs/careers) and D8 for `WF-28`
Catalog titles: owner's written specification (`SH-SRC-0`); UI corroboration in `PERPLEXITY-WORKFLOWS-SOURCE-CROSSCHECK_2026-08-29.md`

---

## 0. Career-family invariants (Part-04-SSOT)

These rules are domain-specific. They do not restate Part 00. Every workflow in this part **MUST** inherit them.

1. **One identity record.** `skill:.agents/skills/cv-studio` owns career identity. The only profile is `profile.yaml` (JSON Resume superset). `x_master` is the only achievement bank. `x_metrics` is the only verified-number source. `x_targets` holds saved job descriptions. Do **not** create a second profile, resume store, cover-letter store, LinkedIn-copy store, interview biography, or story bank (`SH-DUP-4`).
2. **Zero fabrication.** Any employment fact, degree, date, tool, or metric in an output **MUST** trace to `profile.yaml` / `x_master` / `x_metrics` or to a retrieved, hashed source. Unsourced figures are dropped or flagged; they are never invented. `cvstudio.py validate` is the mechanical lint for CV/letter surfaces.
3. **Submitted CV vs portfolio.** The ATS-submitted artifact remains selectable-text, single-column, tagged PDF (RenderCV). Visual/portfolio CV remains a separate `visual` path (`design-studio` / JSON Resume HTML). The designed artifact **MUST NOT** replace the ATS artifact.
4. **`resume` is not `resume-session`.** `source-command-resume-session` recovers agent session context. It **MUST NOT** alias to `WF-33` and **MUST NOT** share schema or storage with `profile.yaml`.
5. **Recovered LinkedIn MCP boundary.** Tracked source `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\linkedin-mcp\` is **RECOVERABLE/HEALTHY-SOURCE**: 82 offline tests passed; **runtime registration, app/auth, stdio live integration, and live LinkedIn API remain `NOT-CHECKED`**. Tools cover self-serve OIDC identity and posting/deleting on the authenticated owner's **own feed** only. Alumni search, Recruiter, Talent, Sales Navigator, organization, and advertising APIs are **not built**. No workflow in this part may treat that MCP as a discovery, alumni, or job-search provider.
6. **No auto-apply / auto-outreach / auto-post.** Draft, rank, and verify only. Submit, message, InMail, Handshake apply, and LinkedIn upload/post are `external_action` → **R3**, owner-present, out of scope for these eight (`SH-TOOL-5`, `BR-4`).
7. **No bulk dossier or ToS scrape.** Platform UIs (LinkedIn, Indeed, Handshake) are T3 discovery indexes under ToS. Prefer official APIs if ever present (currently **absent/deferred** from the 40-record registry). Otherwise owner-present browser + `SH-SEC-BROWSER` BR-1. **MUST NOT** use `web.crawl` or parked `apify`/`scrapegraph` against those hosts. Cache URL + listing/requisition ID + `content_hash` + `retrieved_at` only — **no full HTML dumps** of ToS-restricted pages (`SH-CACHE-7` for `PII`).
8. **P2 handling.** Owner CV/letters/photos: classification `PII` (RISK P2/P6), run directory only, redacted logs (`SH-SEC-REDACT`). Third-party alumni: minimize fields; no stalking dossier; no Basic Memory write of contact lists (`memory.capture: none` on `WF-32`). Discriminatory filters on protected characteristics are **POLICY** denials.
9. **Claim-type TTLs (tighten D5 vs §9.2 medium 24 h where stated):** vacancy still open / career-page body / board card = **12 h**; scholarship deadline still open = **24 h**; official labor-statistics table = **30 days or until next labeled release**. Serving a cached listing as “still open” past TTL is `STALE` / `FAILED-TO-RUN`, never green (`SH-VAL-1`).
10. **Disclaimer IDs.** `safety/disclaimers.yaml` does not yet exist on disk. Implementation **MUST** add and render `DISC-CAREER-1` (listings stale; not an offer of employment/admission/funding) and `DISC-IMAGE-SYNTHETIC-1` (AI-edited likeness; not an identity document). Until that file exists, the disclaimer gate is `NOT-CHECKED` — not a silent pass.

---

### WF-25 — Job finder

**Source ref:** `user-spec:WF-25` · **Status:** planned · **Version:** 0.1.0
**Part (batch):** 4 · **Domain family:** careers-housing
**Risk tier:** R1 (factors: none at rest; `browser_authenticated` if a logged-in board session is used → R2; `external_action` never executed here) · **Engine:** simple · **Default intensity:** medium
**Reconciliation:** action `UPGRADE` · canonical owner `skill:.agents/skills/cv-studio` (jobs mode)
· existing assets `skill:.agents/skills/cv-studio` (profile/tailor foundation); `skill:.agents/skills/deep-research`; `skill:.agents/skills/browser-rail`; MCP `firecrawl` / `playwright` / `chrome-devtools` (Cursor-active); `tavily` (plugin-managed); LinkedIn/Indeed/Handshake providers **absent/deferred**
· duplicate surfaces avoided `a new job-profile schema`; `one finder skill per board`; `bulk LinkedIn scrape`; `application submission`
· delta `Use profile.yaml goals/skills, verify each vacancy on the employer career page, record requisition/12h TTL, and keep platform browsing consent-gated.`
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-25`; `.agents/skills/cv-studio/SKILL.md`; `.agents/PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md` D5/WF-25; REG/CUR/PARK

#### 1. Purpose and user story
- The owner supplies (or already has) a cv-studio profile plus target role, location, and hard constraints, and receives a ranked shortlist of currently open jobs/internships with fit score, employer career-page link, requisition/date, match reasons, gaps, and unsent outreach notes — never a submitted application.
- User story: "As a job seeker, I want vacancies matched to my verified profile and constraints so that I can choose where to apply myself."
- Boundary: **NOT** for applying or messaging (`external_action` / R3, owner-only). **NOT** housing (`WF-31`). **NOT** resume rewriting (`WF-33`). **NOT** cover letters (`WF-27`). **NOT** alumni (`WF-32`). **NOT** career-path exploration without vacancies (`WF-30`).
- Routing: triggers `find jobs`, `job finder`, `internship listings`, `match me to openings`, `search Indeed/LinkedIn jobs`; negative `apply for me` / `submit this application` (no workflow — R3 owner action), `edit my CV` → `WF-33`, `write a cover letter` → `WF-27`, `find alumni` → `WF-32`, `internship housing` → `WF-31`; aliases `/job-finder`, `/jobs`.
- Execution modes: `interactive`; `owner-present-only` when ToS-restricted boards or authenticated Handshake/LinkedIn UI are required; `background`/`scheduled` **MAY** re-fetch **public employer career pages** already in the shortlist — they **MUST NOT** drive logged-in boards or apply.
- Success criterion: every listed “open” row has a career-page (or recorded `UNVERIFIED-STALE`) SourceRecord within 12 h, a requisition or canonical URL, a fit score that does not use protected-class features, and zero apply/send side effects.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `profile_path` | file | yes | `accept_mime: [application/yaml, text/yaml]`; must be cv-studio `profile.yaml` | PII | active project's `profile.yaml` |
| `target_role` | string | no | `max_len: 200`; else `profile.yaml` goals/`x_targets` | INTERNAL | from profile |
| `locations` | list\<string\> | no | `max_items: 12`; city/region/country or `remote` | INTERNAL | from profile |
| `constraints` | object | no | seniority, work-authorization statement, on-site/hybrid/remote, employment type; **no protected-class filters** | INTERNAL | `{}` |
| `boards` | list\<enum\> | no | `values: [linkedin, indeed, handshake, other]`; discovery only | INTERNAL | `[linkedin, indeed]` |
| `employer_allowlist` | list\<string\> | no | legal names / career-page hosts | PUBLIC | `[]` |
| `max_listings` | integer | no | `min: 1`, `max: 40` | INTERNAL | intensity `sources_target` |
| `browser_profile` | enum | cond | `a\|b\|c`; required before any `browser.*` (`BR-1`) | INTERNAL | `b` |

- Preconditions: `free_ram_gb_min` 8 if `browser.*` else 4; `capability_healthy: web.search` and `web.fetch`; `profile_path` exists and `cvstudio.py validate` is callable (else degrade: treat YAML as T4 text, mark `zero_fab: NOT-CHECKED`); no job-board API credential required (adapters absent/deferred).
- Intensity profile — numbers only; preset meanings are fixed by §14.1:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 3 | 6 | 2 | 3 | 1 | 0 |
| medium | 6 | 14 | 5 | 3 | 2 | 0 |
| high | 12 | 30 | 12 | 5 | 2 | 0 |
| limitless | null | null | all load-bearing | null | 3 | 0 |

- Budget: small `48 / 900 / 8`; medium `120 / 1800 / 22`; high `220 / 2700 / 40`; limitless same hard caps as high (breaker still applies, `SH-INT-3`).
- Deviations from shared input/intensity defaults: vacancy-open freshness is **12 h** (RISK D5), tighter than §9.2 `medium` 24 h; `max_listings` caps `foreach` so ToS boards cannot be bulk-scraped.

#### 3. Data sources and knowledge bases
- Canonical authorities: **employer/institution career page** (T0 for that vacancy: posting URL, requisition ID, retrieved_at). Official university Handshake **when it is that institution's system** (T1 + job ID). Occupational datasets are **not** vacancy proof (use `WF-30`). Boards (LinkedIn Jobs, Indeed, Handshake-as-index) are **T3 convenience indexes** — confirm on the career page when it exists. Independence **fails** if a board card and an aggregator mirror the same posting (`SH-SRC` independence analogue in RISK §5.1).
- `sources.min_tier` T3 for discovery rows (must be labeled T3); load-bearing “still open” requires T0 career-page fetch or status `UNVERIFIED-STALE`. `min_independent` 1 when T0 career page was read; 2 if only T3 boards exist. `recency_max_days` 1, with claim-type TTL **12 h** via `cache.ttl_override_s: 43200`.
- Domain data: `data.job_postings` — optional official/licensed job APIs. **Current estate: LinkedIn/Indeed/Handshake MCP/API adapters absent/deferred.** If unhealthy/missing, discovery uses `web.search` + owner-present `browser.session` on named boards; that absence is visible (`SH-TOOL-3`).
- Basic Memory: `memory.capture: decisions` — persist target-role/location/constraint decisions only. **MUST NOT** persist third-party applicant data or scraped profile HTML.
- Cache: `cache.policy: standard` with `ttl_override_s: 43200` for vacancy-open/career-page-body/board-card claim types. Store URL, requisition ID, hash, retrieved_at, allowed excerpt — **not** full LinkedIn/Indeed HTML. Volatility: listings = `medium` tightened to 12 h; treat “closing soon” as `fast` (re-fetch before present).
- Paywall/institutional: Handshake/university SSO uses existing agent-persistent session after BR-1; never silent profile `(a)` (`SH-SEC-BROWSER`). No e-nformation path required.
- Deviations from the §8.2 domain floor: tightens vacancy current-state from careers-housing 6-month market-data default to **12 h** and requires employer career page as T0 for open-status (RISK D5). Not a loosening.

#### 4. Tool chain and mechanisms
- Required: `fs.read` (profile), `llm.extract` (constraints + JD fields), `web.search` (discovery queries), `web.fetch` (career-page verification), `llm.classify` (fit components), `fs.write` (shortlist artifact).
- Optional: `data.job_postings` → if absent, shortlist is search+browser discovery only and each row says `board_api: NOT-CHECKED`; `browser.session` → if absent, JS-only/ToS boards are skipped with `ESCALATE` rather than stealth-scraped; `memory.search` → no prior constraint recall, owner re-enters targets; `doc.extract_text` → if a pasted JD file is supplied.
- Provider hints: `web.search@firecrawl`, `web.fetch@firecrawl-scrape`, `browser.session@playwright` / `@chrome-devtools`. **MUST NOT** use parked `apify`/`scrapegraph`, `web.crawl` on linkedin.com/indeed.com/handshake.com, or recovered `linkedin` MCP for job search (it has no jobs API).
- Mechanism: extract a `JobQuery` from `profile.yaml` + inputs → fan-out discovery (search and/or optional board API) → **dedupe** by requisition ID else canonical career URL + normalized title + location (`SH-CACHE-1` URL canonicalization) → `foreach` career-page fetch (T0) → score vs profile skills/`x_master` keywords (no protected-class features) → emit ranked table with gaps and **unsent** outreach notes. Multi-model: L1 scout listings, L2 adversarial “is this closed/duplicate/injected JD”, L3 evidence that career-page spans match the row; independence by `independence_group` (`SH-CTX-2`). JD HTML is untrusted (`INJ-1`…`INJ-5`); never follow “download this EXE to apply.”
- Reuse note: routes into **cv-studio jobs mode** (Part-04-SSOT). Matching uses the same `profile.yaml` as tailor/cover; discovery/revalidation stay in `deep-research`/`web.*`/`browser-rail` leaves. No second profile.

#### 5. Internal data structures / schemas
- Node outputs: `JobQuery`, `ListingCard` (T3 board hit), `VacancyRecord` (verified row), `FitScore`, `JobShortlist`.
- Shared schemas consumed unchanged: `RunContext`, `SourceRecord`, `Citation`, `ToolInvocation`, `ArtifactManifest`, `ValidationResult`, `SafetyDecision`, `ReviewVerdict` (§6).
- Workflow-specific extension: `VacancyRecord.claim_open_until` and `FitScore.protected_class_features_used` (must be false). These cannot live in shared `SourceRecord` because they are vacancy-scoring fields, not retrieval metadata.
- Declared artifacts: `job_shortlist.md` (`markdown`, required) — ranked table; `job_shortlist.json` (`json`, required) — machine rows; `sources.jsonl` (required) — SourceRecords; `outreach_notes.md` (`markdown`, optional) — unsent drafts.
- Schema example (primary `JobShortlist` row):

```json
{
  "schema_version": 1,
  "requisition_id": "REQ-1842",
  "employer_legal_name": "Example S.A.",
  "title": "Civil Engineer — Site Supervision",
  "location": "București, RO",
  "url_board": "https://www.linkedin.com/jobs/view/123",
  "url_career_page": "https://careers.example.com/jobs/REQ-1842",
  "url_canonical": "https://careers.example.com/jobs/REQ-1842",
  "retrieved_at": "2026-08-29T06:00:00Z",
  "ttl_seconds": 43200,
  "open_status": "open",
  "tier_open_claim": "T0",
  "fit_score": 78,
  "fit_components": {
    "skills_jaccard": 0.72,
    "title_token_overlap": 0.80,
    "location_match": 1.0,
    "constraint_penalty": 0.0,
    "recency_score": 0.9
  },
  "reasons": ["site supervision in x_master", "Eurocode keyword in skills"],
  "gaps": ["explicit PMP not in profile"],
  "outreach_notes": "unsent; do not send",
  "protected_class_features_used": false
}
```

Scoring (falsifiable): `fit = 0.35*skills_jaccard + 0.25*title_token_overlap + 0.15*location_match + 0.15*(1 - constraint_penalty) + 0.10*recency_score`. Hard constraint failure → `constraint_penalty = 1` and row tagged `ineligible` (still listed if the owner asked to see them).

#### 6. Step-by-step execution flow
- Engine: simple — node set known at authoring time; bounded `foreach` over listings, no adaptive DAG.
- Lifecycle phases used: `discover`, `recall`, `execute`, `spec-review`, `quality-review`, `acceptance`, `capture` (retrieval/report class, `SH-LIFE-4`).
- Numbered walkthrough:
  1. `load_profile` (discover, tool, `fs.read`) → read `profile.yaml` → `ProfileSnapshot`
  2. `validate_zero_fab` (discover, gate, cv-studio validate) → lint errors/warnings → `ValidationResult`
  3. `build_query` (discover, llm, `llm.extract`) → `JobQuery` from profile + inputs
  4. `recall_constraints` (recall, tool, `memory.search`) → prior target-role decisions (untrusted)
  5. `preview_gate` (discover, gate) → distribution preview (`SH-INT-5`); BR-1 if browser will run
  6. `discover_listings` (execute, fanout, `web.search` / optional `data.job_postings`) → `ListingCard[]`
  7. `dedupe_listings` (execute, tool, none/local) → unique by requisition or canonical URL
  8. `verify_career_page` (execute, foreach, `web.fetch`) → `VacancyRecord` + SourceRecord T0 or `UNVERIFIED-STALE`
  9. `browser_board` (execute, tool, `browser.session`) → only when fetch failed and owner chose a profile; **no `browser.act` apply**
  10. `score_fit` (execute, llm, `llm.extract`) → `FitScore` vs profile skills/`x_master`
  11. `adversarial_closed_dup` (execute, llm, `llm.judge`) → advisory closed/duplicate/injection flags
  12. `spec_review` (spec-review, gate, deterministic) → TTL, T0 open-claim, no-apply invariant
  13. `quality_review` (quality-review, llm, `llm.judge`) → advisory ranking sanity
  14. `acceptance` (acceptance, gate, human) → owner sees shortlist; **does not** send applications
  15. `export_shortlist` (capture, export, `fs.write`) → artifacts + sidecar manifest
- Branches: skip `browser_board` when all rows have T0 career pages; if a board is required and BR-1 is refused, `ESCALATE` those rows rather than scrape. `foreach` join after verification. No re-research loop (simple engine; loops = 0).
- Artifact-emitting nodes: `load_profile`, `verify_career_page`, `export_shortlist`. Checkpoints: `node` granularity after `discover_listings` and after `verify_career_page` (`SH-RUN-7`).
- Approval points: `deterministic` (TTL, citation_coverage, provenance_chain, reconciliation_survey, no-external-apply); `human_required: 1` on final shortlist (R1); `panel_required: false` unless escalated to R2 by `browser_authenticated`. Blocking beyond shared gates: any `browser.act` toward Apply → `POLICY`; protected-class filter in constraints → `POLICY`.
- Resume behavior: reuse hashed `VacancyRecord`s still inside 12 h TTL; re-fetch open-status on resume if TTL expired (`SH-RUN-11`).

#### 7. Output format and UX behavior
- Deliverable over §16.1 skeleton: **Result** = ranked table (employer, title, location, fit, requisition, career-page URL, retrieved_at, open_status, reasons, gaps, outreach-notes-unsent). **Evidence** = numbered citations (`SH-SRC-9`) with tier labels (T0 career page vs T3 board). **Uncertainty** = stale/unverified rows, board incompleteness, JS pages skipped. **Next actions** = “apply yourself if you choose”; no send button.
- Export formats `md`, `json`, `xlsx` (`doc.render_table`) · destination `active_project_docs` · naming `job-shortlist_{YYYY-MM-DD}` · language `en` (set `ro` only if the owner requested Romanian work output).
- Progress: heartbeat on `discover_listings` and each `foreach` batch > 60 s (`SH-UX-3`). Preview names boards, browser profile, listing cap, and that apply is disabled.
- Citations/staleness: open-status past 12 h renders `STALE` in the table cell, not as open. Conflicts (board says open, career page 404) surface in Uncertainty (`SH-SRC-5`).
- Degradation UX: `data.job_postings` missing → `FALLBACK: board APIs NOT-CHECKED; discovery is web.search plus optional owner-present browser. Ranked list may be incomplete.` Browser missing → `ToS-restricted boards skipped; only public career pages and search snippets were used.`
- Deviations from §16 output/export defaults: extra `xlsx` table for the shortlist; outreach notes file is drafts-only and classified `PII`.

#### 8. Logging, validation, and safety
- Safety controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER` (when browser used), `SH-SEC-REDACT`, `SH-SEC-CRED`. JD/board HTML is PI-HIGH; apply-EXE links are PI-CRIT (`INJ-5` quarantine).
- Required disclaimers: `DISC-CAREER-1` (`SH-RISK-3`). Do not inline disclaimer prose.
- Risk factors: none at rest → R1; `browser_authenticated` → R2; `external_action` must not trigger. Data classes: owner profile `PII`; public postings `PUBLIC`; third-party applicant CVs **MUST NOT** be collected.
- Deterministic gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, `vacancy_ttl_fresh` (12 h), `zero_apply_side_effect`, `protected_class_filter_absent`, `career_page_t0_or_unverified`.
- Validation: `JobShortlist` schema; `fit_score` in 0–100; `protected_class_features_used == false`; URL SSRF pipeline on every fetch (`SH-VAL-5`, `SH-SEC-SSRF`).
- Failure and degradation table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Career page 404 after board hit | `NOT_FOUND` | Row kept as `UNVERIFIED-STALE` / closed | `Employer career page not found; not marked open.` |
| Board rate limit | `RATE_LIMIT` | Backoff then fallback; no key rotation | `Board throttled; retrying then falling back to search.` |
| Missing LinkedIn session and no (a) | `POLICY` | Skip LinkedIn rows | `LinkedIn UI skipped: no browser profile choice for a logged-in session. I will not select (a).` |
| Constraints include protected class | `POLICY` | Fail validation | `Protected-characteristic filters are not allowed.` |
| Node tries Apply/submit | `POLICY` | Block; no retry | `This workflow does not apply. Apply remains an owner R3 action.` |
| RAM guard | `RESOURCE` | `FAILED_TO_RUN` | `Run refused: free RAM below precondition.` |
| Budget abort mid-foreach | `RESOURCE` | `FAILED_TO_RUN` | `FAILED_TO_RUN: budget breaker; partial shortlist not exported.` |

- Logging/provenance: extra metrics `listings_discovered`, `listings_deduped`, `career_page_verified_ratio`, `unverified_stale_count`, `browser_profile`. Ledger redacts PII excerpts.
- Tests: happy-path fixture `fixtures/WF-25/public_career_pages.json` (two T0 pages, one T3 board card deduped); degraded `fixtures/WF-25/no_board_api.json` (`data.job_postings` absent); safety-trigger `fixtures/WF-25/jd_injection_apply_exe.json` (quarantine + no navigate). Contract tests: `web.search`, `web.fetch`. Golden: `golden/WF-25/job-shortlist.md`. Beyond A1–A19: `zero_apply_side_effect` must PASS.
- Deviations from shared safety/validation defaults: 12 h vacancy TTL; explicit ban on recovered LinkedIn MCP as a job provider.

---

### WF-26 — Interview prep

**Source ref:** `user-spec:WF-26` · **Status:** planned · **Version:** 0.1.0
**Part (batch):** 4 · **Domain family:** careers-housing
**Risk tier:** R1 (factors: none at rest; `browser_authenticated` only if owner-present company portal is used → R2) · **Engine:** simple · **Default intensity:** medium
**Reconciliation:** action `UPGRADE` · canonical owner `skill:.agents/skills/cv-studio` (interview mode)
· existing assets `skill:.agents/skills/cv-studio`; `skill:.agents/skills/deep-research`; `skill:.agents/skills/humanizer` (optional); public company research via Firecrawl/Tavily; no interview MCP
· duplicate surfaces avoided `a separate interview-profile skill`; `a parallel biography store`; `fabricated biography/achievements`
· delta `Generate questions and proof points only from profile.yaml, x_master, and verified JD/company facts; flag gaps.`
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-26`; `.agents/skills/cv-studio/SKILL.md`; RISK D5/WF-26 zero-fabrication

#### 1. Purpose and user story
- The owner names a company, role, JD, and interview type and receives a prep pack: knowledge topics, technical and behavioral questions, cases/exercises, and sample-answer **frameworks** grounded only in verified achievements — not invented war stories.
- User story: "As a candidate, I want company-specific interview practice tied to my real achievements so that I can prepare without fabricating experience."
- Boundary: **NOT** live interview coaching as a certified coach. **NOT** STAR story bank creation (`WF-34` in Part 05). **NOT** job search (`WF-25`). **NOT** cover letter (`WF-27`). **NOT** resume edit (`WF-33`).
- Routing: triggers `interview prep`, `practice interview questions`, `case interview for`, `behavioral questions for`; negative `invent a story about` (refuse fabrication), `find jobs` → `WF-25`, `STAR stories` → `WF-34`, `cover letter` → `WF-27`; aliases `/interview-prep`, `/interview`.
- Execution modes: `interactive`; `background` allowed for **public** company/role research; `owner-present-only` if an authenticated careers portal is fetched; `scheduled` not useful (prep is per interview).
- Success criterion: every sample-answer framework cites `x_master`/`x_metrics` IDs or an explicit `GAP`; every company fact cites a retrieved SourceRecord; no fabricated metrics.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `profile_path` | file | yes | cv-studio `profile.yaml` | PII | active `profile.yaml` |
| `company_name` | string | yes | `max_len: 200` | INTERNAL | — |
| `role_title` | string | yes | `max_len: 200` | INTERNAL | — |
| `job_description` | file \| string | no | JD text or `x_targets` id | PII | from `x_targets` if id given |
| `interview_type` | enum | no | `values: [behavioral, technical, case, mixed, modeling, hiring-manager]` | INTERNAL | `mixed` |
| `company_urls` | list\<url\> | no | official careers/about/IR only after SSRF | PUBLIC | `[]` |
| `browser_profile` | enum | cond | `a\|b\|c` if browser used | INTERNAL | `b` |

- Preconditions: profile exists; `web.search`/`web.fetch` healthy for company materials; cv-studio validate callable or `zero_fab: NOT-CHECKED`.
- Intensity profile:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 3 | 6 | 2 | 3 | 1 | 0 |
| medium | 6 | 14 | 5 | 3 | 2 | 0 |
| high | 12 | 30 | 12 | 5 | 2 | 0 |
| limitless | null | null | all load-bearing | null | 3 | 0 |

- Budget: small `40 / 720 / 8`; medium `90 / 1500 / 18`; high `180 / 2400 / 32`; limitless capped at high hard limits.
- Deviations from shared input/intensity defaults: none for intensity; company “current” facts use `slow` 7-day TTL, not vacancy 12 h.

#### 3. Data sources and knowledge bases
- Canonical authorities: employer **official** about/careers/role pages and, if public, IR (T0/T2 for *what the company currently publishes*). Role JD is T4 if owner-supplied, T0 if fetched from the career page. Credible interview guides (recognized professional bodies, university career services) are T2 **for question-type pedagogy only**, never for the owner's biography. Forums/Glassdoor anecdotes are T4/T5 — hypothesis, not proof of process.
- `sources.min_tier` T2 for company facts used as load-bearing; T4 owner JD allowed. `min_independent` 2 for contested company claims (e.g. product set); 1 for a single official about page actually read. `recency_max_days` 7 for “current company” claims.
- Domain data: none required. Do not use `data.job_postings` as interview-process truth.
- Basic Memory: `memory.capture: none` by default (interview packs are run artifacts). `decisions` only if the owner asks to remember a scheduled interview date (no P2 third parties).
- Cache: `standard`; company pages volatility `slow` (7 d). JD file: until hash changes. **No** cache of authenticated portal HTML.
- Paywall/institutional: optional university career-guide PDFs via existing entitlement (`SH-SRC-8`); not required.
- Deviations from the §8.2 domain floor: company current-state 7 days (tighter than 6-month market-data default). Pedagogy sources labeled T2 and cannot corroborate owner achievements.

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `llm.extract` (JD competencies), `web.search`, `web.fetch`, `llm.rewrite` (question phrasing only), `fs.write`.
- Optional: `browser.session` for JS career pages → if absent, use fetched HTML only; `doc.extract_text` for JD PDF; `llm.judge` advisory coverage of competencies; `humanizer` only if the owner asks to polish spoken answers (still zero-fab).
- Provider hints: Firecrawl/Tavily for public pages. **MUST NOT** use recovered LinkedIn MCP to scrape employees or interviewers. **MUST NOT** use `browser.act` to book interviews.
- Mechanism: load profile + JD → extract competency list → fetch official company/role materials → generate knowledge topics and questions **mapped to competencies** → for each behavioral prompt, attach a **framework** (STAR/CAR skeleton) whose proof bullets are IDs into `x_master`/`x_metrics` or `GAP`. Technical/case items cite JD + official role text. Three voices: scout facts, adversarial fabrication hunt, evidence that every number is in `x_metrics`.
- Reuse note: **cv-studio interview mode** consumes the same profile/`x_targets` as tailor. `WF-34` (Part 05) may later render full STAR stories from the same `x_master`; this workflow does not create a second story store.

#### 5. Internal data structures / schemas
- Node outputs: `CompetencyMap`, `CompanyFactset`, `QuestionItem`, `AnswerFramework`, `InterviewPrepPack`.
- Shared schemas unchanged: §6 list as WF-25.
- Extension: `AnswerFramework.achievement_refs[]` pointing at `x_master` keys / `x_metrics` strings; `gap: true` when none exist. Shared Citation cannot encode profile-internal IDs.
- Declared artifacts: `interview-prep.md` (required); `questions.json` (required); `gap-list.md` (required).
- Schema example:

```json
{
  "schema_version": 1,
  "question_id": "Q-B-04",
  "kind": "behavioral",
  "prompt": "Tell me about a time you coordinated a multi-contractor site programme.",
  "competency": "site supervision",
  "framework": "STAR",
  "achievement_refs": ["Example SA|Site Engineer"],
  "metric_refs": [],
  "gap": false,
  "company_fact_citations": ["src_01K3"]
}
```

#### 6. Step-by-step execution flow
- Engine: simple.
- Lifecycle phases used: `discover`, `recall`, `execute`, `spec-review`, `quality-review`, `acceptance`, `capture`.
- Numbered walkthrough:
  1. `load_profile` (discover, tool, `fs.read`) → `ProfileSnapshot`
  2. `zero_fab_lint` (discover, gate) → cv-studio validate
  3. `parse_jd` (discover, llm, `llm.extract`) → competencies
  4. `recall` (recall, tool, `memory.search`) → skip if capture none
  5. `preview_gate` (discover, gate)
  6. `research_company` (execute, fanout, `web.search`/`web.fetch`) → `CompanyFactset`
  7. `optional_browser` (execute, tool, `browser.session`) → JS official pages only
  8. `build_questions` (execute, llm, `llm.rewrite`) → `QuestionItem[]`
  9. `bind_achievements` (execute, tool, local) → map to `x_master`/`x_metrics` or `GAP`
  10. `fabrication_hunt` (execute, llm, `llm.judge`) → advisory; deterministic gate drops unsourced metrics
  11. `spec_review` (spec-review, gate)
  12. `quality_review` (quality-review, llm, `llm.judge`)
  13. `acceptance` (acceptance, gate, human)
  14. `export_pack` (capture, export, `fs.write`)
- Branches: no JD → use `x_targets` or ASK-GATE (1–3 questions, `SH-TMPL` closest slot is inputs/preconditions). No browser if fetch succeeded.
- Artifact-emitting: `research_company`, `export_pack`. Checkpoint after `bind_achievements`.
- Approval: `deterministic` + `human_required: 1`; `panel_required: false` at R1. Blocking: any output metric not in `x_metrics`; any employer fact without SourceRecord.
- Resume: reuse `CompanyFactset` inside 7-day TTL; re-bind achievements if `profile.yaml` hash changed.

#### 7. Output format and UX behavior
- Result sections: company snapshot (cited), role/JD competencies, knowledge topics, technical questions, behavioral questions with STAR/CAR **frameworks** (not invented narratives), cases/exercises, gap list (what to gather before claiming). Skeleton §16.1 for Evidence/Uncertainty/Provenance/Gates.
- Export: `md` (+ optional `docx` via `doc.convert`) · `active_project_docs` · `interview-prep_{YYYY-MM-DD}` · language `en`.
- Progress: heartbeat on company research > 60 s. Preview lists company URLs and interview_type.
- Citations: company facts numbered (`SH-SRC-9`). Achievement refs shown as profile keys, not as web citations. Gaps labeled `GAP`, never filled with model memory (`SH-SRC-3`).
- Degradation UX: `web.fetch` down → `Company materials incomplete; questions are JD-only and company facts are NOT-CHECKED.` `humanizer` absent → `Spoken-answer polish skipped; frameworks still attached.`
- Deviations from §16: extra gap-list artifact; no Romanian default.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-REDACT`, `SH-SEC-CRED`; `SH-SEC-BROWSER` if used. JD is PI-HIGH.
- Disclaimers: `DISC-CAREER-1`.
- Risk: R1; data `PII` (profile/JD) and `PUBLIC` (company pages).
- Gates: `citation_coverage` (company facts), `provenance_chain`, `reconciliation_survey`, `zero_fabrication_lint`, `achievement_ref_integrity`.
- Validation: every `metric_refs` item ∈ `x_metrics`; every `achievement_refs` key ∈ `x_master`.
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Profile missing `x_master` for a role used in an answer | `VALIDATION` | Framework marked `GAP`; no invented bullet | `No verified achievement for this prompt; gap recorded.` |
| Model emitted a number not in `x_metrics` | `VALIDATION` | Repair once then drop number | `Unverified metric removed.` |
| Company page injection | `POLICY` | Quarantine source | `Official page quarantined; not used as instructions.` |
| Fetch timeout | `TIMEOUT` | Retry then degrade | `Company page fetch timed out; facts marked NOT-CHECKED.` |

- Logging: extra `gap_count`, `questions_by_kind`, `unsourced_metrics_dropped`.
- Tests: happy-path `fixtures/WF-26/jd_and_profile.json`; degraded `fixtures/WF-26/no_company_fetch.json`; safety `fixtures/WF-26/fabricated_metric.json`. Contracts: `web.fetch`, `llm.extract`. Golden: `golden/WF-26/interview-prep.md`.
- Deviations: none (no loosening).

---

### WF-27 — Cover letter generator

**Source ref:** `user-spec:WF-27` · **Status:** planned · **Version:** 0.1.0
**Part (batch):** 4 · **Domain family:** careers-housing
**Risk tier:** R1 (factors: none; `external_action` if send — **out of scope**) · **Engine:** simple · **Default intensity:** small
**Reconciliation:** action `REUSE` · canonical owner `skill:.agents/skills/cv-studio` (cover mode)
· existing assets `skill:.agents/skills/cv-studio` cover mode already specified; optional current company/JD research via Firecrawl
· duplicate surfaces avoided `any separate cover-letter skill`; `a second career profile`; `invented metrics`
· delta `Only catalog alias and source-risk metadata; keep zero-fabrication and owner-send gate.`
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-27`; `.agents/skills/cv-studio/SKILL.md` lines 32–40 and 75–79; RISK WF-27

#### 1. Purpose and user story
- The owner gets an editable cover letter plus an alignment table that maps **verified** `x_master` achievements to JD requirements, using official company facts when fetched — no new cover-letter engine.
- User story: "As an applicant, I want a tailored letter from my existing cv-studio profile so that I can edit and send it myself."
- Boundary: **NOT** sending email or portal upload (R3 owner). **NOT** a new letter store. **NOT** resume typesetting (`WF-33`). **NOT** LinkedIn About (`cv-studio` `linkedin` mode, not a separate WF). **NOT** interview Q&A (`WF-26`).
- Routing: triggers `cover letter`, `write a letter for this JD`, `scrisoare de intenție`; negative `send this letter` (R3 owner), `rewrite my resume` → `WF-33`, `LinkedIn About` → cv-studio `linkedin` (catalog, not new skill); aliases `/cover-letter`, `/cover`.
- Execution modes: `interactive`; `background` allowed (local transform + optional public fetch); not `scheduled`; not owner-present unless optional company fetch needs browser.
- Success criterion: letter has three short paragraphs (hook / proof / close) per cv-studio cover mode; every proof bullet traces to `x_master`; every number to `x_metrics`; alignment table rows cite JD spans; no send.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `profile_path` | file | yes | cv-studio `profile.yaml` | PII | active `profile.yaml` |
| `job_description` | file \| string | yes | JD text or `x_targets` id | PII | — |
| `company_name` | string | no | used for official-facts fetch | INTERNAL | parsed from JD |
| `tone` | enum | no | `values: [neutral, formal, concise]` | INTERNAL | `formal` |
| `language` | enum | no | `en\|ro` | INTERNAL | `en` |
| `fetch_company_facts` | bool | no | public official pages only | INTERNAL | `true` |

- Preconditions: profile + JD present; `cvstudio.py validate` callable; `web.fetch` only if `fetch_company_facts`.
- Intensity profile:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 2 | 4 | 2 | 3 | 1 | 0 |
| medium | 4 | 8 | 3 | 3 | 2 | 0 |
| high | 6 | 12 | 5 | 5 | 2 | 0 |
| limitless | null | null | all load-bearing | null | 3 | 0 |

- Budget: small `24 / 480 / 5`; medium `48 / 900 / 10`; high `80 / 1200 / 16`; limitless capped at high.
- Deviations: default intensity `small` (REUSE transform, not research). Company-fact corroboration only when `fetch_company_facts` is true.

#### 3. Data sources and knowledge bases
- Canonical authorities: owner `profile.yaml` (T4 elevated to T0 **for the owner's own history**). JD (T4 owner paste or T0 career-page JD if fetched). Company **official** about/careers facts (T0) — never blog “culture” listicles as authority.
- `sources.min_tier` T4 for owner facts (must still pass zero-fab); T0/T2 for company claims in the letter. `min_independent` 1 for a single official company page; unsourced company superlatives forbidden. `recency_max_days` 7 for company facts; JD until hash changes.
- Domain data: none. Optional `web.fetch` only.
- Basic Memory: `memory.capture: none` (letter is a run artifact; profile remains the SSOT).
- Cache: `standard` for official company pages (`slow`); **never** cache the letter's PII in shared cache (`SH-CACHE-7`).
- Paywall: none expected.
- Deviations: none vs D5 cover-letter rules (facts from T4 resume only).

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `llm.extract` (JD requirements), `llm.rewrite` (letter prose from `x_master` only), `fs.write`.
- Optional: `web.search`/`web.fetch` for official company facts → if absent, hook paragraph omits unsourced company claims; `doc.extract_text` if JD is PDF; `doc.convert` for DOCX export.
- Provider hints: none binding. **MUST NOT** add a cover-letter skill or SMTP/send adapter.
- Mechanism: cv-studio cover mode — three paragraphs: hook (why this company/role, using official facts if present), proof (2–3 `x_master` achievements mapped to JD), close (CTA). Mirror JD terminology from `tailor` keywords. Alignment table is mechanical requirement↔achievement IDs. Voices: writer, fabrication auditor, JD-coverage checker (`SH-CTX-2`).
- Reuse note: **catalog alias only**. Implementation is existing cover mode + RISK metadata. No second profile.

#### 5. Internal data structures / schemas
- Node outputs: `JdRequirement[]`, `AlignmentRow`, `CoverLetterDraft`.
- Shared schemas unchanged: §6.
- Extension: `AlignmentRow.requirement_span` + `achievement_ref` — cover-specific, not a shared Citation replacement (company facts still use Citation).
- Declared artifacts: `cover-letter.md` (required); `alignment-table.md` (required); optional `cover-letter.docx`.
- Schema example:

```json
{
  "schema_version": 1,
  "paragraphs": ["hook", "proof", "close"],
  "alignment": [
    {
      "jd_requirement": "site supervision of multiple contractors",
      "achievement_ref": "Example SA|Site Engineer",
      "metric_ref": null,
      "status": "mapped"
    }
  ],
  "unsourced_claims": []
}
```

#### 6. Step-by-step execution flow
- Engine: simple.
- Lifecycle phases used: `discover`, `execute`, `quality-review`, `capture` (transform class). Add `spec-review` when company facts are fetched.
- Numbered walkthrough:
  1. `load_profile` (discover, tool, `fs.read`)
  2. `validate_profile` (discover, gate, cv-studio validate)
  3. `parse_jd` (discover, llm, `llm.extract`) → requirements + keywords
  4. `optional_company_fetch` (execute, tool, `web.fetch`)
  5. `map_achievements` (execute, tool, local) → `AlignmentRow[]`
  6. `draft_letter` (execute, llm, `llm.rewrite`) → `CoverLetterDraft`
  7. `zero_fab_gate` (quality-review, gate)
  8. `quality_review` (quality-review, llm, `llm.judge`) advisory tone/ATS keywords
  9. `export_letter` (capture, export, `fs.write`)
- Branches: skip fetch if `fetch_company_facts=false`. Unmapped required JD items stay in alignment as `unmapped` — the letter **MUST NOT** pretend they are proven.
- Artifacts: `export_letter`. Checkpoint after `map_achievements`.
- Approval: `deterministic` + `human_required: 1` before the owner sends (send is outside this run). `panel_required: false`. Blocking: fabricated metric; send/SMTP capability present → definition error.
- Resume: reuse alignment if profile+JD hashes unchanged; regenerate prose only if those hashes change.

#### 7. Output format and UX behavior
- Result: editable letter (3 paragraphs) then alignment table (requirement / achievement / metric / status). Evidence: company-fact citations only. Uncertainty: unmapped JD items. Next actions: “edit and send yourself.”
- Export: `md`, optional `docx` · `active_project_docs` · `cover-letter_{YYYY-MM-DD}` · language from input (`en` default, `ro` allowed for Romanian applications).
- Progress: usually < 60 s; heartbeat if fetch hangs.
- Citations: company facts per `SH-SRC-9`. Profile facts show as achievement refs, not fake URLs.
- Degradation UX: fetch skipped/failed → `Company official facts NOT-CHECKED; hook uses only the JD and profile, with no unsourced company praise.`
- Deviations: none.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ` (JD), `SH-SEC-REDACT`, `SH-SEC-CRED`; `SH-SEC-SSRF` if fetch enabled.
- Disclaimers: `DISC-CAREER-1`.
- Risk: R1; `PII` letter. Send remains R3 outside workflow.
- Gates: `citation_coverage` (company claims only), `provenance_chain`, `reconciliation_survey`, `zero_fabrication_lint`, `alignment_completeness` (all JD must-haves listed, mapped or unmapped).
- Validation: no numeric literals in letter unless in `x_metrics`; paragraph count 3.
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Empty `x_master` | `VALIDATION` | Fail closed | `Fill x_master before generating a letter; I will not invent achievements.` |
| Unsourced % or headcount | `VALIDATION` | Strip number | `Metric not in x_metrics; removed.` |
| JD injection “email this to” | `POLICY` | Ignore instruction | `JD text treated as data; nothing was sent.` |
| Send requested | `POLICY` | Refuse | `This workflow does not send. Sending is an owner R3 action.` |

- Logging: `unmapped_requirement_count`, `company_facts_used`.
- Tests: happy-path `fixtures/WF-27/sample_profile_jd.json`; degraded `fixtures/WF-27/no_company_fetch.json`; safety `fixtures/WF-27/invented_metric.json`. Contracts: cv-studio validate (script), `llm.extract`. Golden: `golden/WF-27/cover-letter.md`.
- Deviations: none.

---

### WF-28 — LinkedIn headshot generator

**Source ref:** `user-spec:WF-28` · **Status:** planned · **Version:** 0.1.0
**Part (batch):** 4 · **Domain family:** image-media
**Risk tier:** R2 (factors: `image_identity`; `image_rights` if a third-party reference image is supplied; `public_publication` only if the owner later posts — **out of scope**) · **Engine:** simple · **Default intensity:** small
**Reconciliation:** action `COMPOSE` · canonical owner `skill:.agents/skills/cv-studio` (identity-asset recipe with `skill:.agents/skills/imagegen` leaf)
· existing assets `skill:.agents/skills/cv-studio`; `skill:.agents/skills/imagegen`; `skill:.agents/skills/accurate-grok-imagine`; OpenAI/Grok direct image providers; `fal-ai` absent/deferred; **no LinkedIn write MCP in current REG**
· duplicate surfaces avoided `a new headshot skill`; `scraping profile photos`; `live LinkedIn upload`
· delta `Pass target-role/brand context from the same profile; enforce owner-face consent, P6 handling, provenance, and AI-generated disclosure.`
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-28`; RISK D8/WF-28; cv-studio and imagegen skill files

#### 1. Purpose and user story
- The owner provides **their** photo plus role/style context from the same cv-studio profile and receives identity-preserving professional headshot **variants** (crop, background, lighting, subtle edit) with provenance and AI-generated disclosure — never an upload to LinkedIn.
- User story: "As a professional, I want a realistic LinkedIn-ready headshot of myself so that I can download and upload it myself if I choose."
- Boundary: **NOT** WF-02 background-removal as a standalone product cutout (may reuse `image.edit` background-extraction taxonomy). **NOT** product photos (`WF-13`) or thumbnails (`WF-24`). **NOT** generating another real person's face. **NOT** LinkedIn upload/post (recovered MCP `linkedin_post_image` is **out of scope** and live API is `NOT-CHECKED`). **NOT** KYC/identity documents.
- Routing: triggers `LinkedIn headshot`, `professional portrait from this photo`, `clean up my profile photo`; negative `upload to LinkedIn` (R3 owner), `make me look like [other person]`, `headshot of this employee photo I scraped`; aliases `/linkedin-headshot`, `/headshot`.
- Execution modes: `interactive` and **`owner-present-only`** (likeness consent). Forbidden in `background`/`scheduled` (`image_identity`).
- Success criterion: outputs are variants of the **consenting owner's** face; identity lock recorded; C2PA/manifest or hash-chain from input to output; labeled AI-edited; zero network calls to LinkedIn upload endpoints.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `owner_photo` | image | yes | `formats: [jpeg, png, webp]`; decode-bomb limits §10.1; EXIF inspected | PII | — |
| `subject_is_owner` | bool | yes | must be `true`; otherwise `POLICY` | INTERNAL | — |
| `consent_likeness` | bool | yes | must be `true` this run | INTERNAL | — |
| `profile_path` | file | no | cv-studio profile for role/brand context | PII | active `profile.yaml` if present |
| `target_role` | string | no | else profile `basics.label` | INTERNAL | from profile |
| `style` | enum | no | `values: [studio-neutral, outdoor-soft, corporate-indoor, plain-color]` | INTERNAL | `studio-neutral` |
| `variant_count` | integer | no | `min: 1`, `max: 6` | INTERNAL | 4 |
| `allow_generate_beyond_edit` | bool | no | default false; generate-from-scratch of a real face is denied | INTERNAL | `false` |

- Preconditions: `capability_healthy: image.edit` or `image.transform`; owner present; `subject_is_owner` and `consent_likeness`; `OPENAI_API_KEY` env **name** present for imagegen leaf (value never logged). RAM 4 GB min if no browser (no browser in happy path).
- Intensity profile (breadth = variants/QA voices, not web queries):

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 0 | 0 | 0 | 3 | 1 | 0 |
| medium | 0 | 1 | 0 | 3 | 1 | 0 |
| high | 0 | 2 | 0 | 5 | 2 | 0 |
| limitless | 0 | 2 | 0 | 5 | 2 | 0 |

- Budget: small `20 / 600 / 12`; medium `36 / 900 / 22`; high `48 / 1200 / 36`; limitless capped at high (image cost).
- Deviations: web intensity unused; `limitless` does not add web search for celebrity lookalikes (forbidden). Rights corroboration applies only if a third-party reference image is supplied (discouraged).

#### 3. Data sources and knowledge bases
- Canonical authorities: owner-supplied photo (T4 = T0 of **that asset**). cv-studio profile for role/brand **text** context only. Licensed style references the owner has rights to. **Not sources of identity:** model-generated faces as photographs of a named person; scraped social photos of third parties (D8).
- `sources.min_tier` T0 for rights/license claims (`image-media` floor). `min_independent` 1 except rights claims → 2. `recency_max_days` null (generated bits are session artifacts).
- Domain data: none. Image providers are direct APIs, not REG MCP (`fal-ai` absent/deferred).
- Basic Memory: `memory.capture: none`. **MUST NOT** store face embeddings or biometric templates.
- Cache: do not write owner face to shared cache (`SH-CACHE-7`). Run-dir artifacts only. Volatility N/A for generated bits.
- Paywall: none.
- Deviations: none vs D8; never treat output as an identity document.

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `image.analyze` (face detect / crop hints / injection EXIF), `image.transform` (deterministic crop/resize/EXIF strip — prefer over LLM, `SH-TOOL-6`), `image.edit` (background, lighting, subtle cleanup with identity-preserve taxonomy), `fs.write`.
- Optional: `image.generate` only for **non-face** background plates if edit cannot; if `image.edit` absent → `FAILED_TO_RUN` / `capability_unavailable` rather than swapping in a different person's stock photo; `accurate-grok-imagine` as **prompt-pattern** leaf for identity-preserve edits (still `image.edit` capability); `llm.classify` for QA (identity-drift / over-smoothing).
- Provider hints: `image.edit` via imagegen CLI (`gpt-image-1.5` edit, `identity-preserve`, high input fidelity). Optional Grok Imagine edit patterns. **MUST NOT** use recovered LinkedIn MCP `linkedin_post_image`. **MUST NOT** `browser.act` to linkedin.com/upload. **MUST NOT** `@fal` unless owner opts in (absent/deferred; visible fallback only).
- Mechanism: consent gate → analyze face bbox → deterministic crop to LinkedIn-safe square → edit background/lighting with **invariants: same person, no age/race/gender rewrite, no extra people** → N variants → hash-chain + optional C2PA → disclose AI-edited. Three voices on QA only (identity drift, overbeautify, rights). cv-studio supplies `target_role`/headline keywords for framing (wardrobe/background professionalism), not for face identity.
- Reuse note: **compose** cv-studio context + imagegen leaf. Pixels owned by imagegen; profile owned by cv-studio. No third headshot skill.

#### 5. Internal data structures / schemas
- Node outputs: `FaceCrop`, `EditInvariantSet`, `HeadshotVariant`, `HeadshotBundle`.
- Shared schemas unchanged: §6. `SafetyDecision` records consent.
- Extension: `HeadshotVariant.input_hash` / `output_hash` / `identity_lock: true` / `ai_generated: true`. Shared ArtifactManifest holds files but not identity-lock semantics.
- Declared artifacts: `variant-NN.png` (required, 1..N); `headshot-manifest.json` (required); `disclosure.txt` (required, ID `DISC-IMAGE-SYNTHETIC-1` only — no inline prose in the part).
- Schema example:

```json
{
  "schema_version": 1,
  "subject_is_owner": true,
  "consent_likeness": true,
  "input_hash": "sha256:4f2a...",
  "variants": [
    {
      "name": "variant-01.png",
      "output_hash": "sha256:aa19...",
      "ops": ["crop", "background", "lighting"],
      "identity_lock": true,
      "ai_generated": true
    }
  ],
  "linkedin_upload": false
}
```

#### 6. Step-by-step execution flow
- Engine: simple.
- Lifecycle phases used: `discover`, `plan`, `execute`, `quality-review`, `acceptance`, `capture` (generative media, `SH-LIFE-4`).
- Numbered walkthrough:
  1. `consent_gate` (discover, gate) → require `subject_is_owner` + `consent_likeness` + owner present
  2. `load_context` (discover, tool, `fs.read`) → optional profile role/style
  3. `inspect_photo` (discover, tool, `image.analyze`) → face present, EXIF/injection scan
  4. `plan_invariants` (plan, llm, `llm.extract`) → EditInvariantSet
  5. `preview_gate` (plan, gate) → R2 preview (`SH-STATE-1`)
  6. `crop_transform` (execute, tool, `image.transform`) → FaceCrop
  7. `edit_variants` (execute, foreach, `image.edit`) → HeadshotVariant[]
  8. `qa_identity` (quality-review, llm, `llm.classify`) → advisory drift flags; deterministic hash-chain still required
  9. `acceptance` (acceptance, gate, human) → owner picks variants; **no upload**
  10. `export_images` (capture, export, `fs.write`)
- Branches: no face detected → `FAILED` validation, do not generate a synthetic stand-in. Third-party face → `POLICY`. `allow_generate_beyond_edit=true` still **MUST NOT** synthesize a different real person.
- Artifacts: each variant + manifest. Checkpoint after `crop_transform`.
- Approval: `deterministic`, `core_panel`, `human`; `human_required: 1`; `panel_required: true` (R2). Record household two-party gap if only one human (`SH-APR` / GATE §6). Blocking: missing consent; LinkedIn upload attempt; biometric template write.
- Resume: do not reuse cropped faces across runs without re-consent; input hash change invalidates variants.

#### 7. Output format and UX behavior
- Result: gallery of variants + invariant list + disclosure ID rendered from yaml. Evidence: hash-chain, model/provider IDs, seed if any. Uncertainty: identity-drift QA flags. Next actions: “download and upload yourself if you want; this run did not post.”
- Export: `png`/`webp` · destination `output` · naming `linkedin-headshot_{YYYY-MM-DD}` with `_v2` if needed · language `en`. Sidecar manifest (`SH-UX-11`).
- Progress: heartbeat per variant > 60 s. Preview shows variant_count, provider, and `linkedin_upload: false`.
- Citations: rights/license if stock background used (`SH-SRC-9`). No “this is an unedited camera photo” if it is not.
- Degradation UX: `image.edit` down → `FAILED_TO_RUN: identity-preserving edit unavailable; I will not substitute a generated stranger or a scraped photo.` `fal-ai` absent → `fal-ai MCP absent/deferred; using imagegen leaf only.`
- Deviations: destination class `output` (images) rather than `docs`; no Romanian report.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-IDENTITY`, `SH-SEC-INJ` (EXIF/XMP/SVG), `SH-SEC-REDACT`, `SH-SEC-CRED`. No browser in happy path.
- Disclaimers: `DISC-IMAGE-SYNTHETIC-1`.
- Risk: R2 `image_identity`. Data: owner face `PII` (RISK P6). No extra-vendor upload without per-run consent.
- Gates: `reconciliation_survey`, `identity_consent`, `hash_chain_complete`, `no_linkedin_upload`, `no_biometric_template`, `ai_disclosure_present`. `citation_coverage` applies only if third-party imagery/rights claims exist; otherwise N/A documented in the gate row as `NOT-CHECKED` skipped-with-reason (rights claims absent) — do not fold into PASS if rights were claimed.
- Validation: face count = 1; output dimensions suitable for LinkedIn square; `ai_generated: true`.
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| `subject_is_owner` false | `POLICY` | Stop | `I will not generate a headshot of someone who is not the consenting owner.` |
| No consent | `POLICY` | Stop | `Likeness consent is required for this run.` |
| Upload to LinkedIn requested | `POLICY` | Refuse | `This workflow never uploads. Posting is an owner R3 action. LinkedIn MCP live API is NOT-CHECKED and is not used here.` |
| Identity drift QA fail | `VALIDATION` | Retry edit once, then fail variant | `Variant dropped: identity lock failed.` |
| Image provider 401 | `AUTH` | Fail node; never rotate keys | `Image provider authentication failed. Missing env name reported; no rotation.` |

- Logging: extra `variant_count`, `identity_lock_pass_ratio`, `provider_id`. Never log face embeddings.
- Tests: happy-path `fixtures/WF-28/owner_photo_consent.json`; degraded `fixtures/WF-28/image_edit_unhealthy.json`; safety `fixtures/WF-28/third_party_face.json` and `fixtures/WF-28/upload_requested.json`. Contracts: `image.transform`, `image.edit`. Golden: `golden/WF-28/headshot-manifest.json`.
- Deviations: none (R2 identity is a tightening vs generic image R1).

---

### WF-29 — Scholarship and fellowship finder

**Source ref:** `user-spec:WF-29` · **Status:** planned · **Version:** 0.1.0
**Part (batch):** 4 · **Domain family:** careers-housing
**Risk tier:** R1 (factors: none at rest; `browser_authenticated` if funder portal login → R2; `external_action` apply out of scope) · **Engine:** simple · **Default intensity:** medium
**Reconciliation:** action `COMPOSE` · canonical owner `skill:.agents/skills/cv-studio` (opportunities mode)
· existing assets `skill:.agents/skills/cv-studio`; `skill:.agents/skills/deep-research`; `skill:.agents/skills/grant-proposal-architecture`; Firecrawl/Tavily for discovery; official funder pages direct HTTPS; no scholarship MCP
· duplicate surfaces avoided `a separate scholarship profile/finder per funder`; `blog lists as authority`; `portal submission`
· delta `Match one profile to official eligibility/deadline records, then hand selected opportunity to grant-proposal architecture; 24h deadline TTL.`
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-29`; cv-studio/deep-research/grant skill files; RISK WF-29

#### 1. Purpose and user story
- The owner gets a concise ranked table of scholarships/fellowships matched to the **same** cv-studio profile (study field, citizenship, location, deadlines), with eligibility verified on official university/foundation/program pages, plus requirement lists, URLs, and application-gap notes — not a submitted application.
- User story: "As a student or researcher, I want official, currently open funding opportunities matched to my profile so that I can see gaps before I apply myself."
- Boundary: **NOT** job finder (`WF-25`). **NOT** writing the full proposal (hand off selected row to `grant-proposal-architecture`). **NOT** portal submit (R3). **NOT** a second “scholar profile.”
- Routing: triggers `find scholarships`, `fellowship finder`, `burse și fellowship-uri`, `funding opportunities for my CV`; negative `submit this application`, `find jobs` → `WF-25`, `write the grant` → grant-proposal-architecture after selection; aliases `/scholarships`, `/fellowships`.
- Execution modes: `interactive`; `owner-present-only` for authenticated funder portals; `background`/`scheduled` **MAY** refresh **official public** deadline pages already in the table (24 h TTL), never submit.
- Success criterion: every “still open” deadline is T0 official-page verified within 24 h or `UNVERIFIED-STALE`; eligibility notes cite the funder page; gaps vs profile are explicit; no apply.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `profile_path` | file | yes | cv-studio `profile.yaml` | PII | active `profile.yaml` |
| `study_field` | string | no | else education/skills from profile | INTERNAL | from profile |
| `citizenship` | list\<string\> | no | ISO country codes; owner-declared | PII | from profile if present |
| `study_locations` | list\<string\> | no | countries/cities | INTERNAL | `[]` |
| `deadline_window` | object | no | `{from, to}` ISO dates | INTERNAL | next 12 months |
| `degree_cycle` | enum | no | `values: [bachelor, master, phd, postdoc, other]` | INTERNAL | from profile education |
| `browser_profile` | enum | cond | BR-1 if portal | INTERNAL | `b` |
| `handoff_grant_architecture` | bool | no | after owner picks a row | INTERNAL | `false` |

- Preconditions: profile exists; `web.search`/`web.fetch` healthy; validate profile or `zero_fab: NOT-CHECKED`.
- Intensity profile:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 3 | 6 | 2 | 3 | 1 | 0 |
| medium | 6 | 14 | 5 | 3 | 2 | 0 |
| high | 12 | 30 | 12 | 5 | 2 | 0 |
| limitless | null | null | all load-bearing | null | 3 | 0 |

- Budget: small `48 / 900 / 8`; medium `120 / 1800 / 22`; high `220 / 2700 / 40`; limitless capped at high.
- Deviations: deadline-open TTL **24 h** (RISK D5); aggregator blogs cannot clear eligibility.

#### 3. Data sources and knowledge bases
- Canonical authorities: **official university / foundation / program pages** (T0: program name, year/cycle, official URL, deadline timezone). Gazette or funder PDF of rules when that is the instrument. Scholarship-aggregator blogs and “top 50 fellowships” SEO lists are T5 discovery hints only — never eligibility authority.
- `sources.min_tier` T0 for load-bearing eligibility/deadline; T3/T5 allowed for discovery queries labeled as such. `min_independent` 1 when the official program page was fully read; 2 if translating a blog list into claims (blog + official page, and the blog **does not** count as independent once the T0 is read — the T0 alone carries the claim). `recency_max_days` 1 for “still open”; pin the cycle year.
- Domain data: none in REG. Direct HTTPS to funder hosts via `web.fetch`.
- Basic Memory: `memory.capture: decisions` — selected program names/URLs the owner chose to pursue, not bulk ineligible lists.
- Cache: `standard`; deadline-open claim type TTL **86400 s**. Cache URL + program ID + hash + retrieved_at; do not dump applicant-portal HTML.
- Paywall: some funder portals; BR-1 + existing session; no credential typing by agents.
- Deviations: tightens “open” claims to 24 h vs §9.2 24 h medium (aligned) and vs 6-month market default (tighter).

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `llm.extract`, `web.search`, `web.fetch`, `llm.classify` (eligibility signals), `fs.write`.
- Optional: `browser.session` for JS official pages; `doc.extract_text` for official PDFs; `grant-proposal-architecture` **after** owner selects a row (`handoff_grant_architecture`); `memory.search` for prior pursuit decisions.
- Provider hints: Firecrawl/Tavily discovery. **MUST NOT** treat scholarship-blog tables as T0. **MUST NOT** `browser.act` submit. **MUST NOT** invent a per-funder finder skill.
- Mechanism: extract eligibility features from **one** profile → discover candidates → **foreach** official-page fetch → parse deadline (timezone) + eligibility → match to profile (citizenship, field, degree, location) → rank eligible-open first → gap notes (missing transcript, language cert, etc. as **prompts**, not fake documents). Voices: scout, adversarial closed-deadline hunter, evidence pin-cite on official page.
- Reuse note: **cv-studio opportunities mode** + deep-research leaves + grant-proposal-architecture as a **downstream** skill, not a duplicate opportunities DB.

#### 5. Internal data structures / schemas
- Node outputs: `OpportunityQuery`, `OpportunityRecord`, `EligibilityMatch`, `OpportunityTable`.
- Shared schemas unchanged: §6.
- Extension: `OpportunityRecord.deadline_at` + `deadline_tz` + `cycle` + `official_url_canonical`. Needed for 24 h open claims.
- Declared artifacts: `scholarships.md` (required table); `scholarships.json` (required); `application-gaps.md` (required).
- Schema example:

```json
{
  "schema_version": 1,
  "program": "Example Foundation Doctoral Fellowship",
  "funder": "Example Foundation",
  "cycle": "2026",
  "official_url": "https://foundation.example.org/fellowship-2026",
  "deadline_at": "2026-10-15T21:59:00Z",
  "deadline_tz": "Europe/Bucharest",
  "open_status": "open",
  "retrieved_at": "2026-08-29T06:00:00Z",
  "ttl_seconds": 86400,
  "eligibility": ["EU citizenship", "PhD enrolment"],
  "profile_match": "eligible",
  "gaps": ["language certificate not in profile"],
  "tier": "T0"
}
```

Rank eligible ∩ open by deadline urgency, then by match coverage. `open_status` must be T0-backed.

#### 6. Step-by-step execution flow
- Engine: simple.
- Lifecycle phases used: `discover`, `recall`, `execute`, `spec-review`, `quality-review`, `acceptance`, `capture`.
- Numbered walkthrough:
  1. `load_profile` (discover, tool, `fs.read`)
  2. `build_query` (discover, llm, `llm.extract`)
  3. `recall` (recall, tool, `memory.search`)
  4. `preview_gate` (discover, gate) + BR-1 if needed
  5. `discover_opps` (execute, fanout, `web.search`)
  6. `verify_official` (execute, foreach, `web.fetch` / optional `browser.session`)
  7. `match_eligibility` (execute, llm, `llm.classify`) vs profile — **no fabricated citizenship/degrees**
  8. `spec_review` (spec-review, gate) → T0 deadline + 24 h TTL
  9. `quality_review` (quality-review, llm, `llm.judge`)
  10. `acceptance` (acceptance, gate, human) → owner may set `handoff_grant_architecture`
  11. `optional_handoff` (capture, tool, none) → invoke grant-proposal-architecture on selected official URL + profile
  12. `export_table` (capture, export, `fs.write`)
- Branches: blog-only hits without official URL → discovery appendix, not ranked-open table. Handoff skipped unless owner picked a row.
- Artifacts: table + gaps. Checkpoint after `verify_official`.
- Approval: `deterministic` + `human_required: 1`. Apply/submit `POLICY`. `panel_required: false` at R1.
- Resume: re-fetch deadline if TTL expired; reuse eligibility parse if content_hash unchanged.

#### 7. Output format and UX behavior
- Result: ranked table (program, funder, cycle, deadline+tz, official URL, eligibility signals, match, gaps). Appendix: unverified aggregator hits. Evidence: T0 citations. Uncertainty: timezone ambiguity, stale portals. Next actions: apply yourself; optional grant-architecture handoff.
- Export: `md`, `xlsx` · `active_project_docs` · `scholarships_{YYYY-MM-DD}` · language `en` (or `ro` if owner requested).
- Progress: heartbeat on foreach fetches. Preview shows deadline window and that blogs are not authority.
- Staleness: deadline-open past 24 h → `STALE`. Conflicts between blog and official page → official wins; conflict section notes the blog (`SH-SRC-5`).
- Degradation UX: `Official program page unreachable; row moved to unverified appendix.` Grant skill missing → `Handoff skipped; table still complete.`
- Deviations: extra xlsx; appendix for T5-only hits.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER` if used, `SH-SEC-REDACT`, `SH-SEC-CRED`.
- Disclaimers: `DISC-CAREER-1`.
- Risk: R1; profile `PII`. Discriminatory eligibility **copied from the funder T0** is allowed as a **quoted rule**; the workflow **MUST NOT** add extra protected-class filters of its own.
- Gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, `deadline_ttl_fresh` (24 h), `official_url_present_for_ranked_rows`, `zero_apply_side_effect`, `zero_fabrication_lint` (citizenship/education vs profile).
- Validation: ISO deadline parse; timezone required or `NOT-CHECKED` on open_status.
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Blog list without official URL | `VALIDATION` | Exclude from ranked-open | `Aggregator hit omitted from ranked table; no official page.` |
| Deadline parse fail | `VALIDATION` | `open_status: NOT-CHECKED` | `Could not parse an official deadline.` |
| Apply click | `POLICY` | Block | `This workflow does not submit applications.` |
| Profile citizenship contradicted by letter text | `VALIDATION` | Fail closed | `Citizenship claims must match profile.yaml.` |

- Logging: extra `t0_official_ratio`, `stale_deadline_count`, `handoff_invoked`.
- Tests: happy-path `fixtures/WF-29/official_pages.json`; degraded `fixtures/WF-29/blog_only.json`; safety `fixtures/WF-29/portal_submit.json`. Contracts: `web.fetch`. Golden: `golden/WF-29/scholarships.md`.
- Deviations: 24 h deadline TTL (documented tighten).

---

### WF-30 — Career explorer

**Source ref:** `user-spec:WF-30` · **Status:** planned · **Version:** 0.1.0
**Part (batch):** 4 · **Domain family:** careers-housing
**Risk tier:** R1 (factors: none; salary figures are statistics, not `financial_advice`) · **Engine:** simple · **Default intensity:** medium
**Reconciliation:** action `UPGRADE` · canonical owner `skill:.agents/skills/cv-studio` (career mode)
· existing assets `skill:.agents/skills/cv-studio`; `skill:.agents/skills/deep-research`; evidence-ledger pattern; ESCO/ISCO/COR/O*NET/Eurostat/INS/BLS as **direct** data sources; no labor MCP in REG
· duplicate surfaces avoided `a new career-profile skill`; `unsupported salary/outcome promises`
· delta `Map profile skills to occupation codes and evidence-backed gaps; keep statistics separate from anecdote and preserve source release/date.`
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-30`; RISK WF-30/D5; cv-studio and deep-research skills

#### 1. Purpose and user story
- From major/interests/skills/goals/preferences on the **same** profile, the owner receives role clusters, paths, skill gaps, next steps, and resources, with official occupation codes and labor statistics **labeled as statistics**, not as personal outcome promises.
- User story: "As a student or mid-career professional, I want occupation-code-backed path options so that I can plan learning without treating anecdotes as labor-market proof."
- Boundary: **NOT** vacancy search (`WF-25`). **NOT** interview prep (`WF-26`). **NOT** guaranteed salary/placement. **NOT** a second career profile.
- Routing: triggers `career explorer`, `what jobs fit my major`, `occupation paths`, `skill gaps for`; negative `find open jobs` → `WF-25`, `guarantee I will earn` (refuse), `interview questions` → `WF-26`; aliases `/career-explorer`, `/careers`.
- Execution modes: `interactive`; `background` allowed (public stats); `scheduled` MAY refresh official tables when a new release is labeled; no owner-present requirement unless a JS statistical browser is needed.
- Success criterion: every occupation row has a pinned code (ESCO/ISCO/COR/O*NET) + release; every salary/employment figure has table ID + release date; inference/anecdote labeled `inference` and non-load-bearing.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `profile_path` | file | yes | cv-studio `profile.yaml` | PII | active `profile.yaml` |
| `major_or_field` | string | no | else education | INTERNAL | from profile |
| `interests` | list\<string\> | no | `max_items: 20` | INTERNAL | profile `interests` |
| `goals` | string | no | | INTERNAL | from profile |
| `work_preferences` | object | no | remote/on-site, sector, travel; no protected-class filters | INTERNAL | `{}` |
| `jurisdiction` | enum | no | `RO\|EU\|US\|other` | INTERNAL | `RO` |
| `include_salary_stats` | bool | no | requires T0/T1 tables | INTERNAL | `true` |

- Preconditions: profile exists; `web.fetch` healthy for official stats hosts; optional `data.occupations` / `data.labor_statistics` (usually absent — HTTPS fallback).
- Intensity profile:

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 3 | 6 | 2 | 3 | 1 | 0 |
| medium | 6 | 14 | 5 | 3 | 2 | 0 |
| high | 12 | 30 | 12 | 5 | 2 | 0 |
| limitless | null | null | all load-bearing | null | 3 | 0 |

- Budget: small `40 / 900 / 8`; medium `100 / 1800 / 20`; high `200 / 2700 / 36`; limitless capped at high.
- Deviations: salary/employment load-bearing claims require `min_independent` 2 and official release pin (tighten §8.2 careers-housing salary floor).

#### 3. Data sources and knowledge bases
- Canonical authorities (T0/T1 labor/occupation):
  - ESCO: `https://esco.ec.europa.eu/` and API `https://ec.europa.eu/esco/api`
  - ISCO-08: ILO `https://ilostat.ilo.org/resources/concepts-and-definitions/classification-occupation/`
  - COR (RO): MMSS / Monitorul Oficial classification instruments (T0 gazette/order), not third-party COR browsers
  - O*NET: `https://www.onetonline.org/` and `https://www.onetcenter.org/database.html`
  - Eurostat: `https://ec.europa.eu/eurostat`
  - INS: `https://insse.ro/`
  - BLS OEWS: `https://www.bls.gov/oes/`
  Current postings (T3) may **illustrate** demand only, labeled T3, never as wage T0.
- `sources.min_tier` T1 for occupation definitions; T0/T1 for statistics tables. `min_independent` 2 for salary/employment figures (e.g. INS + Eurostat, or BLS + O*NET wage tables — not two mirrors of the same series). `recency_max_days` 30 for “current table” (or until next labeled release); 180 allowed only with staleness note for older yearbooks (`SH-SRC-7`).
- Domain data: `data.occupations` (code lookup), `data.labor_statistics` (series pull). **Both absent from REG today** → `web.fetch` official HTML/CSV/API; status `adapter: NOT-CHECKED`.
- Basic Memory: `memory.capture: decisions` — chosen occupation codes and jurisdiction, not raw wage dumps.
- Cache: `standard`; volatility `slow` for classifications, `slow`/`medium` for statistical releases. Pin `release` in the cache key.
- Paywall: none for these public stats; institutional rail unused.
- Deviations: tightens salary recency from 6 months default to **30 days or current release**; forbids Reddit/forum as labor proof (T5).

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `llm.extract` (skills/goals), `web.search`, `web.fetch`, `llm.classify` (cluster labels — advisory), `fs.write`.
- Optional: `data.occupations`, `data.labor_statistics` → if absent, official HTTPS fetch; `data.job_postings` **illustration only**; `doc.render_table` for xlsx; `memory.search`.
- Provider hints: direct official hosts. **MUST NOT** use unofficial COR scrapers as T0. **MUST NOT** promise outcomes.
- Mechanism: map profile skills/education to candidate codes in the jurisdiction's system (COR+ESCO for RO/EU; O*NET+SOC for US explicitly selected) → cluster roles → skill-gap = essential occupation skills minus profile.skills/`x_master` tools → attach statistics with release IDs → paths/next steps as **inference** unless a cited training standard exists. Voices: scout codes, adversarial overclaim on wages, evidence pin on table/release.
- Reuse note: **cv-studio career mode** on the same `profile.yaml`. No parallel career DB.

#### 5. Internal data structures / schemas
- Node outputs: `OccupationHit`, `RoleCluster`, `SkillGap`, `StatClaim`, `CareerMap`.
- Shared schemas unchanged: §6. `Citation` for every StatClaim.
- Extension: `StatClaim.series_id` + `release` + `kind: statistic|inference`. Shared SourceRecord has no occupation-code field.
- Declared artifacts: `career-explorer.md` (required); `occupation-map.json` (required); `skill-gaps.md` (required).
- Schema example:

```json
{
  "schema_version": 1,
  "code_system": "ESCO",
  "code": "2142.1",
  "label": "civil engineer",
  "release": "ESCO v1.2.1",
  "jurisdiction": "EU",
  "stat_claims": [
    {
      "kind": "statistic",
      "metric": "employment",
      "value": null,
      "unit": null,
      "table_id": "EXAMPLE",
      "release": "2025-Q4",
      "source_id": "src_01K3",
      "load_bearing": true
    }
  ],
  "inferences": ["site-to-design path is common in owner sector — labeled inference"],
  "gaps": ["Eurocode detailing not listed in skills"]
}
```

#### 6. Step-by-step execution flow
- Engine: simple.
- Lifecycle phases used: `discover`, `recall`, `execute`, `spec-review`, `quality-review`, `acceptance`, `capture`.
- Numbered walkthrough:
  1. `load_profile` (discover, tool, `fs.read`)
  2. `jurisdiction_gate` (discover, gate) → default RO; ASK-GATE if ambiguous US/UK
  3. `extract_skills` (discover, llm, `llm.extract`)
  4. `recall` (recall, tool, `memory.search`)
  5. `preview_gate` (discover, gate)
  6. `lookup_codes` (execute, fanout, `web.fetch` / optional `data.occupations`)
  7. `cluster_roles` (execute, llm, `llm.classify`)
  8. `pull_stats` (execute, foreach, `web.fetch` / optional `data.labor_statistics`)
  9. `optional_postings_illust` (execute, tool, `web.search`) → T3 labeled
  10. `gap_analysis` (execute, tool, local) → profile vs essential skills
  11. `spec_review` (spec-review, gate) → statistic vs inference split; salary corroboration
  12. `quality_review` (quality-review, llm, `llm.judge`)
  13. `acceptance` (acceptance, gate, human)
  14. `export_map` (capture, export, `fs.write`)
- Branches: `include_salary_stats=false` skips wage tables. T3 postings never enter StatClaim.load_bearing.
- Artifacts: map + gaps. Checkpoint after `lookup_codes`.
- Approval: `deterministic` + `human_required: 1`. Blocking: wage number without series+release; mixing inference into statistic column.
- Resume: reuse codes if profile hash unchanged; re-pull stats if release TTL expired.

#### 7. Output format and UX behavior
- Result: role clusters (codes + labels), paths, skills, gaps, next steps, resources. Two clearly separated tables: **Statistics** vs **Inference**. Evidence: table/release citations. Uncertainty: series lags, crosswalk ESCO↔COR↔O*NET error. Next actions: learning resources; optional `WF-25` for vacancies.
- Export: `md`, `xlsx` · `active_project_docs` · `career-explorer_{YYYY-MM-DD}` · language `en` (RO labels allowed for COR).
- Progress: heartbeat on stats fetches. Preview names jurisdiction and code systems.
- Staleness: table older than recency window labeled `STALE` and non-load-bearing unless noted.
- Degradation UX: `data.occupations` absent → `Occupation adapters NOT-CHECKED; using official ESCO/O*NET/COR pages via web.fetch.` Missing wage table → `Salary omitted; NOT-CHECKED rather than estimated.`
- Deviations: dual statistic/inference tables required.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-REDACT`, `SH-SEC-CRED`.
- Disclaimers: `DISC-CAREER-1`.
- Risk: R1; do not set `financial_advice` unless the text recommends a specific investment (it must not). Data: profile `PII`; stats `PUBLIC`.
- Gates: `citation_coverage`, `provenance_chain`, `reconciliation_survey`, `occupation_code_pin`, `stat_vs_inference_split`, `salary_min_independent` (when wages present), `zero_outcome_promise`.
- Validation: code format per system; no NaN wages (`SH-VAL-6` analogue for labor units).
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Unofficial COR browser as only source | `VALIDATION` | Reject as T0 | `COR code must cite MMSS/Monitorul Oficial or ESCO crosswalk, not a third-party browser.` |
| Model wage with no table | `VALIDATION` | Drop wage | `Salary figure removed: no official series.` |
| Protected-class preference in inputs | `POLICY` | Fail | `Protected-characteristic filters are not allowed.` |
| Stats host timeout | `TIMEOUT` | Retry then omit series | `Labor table fetch failed; statistic marked NOT-CHECKED.` |

- Logging: extra `codes_pinned`, `stat_claims`, `inference_claims`, `crosswalk_notes`.
- Tests: happy-path `fixtures/WF-30/esco_ins.json`; degraded `fixtures/WF-30/no_wage_table.json`; safety `fixtures/WF-30/guaranteed_salary.json`. Contracts: `web.fetch`. Golden: `golden/WF-30/career-explorer.md`.
- Deviations: salary corroboration floor 2; 30-day table recency.

---

### WF-32 — Alumni finder

**Source ref:** `user-spec:WF-32` · **Status:** planned · **Version:** 0.1.0
**Part (batch):** 4 · **Domain family:** careers-housing
**Risk tier:** R2 (factors: `browser_authenticated` when verifying LinkedIn in-session; third-party identity is `PII`) · **Engine:** simple · **Default intensity:** small
**Reconciliation:** action `COMPOSE` · canonical owner `skill:.agents/skills/cv-studio` (alumni mode) composed with `skill:.agents/skills/deep-research` / public search and owner-present browser verification
· existing assets `skill:.agents/skills/cv-studio`; `skill:.agents/skills/deep-research`; `skill:.agents/skills/browser-rail`; recovered `tools\mcp\linkedin-mcp` source (**RECOVERABLE/HEALTHY-SOURCE**, 82 offline tests; **no** alumni/search/Recruiter/Talent capability; REG/CUR/PARK absence; registration/auth/live API **NOT-CHECKED**)
· duplicate surfaces avoided `a new alumni or LinkedIn MCP`; `treating own-feed posting as alumni discovery`; `bulk profiles/dossiers`; `automated outreach`
· delta `Compose public discovery and browser verification with P2 minimization; the recovered MCP is optional only for owner OIDC identity and own-post outreach; registration/auth/live API remain NOT-CHECKED.`
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-32`; matrix §7; `source\agent-skills-toolchain\tools\mcp\linkedin-mcp\README.md`; RISK WF-32

#### 1. Purpose and user story
- The owner names a school plus target firms/roles/locations and receives a **minimized** contact list of people whose school and current-company affiliation were verified from public/official pages and owner-present LinkedIn **browser** checks, plus **unsent** outreach drafts — not a dossier, not Recruiter search, not auto-message.
- User story: "As an alumnus, I want to find classmates at target companies so that I can choose whom to contact myself."
- Boundary: **NOT** LinkedIn Recruiter/Talent/Sales Navigator. **NOT** the recovered LinkedIn MCP as a search tool (it cannot). **NOT** bulk scrape. **NOT** sending InMail/email (`external_action` R3). **NOT** job finder (`WF-25`). Own-feed posting is **not** this workflow's default path even if the MCP is later integrated (that would be a separate R3 post action).
- Routing: triggers `alumni finder`, `who from my school works at`, `find alumni at`; negative `scrape all alumni`, `send InMails`, `use Recruiter`, `LinkedIn MCP people search` (does not exist); aliases `/alumni`, `/alumni-finder`.
- Execution modes: **`interactive` + `owner-present-only`**. Forbidden in `background`/`scheduled` (P2 + ToS browser).
- Success criterion: each listed person has verification status for school and company; fields minimized; outreach unsent; no MCP search claims; listing cap honored.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `profile_path` | file | no | owner school from education[] | PII | active `profile.yaml` |
| `school` | string | yes | official name | INTERNAL | from profile education |
| `target_firms` | list\<string\> | yes | `min_items: 1`, `max_items: 20` | INTERNAL | — |
| `target_roles` | list\<string\> | no | `max_items: 20` | INTERNAL | `[]` |
| `locations` | list\<string\> | no | | INTERNAL | `[]` |
| `max_people` | integer | no | `min: 1`, `max: 25` | INTERNAL | intensity sources cap (≤ 15 at small) |
| `browser_profile` | enum | yes | BR-1; default `b`; never silent `a` | INTERNAL | `b` |
| `persist_contacts` | bool | no | default false; if true, still local run-dir only, not Basic Memory | PII | `false` |

- Preconditions: owner present; `free_ram_gb_min` 8; `browser.session` healthy if LinkedIn verification requested; `web.search`/`web.fetch` for public/official pages. LinkedIn MCP **not** a precondition (and not used for search).
- Intensity profile (people, not generic SERP breadth):

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 3 | 6 | 2 | 3 | 1 | 0 |
| medium | 6 | 12 | 5 | 3 | 2 | 0 |
| high | 8 | 20 | 8 | 5 | 2 | 0 |
| limitless | 8 | 25 | 8 | 5 | 2 | 0 |

`max_people` **MUST NOT** exceed 25 even at `limitless` (no bulk dossier).
- Budget: small `36 / 900 / 10`; medium `80 / 1500 / 18`; high `120 / 2100 / 28`; limitless capped at high.
- Deviations: hard cap on people; `limitless` does not mean unbounded LinkedIn crawl.

#### 3. Data sources and knowledge bases
- Canonical authorities: **official alumni directories / university news / company team or careers pages** (public T0/T1, P1). Owner-present LinkedIn **public profile view** is T3/ToS-restricted observational confirmation — not an API search. School affiliation and company affiliation **MUST** be verified separately when both are claimed. Aggregators mirroring a LinkedIn post are the **same** independence group as that post (RISK §5.1).
- `sources.min_tier` T1 for official school/company pages; LinkedIn UI is T3 labeled. Load-bearing “works at X and attended Y” needs verification of both claims (`min_independent` 2 instruments: e.g. company page + school mention, or company page + owner-present profile read — LinkedIn + its mirror count as one). `recency_max_days` 7 for current-company claims (`slow` company profiles).
- Domain data: **none**. Recovered LinkedIn MCP is **not** `data.*` for people search. Do not invent `data.alumni`.
- Basic Memory: `memory.capture: none`. **MUST NOT** write alumni contact lists to the vault.
- Cache: URL + verification status + retrieved_at + hash; **no LinkedIn HTML dumps**; **no** bulk identity dossier beyond the run unless `persist_contacts` (still run-dir / project, not BM). Volatility `slow` for company pages; LinkedIn cards 12 h if used as current-role claims (D5 board-card TTL) but affiliation verification should re-read when presenting.
- Paywall/ToS: LinkedIn UI owner-present + BR-1; prefer `(b)`; `(a)` only explicit. No fake accounts. No Recruiter.
- Deviations: tighter P2 minimization than generic careers-housing; explicit MCP non-use for search.

#### 4. Tool chain and mechanisms
- Required: `web.search`, `web.fetch`, `browser.session` (verification, read-only), `llm.extract` (public-page fields only), `fs.write`.
- Optional: `fs.read` profile for school default; `browser.act` **denied** for message/connect/InMail (`POLICY`); recovered LinkedIn MCP **MUST NOT** be required; if later present, it may provide `linkedin_whoami` (owner identity) only — **not** people search. `memory.search` unused for third-party P2.
- Provider hints: Firecrawl for **public** pages; Playwright/Chrome for owner-present LinkedIn **verification**. **MUST NOT** `@apify`/`scrapegraph`. **MUST NOT** `web.crawl` linkedin.com. **MUST NOT** register a new alumni MCP.
- Mechanism: search official/public pages for “school + firm” → candidate URLs → cap at `max_people` → owner-present browser **spot-verify** school and company on each kept profile/page → record `verification_status` → draft **unsent** outreach using owner profile (zero-fab). Voices: scout public pages, adversarial over-identification (wrong person), evidence that both affiliations were seen. Recovered MCP is documented as **non-capable** for this job; claiming it searched alumni is a spec defect.
- Reuse note: **cv-studio alumni mode** (same profile for the owner's school/voice in drafts) + deep-research public search + browser-rail verification. Composition owns sequencing, not a new graph DB.

#### 5. Internal data structures / schemas
- Node outputs: `AlumniCandidate`, `AffiliationVerification`, `OutreachDraft`, `AlumniList`.
- Shared schemas unchanged: §6.
- Extension: minimized P2 fields only — `display_name`, `public_url`, `school_claim`, `company_claim`, `role_claim`, `location_public`, `verification_status`. No phone, no scraped email harvest, no employee ID. Shared SourceRecord URLs are kept; payloads redacted.
- Declared artifacts: `alumni-contacts.md` (required, minimized); `alumni-contacts.json` (required); `outreach-unsent.md` (required). Retention: delete or trash after run unless owner `persist_contacts`.
- Schema example:

```json
{
  "schema_version": 1,
  "display_name": "A. B.",
  "public_url": "https://example.com/team/ab",
  "school_claim": "Example University",
  "company_claim": "Example S.A.",
  "role_claim": "Engineer",
  "location_public": "București",
  "verification_status": "verified_school_and_company",
  "instruments": ["company_page", "owner_present_linkedin_view"],
  "linkedin_mcp_used_for_search": false,
  "outreach_sent": false
}
```

`verification_status` ∈ `verified_school_and_company` | `verified_school_only` | `verified_company_only` | `unverified` | `conflict`.

#### 6. Step-by-step execution flow
- Engine: simple.
- Lifecycle phases used: `discover`, `recall` (skipped with reason: no P2 recall from BM), `execute`, `spec-review`, `quality-review`, `acceptance`, `capture`.
- Numbered walkthrough:
  1. `load_owner_school` (discover, tool, `fs.read`) optional
  2. `br1_gate` (discover, gate) → browser profile choice recorded
  3. `preview_gate` (discover, gate) → R2 preview; shows MCP is not a search provider
  4. `public_discover` (execute, fanout, `web.search`/`web.fetch`) → official/public hits
  5. `cap_and_minimize` (execute, tool, local) → ≤ max_people
  6. `verify_affiliation` (execute, foreach, `browser.session` and/or `web.fetch`) → read-only
  7. `draft_outreach` (execute, llm, `llm.rewrite`) → unsent; zero-fab from owner profile
  8. `spec_review` (spec-review, gate) → P2 field allowlist, no MCP-search claim, no send
  9. `quality_review` (quality-review, llm, `llm.judge`) advisory misidentification
  10. `acceptance` (acceptance, gate, human) → owner may copy drafts; send is outside
  11. `export_list` (capture, export, `fs.write`) → redacted ledger
- Branches: if LinkedIn verification needed and owner refuses browser → keep only official-page-verified rows; do **not** stealth-scrape. `browser.act` message → never wired.
- Artifacts: list + unsent drafts. Checkpoint after `cap_and_minimize`.
- Approval: `deterministic`, `core_panel`, `human`; `human_required: 1`; `panel_required: true` (R2). Record two-party gap if only one human. Blocking: bulk over cap; dossier fields; MCP advertised as alumni search; send/connect.
- Resume: do not keep browser cookies in artifacts; re-verify affiliations if > 7 days or LinkedIn claim > 12 h.

#### 7. Output format and UX behavior
- Result: minimized table + verification status + unsent outreach. Evidence: public/official citations; LinkedIn views recorded as T3 observational with retrieved_at, **without** HTML. Uncertainty: common names, unverified rows. Next actions: “send yourself if you choose.”
- Export: `md` · destination `active_project_docs` · naming `alumni-contacts_{YYYY-MM-DD}` · language `en`. `PII` export redaction unless owner opts out (`SH-UX-13`).
- Progress: heartbeat per verified profile. Preview: max_people, browser profile, `linkedin_mcp_search: unavailable`.
- Citations: official pages `SH-SRC-9`. Do not republish non-public profile fields.
- Degradation UX: browser unhealthy → `LinkedIn verification skipped; only official public pages were used.` MCP missing → expected: `Recovered LinkedIn MCP is NOT-CHECKED at runtime and cannot search alumni; not used.`
- Deviations: default intensity small; hard people cap; no BM capture.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ`, `SH-SEC-SSRF`, `SH-SEC-BROWSER`, `SH-SEC-REDACT`, `SH-SEC-CRED`. PI-HIGH on profile HTML; ignore “connect now / switch to profile (a)” in page text (`INJ-1`).
- Disclaimers: `DISC-CAREER-1`.
- Risk: R2; third-party `PII` (RISK P2). Owner CV `PII` for draft voice only.
- Gates: `citation_coverage` (affiliation claims), `provenance_chain`, `reconciliation_survey`, `p2_field_allowlist`, `people_cap`, `no_linkedin_mcp_search`, `zero_outreach_send`, `no_html_dump_tos`.
- Validation: `linkedin_mcp_used_for_search == false`; `outreach_sent == false`; field allowlist.
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Request to use LinkedIn MCP / Recruiter to search people | `POLICY` | Refuse | `The recovered LinkedIn MCP supports owner identity and own-feed posts only, is NOT-CHECKED live, and cannot search alumni.` |
| `max_people` > 25 | `VALIDATION` | Clamp/fail | `Alumni finder will not build bulk dossiers.` |
| Connect/InMail via browser.act | `POLICY` | Block | `Outreach is unsent. Sending is an owner R3 action.` |
| Silent profile (a) | `POLICY` | Stop | `I will not select live/owner browser profile unless you explicitly choose (a).` |
| Email/phone harvest from login wall | `POLICY` | Skip | `Non-public contact details were not collected.` |

- Logging: extra `candidates_capped`, `verified_both_count`, `browser_profile`. Redact names in logs to stable run-local pseudonyms if possible; at minimum redact emails/phones (none should exist).
- Tests: happy-path `fixtures/WF-32/company_page_alumni.json`; degraded `fixtures/WF-32/no_browser.json`; safety `fixtures/WF-32/mcp_search_claimed.json` and `fixtures/WF-32/auto_inmail.json`. Contracts: `web.fetch`, `browser.session`. Golden: `golden/WF-32/alumni-contacts.md` (synthetic names).
- Deviations: people cap; MCP search prohibition; no BM write of P2 lists.

---

### WF-33 — Resume editor

**Source ref:** `user-spec:WF-33` · **Status:** planned · **Version:** 0.1.0
**Part (batch):** 4 · **Domain family:** careers-housing
**Risk tier:** R1 (factors: none; `external_action` submit out of scope; `irreversible_local` avoided via `_v2` naming) · **Engine:** simple · **Default intensity:** small
**Reconciliation:** action `REUSE` · canonical owner `skill:.agents/skills/cv-studio` (ATS/tailor modes)
· existing assets `skill:.agents/skills/cv-studio` ATS, tailor, build, validate, selfcheck, JSON Resume export; RenderCV/JSON Resume/local scripts; no MCP required
· duplicate surfaces avoided `a new resume/CV editor skill`; `a graphic ATS CV`; `source-command-resume-session`
· delta `Catalog alias only; retain one profile.yaml, x_master, x_metrics, selectable-text and zero-fabrication gates.`
· evidence `.agents/PERPLEXITY-WORKFLOWS-REUSE-MCP-MATRIX_2026-08-29.md#WF-33`; `.agents/skills/cv-studio/SKILL.md` lines 19–73 and 105–114; RISK WF-33

#### 1. Purpose and user story
- The owner gets an ATS-aware resume revision (structure, keywords, bullets, layout) as a **clean** RenderCV PDF plus a change-tracked summary, using the existing cv-studio pipeline — submitted CV stays selectable-text single column; visual portfolio stays separate.
- User story: "As an applicant, I want my existing cv-studio profile tailored to a JD so that I can submit an ATS-safe PDF I can still select text from."
- Boundary: **NOT** `source-command-resume-session`. **NOT** a Figma/multi-column graphic as the **submitted** CV (`visual` mode is a separate artifact). **NOT** cover letter (`WF-27`). **NOT** LinkedIn copy (cv-studio `linkedin` mode). **NOT** STAR story bank (`WF-34`). **NOT** inventing jobs/dates/metrics.
- Routing: triggers `resume editor`, `ATS resume`, `tailor my CV`, `RenderCV build`; negative `/resume-session`, `make a designed infographic resume for Workday`, `write cover letter` → `WF-27`; aliases `/resume`, `/cv`, `/ats-resume`.
- Execution modes: `interactive`; `background` allowed (local deterministic scripts); not scheduled; owner-present not required unless they want visual-design routing.
- Success criterion: `cvstudio.py build` prints `SUCCESS:`; PyMuPDF self-check finds name, email, every company, every institution in the text layer; tailor report maps keywords; change summary lists diffs vs previous PDF hash; zero fabrication warnings unresolved.

#### 2. Inputs and configuration options
| Name | Type | Required | Constraints | Classification | Default |
|---|---|---|---|---|---|
| `profile_path` | file | yes | cv-studio `profile.yaml` | PII | active `profile.yaml` |
| `job_description` | file \| string | no | required for `tailor` | PII | omit for untailored ATS build |
| `mode` | enum | no | `values: [ats, tailor, build, validate, selfcheck, json]` | INTERNAL | `ats` |
| `theme` | enum | no | RenderCV single-column themes: `classic`, `engineeringresumes`, `sb2nov`, `engineeringclassic`, `moderncv` | INTERNAL | `classic` |
| `visual_portfolio` | bool | no | if true, **route** to design-studio/JSON Resume HTML; does not replace ATS PDF | INTERNAL | `false` |
| `prior_pdf` | file | no | for change-tracked summary | PII | previous run artifact if present |

- Preconditions: cv-studio venv Python available (`INSTALL.md` path); `profile.yaml` exists; scripts `validate`/`build`/`tailor`/`selfcheck`/`json` present. No MCP.
- Intensity profile (LLM only for bullet rewrite from `x_master`; scripts are deterministic):

| Preset | Queries | Sources | Full-text reads | Voices | Corroboration | Loops |
|---|---|---|---|---|---|---|
| small | 0 | 1 | 1 | 3 | 1 | 0 |
| medium | 0 | 1 | 1 | 3 | 1 | 0 |
| high | 0 | 2 | 1 | 5 | 1 | 0 |
| limitless | 0 | 2 | 1 | 5 | 1 | 0 |

JD is the only “source” besides the profile. Voices review bullets for fabrication, not web corroboration of employment (T4 owner assertions still cannot be invented).
- Budget: small `16 / 480 / 4`; medium `24 / 720 / 6`; high `40 / 900 / 10`; limitless capped at high.
- Deviations: default intensity small; web search not used for employment facts.

#### 3. Data sources and knowledge bases
- Canonical authorities: `profile.yaml` / `x_master` / `x_metrics` (T4 owner SSOT). JD (T4 or T0 if fetched — this REUSE workflow does not require fetch; paste is enough). RenderCV/JSON Resume schemas (tooling T0 for layout rules). ATS rules in `skills/cv-studio/references/ats-rules.md` (skill reference, not a web claim).
- `sources.min_tier` T4 for owner history; no web floor for style. `min_independent` 1. `recency_max_days` null (file hash).
- Domain data: none.
- Basic Memory: `memory.capture: decisions` — e.g. chosen theme / which `x_targets` id was used — not raw CV PII.
- Cache: none shared for PII profile. Run-dir only.
- Paywall: none.
- Deviations: none. Visual CV **MUST NOT** be treated as the ATS authority.

#### 4. Tool chain and mechanisms
- Required: `fs.read`, `fs.write`; cv-studio scripts as local tools mapped to `doc.convert`/`doc.extract_text` only where PDF text is checked — the **canonical mechanic** is `cvstudio.py` (`validate` → zero-fab lint → RenderCV render → PyMuPDF self-check). `llm.rewrite` **only** to compress `x_master` notes into bullets (never invent).
- Optional: `llm.extract` for JD keywords (`tailor`); `doc.convert` if a posting demands DOCX (rare); design-studio/figma **only** when `visual_portfolio=true` (separate artifact); `web.fetch` not required.
- Provider hints: local cv-studio venv. **MUST NOT** create a new editor skill. **MUST NOT** alias to `source-command-resume-session`. **MUST NOT** emit multi-column/image-only ATS PDFs.
- Mechanism: validate profile → optionally tailor (keyword 3-place map: skills, title line, proving bullet — no stuffing; falsity forbidden) → rewrite bullets from `x_master` with numbers only from `x_metrics` → build tagged single-column PDF → self-check text layer → diff vs `prior_pdf` → optional JSON Resume export (`x_` stripped). Voices: bullet writer, fabrication auditor, ATS keyword coverage (advisory vs tailor-report numbers).
- Reuse note: **catalog alias**. Entire pipeline already exists in cv-studio. This workflow adds registry/risk/gates only (`SH-DUP-5`: if delta were larger, action would not be REUSE).

#### 5. Internal data structures / schemas
- Node outputs: `TailorReport`, `BulletDiff`, `AtsBuildResult`, `ResumeEditResult`.
- Shared schemas unchanged: §6.
- Extension: `AtsBuildResult.text_layer_contains[]` (name, email, companies, institutions). Specific to self-check, not ArtifactManifest.
- Declared artifacts: `*_CV.pdf` (required for ats/build); `tailor-report.md` (required if tailor); `changes.md` (required); optional `profile.resume.json` (JSON Resume, `x_` stripped); optional visual portfolio path **separate**.
- Schema example:

```json
{
  "schema_version": 1,
  "build_status": "SUCCESS",
  "pdf_path": "out/Name_CV.pdf",
  "pdf_hash": "sha256:e4c0...",
  "theme": "classic",
  "single_column": true,
  "selectable_text": true,
  "selfcheck": {
    "name": true,
    "email": true,
    "companies": true,
    "institutions": true
  },
  "zero_fab_unresolved": 0,
  "visual_replaced_ats": false
}
```

#### 6. Step-by-step execution flow
- Engine: simple.
- Lifecycle phases used: `discover`, `execute`, `quality-review`, `capture` (transform). Include `spec-review` when tailor/JD present.
- Numbered walkthrough:
  1. `load_profile` (discover, tool, `fs.read`)
  2. `validate` (discover, gate, cv-studio validate)
  3. `optional_tailor` (execute, tool, cv-studio tailor + optional `llm.extract`)
  4. `rewrite_bullets` (execute, llm, `llm.rewrite`) from `x_master` only
  5. `revalidate` (execute, gate, validate) → unresolved zero-fab warnings block ship
  6. `build_pdf` (execute, tool, cv-studio build / RenderCV)
  7. `selfcheck` (quality-review, gate, cv-studio selfcheck / PyMuPDF)
  8. `change_summary` (quality-review, tool, local diff vs `prior_pdf`)
  9. `optional_json` (execute, tool, cv-studio json)
  10. `optional_visual_route` (execute, tool, none) → pointer to design-studio; **does not overwrite ATS PDF**
  11. `export` (capture, export, `fs.write`) `_v2` if needed (`SH-UX-8`)
- Branches: no JD → skip tailor. `visual_portfolio` cannot skip ATS build when the owner asked for a submitted CV.
- Artifacts: PDF + reports. Checkpoint after `validate` and after `build_pdf`.
- Approval: `deterministic` + `human_required: 1` before the owner submits (submit is R3 outside). `panel_required: false`. Blocking: selfcheck fail; unresolved zero-fab; graphic-only PDF as submitted artifact.
- Resume: reuse PDF if profile+theme+JD hashes unchanged; otherwise rebuild. Never overwrite source `profile.yaml` without `_v2` copy.

#### 7. Output format and UX behavior
- Result: clean ATS PDF + change-tracked summary (added/removed keywords, bullet rewrites with `x_master` refs) + tailor % if applicable. Evidence: self-check receipt. Uncertainty: JD terms not honestly mappable (`unmapped`, not stuffed). Next actions: submit yourself; visual portfolio separately if requested.
- Export: PDF + `md` · `active_project_docs` or project `out/` · naming `resume-ats_{YYYY-MM-DD}` / RenderCV `First_Last_Resume.pdf` convention · language `en` (RO content allowed inside profile).
- Progress: build may exceed 60 s — heartbeat. Preview: theme, tailor on/off, visual not replacing ATS.
- Citations: JD keywords are not web citations; optional company name left as in JD. No fake metrics cites.
- Degradation UX: cv-studio venv missing → `FAILED_TO_RUN: cv-studio scripts unavailable; I will not substitute an unvalidated graphic PDF.` RenderCV fail → `FAILED:` from the script, not a silent Word export.
- Deviations: PDF primary artifact; change-tracked summary required even on REUSE.

#### 8. Logging, validation, and safety
- Controls: `SH-SEC-INJ` (JD), `SH-SEC-REDACT`, `SH-SEC-CRED`. No browser. No SSRF unless someone later adds JD URL fetch (not required).
- Disclaimers: `DISC-CAREER-1`.
- Risk: R1; profile/CV `PII`. Submit R3 outside.
- Gates: `reconciliation_survey`, `zero_fabrication_lint`, `ats_selfcheck`, `single_column_selectable_text`, `visual_not_replacing_ats`, `not_resume_session_alias`. `citation_coverage` N/A for purely T4 owner prose unless JD-sourced company claims are added — if added, they must be cited or omitted.
- Validation: schema + zero-fab + RenderCV + PyMuPDF chain (cv-studio order). Theme ∈ allowed enum.
- Failure table:

| Scenario | Error class | Behavior | User-visible message |
|---|---|---|---|
| Unsourced metric in a bullet | `VALIDATION` | Block ship | `Resolve zero-fabrication warnings; I will not ship unsourced numbers.` |
| Self-check missing employer name in text layer | `VALIDATION` | `FAILED:` | `ATS text layer missing a company name; PDF not accepted.` |
| Request for multi-column graphic as the submitted CV | `POLICY` | Keep ATS path; offer visual separately | `The submitted CV stays single-column selectable text. Visual portfolio is a separate artifact.` |
| Alias to resume-session | `POLICY` | Refuse routing | `This is cv-studio, not session recovery.` |
| Overwrite profile.yaml | `POLICY` | Write `_v2` | `Existing files are not overwritten.` |

- Logging: extra `build_status`, `selfcheck_pass`, `theme`, `tailor_keyword_pct`.
- Tests: happy-path `assets/sample-profile.yaml` build (`SUCCESS:` + self-check) as fixture pointer; degraded `fixtures/WF-33/missing_x_master.json`; safety `fixtures/WF-33/graphic_ats_requested.json` and `fixtures/WF-33/resume_session_alias.json`. Contracts: cv-studio validate/build/selfcheck. Golden: `golden/WF-33/changes.md` (structural, not byte-identical PDF unless cassette).
- Deviations: none vs cv-studio acceptance; this part only adds catalog/safety envelope.

---

## Conformance receipt (mechanical)

Lint against Part 00 `SH-TMPL-7` was re-run on this file after write. Provenance: `disk-verified` (file re-read; `####` headings extracted and compared by exact string equality).

| Check | Result |
|---|---|
| Path | `C:\Users\Prekzursil\.agents\PERPLEXITY-WORKFLOWS-PART-04-CAREER_2026-08-29.md` |
| Workflows in this part | **8**: WF-25, WF-26, WF-27, WF-28, WF-29, WF-30, WF-32, WF-33 |
| WF-31 / WF-34 as workflow headings | **0** (neighbours cited only; they belong in Part 05) |
| `####` headings per workflow | **8 each, 64 total**, verbatim and in order |
| Extra / orphan `####` | **0** |
| Heading strings | Exact match to Part 00 §21.2 (including “behavior”, not “behaviour”) |
| Reconciliation actions | UPGRADE, UPGRADE, REUSE, COMPOSE, COMPOSE, UPGRADE, COMPOSE, REUSE (copied from matrix) |
| Canonical profile owner | `cv-studio` `profile.yaml` / `x_master` / `x_metrics` only |
| LinkedIn MCP as alumni/job search | Not claimed; runtime/auth/live API `NOT-CHECKED` |

### Blockers / NOT-CHECKED (implementation, not this document)

1. `safety/disclaimers.yaml` is absent — `DISC-CAREER-1` and `DISC-IMAGE-SYNTHETIC-1` must be added before runs can render disclaimers (`SH-RISK-3`). Until then disclaimer gates are `NOT-CHECKED`.
2. LinkedIn/Indeed/Handshake official APIs and MCP adapters are **absent/deferred** from the 40-record registry.
3. Recovered LinkedIn MCP: source + 82 offline tests only; **registration, auth, live API `NOT-CHECKED`**; cannot search alumni.
4. `data.occupations` / `data.labor_statistics` / `data.job_postings` adapters are not live REG servers — official HTTPS/`web.fetch` is the fallback.
5. cv-studio venv presence on a given run host is a precondition, not proven by this file.
6. Two-party R2 human independence is typically **not** achievable in a single-owner household — runs must record that gap (GATE §6), not substitute a model panel.

This file is documentation only. It does not implement skills, register MCP servers, or create commits.
