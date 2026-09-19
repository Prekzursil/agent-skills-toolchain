# Estate MCP / TUI / Skills Audit — Master Report

**Run:** 2026-09-19, harness-audits/2026-09-19-mcp-tui-audit · **Lanes:** waveA A01-A20 (80 per-server verdicts), waveB B1-B7 (TUI/surface lanes), waveC C1-C8 (skills/rules hygiene), waveD V1-V5 (adversarial verification) + R1-R5 (reprobes) · **Mandate:** READ-ONLY — no config edited, no commits, no process kills; only verdict files + this report written. All 45 verdict files read and folded in; scoreboard.json is the machine-readable twin.

**Verdict on the ground-truth set:** 5 claims, 5 corrected. (1) registry is **81 servers, not 80** — `video-agent-kit` was added at 06:59, after the 05:41 snapshot (B2/B3/B4/B5/B6/B7/C4/C8/V2/V3/V4 — unanimous, jq/node/tomllib independent parses). (2) `~/.claude.json` root mcpServers is **87, not 86** (same edit); `~/.mcp.json` holds **34 servers, not "19+"**, of which only **14 are truly undocumented** (C5/V4). (3) the "failed to connect" list: root cause for 11 of 19 is the **dead pre-2026-09-07 314xx/3138x port band** (live band = 311xx, fronts alive — B7/V3); the GT corollary "not-listed = connected fine" is REFUTED (apify/linear/notion/codacy/codecov/mcp-graphql/meta-tool are absent because disabled, not connected — V1). (4) playwright x10 pile-up was real at 05:41 but **drained to 7 instances by 07:21** (base 3 / cdp 2 / ext 2; R2, two independent Windows APIs). (5) agents CLI **0.9.1 was already installed (05:38) before the 05:41 doctor run, and it still drops zcode/hermes** — 31 loud (not silent) warnings; harmless because sync uses custom rails, not the CLI (B5/V3).

---

## 1) Health scoreboard (80 audited servers)

| Health | Count | Meaning |
|---|---|---|
| LIVE-SESSION | 33 | Connected + tools enumerated in the live session |
| OFF-BY-DESIGN | 15 | Disabled at registry root and/or Claude deny-lists; parked deliberately |
| UNREACHABLE | 13 | Configured but could not connect (root causes below) |
| STATIC-OK | 10 | Heavy/dangerous servers verified statically only (spawn banned by mandate) |
| SPAWN-OK | 7 | Cheap stdio spawn completed MCP handshake during the audit |
| UNRESOLVED | 2 | docker (cached import broken vs current MCP SDK), linkedin (4 env vars unset at all scopes) |

Disposition classes: registry-pinned 30 · vendor-source 25 · decommission-candidate 17 · local-impl-move 8.

| # | Server | Health | Disposition | # | Server | Health | Disposition |
|---|--------|--------|-------------|---|--------|--------|-------------|
| 1 | agent-mail | LIVE-SESSION | registry-pinned | 41 | hexstrike-ai-hub | UNREACHABLE | registry-pinned |
| 2 | angr | LIVE-SESSION | registry-pinned | 42 | huggingface | LIVE-SESSION | vendor-source |
| 3 | annas-archive | LIVE-SESSION | vendor-source | 43 | ida-pro-mcp | STATIC-OK | registry-pinned |
| 4 | apify | OFF-BY-DESIGN | decommission-candidate | 44 | kaggle | OFF-BY-DESIGN | decommission-candidate |
| 5 | arxiv | LIVE-SESSION | vendor-source | 45 | libgen | OFF-BY-DESIGN | registry-pinned |
| 6 | basic-memory | LIVE-SESSION | registry-pinned | 46 | linear | OFF-BY-DESIGN | vendor-source |
| 7 | bedrock-claude | UNREACHABLE | local-impl-move | 47 | linkedin | UNRESOLVED | local-impl-move |
| 8 | binary-ninja-mcp | STATIC-OK | vendor-source | 48 | markitdown | OFF-BY-DESIGN | decommission-candidate |
| 9 | biomni-hub | LIVE-SESSION | local-impl-move | 49 | mcp-graphql | LIVE-SESSION | vendor-source |
| 10 | browserstack | SPAWN-OK | vendor-source | 50 | meta-tool | OFF-BY-DESIGN | decommission-candidate |
| 11 | burp | OFF-BY-DESIGN | decommission-candidate | 51 | mitmproxy | LIVE-SESSION | registry-pinned |
| 12 | cheatengine | STATIC-OK | registry-pinned | 52 | notion | STATIC-OK | vendor-source |
| 13 | chrome-devtools | LIVE-SESSION | vendor-source | 53 | nuclei | UNREACHABLE | registry-pinned |
| 14 | claude-code-mcp | LIVE-SESSION | vendor-source | 54 | nuclei-hub | UNREACHABLE | registry-pinned |
| 15 | cloud-audit | UNREACHABLE | local-impl-move | 55 | openaiDeveloperDocs | STATIC-OK | vendor-source |
| 16 | cloud-audit-hub | OFF-BY-DESIGN | decommission-candidate | 56 | openalex | LIVE-SESSION | registry-pinned |
| 17 | codacy | OFF-BY-DESIGN | decommission-candidate | 57 | openalex-alt | UNREACHABLE | registry-pinned |
| 18 | codecov | OFF-BY-DESIGN | decommission-candidate | 58 | osint | UNREACHABLE | registry-pinned |
| 19 | context7 | LIVE-SESSION | vendor-source | 59 | osint-hub | OFF-BY-DESIGN | decommission-candidate |
| 20 | crossref | LIVE-SESSION | vendor-source | 60 | paper-search | LIVE-SESSION | local-impl-move |
| 21 | cursor-bridge | LIVE-SESSION | registry-pinned | 61 | pdf-reader | LIVE-SESSION | vendor-source |
| 22 | cve-mcp | UNREACHABLE | registry-pinned | 62 | playwright | LIVE-SESSION | vendor-source |
| 23 | cve-mcp-hub | OFF-BY-DESIGN | registry-pinned | 63 | postgres | OFF-BY-DESIGN | registry-pinned |
| 24 | dbx-ai | LIVE-SESSION | local-impl-move | 64 | pubmed | LIVE-SESSION | vendor-source |
| 25 | deepscan | LIVE-SESSION | registry-pinned | 65 | pubmed-tool | UNREACHABLE | registry-pinned |
| 26 | deepsource | SPAWN-OK | registry-pinned | 66 | qlty | SPAWN-OK | registry-pinned |
| 27 | deepwiki | OFF-BY-DESIGN | registry-pinned | 67 | ralph-orchestrator | SPAWN-OK | registry-pinned |
| 28 | digitalocean | SPAWN-OK | decommission-candidate | 68 | repomix | SPAWN-OK | registry-pinned |
| 29 | docker | UNRESOLVED | registry-pinned | 69 | scholarly-access | LIVE-SESSION | registry-pinned |
| 30 | exa | STATIC-OK | registry-pinned | 70 | sci-hub | LIVE-SESSION | vendor-source |
| 31 | excel | LIVE-SESSION | registry-pinned | 71 | scrapegraph | LIVE-SESSION | vendor-source |
| 32 | firecrawl | SPAWN-OK | registry-pinned | 72 | semgrep | LIVE-SESSION | local-impl-move |
| 33 | frida-mcp | STATIC-OK | registry-pinned | 73 | semgrep-hub | UNREACHABLE | registry-pinned |
| 34 | ghidra-mcp | STATIC-OK | registry-pinned | 74 | sentry | STATIC-OK | vendor-source |
| 35 | github | LIVE-SESSION | vendor-source | 75 | sonarqube | STATIC-OK | vendor-source |
| 36 | github-security | UNREACHABLE | local-impl-move | 76 | tavily | LIVE-SESSION | registry-pinned |
| 37 | github-security-hub | UNREACHABLE | decommission-candidate | 77 | web-reader | LIVE-SESSION | vendor-source |
| 38 | github_cli | LIVE-SESSION | vendor-source | 78 | web-search-prime | LIVE-SESSION | vendor-source |
| 39 | glm53-space | OFF-BY-DESIGN | decommission-candidate | 79 | zai-vision | UNREACHABLE | registry-pinned |
| 40 | hexstrike-ai | LIVE-SESSION | registry-pinned | 80 | zread | LIVE-SESSION | vendor-source |

**81st server:** `video-agent-kit` (targets claude,codex,zcode; entry script verified on disk by C4) entered the registry mid-audit — pending first audit, carried in scoreboard.json as NOT-AUDITED.

**UNREACHABLE root causes (all settled by V1/V2/V3/R3):** stale 314xx port pins with live 311xx backends: github-security (31110 up), cve-mcp (31111 up), osint (31112 up), nuclei (31117 up), semgrep-hub (31119 up), cloud-audit (31118 canonical but front deliberately not started — R3 proved the logon Scheduled Task runs `-Profile Heavy` + watchdog auto-heal; down by a manual restart decision, not missing wiring). Dead hermes-only aliases (materialize nowhere Claude-side): github-security-hub, hexstrike-ai-hub, nuclei-hub, cve-mcp-hub. Missing impl: bedrock-claude (tools/mcp/bedrock-claude-mcp/ gone entirely). Dead upstream: zai-vision (npm/GitHub package `z_ai/mcp-server` does not exist — 404). Wrong packaging: pubmed-tool (no stdio mode; hardcodes http 0.0.0.0:8000 which is already owned). Stale twin: openalex-alt (superseded by openalex, which is LIVE). **Caveat (V2/V4):** "OFF" is a Claude-surface verdict — McpHub children, gemini/zcode/hermes variants keep several of these capabilities alive on surfaces waveA did not scan (codacy/codecov/digitalocean confirmed tied at 5 surfaces each — R4). **z.ai trio (R1):** web-reader / web-search-prime / zread are LIVE as transports but their shared stored credential is REJECTED as expired (credentialed initialize → code 401 "expired or incorrect" on all three endpoints; one 21-char header across all 6 config slots).

---

## 2) Scatter map (surface by surface)

| Surface | Servers | Governance | State |
|---|---|---|---|
| **SSOT registry** `~/.agents/agents.json` | **81** | source of truth, syncMode=source-only | targets: claude 68, codex 6, zcode 17, hermes 17, cursor 0; enabled=false ×6 (burp, glm53-space, kaggle, libgen, markitdown, meta-tool); mid-migration — 7 hermes twins still on dead 314xx band while firecrawl already moved to 31114 |
| **Claude** `~/.claude.json` root mcpServers | **87** | 64 governed + **23 ungoverned extras** | extras: McpHub, apktool-mcp, cloud-hub, codex, elevenlabs, fiddler, figma, figma-rest, gitlab, jadx-mcp, mcp-windbg, ocr-suite, openmm-md, perplexity, qdx-rush, rdkit, schrodinger, search-hub, searxng, social-hub, tooluniverse, zai-mcp-server (+1); root disabledMcpServers 131 entries; per-project disable marks ~36/43 projects; 5 stale 314xx URLs to re-point |
| **Codex** `~/.codex/config.toml` | **16** | 6 governed + **10 ungoverned** | ungoverned = hand-maintained security cluster: sliver, sliver-full, metasploit, hacktricks, cve, firecrawl-kit, mcphub, brightdata, node_repl, figma |
| **Cursor** `~/.cursor/mcp.json` | 7 | mirror of Claude surface (merge_generated_cursor_mcp.py) | NOT a registry target — cursor policy lives in code constants, invisible to registry tooling (B6-G3) |
| **Gemini** `~/.gemini/settings.json` | **33** | **entirely out-of-band** — zero registry targets, no merge step | 7+ drifted entries; figma+memory unregistered; github/github_cli duplicate mounts of gh-cli-mcp; linear endpoint path broken |
| **`~/.mcp.json`** (HOME project scope) | **34** | **never a sync target** (pre-SSOT legacy fleet home) | 20 SSOT-documented exact · 2 name-variants · **14 truly undocumented** (below); shadows 25 same-name user-scope entries; loaded as PROJECT scope whenever a session starts with cwd=HOME — this is the proven injection path for the 05:16 banner failures of hacktricks/metasploit/sliver/sliver-full (C5) |
| **zcode** `~/.zcode/cli/config.json` | **29** | 17 registry-wired (custom rails) + **12 ungoverned** | kaggle+burp disabled; hermes-parity security cluster ungoverned |
| **hermes** `AppData/Local/hermes/config.yaml` | 17 | registry-wired via deploy_hermes_mcp.py | 7 entries on dead 314xx band (V3 corrected B5's "6 of 17" — it is SEVEN); **RUNTIME DORMANT** — zero hermes processes on any lane (R5: process table, services, tasks, WSL, docker; logs frozen since 09-04); config re-written 4× today by sync itself |
| **goose** `~/.config/goose/config.yaml` | 37 extensions | inline, XDG SSOT | 20 streamable_http (15 enabled), **0 stdio** — G-42 hard core satisfied; 8 enabled CS-kit fronts on dead 314xx + 5 remote-cloud beyond the G-42 enumeration |
| **agy** `~/.agy` | 0 MCP | G-72/G-95 compliant (junction skills, no private mcp.json) | pointer file pins DEAD hub ports 8765/8812 (live: 18765/18812) — a compliant agy cannot reach either hub |
| **opencode** | 0 MCP | unwired | zero MCP/skills/rules share; **two literal provider credential strings** (norm = env refs); byte-identical config twin |
| **aider** | n/a | rules-share via `read:` OK | no MCP capability (CLI scan negative) — by design |
| **grok** `~/.grok/config.toml` | 22 | hand-maintained | ≥6 not in SSOT (fiddler :8868 dead, mcphub :24680 wrong route /sse→/mcp, search-hub, hacktricks-hub, firecrawl-hub, brightdata); 3 enabled-but-dead; 15 stale disabled entries; 157-line diverged AGENTS.md copy (G-96 violation); skills share empty |
| **cyberstrike** `~/.config/cyberstrike` | 12 fronts (311xx) | self-managed band | 11/12 fronts alive (cloud-audit 31118 down by decision); 6 flag-only no-type entries unverifiable statically; **fabric distillery never completes** — ~/.agents/distillery/INDEX.md absent though global CLAUDE.md consults it |

**Name variants (collision registry):** `cve` (~/.mcp.json) ≡ `cve-mcp` (SSOT, same port 31411 — duplicate key in one file); `semgrep` (SSOT stdio exe, Claude) vs `semgrep-hub` (SSOT http 31419, hermes) vs `semgrep` (~/.mcp.json http — transport conflict racing the stdio one); `github` (SSOT = GitHub Copilot HTTP) vs `github`/`github_cli` (gemini = gh-cli-mcp stdio, mounted twice); `figma` + `figma-rest` (Claude-only pair, unregistered); `playwright` (@latest, SSOT) vs `playwright-cdp`/`playwright-extension` (pinned 0.0.78, ~/.mcp.json-only — different launch modes, not variants); the `-hub` family (7 hermes twins, byte-duplicates of stale claude URLs); `McpHub` aggregator re-serving registry names as children (codacy/codecov/digitalocean/mcp-graphql/pdf-reader/scrapegraph/cve/osint/github-security/social-hub/hexstrike).

**The 14 truly undocumented `~/.mcp.json` actives** (V4 arithmetic; supersedes GT "19+"): brightdata, cloud-hub, cve (name-variant), figma, firecrawl-kit, hacktricks, metasploit, playwright-cdp, playwright-extension, schrodinger, search-hub, social-hub, sliver, sliver-full. Plus claude-only undocumented: tooluniverse (uvx-pinned, research-load-bearing), fiddler (rogue, zero provenance, app-dependent), McpHub, social-hub (both also in ~/.claude.json).

---

## 3) Consolidation plan (ordered; scholarly-access as the reference pattern)

**Reference pattern (`scholarly-access`):** one first-class server = repo dir under `agent-skills-toolchain/tools/` (source + tests, 148 green), console-script exe, single SSOT registry entry with explicit targets, materialized only by sync. Every local-impl server below converges on this shape.

- **Phase 0 — re-baseline (before any write):** regenerate registry-inventory.json / tui-inventory.json (81 registry; claude 87; codex 16 via tomllib; cursor 7 + policy note; zcode 29; hermes 17; gemini 33; opencode 0; ADD a `home-mcp` section — the 05:41 sweep never probed ~/.mcp.json, which is why GT#2 was wrong). Every count claim must carry a timestamp (86→87 and 80→81 both aged mid-audit).
- **Phase 1 — dead-entry repair (registry edits, owner-approved):** bedrock-claude delete-or-restore (impl dir gone); glm53-space impl gone (delete or rewrite); kaggle dangling Downloads venv (rebuild under stable path or leave disabled); burp repin JDK 21.0.10.7→21.0.11.10 (or PATH `java`); zai-vision rewrite as direct `npx -y <pinned>` (current `cmd /c npx @latest` points at a nonexistent package — 404); pubmed-tool retire (no stdio mode; port 8000 owned; pubmed already LIVE); libgen stays disabled (no registry package exists); docker rebuild cache (import-broken against current MCP SDK) or retire; linkedin park until env vars exist.
- **Phase 2 — registration pass (13 + cluster, one PR-shaped batch):** register cloud-hub, search-hub, social-hub (toolchain hub.py builds — register as `tools/mcp/<name>` servers with targets=[claude]), McpHub (:24680, correct route /mcp), tooluniverse (uvx, pinned, targets=[claude] — currently one curation sweep from silent loss), brightdata (env-indirected), figma + figma-rest (targets decision: B3 says [claude,gemini]), playwright-cdp/-extension (with process-ceiling note), and the security cluster metasploit/sliver/sliver-full/hacktricks/firecrawl-kit as **enabled=false on-demand** rows (targets codex+claude) so codex/zcode copies become sync-managed. Delete the `cve` alias key and the ~/.mcp.json http `semgrep` (keep exactly one semgrep definition).
- **Phase 3 — port-band re-point (314xx/3138x → 311xx), then sync, then delete ~/.mcp.json duplicates:** github-security 31410→31110 · cve-mcp 31411→31111 · osint 31412→31112 · firecrawl-kit 31414→31114 · hacktricks 31415→31115 · metasploit 31416→31116 · nuclei 31417→31117 · cloud-audit 31418→31118 · semgrep-hub 31419→31119 · sliver-full 31381→31101 · drop legacy sliver 31380. Same 5 fixes in ~/.claude.json, 8 in ~/.mcp.json. **Order matters (V2 refutation):** deleting a registry row does NOT prune materialized surfaces (merges only pop rows still present) — fix URLs in registry + sync, THEN hand-prune ~/.mcp.json / extras, then register the cluster.
- **Phase 4 — tools/ placement (local-impl-move ×8):** semgrep → rewrite SSOT command to `semgrep mcp`, retire the standalone stub exe (safe — different binary from the CLI; 10 consumer surfaces re-point via sync); dbx-ai → move impl from D:/opt/cyberstrike-mcp into repo `tools/mcp/dbx-ai/` (5 surfaces auto-heal); github-security + cloud-audit → URL fix only, impl already canonical under D:/opt/cyberstrike-mcp (github-security-mcp.cmd + node_modules verified real files); biomni-hub → re-home into tools/; paper-search → keep D:/ReverseTools venv exe but add a repo wrapper + README (mixed-drive note); bedrock-claude → restore into tools/mcp/bedrock-claude-mcp/ or delete row.
- **Phase 5 — decommission queue (owner, one-by-one, never bulk):** 15 OFF-BY-DESIGN rows. **apify first needs credential archaeology:** a literal auth header exists ONLY in ~/.claude.json (length 21) and differs from the OS-env value (length 46) — distinct credential material that deletion destroys; env-indirect it (owner supplies env name; NEVER rotate) before removing the row. codacy/codecov/digitalocean: env-referenced credentials only (R4 refuted V2's "inline literals" — the 23/19-char strings were the `${VAR}` reference names themselves), but each has a McpHub child + a divergent gemini variant that must be pruned in the same pass or the capability silently survives the decommission. Remaining: burp, cloud-audit-hub, cve-mcp-hub, osint-hub, deepwiki, glm53-space, kaggle, libgen, linear, markitdown, meta-tool, postgres, github-security-hub, nuclei-hub, openalex-alt, semgrep-hub, pubmed-tool, zai-vision (dead aliases and dead twins — safe deletions after Phase 3).
- **Phase 6 — version the load-bearing unversioned (C6):** agentmail_supervisor.ps1 (the Scheduled Task executes an UNTRACKED copy inside the third-party clone; the mingle/ duplicate has drifted 13,246B vs 16,862B) → commit live version + install_service.ps1 to repo, deploy-in; mcp_doctor.py + re-harness (the instrument behind this audit's own GT#4) → version in repo; mingle doctor/relay suite → house; monitorcore → re-vendor the one drifted file (redact.py) and refresh the repo .agents mirror (codex_monitor shim 714b vs live 730b).

---

## 4) Cross-TUI wiring plan (12 CLIs + zcode/hermes lanes)

| TUI | Max-legal wiring | Action |
|---|---|---|
| claude | sync-managed | after Phases 2-3: 23 extras → 0; re-point 5 URLs; keep root deny-lists |
| codex | sync-managed | adjudicate 10 ungoverned (cluster becomes managed via Phase 2) |
| cursor | mirror via merge script | document the code-constant policy or add a `cursor` registry target (B6-G3) |
| gemini | **new writer** | clone merge_generated_claude_mcp.py → merge_generated_gemini_mcp.py (31/33 shape-compatible immediately); recommended lightweight set: context7, notion, linear (fix /mcp path), huggingface, figma; drop heavy RE stdio + docker from the TUI; dedupe github/github_cli; delete `memory` per G-81 |
| zcode | custom rails (keep) | 17 wired; 12 ungoverned → same cluster decision as codex; guard against double-wiring if agents CLI ever adds native zcode |
| hermes | custom rails (keep) | re-point 7 dead-band rows (Phase 3); runtime dormant — owner decides revive vs park; wiring stays SSOT-correct either way (B5) |
| goose | G-42 max = basic-memory :18765 + agent-mail :18812 + builtin developer (hard core already satisfied: 0 stdio) | drop 8 dead CS-kit 314xx fronts; owner amendment for 5 remote-cloud (context7/figma/brightdata/apify/github) or drop; set GOOSE_TELEMETRY_ENABLED:false |
| agy | zero MCP (G-72/G-95) | fix pointer ports 8765→18765, 8812→18812; optional fail-closed pre-engagement hub probe; keep zero-target registry posture |
| opencode | minimal or none | convert 2 literal credentials to env refs (owner; NEVER rotate); delete twin config; add 10-line AGENTS.md pointer; wire minimal mcp block (basic-memory + agent-mail) or document MCP-free-by-choice |
| aider | none possible | nothing (rules-share already OK) |
| grok | prune + pointer | drop 3 enabled-dead (github-security-hub, hacktricks-hub, fiddler) + 15 stale disabled entries; fix mcphub route /sse→/mcp; replace 157-line AGENTS.md copy with G-96 pointer; wire skills share (currently 0/387) |
| cyberstrike | self-managed 311xx band | keep; optionally register the band in SSOT as reference rows; repair cloud-audit front (start `-Profile Heavy` once); fix 6 flag-only entries with explicit type/url |
| fabric | CLI suite | repair session distillery (fabric_session_distillery.py — hanging `claude -p`, 240s LLM_TIMEOUT insufficient; verify INDEX.md + state file with `--limit 2 --dry-run` before re-arming nightly) or drop the CLAUDE.md consult path |

**Sync-script extension outline (sync_shared_state.ps1 + merges):**
1. `merge_generated_gemini_mcp.py` (new; --live ~/.gemini/settings.json, backup-first, target-select like the claude merge).
2. `merge_generated_opencode_mcp.py` (new; schema must be verified first — curl opencode.ai/docs/mcp or `opencode` doctor; B6-G2).
3. Add a **rules/guides stage** — currently 0 handling for either (C3); run scripts/sync-rules.ps1 as the bridge and gate `common/` file-count in agents doctor.
4. Add a **~/.mcp.json retirement step**: after Phase 2/3 registration, delete superseded duplicates (canonical-promote pattern); the file should end empty or deleted.
5. Keep `integrations.enabled: []` (native agents sync would create agents__ duplicates and cannot express zcode/hermes); keep custom rails; optionally filter the 31 expected unsupported-target doctor warnings.
6. Add manifest regeneration (Phase 0) as a pre-step of every sync run so inventories stop aging mid-audit.

---

## 5) Skills / rules hygiene (C1-C8 folded in)

- **C1 — Claude distribution HEALTHY:** junction chain `.claude/skills → skills.daily → .agents/skills` intact, byte-identical 383/383 (0 hash diffs); skills.daily IS the full vault (G-94 compliant). Real drift is vault↔repo: 6 live skills never backported, 2 one-sided edits (repo ahead: ci-silent-pass-lint; vault ahead: deep-research full-allow doctrine), stale SKILLS-MANIFEST (−18 rows), 1 uncommitted repo skill. skills-claude-only/ = dead 2.5-month tree (31/36 reach no live target) → retire. CRLF phantoms confirmed non-drift (qdx-rush, skill-stocktake).
- **C2 — flagged-skills ground truth corrected:** the flagged set is 8, not 6; disk-space-manager is NOT absent (byte-identical in repo, merely untracked → one `git add`); "absent-from-repo-tree" actually means not-git-tracked. 7 real orphans to repose (~65KB/18 files; sensitive ones committable only because repo is PRIVATE-ONLY — owner HARD rule): estate-offensive-doctrine (SKILL.md only), fabric-patterns (G-58 no-upstream note), hosted-model-agents (full dir), jailbreak, opusclip-shorts (RE-COPY at commit time — edited 06:58 mid-audit), qwen-space-tool-api (tombstone-only, codex-consult precedent). `synced/` = 10.1MB vendored marketplace bucket = hook false-positive — relocate + add top-level-SKILL.md filter to the hook; do NOT commit.
- **C3 — headline rules defect:** `~/.claude/rules/common/` is EMPTY (0 of 20 repo files materialized) while three live-config hard pointers dangle into it (AGENTS-RUNTIME.md §11 windows-shell :171, §0 owner-ops :18, ~/.claude/CLAUDE.md static-analyzer :21). Root cause = sync gap: sync_shared_state.ps1 has zero rules/guides handling; sync-rules.ps1 works (dry-run verified, would copy 20) but never ran successfully. Shared language rules are content-clean (52/68 CRLF-only, 0 real drift). ~/.codex/rules = half-flattened stale merge (nested rules/rules/, 27 real-drift files, 23 missing). Guides trees forked/undocumented (2 repo-only guides never materialized).
- **C4 — registry path canonicality:** 195 tokens scanned, detectors validated. 3 dead paths (bedrock-claude, burp JDK pin, kaggle venv); 0 8.3 names in registry (but live TEMP/TMP env IS an 8.3 path); no C:/D: binary duplication (D: payloads ×3: cursor-bridge, dbx-ai, paper-search); 27 bare PATH-resolved commands (npx×19, uvx×3, docker×2...); 7 npm + 2 docker floating `@latest`/`:latest` refs; zai-vision cmd/npx double-indirection + nonexistent package (connect-failure root cause); style otherwise clean.
- **C5 — ~/.mcp.json reconciliation:** folded into §2 (34 total / 20 documented / 2 variants / 11 unregistered + rogue fiddler + bonus social-hub & McpHub; project-scope-at-HOME mechanism proven).
- **C6 — script scatter:** monitorcore = model citizen (repo-housed, controlled vendor pipeline; 1 drifted file redact.py, 1 stale mirror shim). Risk concentration on the mingle side: third-party mcp_agent_mail clone correctly pinned (HEAD 35e774f == PINNED_COMMIT.txt) but the always-on supervisor layer is untracked-with-zero-copies and its mingle duplicate has drifted; re-harness + mcp_doctor local-only with 7+ skills path-locking them → version (Phase 6).
- **C7 — memory control-plane files in unusually good shape:** 19/19 paths exist, 12/12 load-bearing vault permalinks resolve, :18765 (Basic Memory 4.0.0b1, handshake-proven) and :18812 (agent-mail, health 200 + cmdline-proven) live with verified owners; only gap: :18317 (auth2api) documented-migrated but bound by nothing (consistent with on-demand). Real debt is elsewhere: the 8812/8765 stale-port doc family (see D21).
- **C8 — live .agents structural state:** harness-at-root layout HELD (no platform/ checkout); live ~/.agents is itself a git clone on `live-capture/2026-09-02` (HEAD == remote tip today; 133 dirty files = today's uncaptured edits) — one `git pull`/`checkout main` in live would break load paths; repo .agents/ mirror 12 days stale (agents.json 52,670B vs live 62,603B); secrets hygiene clean (local.json/secrets/*.key/*.pem untracked; browser-profiles = documented owner exception); cruft: 15 vm_*.ps1, 7 agents.json.bak (one committed), mitm_mcp_traffic.db at repo root (ignored but sensitive — relocate), 5 stale toolchain dupes around ~/source.

---

## 6) Adversarial-verification results (V1-V5 + R1-R5)

**Counts (96 verifications):** CONFIRMED 81 · REFUTED 13 · NUANCED 1 · UNVERIFIED 1. Per lane: V1 51C/3R/1N, V2 4C/6R/1U, V3 7C/1R, V4 9C/2R, V5 10C/1R. Contradictions logged 22 — **all adjudicated**; gaps logged 22 (most closed by R-lanes). Reprobes R1-R5: all CONFIRMED, three with material corrections.

**Refuted items of record (13):** (V1) "fixing cloud-audit URL restores it" — front not started; "codecov never npx-cached" — time-sensitive, cache now populated; GT#3 corollary "not-listed = connected" — disabled ≠ connected. (V2) apify deletion "safe" — UNSAFE (unique literal credential, see D5); codacy decommission "safe" — unsafe-as-stated (McpHub+gemini survivors; credential axis later corrected by R4); "zcode/hermes materialize nowhere" — REFUTED, sync's custom rails write real consumer files; "registry deletion prunes surfaces" — merges only pop present rows; "SSOT edit + sync covers all consumers" — ~/.mcp.json/gemini/grok/McpHub out of scope; GT#1 "80 servers" — 81. (V3) task-text "B3/C2 dropped with receipts" — both delivered (disk + manifest). (V4) GT#2 "19+ undocumented" — 34/14; task premise B3/C2 drop — stale. (V5) `path:lineno` citation form is not an NTFS path (file itself exists).

**Major contradictions resolved:**
1. **agents CLI version** (B6 "0.8.10, upgrade to 0.9.1 will fix" vs B5 "0.9.1 already installed, still drops"): B5 wins — package.json mtime 05:38:47 predates the 05:41 doctor run; 0.9.1 has zero zcode/hermes refs. No upgrade path exists; custom rails are the mechanism.
2. **Dead 314xx band remediation** (B5 "revive supervisor, keep 314xx" vs B7 "band moved to 311xx on 07.09, re-point"): B7 wins — live fronts measured on 31110-31117/31119, all 314xx dead, registry itself mid-migration (firecrawl already at 31114). Re-point, don't revive.
3. **opusclip-shorts reposed status** (C2 "unreposed" vs C8 "captured"): both true at different levels — absent from canonical repo; captured on the live-capture branch; vault copy actively edited mid-audit. Re-copy at commit time.
4. **codacy credential loss** (V2 "inline literals lost on decommission" vs R4): R4 wins — the "literals" were `${VAR}` reference strings; real credentials live in OS env; nothing inline is lost. Decommission remains non-trivial only for surface-survivor reasons.
5. **playwright pile-up** (GT#4 x10 vs A16 x2): R2 reconciles — x10 real at 05:41, drained to 7 by 07:21 (base regrew to ceiling 3 under verifier load); enforcement = mcp_doctor ceiling, not config.
6. **cloud-audit "orphaned-off" vs "wired"**: R3 — logon Scheduled Task + watchdog both wired to start `-Profile Heavy`; down by manual restart decision after health failures.
7. **B5 "6 of 17" hermes dead-band rows**: undercount — true number SEVEN (V3 registry extraction).
8. **Detector-artifact contradictions** recorded so no lane re-derives them: reg.exe env probe (MSYS flag mangling), V3's first zcode/codex TOML probes (wrong block + quote-blind regex), V5's Resolve-Path 8.3 preservation.

**Residual UNVERIFIED (settling experiments on record):** cloud-audit 31118 serving liveness after front start (R3 closed the wiring half); MCP handshake success on live 311xx fronts (TCP/HTTP liveness only — MCP clients banned this run); hermes runtime invocation-between-probes (point-in-time table; 15-day log freeze makes it unlikely); grok server-side agent-settings surface (authenticated GET needed).

---

## 7) Owner decision list

Full list with recommendations lives in scoreboard.json `open_decisions` (D1-D25). Headline set, each with recommendation:

- **D1 baseline 81** (re-snapshot inventories first) — REC yes. **D2 port-band re-point wave** — REC approve. **D3 cloud-audit front** — REC start `-Profile Heavy` once, then decide. **D4 registration pass (13 + security cluster enabled=false)** — REC approve. **D5 decommission adjudication (15 rows, one-by-one; apify credential-preserve first; NEVER rotate)** — REC schedule. **D6 goose G-42 amendment** — REC drop dead CS-kit fronts, amend for 5 remote-cloud. **D7 gemini in-band writer** — REC yes. **D8 opencode credentials→env + twin deletion + pointer** — REC yes (owner supplies env). **D9 ~/.mcp.json register-and-retire** — REC yes. **D10 z.ai credential expired (all 3 endpoints)** — owner refreshes (agents never rotate). **D11 cursor-bridge vs G-32 lock** — owner reconciles. **D12 run sync-rules.ps1 + add rules/guides sync stage** — REC yes. **D13 repose 6 orphan skills + git add disk-space-manager** — REC yes (owner-invoked commits, G-68). **D14 version supervisor/mcp_doctor/re-harness/mingle** — REC yes, priority 1 on the C6 side. **D15 agents CLI: no action** (warnings = expected noise). **D16 retire skills-claude-only/** — REC yes. **D17 vault synced/ + .ruff_cache relocation + hook filter** — REC yes. **D18 hermes revive-vs-park** — owner call (wiring correct either way). **D19 distillery repair or drop consult path** — REC repair. **D20 guard live ~/.agents git (no checkout main/pull; capture-commit 133 dirty; refresh mirror)** — REC yes. **D21 stale-port doc family (8812→18812, 8765→18765) across 5 files** — REC yes. **D22 relocate mitm_mcp_traffic.db + debris sweep** — REC yes. **D23 playwright ceiling enforcement (3)** — REC yes. **D24 kaggle/burp repins only-if-re-enabled** — REC defer. **D25 zai-vision rewrite-or-retire (package 404)** — REC retire unless a corrected package exists.

DELIVERED: C:/Users/Prekzursil/source/agent-skills-toolchain/harness-audits/2026-09-19-mcp-tui-audit/AUDIT-SUMMARY.md
