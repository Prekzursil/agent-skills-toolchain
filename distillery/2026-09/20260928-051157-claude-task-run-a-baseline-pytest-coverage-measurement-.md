# Task: run a baseline pytest coverage measurement. Do NOT create, edit, or delete any source file. Do NOT run git command

- runtime: claude
- session date: 2026-09-22 19:38
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil-Documents-GitHub-WebCoder\8ded6b01-c8ff-4328-a121-145d688f6426.jsonl`
- distilled: 2026-09-28T05:11:57
- backend: claude

## create_summary

## Session Digest — WebCoder baseline coverage task (queued 2026-09-22)

**Purpose:** Execute a queued, strictly read-only baseline pytest coverage measurement of the Django `submissions` app (WebCoder, branch `wave/nextjs-migration`) and report exact, unsummarized results.

### Key Points

1. Queued task: run baseline pytest coverage; no file creation, edits, deletion, or git commands.
2. Command: venv python with `SECRET_KEY`/`DB_PASSWORD` env, pytest `submissions` under test settings, `--cov-branch`, `term-missing`.
3. Single run, no parallelism — machine under RAM pressure; up to 15 minutes allowed.
4. Report must include pytest summary line, every `submissions*` coverage row with Missing column, TOTAL row.
5. Warnings/errors verbatim; tracebacks truncated to last 30 lines; exact numbers only.
6. Branch `wave/nextjs-migration` @ `40fda968`; prior sessions produced 20-finding audit in `docs/SECURITY-AUDIT-auth.md`.
7. Audit CRITICALs: role mass-assignment via register endpoint (A-14); `ACCOUNT_SIGNUP_FIELDS` uses `password` not `password1` (A-19).
8. `manage.py check` exits 1 (KeyError `SECRET_KEY`; `backend/.env` absent); verdict: not production-ready.
9. Wire-check hook flagged six added-but-unreferenced test classes plus `BranchArcResolver` as dead code.
10. Stale Sep-22 append chunks for `tests_wave.py` declined: truncated mid-line, false "file ends line 602" precondition, near-identical `test_wave.py` (1,292 lines) already exists.

### Takeaways

1. Coverage baselines demand exact table rows; "do not summarize away numbers" is a binding contract.
2. Read-only discipline held: running the suite was the sole sanctioned action; no git, no edits.
3. Queued payloads without END-CHUNK markers or with false preconditions must be fully resent, never salvaged via append.
4. Pre-write verification (actual file length, existing similar files) prevents shadow-duplicated test classes.
5. Security debt (JWT in localStorage, no blacklist/refresh, mass-assignment) blocks production; P0–P3 patches queued for Next.js port.

## extract_wisdom

## Session digest — WebCoder (`wave/nextjs-migration`), logs 2026-09-22 → 09-28

**Key decisions and why**

1. Security audit written to `docs/SECURITY-AUDIT-auth.md` (20 findings A-01..A-20, 19 patches P0–P3) at commit `40fda968`; verdict NOT prod-ready — grounded in `manage.py check`/`--deploy` both exiting 1.
2. Read-only discipline for recon: no file edits, no git commands, hash-verified writes only.
3. Stale queued appends to `backend/submissions/tests_wave.py` declined across 5 sessions (09-28, 04:02–04:44); loop closed pending complete chunk resend.

**Surprising findings**

4. `manage.py check` CRITICAL: `ACCOUNT_SIGNUP_FIELDS` uses `password` not `password1` (A-19); KeyError `SECRET_KEY` — `backend/.env` missing (only `.env.example`).
5. Role mass-assignment via register endpoint (A-14); roles BASIC/CREATOR/VERIFIER/ADMIN, default BASIC.
6. Existing `test_wave.py` (1,292 lines) already holds ExecutionTests/CheckerTests — the queued `tests_wave.py` would shadow-duplicate.
7. wire-check hook: newly added test classes (`BuildCommandTests`, `RunJudgedProcessLocalTests`, …) referenced 0× — dead or unwired.

**Mistakes and fixes**

8. Queued chunks truncated mid-line at `def test_`, no END-CHUNK markers → verbatim append = invalid Python; fixed by declining, not patching.
9. Precondition "file ends line 602" was false (608, mid-file) → verify on-disk state before applying queued edits.
10. Origin 09-22 session was tool-less (MCP/CDP dead) → queued payloads unverified; treat such work as untrusted until resent.

**Dependencies/tools**

11. Django 5.2.1, DRF 3.16.0, simplejwt 5.5.0, cors-headers 4.9.0, dj-rest-auth 7.2.0, allauth 65.19.4, celery 5.5.3; no gunicorn/whitenoise.
12. Queued pytest baseline: `--ds webcoder_api.test_settings --cov-branch --cov-report=term-missing`, env `SECRET_KEY`/`DB_PASSWORD`, single run (RAM pressure); `pytest.ini` pins `webcoder_api.settings` + `--nomigrations`.
