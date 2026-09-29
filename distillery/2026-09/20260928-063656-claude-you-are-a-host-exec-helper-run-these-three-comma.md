# You are a host-exec helper. Run these three commands on this Windows box and report their outputs verbatim. Do NOT modif

- runtime: claude
- session date: 2026-09-20 17:51
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\3d990e52-e059-433a-8861-e92e1054bd06.jsonl`
- distilled: 2026-09-28T06:36:56
- backend: claude

## create_summary

**Purpose:** A Windows host-exec helper session (2026-09-20/28) bootstraps to execute three queued claude-science/MCP diagnostics while session-start hooks inject health, memory, and stale-queue context.

**Key points:**

1. Queued task requests three verbatim diagnostics: `claude-science url`, curl MCP initialize probe on 127.0.0.1:7870, sqlite `custom_mcp_servers` baseline.
2. Resource guard flags 1.3GB free RAM; 57 duplicate npx-cli.js copies consume ~1560MB.
3. Proposed remedy: run mcp_doctor audit, then `reap --apply` to cut MCP process duplication.
4. Event ledger shows 9 unresolved failures open, including WU-B audit and terminal-critic blocks.
5. Metaswarm installed but unconfigured; `/migrate` suggested to purge redundant npm-era framework copies.
6. Shared SessionStart hook timed out (13.6s vs 5s limit); other startup hooks completed successfully.
7. Memory: Stanford Biomni installed in WSL (biomni_e1, py3.11.16); ibuprofen ADMET E2E passed after rdkit fix.
8. Stale 2026-09-22 queued append chunks targeting `tests_wave.py` were blocked or declined across five sessions.
9. Decline reasons: truncated payloads, missing END-CHUNK markers, false line-602 precondition, duplicate `test_wave.py` exists.
10. Chunks held ExecutionTests/SubmissionViewTests mocking `subprocess.Popen` for judge verdicts and docker argv checks.

**Takeaways:**

1. Queued host-exec work must return verbatim output with explicit SUCCESS/FAILED markers per task section.
2. MCP process duplication, not agents, dominates RAM pressure; audit-then-reap is the standing remedy.
3. Never apply stale queue chunks with truncated payloads or invalidated preconditions — decline and request resend.
4. Close ledger failure loops explicitly (`milestone --supersedes`) instead of silently re-walking them.
5. Hook timeouts fail open; sessions continue with partial startup context (one unflushed spool noted).

## extract_wisdom

# Digest — sessions 2026-09-20 → 09-28 (3d990e52 et al.)

**Key decisions**
1. Stale queued ops are declined, never blind-applied: 2026-09-22 chunks appending `backend/submissions/tests_wave.py` were blocked/declined across 5+ sessions (52ca59f8, 8cc6c763, 87fbc27d, 6e884ad3) — payloads truncated mid-`def test_`, no END-CHUNK markers, precondition "file ends line 602" false (608 is mid-file), target file absent, and existing `test_wave.py` (1,292 lines) already holds the classes, so append would shadow-duplicate.
2. Biomni WSL install rebuilt synchronously after background `mamba env create` died on a WSL exit — bg overnight WSL jobs judged unreliable that day.
3. A "host-exec helper" probe was enqueued→dequeued 131 ms apart (09-20 14:33): claude-science login URL, FastMCP handshake on `127.0.0.1:7870/mcp`, sqlite baseline on `~/.claude-science/operon-cli.db`. Delivery is logged; no execution result appears in this excerpt.

**Surprising findings**
4. Resource guard: RAM 1.3 GB free (<4); 57 duplicate npx-cli.js processes (24× mcp-proxy.mjs, 15× cli.js, 12× semgrep), MCP RAM ≈1,560 MB, excess=169 → `mcp_doctor.py audit` + `reap --apply` proposed, not run.
5. Shared SessionStart hook timed out (13.6 s vs 5 s cap) and was cancelled — fail-open held.
6. zcode video-agent-kit stayed `[disabled]` despite a healthy server (37 tools, full handshake); watcher logged zero file writes — blocked on user's clean TUI exit.
7. 9 ledger failures still open (WU-B audit traversal; WU-B terminal critic blocking unconditional success).

**Mistakes & fixes**
8. Biomni E2E failed `No module named 'rdkit'` (+ wrong interpreter, watchdog) → installed rdkit + CPU torch → ibuprofen ADMET passed (7 steps, 84% PPB, Lipinski-pass).
9. Origin 09-22 session was tool-less (MCP/file:///CDP dead) — queued work was unverified at source.

**Dependencies/tools**: WSL Ubuntu, Miniforge/mamba (py3.11.16), GLM via `BIOMNI_SOURCE=Custom`, gradio, FastMCP :7870, operon-cli.db, metaswarm (npm→plugin `/migrate` pending), superpowers, basic-memory.
