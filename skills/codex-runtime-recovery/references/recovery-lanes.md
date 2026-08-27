# Recovery Lanes

## Lightweight recovery

Use when a thread exists but is not visible in the active host. Favor targeted session import, `codex resume`, or launch-path correction.

## Canonicalization

Use when multiple stores have diverged. Preserve the best store, archive mirrors, and repoint every launch path to the canonical root.

## Reset-only lane

Use only when startup fails across all launch paths and the failure is tied to migration mismatch or unrecoverable runtime state. Backup first, rotate only the minimal files, and let regeneration prove the diagnosis.

## Evidence to capture

- which hosts still launch
- which stores still receive new sessions
- whether the failure is visibility, auth, or launch stability
- exact files backed up before any reset
