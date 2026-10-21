---
name: biomni-local
description: Use to bring up, diagnose, or run Stanford Biomni locally - the agentic bio toolchain (A1 agent on the GLM coding plan, 41-package R stack, 181 CLI bioinformatics tools, 14GB data lake) as a WSL2 gradio daemon on 127.0.0.1:7860. Triggers - biomni, bm verbs, agent bio task, plink2/bwa/homer/genomics/DESeq2/xcms work, :7860 down, biomni crash, data lake questions. Covers the bm verbs, bare A1() asserts, the pins (gradio<6, langgraph 1.2.x), lake at ~/Biomni/data.
license: MIT
---

# Biomni (local) — one-command control via `bm`

> Stanford's **Biomni** agentic bio toolchain, installed fully local in WSL2 Ubuntu:
> A1 agent (LLM = **glm-5.3-flash on the Z.AI Coding Plan** — cheap credits; switch
> `BIOMNI_LLM` in `~/Biomni/.env` to `glm-5.3` for harder reasoning), the **E1 stack**
> (41 R packages: DESeq2, dada2, xcms, WGCNA, lme4, flow suite…; 181 CLI tools:
> plink2, bwa, iqtree2, muscle, gcta64, FastTree, full HOMER+hg38), and a **14 GB
> data lake**. The web UI is a gradio daemon on **http://127.0.0.1:7860/**. The `bm`
> dispatcher (`~/.local/bin/bm.ps1`, the `cs` pattern) makes it one command from any
> Windows shell.

## When to use

- "Run a bio agent task" / "GWAS QC with plink2" / "differential expression with DESeq2"
- "Biomni is down/slow", "`:7860` won't load", before any tool or agent calls the daemon
- You need genomics/flow-cytometry/comp-bio tools without agent overhead

## The `bm` verbs (any Windows shell; slash command `/biomni`)

| Verb | What it does |
|---|---|
| **`bm open`** | ensure up (readiness-poll) + open the UI. The human one-click. |
| **`bm ensure`** | headless ensure-up → `SUCCESS:bm-up` / `FAILED:bm-down`. **Call before any :7860 request.** |
| **`bm status [-Json]`** | state + measured latency + `*** WEDGED ***` flag (≥4s). |
| **`bm fix`** | graceful recover: stop → clear stale state → restart → wait HEALTHY. |
| **`bm stop`** | stop the daemon. |
| **`bm task "<prompt>"`** | full A1 agent task (plans, runs tools, self-corrects). Result printed + saved to `D:\Research\tools\biomni-local\tasks\`. Bills plan credits. |
| **`bm tool <cmd> [args]`** | any E1 CLI tool directly: `bm tool plink2 --version`, `bm tool bwa index ref.fa` |
| **`bm r '<R code>'`** | R one-liner in the env: `bm r 'library(DESeq2); cat("ok")'` |
| **`bm doctor`** | PASS/WARN/FAIL/NOT-CHECKED across the whole stack (daemon, env, lake, R, CLI, pins, watchdog, RAM). Exits non-zero on FAIL. |

## Facts that flip diagnoses

1. **Slow ≠ down.** A ≥4s-answering daemon is **WEDGED** (WSL frozen under host-RAM
   pressure) — `bm fix` recovers. Host RAM < 3 GB is the known trigger on this box.
2. **Bare `A1()` CRASHES.** `a1.py:197` asserts `base_url must be provided` — biomni's
   config loads `.env` into its own object, NOT `os.environ`. Always construct
   canonically (this is what `bm task` does):
   ```python
   from dotenv import load_dotenv; load_dotenv("/home/prekzursil/Biomni/.env")
   agent = A1(path="~/Biomni/data", llm=os.environ["BIOMNI_LLM"], source="Custom",
              base_url=os.environ["BIOMNI_CUSTOM_BASE_URL"],
              api_key=os.environ["BIOMNI_CUSTOM_API_KEY"])
   ```
3. **The lake lives at `~/Biomni/data`** (14 GB, `biomni_data/{benchmark,data_lake}`).
   `~/biomni-data` is a **symlink** to it — every entrypoint resolves to one copy.
   Never re-download; `bm doctor` verifies the lake + marker.
4. **Version pins are load-bearing**: `gradio>=5.0,<6.0` (6.x broke `Chatbot(type=)`)
   and `langgraph 1.2.x` (a gradio install once dragged langgraph to 0.3.x and
   broke langchain 1.4). `bm doctor` rows both.
5. **A `.env` banner prints the API key in cleartext** on gradio startup — treat that
   scrollback accordingly; never paste it further. (NEVER-ROTATE: lifecycle is the owner's.)

## Architecture (what keeps it healthy)

- **Daemon**: `python biomni_web.py` in WSL (gradio, :7860), launched by `~/bin/biomni-web`
  or `bm-start`; log `~/biomni-web.log`.
- **Watchdog**: Scheduled Task `BiominiStackGuard` → `bm-watchdog.ps1` (heartbeat +
  recover-log in `%LOCALAPPDATA%`; auto-recovers a down/wedged daemon every cycle).
- **Health model**: HTTP 200 < 4s = HEALTHY; ≥4s = WEDGED; refused = DOWN.
- **`bm doctor` is the gate**: NOT-CHECKED is not PASS; exit code propagates.

## Claude Science integration (the two workbenches)

Both are WSL daemons with the same control pattern — use them together:
- **cs** (`/claude-science`, :8000) = compchem/life-science workbench (molecular
  modeling, docking-adjacent compute).
- **bm** (`/biomni`, :7860) = agentic bio toolchain (genomics, flow, pharmacology
  data, bioinformatics CLI/R).
- Chain them: e.g. FAERS/target hypothesis → `bm task` for genomics/pharmacology
  context → hand structures/hypotheses to cs for compchem. The MCP fleet
  (schrodinger, qdx_rush, rdkit, openmm) is the third leg for molecular work.

Receipts: `D:\Research\tools\biomni-local\` (install, E1 repair, acceptance transcript).
Related: [[zai-lane-c-plan-entitled-asr-tts-everywhere]] (the plan the LLM bills).
