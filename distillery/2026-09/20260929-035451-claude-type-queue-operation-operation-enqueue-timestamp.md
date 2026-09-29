# {"type":"queue-operation","operation":"enqueue","timestamp":"2026-09-20T16:49:45.381Z","sessionId":"9360f6b8-2273-436f-b

- runtime: claude
- session date: 2026-09-28 06:14
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Windows-System32\44fd3e4b-a14e-4ede-8583-2d28443df648.jsonl`
- distilled: 2026-09-29T03:54:52
- backend: claude

## create_summary

## Session Digest

**Purpose:** Install and validate Stanford Biomni locally in WSL, wire its A1 agent to the GLM plan, and kick off the full E1 toolchain as an overnight job.

### Key Points

1. Verified genuine Stanford `biomni` pip package; cloned snap-stanford/Biomni into WSL.
2. Installed Miniforge/mamba; background `mamba env create` died, rebuilt synchronously.
3. `biomni_e1` env ready: Python 3.11.16, langchain, gradio; Biomni built from source.
4. A1 wired to GLM plan via `BIOMNI_SOURCE=Custom` (ChatOpenAI); key moved to `.env`.
5. E2E ibuprofen ADMET task ran glm-5.3-flash ReAct loop fully end-to-end.
6. Failed on `No module named 'rdkit'`; installed rdkit plus CPU torch; task passed.
7. Result: 7 steps, RDKit-validated pharmacology — 84% PPB, Lipinski-pass.
8. Built launchers `~/bin/biomni` and `~/bin/biomni-web`.
9. Wrote install receipt to `D:\Research\tools\biomni-local`; saved memory `project_biomni_local_install`.
10. Full E1 approved: overnight `setup.sh` (NON_INTERACTIVE=1, PID 29408, log, resume wrapper); Windows PATH leak fixed.

### Takeaways

1. Background mamba env creation is unreliable under WSL exits; synchronous rebuild recovered faster than retrying.
2. Missing native dependencies (rdkit) only surface at E2E execution — pre-install them before validating agents.
3. Credential handoff via temp file → `.env` avoids leaking keys into shell history or logs.
4. Long jobs need `NON_INTERACTIVE=1`, a log file, and a resume wrapper so overnight runs survive interruption.
5. Queued file-append chunks must be checked for truncation and staleness before applying — incomplete payloads yield invalid Python.

## extract_wisdom

**Session digest — sessions 9360f6b8 (2026-09-20), cb3700e6 (2026-09-28/29)**

**Decisions and rationale**
1. Biomni (`snap-stanford/Biomni`, installed from source) runs in WSL2 Ubuntu under conda env `biomni_e1` (py3.11.16, langchain/gradio) — rebuilt synchronously after background `mamba env create` died on a WSL exit; bg env builds across WSL restarts deemed unreliable.
2. LLM backend = GLM via `BIOMNI_SOURCE=Custom` (Custom→ChatOpenAI; key staged temp file → `.env`) — rides the existing plan, no new provider.
3. Full E1 tool install (>10 h, ≥30 GB, ~11 GB datalake) pushed to an overnight `NON_INTERACTIVE=1` job (PID 29408, log `~/e1-setup.log`, resume wrapper `~/bin/biomni-e1-resume`) instead of interactive.
4. Declined stale Sep-22 queued appends (chunks 2/3, 3/3) to `backend/submissions/tests_wave.py`: payloads truncated mid-line at `def test_`, no END-CHUNK marker; target file absent while real `test_wave.py` (1,292 lines) already contains those classes; "ends at line 602" precondition false (608, mid-file). Appending would shadow-duplicate.

**Surprising findings**
1. E2E ibuprofen-ADMET run failed only on `No module named 'rdkit'` (+ wrong interpreter, watchdog bugs); installing rdkit + CPU torch → 7-step ReAct pass (84% PPB, Lipinski-pass).
2. zcode video-agent-kit plugin stayed `[disabled]` despite a healthy server (37 tools, full handshake); watcher logged zero file writes — blocked on user's clean TUI-exit toggle.
3. SessionStart hook output hit 64 KB (persisted to file); local hook dispatch timed out (39 s > 35 s cap).
4. Queue held week-old chunks; a one-command WSL env-probe (uname/python/uv/df/free) was dequeued 43 ms after enqueue with no recorded result.

**Mistakes → fixes**
1. bg env create died → synchronous rebuild. 2. Missing rdkit/CPU-torch → install, task passed. 3. Windows PATH leaked into WSL job → fixed in-job.

**Artifacts/dependencies:** `~/bin/biomni`, `~/bin/biomni-web`; receipt `D:\Research\tools\biomni-local\RECEIPT-biomni-install_2026-09-20.md`; memory `project_biomni_local_install`; metaswarm npm→marketplace migration still pending.
