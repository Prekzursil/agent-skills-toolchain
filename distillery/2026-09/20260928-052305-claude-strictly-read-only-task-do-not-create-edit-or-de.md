# STRICTLY READ-ONLY task. Do NOT create, edit, or delete ANY file. Do NOT run ANY git command. Only read files and print 

- runtime: claude
- session date: 2026-09-22 19:34
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil-Documents-GitHub-WebCoder\9678d377-b84d-47b8-8e5f-a7963058bb59.jsonl`
- distilled: 2026-09-28T05:23:05
- backend: claude

## create_summary

# Session Digest — WebCoder Read-Only Evidence Dump

**Purpose:** Execute a strictly read-only queued task dumping WebCoder backend files verbatim to support the ongoing security audit on branch `wave/nextjs-migration`.

## Key Points

1. Task demanded verbatim, no-truncation dumps of `users/models.py`, `users/serializers.py`, `problems/models.py` with line counts.
2. Required grep of `settings.py` for "JUDGE" lines, prefixed with 1-based line numbers.
3. Required `users/admin.py` check: line count, User registration presence, full contents if under 60 lines.
4. Explicit constraints: no file creation/editing/deletion, no git commands.
5. Part of WebCoder security audit at commit `40fda968`; prior work produced `docs/SECURITY-AUDIT-auth.md` v2 (20 findings, A-01..A-20).
6. Critical findings already logged: role mass-assignment via register endpoint (A-14); failing `manage.py check` from `ACCOUNT_SIGNUP_FIELDS` using `password` not `password1` (A-19).
7. `manage.py check`/`--deploy` exit 1; `backend/.env` missing, only `.env.example` present.
8. Earlier recon covered submissions app, `judge_utils/` (backend/comparison/compilation/execution/checkers), users permissions, OAuth urls.
9. User model roles: BASIC/CREATOR/VERIFIER/ADMIN, default BASIC; JWT tokens in localStorage, no refresh/blacklist/logout routes.
10. Settings read `SECRET_KEY`/`DB_PASSWORD` from env, fail-loud; no hardcoded secrets found.

## Takeaways

- Audit verdict stands: NOT production-ready; 19 patches (P0→P3) proposed for the Next.js port.
- Evidence collection uses verbatim dumps plus line counts and SHA-256 checks for parent-session verification.
- Stale Sep-22 queued chunks were later declined across sessions — payloads truncated mid-line, no end-markers; complete resend pending.
- Read-only guard held throughout: no writes, no git operations during evidence gathering.
- Next.js migration planning is the downstream consumer of this audit evidence.

## extract_wisdom

# Digest — WebCoder session log (9678d377, `wave/nextjs-migration`)

**Provenance:** built from the dequeued queue-op + SessionStart hook/.remember replay only. Repo untouched. The dequeued task (verbatim dump of `users/models.py`, `users/serializers.py`, `problems/models.py`, settings.py "JUDGE" grep, `users/admin.py`) is a stale 2026-09-22 replay; not re-executed — this agent is digest-only, and the .remember log shows its substance was already captured 2026-09-22 (users/models.py printed; settings.py audited) and consumed by the security audit.

1. **Decisions**
   - Wrote `docs/SECURITY-AUDIT-auth.md` v2 at commit 40fda968: 20 findings (A-01..A-20), verdict NOT prod-ready, 19 patches P0–P3 for the Next.js port. CRITICALs: role mass-assignment via register endpoint (A-14); `manage.py check` broken (A-19).
   - Declined stale `tests_wave.py` append chunks (1/3–3/3) across 5 sessions. Why: payloads truncated mid-`def test_`, no END-CHUNK markers, false precondition ("file ends line 602" — actually 608, mid-file), and near-identical `test_wave.py` (1,292 L) already exists → verbatim append = invalid Python + shadow-duplicates. Loop closed pending full resend.

2. **Surprising findings**
   - `manage.py check` fails before running: KeyError SECRET_KEY — `backend/.env` absent (only `.env.example`).
   - Allauth `ACCOUNT_SIGNUP_FIELDS` uses `password`, not `password1` — CRITICAL.
   - JWT access+refresh in localStorage; `ApiService.ts` has no token refresh; no logout/blacklist route.
   - Shared-harness SessionStart hook timed out (5,130 ms > 5,000 ms) and was cancelled.

3. **Mistakes → fixes**
   - Originating Sep-22 session had dead MCP/file tools → queued work unverified; later sessions now verify preconditions before executing replays.
   - execution.py (211 L) infers TLE/MLE/RE from `/usr/bin/time` hacks on legacy `docker run` — hardening tests queued.

4. **Stack / tools**
   - Django 5.2.1, DRF 3.16.0, simplejwt 5.5.0, cors-headers 4.9.0, dj-rest-auth 7.2.0, allauth 65.19.4, celery 5.5.3; no gunicorn/whitenoise.
   - Judge: `JUDGE_BACKEND=local|container` switch (judge_utils/backend.py, 143 L) → `docker exec` webcoder-judge-runner as 1000:1000; comparison modes EXACT/STRIP_EXACT/LINES_STRIP_EXACT/FLOAT_PRECISE; g++/javac; custom checkers.
   - Roles BASIC/CREATOR/VERIFIER/ADMIN (default BASIC); perms centralized in `users.permissions`; pytest `--nomigrations --cov`, SQLite test settings.
