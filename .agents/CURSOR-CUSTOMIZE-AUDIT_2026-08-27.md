# Cursor Customize + marketplace audit — 27.08.2026

Companion files: `CURSOR-MARKETPLACE-VISITED_2026-08-27.md` (visited-set), `.agents\skills\openrouter-routing\MAX-EFFORT-PLUGIN-CLEANUP_2026-08-27.md` (the "do" track).
Diagnosis context: screenshots 27.08 04:08–04:13 (MCPs tab User + project scopes; Plugins tab boltable+common; Bolt team marketplace; popular-skills stats).

---

## 1. Customize inventory (what exists where)

### Plugins

| Where | State |
| --- | --- |
| Cursor enable map `~\.cursor\settings.json` | 45 ids, **all `enabled: false`** (incl. the four pins added 27.08: compound-engineering, astronomer-data, canva, tavily). |
| Installed (Bolt team marketplace) | `common` 1.0.22 + `boltable` 1.0.3 — the only two under `plugins\marketplaces\...\bolt-technology-o\`. UI shows them because installed ≠ enabled. |
| Cursor-public cache | 181 catalog folders = marketplace index, NOT installs. Left intact (hard rule). |
| Bolt team marketplace | 25 plugin ids total; 5 absent from the enable map (comms-privacy-dev, analytics-engineering-tooling, micromobility-supply-chain-team, talent-management, central-fp-a) — team-managed, not pinned (outside pin list). |
| Claude `~\.claude\settings.json` `enabledPlugins` | ~100 entries; **10 true**: codex@openai-codex, hookify, ralph-loop, remember, skill-creator, superpowers (claude-plugins-official), claude-reflect, metaswarm, modern-web-guidance@googlechrome; agentbridge false (retired). |
| Codex `~\.codex\config.toml` `[plugins.*]` | ~70 entries, mix true/false (openai-bundled/curated + claude-cowork + claude-plugins-official mirrors). Codex-owned, not Cursor's concern. |

Shared-harness verdict: the **skills vault `.agents\skills` is the plugin surface that matters**; Cursor plugins stay a disabled shell except where a plugin ships something the vault lacks.

### MCPs

| Scope | Content |
| --- | --- |
| `.agents\agents.json` (SSOT) | 39 registry servers (apify … agent-mail). `integrations.enabled: []` — custom merge scripts only. |
| Cursor live `~\.cursor\mcp.json` | 6 always-on: agent-mail (8812), basic-memory (8765), chrome-devtools, context7, firecrawl, playwright. Parked 31 in `.agents\mcp-cursor-parked-31.json`. |
| Cursor **project scope** | Workspace root IS the home dir, so the *same* `~\.cursor\mcp.json` is read a second time as project config → the duplicate rows in the MCPs tab. Not a second file. |
| Claude | 40 servers via `merge_generated_claude_mcp.py` (registry targets). |
| Codex `[mcp_servers]` | 12: exa, kaggle (disabled), node_repl, deepwiki, scholarly-access, biomni-hub, burp, openaiDeveloperDocs, agent-mail, apify, basic-memory, github. |
| Plugin-provided MCP | All carriers (playwright, firecrawl, context7-plugin, canva, tavily…) pinned false — `.agents`-synced servers win. |

### Skills

- SSOT: `.agents\skills` → materialized to `~\.claude\skills` (~300 skills, incl. deep-research, grill-me, playwright, firecrawl…).
- Cursor-native: `~\.cursor\skills-cursor` (16 built-ins: canvas, loop, babysit, share…). Cursor-only, no vault overlap by id.
- Codex-local: `~\.codex\skills` (built-ins + hatch-pet + .system\review-agent — the "review-agent 199 uses / 100%" popular item).
- Bolt plugin skills (dormant while plugins false): common 26, boltable 4.
- Duplicate rule holds: marketplace `deep-research`/`grill-me` shadow vault skills → plugins stay false, vault wins.

### Subagents

- Cursor session exposes metaswarm's 18 agents (architect-agent, coder-agent, …) + local `.claude` agents (bugbot, planner, code-reviewer…) — all sourced from the Claude/metaswarm side of the shared harness, not from Cursor plugins.
- No Cursor-only subagent definitions found on disk.

### Rules

- No `~\.cursor\rules\` and no `~\.cursor\commands\` directories exist.
- Always-applied workspace rules = `~\CLAUDE.md` + `~\AGENTS.md` (shared-harness SSOT). Cursor-only rules: none. Good — no drift surface.

### Commands

- Cursor: none on disk. Slash-commands (/start-task, /prime, /self-reflect…) live in the Claude plugin/skill layer. Nothing to collapse.

### Hooks

- Claude: `~\.claude\settings.json` — every lifecycle event routes through the shared dispatcher `C:/Users/Prekzursil/.agents/harness/dispatcher.py` plus ~20 local guard hooks (`~\.claude\hooks\*`). This is the hook SSOT.
- Codex: `~\.codex\hooks.json` (12 events, hash-trusted in config.toml) + plugin hooks (claude-reflect, hookify, metaswarm, remember…).
- Cursor: only plugin hook state at `~\.cursor\hooks\state\continual-learning.json` (first-party continual-learning; left enabled/unpinned per cleanup log).

---

## 2. MCP duplicate-scope map (exact recommendation per server)

Root cause first: **User scope and "Prekzursil project" scope are the same `~\.cursor\mcp.json`** because the workspace root is the home directory. Every server therefore appears twice; each enabled copy is a separate spawned process (RAM cost on a 1.8 GB-free box).

| Server | Keep enabled (ONE scope) | Disable | Why |
| --- | --- | --- | --- |
| agent-mail | **User** | project copy | Shared 8812 HTTP server; must exist for every window, not per-project. |
| basic-memory | **User** | project copy | Shared 8765 HTTP server. The red "Error" on the User copy = server down/stale connection — **watchdog is a sibling track**, do not fix here; reconnect after Cursor restart. |
| chrome-devtools | **User** | project copy | stdio npx spawn — two enabled scopes = two node processes. |
| context7 | **User** | project copy | Same; API-key env comes from user env either way. |
| firecrawl | **User** | project copy | Same. |
| playwright | **User** | project copy | Screenshot showed the *project* copy enabled (0→24 tools) while User was duplicated; standardize on User like the rest. |

Rule going forward: **User scope = the `.agents`-synced six, always. Project scope = everything toggled off** in this home-root workspace. (These are UI toggles stored in Cursor state, not editable JSON — user clicks required, listed at the end.)

---

## 3. Marketplace enumeration

### 3a. Bolt team marketplace (25 ids, rev `edb0999…`)

Legend: what · why-Miky (civil engineer, RE/security, research, media, shared multi-agent harness) · REC ∈ {ADOPT, SKIP, LATER}.

| id | one-liner | REC |
| --- | --- | --- |
| common | 26 general skills — the only Bolt pack with non-Bolt value (token-diet, conversation-kickoff, anti-slop, polish-pr, auto-convert-to-markdown, find-answer); rest is Bolt-internal (WBR, governance, Gmail invoices) | **ADOPT selectively** — port the 5-6 gems into `.agents\skills`, keep plugin false |
| boltable | Bolt's internal push-to-live platform (core/db/integrations/storage) · useless outside Bolt infra | SKIP |
| jira-hygiene | JPD hygiene for Bolt PMs · no Jira in Miky's stack | SKIP |
| delivery-management | Bolt weekly delivery reporting · team-specific | SKIP |
| commerce | Bolt commerce skills · n/a | SKIP |
| im-rides | Incentive-modelling team docs/workflows · n/a | SKIP |
| n8n | n8n helper tuned to *Bolt's* n8n setup · Miky has no n8n | SKIP |
| design | Bolt Design System enforcement · Bolt UI only | SKIP |
| rider-qa | Rider QA · n/a | SKIP |
| insights | Insights-team engineering mgmt · n/a | SKIP |
| internal-products | Bolt internal-products shared items · n/a | SKIP |
| developers-ai-marketplace | Skills for the marketplace devs themselves · only mildly interesting as plugin-authoring reference | LATER |
| performance-cycle | Evidence-based self/peer reviews from Slack/Confluence/Jira · needs Bolt tooling | SKIP |
| customer-payments-skills | Payments engineering support · n/a | SKIP |
| new-bets-strategy-skills | TAM/SAM/SOM market sizing + 5y financials · occasionally useful for opportunity analysis but generic-LLM-replaceable | LATER |
| ux-research | UX research pack · n/a | SKIP |
| diy-unmoderated-usability-test | AI-run usability study end-to-end · n/a | SKIP |
| performance-creative-automation | Bulk ad creatives via AdManage MCP · n/a | SKIP |
| usability-reviewer | Prototype usability review · marginal | SKIP |
| apis | Direct 3rd-party API querying where MCPs are missing · pattern already covered by vault skills | SKIP |
| comms-privacy-dev | Comms&Privacy team workflows · n/a | SKIP |
| analytics-engineering-tooling | AE department skills · n/a | SKIP |
| micromobility-supply-chain-team | Team share pack · n/a | SKIP |
| central-fp-a | FP&A team repo · n/a | SKIP |

Popular-skills stats cross-ref: review-agent 199/100% (Codex system skill, already local), boltable-core 147/98% (Bolt-only), conversation-kickoff 119/100% + token-diet 111/100% (both in `common` → the adopt-selectively gems), grill-me 105/96% (vault already has it — plugin stays false), deep-research 90/**42%** (see §5).

### 3b. Cursor-public catalog (181 ids — compact, catalog cache only)

Full id list lives in the visited-set file. Buckets:

- **Vendor SaaS connectors (~120)** — 1password, airtable, asana, auth0, aws-*, box, clerk, clickup, cloudflare, cockroachdb, databricks, datadog-likes (coralogix, dynatrace, grafana-*, observe), docusign, elastic, firebase, gitbook, gong, hubspot, intercom, jfrog, launchdarkly, linear, monday-crm, mongodb, neon-postgres, netlify, pagerduty, planetscale, postman, prisma, railway, ramp, redis, render, resend, revenuecat, salesforce, sanity, scylladb, shopify, snowflake, sourcegraph, stripe, temporal, webflow, wix, zenity… → SKIP wholesale: no accounts / no stack overlap; each is trivially adoptable later if a project demands it.
- **Scrape/search dupes** — apify, bright-data, browse, browser-use, exa, firecrawl, parallel, tavily → SKIP (anti-overfit: scrape-MCP dupes; live firecrawl MCP + vault skills cover it).
- **Memory/vector** — mem0, pinecone, turbopuffer, paradedb → SKIP (anti-overfit: no vector-DB; basic-memory is the store).
- **Observability #2** — sentry → SKIP (anti-overfit: Sentry#2; vault sentry skill exists).
- **Review/critic** — coderabbit, tabnine, spottercode, subtext-verify, meticulous → SKIP (anti-overfit: no trained critic; adversarial-review gates exist).
- **Orchestrators** — orchestrate, compound-engineering, agent-compatibility, merge-agent-handler → SKIP (anti-overfit: no 2nd orchestrator; metaswarm is it).
- **Cursor meta-tooling** — create-plugin, cursor-sdk, cursor-team-kit, docs-canvas, pr-review-canvas → **LATER, genuinely interesting**: harness owner authoring own Cursor plugins/canvases.
- **Media/creative** — remotion (programmatic video), higgsfield, heygen, cloudinary, canva, tldraw, gsap-skills → remotion LATER (media pipeline fit: caption-burn/video-* skills exist); rest SKIP.
- **Research/ML** — huggingface-skills, sagemaker-ai, braintrust, langfuse, arize, hex, dbt, dagster → huggingface-skills LATER (ML research); rest SKIP.
- **Security** — semgrep-plugin, checkmarx, chainguard, endorlabs, opsera-devsecops, aikido-likes → SKIP (semgrep already routed via quality MCPs/skills; others are enterprise SaaS).
- **Web frameworks** — shadcn, svelte, react-doctor, modern-web-guidance → modern-web-guidance already enabled on the Claude side (googlechrome marketplace) — do NOT double-enable in Cursor; react-doctor LATER for web projects; rest SKIP.
- **Misc** — continual-learning (already active, first-party), x (social research — LATER, x-api vault skill exists → likely dup), astronomer-data, dataverse, dnb-*, meta-vr, phantom-connect, revolut-x, circle, raisely, juicebox, quiverai, monk, mainframe, manufact, thermos, tierzero, pstack, port, plain, profound, falconer, firetiger, githits, here_now, icepanel, aleph, antimetal, atlan, amd-skills, nvidia-skills, opensearch-agent-skills, datarobot-agent-skills, omni-analytics, resolve-ai(-admin), runlayer, corridor, ctx, cli-for-agent, encore, functions, app-builder, magic-patterns, magicpath, lovable, lucid, mobbin, chatprd, clay, circleback, buildkite, harness, forge, glean, gitlab, github, figma, linear, link, mintlify-cursor-plugin, mixpanel-mcp, paper-desktop, docusign, atlassian-twg-cli, airwallex-dev, amazon-location-service, agentmail, appwrite-plugin, browserstack, box, semgrep-plugin… → SKIP (no stack/account overlap or already covered).

---

## 4. Visited-set

Written to `CURSOR-MARKETPLACE-VISITED_2026-08-27.md`: 25 Bolt ids @ rev `edb0999…` (common 1.0.22, boltable 1.0.3) + 181 cursor-public ids, dated 27.08.2026. Future hunts skip these unless version/hash changes.

---

## 5. Reliability debt flag

**deep-research: 90 uses, 42% success** — worst popular skill by far. Hypothesis (one line): long multi-hop research runs on this RAM-starved box outlive their context/tool budget (MCP search backends stall or the session gets OOM-killed mid-run), so partial runs log as failures rather than the skill logic being wrong.

---

## 6. Tiered queue

### TIER-0 — reversible, do now
1. Cursor restart (user click) — flushes stale MCP schemas; re-test Max Effort + basic-memory reconnect.
2. Disable all six **project-scope** MCP duplicate rows in the MCPs tab (UI toggles; User scope stays on). Halves potential MCP process count.
3. Port the `common` gems into `.agents\skills` as vault-owned copies: **token-diet, conversation-kickoff, anti-slop, polish-pr, auto-convert-to-markdown** (plugin itself stays `enabled: false`). Then `sync_shared_state.ps1`.

### Top gems (worth real consideration)
- token-diet (111 uses/100%) — context economy on a machine where context IS the constraint.
- conversation-kickoff (119/100%) — session priming; complements `/start-task`.
- anti-slop + polish-pr — output-quality passes matching the existing slop-check/humanizer discipline.
- create-plugin / cursor-sdk (cursor-public) — author own Cursor plugins from the `.agents` vault instead of adopting third-party ones.
- remotion (cursor-public) — programmatic video fits the existing media skill family (LATER, on demand).

### SKIP (anti-overfit list — enforced)
- 2nd orchestrator: orchestrate, compound-engineering, merge-agent-handler (metaswarm is the orchestrator).
- Vector-DB: pinecone, turbopuffer, mem0, paradedb (basic-memory is the store).
- Sentry#2: sentry plugin (vault sentry skill exists).
- Trained critic: coderabbit, tabnine, spottercode, meticulous (adversarial-review gates exist).
- Scrape-MCP dupes: apify, bright-data, browse, browser-use, exa, parallel, tavily, firecrawl-plugin (live firecrawl MCP wins).
- OpenRouter MCP: none present — keep it that way (OpenRouter stays a spend-capped Codex sidecar, never Cursor BYOK).
- Everything Bolt-internal (boltable + 22 team packs).
