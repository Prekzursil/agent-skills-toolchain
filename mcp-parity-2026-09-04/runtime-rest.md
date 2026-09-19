# Runtime-rest vs 2026-08-27 scorecard (disk re-read 2026-09-04)

Q1 Hermes fold land? **YES MCP+skills; NO rules pointer.**
Q2 Goose skills unverified? **Search path YES still unverified; tree now exists.**
Q3 Agy vault-orphaned? **YES** (`~\.gemini\skills` still 26 GCP-stock dirs).

Evidence from named-file re-reads, not the inventory digest. No home rglob.

## Hermes (absent from scorecard 08-27)

- Fold signals: `mcp_control_plane.py:15` VALID_TARGETS={claude,codex,zcode,hermes};
  `sync_shared_state.ps1:194-214` calls `deploy_hermes_mcp.py` + `sync_hermes_skills.ps1`;
  receipt `HERMES-HARMONIZATION_2026-09-03.md:1-39` (G-1 HTTP-only, G-3 robocopy /MIR).
- MCP **17 HTTP** `AppData\Local\hermes\config.yaml:188-232` = `inventory.json:265-283`:
  agent-mail, basic-memory, cloud-audit-hub, context7, cve-mcp-hub, deepwiki, exa,
  firecrawl, github-security-hub, hexstrike-ai-hub, nuclei-hub, openaiDeveloperDocs,
  osint-hub, semgrep-hub, web-reader, web-search-prime, zread.
  All `url:` (`deploy_hermes_mcp.py:20-23` ALLOWED_TRANSPORTS={url}). 17/17 (`inventory.md:14`).
- Second-config **YES**: live `config.yaml` mcp_servers vs vendor `hermes-agent/optional-mcps`
  (65 yaml) + `hermes-agent/skills` + `plugins`. Merge YES (`inventory.json:293`).
  Backups `config.yaml.bak-20260903-*` and `bak-20260904-222855`.
- Skills: `%LOCALAPPDATA%\hermes\skills` vault-shaped (`sync_hermes_skills.ps1:16-32` /MIR).
  `config.yaml:105-106` no extra_skill_dirs. SKILL.md **NOT-COUNTED** (listing truncated;
  receipt claims 381).
- Memory **DUAL**: native `config.yaml:97-102` memory_enabled:true +
  `AppData\Local\hermes\memories\MEMORY.md` AND BM `http://127.0.0.1:18765/mcp`
  (`config.yaml:191-192`). Parallel vs G-81.
- Rules **NOT folded**: no AGENTS pointer in config.yaml; `SOUL.md` vendor persona;
  `hermes-agent/AGENTS.md:1-14` upstream dev guide.

## Goose

- MCP **2 HTTP unique** (basic-memory, agent-mail). Duplicate YAML keys:
  `config.yaml:3-16` (`url:`) then `:141-158` (`uri:`). Last-wins not runtime-proven.
- Enabled unique extensions **11**: BM, agent-mail, apps, skills, extensionmanager,
  analyze, todo, scheduler, summon, tom, developer. Builtin memory **false** (`:125-132`).
  Skills ext `:45-51` “filesystem and builtins” — **no path key**.
- Second-config **YES**: XDG `~\.config\goose\config.yaml` (G-12 SSOT) and scorecard path
  `AppData\Roaming\Block\goose\config\config.yaml` — identical children + bak stamps
  (junction-vs-copy not metadata-proven). Merge **NO** (`inventory.json:295`).
- Skills tree **now present** at `...\goose\config\skills` (DEPLOYED-MANIFEST).
  Scorecard `CROSS-RUNTIME-SCORECARD_2026-08-27.md:16` said none under AppData.
  Runtime search path **still UNVERIFIED** (no --help/docs; config has no vault path).
- Memory: BM HTTP `:18765` only; bundled memory off.
  Rules: `GOOSE_MOIM_MESSAGE_FILE` `:161` → `C:\Users\Prekzursil\.agents\AGENTS.md:1-9`.

## Agy / Antigravity (`~\.gemini`)

- Skills **26 GCP-stock** (scorecard `:15,:37`). Names: accidental-data-loss-prevention,
  bigquery-ai-ml, bigquery-bigframes, bigquery-data-transfer-service, bigquery-graph,
  bigquery-sql, building-data-apps, data-autocleaning, dataform-bigquery, dbt-bigquery,
  discovering-gcp-data-assets, enforcing-resource-attribution, federate-lakehouse-catalog,
  gcloud-auth-verification, gcp-composer-troubleshooting, gcp-data-pipelines, gcp-dataflow,
  gcp-managed-airflow-migrations, gcp-pipeline-orchestration,
  gcp-pipeline-resource-provisioning, gcp-spark, gcs-security-assessment,
  managing-python-dependencies, ml-best-practices, notebook-guidance, skill-repair.
  No vault names. `settings.json:23-25` skills.enabled only — no extraDirs.
- Extra non-vault: `extensions/{chrome-devtools-mcp,metaswarm,superpowers}`;
  enablement chrome-devtools-mcp + superpowers (`extension-enablement.json:1-11`).
- MCP **not from agents.json** (agy ∉ VALID_TARGETS). Gemini CLI
  `settings.json:26-326` **33** mcpServers (mostly stdio). Agy
  `config\mcp_config.json:1-14` = `antigravity-cli\mcp_config.json` **3**
  (agentchattr disabled, chrome-devtools disabled, monk enabled). No BM / agent-mail.
- Second-config **YES**. Merge **NO** (`inventory.json:296`).
  Memory **not BM**: `settings.json:182-191` npx `@modelcontextprotocol/server-memory`
  → `C:/Users/Prekzursil/.gemini/memory.jsonl`; plus `antigravity-cli/knowledge/`
  + `conversation_summaries.db`.
  Rules: `~\.gemini\AGENTS.md:1-11` inline addendum.

## Fabric

- MCP n/a. Merge **NO**. Second-config **NO**. Memory none.
- `unique_patterns.txt` **257** names (line 257 `youtube_summary`; scorecard 255).
  `patterns/` subtree 331 files. `~\.config\fabric\sessions\` **empty**.
  No AGENTS.md under `~\.config\fabric`.

## Regressions vs scorecard `:27-32`

- Sync then claude+codex+cursor. Now +zcode+hermes (`inventory.json:1088-1100`).
  Still **not** grok/goose/agy/fabric.
- Hermes: new first-class target; rules pointer still missing.
- Goose: skills **tree appeared**; **search path still unverified**.
- Agy: **still vault-orphaned**. MCP grew private 33+3; parallel server-memory —
  vs scorecard “None from shared plane” and G-72 HTTP-hubs-only.
- Fabric: still unused (0 sessions); pattern names 255→257.

UNIT-COMPLETE: runtime-rest
Receipt: C:\Users\Prekzursil\.agents\mcp-parity-2026-09-04\runtime-rest.md
