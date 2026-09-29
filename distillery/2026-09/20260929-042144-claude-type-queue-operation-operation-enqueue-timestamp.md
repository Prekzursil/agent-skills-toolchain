# {"type":"queue-operation","operation":"enqueue","timestamp":"2026-09-22T15:02:46.623Z","sessionId":"86b9d1a8-40b5-4757-b

- runtime: claude
- session date: 2026-09-28 05:42
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Windows-System32\0d85fc0a-6852-455c-ba21-7ac84df9e8c3.jsonl`
- distilled: 2026-09-29T04:21:44
- backend: claude

## create_summary

**Purpose:** A two-part read-only security audit of WebCoder's Django backend and Next.js frontend auth/CORS/secrets (branch `wave/nextjs-migration`, commit `40fda968`), plus later handling of stale queued work.

## Key points

1. Audit scope: `settings.py`, `requirements.txt`, `AuthContext.tsx`, `manage.py check`, auth URL wiring.
2. PART A writes `docs/SECURITY-AUDIT-auth.md` skeleton verbatim; skipped entirely if file already exists.
3. Hard rules: no git writes, no edits beyond PART A file, no pip/builds/servers, searches depth ≤ 4.
4. A-01 CRITICAL: `DEBUG = True` hardcoded at settings.py:37, not env-driven.
5. A-02/A-03 HIGH: empty `ALLOWED_HOSTS`; access and refresh JWTs persisted in localStorage (XSS-stealable).
6. A-04/A-05/A-06 HIGH: GitHub OAuth over-scope (`repo`, `read:org`); no refresh rotation/blacklist; logout client-side only.
7. MEDIUM/LOW: optional email verification, AllowAny default permissions, duplicate `DJ_REST_AUTH` blocks, `console.log` of user data.
8. Positives: fail-loud env reads for SECRET_KEY/DB_PASSWORD, gitignored `.env`, narrow explicit CORS origin list.
9. PART B evidence: `manage.py check` with process-local dummy secrets, full `urls.py`, users app files, frontend Authorization/Bearer grep.
10. Follow-up session declined three stale queued `tests_wave.py` append chunks (truncated mid-line, no END-CHUNK); no files touched.

## Takeaways

1. Django checks run read-only with process-local dummy env vars — values never persisted.
2. localStorage JWT storage plus missing rotation/blacklist are the highest-impact auth risks found.
3. Skeleton reports mark UNKNOWN sections so unmeasured verdicts cannot be cited as fact.
4. Truncated queued append chunks without END-CHUNK markers must be blocked, not force-applied.
5. Stale queued operations require validation against current file state — target may already contain the content.

## extract_wisdom

# Session Digest — WebCoder Auth Security Audit (2026-09-22, dequeued 2026-09-28 — STALE)

## Key decisions
1. Audit split: PART A writes one skeleton file (`docs/SECURITY-AUDIT-auth.md`) verbatim; PART B gathers read-only evidence only. Hard bans: git writes, extra edits, installs, unscoped search (depth ≤ 4).
2. Skeleton carries a self-invalidation guard: if still all-UNKNOWN, the unit died before measuring and "no verdict may be cited."
3. `manage.py check` retry plan: process-local dummy `SECRET_KEY`/`DB_PASSWORD` env vars — never persisted, never written to files.

## Surprising findings (measured, file:line anchored)
4. 13 findings, top: `DEBUG=True` hardcoded (settings.py:37), `ALLOWED_HOSTS=[]` (:39), access+refresh JWTs in `localStorage` (AuthContext.tsx:17-18), GitHub OAuth over-scoped to `repo`+`read:org` (:215-220), refresh-token rotation/blacklist configured-but-inert (:256-266), logout client-side only.
5. Positives: SECRET_KEY/DB_PASSWORD are fail-loud env reads; CORS is a narrow explicit list; `.env` gitignored; blacklist app installed but never triggered.
6. `DJ_REST_AUTH` dict defined twice (settings.py:202-204 dead vs 269-273 live).

## Mistakes and fixes
7. First `manage.py check` failed: `KeyError: SECRET_KEY` — `backend/.env` absent on the auditing machine. Fix: process-local dummy env (pending execution when queue stalled).
8. Stale-queue pattern (from this session's memory): Sep-22 queued chunks to `tests_wave.py` were truncated mid-line (`def test_`), no END-CHUNK marker, and target files had moved on (1,292 lines, content already present). Declined rather than applied — appending would produce invalid Python or shadow-duplicate classes. Rule formed: verify target-file state before applying any queued write.

## Dependencies/tools
9. Django + dj-rest-auth + djangorestframework-simplejwt (token_blacklist) + django-allauth (GitHub OAuth) + Celery (`filesystem://` broker); React/Next.js frontend, axios; branch `wave/nextjs-migration`, commit `40fda968`.

## Open loop
10. PART B evidence (urls.py, users app, frontend API client) never executed — audit remains SKELETON v1; treat all findings as unmeasured if UNKNOWNs persist. Check queue for more Sep-22 chunks.
