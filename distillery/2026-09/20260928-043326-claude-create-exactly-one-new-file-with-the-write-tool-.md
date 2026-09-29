# Create exactly ONE new file with the Write tool: C:\Users\Prekzursil\Documents\GitHub\WebCoder\backend\submissions\tests

- runtime: claude
- session date: 2026-09-22 19:52
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil-Documents-GitHub-WebCoder\ef83c6e7-8d11-40ff-915b-9675b3605f68.jsonl`
- distilled: 2026-09-28T04:33:26
- backend: claude

## create_summary

**Purpose:** A queued 2026-09-22 instruction (chunk 1 of 3) directs verbatim creation of a Django coverage-extension test file for the WebCoder `submissions` app.

**Key points:**

1. Target: `backend/submissions/tests_wave.py`, WebCoder repo, branch `wave/nextjs-migration`; chunk 1 of 3, exact text.
2. Strict constraints: no reformatting, one file only, no git commands; report line count and last verbatim line.
3. Content: imports, verdict constants, ORM factory helpers, `_FakeProcess`, model and serializer test classes.
4. Header pins known defect: `IsOwnerOrAdminForSubmission` checks `obj.author`; `Submission` field is `user` → AttributeError.
5. Conventions: eager Celery via `apply`, sandbox mocked at `submissions.tasks`, real `compare_outputs`, external temp dirs.
6. Memory shows chunks 2/3 and 3/3 later declined: truncated mid-line at `def test_`, no END-CHUNK.
7. On-disk reality (2026-09-28): `tests_wave.py` absent; `test_wave.py` (1,292 lines) already contains ExecutionTests plus later classes.
8. Precondition "file ends at line 602" false — line 608 is mid-file; appending would shadow-duplicate classes.
9. Original 2026-09-22 session ran tool-less: McpHub children disconnected, `file://` rejected, playwright-cdp ECONNREFUSED :9222.
10. Sibling queued read-only tasks (rvc grep, 6-section extraction) dequeued but never executed — outcomes unverified.

**Takeaways:**

1. Chunked verbatim delivery without complete END-CHUNK markers yields invalid Python; decline incomplete chunks pending resend.
2. Stale queue preconditions must be re-verified against on-disk state before executing anything.
3. Near-identical filenames (`tests_wave.py` vs `test_wave.py`) make append targets ambiguous — verify the exact path.
4. A session whose tools (MCP, file://, CDP) never connected cannot have executed queued work; treat as unverified.
5. Decline stale queue items with recorded reasons and loop closure; never silently drop or blindly replay.

## extract_wisdom

## Session Digest — WebCoder queue replays & tests_wave.py saga

**Key decisions**
1. Declined all three stale queued chunks (2026-09-22) for `backend/submissions/tests_wave.py`: chunk 1/3 would create the file fresh, but chunks 2/3 and 3/3 were truncated mid-line (`def test_…`) with no `END-CHUNK` marker — verbatim append would yield invalid Python.
2. Chunks 2/3+3/3 also failed their precondition: on-disk `test_wave.py` was already 1,292 lines containing the same `ExecutionTests`/`CheckerTests` classes; appending would shadow-duplicate. Loop closed; advised complete resend.
3. Chunked file writes use BEGIN-CHUNK/END-CHUNK fencing, exact-content, single-file, no git — markers are the integrity check.

**Surprising findings**
4. Pinned defect: `users.permissions.IsOwnerOrAdminForSubmission` checks `obj.author`, but `Submission` has only `user` — detail-endpoint GET raises AttributeError; pinned by test, not fixed.
5. Queue replays log enqueue/dequeue with zero execution output — "dequeued" ≠ "done"; outcomes stayed unverified across multiple sessions.
6. Transport stack failed wholesale on 2026-09-22 (McpHub "Not connected", `file://` rejected, cursor-bridge dead, playwright-cdp ECONNREFUSED :9222); native Read/Grep worked first try on 09-28.

**Mistakes and fixes**
7. Asking a digest session for verbatim multi-line dumps (67 keyword lines from `pvc_edit_page.txt`) collides with the 300-word digest contract — fix: re-dispatch extraction to a tool-bearing session.
8. Escaped `$d` and wrong dist-info glob (`aviary-*` vs `fhaviary-0.37.0.dist-info`) broke a RECORD manifest check; re-run closed both (31 files, 0 missing).

**Dependencies/tools**
9. Django tests: eager Celery via `task.apply`, sandbox helpers mocked at `submissions.tasks`, `compare_outputs` real, temp dirs via `tempfile`.
10. Repo: WebCoder, branch `wave/nextjs-migration`.
