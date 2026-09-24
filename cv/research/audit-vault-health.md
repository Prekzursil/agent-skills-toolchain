# basic-memory vault health and integrity audit — D:\basic-memory

Audited 2026-09-23 (box clock UTC; old-box timestamps in logs are +03:00). Read-only: nothing in
D:\basic-memory or ~ was modified, no daemon started, nothing installed or bound.

Label legend: **VERIFIED** = checked on disk / by command this session. **INFERRED** = derived from
verified facts or from upstream documentation fetched as untrusted data. Upstream basic-memory
source/docs were fetched from the `main` branch and docs site; the vault-era version was 0.23.2, so
behavior differences are possible where noted.

Evidence files (scratchpad): `vh-vault_scan.json` (per-note index, 713 rows), `vh-vault_scan_digest.md`,
`vh-analyze.json`, `vh-tarlist-*.txt` (five tar listings), `vh-analyze.py`, `vh-links.py`, `vh-ckpt.py`.

---

## 0. Executive summary

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | The daemon cannot come back by itself: the uv tool venv (`D:\uv\tools\basic-memory`) is gone, `~/.basic-memory` (config.json, memory.db, .bmignore, hardened launcher/watchdog, logs, backups) is gone, the `BasicMemory-HTTP-MCP` / `BasicMemory-Watchdog` tasks are not registered, and `~/.claude/settings.json` (724 B) carries no hooks, so the mcp-liveness self-heal is not even wired. Every client (Claude, Codex, Cursor) still dials `http://127.0.0.1:18765/mcp`. | critical | VERIFIED |
| 2 | 153 unflushed "Session capture" writes sit in `~/.agents/state/harness/bm-spool` (87 from 09-19, 35 from 09-20, 24 from 09-22, 2 from 09-23). The CLI replay path has failed since 2026-09-03 on the old box ("CLI not found on PATH"), and today with "uv trampoline failed to canonicalize script path". This is the silent-memory-loss class the harness exists to prevent. | high | VERIFIED |
| 3 | No vault backup job exists on this box. The only copies are `C:\suite\resume-vault.tar` (byte-complete, same C: volume as the subst-mapped D:) and, inferred, the GCS bootstrap bucket. | high | VERIFIED (job absence), INFERRED (bucket) |
| 4 | Load-bearing pointers assert things now false: `D:\basic-memory\index\WHERE.md` says daemon `:8765` and config at `~/.basic-memory/config.json`; the WHERE-map and `mcp-fleet-curation/SKILL.md` say the daemon is live / self-healing and cite files that do not exist. | high | VERIFIED |
| 5 | The "84% lack observations" headline is mostly a category error, not 600 broken notes: 152 machine dumps (should not be in ingest per contract), 156 frozen pre-contract `claude-memory/` imports, 287 pre-contract knowledge notes never retrofitted, and only 6 post-contract knowledge notes lacking observations. Post-contract knowledge notes are 91% fully compliant (92/101). | medium | VERIFIED |
| 6 | Integrity defect class: `edit_note` appends that miss their target create root-level stubs (3 occurrences: 2026-06-27, 2026-09-04, 2026-09-19); the 09-04 case destroyed a 10-event incident note (later reconstructed under a `-1` permalink, no `superseded_by` link). Two test fixtures (`main/bad note.md`, `main/Alpha decision.md`) were written into the live vault. | medium | VERIFIED |
| 7 | The surviving launcher/watchdog copies lack the 27.08 hardening the old box ran (HTTP probe, two-strike, supervisor mirror log); the toolchain copies dated 2026-09-19 still hardcode port 8765. Restoring from them regresses reliability unless re-hardened. | medium | VERIFIED |
| 8 | 14.17 GB of model caches live inside the vault: `.hf` (13,982.6 MB, general HuggingFace hub cache for Whisper/SmolVLM/etc.) and `.models` (192.2 MB, exactly basic-memory's FastEmbed embedding + reranker). basic-memory ignores hidden dirs by default, so they do not pollute the index, but they are 94% of the restore tar and sit on C: (20.4 GB free). | low | VERIFIED (contents), INFERRED (ignore rule for 0.23.2) |
| 9 | Duplication is small: 0 exact-body duplicates, 0 duplicate permalinks, 3 title groups. `main/` in permalinks is the project slug (intended); the on-disk `main/` folder (20 files) is a writer artefact. `phenibut/` vs `projects/phenibut/` is an intentional, documented twin store with zero overlap. | low | VERIFIED |

---

## 1. Why the daemon is down and what it takes to bring it back

### 1.1 Root-cause chain (all VERIFIED unless marked)

1. **Runtime state directory gone.** `Test-Path ~/.basic-memory` = False. On the old box it held
   `config.json`, `memory.db`, `.bmignore`, `bm-http-server.ps1` (canonical launcher),
   `bm-watchdog.ps1`, `logs/`, `backups/` (`sota-20260828-045938`, `*.bak_2026-08-27`) and
   `quarantine/` (per `~/.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md`, the vault note
   `harness/basic-memory SOTA implementation 2026-08-28`, and `~/.agents/scripts/bm-quarantine-oversize.ps1`).
2. **Package gone, trampoline dangling.** `~/.local/bin/basic-memory.exe` (47,104 B, 2026-08-28)
   is a uv trampoline whose embedded target is `D:\uv\tools\basic-memory\Scripts\python.exe`.
   `D:\` contains only `basic-memory` and `npm-cache`; `D:\uv` does not exist. `uv tool dir` on
   this box is `%APPDATA%\uv\tools` (only `.gitignore`/`.lock`); `uv tool list` prints "No tools
   installed"; `pipx.exe` fails the same way. No `basic_memory` package directory exists under
   `~/.venvs`, `~/.local`, `%LOCALAPPDATA%\uv`, `%APPDATA%\uv`, `C:\Python314`, `D:\opt`.
   The bm-spool `flush-errors.log` records the exact error at 2026-09-23T12:22:52Z:
   `CLI exit 1: error: uv trampoline failed to canonicalize script path`.
3. **Supervision not registered.** Non-Microsoft scheduled tasks on this box: `GCEStartup`,
   `MapDriveD`, Edge/Google updaters. No `BasicMemory-HTTP-MCP`, `BasicMemory-Watchdog`,
   `BasicMemory-Vault-Backup`. Nothing listens on 18765; no process matches `basic-memory`.
4. **Self-heal hooks not wired.** `~/.claude/settings.json` is 724 B (keys: permissions, model,
   sandbox, tui, ...) with **no `hooks` key**. The golden `C:\suite\settings.json` (25,912 B,
   repaired 15:12Z per `mirror.log`) carries 20 hook events including the harness dispatcher,
   mcp-liveness, memory-spool. Something rewrote `~/.claude/settings.json` at 16:47Z. Consequence:
   `liveness.py` -> `restart-basic-memory.ps1` never runs, and even if it did it would find no
   task and no launcher at `C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1`.
5. **Clients still dial the SSOT URL.** `~/.claude.json` line 7087, `~/.codex/config.toml` line
   1089, `~/.cursor/mcp.json` line 12 all say `http://127.0.0.1:18765/mcp` -> ECONNREFUSED.
6. **Per-process env not present.** None of `HF_HOME`, `FASTEMBED_CACHE_PATH`, `BASIC_MEMORY_*`,
   `UV_TOOL_DIR` are set at User/Machine/Process scope. The launcher sets
   `BASIC_MEMORY_HOME=D:\basic-memory` and `FASTEMBED_CACHE_PATH=D:\basic-memory\.models` per
   process; `HF_HOME` was a User env var on the old box (launcher comment; vault note
   `claude-memory/Documents-GitHub/reference_claude-memory-extension.md`).
7. **D: is not a disk.** Task `MapDriveD` runs `subst D: C:\drive-d`; `D:\basic-memory` is
   physically `C:\drive-d\basic-memory`. C: has 20.4 GB free.

### 1.2 How it was previously launched (VERIFIED from surviving artefacts)

- Logon task `BasicMemory-HTTP-MCP` (logon + every 5 min, IgnoreNew, restart-on-failure) ->
  `pwsh -File C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1` -> runs
  `C:\Users\Prekzursil\.local\bin\basic-memory.exe mcp --transport streamable-http --host 127.0.0.1 --port 18765 --path /mcp`
  with `BASIC_MEMORY_HOME=D:\basic-memory`, `FASTEMBED_CACHE_PATH=D:\basic-memory\.models`, `DO_NOT_TRACK=1`
  (copy: `~/.agents/scripts/agentic-perfection/bm-http-server.ps1`, 2026-09-04).
- Task `BasicMemory-Watchdog` (every 3 min + logon) -> `bm-watchdog.ps1` (probe, force-recover).
- Three restarters existed: task, watchdog, and the `mcp-liveness` hook's `restart-basic-memory.ps1`.
- Old-box liveness evidence: `~/.agents/logs/basic-memory-supervisor.log` (647 lines,
  2026-08-27 -> 2026-09-23T12:54+03:00 = 09:54Z): 162 launcher starts, 143 force-recovers, 9 starts
  on 2026-09-23 alone; chronic pattern `:18765 bound but HTTP unresponsive - strike 1/2 -> force-recover`
  (RAM pressure). The daemon was alive-but-thrashing right up to the snapshot; it has never run here.
- `.sync.log` in the vault root (2026-06-10) shows the pre-contract `stdio` era (FastMCP 3.3.1).
- Version: vault notes state CLI 0.22.1 (2026-07-17, 2026-08-28) and "Package is 0.23.2"
  (`harness/basic-memory SOTA implementation 2026-08-28`, valid_as_of 2026-08-28). Last known
  installed = **0.23.2** (VERIFIED as a note claim; INFERRED as the actual installed version).

### 1.3 What basic-memory needs to re-initialize (upstream source/docs, treated as data)

- Config dir resolution: `BASIC_MEMORY_CONFIG_DIR` > `$XDG_CONFIG_HOME/basic-memory` >
  `~/.basic-memory`; files `config.json` and `memory.db` (`config_models.py`).
- `config.json` is **auto-created on first load** if missing (`config.py`:
  `config = BasicMemoryConfig(); self.save_config(config)`). If no projects exist, a default project
  `main` is created at `BASIC_MEMORY_HOME` if set, else `~/basic-memory`. Running any
  `basic-memory` command before setting env/project would therefore create a wrong, empty default
  project at `C:\Users\prekzursil\basic-memory`. INFERRED risk; avoid by setting env first.
- `permalinks_include_project` defaults to **true** ("Include project slug in permalinks"). This is
  why all 713 permalinks begin with `main/` (see section 4). Re-index with project name `main`
  keeps stored and computed permalinks consistent.
- Default ignore patterns include `.*` (hidden), `*.db`, `config.json`; `.bmignore` is global in
  the data dir and honors `BASIC_MEMORY_CONFIG_DIR` (`ignore_utils.py`, main branch). So `.hf`,
  `.models`, `.sync.log` are skipped by default. INFERRED for 0.23.2.
- Rebuild: `bm reset --reindex` "Drops all tables and recreates them. Files are never deleted."
  and "refuses to run while an MCP server is attached" (cli-reference). `basic-memory sync` and
  `basic-memory status --wait` exist. Sync can add frontmatter only under
  `BASIC_MEMORY_ENSURE_FRONTMATTER_ON_SYNC`; file-writing flags (`kebab_filenames`,
  `format_on_save`, `update_permalinks_on_move`) default off/false.
- Is re-indexing destructive to the 713 notes? **No** (INFERRED from the above): the SQLite index
  is derived from the markdown; the only write-back paths are opt-in flags, and every note already
  has frontmatter + permalink (713/713, 0 duplicate permalinks), so even those paths would be no-ops.
- Is anything permanently lost with the SQLite index? The index itself: no (re-scan + re-embed).
  Lost and only reconstructable: `config.json` settings (decisions recorded in
  `harness/basic-memory SOTA implementation 2026-08-28`: semantic ON, hybrid default, FastEmbed
  local, reranker ON `jinaai/jina-reranker-v1-tiny-en`, cache `D:\basic-memory\.models`),
  custom `.bmignore` content (unknown), daemon logs, script backups, and `quarantine/` (0 notes
  carry `status: quarantined`, so most likely nothing was ever quarantined - INFERRED).
- Cost: embedding 713 notes (2.2 MB) with bge-small ONNX on CPU is minutes, not hours (INFERRED;
  models are already cached in `.models`, so no download if `FASTEMBED_CACHE_PATH` points there).

### 1.4 Proposed recovery procedure (for the owner; nothing here was executed)

Pre-flight: C: free >= 5 GB (20.4 GB now); confirm 18765 idle (`Get-NetTCPConnection -LocalPort 18765`).

1. Install the package (regenerates the `~/.local/bin` trampolines; `~/.local` is a junction into
   `C:\suite\payload\Users\Prekzursil\.local`):
   `uv tool install basic-memory==0.23.2` (pin to the vault-era version; the README's
   `--prerelease=allow` form fetches the newest). Optionally `$env:UV_TOOL_DIR='D:\uv\tools'` first
   to reproduce the old layout (D: is a subst of C:, so it buys nothing except path parity).
   Verify: `basic-memory --version` (do NOT run other subcommands yet).
2. Create the config and project before any sync:
   `$env:BASIC_MEMORY_HOME='D:\basic-memory'`; `basic-memory project add main D:\basic-memory --default`.
   Then check `~/.basic-memory/config.json`: project `main` -> `D:\basic-memory`,
   `semantic_search_enabled: true`, `reranker_enabled: true`,
   `reranker_model: jinaai/jina-reranker-v1-tiny-en`, `semantic_embedding_model: bge-small-en-v1.5`,
   `permalinks_include_project: true`, `update_permalinks_on_move: false`, `kebab_filenames: false`,
   `format_on_save: false`, ensure-frontmatter-on-sync off.
3. Write `~/.basic-memory/.bmignore` (explicit, do not rely on defaults): `.hf/`, `.models/`,
   `.sync.log`. Owner decision: also `compaction-checkpoints/` and `sessions/` (contract says
   dumps stay out of ingest; the cleaner fix is to point the writers outside the vault, section 2.4).
4. Index once, headless: `$env:FASTEMBED_CACHE_PATH='D:\basic-memory\.models'`;
   `basic-memory sync` (or `bm reset --reindex` if a stale `memory.db` exists); then
   `basic-memory status --wait --timeout 600`. Expect 713 entities, 0 permalink conflicts.
5. Restore the launcher and watchdog to `C:\Users\Prekzursil\.basic-memory\` from
   `~/.agents/scripts/agentic-perfection/` (port 18765 versions). Re-apply the 27.08 hardening
   from `~/.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md` (HTTP GET probe with 30 s timeout,
   two-strike rule via `%TEMP%\bm-http-degraded.strike`, mirror to
   `~/.agents/logs/basic-memory-supervisor.log`) - the surviving copies have none of it.
6. Register tasks: `BasicMemory-HTTP-MCP` (logon + 5-min repetition, IgnoreNew, restart on
   failure) -> `pwsh -NoProfile -File C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1`;
   `BasicMemory-Watchdog` (logon + 3-min) -> `bm-watchdog.ps1`. Then `Start-ScheduledTask BasicMemory-HTTP-MCP`.
7. Verify: `Invoke-WebRequest http://127.0.0.1:18765/mcp -Method GET` -> HTTP 406 = serving;
   POST `~/.agents/scripts/bm-init-probe.json` with `Accept: application/json, text/event-stream`
   -> 200 SSE with `serverInfo`; then one `search_notes` through MCP from a fresh Claude session.
8. Restore hooks: merge the `hooks` block from `C:\suite\settings.json` (sha8 D14F1D46) into
   `~/.claude/settings.json`; that re-enables mcp-liveness, memory-spool, recall-inject and the
   dispatcher (find what rewrote it at 16:47Z first, or it will happen again).
9. Drain the spool: at the next SessionStart the harness (`~/.agents/harness/modules.py` ~L2425)
   replays `~/.agents/state/harness/bm-spool/*.json` via
   `basic-memory tool write-note --folder sessions --overwrite --local` (default
   `HARNESS_BM_SPOOL_FOLDER=sessions`). 153 entries -> 153 new `sessions/` notes. Decide first
   whether those machine captures belong in the vault at all (section 2).
10. Optional but restores the media tools' offline model loads: User env `HF_HOME=D:\basic-memory\.hf`.
11. Fix the stale pointers listed in section 5 (index/WHERE.md, WHERE-map, mcp-fleet SKILL).
12. Re-create a vault backup job (`BasicMemory-Vault-Backup` existed on the old box; its script
    and destination are not on disk anywhere).

Do not: run `uvx basic-memory` stdio (contract), run `bm reset` while the daemon is attached,
start the daemon before step 2 (auto-config would point `main` at `~\basic-memory`).

---

## 2. Contract compliance in detail (713 notes)

Measured with `vh-vault_scan.py` (frontmatter parsed; strict observation = a line matching
`- [decision]` or `- [fact]`; any-category = `- [word]`; wikilink = `[[...]]`).
Contract date = 2026-08-28 (memory-contract.md "Lane Q2 / 2026-08-28").

### 2.1 Headline decomposition (VERIFIED)

| Set | n | no `[decision]/[fact]` | no wikilinks | neither | fully compliant | has `valid_as_of` |
|---|---|---|---|---|---|---|
| All notes | 713 | 599 (84%) | 397 (56%) | 392 | 114 | 57 |
| Machine dumps | 152 | 150 | 141 | 140 | 1 | 1 |
| Legacy import `claude-memory/` | 156 | 156 | 100 | 100 | 0 | 0 |
| Knowledge notes | 405 | 293 | 156 | 152 | 108 | 56 |
| Knowledge, pre-contract (mtime < 08-28) | 304 | 287 | 148 | 147 | 16 | 11 |
| Knowledge, post-contract | 101 | 6 | 8 | 5 | 92 (91%) | 45 |

The five post-contract knowledge notes with neither: `agents/Launch Goose with another agent.md`,
`agents/MistyBay helper protocol.md`, `index/WHERE.md` (tiny pointer by design),
`probes/offloop-semantic-probe-2026-08-28.md`, `research/research basic-memory-sota 2026-08-28.md`.

### 2.2 Folder concentration of strict-observation violations (VERIFIED)

| folder | notes | no obs | no links | neither | machine | KB | mtime range |
|---|---|---|---|---|---|---|---|
| projects | 180 | 150 | 75 | 74 | 4 | 690.9 | 06-11..09-22 |
| claude-memory | 157 | 157 | 101 | 101 | 1 | 675.5 | 06-10..07-19 |
| compaction-checkpoints | 102 | 101 | 101 | 100 | 102 | 140.3 | 07-24..09-23 |
| research | 38 | 18 | 12 | 11 | 0 | 130.4 | 06-12..09-22 |
| reference | 35 | 27 | 4 | 4 | 0 | 106.7 | 06-30..09-17 |
| sessions | 35 | 35 | 34 | 34 | 35 | 20.9 | 08-07..09-23 |
| phenibut | 33 | 28 | 27 | 26 | 0 | 120.4 | 06-22..09-16 |
| harness | 26 | 19 | 5 | 5 | 0 | 64.6 | 06-21..09-04 |
| main | 20 | 15 | 7 | 7 | 0 | 71.3 | 06-20..09-22 |
| decisions | 17 | 7 | 1 | 1 | 0 | 62.4 | 06-15..09-19 |
| tools | 17 | 0 | 0 | 0 | 0 | 26.6 | 09-02..09-19 |
| notes | 8 | 5 | 5 | 5 | 0 | 14.7 | 06-21..09-20 |
| ast-integrate | 7 | 6 | 6 | 6 | 0 | 13.6 | 08-16..08-17 |
| checkpoints | 6 | 6 | 1 | 1 | 6 | 23.3 | 06-10..06-20 |
| codex-checkpoints / codex-thread-checkpoints | 3 / 1 | 2 / 1 | 2 / 1 | 2 / 1 | 4 | 28.5 | 09-02..09-03 |
| agents, feedback, root, battlecats, bolt, index, reframe, techniques, auth, f, infra, models, ops, owner-ops, p2-wave, probes, re, references | 1-3 each | see digest | | | | | |

Three folders account for 442 of the 599 violations: `projects` (150), `claude-memory` (157),
`compaction-checkpoints` (101) + `sessions` (35).

### 2.3 Machine-generated vs genuine (VERIFIED)

- **Machine dumps: 152 notes (21%)**, 230 KB. `compaction-checkpoints/` 102 (frontmatter
  `type: sanitized-compaction-checkpoint`, written directly by `~/.agents/harness/modules.py`
  `SanitizedCheckpointModule`, default target `D:/basic-memory/compaction-checkpoints`, env
  `BASIC_MEMORY_CHECKPOINT_DIR`); `sessions/` 35 ("Session capture" notes replayed by the harness
  spool via `basic-memory tool write-note --folder sessions`); `checkpoints/` 6 (June-era
  writer); `codex-checkpoints/` 3 + `codex-thread-checkpoints/` 1; 4 checkpoint-titled notes in
  `projects/`; 1 in `claude-memory/`. Information content: 78 of 102 compaction checkpoints have
  both `## Decisions - none` and `## Unresolved failures - none` (median 979 B); 0 of 35 session
  captures carry a `[decision]`/`[fact]` line. The harness's own readers exclude
  `compaction-checkpoints` (`recall_index.py` `_EXCLUDED_DIRS`, `modules.py`
  `_DIGEST_EXCLUDED_PARTS`, `bm-session-recall.ps1`), and `checkpoint_state.py` documents this as
  "a live WRITER and zero READERS". The contract ("Keep transcripts / compaction dumps out of
  ingest") is violated structurally by the writer's default target, not by 152 individual notes.
- **Legacy import: 156 notes (22%)** in `claude-memory/<project>/` = mirrors of Claude Code
  auto-memory (`MEMORY.md` x11 plus their linked files), mtimes 2026-06-10..07-19, no observation
  syntax at all. Frozen: the live `~/.claude/projects/C--Users-prekzursil/memory/MEMORY.md` is
  93 lines (2026-09-22) vs the vault copy's 53 lines; 93 live lines are absent from the vault copy.
  No control-plane script referencing this folder was found (writer retired or one-shot).
- **Genuine knowledge notes: 405 (57%)**, of which 304 predate the contract. Post-contract
  authoring discipline is good (91% fully compliant), so the fix is retrofitting / grandfathering,
  not a broken writing practice.

Verdict on the task's framing: it is a category error for 152 + 156 = 308 notes (43%), a
retrofit backlog for 287 pre-contract knowledge notes, and a real-but-small drift of 6-9
post-contract notes.

### 2.4 Other contract checks

- Size cap: 0 notes > 100 KB; largest `projects/Fleet triage plan 2026-07-25 (wf_081e0b4a-3bc).md` at 41.5 KB. VERIFIED.
- Frontmatter/permalink: 713/713. `status`: 667 blank, 44 `active`, 1 `superseded`, 1 `REFUTED`. VERIFIED.
- `valid_as_of`: 57 notes in frontmatter (8%), typed inconsistently: 43 quoted strings
  (`'2026-09-02'`) vs 14 bare dates. The task brief's 12% likely counted body mentions. VERIFIED (definition noted).
- `superseded_by`: 1 note in frontmatter (`harness/Basic Memory Cursor bridge NDJSON repair 2026-09-01` ->
  `resilient repair 2026-09-02`); 6 files mention the key anywhere. The brief's "2" is a definition difference.
- Wikilink health (knowledge notes only, code fences/inline code stripped): 222 resolved vs 260
  unresolved targets (54% dangling; 188 distinct). Top dangling: `auth2api` (11),
  `single-signal-verification` (6), `WHERE-map pointer` (5), `project_reframe_v1_4_1_shipped_2026-07-09` (5),
  `memory-contract` (3). Many targets are auto-memory basenames or concept slugs that were never
  created as notes, so the relation graph is half-dangling (recall via relations degraded - INFERRED).
- Writer-side fixes (owner decisions): point `BASIC_MEMORY_CHECKPOINT_DIR` and the spool folder
  outside the vault (or into an ignored subtree); retire or refresh `claude-memory/`; add the two
  missing `superseded_by` links (incident note pair; burp pair).

---

## 3. The 14.17 GB of caches inside the vault (VERIFIED)

| Path | Files | Size | What it is |
|---|---|---|---|
| `.hf` | 143 | 13,982.62 MB | HuggingFace hub cache (`HF_HOME`), general-purpose |
| `.hf/hub/models--HuggingFaceTB--SmolVLM2-2.2B-Instruct` | 33 | 8,575.6 MB | vision-language model (OCR/vision tools) |
| `.hf/hub/models--Systran--faster-whisper-large-v3` | 11 | 2,947.7 MB | ASR |
| `.hf/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo` | 12 | 1,546.5 MB | ASR (opusclip-shorts, video-agent-kit receipts) |
| `.hf/hub/models--distilbert-base-multilingual-cased` | 15 | 519.5 MB | |
| `.hf/hub/models--cross-encoder--nli-distilroberta-base` | 18 | 317.9 MB | |
| `.hf/hub/models--Systran--faster-whisper-tiny` | 10 | 74.6 MB | |
| `.hf/hub/models--Alibaba-NLP--Tongyi-DeepResearch-30B-A3B` (+AWQ) | 6+5 | 0.0 MB | metadata/`.no_exist` only, no weights |
| `.hf/hub/spaces--prekzursil--space`, `datasets--futurehouse--lab-bench`, `.hf/xet` | | ~0 | |
| `.models` | 26 | 192.23 MB | FastEmbed cache (`FASTEMBED_CACHE_PATH`) |
| `.models/models--qdrant--bge-small-en-v1.5-onnx-q` | 12 | 64.1 MB | basic-memory default embedding model |
| `.models/models--jinaai--jina-reranker-v1-tiny-en` | 13 | 128.2 MB | basic-memory reranker (ON per 2026-08-28 decision) |

- `.models` **is** basic-memory's own model cache: the launcher sets
  `FASTEMBED_CACHE_PATH='D:\basic-memory\.models'` and its comment says "basic-memory itself uses
  FASTEMBED_CACHE_PATH (.models), not HF_HOME". `.hf` is **not**: the recorded decision in
  `~/.agents/skills/mcp-fleet-curation/SKILL.md` says it is "the GLOBAL HF cache for media/OCR
  tools, NOT basic-memory's model - do not delete", and receipts (`video-agent-kit/receipts/asr-e2e_2026-09-19.md`,
  `opusclip-shorts/SKILL.md`) rely on `HF_HOME=D:\basic-memory\.hf` for offline loads.
- References from inside the vault: none that depend on them. Three notes mention `.models` as
  configuration documentation. The harness excludes both dirs from its recall index/digest; the
  old `~/.claude/hooks/recall-inject/index/recall_index.json` (2026-07-10) still contains 2 entries
  under `.hf` (a model-card README was indexed before exclusions existed) - historical pollution only.
- basic-memory itself: default ignore `.*` skips hidden directories (upstream `ignore_utils.py`;
  INFERRED for 0.23.2), and no `.bmignore` survives to prove what the old config did.
- `HF_HOME` is unset on this box at every scope, so today nothing references `.hf` at all.
- What moving them out would break: `.models` -> nothing, provided the launcher's
  `FASTEMBED_CACHE_PATH` follows it (otherwise a ~190 MB re-download on first search, which needs
  network and a working HF endpoint). `.hf` -> nothing in basic-memory; the ASR/vision tools would
  re-download up to 14 GB unless `HF_HOME` is set to the new location (it must be set anyway now).
- Cost of leaving them: the restore tar is 94% caches (13.98 GB of 14.87 GB); every backup/restore
  of "the vault" moves 14 GB to protect 2.2 MB of notes; and since D: is `subst`-mapped to
  `C:\drive-d`, the 14 GB sits on C: with 20.4 GB free.

---

## 4. Duplication and drift (VERIFIED)

- **`main/` is two different things.** (a) In permalinks: all 713/713 permalinks start with
  `main/` because `permalinks_include_project` defaults to true and the project is named `main`
  (e.g. `index/WHERE.md` -> `permalink: main/index/where`). Intended. (b) On disk: a physical
  `main/` folder with 20 files (2026-06-20..2026-09-22) mirroring ten top-level folder names
  (claude-memory, compaction-checkpoints, decisions, feedback, harness, phenibut, projects,
  reference, research, techniques). These were created when a writer passed the project-prefixed
  path (`main/<folder>`) as the folder argument. Contents: two **test fixtures written into the
  live vault** (`main/bad note.md`, 72 B, body "body2", 2026-07-27; `main/Alpha decision.md`,
  83 B, body "body", 2026-07-29); one truncated remnant
  (`main/decisions/incident-agents-md-policy-inversion-forensic-attribution-2026-09-03.md`,
  1,193 B) whose full reconstruction lives at
  `decisions/incident agents-md policy inversion forensic attribution 2026-09-03.md` (8,923 B,
  permalink suffixed `-1` by basic-memory's collision handling) with no `superseded_by` link; and
  17 unique notes with no twin by title or hash - misplaced, not duplicated. Not a duplicate
  namespace; a namespace-confusion artefact.
- **Exact duplicates: 0** (normalized body hash). **Duplicate permalinks: 0.** Title groups: 3
  (`MEMORY` x11 legitimate per-project files; the burp pair; the incident pair).
- **Root-level stubs = an `edit_note` defect class.**
  `burp-mcp-always-on-hardening-mcp-health-fixes-2026-09-19.md` (root, 886 B, 14:40Z) vs
  `decisions/Burp MCP always-on hardening + MCP health fixes (2026-09-19).md` (2,996 B, 15:27Z);
  `hitman-3-challenge-completion-re-zhmmod-sdk-quintuple-trouble.md` (root, 2026-06-27) vs
  `projects/hitman-re/HITMAN 3 challenge-completion RE (...).md` (13.8 KB). Pattern: an append by
  slug that did not resolve created a new root note titled with the slug. The incident note itself
  records the destructive variant ("a faulty edit_note append ... returned fileCreated ... replaced
  this note with only the new lines"). Three occurrences; one lost content (later reconstructed).
- **`phenibut/` (33) vs `projects/phenibut/` (30):** 0 overlapping titles, 0 hash overlaps. The
  WHERE-map documents it as a twin store ("current Paper A/B" vs "compute/FEP history"). Intentional split.
- **`reference/` (35) vs `references/` (1, 2026-09-22):** stray plural namespace, no overlap.
- **`notes/` (8) vs root (2):** root holds only the two stubs above; `notes/` is a legitimate
  folder (`estate-locks-2026-08-27` etc.).
- **Checkpoint namespaces drifted three times:** `checkpoints/` (June), `compaction-checkpoints/`
  (July->now), `codex-checkpoints/` + `codex-thread-checkpoints/` (Sept).
- **`claude-memory/`** is a frozen June/July mirror of Claude auto-memory (see 2.3).
- Launcher/watchdog source drift: `~/.agents/scripts/agentic-perfection/*` (2026-09-04) use port
  18765 but have 0 occurrences of `strike`, `basic-memory-supervisor.log`, or an HTTP probe;
  `~/source/agent-skills-toolchain/scripts/agentic-perfection/*` (2026-09-19) still say `$Port = 8765`.
  The canonical hardened versions lived in `~/.basic-memory` and are gone.

---

## 5. Staleness (VERIFIED unless marked)

- Only 57 notes carry `valid_as_of` in frontmatter; 1 carries `superseded_by`. 32 lines in 18
  notes cite `8765` as the current port (migrated to 18765 on 2026-09-04 per the WHERE-map and
  `harness/Rail port migrate Hyper-V exclusion SOTA 2026-09-04`).
- Assertions this session proved false, most important first:
  1. `D:\basic-memory\index\WHERE.md` (vault pointer, valid_as_of 2026-08-28, mtime 09-07):
     "Daemon: 127.0.0.1:8765" and "Config: C:\Users\Prekzursil\.basic-memory\config.json". Both false.
  2. `~/.agents/memory-map.md` (WHERE-map): "BM runtime config C:\Users\Prekzursil\.basic-memory\config.json",
     "BM SQLite ...\memory.db" (absent), "MCP :18765 is live semantic store" (down), "watchdog owns
     liveness" (no watchdog task), audit/receipt paths under `C:\Users\Prekzursil\Cowork\output\`
     (`~/Cowork` does not exist on this box).
  3. `~/.agents/skills/mcp-fleet-curation/SKILL.md` lines 82-86: "runs as a shared HTTP server on
     :8765", "run pwsh -File ~/.basic-memory/bm-http-server.ps1" (file absent), "a 5-min scheduled
     task also self-heals it" (not registered).
  4. `reference/harness/basic-memory self-heal loop VERIFIED end-to-end (2026-07-06).md`:
     "daemon live now (pid on :8765)", task `BasicMemory-HTTP-MCP` state=Ready, launcher fallback
     `~/.basic-memory/bm-http-server.ps1`. No valid_as_of.
  5. `reference/MCP config drift- basic-memory + codex absent, re-add.md` (2026-07-17):
     "`~/.basic-memory/config.json` default_project main -> D:\basic-memory; basic-memory 0.22.1 at
     ~/.local/bin". Config absent; exe is a dangling trampoline.
  6. `ast-integrate/p2-wave/AUD-0066 CLOUD-OK refute STILL-OPEN.md` (2026-08-17): "Running:
     MCPAgentMailSupervisor, BasicMemory-HTTP-MCP, BasicMemory-Watchdog ... Listeners 8812=1 8765=1".
  7. `research/gem-hunt 2026-08-27.md`: "health probe is GET http://127.0.0.1:8765/mcp -> 406 = HEALTHY".
  8. `harness/basic-memory SOTA implementation 2026-08-28.md` (valid_as_of set): backup path
     `~/.basic-memory/backups/sota-20260828-045938` and receipt under `Cowork/output/` - both absent.
  9. `notes/estate-locks-2026-08-27.md` (load-bearing #1), `harness/Grill IDs G-32 G-36...` (x3),
     `harness/Reconciliation wave dispatch 2026-09-02`, `harness/Basic-memory SOTA session contract`,
     `research/research basic-memory-sota 2026-08-28`, `research/research leftover gems 2026-08-27` (x5),
     `tools/CyberStrike MCP HTTP fronts and Bolt 2026-09-03`, `ops/mcp/basic-memory -8765 restart-thrash...` (x10):
     all cite 8765 as current without a supersede marker.
- Not stale (probe false positives): the 2026-09-20..23 compaction checkpoints' "daemon healthy"
  lines refer to Claude Science, not basic-memory. `memory.db` is mentioned by 0 vault notes.
- WHERE-map load-bearing list: all 11 named notes exist on disk (checked by title in `harness/`,
  `notes/`, `phenibut/`, `techniques/`), but 2 of the listed `techniques/` titles are not in
  `techniques/`: `techniques/` holds only `Cross-rail byte-parity porting...` and `Three verification
  traps...`; "Green gates found zero of eleven defects" is not a file there (INFERRED: it may live
  under another folder or was never written).

---

## 6. Recoverability (VERIFIED unless marked)

- **If D:\basic-memory were lost right now, nothing would be gone.** `C:\suite\resume-vault.tar`
  (14,866,448,384 B, 2026-09-23 12:09:25Z) lists 883 entries = 713 notes + `.sync.log` + 143 `.hf`
  + 26 `.models`, i.e. exactly the on-disk vault; no vault file has a mtime after the 12:11:04Z
  extraction; the newest note is `compaction-checkpoints/checkpoint-20260923-035327-...` (03:53Z).
  Restore: `C:\Windows\System32\tar.exe -xf C:\suite\resume-vault.tar -C D:\basic-memory`
  (mtimes preserved). Gotcha: the Git-Bash GNU tar 1.35 first on PATH fails on `C:\...` with
  "Cannot connect to C: resolve failed" (treats the drive letter as a host); use bsdtar or `--force-local`.
- **Off-box copy:** the GCE startup script fetches bootstrap objects from
  `storage.googleapis.com/webcoder-462916-offload/` (settings.json, jq.exe - VERIFIED); the
  `import-resume.log` only records "downloaded resume-vault.tar", and the importing script is not
  on disk, so the tar's origin being that bucket is INFERRED. Bucket retention is unknown.
- **Same-volume risk:** all tars in `C:\suite` and the subst-mapped `D:` are on the one C: volume.
- **What no archive contains** (searched resume-settings, resume-claude, resume-vault, claude-rest
  (484,955 entries), suite (512,141 entries): 0 entries under `.basic-memory` or `uv/tools`):
  `config.json`, `memory.db`, `.bmignore`, the hardened launcher/watchdog, daemon/liveness logs,
  `backups/`, `quarantine/`. Only `quarantine/` could hold note bodies; 0 vault notes carry
  `status: quarantined`, so nothing was ever moved out (INFERRED, cannot be proven without the manifest).
- **Knowledge that is not in the vault at all:**
  - 153 unflushed Session-capture spool entries in `~/.agents/state/harness/bm-spool` (159 JSON,
    137 KB; 6 flushed). `flush-errors.log` (586 lines) shows the CLI replay failing since
    2026-09-03 ("CLI exit 3: no output", "CLI not found on PATH") - i.e. for 20 days before the
    restore, not only today. suite.tar carries the spool (161 entries), so it is backed up but unapplied.
  - Live Claude auto-memory (`~/.claude/projects/C--Users-prekzursil/memory/MEMORY.md`, 93 lines,
    2026-09-22): 93 lines absent from the vault's `claude-memory/root/MEMORY.md`. In resume-claude.tar.
  - Derived indexes (`~/.agents/state/harness/recall-digest.json` 09:47Z, `recall-index.json`
    1.99 MB 09:43Z, `bm-graph-neighbors.json` 08-28) are stale old-box artefacts; rebuildable.
- **Going forward:** no backup job exists on this box (`BasicMemory-Vault-Backup` absent; no
  script found under `~/.agents`, `~/.local/bin`, `D:\opt`, `~/.claude`). Once the daemon returns,
  new writes are unprotected until a job is re-created.

---

## Appendix A - measurements this audit accepted from the brief without recomputing

714 note files / 2.20 MB; 169 cache files / 14,174.85 MB; 100% frontmatter and permalink; mtime
clusters 277/121/90/225 (my scan reproduced the month histogram exactly: 2026-06: 277, 07: 121,
08: 90, 09: 225). Where my definitions differ from the brief (valid_as_of 8% in frontmatter vs 12%;
superseded_by 1 in frontmatter vs 2), both numbers are reported with the definition.

## Appendix B - commands/files behind the key claims

- `Test-Path ~/.basic-memory` -> False; `Get-ScheduledTask` filtered; `Get-NetTCPConnection -LocalPort 18765` -> none.
- Trampoline target: ASCII scan of `~/.local/bin/basic-memory.exe` -> `D:\uv\tools\basic-memory\Scripts\python.exe`; `Test-Path` -> False.
- `uv tool dir` -> `C:\Users\prekzursil\AppData\Roaming\uv\tools` (empty); `uv tool list` -> "No tools installed".
- Launch chain: `~/.agents/scripts/agentic-perfection/bm-http-server.ps1`, `bm-watchdog.ps1`,
  `~/.claude/hooks/mcp-liveness/{liveness.py,restart-basic-memory.ps1}`, `~/.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md`,
  `~/.agents/logs/basic-memory-supervisor.log`.
- Client config: `~/.claude.json` L7087, `~/.codex/config.toml` L1089, `~/.cursor/mcp.json` L12.
- Hooks: `~/.claude/settings.json` (724 B, no `hooks`); golden `C:\suite\settings.json` (25,912 B, 20 hook events).
- Spool: `~/.agents/state/harness/bm-spool/*.json` (flushed flag counted), `flush-errors.log`; replay code `~/.agents/harness/modules.py` L513, L566, L2425.
- Caches: `Get-ChildItem -Recurse | Measure-Object` per model dir; env scan of HF_HOME/FASTEMBED_CACHE_PATH/BASIC_MEMORY_*/UV_* at User/Machine/Process.
- Tars: bsdtar 3.8.4 listings saved as `vh-tarlist-*.txt`; GCE metadata `windows-startup-script-ps1` (secrets masked).
- Upstream (data only): `config.py`, `config_models.py`, `ignore_utils.py` (main), `docs.basicmemory.com/raw/reference/{configuration,cli-reference}.md`, `concepts/{knowledge-format,semantic-search}.md`.
