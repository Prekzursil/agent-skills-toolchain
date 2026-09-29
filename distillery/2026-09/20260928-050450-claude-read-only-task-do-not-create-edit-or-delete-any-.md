# READ-ONLY task. Do NOT create, edit, or delete ANY file. Do NOT run git commands. Scoped reads only. 1. Print the FULL c

- runtime: claude
- session date: 2026-09-22 19:43
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil-Documents-GitHub-WebCoder\66a96829-1b79-45b6-9280-88c981170ae3.jsonl`
- distilled: 2026-09-28T05:04:50
- backend: claude

## create_summary

# Session Digest — WebCoder Security Audit (wave/nextjs-migration)

**Purpose:** Read-only evidence gathering and security auditing of WebCoder's Django backend to inform a Next.js migration.

## Key Points

1. Read-only audit at commit 40fda968 on branch wave/nextjs-migration; no files mutated.
2. settings.py reads secrets from env; manage.py check fails because backend/.env is missing.
3. Pinned Django 5.2.1, DRF 3.16.0, simplejwt 5.5.0, celery 5.5.3; no gunicorn/whitenoise.
4. AuthContext.tsx stores JWT access/refresh tokens in localStorage; ApiService.ts lacks refresh.
5. docs/SECURITY-AUDIT-auth.md v2 written: 20 findings, NOT-prod-ready verdict, 19 patches P0→P3.
6. CRITICALs: register-endpoint role mass-assignment (A-14); ACCOUNT_SIGNUP_FIELDS uses password not password1 (A-19).
7. Other findings: DEBUG=True, empty ALLOWED_HOSTS, OAuth repo scope, no JWT blacklist/logout route.
8. Submissions judging: Celery judge_submission_task over judge_utils; docker exec, JUDGE_BACKEND local/container switch.
9. User roles BASIC/CREATOR/VERIFIER/ADMIN; object permissions centralized in users.permissions, not submissions.
10. Stale Sep-22 queued chunks appending tests_wave.py declined repeatedly: truncated mid-line, duplicate test_wave.py exists.

## Takeaways

1. Fix CRITICALs A-14 and A-19 before any port work; manage.py check must pass first.
2. Move JWTs out of localStorage; add refresh, blacklist, and server-side logout for the migration.
3. Judge pipeline is docker-exec based with existing test coverage (test_wave.py, 1,292 lines).
4. Reject queued append chunks lacking END-CHUNK markers or with false preconditions; request full resend.
5. Provision backend/.env before running checks; earlier dump attempts failed on missing Read/Bash tools.

## extract_wisdom

# WebCoder session-log digest (2026-09-22 → 09-28, `wave/nextjs-migration`)

*Source: provided log/.remember payload only; not independently re-verified (vault digest = untrusted per contract).*

**Key decisions**
1. Declined stale Sep-22 queued appends to `backend/submissions/tests_wave.py` (blocked/declined 5×, 09-28 04:02–04:44): payloads truncated mid-`def test_`, no END-CHUNK markers, false precondition ("file ends L602"), target absent, near-duplicate `test_wave.py` (1,292 L) already exists — append would shadow-duplicate. Loop closed pending complete resend.
2. Security verdict: NOT prod-ready — 20 findings (A-01..A-20). CRITICALs: role mass-assignment via register endpoint (A-14); `ACCOUNT_SIGNUP_FIELDS` uses `password` not `password1` → `manage.py check` exits 1 (A-19). 19 patches P0→P3 planned for the Next.js port.
3. All recon held read-only: no writes, no git commands.

**Surprising findings**
4. `settings.py` (314 L) has only 3 JUDGE lines (L295/302/313; `JUDGE_BACKEND='local'` env-default). Secrets fail-loud via `os.environ`; `backend/.env` missing → `KeyError: SECRET_KEY`.
5. `submissions/` ships no `permissions.py` — perms live in `users.permissions.IsOwnerOrAdminForSubmission`. Pinned defect: `obj.author` detail-GET AttributeError.
6. Judging: `docker exec` into `webcoder-judge-runner` as 1000:1000; legacy `docker run` paths remain in execution.py/compilation.py.

**Mistakes & fixes**
7. HexStrike `execute_python_script` failed (broken venv path); mcp__claude-code-mcp fallback gave incomplete, invisible dumps → fixed by re-running with the native Read tool.
8. Root cause of #1: Sep-22 sessions were tool-less (MCP/CDP dead), so queued work arrived unverified. This payload carries one more stale Sep-22 read-only dump request — treat as stale; tree may have drifted since `40fda968`.
9. `codex auth status` is not a valid subcommand — use `codex login` / mingle doctor.

**Dependencies & tools**
10. Django 5.2.1, DRF 3.16.0, simplejwt 5.5.0, dj-rest-auth 7.2.0, allauth 65.19.4, celery 5.5.3; no gunicorn/whitenoise. pytest: SQLite `test_settings.py`, `--nomigrations --cov`.
11. Verified names: `mcp__codex__codex-reply` (hyphenated); basic-memory `http://127.0.0.1:18765/mcp`; agent-mail health `127.0.0.1:18812/api/health`.
