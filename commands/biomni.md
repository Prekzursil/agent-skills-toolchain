---
description: Control the local Biomni stack (bm dispatcher) - open, ensure, status,
  fix, doctor, task, tool, r
permalink: dqverify-repo-20261013/commands/biomni
---

# /biomni — local Biomni control

Dispatch to the `bm` dispatcher (`~/.local/bin/bm.ps1`, the `cs` pattern). Argument: `$ARGUMENTS` (default: `status`).

Route the arguments to the matching verb, run it via PowerShell, and report the output faithfully:

- `open` — ensure up + open the web UI (http://127.0.0.1:7860) for the human
- `ensure` — headless precondition check; proceed only on `SUCCESS:bm-up`
- `status` — state + latency + wedged flag (`*** WEDGED ***` = recover needed)
- `fix` — graceful force-recover (stop → clear locks → restart → readiness-wait)
- `doctor` — full-stack PASS/WARN/FAIL/NOT-CHECKED report; treat FAIL as blocking, NOT-CHECKED as unverified (not green)
- `task "<prompt>"` — run an A1 agent task on the GLM plan; result printed + saved under `D:\Research\tools\biomni-local\tasks\`
- `tool <cmd> [args]` — any E1 CLI tool (plink2, bwa, iqtree2, muscle, gcta64, FastTree, HOMER suite)
- `r '<R code>'` — R one-liner in the biomni_e1 env (DESeq2, lme4, WGCNA, xcms, ...)

Invocation: `powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\.local\bin\bm.ps1" <verb> [args]`

Facts that flip diagnoses (same class as cs):
- A slow (>=4s) but answering UI is **WEDGED, not down** — run `bm fix`.
- `HTTP 000`/connection refused with WSL up = daemon down — `bm fix` starts it.
- Agent tasks bill GLM coding-plan credits (glm-5.3-flash by default).
- The data lake (14 GB) lives at `~/Biomni/data`; `~/biomni-data` is a symlink to it — never re-download.