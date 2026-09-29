# Run this single command and paste its complete raw stdout/stderr verbatim in a code block. Do not create, modify, or del

- runtime: claude
- session date: 2026-09-20 17:54
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\b1f030c2-bafa-4de5-b405-943dfb323387.jsonl`
- distilled: 2026-09-28T06:20:24
- backend: claude

## create_summary

**Purpose:** A Windows Claude Code session handled queued commands and hook/memory context around WSL science tooling (claude-science, Biomni) while repeatedly declining stale queued test-file appends.

**Key points**

1. Queued command (Sep 20) requested running `~/.local/bin/claude-science url` inside WSL Ubuntu, output verbatim.
2. SessionStart hooks timed out (17s vs 5s limit); plugin harness context dropped, then recovered via dispatch.
3. Ledger flagged 9 unresolved failures: WU-B audit traversal and terminal-critic unconditional-success block.
4. Metaswarm plugin active but project unconfigured; `/setup` or `/migrate` suggested, not run.
5. Stanford Biomni installed in WSL: mamba env (py3.11), A1 wired to GLM via `BIOMNI_SOURCE=Custom`.
6. E2E ibuprofen ADMET task passed after rdkit + CPU torch install (7 steps, RDKit-validated).
7. Overnight E1 setup job dispatched with resume wrapper; receipt and memory notes written.
8. zcode video-agent-kit plugin stayed `[disabled]` despite healthy server; blocked on user TUI-exit toggle.
9. Stale Sep-22 queued appends to `backend/submissions/tests_wave.py` declined across four sessions.
10. Decline reasons: truncated payloads, false line-602 precondition, file absent, near-duplicate `test_wave.py` exists.

**Takeaways**

1. Queued work must revalidate preconditions (paths, line counts, END-CHUNK markers) before applying.
2. Hook timeouts silently shed harness context; budget more than 5s for startup hooks.
3. Near-duplicate target filenames make blind verbatim appends a shadow-duplication risk.
4. One unflushed spool entry signals cross-session queue durability worth monitoring.
5. WSL daemons (claude-science :8000, Biomni :7860) need health checks before URL or status claims.

## extract_wisdom

## Session-log digest (2026-09-20 → 2026-09-28 fragments)

**Key decisions and why**
1. Biomni (Stanford, WSL2) install: background `mamba env create` died with a WSL exit → rebuilt synchronously; bg WSL package installs deemed unreliable.
2. A1 agent routed to the GLM coding plan via `BIOMNI_SOURCE=Custom` (ChatOpenAI, key via `.env`) instead of a paid API.
3. Stale 2026-09-22 queued chunks targeting `backend/submissions/tests_wave.py` declined across 4 sessions (52ca59f8, 8cc6c763, 87fbc27d, 6e884ad3): payloads truncated mid-`def test_`, no END-CHUNK markers, "file ends line 602" precondition false, and near-identical `test_wave.py` (1,292 lines) already holds ExecutionTests → append would shadow-duplicate. Pending complete resend.

**Mistakes and fixes**
4. E2E ibuprofen ADMET run failed `No module named 'rdkit'` (+ wrong interpreter) → installed rdkit + CPU torch → passed (7 steps, 84% PPB, Lipinski-pass).
5. Original 09-22 session was tool-less (MCP/file:///CDP dead), so its queued work was never verifiable — check the queue for other stale Sep-22 chunks.

**Surprising findings**
6. SessionStart hooks time out at 5 s while actually running 17–23 s; one dispatch logs both `hook_cancelled` and `hook_success`; a 59.8 KB memory replay got persisted to file with only a 2 KB preview.
7. zcode video-agent-kit stays `[disabled]` despite a healthy server (37 tools, full handshake); watcher logged zero file writes — blocked on a clean TUI-exit toggle.
8. 9 unresolved ledger failures open; 2026-09-28 spool still shows 1 unflushed item.

**Tools/dependencies**
9. Biomni stack: Miniforge/mamba, py3.11.16, langchain/gradio, rdkit, CPU torch; launchers `~/bin/biomni`, `~/bin/biomni-web`; E1 setup log `~/e1-setup.log` (PID 29408; full E1 >10 h, ≥30 GB, datalake ~11 GB); receipt in `D:\Research\tools\biomni-local\`.
10. Open loops close via `python ~/.claude/hooks/open-loops/add.py --close <id>`; Metaswarm npm+plugin double-install awaiting `/migrate`.
