# Perplexity Workflows — Mandatory Reuse and MCP Reconciliation Matrix

Date: 29.08.2026  
Status: DESIGN — documentation only; no skill, MCP, router, script, or registry changes  
Scope: WF-01 through WF-40 from `PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md`

## 1. Decision rule and executive census

Every workflow has exactly one primary implementation action:

- **REUSE** — the existing canonical capability already covers the workflow; add only catalog/launcher metadata.
- **UPGRADE** — extend one existing canonical owner with a bounded mode or adapter; do not create a sibling skill.
- **COMPOSE** — make a thin workflow recipe from existing leaves; the recipe owns sequencing, not duplicate logic.
- **MERGE/ALIAS** — map the catalog name to an existing owner or one of its modes; no new implementation surface.
- **RECOVER** — locate and reconcile a remembered preserved capability before considering replacement.
- **NEW** — no adequate canonical domain owner exists; create one thin owner only after the recovery and duplicate checks pass.

### Action census

| Action | Count | Workflow IDs |
| --- | ---: | --- |
| REUSE | 7 | WF-01, WF-02, WF-05, WF-13, WF-18, WF-27, WF-33 |
| UPGRADE | 6 | WF-04, WF-16, WF-25, WF-26, WF-30, WF-34 |
| COMPOSE | 14 | WF-06, WF-07, WF-10, WF-11, WF-12, WF-14, WF-15, WF-17, WF-19, WF-20, WF-28, WF-29, WF-32, WF-37 |
| MERGE/ALIAS | 9 | WF-03, WF-09, WF-22, WF-23, WF-24, WF-36, WF-38, WF-39, WF-40 |
| RECOVER | 0 | None |
| NEW | 4 | WF-08, WF-21, WF-31, WF-35 |
| **Total** | **40** | **WF-01 through WF-40 exactly once** |

### MCP-state census

The canonical registry contains **40** server records. Its Cursor partition is exact:

| MCP state | Count | Assets |
| --- | ---: | --- |
| Cursor-active configuration | 6 | `agent-mail`, `basic-memory`, `chrome-devtools`, `context7`, `firecrawl`, `playwright` |
| Cursor plugin-managed | 1 | `tavily` |
| Parked but preserved snapshot | 31 | The exact names listed in §4 |
| Disabled/denied | 2 | `markitdown`, `meta-tool` |
| **Canonical registry total** | **40** | **6 + 1 + 31 + 2** |

“Cursor-active” means mounted in `.cursor\mcp.json`, not proven healthy for every run. Live health still requires preflight. Provider names referenced by skills but absent from the 40-record registry are reported separately as **absent/deferred** and are not forced into this total.

## 2. Evidence key

The compact paths below are used in the matrix:

- **RISK** — `C:\Users\Prekzursil\.agents\PERPLEXITY-WORKFLOWS-SOURCE-RISK-MATRIX_2026-08-29.md`
- **DEC** — `C:\Users\Prekzursil\.agents\AUTOMATION-SUITE-DECISIONS_2026-08-29.md`
- **GATE** — `C:\Users\Prekzursil\.agents\RESEARCH-APPROVAL-GATES_2026-08-29.md`
- **REG** — `C:\Users\Prekzursil\.agents\agents.json`
- **CUR** — `C:\Users\Prekzursil\.cursor\mcp.json`
- **PARK** — `C:\Users\Prekzursil\.agents\mcp-cursor-parked-31.json`
- **MERGE** — `C:\Users\Prekzursil\.agents\scripts\merge_generated_cursor_mcp.py`
- **INDEX** — `C:\Users\Prekzursil\.agents\skills-index.md`
- Skill paths are under `C:\Users\Prekzursil\.agents\skills\<name>\SKILL.md`.

## 3. Mandatory 40-workflow reuse matrix

| ID | Workflow | Existing skills/scripts | Existing MCP/providers and observed state | Action | Canonical owner skill/workflow | Specific delta needed | Duplicate surfaces to avoid | Confidence / evidence path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WF-01 | Prompt refinement | `prompt-optimizer`; `claude-prompt-forge` for long autonomous prompts | No MCP required | **REUSE** | `prompt-optimizer` | Add catalog alias and RISK D9 prompt-injection/secret checks in launcher metadata only | A second “prompt refinement” skill; executing the optimized prompt inside this advisory skill | High — INDEX; `skills\prompt-optimizer\SKILL.md`; RISK WF-01 |
| WF-02 | Background removal | `imagegen` and `scripts/image_gen.py`; optional `accurate-grok-imagine` | OpenAI Image API is direct, not a canonical MCP; `fal-ai` is absent/deferred | **REUSE** | `imagegen` edit mode `background-extraction` | Catalog preset plus D8 rights, hash-chain, face/identity, and watermark checks | Standalone background-removal skill or MCP; duplicating image edit code | High — INDEX; `skills\imagegen\SKILL.md`; RISK WF-02 |
| WF-03 | Message polish | `humanizer`; `agentic-humanizer` only when the five-pass/voice workflow is requested | No MCP required; optional Slop-or-Not surface is not in REG | **MERGE/ALIAS** | `humanizer` | Alias “message polish” to light editing; escalate to `agentic-humanizer` only by explicit mode; never send | A third polish/rewriter skill; treating draft generation as permission to send | High — INDEX; `skills\humanizer\SKILL.md`; `skills\agentic-humanizer\SKILL.md`; RISK WF-03 |
| WF-04 | Research update (clinical) | `deep-research`; `biomedical-paper-triage`; `scholarly-literature-review`; `institutional-literature-access` | `firecrawl` active; `tavily` plugin-managed; `huggingface` parked; `scholarly-access`, `tooluniverse`, `perplexity`, `exa`, `searxng` absent from REG | **UPGRADE** | `deep-research` clinical-update mode | Add D1 authority map, PMID/NCT/full-text receipts, claim-type TTLs, retraction/guideline-current checks, P4-safe query logging | New “clinical deep research” engine; model consensus as medical evidence | High — RISK D1/WF-04; `skills\deep-research\SKILL.md`; biomedical skill files; REG/CUR/PARK |
| WF-05 | Website audit | `ui-audit` scripts; `design-studio audit`; `playwright` | `playwright` and `chrome-devtools` active; `firecrawl` active for public fetches | **REUSE** | `ui-audit` | Catalog alias; launcher must enforce the browser a/b/c profile record before navigation and owner-site scope before active testing | New website-audit skill; using `design-studio` to duplicate deterministic audit gates | High — `skills\ui-audit\SKILL.md`; `skills\design-studio\SKILL.md`; RISK WF-05; CUR |
| WF-06 | Evidence brief (medical) | `evidence-ledger-synthesis`; `deep-research`; `biomedical-paper-triage`; `pdf-reader` convention | `firecrawl` active; `tavily` plugin-managed; `pdf-reader` parked; scholarly providers named by skills are absent/deferred | **COMPOSE** | `deep-research` medical-brief recipe | Sequence question/PICO, source retrieval, literal full-text grounding, claim ledger, D1 disclaimer, and R2 review; persist deterministic receipts | A monolithic medical-brief skill that reimplements search, PDF grounding, or the ledger | High — RISK D1/WF-06; `skills\evidence-ledger-synthesis\SKILL.md`; `skills\pdf-reader\SKILL.md`; GATE |
| WF-07 | Medical evidence council | `council`; WF-06 recipe; approval-gate protocol | Same research providers as WF-06; multi-model lanes are agents/providers, not corroborating sources | **COMPOSE** | WF-06 medical-brief recipe plus `council` | Require evidence brief first; voices discover dissent; deterministic receipts and clinician/owner gates remain authoritative | Separate “medical council” evidence engine; majority-vote clearance | High — GATE; DEC G-7/G-11; `skills\council\SKILL.md`; RISK WF-07 |
| WF-08 | SEO keyword research | `deep-research`; `firecrawl`; `data-scraper-agent` patterns; no dedicated SEO owner found | `firecrawl` active; `tavily` plugin-managed; `apify`/`scrapegraph` parked; Google Ads/GSC provider absent/deferred | **NEW** | One thin `seo-keyword-workflow` owner | Create one official-data-first recipe with geo/language/date/match-type schema, GSC/Keyword Planner adapter boundary, SERP snapshot, and `VENDOR-ESTIMATE` labeling | Separate SEO-research, SERP, and keyword-volume skills; stealth SERP scraper | Medium-high — RISK D4/WF-08; INDEX has no SEO owner; targeted skill search; REG/CUR/PARK |
| WF-09 | Keyword generator (Google Ads) | WF-08 owner; generic prompt/text generation | Google Ads/Keyword Planner API absent/deferred; browser providers active but not a substitute for official account data | **MERGE/ALIAS** | `seo-keyword-workflow` ads mode | Add seed expansion and official metrics pull behind account consent; drafts remain usable without spend/write permission | Separate Google-Ads-keyword skill; inventing CPC/volume; campaign-launch code | High — RISK WF-09/D4; WF-08 reconciliation; REG shows no Google Ads MCP |
| WF-10 | Product teardown | `deep-research`; `ui-audit`; `design-studio audit`; `firecrawl` | `firecrawl`, `playwright`, `chrome-devtools` active; `apify`/`scrapegraph` parked | **COMPOSE** | Product-teardown recipe owned by `deep-research` with `ui-audit` leaf | Combine current public-product facts, UI evidence, pricing/legal-page citations, and dated competitor observations | Standalone teardown crawler; copying `ui-audit`; exploit/security testing under a product-review label | High — RISK D7/WF-10; relevant skill files; CUR/PARK |
| WF-11 | Brand inspiration | `design-studio direct`; `ui-ux-pro-max`; `imagegen`; `design-system` | Browser MCPs active if public references are fetched; OpenAI image direct API; `fal-ai` absent/deferred | **COMPOSE** | `design-studio direct` recipe | Add rights/source manifest, brand-vs-reference separation, and no-clone decision record before image exploration | New brand-inspiration skill; copied competitor kits; making generated inspiration the brand SSOT | High — RISK WF-11; `skills\design-studio\SKILL.md`; `skills\ui-ux-pro-max\SKILL.md`; `skills\imagegen\SKILL.md` |
| WF-12 | Store optimizer | `ui-audit`; `design-studio`; `deep-research`; `design-system` | Browser and Firecrawl MCPs active; analytics/Shopify-specific MCP absent/deferred | **COMPOSE** | `design-studio audit` commerce recipe | Add owner-property proof, product/price TTL, analytics PII minimization, and production-change R2 gate | New store-audit engine; production CMS writes; duplicating UI and research leaves | Medium-high — RISK D7/WF-12; design skill files; CUR/REG |
| WF-13 | Product photos | `imagegen` product-mockup mode; `accurate-grok-imagine`; optional `fal-ai-media` | OpenAI/Grok direct provider paths; `fal-ai` MCP absent/deferred | **REUSE** | `imagegen` | Add catalog preset with input-rights/license, seed/provider manifest, product-fidelity invariants, and commercial-use review | New product-photo skill; separate background/edit pipeline | High — `skills\imagegen\SKILL.md`; `skills\accurate-grok-imagine\SKILL.md`; RISK WF-13 |
| WF-14 | Post creator | `humanizer`; `agentic-humanizer`; `imagegen`; `x-api` for an explicitly selected platform | X uses direct API, not REG; image provider is direct; no general social-post MCP in REG | **COMPOSE** | Draft-only post-creator recipe | Compose copy, voice, optional image, platform constraints, source checks, and owner publish gate; never infer permission to post | One skill per social network; auto-publish; fake testimonials | Medium-high — RISK WF-14; humanizer/imagegen/x-api skill files; REG |
| WF-15 | Document summary | `pdf-reader`; `long-pdf-evidence-synthesizer`; `doc`; native file readers | `pdf-reader` parked; `markitdown` disabled/denied; no need to activate either for plain text/DOCX | **COMPOSE** | Document-summary recipe selecting the existing format leaf | Dispatch by file type, require page/span grounding, hash source, inherit P4/R2, and use local parsing before cloud | Generic summarizer duplicating PDF/DOCX logic; treating disabled MarkItDown as available | High — RISK WF-15/D9; `skills\pdf-reader\SKILL.md`; `skills\doc\SKILL.md`; REG/PARK |
| WF-16 | Filetype converter | `nutrient-document-processing`; `doc`; `pdf`; `spreadsheet`; `slides`; `video-convert` | `markitdown` disabled/denied; `nutrient-dws` absent/deferred; local CLIs are not MCPs | **UPGRADE** | `nutrient-document-processing` as a local-first conversion dispatcher | Preserve its cloud API benefit but add local-first format routing, PII consent gate, macro refusal, output `_v2` naming, hash/round-trip checks | A new converter for each format; silently removing Nutrient; enabling MarkItDown as a shortcut | Medium-high — RISK WF-16; `skills\nutrient-document-processing\SKILL.md`; document skill files; REG |
| WF-17 | Memo draft (investment) | `deep-research`; `evidence-ledger-synthesis`; document output skills | `firecrawl` active; `tavily` plugin-managed; direct SEC/EDGAR and official-series HTTPS preferred; no finance MCP in REG | **COMPOSE** | Investment-memo recipe owned by `deep-research` | Add CIK/accession/series schema, latest-vs-immutable TTL distinction, figure-to-filing ledger, delayed-price labeling, and R2/R3 gates | Standalone market-data scraper; treating news/IR copy as independent of EDGAR; trading action | High — RISK D3/WF-17; deep-research/evidence-ledger skills; REG |
| WF-18 | Slide creation | `slides` and bundled render, overflow, montage, and font scripts | No MCP required; image generation remains an optional existing provider | **REUSE** | `slides` | Catalog alias; inherit source citations and P4/R2 classification; require rendered visual/overflow validation | New slide-builder skill; `python-pptx` generation fork; unvalidated deck | High — `skills\slides\SKILL.md`; RISK WF-18 |
| WF-19 | Website builder | `prototype`; `design-studio`; `ui-ux-pro-max`; `clone-website` only for licensed/reference extraction | `playwright`/`chrome-devtools` active; `firecrawl` active; deployment providers are separate | **COMPOSE** | Website-builder recipe over `prototype` then `design-studio` | Define stack/project owner, build from owner requirements/design tokens, validate UI, prohibit competitor cloning, and keep publish R3 separate | A mega “website builder” skill; using `clone-website` as default; silently deploying | High — RISK WF-19; `skills\prototype\SKILL.md`; design and clone skill files |
| WF-20 | Final pass (document QA) | `doc`; `pdf-reader`; `humanizer`; `slides`/`spreadsheet` validators by format | `pdf-reader` parked; `markitdown` disabled/denied; no general QA MCP needed | **COMPOSE** | Format-aware final-pass recipe | Select format leaf; check source hash, layout, citations, unsupported claims, placeholders, and inherited legal/medical risk; do not claim professional clearance | New final-pass skill per format; conflating prose polish with factual/legal/medical review | High — RISK WF-20; document/humanizer skill files; REG/PARK |
| WF-21 | Legal research | `deep-research`; `evidence-ledger-synthesis`; `pdf-reader`; no jurisdiction-aware legal owner found | `firecrawl` active; `tavily` plugin-managed; `pdf-reader` parked; official RO/EU/court portals are direct HTTPS, no legal MCP in REG | **NEW** | One thin `legal-workflow` owner with research/draft/review modes | Implement jurisdiction ASK-gate, official-instrument adapter map, CELEX/ECLI/gazette pin cites, in-force TTL, and R2/R3 disclaimer/authority boundary | Three separate legal skills; law-blog fallback; cross-jurisdiction template reuse | Medium-high — RISK D2/WF-21; INDEX and targeted legal search show no owner; REG/CUR/PARK |
| WF-22 | Draft a contract | `legal-workflow` owner from WF-21; `doc`; `evidence-ledger-synthesis` | No contract MCP required; official legal sources via WF-21; signing providers are out of scope | **MERGE/ALIAS** | `legal-workflow` draft mode | Clause-to-jurisdiction/source map, owner facts, unverified-clause ledger, DOCX render check, and explicit no-send/no-sign gate | Standalone contract-generator skill; “standard clause” claims without source; e-sign integration | High — RISK WF-22; WF-21 reconciliation; `skills\doc\SKILL.md` |
| WF-23 | Contract review | `legal-workflow` owner from WF-21; `pdf-reader`; `doc` | `pdf-reader` parked; `markitdown` disabled/denied; no need for a new contract MCP | **MERGE/ALIAS** | `legal-workflow` review mode | Sandbox/untrusted-document parse, clause locator, issue/source split, counterparty PII controls, and sign R3 gate | Separate contract-review skill; following document-embedded instructions; auto-accept/sign | High — RISK WF-23; `skills\pdf-reader\SKILL.md`; REG/PARK |
| WF-24 | Thumbnail creator | `imagegen`; `fal-ai-media`; `accurate-grok-imagine` | OpenAI/Grok direct providers; `fal-ai` absent/deferred | **MERGE/ALIAS** | `imagegen` thumbnail preset | Add aspect/text-safe-area/legibility preset, rights manifest, and platform-size validation | Dedicated thumbnail skill/MCP; duplicate image provider wrappers | High — RISK WF-24; image skill files; INDEX |
| WF-25 | Job finder | `cv-studio` profile/tailor foundation; `deep-research`; `browser-rail`/Playwright for owner-present platform use | `firecrawl`, `playwright`, `chrome-devtools` active; `tavily` plugin-managed; LinkedIn/Indeed/Handshake providers absent/deferred | **UPGRADE** | `cv-studio` jobs mode | Use `profile.yaml` goals/skills, verify each vacancy on employer career page, record requisition/12h TTL, and keep platform browsing consent-gated | New job-profile schema; one finder per board; bulk LinkedIn scrape; application submission | High — RISK D5/WF-25; `skills\cv-studio\SKILL.md`; deep-research/browser skills; REG |
| WF-26 | Interview prep | `cv-studio`; `deep-research`; `humanizer` optional | Public company research via active Firecrawl/Tavily; no interview MCP needed | **UPGRADE** | `cv-studio` interview mode | Generate questions and proof points only from `profile.yaml`, `x_master`, and verified JD/company facts; flag gaps | Separate interview-profile skill; fabricated biography/achievements | High — RISK WF-26; `skills\cv-studio\SKILL.md`; RISK D5 zero-fabrication rules |
| WF-27 | Cover letter generator | `cv-studio` cover mode already specified | No MCP required; optional current company/JD research uses active Firecrawl | **REUSE** | `cv-studio` cover mode | Only catalog alias and source-risk metadata; keep zero-fabrication and owner-send gate | Any separate cover-letter skill; a second career profile; invented metrics | Very high — `skills\cv-studio\SKILL.md` lines 32–40 and 75–79; RISK WF-27 |
| WF-28 | LinkedIn headshot generator | `cv-studio` for professional positioning; `imagegen`/`accurate-grok-imagine` for identity-preserving image work | Image providers are direct; no LinkedIn write MCP; `fal-ai` absent/deferred | **COMPOSE** | `cv-studio` identity-asset recipe with `imagegen` leaf | Pass target-role/brand context from the same profile; enforce owner-face consent, P6 handling, provenance, and AI-generated disclosure | New headshot skill; scraping profile photos; live LinkedIn upload | High — RISK D8/WF-28; cv-studio and image skill files |
| WF-29 | Scholarship and fellowship finder | `cv-studio`; `deep-research`; `grant-proposal-architecture` | Active Firecrawl/Tavily for discovery; official funder pages are direct; no scholarship MCP | **COMPOSE** | `cv-studio` opportunities mode | Match one profile to official eligibility/deadline records, then hand selected opportunity to grant-proposal architecture; 24h deadline TTL | Separate scholarship profile/finder per funder; using blog lists as authority; portal submission | High — RISK WF-29; cv-studio/deep-research/grant skill files |
| WF-30 | Career explorer | `cv-studio`; `deep-research`; evidence-ledger pattern | Active web providers; ESCO/ISCO/COR/O*NET/Eurostat/INS/BLS are direct data sources; no labor MCP | **UPGRADE** | `cv-studio` career mode | Map profile skills to occupation codes and evidence-backed gaps; keep statistics separate from anecdote and preserve source release/date | New career-profile skill; unsupported salary/outcome promises | High — RISK WF-30/D5; `skills\cv-studio\SKILL.md`; `skills\deep-research\SKILL.md` |
| WF-31 | Internship housing finder | `deep-research`; `browser-rail`; Playwright; no housing-domain owner found | Browser/Firecrawl active; `apify`/`scrapegraph` parked; maps/transit/rental providers absent/deferred or direct | **NEW** | One thin `internship-housing-finder` workflow | Add 6h listing/rent TTL, university-first sources, listing ID/hash, map/transit version, fraud flags, P3 location controls, and pay/sign R3 gate | General housing scraper; board-specific skills; payment/messaging capability | Medium-high — RISK D6/WF-31; INDEX and targeted housing search show no owner; REG/CUR/PARK |
| WF-32 | Alumni finder | `cv-studio`; `deep-research`; `browser-rail`; recovered `tools\mcp\linkedin-mcp` source | Browser providers active; LinkedIn MCP is **RECOVERABLE/HEALTHY-SOURCE** outside current REG/CUR/PARK, but it has no alumni/search/Recruiter/Talent capability | **COMPOSE** | `cv-studio` alumni mode + `deep-research`/public search + owner-present browser verification | Compose public discovery and browser verification with P2 minimization; the recovered MCP is optional only for owner OIDC identity and own-post outreach; registration/auth/live API remain NOT-CHECKED | A new alumni or LinkedIn MCP; treating own-feed posting as alumni discovery; bulk profiles/dossiers; automated outreach | High for source/boundary, medium for runtime — recovered source and 82 offline tests in §7; REG/CUR/PARK absence; RISK WF-32 |
| WF-33 | Resume editor | `cv-studio` ATS, tailor, build, validate, selfcheck, JSON Resume export | No MCP required; RenderCV/JSON Resume/local scripts are the providers | **REUSE** | `cv-studio` ATS/tailor modes | Catalog alias only; retain one `profile.yaml`, `x_master`, `x_metrics`, selectable-text and zero-fabrication gates | New resume/CV editor skill; graphic ATS CV; `source-command-resume-session` | Very high — `skills\cv-studio\SKILL.md` lines 19–73 and 105–114; RISK WF-33 |
| WF-34 | Behavioral story generator | `cv-studio` `x_master` achievement bank and verified metrics | No MCP required | **UPGRADE** | `cv-studio` stories mode | Add STAR/CAR story rendering strictly from `x_master` and `x_metrics`, linked to target JD competencies; unverified facts stay prompts | Separate behavioral-story database/profile; invented impact numbers | High — cv-studio structured profile/zero-fabrication sections; RISK WF-34 |
| WF-35 | Health review | `deep-research`; `evidence-ledger-synthesis`; `pdf-reader`; biomedical skills; no personal-health owner found | `firecrawl` active; `tavily` plugin-managed; `pdf-reader` parked; scholarly/tooluniverse providers absent/deferred | **NEW** | One thin `health-review` owner with review/nutrition/labs/visit/fitness/sleep modes | Create local-P4 intake, document-vs-clinical-evidence separation, D1 source adapter, R2/R3 gates, required disclaimers, and no-diagnosis boundary | Six separate health skills; cloud PHI fan-out; model-as-clinician behavior | Medium-high — RISK D9-health/D1/WF-35; INDEX and targeted health search show biomedical research leaves but no personal-health owner |
| WF-36 | Nutrition planner | `health-review` owner from WF-35; `deep-research` clinical sources | Active web providers; no nutrition MCP required; scholarly providers absent/deferred | **MERGE/ALIAS** | `health-review` nutrition mode | Add dietary preferences/contraindication intake, source-labeled general planning, escalation for medical diets/eating-disorder/pregnancy context | Standalone nutrition-coach skill; treatment diet or supplement prescribing | High — RISK WF-36; WF-35 reconciliation |
| WF-37 | Lab results interpreter | `health-review`; `pdf-reader`; local OCR/parser when needed; biomedical evidence leaves | `pdf-reader` parked; `markitdown` disabled/denied; no lab MCP | **COMPOSE** | `health-review` labs mode with `pdf-reader`/local extraction leaf | Extract value/unit/range/flag and page before commentary; hash report; clinical thresholds require D1 cites; OCR uncertainty is visible | New lab-reader skill; enabling macros; invented ranges; raw P4 in logs | High — RISK WF-37/D9; `skills\pdf-reader\SKILL.md`; REG/PARK |
| WF-38 | Visit prep assistant | `health-review`; evidence-ledger/question-list pattern | Optional patient-portal browser uses active Playwright/Chrome only after profile gate; no portal MCP | **MERGE/ALIAS** | `health-review` visit-prep mode | Turn owner facts into prioritized questions/timeline; no diagnosis; portal upload/send remains R3 and explicit profile (a) only | Separate visit-prep skill; silent patient-portal login; sending records | High — RISK WF-38 and global browser policy; CUR |
| WF-39 | Fitness coach | `health-review`; evidence-ledger and telemetry intake pattern | No MCP required; device exports are local T4; literature uses active web providers if needed | **MERGE/ALIAS** | `health-review` fitness mode | Separate telemetry, guideline evidence, and suggestions; screen injury/condition red flags; retain P4 locally | Standalone fitness-coach profile; medical clearance claims | High — RISK WF-39/D9; WF-35 reconciliation |
| WF-40 | Sleep & recovery coach | `health-review`; evidence-ledger and telemetry intake pattern | No MCP required; wearable exports are local T4; literature uses active web providers if needed | **MERGE/ALIAS** | `health-review` sleep mode | Record export time, distinguish device estimates from clinical facts, flag suspected disorder for clinician review, and keep P4 local | Standalone sleep profile/skill; diagnosis or treatment claims | High — RISK WF-40/D9; WF-35 reconciliation |

## 4. Exact MCP topology and discrepancies

### Canonical 40-record partition

1. **Cursor-active (6):** `agent-mail`, `basic-memory`, `chrome-devtools`, `context7`, `firecrawl`, `playwright`.
2. **Cursor plugin-managed (1):** `tavily`. `MERGE` explicitly excludes it to prevent a double mount.
3. **Parked but preserved (31):** `apify`, `binary-ninja-mcp`, `browserstack`, `cheatengine`, `claude-code-mcp`, `codacy`, `codecov`, `deepscan`, `deepsource`, `digitalocean`, `docker`, `excel`, `frida-mcp`, `ghidra-mcp`, `github`, `github_cli`, `hexstrike-ai`, `huggingface`, `ida-pro-mcp`, `linear`, `mcp-graphql`, `notion`, `pdf-reader`, `postgres`, `qlty`, `ralph-orchestrator`, `repomix`, `scrapegraph`, `semgrep`, `sentry`, `sonarqube`.
4. **Disabled/denied (2):** `markitdown`, `meta-tool`. They remain registry assets but are omitted from Cursor.

This partition was mechanically checked by comparing the name sets in REG, CUR, and PARK plus the plugin/denied constants in MERGE: it has 40 unique names, no missing registry name, and no extra partition name.

### Count and documentation discrepancies that must remain visible

- `mcp-code-orchestrate` refers to a “39-server MCP fleet,” while REG currently contains **40** records. The current machine-readable registry wins; the prose count is stale.
- `deep-research` documents providers including `exa`, `perplexity`, `scholarly-access`, `tooluniverse`, `searxng`, and `cve-mcp`; none is a current REG server. They are **absent/deferred from this registry**, even if another runtime/plugin once exposed one.
- `fal-ai`, `nutrient-dws`, Google Ads/GSC, job-board, maps/transit, legal-research, finance/market-data, and lab providers are also absent from REG. Direct HTTPS/API/CLI access is a separate provider path, not proof of an MCP asset.
- LinkedIn is a special reconciled case: it is absent from current REG/CUR/PARK but has **RECOVERABLE/HEALTHY-SOURCE** in the tracked private repository and an older canonical entry. It is not part of the current 40-record total until a future integration change is approved.
- `mixpanel` is explicitly kept absent by MERGE and is not a member of the canonical 40.
- Therefore, **40 is the registry asset count, not the count of every provider named in every skill**. Adding absent/deferred references to 40 would be a false total.

## 5. Why there is no general on-demand MCP router today

The estate has useful partial mechanisms, but no single component currently performs registry-wide capability resolution plus lifecycle:

- **`deep-research\references\research_harness\routing.py`** is a research-local capability table. It chooses among research providers already represented as live/down statuses. It does not own the 40-record registry, activate PARK entries, enforce cross-domain browser/profile rules, or restore configuration after a run.
- **`mcp-code-orchestrate`** moves repeated same-shape calls into one script to reduce context and startup overhead. It is a fan-out execution pattern, not provider discovery, policy resolution, credential brokerage, or fleet lifecycle.
- **`agents sync` / `sync_shared_state.ps1`** statically validates and materializes canonical configuration into runtime-specific files. The custom Cursor merge deliberately emits only six keep-list servers. Sync is not a per-request router and must not be repurposed to toggle PARK entries.
- **Cursor dynamic tool discovery** can discover schemas in namespaces that the current Cursor session already exposes. It does not prove a parked server is installed/healthy, start or stop it, import credentials, or make a missing provider exist.
- **`meta-tool`** is disabled/denied. Even when enabled, its recorded purpose is a search/describe/execute gateway for a bounded set of broad API servers (`codacy`, `sonarqube`, `github`, `linear`, `sentry`, `notion`), not a general 40-server lifecycle router.

The result is intentional static preservation plus manual/tool-specific activation, not an implemented unified on-demand MCP control plane.

## 6. Proposed non-destructive router contract — design only

No implementation is authorized by this document. A future launcher may satisfy G-1 only if it meets all of the following:

1. **Capability resolution:** accept a workflow capability, risk/domain, runtime, and execution mode; return ranked existing skills, direct providers, active MCPs, parked MCPs, and absent/deferred gaps. Prefer REUSE/UPGRADE/COMPOSE before NEW.
2. **Live preflight:** probe the selected provider cheaply and read-only; distinguish configured, installed, healthy, authenticated, quota-blocked, denied, and missing. A configured entry is never reported as live without the probe.
3. **On-demand lifecycle:** for a parked local server, create a run-scoped rendered configuration or child process without editing REG, CUR, or PARK; stop only the process the run started; never tear down shared singletons or GUI-owned servers.
4. **No credential copying:** pass only environment-variable names or native secret references to the child. Never print, persist, migrate, or duplicate values. Never rotate credentials.
5. **Visible fallback:** show primary and fallback before execution; log every provider/model/source-tier change. A denied, stale, quota-aborted, or failed preflight is not green.
6. **Process/RAM limits:** serialize heavy local work; keep at most one local `cursor-agent`; refuse worker start below 8 GB free RAM; enforce per-server private-byte and fleet-idle limits from REG; terminate only run-owned children.
7. **Browser profile gate:** before any browser capability, require the per-run a/b/c selection record; default to agent-persistent (b), never live/owner (a); owner-present for credential-bearing and ToS-restricted flows.
8. **Graceful restore:** snapshot only run-scoped state, close run-owned processes, verify shared services remain available, and leave canonical files byte-identical. On crash, replay an idempotent cleanup manifest.
9. **Audit log:** append workflow ID, capability, resolved owner, provider state, preflight result, browser choice, fallback, PID ownership, resource readings, start/stop, artifact hashes, and `disk-verified` versus `agent-claimed` provenance. Redact P2–P6 payloads.

### Reversibility and shadow-first condition

The first implementation must be **OFF**, then **SHADOW**: resolve and log what it would select without starting/stopping anything. Only measured agreement with operator choices and zero canonical-file drift may permit an opt-in active phase. Backup/restore targets would be named before implementation; the safest invariant is that REG, CUR, and PARK are never mutation targets during a run.

## 7. CV/résumé, LinkedIn, and career reconciliation

### One profile and one owner

`cv-studio` is the canonical owner for the career identity record. Its `profile.yaml` is a JSON Resume superset, with `x_master` as the only achievement source, `x_metrics` as the verified-number source, and `x_targets` for job descriptions. This proves direct reuse:

- **WF-33 Resume editor:** existing `ats`, `tailor`, `build`, `validate`, `selfcheck`, and JSON Resume export. No new resume editor.
- **WF-27 Cover letter:** existing `cover` mode already maps `x_master` achievements to the JD. No new cover-letter skill.
- **LinkedIn copy:** existing `linkedin` mode already produces headline, About, skills, and keyword-gap output. The skill itself states that a separate LinkedIn-copy skill would be catalogue tax.
- **WF-25 Job finder:** add a `jobs` mode to the same owner so role matching uses the same verified profile; discovery/revalidation is composed from research/browser leaves.
- **WF-26 Interview prep:** add an `interview` mode that consumes the same profile and target JD; no parallel biography store.
- **WF-29 Scholarship/fellowship finder:** compose official opportunity research and `grant-proposal-architecture` around the same profile.
- **WF-30 Career explorer:** add a `career` mode mapping the same skills/history to official occupation codes and data.
- **WF-32 Alumni finder:** compose an `alumni` mode from public research and owner-present browser verification around the same profile. The recovered LinkedIn MCP is not a discovery provider and does not change this recipe.
- **WF-34 Behavioral stories:** add a `stories` renderer over `x_master`/`x_metrics`; no separate story bank.
- **WF-28 LinkedIn headshot:** `imagegen` owns pixels and identity-edit invariants; `cv-studio` supplies target-role/brand context. Neither duplicates the other.

Existing ATS and designed-CV benefits remain: RenderCV remains the submitted, selectable-text path; `design-studio`/Figma or JSON Resume remains the human/portfolio path. The designed artifact must not replace the ATS artifact.

### Résumé/CV is not resume-session

`source-command-resume-session` loads `~/.claude/sessions/*-session.tmp` to continue agent work after a prior session. It does not parse employment history, produce a CV, tailor to a job, or own career data. Keep:

- `resume` / `CV` / `cover letter` / `LinkedIn copy` routed to `cv-studio`;
- `/resume-session` reserved for execution-context recovery;
- no alias from WF-33 to `source-command-resume-session`;
- no shared schema or storage between `profile.yaml` and session `.tmp` files.

### Recovered historical LinkedIn MCP asset and capability boundary

The historical asset is now classified **RECOVERABLE/HEALTHY-SOURCE**:

- Private-repository history verifies:
  - `469cf8370c49addbc8703de776ca252c39645395` — add the self-serve LinkedIn MCP server.
  - `f0501a293776ca83e2a5bb3e3ec64218e34cde89` — add its enable script.
  - `cb5dd9c7dcd2d09e07d4f5e922872493c22618b9` — register on the actual Claude surface and repair the interpreter path.
- Tracked source exists at `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\linkedin-mcp\`, including `server.py`, `linkedin_core.py`, setup/apply/enable scripts, and tests.
- The older `tools\mcp\canonical-mcp-servers.json` contains a `linkedin` stdio entry pointing to the tracked source.
- Current REG, CUR, and PARK contain no `linkedin` entry. No `C:\Users\Prekzursil\.local\opt\linkedin-mcp` install exists; the tracked README documents launching repository source with Python.
- Fresh offline verification against the tracked source completed with `C:\Python314\python.exe -m pytest -q -p no:cacheprovider`: **82 passed in 9.60s**.

This proves source presence and offline behavior only. **Runtime registration, LinkedIn app setup, credentials/authentication, stdio client integration, and live LinkedIn API calls remain NOT-CHECKED.** No end-to-end operation is claimed.

The capability boundary is explicit: the server supports self-serve OIDC identity plus posting and deleting content on the authenticated owner's own feed. LinkedIn alumni/profile search, Recruiter, Talent, Sales Navigator, organization, advertising, and other partner-gated APIs are deliberately not built. It therefore cannot discover alumni and is not the primary provider for WF-32.

## 8. LinkedIn MCP recovery/integration plan — design only

The asset has been recovered; future integration, if authorized, should be non-destructive and default-off:

1. Reconcile the older `linkedin` canonical entry into current REG, making `C:\Users\Prekzursil\.agents\agents.json` the SSOT. Point to tracked repository source or an approved isolated environment; do not invent a second LinkedIn server or copy credentials.
2. Add safe on-demand-router metadata: capability tags limited to owner identity and own-feed posting/deletion; owner-present writes; default-off lifecycle; run-owned process; env-variable **names** only; explicit statement that alumni/search/Recruiter/Talent are unavailable.
3. Keep Cursor static configuration unchanged unless a later owner decision explicitly targets Cursor. Do not place LinkedIn in the six-server always-active keep-list merely because source recovery succeeded.
4. Run registry validation, schema/parity tests, and sync dry-runs. Verify that adding a default-off record does not silently activate it or disturb the current 40-record partition until the approved registry change actually lands.
5. Run a no-secrets stdio initialize plus `tools/list` smoke against repository source. Confirm the server starts, lists only the documented tool surface, and reports missing environment variables safely. This is transport verification, not LinkedIn API verification.
6. Preserve owner-present/default-off write policy in every launcher route. Identity/readiness probes may be read-only; post/delete calls require an explicit per-run owner action and visible target/content preview.
7. If desired, the owner performs LinkedIn developer-app and token setup using the tracked SETUP instructions. Credentials remain in the environment/native secret path and are never copied into REG, logs, artifacts, or command arguments.
8. Only then run consented live identity and owner-feed smoke tests, recording API response and cleanup receipts. Partner-gated alumni/search/Recruiter/Talent capability remains out of scope even if owner-post operations succeed.

## 9. Assumption and adverse-evidence ledger

| Load-bearing assumption | Confidence | Strongest evidence against / falsifier |
| --- | --- | --- |
| REG is the current canonical 40-record MCP inventory and MERGE defines Cursor policy | High | A newer canonical registry or sync receipt showing a different source-of-truth or partition |
| The six entries in CUR are configured active, Tavily is plugin-managed, 31 are preserved, and two are denied | High | A name-set comparison with missing/extra names or Cursor settings showing Tavily is no longer plugin-provided |
| No general on-demand MCP lifecycle router currently exists in the inspected control plane | Medium-high | An executable registry-wide resolver outside the inspected files that can preflight, start/stop parked entries, restore state, and emit audit receipts |
| `cv-studio` is the canonical owner for CV, cover letter, LinkedIn copy, and the shared career profile | High | A newer approved owner skill with the same one-profile contract and explicit supersession record |
| The LinkedIn MCP is RECOVERABLE/HEALTHY-SOURCE but not runtime- or API-verified | High for source; low for live runtime | A failing clean offline test run would refute source health; successful registry, stdio, auth, and live API receipts would replace the NOT-CHECKED runtime states |
| The LinkedIn MCP cannot provide alumni discovery | High | A reviewed, authorized implementation plus LinkedIn-granted partner scopes exposing alumni/search/Recruiter/Talent tools; neither exists in the recovered source |
| Four NEW owners are the minimum non-duplicative set | Medium | Discovery of an existing jurisdiction-aware legal, official-metrics SEO, housing, or personal-health owner that satisfies the RISK matrix without duplicate state |

The strongest general reason **not** to implement any proposed UPGRADE/COMPOSE/NEW action is a recovered existing capability that already meets the acceptance criteria. Recovery and skill-stocktake must therefore precede implementation.

## 10. Acceptance criteria preventing future duplication

A future implementation or MCP proposal is rejected unless all applicable checks pass:

1. Every catalog workflow remains mapped exactly once to one primary action class and one canonical owner.
2. A scoped INDEX plus domain-term SKILL search and relevant Git-history/recovery search is attached before any NEW decision.
3. REUSE and MERGE/ALIAS create no skill body, provider wrapper, profile schema, or second state store.
4. UPGRADE adds a bounded mode/adapter to the named owner and preserves all existing benefits and invocation paths.
5. COMPOSE contains sequencing/policy only; leaf search, document, image, browser, design, and validation logic stays in existing skills/scripts.
6. The career family uses one `cv-studio` `profile.yaml`; no new résumé, cover-letter, LinkedIn-copy, interview-bio, or behavioral-story database is created.
7. `source-command-resume-session` remains lexically and functionally separate from résumé/CV workflows.
8. Legal uses one `legal-workflow` owner with research/draft/review modes; health uses one `health-review` owner with six modes; SEO/Ads uses one owner with modes.
9. No MCP is declared absent until REG, CUR, PARK, plugin state, and scoped repository history have been checked. Recovered, parked, and disabled assets are preserved, not duplicated or deleted.
10. No MCP is declared active or healthy merely because it is configured; a current read-only preflight receipt is required.
11. No workflow copies credentials, activates a denied server, silently selects browser profile (a), or silently changes provider/source/model tier.
12. No router implementation edits canonical config during a run; shadow-mode evidence and byte-identical restore proof precede opt-in lifecycle actions.
13. External send/post/apply/pay/sign/publish remains a separate R3 owner action; a draft workflow never absorbs it.
14. Source-risk requirements, claim-type TTLs, PII class, prompt-injection treatment, and GATE deterministic receipts are inherited by reference, not rewritten inconsistently.
15. The recovered LinkedIn MCP is integrated at most once, default-off, and never represented as an alumni/search/Recruiter/Talent provider; WF-32 remains a composed public-research/browser workflow.
16. Acceptance evidence names the final artifact path, hashes or re-reads it, and records NOT-CHECKED provider states instead of forcing counts or claiming completeness.

## 11. Verification summary

- Matrix rows: **40**, one each for **WF-01 through WF-40**.
- Action census: **7 REUSE + 6 UPGRADE + 14 COMPOSE + 9 MERGE/ALIAS + 0 RECOVER + 4 NEW = 40**.
- MCP topology: **40 canonical = 6 Cursor-active + 1 plugin-managed + 31 parked-preserved + 2 disabled/denied**.
- Historical LinkedIn status: **RECOVERABLE/HEALTHY-SOURCE** with 82 offline tests passing; current registry inclusion, stdio integration, authentication, and live API operation remain **NOT-CHECKED**. Its self-serve boundary excludes alumni/search/Recruiter/Talent APIs.
