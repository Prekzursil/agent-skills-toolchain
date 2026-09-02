# W-rails receipt — target-scope allowlist hook + security-action audit ledger

**Wave:** W-rails · **Branch:** `cursor/cyber-suite-full-program` · **Status:** SKELETON — nothing measured yet.

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: every section below is still UNKNOWN.

## Scope (paths this wave may touch)

- `hooks/target-scope/**` (new)
- `hooks/security-action/**` (new)
- `docs/plans/cyber-receipts/W-rails.md` (this file)

Not touched: `hooks/file-scope/`, `hooks/ulysses/`, `.agents/agents.json`, parked catalog,
provenance, control-plane tests, `docs/plans/2026-09-02-cyber-suite-*.md`.

## Claims (rewrite at each milestone)

| Claim | Status |
|-------|--------|
| Receipt skeleton written first | UNKNOWN - not yet measured |
| `hooks/target-scope/check.py` — PreToolUse allowlist over tool-argument strings (host/URL/path) | UNKNOWN - not yet measured |
| `hooks/target-scope/set_scope.py` — sidecar writer CLI (clone of file-scope) | UNKNOWN - not yet measured |
| `hooks/target-scope/_common.py` — stdlib-only helpers, fail-soft | UNKNOWN - not yet measured |
| target-scope fail-OPEN: no sidecar | UNKNOWN - not yet measured |
| target-scope fail-OPEN: malformed sidecar / garbage stdin | UNKNOWN - not yet measured |
| target-scope fail-OPEN: `TARGET_SCOPE=off` / `.disabled` | UNKNOWN - not yet measured |
| target-scope ALLOW on glob match (exit 0) | UNKNOWN - not yet measured |
| target-scope BLOCK on mismatch (exit 2 + reason on stderr) | UNKNOWN - not yet measured |
| target-scope: no network, pure stdlib (import audit) | UNKNOWN - not yet measured |
| `hooks/security-action/ledger.py` — append-only JSONL audit (ts, tool, redacted args, verdict, reason) | UNKNOWN - not yet measured |
| security-action redacts secret-shaped values (key/token/password patterns) | UNKNOWN - not yet measured |
| security-action atomic replace (tmp + `os.replace`) | UNKNOWN - not yet measured |
| security-action concurrent-writer test (no torn/lost lines) | UNKNOWN - not yet measured |
| `python3 -m pytest hooks/target-scope hooks/security-action -q` green | UNKNOWN - not yet measured |
| ruff 0.15.17 `check` + `format --check` clean on touched Python | UNKNOWN - not yet measured |
| Existing `hooks/file-scope/` + `hooks/ulysses/` tests still green (untouched, regression guard) | UNKNOWN - not yet measured |
| Commit SHA | UNKNOWN - not yet measured |

## Test counts

UNKNOWN - not yet measured

## Verification commands run

UNKNOWN - not yet measured

## Wire spec (for the parent to register; this wave does not edit `hooks.json`)

UNKNOWN - not yet measured

## PARENT MERGE

UNKNOWN - not yet measured

## Commit

UNKNOWN - not yet measured
