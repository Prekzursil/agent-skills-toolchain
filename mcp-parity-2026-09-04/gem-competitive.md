# Gem-hunt · competitive — native MCP managers vs this estate

**UNIT-COMPLETE: gem-competitive**
Date: 2026-09-04. Provenance: **disk-verified** (named receipts + live configs + vendor docs re-read this unit). Not the inventory digest alone.
No secret values. LITERAL-SECRET-PRESENT keys named without values. NEVER-ROTATE.

Goal: what Cursor / Claude Code / Codex / Z.ai ZCode / Grok **native MCP managers** do that this estate under-uses. Tag **NATIVE-vs-BUILD**. Focus: OAuth MCP (Grok red “auth required”), plugin-provided vs registry, a single SSOT merge for Grok.

Do **not** re-propose: second orchestration runtime, Mem0/Graphiti, Cursor BYOK, OpenRouter MCP.
DEDUP-SET: BUILT = `sync_shared_state.ps1` + claude/codex/cursor/zcode merges + hermes deploy + cursor stdio_bridge + parked-31 + grok-parked-2026-08-27. **PLANNED-unbuilt** = grok `VALID_TARGET` + `merge_generated_grok_mcp.py`. ABSORBED = AgentBridge retired.

## Re-verified live facts (two signals)

| Claim | Signal 1 | Signal 2 |
|---|---|---|
| `VALID_TARGETS` = claude, codex, zcode, hermes; **no grok, no cursor** | `mcp_control_plane.py:15` | `agents.json` has **zero** `"grok"` strings; Cursor merge docstring admits Cursor is not first-class and **mirrors claude** |
| No Grok merge | `merge_generated_grok_mcp.py` absent | `sync_shared_state.ps1` merges Codex/Claude/Cursor/ZCode + Hermes deploy; **0 grok hits** |
| Grok TOML 22 / plugins 34 / plugin MCP 19 | `~\.grok\config.toml` `[mcp_servers.*]` | `installed-plugins\registry.json` + plugin `.mcp.json` (peer `runtime-grok.md`) |
| Cursor live **6** (not 13) | `~\.cursor\mcp.json` 6 names | same-day `mcp.json.bak-*` held 13 = G-6 + 7 hubs, then default merge cleared them |
| Claude generated 51 / live 74 / `~\.mcp.json` 21 | `~\.agents\generated\claude.mcp.json` | `.claude.json` L6823 `mcpServers`; `~\.mcp.json` 21 keys |
| Codex 7 (4 merged + 3 preserved) | `~\.codex\config.toml` `[mcp_servers.*]` | merge selects only `targets` containing `codex` |
| ZCode 20 | `~\.zcode\cli\config.json` `mcp.servers` | merge + 4 local-preserved |
| G-11/G-99 Grok keepers were BM + agent-mail | `mcp-grok-parked_2026-08-27.toml:1-5` | live Grok has 20 extra TOML servers; agent-mail `enabled=false` |
| BM/mail ports | contract `:18765` / `:18812` | Grok TOML still `:8765` / `:8812`; Cursor/Codex/Claude/ZCode live maps use new ports |
| SSOT has **no OAuth schema** | grep `oauth` in `agents.json` = 0 | Grok config-ref has `mcp_servers.<name>.oauth*`; Cursor docs have `auth` object |

LITERAL-SECRET-PRESENT (values not echoed, NEVER-ROTATE):
- `~\.grok\config.toml` `[mcp_servers.mcphub.headers]` key `Authorization`
- `~\.codex\config.toml` `[mcp_servers."mcphub"]` `mcp-remote` `--header` `Authorization`
- `~\.grok\mcp_credentials.json` keys `access_token` / `refresh_token` for 6 OAuth clients: `cloudflare-api`, `cloudflare-bindings`, `cloudflare-builds`, `cloudflare-observability`, `exa`, `figma`

Blast radius: those three files + their `*.bak*` siblings. Do not rotate.

---

## Competitive matrix (native manager capabilities)

| Capability | Cursor | Claude Code | Codex | ZCode (Z.ai) | Grok | Estate today |
|---|---|---|---|---|---|---|
| CLI manager | `cursor-agent mcp enable/disable` | `claude mcp add/list/remove` + `/mcp` | `codex mcp add/login/logout` | Settings UI + import | `grok mcp list/add/enable/disable/doctor` + `/mcps` | Merges write **definitions**; enable/disable arrays are **not** SSOT-owned |
| OAuth for remote HTTP | Native Connect + optional `auth.{CLIENT_ID,CLIENT_SECRET,scopes}` | `/mcp` browser OAuth; `--client-id` / DCR | `codex mcp login`; `mcp_oauth_credentials_store = "keyring"` (live) | Plugin host auth for some Zhipu plugins; URL+header for the rest | rmcp OAuth; `/mcps` key **`i`** (“auth required”); tokens in `mcp_credentials.json` (plaintext 0600) | Registry is PAT/header/`x_codex.bearer_token_env_var` only. **No oauth field.** |
| Plugin MCP vs user MCP | Marketplace plugins; merge skip `tavily` (stale: plugin is **off**) | `CLAUDE_PLUGIN_PROVIDED_SERVERS` skip-set (9 names) | `features.plugins=true` + cache `.mcp.json` | UI groups **Configured** vs **Plugin**; plugin keys `plugin:<name>:<server>` | Trusted plugin `.mcp.json` attaches like user MCP; official marketplace **auto-installed** | Claude skip-set exists. Grok/ZCode plugin MCP **not** in `agents.json`. |
| Cross-runtime ingest | — | project `.mcp.json` | — | **Native** `~\.agents\mcp.json` + Claude/Codex/OpenCode import | Default-on `[compat.claude/cursor] mcps=true` | Grok compat left **on** (no pin). Estate does **not** publish `~\.agents\mcp.json`. |
| Enable/disable without deleting defs | Customize toggle; approval store `<name>-<16hex>` | `disabledMcpServers` (top-level **131** names; also `claude.ai *` connectors) | `enabled` on TOML | `enabled` + plugin switches | `disabled_mcp_servers` **and** `[mcp_servers.X].enabled` (split-brain) | Cursor merge is approval-gated. Claude/Grok disable arrays **untouched** by merge. |
| Prefer URL over `mcp-remote` | HTTP `url` + OAuth | HTTP `url` + OAuth | HTTP + `bearer_token_env_var`; **live mcphub still `npx mcp-remote`** | HTTP `url` | Docs: **do not** wrap HTTP in `npx mcp-remote` | Codex/Grok mcphub leftover is the anti-pattern. |
| Deferred tool catalog | All tools at start (hexstrike 154-tool OOM → retired) | Tool Search | — | — | `search_tool` / `use_tool` | Policy `toolAllowlist: ["*"]`. Surface size is the RAM cost. |
| Secret store | `${env:NAME}` in mcp.json; OAuth in client | `${NAME}` headers; OAuth in client | **keyring** (live) | `${user_config.key}` in plugins | `${VAR}` expansion **or** plaintext `mcp_credentials.json` | Control plane forbids literal secrets; live Grok+Codex mcphub violate it. |

Sources: Cursor docs `https://cursor.com/docs/mcp` (OAuth `auth` object, marketplace one-click); Claude Code docs `/mcp` OAuth + plugin MCP; Codex `mcp_oauth_credentials_store` live `:54` + rmcp OAuth; ZCode docs `https://zcode.z.ai/en/docs/mcp-services` (Configured vs Plugin + `~\.agents\mcp.json`); Grok `~\.grok\docs\user-guide\07-mcp-servers.md`, `09-plugins.md`, `26-config-reference.md`.

---

## Findings

### 1. GROK-OAUTH-RED-AUTH-REQUIRED
- **what:** Grok’s red “auth required” is the **native** MCP OAuth gate (`/mcps` → key `i`). Hosted remotes (Linear, Notion, GitHub Copilot MCP, Hugging Face `?login`, Figma, Exa, Cloudflare) are URL-only; Grok’s rmcp client does discovery + DCR + browser grant and writes `~\.grok\mcp_credentials.json`. Plugin Firecrawl/Exa `.mcp.json` even document “OAuth, no API key to paste.”
- **why-this-estate:** Live Grok TOML mounts github/notion/linear/huggingface/apify **without** `oauth` tables and **without** completing `i`. Split-brain: `disabled_mcp_servers` lists huggingface/notion/linear while their tables say `enabled=true`. Meanwhile `mcp_credentials.json` already holds 6 OAuth clients (cloudflare-*, exa, figma) — so native OAuth **works**, just not for the SSOT keepers. Figma is `enabled=false` **and** in `__managed_gateway_connectors` **and** has a token. Red UI is expected, not a merge bug.
- **how:** For OAuth remotes: keep **url-only** (no Authorization header). Authenticate with `grok mcp` / `/mcps` `i`. Do **not** copy `mcp_credentials.json` into `agents.json`. Do **not** stamp `GITHUB_MCP_PAT` onto Grok github (that is the Codex/Claude PAT path). Leave Grok github as native OAuth **or** skip it (plugin/gateway).
- **source:** `07-mcp-servers.md:168-169,210,239-251`; `26-config-reference.md:329-332`; live TOML `:321-344`; `mcp_credentials.json` top-level keys (no values); plugin `firecrawl-grok-plugin-ba077673\.mcp.json`; `exa-grok-plugin-f73327c3\.mcp.json`.
- **value x effort:** **high × S** (authenticate or disable; no new code).
- **NATIVE-vs-BUILD:** **NATIVE-use**. Building an OAuth token store would duplicate Grok’s (worse: plaintext) and Codex’s (better: keyring).

### 2. SSOT-HAS-NO-OAUTH-SCHEMA
- **what:** Native managers all grew an OAuth object. Cursor: `mcpServers.<name>.auth.{CLIENT_ID,CLIENT_SECRET,scopes}` + `${env:}` interpolation. Grok: `mcp_servers.<name>.oauth` / `oauth_client_id` / `oauth_client_secret_env_var` / `oauth_scopes`. Claude: `claude mcp add --client-id --client-secret`. Codex: `codex mcp login` + keyring, **not** a TOML token. Estate `agents.json` schema is stdio|http + `headers` + `x_codex.bearer_token_env_var` only. Grep `oauth` in `agents.json` = **0**. Cursor merge cannot emit `auth`. Claude merge cannot emit OAuth client fields. A naive Grok merge cloned from Codex would inject `bearer_token_env_var` onto github (registry already does this for Codex/Claude/ZCode).
- **why-this-estate:** Notion/Linear in SSOT are already the **right** shape (url, empty `credentialNames`) — Claude merge writes OAuth-ready HTTP. GitHub/HuggingFace/Apify are PAT-shaped. Mixing those into Grok is what paints servers red (401 → “auth required”) or writes long-lived PATs into the wrong client.
- **how:** Before `merge_generated_grok_mcp.py`: add a closed `x_grok` (or shared `authMode: oauth|bearer|none`). `oauth` → render url-only, never headers. `bearer` → `${ENV}` only. Plugin-OAuth names go on a skip-set (Finding 4). Do not put client secrets in the registry.
- **source:** Cursor docs “Static OAuth for remote servers”; Grok config-ref `mcp_servers.<name>.oauth*`; `agents.json` github `:490-518`, notion `:800-815`, linear `:657-672`; `merge_generated_cursor_mcp.py:252-278` (headers/bearer only).
- **value x effort:** **high × M** (schema + tests in `test_mcp_control_plane.py`; blocks a wrong Grok merge).
- **NATIVE-vs-BUILD:** **BUILD** (schema) so **NATIVE** OAuth can be selected per runtime.

### 3. GROK-SSOT-MERGE — the one PLANNED-unbuilt
- **what:** Every other in-use coding runtime is merge-fed from `agents.json` except Grok (and Goose/Agy, out of this lens). Cursor is not a `VALID_TARGET` either, but **has** `merge_generated_cursor_mcp.py` (claude-mirror + G-6 park). Grok has neither target nor script. Scorecard 2026-08-27 already called this “hand-maintained, drift-prone.” Live drift since then: 20 extra TOML servers, plugin MCP surface, **stale BM/mail ports**, agent-mail off, literal mcphub header.
- **why-this-estate:** G-11/G-99 keepers were BM+agent-mail HTTP-only. Rail migrate 2026-09-04 moved BM `8765→18765` and mail `8812→18812`. Cursor/Claude/Codex/ZCode/Hermes got the new URLs via merge/deploy. Grok TOML still dials **closed** `:8765`/`:8812`. That is the load-bearing reason to merge Grok — not “more servers.”
- **how:** One script, Codex-shaped (TOML block replace, preserve non-MCP):
  1. Add `"grok"` to `VALID_TARGETS`.
  2. `merge_generated_grok_mcp.py`: write keepers + explicitly targeted hubs; drop names the registry does not govern (same “registry is the ONLY body” rule as Cursor).
  3. Render BM `http://127.0.0.1:18765/mcp` (raw HTTP is fine on Grok; do **not** copy Cursor’s stdio shim unless handshake fails the way Cursor did).
  4. Render agent-mail `http://127.0.0.1:18812/mcp` `enabled=true` (G-11 keeper).
  5. **Hard pin** `[compat.claude] mcps=false` and `[compat.cursor] mcps=false` in the same write (Finding 5). Without this, merge is theater — Claude’s 74 names still appear.
  6. Plugin skip-set (Finding 4). OAuth url-only (Finding 2).
  7. Wire into `sync_shared_state.ps1` after ZCode, backup-first like Cursor.
  8. Replace literal `Authorization` with `${ENV}` on any remaining static-token HTTP (mcphub). Do not rotate the token.
- **source:** `mcp_control_plane.py:15`; `sync_shared_state.ps1:179-216`; `merge_generated_codex_mcp.py` (TOML template); `merge_generated_cursor_mcp.py:37-44` (registry authority); parked G-11 file; live Grok BM `:307-315`; memory-contract `:10-11`.
- **value x effort:** **high × M** (one merge + VALID_TARGET + tests + sync hook). This is the DEDUP-SET **PLANNED-unbuilt** item — do it once, do not invent a second control plane.
- **NATIVE-vs-BUILD:** **BUILD** the missing merge; **NATIVE** `grok mcp doctor` as the read-only drift probe on every sync (Finding 8). Do **not** use Grok’s Claude-compat ingest as a fake SSOT.

### 4. PLUGIN-MCP-VS-REGISTRY — skip-sets exist, Grok has none
- **what:** Native managers treat plugin MCP as a **second load path**, not as user config. Claude: plugins define `.mcp.json`; merge **skips** `CLAUDE_PLUGIN_PROVIDED_SERVERS` (aws-serverless, deploy-on-aws, firebase, gitlab, microsoft-learn, mintlify, pinecone, sourcegraph, supabase). Cursor: skip `tavily` because “plugin mounts it” — but live `settings.json` has `tavily.enabled: false` (stale skip; dual-config already flagged). ZCode UI: **Configured MCP** vs **Plugin MCP**; merge docstring preserves plugin/local names. Grok: trusted plugin `.mcp.json` attaches like user MCP; **19** plugin MCP names, **empty exact ∩** with the 22 TOML names, but **functional duplicates**: plugin `firecrawl` (hosted OAuth `https://mcp.firecrawl.dev/v2/mcp`) vs TOML `firecrawl-hub` (`:31414`); plugin `context7` vs nothing in TOML (compat/Claude may still pull it); plugin cloudflare-* match the OAuth credential keys.
- **why-this-estate:** `official_marketplace_auto_installed = true` plus `[plugins].enabled` 44 entries fights G-11 “HTTP hubs only.” Claude already solved double-mount with a skip-set. Grok merge without a skip-set will write a second `firecrawl`/`context7` next to the plugin. Cursor’s tavily skip is a warning: skip-lists rot unless they read live plugin enablement.
- **how:** `GROK_PLUGIN_PROVIDED_SERVERS` derived from installed+enabled plugins’ `.mcp.json` keys (or a pinned frozenset: context7, firecrawl, tavily, exa, cloudflare-*, chrome-devtools, discord, convex, …). Merge skips those names. Optionally `grok plugin disable` MCP-heavy plugins that duplicate hubs. Fix Cursor tavily skip to match live `enabled: false` (either mount from registry or drop the skip).
- **source:** `mcp_control_plane.py:25-36`; `merge_generated_claude_mcp.py:27-31,108`; `merge_generated_cursor_mcp.py:110-113`; ZCode docs list-groups; Grok `09-plugins.md:3,154`; `runtime-grok.md` plugin MCP 19; firecrawl plugin `.mcp.json`.
- **value x effort:** **high × S–M** (frozenset now; live-plugin probe later).
- **NATIVE-vs-BUILD:** **NATIVE** plugin surface stays; **BUILD** skip-set so SSOT does not double-mount. Do not flatten plugins into `agents.json`.

### 5. GROK-COMPAT-MCP-DEFAULT-ON
- **what:** Grok natively **scans** `~\.claude.json` and `~\.cursor\mcp.json` for MCP (`[compat.claude] mcps`, `[compat.cursor] mcps`, both default **true**). Merge priority: config.toml > Claude > Cursor > `.mcp.json`. `disabled_mcp_servers` already contains Claude-only names (angr, biomni-hub, deepsource, excel, postgres, ralph-orchestrator, meta-tool) that are **not** in Grok’s 22 TOML servers — proof the compat scanner is live. `[claude_compat] imported=true` is a different switch (Claude **import** marker), not `compat.claude.mcps=false`.
- **why-this-estate:** A Grok merge that only rewrites `[mcp_servers]` leaves the 74-name Claude map in the session. That is how G-11 keepers silently died. Pinning compat **off** is the native lever; it is currently unset (defaults on).
- **how:** Set in user `config.toml` (merge-owned pin):
  ```toml
  [compat.claude]
  mcps = false
  [compat.cursor]
  mcps = false
  ```
  Keep skills/rules/agents compat **on** (vault share). Confirm with `grok inspect` that origin tags `[claude]`/`[cursor]` disappear from MCP.
- **source:** `05-configuration.md:378-406`; `07-mcp-servers.md:224-235`; live `disabled_mcp_servers` L1–19 vs TOML 22 names; `config.toml:422-423` `[claude_compat] imported=true` only.
- **value x effort:** **high × XS**. Prerequisite to Finding 3.
- **NATIVE-vs-BUILD:** **NATIVE-use**. Do not BUILD a denylist of 74 Claude names.

### 6. ENABLE-DISABLE-KNOB-NOT-IN-SSOT
- **what:** Native managers separate **definition** from **runtime on/off**. Claude: merge writes 74 `mcpServers`, then top-level `disabledMcpServers` (131 entries) hides most of them plus **hosted connectors** named `claude.ai Figma`, `claude.ai Notion`, … Grok: `disabled_mcp_servers` vs per-server `enabled` **conflicts** for huggingface/notion/linear/brightdata. Cursor: `cursor-agent mcp enable/disable` + workspace `mcp-approvals.json`; merge refuses `--attach-all-safe` unless approvals ⊆ G-6. Codex/ZCode: `enabled` on the entry.
- **why-this-estate:** Sync that re-enables everything every run fights the human’s `/mcp` and `/mcps` toggles. Claude UI-on ≈19 of 74 is a native RAM valve the merge does not model. Grok split-brain is why servers look both on (table) and off/red (disabled list + OAuth).
- **how:** Merges already drop `disabled` on Cursor (no field). For Grok: treat `disabled_mcp_servers` as **owner runtime state** — merge may add/remove **definitions**, must not wipe the disabled list except for names it fully governs. For Claude: do not start managing `disabledMcpServers` unless SSOT grows an `approvalMode`/`enabled` projection. Single source of **bodies** (`agents.json`); native owns **session enablement**.
- **source:** `.claude.json:7763` `disabledMcpServers`; Grok `config.toml:1-19` vs `:307+`; `merge_generated_cursor_mcp.py:23-27,57-65`; dual-config intra-file duals table.
- **value x effort:** **medium-high × S** (policy in merge docs + one test).
- **NATIVE-vs-BUILD:** **NATIVE** enablement; **BUILD** only “do not clobber.”

### 7. CODEX-KEYRING-OAUTH-UNDERUSED
- **what:** Codex already set `mcp_oauth_credentials_store = "keyring"` (`config.toml:54`). Native path is `codex mcp login <name>` for streamable HTTP OAuth (Notion/Linear/Figma class). Live github is still `bearer_token_env_var = "GITHUB_MCP_PAT"`. Live **mcphub** is `npx mcp-remote` with a **literal** Authorization header — the exact anti-pattern Grok’s docs forbid (prefer `url`, let the client do OAuth/headers via env).
- **why-this-estate:** Same mcphub token class as Grok’s literal header (two-file blast radius). Codex merge **preserves** unmanaged names (`node_repl`, `cua_repl`, `mcphub`) so the leftover never gets env-interpolated. GitHub Copilot MCP can be PAT **or** OAuth; estate picked PAT for Claude/Codex and nothing for Grok.
- **how:** (a) Recode mcphub to native HTTP/SSE `url` + `${MCPHUB_TOKEN}` / `bearer_token_env_var` — no `mcp-remote`, no literal. (b) Leave github as PAT for Codex if that is the owner path; do not copy PAT onto Grok. (c) For new OAuth remotes on Codex, `codex mcp login` + keyring, not headers in TOML.
- **source:** `~\.codex\config.toml:54,987-1015`; Grok `07-mcp-servers.md:168`; Codex rmcp OAuth store (vendor).
- **value x effort:** **medium × S**.
- **NATIVE-vs-BUILD:** **NATIVE-use** (login + keyring + url form). Tiny BUILD only if merge should govern mcphub (today it is local-preserved; optional `targets` add).

### 8. GROK-MCP-DOCTOR-UNUSED
- **what:** `grok mcp doctor` / `grok mcp doctor --json` diagnoses config **and connectivity**. `grok inspect` shows source origin (`[claude]`, `[cursor]`, plugin). Native CLI `enable`/`disable` persists `disabled_mcp_servers`. Estate has no Grok step in `sync_shared_state.ps1`, so closed `:8765` survived from 2026-09-04 rail migrate until this hunt.
- **why-this-estate:** Two-strikes/verification doctrine wants a second probe. Doctor is that probe. A merge without doctor will green-write stale URLs again if the registry ever drifts.
- **how:** After Grok merge (or even before, as a read-only sync warning): run `grok mcp doctor --json`, fail closed on keeper HTTP (BM, agent-mail) if TCP/handshake fails. Do not auto-restart daemons (watchdog owns `:18765`/`:18812`).
- **source:** `07-mcp-servers.md:127-131,370-375`; inventory TCP `:8765` closed; live Grok BM still `:8765`.
- **value x effort:** **medium × S**.
- **NATIVE-vs-BUILD:** **NATIVE-use** inside the existing sync script. Not a new manager.

### 9. ZCODE-NATIVE-AGENTS-MCP-JSON
- **what:** ZCode’s native MCP manager already reads `~\.agents\mcp.json` (`mcpServers`) **and** can import Claude/Codex/OpenCode configs. UI splits Configured vs Plugin. Finance/Zhipu plugins authenticate “through the ZCode host.” Estate **built** `merge_generated_zcode_mcp.py` into `cli\config.json` instead of publishing the standard `.agents/mcp.json` the product documents. Live ZCode also has 9 `enabledPlugins` with their own `.mcp.json` (android-emulator, ios-simulator, mimosa, cloudbase-skills, …).
- **why-this-estate:** The zcode merge works and is in DEDUP-SET BUILT — do not replace it. The under-use is the **documented** shared file other tools (and ZCode import) already understand. `integrations.enabled: []` was deliberate to avoid native `agents sync` `agents__` prefixes — that ban still holds. A generated **reference** `~\.agents\mcp.json` (or keep using `generated/claude.mcp.json`) is optional, not a second live writer.
- **how:** Keep the zcode merge. Optionally `publish_reference_views.py` already emits Claude/Codex views — add a credential-free `generated/mcp.servers.json` if import UX is wanted. Never enable `integrations.enabled` for zcode/claude/codex.
- **source:** `https://zcode.z.ai/en/docs/mcp-services` load paths; `merge_generated_zcode_mcp.py:1-17`; `agents.json` `integrations.enabled: []`; live `~\.zcode\cli\config.json` plugins + mcp.servers.
- **value x effort:** **low-medium × don't-rebuild**. Document only unless import is a real workflow.
- **NATIVE-vs-BUILD:** **NATIVE** already covered by a **BUILT** merge. Do not add a parallel writer.

### 10. HOSTED-CONNECTORS-VS-HAND-FIGMA
- **what:** Grok Space **managed gateway connectors** (`disabled_mcp_tools.__managed_gateway_connectors` = figma, canva, hyperframes_by_heygen) are a native MCP catalog **outside** `mcp_servers`. Claude has the same class as `claude.ai Figma` / `claude.ai Notion` / … inside `disabledMcpServers`. Cursor marketplace “Add to Cursor” is OAuth one-click. Estate also hand-wrote `[mcp_servers.figma] url=https://mcp.figma.com/mcp enabled=false` and Grok still stored a Figma OAuth token.
- **why-this-estate:** Three Figma paths (gateway, TOML, OAuth store) plus a Claude connector name. RAM + auth-required noise. G-11 said strip Grok to hubs.
- **how:** Pick **one** Figma path: native gateway **or** TOML url-only OAuth **or** none. Keep the other two disabled. Do not add Figma to `agents.json` grok targets. Same for Canva/Heygen (leave gateway-disabled).
- **source:** `config.toml:428-433`; `.claude.json:7773+` `claude.ai *`; Cursor marketplace OAuth one-click (docs).
- **value x effort:** **medium × XS**.
- **NATIVE-vs-BUILD:** **NATIVE-use** (leave gateway disabled; delete or keep TOML disabled). No new server in SSOT.

### 11. CURSOR-NATIVE-OAUTH-NOT-RENDERED
- **what:** Cursor HTTP/SSE auth is OAuth by default. Static DCR-less providers take `auth` in `mcp.json`. Live G-6 firecrawl/context7 use **Bearer `${env:API_KEY}`**, not OAuth Connect. Firecrawl’s **Grok plugin** uses OAuth URL with no key; Cursor registry uses the API key. Both valid; inconsistent.
- **why-this-estate:** Cursor merge has no `auth` renderer. If owner wants keyless Firecrawl/Notion on Cursor, SSOT cannot say so today. G-6 key path is the one that survived approval-gating — keep it unless owner switches.
- **how:** Do not change G-6 in this wave (approvals + RAM). If a later OAuth Cursor server is wanted, extend Finding 2 schema and render `auth` with `${env:}` only. Never put CLIENT_SECRET literals in mcp.json.
- **source:** `https://cursor.com/docs/mcp` Static OAuth; live `~\.cursor\mcp.json:24-34`; Grok firecrawl plugin `.mcp.json`.
- **value x effort:** **medium × later**. Not a blocker for Grok merge.
- **NATIVE-vs-BUILD:** **NATIVE** OAuth exists; **BUILD** only if SSOT must project it.

### 12. DEFERRED-CATALOG-VS-SURFACE-SIZE
- **what:** Grok already does not dump every MCP tool into the model: `search_tool` / `use_tool`. Claude has Tool Search. Cursor does **not** — all tools load; hexstrike 154-tool schema OOM’d Fable/Composer (G-15/G-18), hence `CURSOR_RETIRED_SERVERS`. Estate policy `toolAllowlist: ["*"]`.
- **why-this-estate:** The miss is not “build a tool router.” It is **surface size** on Grok: 20 extra TOML servers + 19 plugin MCP + Claude-compat 74, on a RAM-tight box, while keepers (BM, mail) are on the wrong port / disabled.
- **how:** Shrink Grok’s enabled set (Findings 3–5, 10). Leave Cursor G-6. Do not enable hexstrike on Cursor. Do not add a second meta-tool router (REJECTED / meta-tool is Cursor-denied).
- **source:** Grok `07-mcp-servers.md:215-218`; `merge_generated_cursor_mcp.py:120-127`; `agents.json` policy `toolAllowlist`.
- **value x effort:** **high × follows 3–5**.
- **NATIVE-vs-BUILD:** **NATIVE** catalog already deferred on Grok/Claude. **BUILD** is shrinking what is connected.

---

## Recommended sequence (estate, not a new runtime)

1. **NATIVE, now:** `[compat.claude] mcps=false`, `[compat.cursor] mcps=false`. `/mcps` disable non-keepers. `grok mcp enable` agent-mail after URL fix. Do not touch credential rotation.
2. **NATIVE, now:** Authenticate or disable OAuth remotes (`i` vs drop). Do not PAT-stamp Grok github.
3. **BUILD, this is the PLANNED-unbuilt:** `VALID_TARGETS += grok` + `merge_generated_grok_mcp.py` + sync hook + plugin skip-set + `authMode` so OAuth stays url-only. Point BM/mail at `:18765`/`:18812`. Env-interpolate mcphub.
4. **NATIVE, in sync:** `grok mcp doctor --json` as fail-closed keeper probe.
5. **Do not:** second control plane, flatten plugins into registry, enable `integrations.enabled`, copy `mcp_credentials.json` into git, Cursor BYOK, OpenRouter MCP, Mem0/Graphiti.

## What this lens is not

- Not a re-inventory (see `inventory.md`, `runtime-*.md`, `dual-config.md`).
- Cursor “13” is a same-day backup, not live (peer `runtime-cursor.md`).
- Goose/Agy/VS Code/Claude Desktop are out of the five-runtime focus except as “compat ingest” risk.

UNIT-COMPLETE: gem-competitive
disk-verified: this file
