# W-rails receipt — target-scope allowlist hook + security-action audit ledger

**Wave:** W-rails · **Branch:** `cursor/cyber-suite-full-program` · **Status:** DELIVERED — measured below.

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: no sections remain UNKNOWN. Every claim below is measured; commands are in "Verification commands run".

## Scope (paths this wave touched)

- `hooks/target-scope/**` (new)
- `hooks/security-action/**` (new)
- `docs/plans/cyber-receipts/W-rails.md` (this file)

Not touched (verified): `hooks/file-scope/`, `hooks/ulysses/`, `.agents/agents.json`, parked
catalog, provenance, control-plane tests, `docs/plans/2026-09-02-cyber-suite-*.md`.
`git status --porcelain -- hooks/file-scope hooks/ulysses` → empty.

## Files added

target-scope (PreToolUse argument allowlist, cloned from `hooks/file-scope/`):
- `hooks/target-scope/_common.py` — stdlib helpers: glob engine (`**`/`*`), sidecar I/O
  (TTL, atomic write), three-tier keying, target extraction (host/URL/path), pure `evaluate()`.
- `hooks/target-scope/check.py` — the hook. Exit 0 allow / exit 2 block (reason on stderr).
- `hooks/target-scope/set_scope.py` — CLI to write/clear/gc/list sidecars.
- `hooks/target-scope/test_target_scope.py` — 45 tests.

security-action (append-only JSONL audit rail, ideas borrowed from `event-ledger`):
- `hooks/security-action/ledger.py` — `redact()`, `append_record()` (atomic replace under a
  cross-platform mkdir lock; O_APPEND fallback), `read_records()`.
- `hooks/security-action/audit.py` — PreToolUse observer hook; always exit 0; labels
  allow/block by reusing target-scope's pure `evaluate()`; writes one redacted JSONL line.
- `hooks/security-action/test_security_action.py` — 24 tests.

## Claims (measured)

| Claim | Status |
|-------|--------|
| Receipt skeleton written first | DONE — committed `3fe06dd2` before any code |
| `hooks/target-scope/check.py` — PreToolUse allowlist over tool-argument strings (host/URL/path) | DONE |
| `hooks/target-scope/set_scope.py` — sidecar writer CLI (clone of file-scope) | DONE |
| `hooks/target-scope/_common.py` — stdlib-only helpers, fail-soft | DONE |
| target-scope fail-OPEN: no sidecar | DONE — `TestNoSidecar` (2), `test_evaluate_no_sidecar_failopen` |
| target-scope fail-OPEN: malformed sidecar / garbage stdin | DONE — `TestMalformed` (4) |
| target-scope fail-OPEN: `TARGET_SCOPE=off` / `.disabled` | DONE — `TestOptOut` (3) |
| target-scope ALLOW on glob match (exit 0) | DONE — `TestInScope` (5) |
| target-scope BLOCK on mismatch (exit 2 + reason on stderr) | DONE — `TestOutOfScope` (6) |
| target-scope: no-targets → fail-open even with block-all sidecar | DONE — `TestNoTargets` |
| target-scope: no network, pure stdlib | DONE — imports: os/sys/json/re/hashlib/time/pathlib/urllib.parse (parse only, no I/O) |
| `hooks/security-action/ledger.py` — append-only JSONL (ts, tool, redacted args, decision, reason) | DONE — `TestAppend` (6) |
| security-action redacts secret-shaped values (key/token/password patterns) | DONE — `TestRedact` (9) |
| security-action atomic replace (tmp + `os.replace`, no leftovers) | DONE — `TestAtomic` (2) |
| security-action concurrent writers (no lost/torn lines) | DONE — `TestConcurrent` (8 threads × 25 = 200 lines, all present & valid JSON) |
| audit.py hook end-to-end (fail-open, opt-out, authentic allow/block label) | DONE — `TestAuditHook` (6) |
| `python3 -m pytest hooks/target-scope hooks/security-action -q` green | DONE — **69 passed** |
| ruff 0.15.17 `check` + `format --check` clean on touched Python | DONE — check: all passed; format: 7/7 already formatted |
| Existing `hooks/file-scope/` + `hooks/ulysses/` tests still green (regression) | DONE — 62 passed, 4 skipped (Windows-only) |
| Commit SHA | DONE — see Commit section |

## Test counts

| Suite | Result |
|-------|--------|
| `hooks/target-scope` | 45 passed |
| `hooks/security-action` | 24 passed |
| **Combined (`pytest hooks/target-scope hooks/security-action -q`)** | **69 passed in ~5.5s** |
| Regression `hooks/file-scope hooks/ulysses` | 62 passed, 4 skipped (Windows-only drive-letter tests) |

## Verification commands run

```
export PATH="$HOME/.local/bin:$PATH"
python3 -m pytest hooks/target-scope hooks/security-action -q      # 69 passed
python3 -m pytest hooks/target-scope -q                            # 45 passed
python3 -m pytest hooks/security-action -q                         # 24 passed
python3 -m pytest hooks/file-scope hooks/ulysses -q                # 62 passed, 4 skipped
ruff --version                                                     # ruff 0.15.17
ruff check hooks/target-scope hooks/security-action                # All checks passed!
ruff format --check hooks/target-scope hooks/security-action       # 7 files already formatted
git status --porcelain -- hooks/file-scope hooks/ulysses           # (empty — untouched)
```

## Design notes (for reviewers)

- **Same family as file-scope / ulysses.** file-scope governs WHERE an agent writes (file_path);
  target-scope governs WHAT external targets a tool call may reach (host/URL/path arguments). Both
  are opt-in per scoped agent, fail-open when no sidecar applies, and exit 2 only on a real
  out-of-scope target — matching AGENTS.md §6 ("block only dangerous").
- **Target extraction is conservative.** URLs are picked up anywhere (`scheme://`), while bare
  hosts/paths are taken only from explicitly named keys — never guessed out of free-form command
  text — so the hook does not manufacture false blocks. A target is in-scope when ANY of its
  representations (full URL, host, host-without-port) matches ANY allow glob, so allowing a host
  covers every URL on it.
- **security-action is observe-only** (always exit 0); enforcement is target-scope's job. It reuses
  target-scope's pure `evaluate()` so the audit's allow/block label agrees with the enforcer, and
  degrades to `decision:"observe"` if target-scope is absent.
- **Redaction errs toward masking** (audit log must never become a secret sink): secret-shaped keys
  are masked wholesale and secret-shaped substrings (AWS/OpenAI/GitHub/Slack tokens, JWTs, PEM
  private keys, `key=value` secrets) are scrubbed from every string.

## Wire spec (PARENT registers this; this wave does NOT edit `hooks.json`)

Both are PreToolUse hooks. Suggested matcher (broad; each hook self-skips calls with no
host/URL/path arguments):

```
Event:   PreToolUse
Matcher: Bash|PowerShell|WebFetch|WebSearch|mcp__.*
Commands:
  python <hooks>/target-scope/check.py     # exit 0 allow | exit 2 block
  python <hooks>/security-action/audit.py  # exit 0 always (audit-only)
```

Register `target-scope/check.py` as its own PreToolUse entry (like `ulysses`/`tms` do) so its
exit-2 is honored; register `security-action/audit.py` as a separate always-exit-0 entry. Order is
not load-bearing (audit re-derives the verdict independently), but placing audit AFTER check keeps
the enforcement decision first.

## PARENT MERGE

- **No `.agents/agents.json` change required.** These are harness hooks, not skills — nothing to
  register in the skill catalog or parked companion. Provenance untouched.
- **`hooks.json` / settings registration is the parent's call** (see Wire spec). This wave did not
  edit any dispatcher/registry, per its path scope.
- **Test-count delta:** +69 (target-scope 45, security-action 24). No existing suite changed.

## Commit

- `3fe06dd2` — docs(W-rails): skeleton receipt (all UNKNOWN before measurement)
- `57b9abf4` — Add target-scope allowlist hook and security-action audit ledger (implementation)
- `101e9e60` — Apply ruff format to target-scope/security-action
- (this receipt) — docs(W-rails): rewrite with measured results

All commits are path-scoped to `hooks/target-scope`, `hooks/security-action`, and this receipt.
