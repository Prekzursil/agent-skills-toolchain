# Harness Audit — 27.08.2026

**Scope:** shared harness `C:\Users\Prekzursil\.agents` → Claude CLI, Codex, Cursor (via `scripts\sync_shared_state.ps1`)
**Auditor:** Cursor subagent (harness optimizer/auditor), run 2 (resumed after canceled run 1)
**overall_score:** **NOT-CHECKED** (deterministic scorer absent — see below). Qualitative scorecard is **unofficial**.

---

## Resumed section — recovery of canceled run 1

The prior run was canceled mid-flight. Recovered state (verified on disk, 04:45–04:55):

- `HARNESS-AUDIT_2026-08-27.md` did **not** exist — this file is the first write; nothing overwritten.
- Backup `C:\Users\Prekzursil\.agents\backups\cursor-plugin-cleanup-20260827-041500\` (04:23 today) contains pre-edit copies of `.cursor\mcp.json` (929 B, 6 servers) and `.cursor\settings.json` (2 141 B, 41 plugins all-false).
- **Run 1's edit DID land and is kept:** live `C:\Users\Prekzursil\.cursor\settings.json` now has **45** plugin entries — run 1 appended explicit `"enabled": false` for `compound-engineering`, `astronomer-data`, `canva`, `tavily` (the 4 that were previously unlisted). Not redone.
- Live `.cursor\mcp.json` is byte-identical to its backup — run 1 backed it up but made no edit. Consistent with the "document, don't edit" call on the scope duplicates (confirmed below).
- Earlier same-day backup `backups\openrouter-wave1-20260827-025618\` (02:56) belongs to the separate OpenRouter-wave track, not this audit.

## Deterministic part — harness-audit.js: NOT FOUND

Searched (scoped, no home-wide rg): `C:\Users\Prekzursil\.agents\scripts\`, `C:\Users\Prekzursil\source\qzp-lean\scripts\`, and `source\{agent-skills-toolchain, ast-harness-reconcile, databricks-fanout-harness, repos, tools, democracyos, bolteu-github}\scripts\`. No `harness-audit.js`; no metaswarm/ECC checkout under `source\` carries it. Numeric scores for the 12 categories are therefore **NOT-CHECKED**.

## Qualitative scorecard (unofficial — same 12 categories)

| # | Category | Verdict | Key evidence (exact paths) |
|---|----------|---------|---------------------------|
| 1 | Tool Coverage | GOOD | `agents.json` registry ~40 servers, per-server `targets` (Claude 40/40, Codex 4/40, Cursor mirror trimmed to 6 live + `mcp-cursor-parked-31.json`). Merge scripts present: `scripts\merge_generated_{claude,codex,cursor}_mcp.py`. |
| 2 | Context Efficiency | **FAIL (2 findings)** | (a) Cursor MCP scope duplicates — see Finding A. (b) Skill list double-loaded by drive-letter casing — see Finding B. `.agents\skills` = 359 dirs, `.claude\skills` = 359 (parity OK; the bloat is Cursor-side listing, not vault drift). |
| 3 | Quality Gates | PARTIAL | Gates exist in `~\CLAUDE.md` (design/plan review, coverage SSOT) and `.agents\zero-issue-coding\`; but no runnable harness-wide gate script (`harness-audit.js` absent). |
| 4 | Memory Persistence | **DEGRADED (tracked elsewhere)** | basic-memory red, `ECONNREFUSED 127.0.0.1:8765` (`.cursor\mcp.json` → `"basic-memory": {"url": "http://127.0.0.1:8765/mcp"}`). **A sibling agent is building the watchdog — deliberately NOT duplicated here.** Contrast: agent-mail on 8812 is supervised (`MCPAgentMailSupervisor`) and healthy. |
| 5 | Eval Coverage | WEAK | `.agents\tests\` exists but no harness-level eval loop; deep-research skill telemetry **42 % success** (given) has no automated regression harness. |
| 6 | Security Guardrails | GOOD | `.agents\secrets\` + `secure-evidence\` segregated; `scripts\audit_secret_artifacts.py`, `credential_rotation_manifest.json`, `protect_flagged_artifacts.ps1` present; `.cursor\mcp.json` uses `${env:...}` for CONTEXT7/FIRECRAWL keys (no literals). |
| 7 | Cost Efficiency | GOOD | OpenRouter correctly held as CLI/Codex sidecar only (`scripts\openrouter-complete.{ps1,py}`, skill `openrouter-routing`) — no MCP, no BYOK. Cursor plugin map 45/45 disabled avoids duplicate paid tool mounts. |
| 8 | GitHub | PARTIAL | `agents.json` has `https://api.githubcopilot.com/mcp` (targets codex+claude) + `gh-cli-mcp`; not mirrored to Cursor (by design — Cursor uses `gh` CLI). |
| 9 | Vercel | NOT-CHECKED | No Vercel MCP in the 6-server Cursor set; skill `vercel-deploy` exists in vault. Not exercised this audit. |
| 10 | Netlify | NOT-CHECKED | Skill `netlify-deploy` + plugin `netlify-skills` (disabled, correct). Not exercised. |
| 11 | Cloudflare | NOT-CHECKED | Skill `cloudflare-deploy` + plugin `cloudflare` (disabled, correct). Not exercised. |
| 12 | Fly | NOT-CHECKED | No Fly skill/MCP found in `.agents\skills` or `agents.json`. Genuine gap candidate, low priority. |

## Failed checks — detail

### Finding A — Cursor MCP user-vs-project scope duplicates (document-only; edit is ambiguous)
Observed: `agent-mail`, `basic-memory`, `chrome-devtools`, `context7`, `firecrawl`, `playwright` each mount twice (namespaces `user-*` and `project-0-Prekzursil-*`).
Root cause: **the Cursor workspace root IS the home directory** (`C:\Users\Prekzursil`), so the single file `C:\Users\Prekzursil\.cursor\mcp.json` is read **both** as user-level MCP config **and** as the workspace's project-level `.cursor\mcp.json`. Same six JSON pointers serve both scopes: `/mcpServers/agent-mail`, `/mcpServers/basic-memory`, `/mcpServers/chrome-devtools`, `/mcpServers/context7`, `/mcpServers/firecrawl`, `/mcpServers/playwright`.
Why no edit: deleting any pointer removes the server from **both** scopes (there is no second file to keep it in). The unambiguous fixes are structural, not JSON: (1) stop opening `C:\Users\Prekzursil` itself as a workspace (open subfolders/projects instead), or (2) rely on Cursor deduplicating same-file scopes. Per contract, **documented, not edited**.

### Finding B — skill list double-loaded via path casing
Cursor's loaded-skill list enumerates every `.claude\skills\<name>\SKILL.md` twice: once as `C:\Users\Prekzursil\...` and once as `c:\Users\Prekzursil\...`. 359 vault skills (+16 `.cursor\skills-cursor` + 2 `.codex\skills`) thus present as "538+". This is a Cursor path-normalization artifact, not vault duplication — fix belongs upstream (workspace/path casing), not in the vault.

### Finding C — Cursor plugins vs vault skills (resolved by run 1 + this run's verification)
Plugins UI showed `boltable` + `common` (Bolt Technology OÜ team) while enable-map was all-false. Live `settings.json` now explicitly disables **45/45** plugins including team ones. Vault copies remain canonical: `deep-research`, `grill-me` etc. live in `.agents\skills\` (materialized to `.claude\skills\`). Plugin-side duplicates that must stay off: `firecrawl`, `playwright`, `context7-plugin`, `superpowers`, `semgrep-plugin`, `sentry`, `tavily` — all confirmed `"enabled": false`.

### Finding D — orphan atomic-write temp files (fixed this run)
17 stale `local.json.<uuid>.tmp` files sat in `.agents\` root (failed atomic writes). Moved (not deleted) to `backups\localjson-tmp-cleanup-20260827-0450\`. `local.json` itself untouched and re-validated as JSON.

## Files changed this run
- **Moved:** 17 × `C:\Users\Prekzursil\.agents\local.json.*.tmp` → `C:\Users\Prekzursil\.agents\backups\localjson-tmp-cleanup-20260827-0450\` (reversible).
- **Created:** this report.
- **Validated (no edit):** `.agents\local.json`, `.agents\agents.json`, `.cursor\mcp.json`, `.cursor\settings.json` — all parse as valid JSON.
- **Not touched (guardrails honored):** `agents.json` `integrations.enabled` stays `[]` (line 7); no Cursor logout; no MCPs added; no OpenRouter MCP/BYOK/LiteLLM/LangGraph/vector-DB/Sentry#2/trained critic; no second basic-memory watchdog.

## Top 3 actions
1. **Kill the MCP scope duplication at the source:** stop opening `C:\Users\Prekzursil` (home) as a Cursor workspace; open per-project roots so `.cursor\mcp.json` is loaded once (user scope only). Halves MCP mounts and fixes the `C:`/`c:` skill double-listing in one move.
2. **basic-memory:** track the sibling watchdog to completion (port 8765, mirror the proven `MCPAgentMailSupervisor` pattern on 8812); until green, treat basic-memory writes as best-effort and verify reads.
3. **Add a deterministic scorer:** port/adopt `scripts/harness-audit.js` (12 fixed categories) into `.agents\scripts\` so the next audit emits numbers instead of NOT-CHECKED; wire it into `sync_shared_state.ps1` as a post-sync check.

## Suggested next skills
- `harness-audit-runner` — wraps the future `harness-audit.js`, emits the 12-category scorecard + NOT-CHECKED discipline.
- `deep-research-triage` — instrument the 42 %-success deep-research skill: capture failure modes per run, feed `continuous-learning-v2`.
- `fly-deploy` — only genuine deploy-target gap in the vault (Vercel/Netlify/Cloudflare/Render covered).
