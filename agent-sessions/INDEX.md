# Agent-session stores — complete discovery map (INDEX)

Owner mandate (2026-10-18): preserve EVERY AI-agent session on C: and D: (all
TUIs), including orphaned backup folders. Dedup content-identical sessions,
lose nothing. The REPO owns the pipeline (tooling + registry + manifest
summary); bulk content lives in the VAULT on D:, never in git.

| Piece | Where |
|---|---|
| Canonical registry | `tools/agent-sessions/stores.yaml` (67 stores; ids match the live manifest) |
| Sync engine | `tools/agent-sessions/agent_sessions_sync.py` (v1.2.0 — vault dialect) |
| Live install (watchdog-run) | `C:/Users/Prekzursil/.agents/scripts/` (engine + registry, kept in sync from this branch) |
| Vault | `D:/agent-sessions-vault` — `stores/<id>/…`, `manifest.jsonl` (176,145 entries), `state/`, `logs/` |
| Drift baseline | `tools/agent-sessions/manifest-summary.json` (per-store counts + sha256 of the manifest) |
| Runbook | `docs/agent-sessions-vault.md` |

## Store map (both drives)

Columns: source bytes = bytes summed from manifest rows (source-side sizes).
`aliases` = rows deduped to an earlier store's canonical copy (content-identical).
Every store's vault location is `D:/agent-sessions-vault/stores/<id>/`.
"src bytes" totals 312.49GB across 176,145 rows; content dedup saves the
duplicated ~75.9GB of that from being stored twice.

| store id | TUI | source | drv | mode | files | src bytes | aliases | status | notes |
|---|---|---|---|---|---:|---:|---:|---|---|
| `fixt-a` | FixtureA | `C:/Users/Prekzursil/.zcode/workspace/default/out/harness-audit-2026-10-18/_selftest/fixt-a` | C: | tree | 2 | 0.00GB | 0 | vaulted | regression fixture (vault-lane bootstrap; kept for manifest continuity) |
| `fixt-b` | FixtureB | `C:/Users/Prekzursil/.zcode/workspace/default/out/harness-audit-2026-10-18/_selftest/fixt-b` | C: | tree | 2 | 0.00GB | 0 | vaulted | regression fixture (vault-lane bootstrap; kept for manifest continuity) |
| `claude-code` | claude-code | `C:/Users/Prekzursil/.claude/projects` | C: | accepted | 19351 | 12.49GB | 1 | vaulted |  |
| `claude-history` | claude-code | `C:/Users/Prekzursil/.claude/history.jsonl` | C: | tree | 1 | 0.00GB | 0 | vaulted |  |
| `claude-todos` | claude-code | `C:/Users/Prekzursil/.claude/todos` | C: | tree | 24 | 0.00GB | 23 | vaulted |  |
| `claude-checkpoints` | claude-code | `C:/Users/Prekzursil/.claude/checkpoints` | C: | accepted | 2 | 0.00GB | 0 | vaulted |  |
| `claude-agent-worktrees` | claude-code | `C:/Users/Prekzursil/.claude/agent-worktrees` | C: | accepted | 10 | 0.00GB | 0 | vaulted |  |
| `claude-agent-handoff` | claude-code | `C:/Users/Prekzursil/.claude/agent-handoff` | C: | tree | 5 | 0.00GB | 0 | vaulted |  |
| `claude-free` | claude-code | `C:/Users/Prekzursil/.claude-free` | C: | accepted | 20040 | 13.20GB | 19567 | vaulted | alternate Claude home (Git Bash find/du undercounts it - Python walk authoritative) |
| `claude-server-commander` | claude-server-commander | `C:/Users/Prekzursil/.claude-server-commander` | C: | accepted | 1 | 0.00GB | 0 | vaulted |  |
| `codex-live` | codex | `C:/Users/Prekzursil/.codex/sessions` | C: | accepted | 2617 | 1.46GB | 0 | vaulted |  |
| `codex-archived` | codex | `C:/Users/Prekzursil/.codex/archived_sessions` | C: | tree | 19 | 0.00GB | 0 | vaulted | codex archived_sessions (superseded store layout) |
| `codex-root-state` | codex | `C:/Users/Prekzursil/.codex` | C: | accepted_top | 12 | 0.72GB | 2 | vaulted |  |
| `grok` | grok | `C:/Users/Prekzursil/.grok/sessions` | C: | tree | 14682 | 4.17GB | 3569 | vaulted |  |
| `grok-root` | grok | `C:/Users/Prekzursil/.grok` | C: | accepted_top | 2 | 0.00GB | 1 | vaulted |  |
| `grok-desktop` | grok | `C:/Users/Prekzursil/AppData/Roaming/Grok Bot` | C: | tree | 626 | 0.06GB | 87 | vaulted |  |
| `zcode-rollout` | zcode | `C:/Users/Prekzursil/.zcode/cli/rollout` | C: | tree | 533 | 20.18GB | 0 | vaulted |  |
| `zcode-exec` | zcode | `C:/Users/Prekzursil/.zcode/cli/exec` | C: | tree | 746 | 8.95GB | 454 | vaulted | rows flipped status=missing as the live CLI removes old call-logs (vault copies retained) |
| `zcode-image-cache` | zcode | `C:/Users/Prekzursil/.zcode/cli/image-cache` | C: | tree | 28 | 0.01GB | 2 | vaulted |  |
| `zcode-cli-db` | zcode | `C:/Users/Prekzursil/.zcode/cli/db` | C: | tree | 3 | 0.42GB | 0 | vaulted |  |
| `zcode-v2` | zcode | `C:/Users/Prekzursil/.zcode/v2` | C: | accepted_top | 2 | 0.01GB | 1 | vaulted |  |
| `zcode-memories` | zcode | `C:/Users/Prekzursil/.zcode/cli/memories` | C: | tree | 69 | 0.00GB | 0 | vaulted |  |
| `zcode-workspace` | zcode | `C:/Users/Prekzursil/.zcode/workspace` | C: | accepted | 299 | 0.32GB | 114 | vaulted |  |
| `gemini-cli` | gemini | `C:/Users/Prekzursil/.gemini/tmp` | C: | tree | 212 | 0.01GB | 1 | vaulted |  |
| `gemini-history` | gemini | `C:/Users/Prekzursil/.gemini/history` | C: | tree | 35 | 0.00GB | 30 | vaulted |  |
| `cursor-chats` | cursor | `C:/Users/Prekzursil/.cursor/chats` | C: | tree | 1555 | 1.98GB | 6 | vaulted |  |
| `cursor-acp` | cursor | `C:/Users/Prekzursil/.cursor/acp-sessions` | C: | tree | 8 | 0.00GB | 2 | vaulted |  |
| `cursor-globalstorage` | cursor | `C:/Users/Prekzursil/AppData/Roaming/Cursor/User/globalStorage` | C: | accepted_top2 | 2 | 3.01GB | 0 | vaulted |  |
| `opencode` | opencode | `C:/Users/Prekzursil/.local/share/opencode` | C: | tree | 10 | 0.29GB | 2 | vaulted |  |
| `cline` | cline | `C:/Users/Prekzursil/.cline` | C: | accepted | 26 | 0.37GB | 2 | vaulted |  |
| `copilot` | copilot | `C:/Users/Prekzursil/.copilot` | C: | accepted | 2 | 0.00GB | 0 | vaulted |  |
| `cyberstrike-share` | cyberstrike | `C:/Users/Prekzursil/.local/share/cyberstrike` | C: | tree | 12034 | 3.25GB | 1677 | vaulted |  |
| `cyberstrike-home` | cyberstrike | `C:/Users/Prekzursil/.cyberstrike` | C: | tree | 8 | 0.00GB | 1 | vaulted |  |
| `antigravity-cli` | antigravity | `C:/Users/Prekzursil/.antigravitycli` | C: | tree | 0 | - | 0 | registry-only (empty) | empty store (0 files) - ~/.antigravitycli never populated; AGY sessions are in gemini-antigravity |
| `antigravity-local` | antigravity | `C:/Users/Prekzursil/AppData/Local/antigravity` | C: | tree | 1 | 0.00GB | 0 | vaulted |  |
| `claude-desktop-code-sessions` | claude-desktop | `C:/Users/Prekzursil/AppData/Roaming/Claude/claude-code-sessions` | C: | tree | 8 | 0.00GB | 0 | vaulted |  |
| `claude-desktop-agent-mode` | claude-desktop | `C:/Users/Prekzursil/AppData/Roaming/Claude/local-agent-mode-sessions` | C: | tree | 3709 | 0.04GB | 176 | vaulted |  |
| `claude-desktop-indexeddb` | claude-desktop | `C:/Users/Prekzursil/AppData/Roaming/Claude/IndexedDB` | C: | tree | 14 | 0.00GB | 6 | vaulted |  |
| `claude-desktop-localstorage` | claude-desktop | `C:/Users/Prekzursil/AppData/Roaming/Claude/Local Storage` | C: | tree | 11 | 0.00GB | 3 | vaulted |  |
| `vscode-globalstorage` | vscode | `C:/Users/Prekzursil/AppData/Roaming/Code/User/globalStorage` | C: | accepted_top2 | 3 | 0.01GB | 1 | vaulted |  |
| `vscode-workspacestorage` | vscode | `C:/Users/Prekzursil/AppData/Roaming/Code/User/workspaceStorage` | C: | accepted | 54 | 0.01GB | 0 | vaulted |  |
| `continue-index` | continue | `C:/Users/Prekzursil/.continue/index` | C: | accepted | 2 | 0.00GB | 0 | vaulted |  |
| `d-agentchattr` | agentchattr | `D:/agentchattr` | D: | tree | 106 | 0.00GB | 5 | vaulted |  |
| `claude-desktop-backup-20260524` | claude-desktop | `C:/Users/Prekzursil/Documents/claude-desktop-backup-20260524` | C: | tree | 7460 | 0.84GB | 3332 | vaulted | ORPHANED backup (pre-2026-05-24 Claude Desktop state) |
| `ai-exports` | multi | `C:/Users/Prekzursil/Downloads/AIs Conversations` | C: | tree | 9319 | 3.38GB | 515 | vaulted |  |
| `vm-backup` | multi | `C:/Users/Prekzursil/Downloads/BACKUPS VM` | C: | accepted | 3376 | 3.64GB | 2289 | vaulted | BACKUPS VM store (sessions accepted-filtered) |
| `vm-consolidated` | multi | `C:/Users/Prekzursil/Downloads/vm-consolidated-2026-09-24` | C: | accepted | 12 | 0.00GB | 12 | vaulted | ORPHANED VM consolidation output |
| `skills-claude-web` | claude-web | `C:/Users/Prekzursil/Downloads/skills_claude_web` | C: | accepted | 210 | 0.00GB | 209 | vaulted |  |
| `downloads-loose-rollouts` | codex | `?` | ? | files | 2 | 0.05GB | 0 | vaulted | two loose rollout jsonl files in Downloads |
| `cowork-private` | cursor | `C:/Users/Prekzursil/Cowork/private` | C: | accepted | 130 | 48.84GB | 50 | vaulted | owner-named 'cursor-auth backups': ~20 historical state.vscdb snapshots (Cursor chat+auth) |
| `cowork-backups` | multi | `C:/Users/Prekzursil/Cowork/backups` | C: | accepted | 112 | 0.02GB | 97 | vaulted |  |
| `claude-projects-archive` | claude-code | `D:/claude-projects-archive` | D: | tree | 14378 | 20.98GB | 4489 | vaulted | ORPHANED archive of a replaced ~/.claude/projects |
| `claude-history-viewer-archive` | claude-history-viewer | `D:/claude-history-viewer-archive` | D: | tree | 19815 | 10.12GB | 19758 | vaulted | ORPHANED history-viewer export |
| `codex-archive-20260621` | codex | `D:/codex-sessions-archive-20260621` | D: | move | 1587 | 60.79GB | 8 | vaulted | MOVED 2026-10-18 09:11: same-volume rename into vault (60.79GB saved from copying); source path intentionally gone - steady state for mode:move |
| `codex-seed-extracted` | codex | `D:/codex-seed-extracted` | D: | tree | 1540 | 43.92GB | 1503 | vaulted | extraction of codex-seed-tar; 42.68GB of it content-aliases the tar's files |
| `d-backups` | multi | `D:/Backups` | D: | accepted | 34 | 3.84GB | 9 | vaulted | D:/Backups with images+docker-volumes pruned (control-source rule); 1 row(s) status=missing (vanished-source history, vault copies retained) |
| `codex-seed-tar` | codex | `?` | ? | files | 1 | 43.92GB | 0 | vaulted | 43.92GB single-file tar container (irreducible duplicate of codex-seed-extracted) |
| `gemini-antigravity` | antigravity | `C:/Users/Prekzursil/.gemini/antigravity-cli` | C: | tree | 3817 | 0.56GB | 407 | vaulted | GAP FIXED this wave: AGY session corpus, previously covered by neither gemini-cli nor gemini-history; brain/*/.git internals (5,090 git-object files) pruned per control-source rule - working trees + conversations + history + summaries DB vaulted |
| `opencode-config` | opencode | `C:/Users/Prekzursil/.config/opencode` | C: | tree | 5 | 0.00GB | 0 | vaulted | npm node_modules (3,445 files) pruned per control-source rule; config + lockfile vaulted; sessions live in store 'opencode' |
| `grokbot` | grok | `C:/Users/Prekzursil/.grokbot` | C: | tree | 10 | 0.00GB | 0 | vaulted | vault-lane sample review found no session content; whole-tree vaulted anyway (zero-loss) |
| `goose-config` | goose | `C:/Users/Prekzursil/.config/goose` | C: | tree | 3221 | 0.03GB | 288 | vaulted | empty store (0 files) - registry-only until goose writes here |
| `goose-appdata` | goose | `C:/Users/Prekzursil/AppData/Roaming/Goose` | C: | tree | 88 | 0.00GB | 49 | vaulted |  |
| `aider` | aider | `C:/Users/Prekzursil/.aider` | C: | tree | 4 | 0.00GB | 0 | vaulted |  |
| `continue-vscode` | continue | `C:/Users/Prekzursil/.continue` | C: | tree | 12 | 0.00GB | 1 | vaulted |  |
| `vscode-copilot-chat` | copilot | `C:/Users/Prekzursil/AppData/Roaming/Code/User/globalStorage/github.copilot-chat` | C: | tree | 8 | 0.09GB | 0 | vaulted |  |
| `verdict-archive` | verdict | `D:/verdict-archive` | D: | tree | 34118 | 0.33GB | 28 | vaulted | ORPHANED D: archive (34,118 files) - missed by vault-lane discovery, found via tooling-lane registry, vaulted this wave |
| `primariro-scratchpad-archive` | primariro | `D:/PrimariRo-scratchpad-archive-20260812` | D: | tree | 10 | 0.13GB | 0 | vaulted | ORPHANED D: archive - same provenance as verdict-archive |

## Orphaned backups / archives (original no longer corresponds)

Vaulted by design — the owner mandate explicitly includes backups that no
longer correspond to their original: `claude-desktop-backup-20260524`,
`claude-projects-archive`, `claude-history-viewer-archive`,
`codex-archived`, `codex-seed-extracted` + `codex-seed-tar`,
`codex-archive-20260621` (moved in whole), `vm-consolidated`,
`verdict-archive`, `primariro-scratchpad-archive`, and the historical
`cowork-private` vscdb snapshots.

## The MOVE (owner-sanctioned)

`D:/codex-sessions-archive-20260621` (1,587 files / 60.79GB) was renamed
into `D:/agent-sessions-vault/stores/codex-archive-20260621` on
2026-10-18 09:11 (same-volume rename, tree intact, hash-verified at adopt —
60.79GB of copying saved). The source path is INTENTIONALLY gone; the engine
(`mode: move`) adopts-in-place calmly on every later run.

## Prune rule (control-source convention, applied to every store)

Global prune dirs (skipped during walks, identical to the vault-build engine
and `tss/tsis-deepdive/corpus/build_corpus.py`): `node_modules`, `.git`,
`__pycache__`, `.venv`, `venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`;
plus per-store `prune:` csv (only `d-backups`: `images,docker-volumes`).
These are vendored/derivable trees, never session content. Verified this
wave: `gemini-antigravity`'s 5,090 skipped files are ALL `brain/*/.git/`
git-object internals (the brain working trees + conversations + history ARE
vaulted); `opencode-config`'s 3,445 skipped are npm `node_modules`.

## Reviewed and NOT vaulted (no session content — sample-checked 2026-10-18)

`~/.claude-history-viewer` (5KB stub; real archive vaulted),
`~/.claude-runtime`, `~/.claude-swap-backup`, `~/.claude.lock`,
`~/.cursor-profiles`, `~/codex-session-manager` (tool source repo),
`~/Downloads/grok_reupload_work`, `~/Downloads/photos codex conversations`
(screenshots), `~/Downloads/prompts_USEFUL!!!! CODEX`,
`~/Downloads/claude_status_line`, `~/Downloads/Claude_Suspension_Dispute`,
`~/Downloads/Tools, codex, cloud gate 0 and automatization`,
`~/Downloads/.codex-verify-worktrees`,
`~/Documents/claude-diagnostic-a5f735f7-20260524-0049`, the
`Dboltenumpulls*` dumps. Probed absent: Windsurf (`~/.codeium`,
`AppData/Local/Codeium/windsurf*`), fabric (`~/.fabric`), Cline/Ro VS Code
extension globalStorage, `~/.goose` (desktop data is vaulted via
`goose-appdata`), `~/.antigravity`/`~/.agy` (no sessions), Roaming/opencode,
Roaming/grok, `~/.config/grok`, `from-C-20260818` dirs.

## Reconciliation vs control sources

- `tss/tsis-deepdive/corpus/build_corpus.py` ROOTS (control source, found at
  `C:/Users/Prekzursil/.zcode/workspace/default/tss/tsis-deepdive/corpus/`):
  every ROOT is covered by a registry id (mapping in the vault report
  `out/harness-audit-2026-10-18/sessions-vault.md` §2). This registry adds
  beyond it: claude-history, claude-free, claude-server-commander, grok-root,
  d-agentchattr (corpus D_PRUNE wrongly prunes it), cowork-private,
  cowork-backups, downloads-loose-rollouts, claude-desktop-backup-20260524,
  and the 2026-10-18 additions below.
- `ai-sessions-render` (`Documents/GitHub/ai-sessions-render`, providers in
  `llm_anthology/discover.py`): codex/claude-code/grok/exports providers all
  covered. Its `.scratch/_probe_provider_stores.ps1` does not exist (nearest:
  `.scratch/probe_providers.py`).
- 2026-10-18 additions (this wave): `gemini-antigravity` (AGY corpus — a real
  GAP both control sources miss), `opencode-config`, `grokbot`, `goose-config`,
  `goose-appdata`, `aider`, `continue-vscode`, `vscode-copilot-chat`,
  `verdict-archive`, `primariro-scratchpad-archive`.

## Drift detection (how the repo detects vault drift without the bulk)

`tools/agent-sessions/manifest-summary.json` pins the manifest's sha256
(`4c28bca7…`), size, entry count, and per-store counts/bytes/aliases. To
check drift: hash `D:/agent-sessions-vault/manifest.jsonl` and compare
against `manifest_sha256`; per-store deltas localize any change. Regenerate
after any sync with `python tools/agent-sessions/regen_summary.py`.

## Missing rows (vanished-source history — kept forever by design)

8 rows are `status=missing` (zcode-exec call-logs the live CLI removed between
passes + one transient D:/Backups file): their vault copies and hashes remain
in the manifest. Zero-loss means the manifest remembers sources that went
away, not that it forgets them.

## Engine lineage (why two engines exist and which one runs)

The vault-build engine (`tools/sessions-vault/agent_sessions_sync.py`, branch
`sessions-vault` @ `00eda4b1f`, 711 lines) built and verified the 311GB vault.
The tooling engine (this branch, from `98515d111` @ 1076 lines) is the
watchdog-facing one (`--quiet`, lock, `--restore`, `--rediscover`). As of
v1.2.0 (this wave) the tooling engine speaks the vault dialect (modes
tree/accepted*/files/move, original-src keying for moved stores, per-file
vanish marking), so ONE registry + ONE manifest serve both; the daily
watchdog run at `C:/Users/Prekzursil/.agents/scripts/` uses the engine +
registry committed on this branch.
