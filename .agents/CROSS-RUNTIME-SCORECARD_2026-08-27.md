# Cross-Runtime Compatibility Scorecard — 2026-08-27

Verifies the AGENTS.md "Universal harness share (HARD)" mandate: every runtime loads skills
from `C:\Users\Prekzursil\.agents\skills` (359 skills measured today) and rules/behavior from
`C:\Users\Prekzursil\AGENTS.md` (or a compliant pointer/addendum). All rows measured on this
box 2026-08-27 by direct inspection of each runtime's config — not from memory.

| Runtime | Skills source | Rules source | MCP source | Synced by | Gaps |
|---|---|---|---|---|---|
| **Claude CLI** | `~\.claude\skills` materialized copy — **359/359 parity confirmed today**; plus `~\.claude\skills.daily` = Junction → `.agents\skills` (full vault) | `~\AGENTS.md` + `~\.claude\AGENTS.md` (Cross-Tool Behavior Contract addendum) + `~\.claude\CLAUDE.md` | Claude JSON merge from `.agents\agents.json` (40/40 per 2026-08-20 measurement) | `sync_shared_state.ps1` (Claude JSON merge) | None found |
| **Codex CLI** | `~\.codex\skills` holds only 3 Codex-local dirs (`.system`, `hatch-pet`, `skill-stocktake`) — per contract it is Codex-owned; shared skills arrive via the `agent-skills-toolchain@agent-skills-toolchain` plugin mount in `config.toml` | `~\.codex\AGENTS.md` ("ChatGPT / Codex host instructions" addendum) + `~\AGENTS.md` | Codex TOML merge — only servers whose `targets` include `codex` (4/40 per 2026-08-20) | `sync_shared_state.ps1` (Codex TOML merge, preserves non-MCP settings) | Shared-skill surface depends on the plugin staying mounted; no direct `extra_skill_dirs`-equivalent pointing at the vault. `config.toml` contains **zero** direct `.agents` references — verify plugin actually exposes all 359 skills before trusting parity |
| **Cursor** | `~\.claude\skills` + `~\.cursor\skills-cursor` (Cursor reads the Claude materialization — confirmed: this session's skill list is served from `.claude\skills`) | `~\CLAUDE.md` + `~\AGENTS.md` injected as always-applied workspace rules | `.cursor\mcp.json`: 6 servers enabled, 0 disabled; 31 parked in `.agents\mcp-cursor-parked-31.json` (= 37 managed) | `sync_shared_state.ps1` (`merge_generated_cursor_mcp.py`) | None blocking; parity is transitive through the Claude materialization |
| **Grok CLI** | `config.toml [paths] extra_skill_dirs = ['C:\Users\Prekzursil\.agents\skills']` (full vault, verified line 239); `~\.grok\skills` deliberately empty (`default_skills_installs_purged`) | `~\.grok\AGENTS.md` — Grok-tailored contract (<10k chars, Grok truncates rules files at 10,000 chars) pointing at canonical `~\AGENTS.md`; plus `extra_rule_dirs = ['...\.agents\rules']` (line 240) | Grok-native `config.toml` MCP entries (incl. `.agents\meta-tool` servers) — NOT fed from `agents.json` | Manual (GrokHarness audit 2026-08-07 wiring); **not** in `sync_shared_state.ps1` | MCP inventory is hand-maintained in `.grok\config.toml`, drift-prone vs `agents.json`. Skills/rules: fully bridged |
| **Agy / Antigravity** | `~\.gemini\skills` = 26 dirs, ALL Google/BigQuery stock skills — **vault NOT loaded** (no junction, no extra-dirs config found) | `~\.gemini\AGENTS.md` — agy addendum with security non-negotiables inlined (added 2026-08-07; agy does not follow pointer files, so load-bearing rules are inline) | None from shared plane found | Manual (2026-08-07 parity fix); **not** in `sync_shared_state.ps1` | **Skills orphaned.** Usage evidence exists (`~\.gemini\history` present). Smallest fold: determine whether Antigravity supports extra skill dirs or junctioned subdirs; if junction-safe, one `New-Item -ItemType Junction .gemini\skills\<vault-link>` step in `sync_shared_state.ps1` — do NOT bulk-copy 359 skills into it |
| **Goose** | Own `skills` platform extension ("filesystem and builtins") — no evidence its search path includes the vault; no skills dir under `AppData\Roaming\Block\goose\config` | `GOOSE_MOIM_MESSAGE_FILE: C:\Users\Prekzursil\.agents\AGENTS.md` in `config.yaml` → loads the 10-line pointer (compliant pointer-file form) | Goose-native `config.yaml` extensions; not fed from `agents.json` | Manual (config.yaml edits, backups dated 2026-08-26); **not** in `sync_shared_state.ps1` | **Skills path unverified.** Usage evidence: 3 sessions in `data\sessions`. Smallest fold: confirm the goose skills extension's search path first (its docs/`--help`), then point it at the vault via config.yaml — one merged key, no new script |
| **Fabric** | n/a — Fabric uses `patterns` (255 stock patterns in `~\.config\fabric\patterns`), no skills concept | None — no AGENTS.md/pointer anywhere under `~\.config\fabric` | n/a | Nothing | **Orphaned but effectively unused: 0 sessions.** Recommendation: do NOT build a bridge (no usage evidence — AGENTS.md mandate applies to runtimes in use). If Fabric gets adopted, a pattern that embeds the pointer text is the smallest fold |

## Highlights

- **Fully bridged:** Claude (359/359 parity re-verified today), Cursor (transitively via the
  Claude materialization + workspace-rule injection), Grok (best non-Claude bridge on the box:
  vault + rules dirs wired natively in `config.toml`).
- **Bridged for rules, gapped for skills:** Codex (plugin-mediated, unverified 359-parity),
  Agy (26 stock Google skills only), Goose (pointer file loaded via env, skills path unknown).
- **Orphaned:** Fabric — but with 0 sessions ever, it fails the usage-evidence bar for
  building a bridge. NOT-CHECKED whether the fabric binary is even on PATH.
- **Sync coverage:** `sync_shared_state.ps1` covers exactly Claude + Codex + Cursor merges.
  Grok/Agy/Goose were wired manually in one-off audits (2026-08-07, 2026-08-26) and can drift
  silently. The cheapest durable fix is a read-only **drift check** appended to
  `sync_shared_state.ps1` that asserts the Grok `[paths]` lines, the Goose
  `GOOSE_MOIM_MESSAGE_FILE` key, and the `.gemini\AGENTS.md` presence — warning on drift
  without writing to any runtime's config (no new merge scripts until skills-path questions
  above are answered with evidence).

## Evidence trail (for re-verification)

- Vault count: `Get-ChildItem ~\.agents\skills -Directory` → 359; `~\.claude\skills` → 359;
  `~\.codex\skills` → 3; `~\.gemini\skills` → 26 (all GCP-stock names).
- Grok: `~\.grok\config.toml` lines 239–240; `~\.grok\AGENTS.md` header (GrokHarness audit note).
- Goose: `AppData\Roaming\Block\goose\config\config.yaml` (`GOOSE_MOIM_MESSAGE_FILE`,
  `skills:` platform extension block); 3 files in `data\sessions`.
- Cursor: `.cursor\mcp.json` → 6 servers, 0 disabled; `.agents\mcp-cursor-parked-31.json` → 31 parked.
- Fabric: `~\.config\fabric` → `patterns` (255), `sessions` (0), `.env` present (not read — may hold keys).
