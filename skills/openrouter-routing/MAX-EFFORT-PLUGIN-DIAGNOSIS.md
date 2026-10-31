---
title: MAX-EFFORT-PLUGIN-DIAGNOSIS
type: note
permalink: dqverify-repo-20261013/skills/openrouter-routing/max-effort-plugin-diagnosis
---

# Max Effort plugin diagnosis (Wave 0)

Date: 27.08.2026  
Track: parallel to OpenRouter cap/smoke — **not** an OpenRouter fix.  
Method: read-only inventory. No logout, no storage/cookie/auth wipe, no OpenAI base-URL write.

**What actually changed this session: nothing in Cursor settings, plugins, extensions, or auth.**  
`C:\Users\Prekzursil\.cursor\mcp.json` was rewritten **during** this investigation (full fleet with `disabled: true` → six always-on servers). That write was **not** this track. Do not treat it as a completed Max Effort experiment until Cursor is restarted and Max Effort is re-tested.

Coverage: `NOT-CHECKED` for live Max Effort UI (cannot toggle Max Effort from this agent session). Inventory below is on-disk + this session’s loaded MCP namespaces.

---

## Verdict (short)

1. **Every plugin in the Cursor enable-map is already `enabled: false`.** Flipping one of those flags again will not change behavior.
2. **The likely culprits are not in that map.** Gem-hunt names are in the marketplace **cache** and inject skills/hooks/MCP if Cursor treats cache as installed: **compound-engineering** (32 skills, multi-runtime), **astronomer-data** (33 skills + every-prompt hook), **canva** (skills + remote MCP), plus **Bolt team marketplace** and leftover **MCP tool schemas**.
3. **Do not disable** Anysphere Remote WSL/SSH/Containers (not login, but not the Max Effort bug; leave them).
4. **Binary-search first move (you click, after a restart):** add one explicit enable-flag for `compound-engineering`. If Max Effort is still dead, next is `astronomer-data`, then `canva`. Rollback is deleting that key or setting `enabled: true`.

---

## 1. Installed vs enabled

### A. VS Code-style extensions (`%USERPROFILE%\.cursor\extensions`)

Source: `C:\Users\Prekzursil\.cursor\extensions\extensions.json`.

| ID | Version | Enabled? | Notes |
| --- | --- | --- | --- |
| `anysphere.remote-wsl` | 1.0.13 | **yes** (no disabled flag; application-scoped) | Cursor remote. Leave on. |
| `anysphere.remote-ssh` | 1.1.14 | **yes** | Leave on. |
| `anysphere.remote-containers` | 1.0.39 | **yes** | Leave on. |

No other gallery extensions. These are **not** the marketplace plugins from gem-hunt.

### B. Cursor marketplace plugins — enable-map (this is the on/off SSOT)

Source: `C:\Users\Prekzursil\.cursor\settings.json` → `plugins`.

**Enabled: none. Installed-in-map: 41. All `enabled: false`.**

| Plugin id | Enabled |
| --- | --- |
| mixpanel-mcp | false |
| forge | false |
| apify | false |
| browserstack | false |
| context7-plugin | false |
| exa | false |
| figma | false |
| firecrawl | false |
| github | false |
| gitlab | false |
| huggingface-skills | false |
| linear | false |
| playwright | false |
| semgrep-plugin | false |
| sentry | false |
| superpowers | false |
| netlify-skills | false |
| cloudflare | false |
| render | false |
| bright-data | false |
| parallel | false |
| apis | false |
| boltable | false |
| commerce | false |
| common | false |
| customer-payments-skills | false |
| delivery-management | false |
| design | false |
| developers-ai-marketplace | false |
| diy-unmoderated-usability-test | false |
| im-rides | false |
| insights | false |
| internal-products | false |
| jira-hygiene | false |
| n8n | false |
| new-bets-strategy-skills | false |
| performance-creative-automation | false |
| performance-cycle | false |
| rider-qa | false |
| usability-reviewer | false |
| ux-research | false |

**History (from local backups, not live UI):**

- `settings.json.bak-20260820-142444`: only `tavily: enabled true`.
- `settings.json.bak-20260822-231534` and `settings.json.bak-forge-2026-08-20`: `tavily: true`, rest of the Bolt/public set false.
- **Current map dropped `tavily` entirely** (not even `false`). Cache for `tavily` still exists. Missing-from-map ≠ proven uninstalled; it is the last plugin that was **known-on**.

### C. Plugin cache (gem-hunt names) — downloaded, enable-state **uncertain**

Layout: `C:\Users\Prekzursil\.cursor\plugins\` → `cache\`, `local\` (empty), `marketplaces\`.

`.cursorignore` already excludes `/.cursor/plugins/cache/` (RAM). Cache is still on disk.

**`cache\cursor-public\`:** ~174 plugin folders (full public catalog cache, not a sane “I installed 174 plugins” list). Presence here is **not** proof of enabled.

Gem-hunt four + close cousins (all **absent** from the enable-map except where noted):

| Cache id | Version (manifest) | In enable-map? | Injection surface if Cursor loads it |
| --- | --- | --- | --- |
| **compound-engineering** | 3.21.0 | **no** | **32 skills**; adapters for `.cursor-plugin`, `.claude-plugin`, `.codex-plugin`, `.agy`, `.agents`, `.cline`, `.devin-plugin`, `.grok-plugin`, `.kimi-plugin`, `.opencode`, `.pi`. Highest Max Effort risk. |
| **astronomer-data** | 0.1.0 | **no** | **33 skills**; hooks `beforeSubmitPrompt` + `stop` (runs on **every** prompt if active). |
| **canva** | 1.0.0 | **no** | **6 skills** + MCP `https://mcp.canva.com/mcp`. |
| **bolt** | (no public id `bolt`) | — | Team marketplace `bolt-technology-o/ai-marketplace-public` + cache `bolt-ai-marketplace-ai-marketplace-public` + plugin `boltable` (map: **false**). |
| superpowers | 6.1.1 | **false** | Large methodology pack. Skills may still live in `~/.claude/skills` after disable. |
| forge | 1.2.2 | **false** | Work-order / ForgeScore MCP-ish product. |
| tavily | 2.0.0 | **missing** (was **true**) | Web search/crawl CLI plugin. |
| continual-learning | 1.0.0 (Cursor) | **no** | First-party. Hook **state exists** and has `lastRunAtMs` — this one **did run**, unlike CE/Canva/Astronomer which have no hook-state files here. |
| playwright / firecrawl / context7-plugin | cached | **false** | Duplicate of always-on MCP in `mcp.json`. |

**Bolt team marketplace** (`marketplaces\origin.cursor.com\bolt-technology-o\ai-marketplace-public\…\marketplace.json`): 24 plugin ids. Most are in the enable-map as false. **Not in the map:** `comms-privacy-dev`, `analytics-engineering-tooling`, `micromobility-supply-chain-team`, `talent-management`, `central-fp-a`. Team policy can override local false — **NOT-CHECKED** (needs Cursor Settings → Plugins UI / team admin).

`continual-learning` hook state: `C:\Users\Prekzursil\.cursor\hooks\state\continual-learning.json` (`lastRunAtMs` present, `turnsSinceLastRun: 4`). Product plugin, not login. Redundant with basic-memory + `AGENTS.md`, but **not** proven to be the Max Effort break.

---

## 2. Max Mode / Max Effort / models (no OpenAI base URL)

### AppData User `settings.json`

`C:\Users\Prekzursil\AppData\Roaming\Cursor\User\settings.json` — **400 bytes**. Keys only:

- `cursor.composer.codeBlockWordWrap`
- `cursor.composer.conversationDensity` = `detailed`
- `cursor.glassWorkspaceLspMaxLocalWorkspaces` / `Remote` = 9999
- `cursor.worktreeMaxCount` / `worktreesGlobalMaxSizeGb`

**No `openai.baseURL`, no OpenRouter, no API key, no Max Effort toggle.** Do not add a base URL.

### CLI / Composer model store

`C:\Users\Prekzursil\.cursor\cli-config.json` (do not commit; contains account metadata):

- `maxMode`: **true**
- `maxModeAutoEnabled`: false
- Model: `grok-4.6` with `effort: xhigh`, `fast: false`
- Also stored: `claude-fable-5` effort `high`, context `1m`
- Channel: `prod-stable-internal`
- Privacy cache: ghost mode on, privacyMode 2

Max Effort is **requested** in config. If the UI still fails, it is product/plugin/context load, not “Max Mode unset.”

---

## 3. Duplicate skills / MCP (Cursor always-on vs Claude fleet)

### Cursor `mcp.json` **now** (six always-on)

`C:\Users\Prekzursil\.cursor\mcp.json`:

| Server | Cursor | Claude `agents.json` |
| --- | --- | --- |
| agent-mail | always-on | enabled (targets include claude) |
| basic-memory | always-on | enabled |
| chrome-devtools | always-on | enabled (claude-only tag) |
| context7 | always-on | enabled |
| firecrawl | always-on | enabled |
| playwright | always-on | enabled |

All six Cursor always-on servers are **also** in the Claude registry. That is the intended mirror, not a second product. Duplication **inside one Cursor session** still hurts: this session exposed **both** `project-0-Prekzursil-basic-memory` **and** `user-basic-memory`, and **both** `project-0-Prekzursil-playwright` **and** `user-playwright`.

### Claude fleet (`C:\Users\Prekzursil\.agents\agents.json`)

~40 servers, **no** `"enabled": false` in the registry. Claude `settings.json` `deniedMcpServers`: markitdown, rdkit, serena, gitlab, meta-tool.

Cursor is supposed to be a **subset**. A backup from 26.08.2026 (`mcp.json.bak-20260826-163712`) still had the **full** fleet with **no** `disabled` flags. At the start of this diagnosis the live file looked like that fleet plus `disabled: true`. It then became the six-server file. **This Cursor session still advertised** hexstrike, ghidra, ida-pro, frida, cheatengine, binary-ninja, docker, postgres, sonarqube, linear, notion, repomix, github_cli, claude-code-mcp, semgrep, etc. Tool-schema load can survive `mcp.json` edits until **restart**.

Hexstrike’s tool list alone is a Max Effort-sized context tax.

### Skills

This Cursor agent session listed **538+** skills from `~\.claude\skills` and `~\.codex\skills` plus `~\.cursor\skills-cursor` (product builtins; sync-manifest ~24 Cursor skills). Marketplace **superpowers** is flag-false, but the vault still holds that style of skill. That is harness share (`AGENTS.md`), not a Cursor plugin flag — same failure mode (context bloat), different knob.

Plugin cache CE/Astronomer skills were **not** obviously named in the truncated skill list; if they inject, it is via plugin runtime, not the vault copy.

---

## 4. Most likely Max Effort culprits (ranked)

| Rank | Suspect | Why | Confidence |
| --- | --- | --- | --- |
| 1 | **compound-engineering** cache load | 32 skills + many harness adapters; classic “marketplace plugin killed Max Effort” shape; **not** in the false-map so it may still be implicit-on | Medium — cache-present, enable **NOT-CHECKED** |
| 2 | **astronomer-data** | 33 skills + **beforeSubmitPrompt** hook every turn | Medium — same enable uncertainty |
| 3 | **MCP schemas still bound in the live session** | Disabled/removed servers still in the tool list (hexstrike-class) | High for *this* session; after restart **NOT-CHECKED** |
| 4 | **Shared skill vault in Cursor** | 538+ skills injected via harness pointer | High for bloat; may be independent of marketplace |
| 5 | **canva** | Extra remote MCP + skills | Lower unless enabled |
| 6 | **tavily** last-known-on | Was `enabled: true`; now omitted from map | Medium for “what broke it originally” |
| 7 | **Bolt `common` / team override** | Large skill packs (write-right, token-diet, …); local flag already false | Low–medium; team override NOT-CHECKED |
| 8 | **continual-learning** | Proven to have run (hook state); first-party; writes preferences | Low for *the* break; easy later trial |
| 9 | Anysphere remotes | Unlikely | Very low |

Privacy/team/channel (`prod-stable-internal`, ghost mode) are **NOT-CHECKED** as Max Effort blockers; do not chase them before plugins/MCP restart.

---

## 5. Binary-search DISABLE ORDER (with rollback)

**Do not delete cache folders. Do not clear AppData. Do not log out.** Only `~\.cursor\settings.json` → `plugins.<id>.enabled`.

Copy `settings.json` to `settings.json.bak-max-effort-YYYYMMDD-HHMM` before any edit (this track did not).

### Phase 0 — restart only (no flag change)

All 41 mapped plugins are already false. **Restart Cursor**, new chat, test Max Effort.

- If **fixed:** leftover MCP schemas / stale plugin runtime. Rollback: none.
- If **still broken:** go to Phase 1.

### Phase 1 — unmapped heavies (add explicit `false`, **one** per restart)

Order:

1. **`compound-engineering`**
2. **`astronomer-data`**
3. **`canva`**
4. **`tavily`** (explicit false, in case omit-from-map still loads cache)
5. **`continual-learning`** (first-party; only after 1–4 fail)

Example (Phase 1.1):

```json
"compound-engineering": { "enabled": false }
```

**Rollback:** delete that key, or `"enabled": true`, restart.

**Re-enable in UI:** Cursor Settings → Plugins → find the plugin → Enable. If it never appeared as installed, the flag was a no-op.

### Phase 2 — Bolt team pack

Already false locally. If Max Effort still dead after Phase 1: disable in **team** Plugins UI (or ask team admin). Binary-split: `common` + `boltable` vs the rest.

**Rollback:** re-enable those two in the same UI.

### Phase 3 — MCP (not plugins)

After a clean restart, if the session still lists hexstrike-class tools: the six-server `mcp.json` is not what the process loaded. Then temporarily keep only `agent-mail` + `basic-memory` (move the other four out of `mcp.json` into a sidecar file).

**Rollback:** restore `mcp.json.bak-20260826-163712` or the six-server file — **never** a storage reset.

### Phase 4 — skill vault (harness, not marketplace)

Only if 0–3 fail: Cursor loading `~\.claude\skills` / `~\.codex\skills`. That is `AGENTS.md` / skills pointer — out of this plugin binary search.

### Do not binary-search

- Anysphere `remote-wsl` / `remote-ssh` / `remote-containers`
- Auth, cookies, `state.vscdb`, ghost-mode toggle
- OpenAI / OpenRouter base URL
- Deleting `plugins\cache` (not an enable-flag; painful rollback)

---

## 6. The one disable this track *would* have done (not done)

**Not done.** Unsure whether `compound-engineering` is actually enabled (cache-only vs installed). Instruction: inventory only.

If you want one reversible Cursor-only flag that cannot log you out:

1. Backup `C:\Users\Prekzursil\.cursor\settings.json`.
2. Add `"compound-engineering": { "enabled": false }` under `plugins`.
3. Restart Cursor. Test Max Effort.
4. Re-enable: set `true` or remove the key; or Plugins UI → Enable.

`continual-learning` is the only cache plugin **proven** to have executed (hook state), but it is a product learning loop, not clearly redundant for Max Effort, so it was not flipped.

---

## 7. What this track changed

| Item | Action |
| --- | --- |
| Plugin enable flags | **None** |
| Extensions | **None** |
| AppData settings / OpenAI URL | **None** (read only; no base URL present) |
| Auth / cookies / storage | **None** |
| `mcp.json` | **Not this track.** File content changed during the window; restart Cursor before treating MCP as the experiment. |

---

## 8. Next measurement (after you restart)

1. New agent chat → Max Effort / Max Mode on Grok 4.6 Extra High (already `maxMode: true` in cli-config).
2. Snapshot MCP: if hexstrike-class tools are gone, Phase 3 is done.
3. If still broken → Phase 1.1 `compound-engineering` flag only.

---

## 9. Cleanup track (27.08.2026) — pointer

Wave 0 above is still the read-only inventory. The follow-up **did** pin cache-only plugins false and left the catalog on disk.

See: [`MAX-EFFORT-PLUGIN-CLEANUP_2026-08-27.md`](MAX-EFFORT-PLUGIN-CLEANUP_2026-08-27.md)