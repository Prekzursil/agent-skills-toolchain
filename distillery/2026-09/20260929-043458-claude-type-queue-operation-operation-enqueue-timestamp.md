# {"type":"queue-operation","operation":"enqueue","timestamp":"2026-09-22T16:36:39.339Z","sessionId":"8ded6b01-c8ff-4328-a

- runtime: claude
- session date: 2026-09-28 05:08
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Windows-System32\cdb6959e-315e-40b6-8961-435480ae5fd9.jsonl`
- distilled: 2026-09-29T04:34:58
- backend: claude

## create_summary

# Session Digest — WebCoder backend audit & stale queue triage

**Purpose:** Read-only security audit and pytest coverage baseline for the WebCoder Django backend, plus triage of stale queued test-file appends.

## Key Points

1. Queued task: baseline pytest coverage on `submissions` app; strictly read-only, no git commands, single run.
2. Two stale queued append chunks (2/3, 3/3) targeting `backend/submissions/tests_wave.py` were declined.
3. Both chunks truncated mid-line (`def test_…`) with no END-CHUNK marker; appending would yield invalid Python.
4. Target `tests_wave.py` never existed; actual `test_wave.py` (1,292 lines) already contains ExecutionTests.
5. Existing tests cover AC/RE/TLE/IE verdicts, docker argv/mount/network hardening, java11 classpath, `../evil.jar` traversal rejection.
6. Security audit doc `docs/SECURITY-AUDIT-auth.md` created with findings A-01..A-13 at commit 40fda968.
7. Findings: hardcoded `DEBUG=True`, empty `ALLOWED_HOSTS`, JWT tokens in localStorage, OAuth `repo` scope.
8. No JWT rotation/blacklist or logout route; `ApiService.ts` fetch-based, no token refresh.
9. `manage.py check`/`--deploy` exit 1: missing `.env`/SECRET_KEY; `ACCOUNT_SIGNUP_FIELDS` uses `password` not `password1`.
10. Wire-check flags six unreferenced additions: five test classes in tests.py plus `BranchArcResolver` in bytecode.py.

## Takeaways

1. Chunked appends require END-CHUNK markers; truncated payloads must be declined, never guessed.
2. Verify queue freshness before applying — target files evolve past stale preconditions.
3. Auth backlog: server-side logout, JWT blacklist/rotation, tokens moved out of localStorage.
4. Deploy blockers (SECRET_KEY env, signup fields, ALLOWED_HOSTS) need fixing before ship.
5. Wire-check-flagged dead code must be wired in, deleted, or confirmed as intentional API.

## extract_wisdom

## Session digest — WebCoder (`wave/nextjs-migration`), commit 40fda968

### Key decisions
1. Declined two stale queued appends to `backend/submissions/tests_wave.py` (chunks 2/3, 3/3, enqueued 2026-09-22): payloads truncated mid-line (`def test_…`) with no END-CHUNK marker; verbatim append would yield invalid Python or shadow-duplicate classes already present in the actual `test_wave.py` (1,292 lines). Loops closed; resend of complete chunks requested.
2. Baseline coverage task scoped read-only: no file edits, no git commands, single pytest run (no parallelism — RAM pressure), 15-min cap, dummy `SECRET_KEY`/`DB_PASSWORD` set inline, `--ds webcoder_api.test_settings --cov-branch --cov-report=term-missing`.
3. Audit stayed evidence-only: findings recorded in `docs/SECURITY-AUDIT-auth.md` (A-01..A-13 + B1-B5); manual `.env` creation blocked to preserve read-only discipline.

### Surprising findings
4. `manage.py check` exits 1 with `KeyError: 'SECRET_KEY'` — `backend/.env` missing (only `.env.example`); env vars must be injected for any Django command.
5. allauth CRITICAL: `ACCOUNT_SIGNUP_FIELDS` uses `password` not `password1`; 10 deploy issues (W018/W020) corroborate hardcoded `DEBUG=True` and empty `ALLOWED_HOSTS`.
6. Wire-check: five new test classes (BuildCommandTests, JudgeBackendSelectionTests, LegacyJudgeFlowUntouchedTests, RunJudgedProcessContainer/LocalTests) and `BranchArcResolver` (bytecode.py) referenced 0× — built, not wired; the hook's own `orphan-commit` referral is itself wired nowhere.
7. `urls.py` wires token/refresh/verify + dj-rest-auth/allauth/OAuth but no logout or JWT-blacklist route; `AuthContext.tsx` stores access/refresh tokens in localStorage.

### Mistakes and fixes
8. Queued chunks carried a false precondition ("file ends at line 602"; actual 608, mid-file) — fix: verify file state before applying queued ops.
9. Shared-harness SessionStart hook exceeded its 5 s budget (5,831 ms) and was cancelled — unresolved.

### Dependencies/tools
10. Django 5.2.1, DRF 3.16.0, simplejwt 5.5.0, cors-headers 4.9.0, dj-rest-auth 7.2.0, allauth 65.19.4, celery 5.5.3; no gunicorn/whitenoise; venv at `backend\venv\Scripts\python.exe`.
