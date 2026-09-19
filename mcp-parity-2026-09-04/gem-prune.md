# Gem-hunt lens `prune` — Grok plugins vs HTTP hubs, Cursor G-6 extras, hexstrike OOM, search-hub stdio

**UNIT-COMPLETE: gem-prune**
Date: 2026-09-04. Live files re-read this unit (not digest-only). No secret values.
Receipt: this file.

## Verdict in one page

| Surface | Live state (re-read) | Park vs keep |
|---|---|---|
| Cursor `~/.cursor/mcp.json` | **Exactly G-6** (6 names, 0 extras) | **KEEP** G-6. Do not re-hand-edit Hermes hubs. |
| Cursor hexstrike | Absent live; in `CURSOR_RETIRED_SERVERS` + parked-31 | **KEEP PARKED**. Remount OOMs Fable. |
| Cursor same-day extras (13 = G-6 + 7 hubs) | Only in `mcp.json.bak-*` | **KEEP PARKED**. Fights G-6 RAM. |
| Grok G-11/G-99 keepers | BM on **stale :8765**; agent-mail **enabled=false** on stale :8812 | **KEEP** both, after port/enable fix (not a prune of keepers). |
| Grok `search-hub` | **stdio** python `hub.py` (84 tools this session) | **PARK**. Violates HTTP-hubs-only. |
| Grok plugin MCP vs hubs | firecrawl plugin **and** firecrawl-hub both connected this session | **PARK** the duplicate; keep one HTTP path. |
| Grok Hermes/CyberStrike hubs | 7 registry hermes-only + 2 unregistered copied into Grok TOML | **PARK on Grok**. Hermes-owned (G-1). |
| Grok marketplace plugins that spawn MCP | 19 `.mcp.json` names; 34 plugin IDs; `[plugins].enabled` includes firecrawl/tavily/exa/context7/cloudflare/chrome-devtools-mcp | **PARK** search duplicates + stdio plugins. Skills-only plugins may stay. |
| `merge_generated_grok_mcp.py` / grok `VALID_TARGET` | Still unbuilt | **Do not re-propose** (DEDUP PLANNED-unbuilt). Prune is NATIVE config. |

This Grok Build session is a live witness: connected MCP includes **both** `firecrawl` (plugin, 3 tools) and `firecrawl-hub` (27 tools), plus stdio `search-hub` (84 tools), plugin `context7` and `cloudflare-docs`, and seven CyberStrike hubs that `agents.json` targets **hermes** only.

LITERAL-SECRET-PRESENT: `~/.grok/config.toml` `[mcp_servers.mcphub.headers]` key `Authorization`. Blast radius: that file. NEVER-ROTATE.

## Policy SSOT (do not conflate)

1. **Grok G-11 + G-99** (`Cowork/output/grill-proposed-answers_2026-08-27.md:122-125,395-396`; parked header `mcp-grok-parked_2026-08-27.toml:1-7`): strip Grok MCP to **HTTP hubs = agent-mail + basic-memory**. Social/RE return only for a titled task, single instance. Cap 1 Grok window.
2. **Hermes G-1** (`HERMES-HARMONIZATION_2026-09-03.md:8-10`): Hermes MCP = HTTP hubs (estate daemons + remote HTTP + cyberstrike mcp-proxy). **Hermes-only.** Not a license to copy those hubs onto Grok or Cursor.
3. **Cursor G-6 = 6B keep-list** (`merge_generated_cursor_mcp.py:129-140`; live `mcp.json:2-46`): agent-mail, basic-memory, chrome-devtools, context7, firecrawl, playwright. Extra hubs fight this RAM policy.
4. **Cursor G-10** (grill `:117-120`): CLI should disable the stdio members of G-6; keep the 2 HTTP hubs for headless. Live G-6 now has context7+firecrawl as **HTTP** (G-10's "4 npx stdio" is stale); chrome-devtools + playwright remain npx stdio.
5. **Hexstrike on Cursor** (`merge_generated_cursor_mcp.py:120-127`; `CURSOR-FABLE-CYBERSAFE_2026-09-02.md:24,52`): 154-tool schema dump OOMs Fable/Composer (G-15/G-18, park 2026-09-04). Do not add to `mcp.json` except a titled RE session.
6. **DEDUP-SET**: do not re-propose grok `VALID_TARGET` + `merge_generated_grok_mcp.py` (PLANNED-unbuilt). Prune = disable/park on disk.

## Live evidence (this unit)

- Grok TOML MCP: `~/.grok/config.toml:307-420` — 22 names; disabled **agent-mail**, **figma**; **search-hub** is `command`+`args` stdio, not `url`.
- Grok plugins: `config.toml:47-93` enabled includes `firecrawl`, `tavily`, `exa`, `context7`, `cloudflare`, `chrome-devtools-mcp`, `browser-use`, `desktop-commander`, `discord`, `convex`, `cockroachdb`. Docs: trusted `.mcp.json` attaches like other MCP (`~/.grok/docs/user-guide/09-plugins.md:154,346`).
- Plugin `.mcp.json` re-read: firecrawl hosted HTTP; tavily hosted HTTP; exa hosted HTTP; context7 hosted HTTP; cloudflare **five** HTTP; cockroachdb 3; discord bun stdio; desktop-commander npx stdio; browser-use uvx stdio; convex npx stdio; tinyfish/expo/CodSpeed HTTP.
- Registry hubs: `agents.json:1647-1786` — github-security-hub :31410, cve :31411, osint :31412, hexstrike-ai-hub :31413, nuclei :31417, cloud-audit :31418, semgrep :31419; **targets=["hermes"]** only. **No** `search-hub`, **no** `firecrawl-hub`, **no** `hacktricks-hub` in `agents.json`.
- CyberStrike launcher still maps firecrawl :31414 and hacktricks :31415 (`D:\opt\cyberstrike-mcp\start-cyberstrike-mcp-http.ps1:30-31`). Grok TOML copied those unregistered fronts.
- Cursor live: `~/.cursor/mcp.json:2-46` = G-6 only. BM = `bm_cursor_http_session.py --stdio --url http://127.0.0.1:18765/mcp`. agent-mail = `:18812`.
- Cursor bak extras: `mcp.json.bak-park-hexstrike-20260904-165736:45-65` G-6 + 7 hubs including **hexstrike-ai-hub**; `mcp.json.bak-20260904-222855:45-65` same minus hexstrike, plus **hacktricks-hub**.
- search-hub implementation: `D:\opt\search-hub-pr310\tools\mcp\search-hub\hub.py:1-21` — stdio multiplexer; **spawns** Exa/Tavily/Firecrawl/SearXNG **stdio children**. Second copy: `~/source/agent-skills-toolchain/tools/mcp/search-hub/hub.py` used by `~/.mcp.json:57-70`.
- Tool counts this session (connected): search-hub 84, firecrawl-hub 27, firecrawl 3, github-security-hub 39, cve-mcp-hub 41, osint-hub 37, cloud-audit-hub 38, hacktricks-hub 7, nuclei-hub 3, semgrep-hub 1, context7 2, cloudflare-docs 2. Hermes measure hexstrike **150** (`HERMES-HARMONIZATION_2026-09-03.md:51`). Merge comment hexstrike **154**-tool OOM.

---

## Per-find

### 1. GROK-SEARCH-HUB-STDIO

- **name:** Grok `search-hub` stdio vs HTTP-hubs-only
- **what:** `[mcp_servers.search-hub]` runs `C:\Python314\python.exe D:\opt\search-hub-pr310\tools\mcp\search-hub\hub.py` (`config.toml:366-375`). Not in `agents.json`. 84 tools attached this session. Docstring: lazy stdio multiplexer that **spawns child stdio MCPs** for Exa, Tavily, Firecrawl, SearXNG.
- **why-this-estate:** G-99 keepers are agent-mail + basic-memory only. A 84-tool schema plus on-call child processes is the same clone-cost G-99 killed (frida/social-hub). RAM-tight box; search is already covered by hosted HTTP plugins **and** `firecrawl-hub`.
- **how:** `enabled = false` (or delete the TOML block; keep parked copy). Do not convert to a second HTTP daemon. If search is needed on Grok, use **one** hosted HTTP (plugin `firecrawl` **or** registry-style `https://mcp.firecrawl.dev/v2/mcp`), not the mux.
- **source:** `config.toml:366-375`; `hub.py:1-21`; G-99 grill `:395-396`; parked TOML already contained a search-hub stdio block (`mcp-grok-parked_2026-08-27.toml:449-461`) — this is a **regression**, restored after the 2026-08-27 park. This session: `search-hub (84 tools)`.
- **value x effort:** High × Low
- **NATIVE-vs-BUILD:** **NATIVE** (TOML disable). Not a merge-script job.

**Recommend: PARK.**

### 2. GROK-PLUGIN-FIRECRAWL-DUP-FIRECRAWL-HUB

- **name:** Plugin `firecrawl` duplicates `firecrawl-hub` (and registry `firecrawl`)
- **what:** Trusted plugin `.mcp.json` points at `https://mcp.firecrawl.dev/v2/mcp` (3 tools this session). Grok TOML `firecrawl-hub` points at `http://127.0.0.1:31414/mcp` (27 tools). Registry `firecrawl` is the same hosted URL, targets claude+hermes (`agents.json:422-450`). `firecrawl-hub` is **not** a registry server; it is a CyberStrike mcp-proxy front (`start-cyberstrike-mcp-http.ps1:30`).
- **why-this-estate:** Double schema (3+27) for one vendor. Local hub still needs the :31414 proxy process; hosted HTTP needs none. G-99 does not list firecrawl as a Grok keeper.
- **how:** Disable plugin `firecrawl` **or** disable `[mcp_servers.firecrawl-hub]`, not neither. Prefer **park the local hub on Grok**; hosted HTTP matches Cursor G-6 + registry. Leave :31414 for Hermes/CyberStrike supervisor.
- **source:** `firecrawl-grok-plugin-ba077673/.mcp.json:2-8`; `config.toml:412-415`; `agents.json:422-450`; this session both `firecrawl` and `firecrawl-hub` connected; 09-plugins.md:154.
- **value x effort:** High × Low
- **NATIVE-vs-BUILD:** **NATIVE** (`[plugins].enabled` drop and/or TOML `enabled=false`).

**Recommend: PARK `firecrawl-hub` on Grok; KEEP at most one hosted Firecrawl (plugin or TOML URL, not both).**

### 3. GROK-PLUGIN-TAVILY-EXA-DUP-SEARCH-HUB

- **name:** Plugin `tavily` + `exa` duplicate search-hub lanes (and registry)
- **what:** `tavily-grok-plugin-05ff8f77/.mcp.json` → `https://mcp.tavily.com/mcp`. `exa-grok-plugin-f73327c3/.mcp.json` → `https://mcp.exa.ai/mcp/oauth`. Registry `tavily` is **stdio npx** claude-only (`agents.json:1080-1114`). Registry `exa` is a Hermes HTTP target. search-hub fronts Exa+Tavily+Firecrawl as **stdio children**.
- **why-this-estate:** Three ways to buy the same search tools. Plugin HTTP is G-99-legal transport but extra schema; search-hub is illegal transport **and** extra schema. Cursor merge already treats Tavily as plugin-provided and **skips** rendering it (`CURSOR_PLUGIN_PROVIDED_SERVERS`, `merge_generated_cursor_mcp.py:110-113`); Cursor `settings.json` has tavily `enabled: false` (runtime-cursor / dual-config).
- **how:** After parking search-hub, disable Grok plugins `tavily` and `exa` unless a titled search task needs one hosted vendor. Do not re-enable registry tavily stdio on Grok.
- **source:** plugin `.mcp.json` files above; `hub.py:3-5`; `agents.json:1080-1114`; `config.toml:59-61,75`.
- **value x effort:** High × Low
- **NATIVE-vs-BUILD:** **NATIVE**

**Recommend: PARK search-hub first; then PARK tavily/exa plugins on Grok until a titled task. KEEP Cursor's tavily plugin **off**.**

### 4. GROK-PLUGIN-CONTEXT7-DUP-REGISTRY

- **name:** Plugin `context7` duplicates Cursor G-6 / Hermes / registry context7
- **what:** Plugin HTTP `https://mcp.context7.com/mcp` attached this session (2 tools). **Not** in Grok `config.toml` mcp_servers. Registry/Cursor already have the same URL.
- **why-this-estate:** Harmless-looking (2 tools) but it is a second MCP load path Grok sync cannot see. G-99 keepers do not include it.
- **how:** Remove `context7` from `[plugins].enabled` (skills unused) **or** leave plugin installed but untrusted so `.mcp.json` does not attach. Do not add a TOML duplicate.
- **source:** `...external-plugins-context7-4bbc153f/.mcp.json:2-9`; this session `context7 (2 tools)`; Cursor `mcp.json:24-28`.
- **value x effort:** Med × Low
- **NATIVE-vs-BUILD:** **NATIVE**

**Recommend: PARK plugin MCP on Grok. KEEP on Cursor G-6.**

### 5. GROK-PLUGIN-CLOUDFLARE-FIVE

- **name:** Cloudflare plugin mounts five HTTP MCPs
- **what:** `skills-39968d19/.mcp.json` defines cloudflare-api, cloudflare-docs, cloudflare-bindings, cloudflare-builds, cloudflare-observability. This session loaded `cloudflare-docs` (2 tools). Not in registry, not a G-99 keeper.
- **why-this-estate:** Five extra tool schemas whenever the plugin is trusted. No Cloudflare control-plane task in the MCP-parity hunt.
- **how:** Drop `cloudflare` from `[plugins].enabled` (or untrust). Re-enable per titled Cloudflare task.
- **source:** `skills-39968d19/.mcp.json:1-24`; `config.toml:58`; 09-plugins.md:154.
- **value x effort:** Med × Low
- **NATIVE-vs-BUILD:** **NATIVE**

**Recommend: PARK (demand-start).**

### 6. GROK-PLUGIN-STDIO-FLEET

- **name:** Marketplace stdio MCPs on Grok (browser-use, desktop-commander, discord, convex, cockroachdb-toolbox)
- **what:** browser-use `uvx browser-use@latest --cli-mcp`; desktop-commander `npx -y @wonderwhy-er/desktop-commander@latest`; discord `bun run start`; convex `npx convex mcp start`; cockroachdb-toolbox `toolbox --stdio` plus a :5000 HTTP twin. chrome-devtools-mcp ships `gemini-extension.json` npx `chrome-devtools` but **no** Grok `.mcp.json` (Grok attaches `.mcp.json` only — 09-plugins.md:346), so it may be inert as MCP; it is still enabled as a plugin.
- **why-this-estate:** G-99 banned default stdio on Grok after measured 8× frida / 6× social-hub clones. These recreate that class of process. browser-use overlaps Cursor chrome-devtools + playwright (G-6).
- **how:** Remove those IDs from `[plugins].enabled` (or untrust). Leave skill-only plugins (superpowers, code-review, …) if they have no `.mcp.json`.
- **source:** `plugins-git-grok-ba06cd19/grok/.mcp.json`; `claude-a61e7e9d/.mcp.json`; discord `.mcp.json`; `convex-backend-skill-b4d71a2b/.mcp.json`; `claude-plugin-eecc3f20/.mcp.json`; `chrome-devtools-mcp-2df60288/gemini-extension.json:3-10`; G-99 `:395-396`.
- **value x effort:** High × Low
- **NATIVE-vs-BUILD:** **NATIVE**

**Recommend: PARK all stdio plugin MCPs on Grok. KEEP chrome-devtools on Cursor G-6 only.**

### 7. GROK-HERMES-HUBS-COPIED

- **name:** CyberStrike HTTP hubs copied onto Grok (hermes-only in registry)
- **what:** Grok TOML enables github-security-hub :31410, cve-mcp-hub :31411, osint-hub :31412, hexstrike-ai-hub :31413, nuclei-hub :31417, cloud-audit-hub :31418, semgrep-hub :31419 (`config.toml:377-410`). Plus unregistered firecrawl-hub :31414 and hacktricks-hub :31415 (`:412-420`). Registry targets for the seven are **`["hermes"]` only** (`agents.json:1647-1786`). This session connected the set except hexstrike (hub DOWN in inventory).
- **why-this-estate:** Schema dump this session without hexstrike already ≈ 39+41+37+3+38+1+27+7 = **193 hub tools**, on top of search-hub 84 and plugins. Hermes G-1 owns these fronts. Grok G-99 keepers do not. Cursor already had to **undo** the same copy (bak → live G-6). Copying Hermes hubs onto Grok is the same RAM/policy bug Cursor just cleared.
- **how:** `enabled = false` on all nine `*-hub` blocks in Grok TOML (or move them into `mcp-grok-parked_2026-08-27.toml`). Do not add them to `agents.json` grok targets. Hermes deploy stays the owner of :314xx.
- **source:** `config.toml:377-420`; `agents.json:1647-1786`; `HERMES-HARMONIZATION_2026-09-03.md:8-10,26-28`; Cursor baks; this session tool list.
- **value x effort:** High × Low
- **NATIVE-vs-BUILD:** **NATIVE**. Adding grok as `VALID_TARGET` would **spread** these if someone targets grok — the opposite of prune. DEDUP: do not build the merge.

**Recommend: PARK all nine on Grok. KEEP on Hermes.**

### 8. HEXSTRIKE-ON-CURSOR-OOM (and Grok twin)

- **name:** hexstrike on Cursor OOM; Grok hub still enabled
- **what:** Cursor live has **no** hexstrike (`mcp.json` re-read). `CURSOR_RETIRED_SERVERS` = mixpanel, mixpanel-mcp, hexstrike-ai, hexstrike-ai-hub (`merge_generated_cursor_mcp.py:120-127`) because **154-tool schema dump OOMs Fable/Composer** (G-15/G-18, park 2026-09-04). Parked catalog still has stdio `hexstrike-ai` + HTTP `hexstrike-ai-hub` disabled (`mcp-cursor-parked-31.json:169-178`). Same-day bak **did** attach hexstrike-ai-hub (`mcp.json.bak-park-hexstrike-20260904-165736:54-56`). Registry still has claude-targeted **stdio** `hexstrike-ai` (`agents.json:555-566`) and hermes-targeted **HTTP** `hexstrike-ai-hub` (:31413). Grok TOML has hexstrike-ai-hub **enabled=true** (`config.toml:392-395`). Hermes measured **150** hexstrike tools. This session did not attach it (inventory hub DOWN).
- **why-this-estate:** 31.6 GB box under RAM pressure; Fable/Composer already OOMed on the schema dump. 150 tools is larger than G-6's entire useful surface. Cursor policy is correct. Grok enabling the same hub is waiting for the hub process to come up and dump 150 tools into this CLI.
- **how:** Cursor: do nothing except refuse hand-edits / `--attach-all-safe` without reading retired set (already guards). Grok: `enabled = false` on hexstrike-ai-hub. Claude stdio hexstrike is out of this lens; do not route it to Cursor.
- **source:** merge `:120-127`; parked-31 `:169-178`; bak-park-hexstrike `:54-56`; `CURSOR-FABLE-CYBERSAFE_2026-09-02.md:24,52`; `agents.json:555-566,1707-1725`; `HERMES-HARMONIZATION:51`; Grok `config.toml:392-395`.
- **value x effort:** High × Low (Grok disable). Cursor keep-parked = **zero** effort.
- **NATIVE-vs-BUILD:** **NATIVE**. Retired-set is already BUILD and must stay.

**Recommend: KEEP PARKED on Cursor. PARK on Grok. KEEP HTTP hub on Hermes only, demand-start.**

### 9. CURSOR-EXTRA-HUBS-VS-G-6

- **name:** Cursor extra hubs fight G-6 RAM policy
- **what:** Live extra vs G-6 = **none** (`mcp.json:2-46` = the six). Prompt "Cursor 13" is the **same-day bak**, not live: G-6 + github-security-hub, cve-mcp-hub, osint-hub, hexstrike-ai-hub **or** hacktricks-hub, nuclei-hub, cloud-audit-hub, semgrep-hub. Those names are hermes-only in registry; `hacktricks-hub` is **absent** from `agents.json`. `sync_shared_state.ps1` runs cursor merge **without** `--attach-all-safe` → SAFE_DEFAULT G-6. glm53-space is in SAFE_DEFAULT but registry `enabled=false` — not live.
- **why-this-estate:** G-6 exists because pre-6B Cursor cloned ~37 servers / 76 node. The 7-hub hand-edit reintroduced Hermes' ~193-tool dump into the editor. Merge later cleared it. Re-attaching is the RAM regression.
- **how:** Do not hand-edit `mcp.json`. Do not run `--attach-all-safe`. G-10 still applies to **CLI**: disable chrome-devtools + playwright npx for `cursor-agent`; editor may keep them (G-6).
- **source:** live `mcp.json`; baks cited; `merge_generated_cursor_mcp.py:46-55,129-147,320-326`; grill G-10 `:117-120`; inventory.md:31-32.
- **value x effort:** High × Zero (already pruned). Guard is High × Low (don't re-edit).
- **NATIVE-vs-BUILD:** Live KEEP is **NATIVE** file state. Guard is existing **BUILD** (merge default + retired set).

**Recommend: KEEP live G-6. KEEP PARKED the 7 hubs + parked-31. Do not treat bak-13 as current.**

### 10. GROK-KEEPERS-AND-PORT-DRIFT (keep, not park)

- **name:** G-99 keepers present but wrong port / agent-mail off
- **what:** BM `url = http://127.0.0.1:8765/mcp` enabled (`config.toml:307-310`). Contract SSOT is `:18765` (`memory-contract.md:10-11`; WHERE-map rail migrate 2026-09-04). agent-mail `url = http://127.0.0.1:8812/mcp` **enabled=false** (`:312-315`); live mail is `:18812` (Cursor mcp.json; inventory health 200 on 18812). `disabled_mcp_servers` also lists agent-mail, huggingface, notion, linear, brightdata (`config.toml:1-18`) while several of those have `enabled = true` blocks — two knobs, opposite signs.
- **why-this-estate:** Pruning extras is wasted if the two keepers cannot connect. Inventory TCP `:8765` closed; BM handshake failed. Agent-mail disabled means Grok has no peer channel.
- **how:** Point BM at `http://127.0.0.1:18765/mcp`; agent-mail at `http://127.0.0.1:18812/mcp` with `enabled = true`; reconcile `disabled_mcp_servers` with the blocks. **Do not restart daemons** from this unit.
- **source:** config.toml cited; memory-contract; Cursor mcp.json:3-13; inventory hubs/TCP; dual-config.md conflict note.
- **value x effort:** High × Low
- **NATIVE-vs-BUILD:** **NATIVE** (two URL lines + one enabled flag).

**Recommend: KEEP keepers; fix port/enable. Not a park.**

### 11. GROK-MCPHUB-SSE-AND-SAAS-RESTORED

- **name:** mcphub SSE + restored remote SaaS vs 2026-08-27 park
- **what:** Live extras vs G-99 keepers: apify, brightdata, deepwiki, fiddler, figma (off), github, huggingface, linear, notion, mcphub SSE `:24680`, plus the hubs/search-hub above. Parked file removed huggingface, apify, github, linear, notion, deepwiki, search-hub, fiddler, brightdata as **non-keepers**. mcphub has a literal Authorization header (not `${ENV}`).
- **why-this-estate:** Each remote HTTP still spends tool-schema tokens every session (G-10/G-99 rationale). mcphub is SSE not HTTP-MCP, and embeds a secret. `:24680` was the only inventory TCP open among the old rails.
- **how:** Park mcphub, fiddler, apify, brightdata, huggingface, notion, linear, figma, github, deepwiki from Grok default list (paste back into parked TOML). Re-enable **one** remote per titled task. Redact mcphub header to `${MCPHUB_TOKEN}` (do not rotate).
- **source:** `config.toml:321-364`; `mcp-grok-parked_2026-08-27.toml:1-7,93-95,259-261`; scorecard `:13`.
- **value x effort:** Med × Low
- **NATIVE-vs-BUILD:** **NATIVE**

**Recommend: PARK from Grok default. KEEP github on Codex (registry codex target) not via Grok copy.**

### 12. SEARCH-HUB-PATH-FORK

- **name:** Three search-hub install paths
- **what:** Grok live: `D:\opt\search-hub-pr310\...`. Claude `~/.mcp.json`: toolchain `source/agent-skills-toolchain/tools/mcp/search-hub/hub.py`. Parked Grok 2026-08-27: same toolchain path. Not in registry.
- **why-this-estate:** Pruning one path leaves another runtime spawning the mux. Claude extra search-hub is a dual-config leftover (`inventory.md:75`).
- **how:** Park/disable Grok block **and** drop search-hub from `~/.mcp.json` (Claude merge does not own that file). Do not HTTP-wrap it for Grok.
- **source:** paths above; `~/.mcp.json:57-70`; runtime-claude extras list.
- **value x effort:** Med × Low
- **NATIVE-vs-BUILD:** **NATIVE**

**Recommend: PARK both leftover stdio entries.**

---

## Plugin MCP vs registry HTTP hubs (matrix)

Exact or functional duplicates (park the extra):

| Plugin MCP | Registry / hub twin | Transport | This session | Park? |
|---|---|---|---|---|
| firecrawl | registry `firecrawl` HTTP + Grok `firecrawl-hub` :31414 | HTTP + HTTP hub | **both** firecrawl + firecrawl-hub | PARK hub on Grok; one hosted max |
| tavily | registry tavily **stdio** + search-hub Tavily lane | HTTP plugin vs stdio mux | search-hub yes; tavily plugin not in this tool list | PARK mux; park plugin until titled |
| exa | registry exa (hermes) + search-hub Exa lane | HTTP vs stdio mux | search-hub yes | PARK mux; park plugin until titled |
| context7 | registry/Cursor/Hermes context7 | HTTP | yes (2 tools) | PARK on Grok; KEEP Cursor G-6 |
| chrome-devtools (gemini-extension only) | Cursor G-6 chrome-devtools npx | stdio if loaded | not in this tool list | PARK plugin on Grok; KEEP Cursor |

Not registry-hub duplicates, still G-99 extras (park default):

cloudflare (5 HTTP), cockroachdb (stdio+HTTP+cloud), discord stdio, desktop-commander stdio, browser-use stdio, convex stdio, tinyfish HTTP, expo HTTP, CodSpeed HTTP.

## What not to do

- Do **not** add `grok` to `VALID_TARGETS` or write `merge_generated_grok_mcp.py` in this prune (DEDUP PLANNED-unbuilt). A merge that mirrored Hermes would **re-attach** the hubs this lens parks.
- Do **not** remount hexstrike-ai / hexstrike-ai-hub on Cursor (`CURSOR_RETIRED_SERVERS`).
- Do **not** `--attach-all-safe` to "fix" Cursor 13 — live is already 6; attach-all would pull parked-31 Claude stdio, not the Hermes hubs, and would still be a RAM bomb.
- Do **not** restart basic-memory / agent-mail or bind :18765/:18812/:18317.
- Do **not** rotate the mcphub token. Report blast radius only.
- Do **not** re-propose Mem0/Graphiti, Cursor BYOK, OpenRouter MCP, or a second orchestration runtime.

## Park order (if executing later; this unit is recommend-only)

1. Grok: disable `search-hub` (stdio, 84 tools).
2. Grok: disable hexstrike-ai-hub + the other eight `*-hub` blocks.
3. Grok: disable plugin MCP duplicates (firecrawl, tavily, exa, context7, cloudflare) and stdio plugins (browser-use, desktop-commander, discord, convex, cockroachdb).
4. Grok: park mcphub/fiddler/SaaS remotes; fix BM :18765 + agent-mail :18812 enable.
5. Cursor: no file change; G-6 KEEP.
6. Optional G-10: CLI-disable chrome-devtools + playwright only.

## Confidence

- Live Cursor = G-6 only: **almost certain** (re-read `mcp.json` + merge SAFE_DEFAULT + inventory).
- Grok search-hub is stdio and violates G-99: **almost certain** (TOML `command` + hub.py docstring + 84 tools this session).
- firecrawl plugin ∥ firecrawl-hub both loaded: **almost certain** (this session tool inventory + both config files).
- hexstrike OOM on Cursor: **likely** from merge comment + 150-tool Hermes measure + retired set + cybersafe receipt; this unit did **not** re-run an OOM reproduction (hub DOWN).
- chrome-devtools-mcp actually attaching on Grok: **uncertain** (no `.mcp.json`; gemini-extension only). Treat as park-plugin-id, not a proven second chrome-devtools process.

UNIT-COMPLETE: gem-prune
