---
title: README
type: note
permalink: dqverify-repo-20261013/agent-self/harness/readme
---

# Shared Lifecycle Harness

This directory is the provider-neutral lifecycle layer for Claude Code, Codex and the
xAI Grok CLI. Each provider sends its native stdin JSON to `dispatcher.py`;
`adapters.py` normalizes it, the ordered modules return the closed core result
contract, and the adapter emits only the provider's supported native fields. (Grok is a
RUNTIME provider only: its hook file is produced by Grok's own importer, and
`install.py` still writes just the Claude and Codex documents.)

```text
provider stdin
    |
    v
normalize -> ordered modules -> core HookResult -> native adapter -> provider stdout
                         |
                         +-> terminal.jsonl (SUCCESS:<id> or FAILED:<id>)
```

## Invariants

- Core results contain only `status`, `action`, `reason_code`, `additional_context`,
  and optional `continuation`. See `schemas/hook-result.schema.json`.
- Module order is fixed: secret guard, sensitive-artifact report, event ledger, goal
  reinjection, sanitized checkpoint, bounded recall, anti-degeneration, claim warning,
  subagent lifecycle.
- Unexpected module errors fail open and are recorded as `FAILED:hook-<event>` without
  exposing exception text to either model.
- Only irreversible operations and literal-secret or credential access paths are blocked.
- Recall reads a local lexical index only. Hooks never call vector, semantic, network,
  or model search.
- Recall never serves an index it cannot date. A candidate index file is used only when it
  declares a `schema_version` this consumer understands and a `built_at` inside the age
  limit; otherwise it is skipped in favour of the next configured path, and recall stays
  quiet when every candidate is rejected. Stale-but-quiet beats obsolete-and-injected.
- Pre-compaction checkpoints contain a session hash and project hash, never a transcript
  path, raw session identifier, absolute cwd, or unredacted secret.
- Provider output never contains `suppressOutput`, and an inject is rendered as
  `hookSpecificOutput.additionalContext` only for events whose member of the host's
  output union can carry it; the rest (`PostCompact`, `TaskCompleted`, `TaskCreated`,
  `TeammateIdle`, `PermissionDenied`, `ConfigChange`) render as `systemMessage` so the
  host does not discard the whole payload.
- The module fan-out runs under a wall-clock budget derived from the event's registered
  host timeout (`registration._TIMEOUTS` minus a 0.6s start-up allowance). A module that
  outlives it is abandoned and named in `failed_modules`; the terminal record is written
  either way. `HARNESS_DISPATCH_BUDGET_MS` overrides the budget (`0` disables it).
- Terminal health describes what actually ran: an enforced breaker quarantine, an
  abandoned module and an unparseable stdin all stamp `FAILED:hook-<event>`.
- A typed verification receipt is minted only by a tool that EXECUTES a command
  (`Bash`, `PowerShell`, `shell`, MCP `*run_command`, ...), never from a payload that
  merely contains `command`; informational invocations (`pytest --version`), read-only
  heads (`echo test`), exit-code laundering (`... || true`) and zero-test runs never
  count as a green. The newest receipt per class decides, so a failing rerun revokes an
  earlier pass, and a mutation anywhere in the cwd invalidates it.
- The ledger lock is an OS-level advisory lock (`fcntl`/`msvcrt`) that the kernel
  releases when the holder dies; a killed hook worker never stalls the next append.

## Operations

Run tests:

```powershell
python -m pytest -q C:\Users\Prekzursil\.agents\harness\tests
```

Rebuild the shared Basic Memory lexical index:

```powershell
python C:\Users\Prekzursil\.agents\harness\recall_index.py --vault D:\basic-memory
```

The rebuild is manual, so the index is the one harness artifact that can silently rot:
notes get edited, superseded, or deleted in the vault while the built document stays on
disk. `recall_index.py` therefore stamps each document with `schema_version` (the note
schema it was produced with), `built_at` (UTC build time) and `vault_hash` (a fingerprint
over every indexed path plus its mtime), and `RecallModule` refuses to serve a document
whose `schema_version` it does not understand or whose `built_at` is older than 30 days.
Consequence to expect in the field: recall goes quiet rather than wrong once the index
expires — rerun the command above (and re-run it after any bulk vault edit, since an
unchanged `built_at` is what the age check reads). Operators who rebuild out-of-band on a
different cadence can widen or disable the age check with
`AGENT_HARNESS_RECALL_MAX_AGE_DAYS` (days; `0` disables it).

Every build also writes the slim `recall-digest.json` sidecar next to the index (top 16
notes by importance/mtime, no keyword arrays, cache paths excluded). `RecallModule`
injects that digest — marked UNTRUSTED — once per session on `SessionStart` and once on
the first `UserPromptSubmit` (the portable path for hosts that drop `SessionStart`
stdout). It never walks the vault and never loads the full keyword index for this.
Rebuild the sidecar alone, without a vault scan, with:

```powershell
python C:\Users\Prekzursil\.agents\harness\recall_index.py --from-index C:\Users\Prekzursil\.agents\state\harness\recall-index.json
```

`AGENT_HARNESS_RECALL_DIGEST` relocates the sidecar the module reads.

Capture discipline (`basic_memory_nudge`): a session that mutated any file and wrote
nothing to basic-memory gets one Stop-time nudge, tracked by sticky per-session flags
under `state/session-flags/` (the bounded ledger window is only the fallback carrier),
and the Stop hook spools a session note under `state/bm-spool/`. The spool is flushed
best-effort through the `basic-memory` CLI (`BASIC_MEMORY_CLI` overrides the binary) and
retried on the next `SessionStart`; under pytest the flush is inert unless
`HARNESS_BM_FLUSH_IN_TEST=1`.

Install registrations after the tests pass:

```powershell
python C:\Users\Prekzursil\.agents\harness\install.py
python C:\Users\Prekzursil\.agents\harness\install.py --check
```

The installer creates an exact timestamped rollback copy under `backups/` and updates
each JSON document atomically. Codex hashes changed hook definitions and requires review
through `/hooks` in a fresh session; do not bypass that trust review.