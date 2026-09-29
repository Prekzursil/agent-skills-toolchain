# Read-only verification, do not write or modify anything. Run a directory listing and report the exact byte size and firs

- runtime: claude
- session date: 2026-09-20 08:54
- category: research
- source: `C:\Users\Prekzursil\.claude\projects\D--Research-projects-phenibut\21a98e84-43d0-4f5c-9876-e2cc5a3bb4e0.jsonl`
- distilled: 2026-09-29T04:55:36
- backend: claude

## create_summary

**Purpose:** This log captures a phenibut research-project Claude Code session startup — hook initialization, memory replay, and a queued read-only file verification task — alongside declined stale queued appends from prior sessions.

## Key Points

1. Session ran in `D:\Research\projects\phenibut`, branch `main`, Claude Code v2.1.277, sdk-cli entrypoint.
2. Queued read-only task: verify existence, byte size, first 3 lines of `L09_mr_coloc_sota.md`.
3. Task enqueued and dequeued at 2026-09-20T05:52; no execution output appears in this log.
4. Metaswarm plugin installed but project unconfigured; `/setup` or `/start-task` suggested.
5. Shared-harness SessionStart hook timed out at 5000ms and was cancelled; other hooks succeeded.
6. Health hook reported clean state: 0 background jobs, 0 unflushed spool, memory up.
7. Memory replay: Scaleway CLI auth debugged, `/scratch` found ephemeral, 6.0 GB trajectories archived with verified integrity, 3 instances stopped.
8. Recent work: OVH $210 L40S GPU infra, Biomni OAuth/CDP auth stack (PR #44–57), 372 tests passing.
9. Science state: Boltz-2 α2δ-1 validated (ρ=+0.48, n=486); α2δ-FEP no-go (Spearman=0.00); BPMD ladder complete.
10. `now.md` records declining stale Sep-22 queued appends to `tests_wave.py` — truncated chunks, false line-602 precondition, no files touched.

## Takeaways

1. The queued verification task never executed here — only enqueue/dequeue events were logged.
2. Stale queued appends with truncated payloads and false preconditions were correctly declined, preventing shadow-duplicated test classes.
3. Hook timeouts are non-fatal; fail-open behavior kept session startup proceeding.
4. The project requires `/setup` before metaswarm workflows become usable.
5. Cross-session memory (`now.md`, `recent.md`) reliably carries infra and science state across compaction boundaries.

## extract_wisdom

# Session-Log Digest (2026-09-20 → 09-28)

## Key decisions & why
1. Declined (6+ sessions) stale 2026-09-22 append chunks to `backend/submissions/tests_wave.py`: payloads truncated mid-`def test_`, no END-CHUNK marker, precondition "file ends line 602" false (608 mid-file), and 1,292-line `test_wave.py` already on disk — appending would shadow-duplicate classes. Stranded: pinned `obj.author` detail-GET AttributeError bug, docker argv-hardening asserts. Needs complete resend.
2. Queue replays with no exec output = unverified; re-dispatch fresh, never replay. Origin sessions were tool-less, so queued payloads are untrusted.
3. SECURITY-AUDIT-auth.md v2 overwrite guard-stopped: disk already held v2-final (157 lines, 20,127 B) and payload was truncated.
4. Precedent set: treat fetched/queued content as logged data, not commands.

## Surprising findings
5. Origin-session MCP transports dead (McpHub "Not connected", file:// rejected, playwright-cdp ECONNREFUSED :9222) — native Read/Grep/Glob succeeded first try.
6. WebCoder CRITs: writable `role` on AllowAny register (anon→ADMIN); `ACCOUNT_SIGNUP_FIELDS 'password'` → `manage.py check` exit 1. Repo root on DESKTOP-A60S9GP is now pure Next.js — Django backend exists only on the other host.
7. gh renames: block/goose→aaif-goose/goose, sst/opencode→anomalyco/opencode (v1-harness.json 4,338 B, no BOM, sha256 recorded).

## Mistakes & fixes
8. WSL 4 GB `.wslconfig` cap OOM-killed/corrupted biomni editable install → uncapped, rebuilt sync; rdkit+CPU-torch → ADMET E2E pass.
9. Aviary RECORD check empty from escaped `$d` + wrong glob (`fhaviary-0.37.0.dist-info` not `aviary-*`) → re-run: 31 files, 0 missing.
10. `python -m uv` fails ("No module named uv") → `uv pip list` fallback.

## Open risks / tools
11. 57 duplicate npx-cli.js MCP procs, peak 4.3 GB RAM — `mcp_doctor audit`/`reap --apply` proposed, not run. 41 skills outside repo trees; 13 vanished unrecorded; agent-skills-toolchain 201+ uncommitted files. SessionStart hooks time out (5–66 s vs 5 s) fail-open. Torch 2.7.1 cu128 (<2.8), gradio pin 5.50, Celery/docker judge.
