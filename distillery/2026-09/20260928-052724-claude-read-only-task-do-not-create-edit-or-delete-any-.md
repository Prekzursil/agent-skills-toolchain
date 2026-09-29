# READ-ONLY task. Do NOT create, edit, or delete ANY file. Do NOT run git commands. Scoped reads only. Print the FULL verb

- runtime: claude
- session date: 2026-09-22 19:25
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil-Documents-GitHub-WebCoder\6e5bafaf-8829-43fa-90be-6ca43db48d0f.jsonl`
- distilled: 2026-09-28T05:27:24
- backend: claude

## create_summary

# Session Digest: WebCoder Security Audit

**Purpose:** Read-only security audit and code recon of the WebCoder Django backend (commit 40fda968, branch wave/nextjs-migration) to produce a findings report and prep the Next.js port.

## Key Points

1. Read-only audit of WebCoder backend; no source files edited, no git commands run.
2. settings.py reads SECRET_KEY and DB_PASSWORD from environment; no hardcoded secrets.
3. `manage.py check` exits 1: ACCOUNT_SIGNUP_FIELDS uses `password` not `password1` (A-19).
4. AuthContext.tsx stores JWT access/refresh tokens in localStorage; no refresh/logout calls.
5. Pins: Django 5.2.1, DRF 3.16.0, simplejwt 5.5.0, cors-headers 4.9.0, celery 5.5.3.
6. Wrote docs/SECURITY-AUDIT-auth.md v2: 20 findings (A-01..A-20), 19 patches P0–P3.
7. Critical: role mass-assignment via register endpoint (A-14); verdict NOT production-ready.
8. Also flagged: DEBUG=True, empty ALLOWED_HOSTS, GitHub OAuth `repo` scope, no JWT blacklist.
9. Submissions perms live in users.permissions.IsOwnerOrAdminForSubmission; judging via Celery judge_submission_task.
10. Later stale queued chunks appending tests_wave.py declined: truncated payloads, false preconditions.

## Takeaways

1. Auth stack is not production-ready; fix A-14 (role mass-assignment) and A-19 (check failure) first.
2. Next.js port must move JWTs out of localStorage and add refresh/blacklist server routes.
3. backend/.env is missing (only .env.example), so local `manage.py` checks cannot run.
4. Submissions tests are a single 238-line file; any tests_wave.py append duplicates existing test_wave.py coverage.
5. Declining unverifiable truncated queue payloads prevented writing invalid Python — resend complete chunks before retry.

## extract_wisdom

# WebCoder session digest — 2026-09-22, branch `wave/nextjs-migration`, audit @ `40fda968`

**Decisions**
1. Evidence-first, strictly read-only security audit before the Next.js port; output `docs/SECURITY-AUDIT-auth.md` v2 (20 findings A-01..A-20, 19 patches P0→P3), verdict NOT prod-ready.
2. Keep settings fail-loud: `SECRET_KEY`/`DB_PASSWORD` via `os.environ`, zero hardcoded secrets — pattern to preserve in the port.
3. Test baseline = SQLite via `webcoder_api/test_settings.py` (`pytest --nomigrations --cov`); Postgres not needed for tests.

**Surprising findings**
4. `manage.py check` exits 1: allauth `ACCOUNT_SIGNUP_FIELDS` uses `password`, not `password1` (A-19, CRITICAL).
5. Role mass-assignment via the register endpoint (A-14, CRITICAL).
6. Auth posture: JWT in localStorage, no rotation/blacklist route, client-only logout, GitHub OAuth `repo` scope, `DEBUG=True`, empty `ALLOWED_HOSTS`.
7. `submissions` has no `permissions.py` — perms live in `users.permissions.IsOwnerOrAdminForSubmission`; judging = Celery `judge_submission_task` over `judge_utils/` (compile/execute/compare/checkers).
8. `backend/.env` absent (only `.env.example`) — settings import `KeyError: SECRET_KEY`; manual creation blocked by read-only scope.

**Mistakes & fixes**
9. Check-failure fix: `password` → `password1` (10 `--deploy` warnings corroborate A-01/A-02).
10. Queued "print 4 files verbatim" job was served as read-only recon (dir listings, key files; models 116 / views 56 / serializers 77 / tests.py 238 lines). Later queued appends to `tests_wave.py` were declined: payloads truncated mid-`def test_`, no END-CHUNK markers, false "ends line 602" precondition, near-duplicate `test_wave.py` (1,292 L) already on disk — full resend required.

**Dependencies**
11. Django 5.2.1, DRF 3.16.0, simplejwt 5.5.0, cors-headers 4.9.0, dj-rest-auth 7.2.0, allauth 65.19.4, celery 5.5.3; no gunicorn/whitenoise — deploy gap for the port.
