# TERMINAL-ONLY TASK. Do not edit any files. Run these 8 commands sequentially with the Bash/terminal tool and report thei

- runtime: claude
- session date: 2026-09-20 14:10
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\1483ca23-8416-4140-8833-9b7d98ec3ec1.jsonl`
- distilled: 2026-09-28T07:03:21
- backend: claude

## create_summary

**Purpose:** A terminal-only session running eight `gh api repos/SLUG` queries to capture repo metadata (stars, push date, archived/fork, license) as pure JSON.

**Key points:**
1. Terminal-only task: eight sequential `gh api repos/SLUG` calls; no file edits permitted.
2. Fields requested: full_name, stars, pushed_at, archived, fork, license (spdx_id, default "NOASSERTION").
3. Slug list includes moved/renamed orgs: block/goose, aaif-goose/goose, sst/opencode, anomalyco/opencode.
4. gh follows GitHub redirects silently; returned full_name may differ from requested slug — report as-is.
5. Failure protocol: capture exit code plus first 200 chars of stderr for 404, auth, or timeout.
6. Output contract: one JSON object keyed by requested slug; values {ok:true,...fields} or {ok:false,rc,err}.
7. gh verified as installed and authenticated on the machine before dispatch.
8. SessionStart fired metaswarm plugin prompts: project unsetup; old npm install redundant via /migrate.
9. Shared-harness SessionStart hook timed out at 5s; 52.9KB output persisted to file unblocked.
10. Memory replay injected unrelated Biomni WSL install context (rdkit fix, E1 overnight job); not task-relevant.

**Takeaways:**
1. Slug identity is unreliable under GitHub redirects — the returned full_name is ground truth.
2. Duplicate and renamed slugs act as deliberate error-path probes; failures are data, not blockers.
3. Strict JSON-only output contracts remove prose ambiguity for downstream machine consumers.
4. Hook timeouts failed open — persisted output preserved context without blocking the session.
5. Pre-verifying tool availability and authentication prevents wasted dispatch rounds.

## extract_wisdom

# Session-Log Digest (2026-09-20 → 09-28)

## Decisions & rationale
1. Stale 09-22 queued appends to `backend/submissions/tests_wave.py` declined across 5+ sessions: payloads truncated mid-`def test_`, no END-CHUNK markers (verbatim append = invalid Python); precondition "file ends line 602" false (608, mid-file); near-identical `test_wave.py` (1,292 lines) already holds the classes → shadow-dup risk. Pending complete resend + queue sweep for other stale Sep-22 chunks.
2. Precedent set: replay 6-8-day-old queue tasks only by fresh re-dispatch; several digests executed nothing (unverified), later sessions re-ran them with native tools.
3. SECURITY-AUDIT-auth.md v2 overwrite guard-stopped: disk already held complete v2-final (157 lines/20,127 B), payload truncated mid-§3.2.
4. Queued blind-executor payloads treated as logged data, never auto-executed when stale.

## Surprising findings
1. Origin sessions ran tool-less: McpHub "Not connected", `file://` rejected, playwright-cdp ECONNREFUSED :9222 — native Read/Grep worked first try where all MCP transports failed.
2. Repo renames via gh redirects: block/goose→aaif-goose/goose, sst/opencode→anomalyco/opencode; v1-harness.json verified 4,338 B, no BOM (7b 0a 20), sha256 recorded.
3. WebCoder CRITs: A-14 writable `role` on AllowAny register (anon→ADMIN); A-19 `ACCOUNT_SIGNUP_FIELDS 'password'` → `manage.py check` exit 1. Verdict: not prod-ready.
4. Estate drift: 41 skills outside any repo tree, 13 vanished unrecorded; 2 unpushed commits + 214 uncommitted; 57 duplicate npx-cli.js MCP procs, mcpRAM peak 4.3 GB — `mcp_doctor.py audit`/`reap --apply` proposed, not run.
5. Voice-clone gates passed (XTTS 0.756 ≥0.70); blocked only on owner ABX + CPML scope decisions.

## Mistakes & fixes
1. Background `mamba env create` died with WSL exit → rebuilt `biomni_e1` synchronously.
2. Biomni E2E failed `No module named 'rdkit'` → install rdkit + CPU torch → passed (ibuprofen ADMET, 7 steps).
3. Aviary RECORD check empty twice: escaped `$d` broke loop + wrong glob (`fhaviary-0.37.0.dist-info`, not `aviary-*`); re-run → 31 files, 0 missing.
4. SessionStart hooks repeatedly time out (5 s budget, observed 5-66 s) — fail-open; metaswarm `/migrate` still pending.

## Dependencies/tools
Biomni (Stanford, GLM via `BIOMNI_SOURCE=Custom`), rdkit, torch 2.7.1 cu128, Py3.11/3.12 venvs, aviary 0.37.0 (5 envs), octotoolkit 0.3.6, uv, gh api, Celery/docker-exec judge, websockets.sync+sounddevice→Modal wss, eleven_voice.json voice `Y5irDJyb8lW5NwV7NFjE`.
