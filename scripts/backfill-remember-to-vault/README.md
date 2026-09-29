# backfill-remember-to-vault (PREPARED, NOT EXECUTED)

14 ready-to-write vault notes covering 2026-09-23..2026-09-29, plus one idempotent
writer. **Nothing has been written to the vault.** `--plan` is the default; `--apply`
is mandatory to write and is gated twice (below).

```
backfill_remember_to_vault.py        # the one script: --seal / --plan / --apply
manifest.json                        # id -> title, folder, type, tags, sha256, source_slice, restates
notes/01..14-*.md                    # the note bodies, each ending in an immutable marker line
```

## Run order for the orchestrator

```powershell
# 0. inspect (writes nothing, exits 0)
python backfill_remember_to_vault.py

# 1. ONLY after basic-memory has been brought up cleanly once and the DB confirmed at
#    head, and with the daemon then DOWN again:
python backfill_remember_to_vault.py --apply --migrations-verified

# 2. disposition each OPEN supersede row, then ack it:
python backfill_remember_to_vault.py --record-supersede "L6-BF-03:reference_opus55_cyber_fallback_2026-09-25.md"
```

Until every blocking supersede row is acked, `--apply` ends in `FAILED:` **even when all
14 notes wrote cleanly** — by design, so a green run cannot hide knowledge fragmentation.
Read the counts on the summary line; `failed=0 partial=0 conflicts=0` with a non-zero
`supersede_unactioned` means the writes succeeded and only the supersede edges are open.

## The two gates on `--apply`

| Gate | Flag | Why |
|---|---|---|
| ordering | `--migrations-verified` | `db.py:352-353` runs alembic automatically on first local-ASGI DB use, and `i2c3d4e5f6g7_auto_backfill_semantic_embeddings.py` documents that the transition triggers an embedding backfill. A 14-note batch must not be that first invocation, least of all against the just-repointed `C:\drive-d\basic-memory`. |
| serialization | `--allow-daemon-up` | Refuses while `:18765` is listening, so this can never become a second in-process SQLite writer during a daemon restart window. Daemon lifecycle belongs to the orchestrator. |

## Where things live

- **Ledger (default):** `~/.agents/state/harness/backfill-remember-to-vault/ledger.jsonl`
  — under `state/`, which `.gitignore:17` ignores, so a per-run runtime artifact never
  enters the end-of-run commit. G1 therefore trusts a *local* ledger; after a repo
  restore the ledger is gone and dedup falls through to G2/G3 against the live vault,
  which is the safe direction.
- **Supersede queue / acks:** beside the ledger, same gitignored directory.
- **Vault:** resolved once at preflight from `~/.basic-memory/config.json`
  `projects.main.path`, never hardcoded (`RecallModule` still defaults to the stale
  `D:/basic-memory`). `--vault` overrides it for verification only.

## Dedup and verification

Three gates, cheapest first, sequential: **G1** ledger hit with a matching body sha256
(zero CLI calls) · **G2** on-disk, *marker-glob primary* with the predicted
`<folder>/<title>.md` only a hint — a foreign note at that path is reported
`CONFLICT-foreign-note` and never touched · **G3** server-side `NOTE_ALREADY_EXISTS`
(`--overwrite` is never passed), mapped to a SKIP, not a FAILED.

Verification is an AND-gate of two mechanically independent signals: **A** reads the note
back through `tool read-note` using the permalink *returned in the write result JSON* and
parses it (exit code is unusable — `tool.py` documents that a genuine not-found returns
null fields and still exits 0); **B** globs the target folder for the immutable marker and
checks mtime. Both → `SUCCESS`, one → `PARTIAL`, neither → `FAILED`.

`--seal` recomputes every marker and manifest hash. The sha256 span is the body with LF
line endings and trailing whitespace stripped, **excluding the trailing marker line**, so
the marker never hashes itself. Re-run `--seal` after editing any body.

## Transport

`basic-memory tool write-note`, content on stdin, `--local` on every call. The CLI imports
the MCP tool in-process over an ASGI transport: it binds no port, never touches `:18765`,
and spawns no server, so it is neither a stdio spawn nor a port bind
(`memory-contract.md:11-13`) and it writes *through* `write_note`, satisfying the G-81
writer lock (`memory-contract.md:67`). The estate's own production flusher
(`harness/modules.py:500-525`) already shells this exact form.
