# {"type":"queue-operation","operation":"enqueue","timestamp":"2026-09-20T14:50:03.065Z","sessionId":"4305aae5-6be6-4ebc-b

- runtime: claude
- session date: 2026-09-28 06:25
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Windows-System32\8965a72c-ec2e-410c-a52b-7b8b856813f0.jsonl`
- distilled: 2026-09-29T03:45:46
- backend: claude

## create_summary

## Purpose

This log captures Claude Code session 4305aae5 (sdk-cli v2.1.277) whose startup was dominated by slow, mostly-timing-out hooks while a queued verbatim diagnostic probe arrived for immediate execution.

## Key Points

1. Queued probe (2026-09-20): run octotoolkit version check; list uv/python processes; verbatim raw output only.
2. Task enqueued and dequeued within 18ms; an outer re-enqueue arrived eight days later (2026-09-28).
3. Four SessionStart hooks timed out and were cancelled: TUI reminder, lifecycle hook, shared harness, local dispatch.
4. Local-hooks dispatch alone consumed 35.4s before cancellation; total startup hook overhead exceeded 100 seconds.
5. Metaswarm hook succeeded (18s): project unconfigured; recommends /setup, /start-task, and /migrate for npm duplicates.
6. Superpowers skill injected (25s), mandating skill invocation before any response, including clarifying questions.
7. Memory replay persisted at 59.8KB; 2KB preview covers Biomni WSL install history and receipts.
8. Biomni milestone: biomni_e1 env (py3.11.16), rdkit fix, ibuprofen ADMET task passed, launchers built.
9. Biomni agent rides GLM plan via BIOMNI_SOURCE=Custom; receipt written to D:\Research\tools\biomni-local.
10. zcode video-agent-kit plugin stays disabled despite healthy 37-tool server; blocked on user TUI-exit toggle.

## Takeaways

1. Hook timeouts dominated startup — trim, parallelize, or raise the 5s/35s budgets.
2. Queued tasks can age for days; validate staleness before executing old payloads.
3. Persisted-output previews keep large memory replays from flooding the context window.
4. Dual metaswarm installs (npm plus plugin) need the /migrate cleanup to deduplicate framework files.
5. Verbatim-output contracts (labeled fenced blocks plus exit codes) keep probe results auditable.

## extract_wisdom

## Session Log Digest

### Key decisions
1. Declined stale queued appends (chunks 2/3, 3/3 → `backend/submissions/tests_wave.py`): payloads truncated mid-line at `def test_`, no END-CHUNK marker; real `test_wave.py` (1,292 lines) already contained the content — appending would yield invalid Python and shadow-duplicate classes.
2. Biomni LLM rides GLM plan via `BIOMNI_SOURCE=Custom` (Custom=ChatOpenAI, key temp file → `.env`) — avoids dedicated API key.
3. Rebuilt `biomni_e1` env synchronously after background `mamba env create` died with a WSL exit.

### Surprising findings
1. SessionStart hooks routinely time out yet fail open: local-TUI reminder 12.6s vs 5s cap; node lifecycle hook 12.6s; "Local hooks dispatch" 35.4s vs 35s cap — session proceeds anyway.
2. Queued probe tasks can sit ~8 days (enqueued 2026-09-20, dequeued 2026-09-28) — queued workloads need staleness/precondition checks before execution.
3. zcode video-agent-kit plugin stayed `[disabled]` despite healthy pristine server (37 tools, full handshake); watcher logged zero file writes — blocked on user clean TUI-exit toggle.

### Mistakes and fixes
1. Biomni E2E ibuprofen ADMET task failed `No module named 'rdkit'` (+ wrong interpreter) → installed rdkit + CPU torch → passed (7 steps, RDKit-validated: 84% PPB, Lipinski-pass).
2. Full E1 tool envs are heavy (>10h, ≥30GB, datalake ~11GB first run) → deferred to overnight job rather than inline.

### Dependencies / tools
1. Biomni (snap-stanford/Biomni) in WSL2: Miniforge/mamba, py3.11.16, langchain/gradio, gradio daemon on 127.0.0.1:7860; launchers `~/bin/biomni`, `~/bin/biomni-web`; receipt in `D:\Research\tools\biomni-local\`.
2. octotools venv: `C:/Users/Prekzursil/.venvs/octotools`.
3. Metaswarm marketplace plugin active; old npm install redundant → run `/migrate` (safe, reversible).
