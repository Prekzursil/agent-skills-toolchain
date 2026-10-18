# Agent Sessions Vault — runbook

Owner mandate (2026-10-18): preserve EVERY AI-agent session on C: and D: (all
TUIs), including orphaned backup folders. Dedup content-identical sessions but
lose nothing. This repo OWNS the pipeline tooling and manifests; the bulk
content lives in the vault on D:, NOT in git (this repo already suffers
vendored-tree bloat — content-in-git would be an explicit owner opt-in).

## Topology

| Piece | Where | Notes |
|---|---|---|
| Sync tool | `tools/agent-sessions/agent_sessions_sync.py` (live copy: `C:/Users/Prekzursil/.agents/scripts/agent_sessions_sync.py`) | The live copy is the one the scheduler runs; keep them in sync via this branch. |
| Store registry | `tools/agent-sessions/stores.yaml` (live: same dir) | THE single config the owner edits when a new TUI appears. |
| Vault | `D:/agent-sessions-vault` | `stores/<id>/...` content, `manifest.jsonl` (+`.bak`), `manifest-summary.json`, `state/last-run.json`, `logs/sync-YYYYMMDD.log`, `.sync.lock`. |
| Cadence | `D:/opt/cyberstrike-mcp/watchdog-mcp-estate.ps1` section 8 | Throttled daily launch (no new scheduled task — owner rule). Rollback: `watchdog-mcp-estate.ps1.bak-20261018`. |

Stdlib-only Python (PyYAML optional — a built-in fallback parser handles the
registry subset; both loaders were verified to produce identical 25-store
registries). Run with any Python >= 3.7, e.g. `C:\Python314\python.exe`.

## Daily operation

The watchdog sweep launches the sync once per 24 h (detached, hidden). The
sync is single-instance (lock), resumable, and incremental — safe to also run
manually any time:

```
# plan only, writes nothing anywhere
python agent_sessions_sync.py --dry-run [--only STORE_ID]

# real incremental sync (this is what the watchdog runs, with --quiet)
python agent_sessions_sync.py --quiet

# zero-loss proof (see Verification below)
python agent_sessions_sync.py --verify
```

Exit codes: `0` clean (or lock-SKIP), `1` warnings (e.g. unreadable source
files), `2` LOSS-RISK — inspect `<vault>/logs/sync-*.log` and
`<vault>/state/last-run.json`. The watchdog retries a non-zero run on the next
sweep (5 min) and logs one WARN per failed run; a clean run calms it for 24 h.

## Registry semantics (stores.yaml)

One entry per store: `id` (becomes `vault/stores/<id>/`), `tui` label, `path`
(source root — NEVER modified, copy-only), optional `include`/`exclude` posix
globs, optional `mode`.

- `mode: rename` — same-drive ADOPTION for already-archived trees. Used ONLY
  (owner-sanctioned) for `D:/codex-sessions-archive-20260621` (~56 G): the
  tree is `os.rename`d INTO the vault intact (0 bytes copied), file/byte
  counts verified pre/post, original path recorded in
  `stores/<id>/_ADOPTED_FROM.txt`, then hashed in place into the manifest.
  Both source-and-dest present = conflict = loss-risk exit (never overwrite).
- Live SQLite stores (`opencode.db`): `-wal` is kept (committed data),
  `-shm` excluded (transient). A copy torn mid-write is caught by the
  hash-verify; the `.prev` chain keeps the prior generation recoverable.
- Gotchas encoded in the registry: the Codex live store is `.jsonl.zst` only
  (plain jsonl globs miss it — codex-live has NO include filter, so zst is
  caught); Grok stores one directory per session (`sessions/**` include).

## Incremental semantics

`manifest.jsonl` is the state: one JSON object per source file, keyed by `src`
(absolute, forward slashes). Fields: `sha256`, `size`, `mtime_ns`, `gen`,
`prev {sha256,size}`, `alias_of`, `vault_path`, `store`, `tui`, `first_seen`,
`last_synced`, `status`.

- **NEW** — sha256 the file; if that content is already materialized in the
  vault, record an **ALIAS** (`alias_of` -> canonical `vault_path`, no second
  copy). Otherwise copy via `<dest>.part`, hash the .part, compare, then
  atomic `os.replace`. Any mismatch = loss-risk = exit 2.
- **GROWN** (jsonl append/resume: size/mtime drift, sha changed) — rotate the
  prior vault copy to `<vault_path>.prev` (exactly one generation kept, prior
  sha recorded in `prev`), fresh verified copy, `gen += 1`. Growth NEVER
  aliases.
- **mtime-only churn** (sha identical) — manifest timestamps refreshed, no copy.
- **ALIAS healing** — if a canonical target later grows, aliases whose target
  drifted are re-materialized from their (unchanged) source into their own
  vault copy.
- **Dedup is per-file sha256 with zero file-lineage assumptions** — a prior
  merge bug dropped 47.1% (953 files) of the Codex store; nothing here trusts
  filenames or store identity for content equality.
- **Unreadable** files get a manifest line with `status: unreadable`
  (visible, counted, exit 1) — never silently skipped.

## Verification (the zero-loss proof)

```
python agent_sessions_sync.py --verify
```

Three passes: (1) re-hash every unique materialized vault file against the
manifest; (2) every `status: ok` manifest line must be provable — alias lines
resolve to their target's verified sha; (3) a dry-run plan over all sources
must be EMPTY (no pending new/grown). Prints `ZERO-LOSS PROOF: PASS` iff all
hold; exit 2 otherwise. Run after any bulk copy, disk swap, or suspected
interference.

## Restore procedure

```
python agent_sessions_sync.py --restore STORE_ID --to C:/restore/target
```

Materializes the store from the vault (canonical copies AND aliases expanded
to their own files), re-hashing every restored file against the manifest sha;
any mismatch is reported and fails the run. For a generation-0 copy of a file
that later grew, restore from `<vault_path>.prev` manually (the manifest's
`prev.sha256` is the reference).

## Adding a TUI / re-discovery

Edit `stores.yaml` (the registry is the single source of truth), then run the
sync. To hunt for stores not yet registered:

```
python agent_sessions_sync.py --rediscover
```

prints YAML snippets for candidate session-looking trees (bounded scan of the
usual roots on C:/D:). Review, assign an `id`, paste into `stores.yaml`.

Open reconciliation items (2026-10-18):
- The vault lane's discovery report
  (`out/harness-audit-2026-10-18/sessions-vault.md`) had NOT landed when this
  registry was seeded/extended — re-run `--rediscover` and merge its findings
  when it does.
- `tss/tsis-deepdive/corpus` (build_corpus.py + manifest.jsonl) was NOT found
  on either drive (checked D:/ root, `~/`, `~/source`, `~/Documents`, bounded
  deep finds) — if it resurfaces, cross-reference its provider enumeration
  against this registry rather than duplicating content.
- `ai-sessions-render` exists at `C:/Users/Prekzursil/Documents/GitHub/ai-sessions-render`
  but its `.scratch/_probe_provider_stores.ps1` probe script was not present.
- Probed and absent on this machine: Windsurf, fabric, Cline/Ro VS Code
  extensions. `.agy` holds no sessions (AGY sessions live under
  `.gemini/antigravity-cli/`).

## Cadence wiring detail (watchdog section 8)

Added 2026-10-18 behind a clearly-marked `# 8)` block in
`D:/opt/cyberstrike-mcp/watchdog-mcp-estate.ps1` (the sweep that already runs
the hourly sampler + rotation — no new scheduled task). Design:

- Launch is DETACHED (`Start-Process -WindowStyle Hidden`) because the sweep's
  PT5M execution limit hard-kills synchronous children mid-copy; the sync's
  own lock + `.part`-then-atomic-replace discipline make that safe.
- Throttle: the vault's `state/last-run.json` is authoritative — `phase=done`,
  `rc=0`, finished <24 h ago means calm; a `last-agent-sessions-sync.stamp`
  (rotate-style) is the fallback when that file is missing/unreadable.
- A non-zero rc leaves the window open, so the next 5-min sweep RETRIES
  (retry-until-clean posture) and warns exactly once per failed run via
  `last-agent-sessions-sync-warn.stamp`.
- Verified: PSParser + Language.Parser both 0 errors; five stubbed behavioral
  scenarios (fresh-success calm, failed-run warn-once retry, no-state launch,
  stamp-fallback calm, real-state calm) all pass.
- Rollback: `copy /y watchdog-mcp-estate.ps1.bak-20261018 watchdog-mcp-estate.ps1`.
