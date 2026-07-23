# Shared Lifecycle Harness

This directory is the provider-neutral lifecycle layer for Claude Code and Codex. Both
providers send their native stdin JSON to `dispatcher.py`; `adapters.py` normalizes it,
the ordered modules return the closed core result contract, and the adapter emits only
the provider's supported native fields.

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
- Pre-compaction checkpoints contain a session hash and project hash, never a transcript
  path, raw session identifier, absolute cwd, or unredacted secret.
- Provider output never contains `suppressOutput`.

## Operations

Run tests:

```powershell
python -m pytest -q C:\Users\Prekzursil\.agents\harness\tests
```

Rebuild the shared Basic Memory lexical index:

```powershell
python C:\Users\Prekzursil\.agents\harness\recall_index.py --vault D:\basic-memory
```

Install registrations after the tests pass:

```powershell
python C:\Users\Prekzursil\.agents\harness\install.py
python C:\Users\Prekzursil\.agents\harness\install.py --check
```

The installer creates an exact timestamped rollback copy under `backups/` and updates
each JSON document atomically. Codex hashes changed hook definitions and requires review
through `/hooks` in a fresh session; do not bypass that trust review.

