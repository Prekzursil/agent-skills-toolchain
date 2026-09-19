# Scout brief — review of the HF Space `Prekzursil/qwen38-27b-heretic-chat`

You are one agent in a multi-agent engineering review. The owner asked: "analyze my HF Space and
suggest improvements". Read this brief fully before doing anything else.

## 1. What the Space is
A PRIVATE Gradio 6.26.0 Space (Python 3.12) on **ZeroGPU** (`zero-a10g` hardware flavour, PRO account),
serving `heretic-org/Qwen3.8-27B-heretic-ara` (27B, hybrid linear-attention + full-attention, VLM wrapper
class) quantized on the fly to bitsandbytes NF4, with a `Qwen/Qwen3.5-2B` draft model for speculative
decoding. It has: a ChatInterface with ~20 extra inputs, an in-Space agent tool loop (file bench, web
tools, memory/todo, optional python_eval), personas, an OpenAI-compatible `/v1/chat/completions` route
monkey-patched onto Gradio's FastAPI app, and `mcp_server=True`.

## 2. Where everything is (absolute paths)
SCRATCH = /tmp/claude-1000/-workspaces-agent-skills-toolchain/ca9aa7a4-16ad-4e9d-bafe-00eed0171063/scratchpad

- `SCRATCH/space-src/`  — git clone of the Space at HEAD `17dce0c` (full history, 31 commits). **Read-only snapshot.**
- `SCRATCH/meta/space_info.json` — HF API metadata: runtime stage, hardware, devMode, volumes, running sha, cardData.
- `SCRATCH/meta/live_runlog.txt` — fresh sample of the Space's runtime log stream (SSE `data: {json}` lines), captured 2026-09-18 ~23:45Z.
- `SCRATCH/meta/unittest_output.txt` — the Space's own unit tests run locally (Python 3.14): 61 tests, all pass.
- `SCRATCH/meta/live_*.json` — zero-GPU-cost probes of the live app, if present (the Space was mid-restart during scouting, so some may be missing or empty).
- `SCRATCH/libsrc/gradio/`, `SCRATCH/libsrc/spaces/`, `SCRATCH/libsrc/transformers/` — unpacked wheels of the EXACT pinned
  versions the Space runs: **gradio 6.26.0, spaces 0.51.3, transformers 5.16.1**. These post-date most training data:
  **never assert library behaviour from memory — open the source here and quote `path:line`.**
  Useful entry points: `libsrc/spaces/spaces/zero/{decorator,wrappers,client,gradio,config}.py`, `libsrc/spaces/spaces/zero/torch/{packing,bitsandbytes,aoti}.py`,
  `libsrc/transformers/transformers/models/qwen3_5/`, `libsrc/transformers/transformers/generation/` (utils.py, candidate_generator.py),
  `libsrc/transformers/transformers/cache_utils.py`, `libsrc/gradio/gradio/{chat_interface,helpers,utils,routes,mcp,blocks}.py`.

## 3. Hard rules
1. **Read-only review.** Never modify `SCRATCH/space-src`, never push, never open PRs/discussions. To experiment, copy
   files into `SCRATCH/work/<your-label>/` and work there.
2. **Do not touch the live Space or spend the owner's quota.** You have no token for it and must not look for one.
   No requests to `*.hf.space`. On the Hugging Face MCP connector you may use ONLY the read-only tools
   (`hf_fs` with ls/cat/find/search/stat, `hub_repo_search`, `hub_repo_details`). NEVER call `hf_jobs`, `dynamic_space`,
   `create_repo`, `hf_fs_write`, or any tool that writes, creates, launches or bills anything. Do not use any other
   connector (Gmail, Drive, Calendar, Canva, Figma, Supabase, Scite, …). WebSearch/WebFetch for public docs are fine.
3. Ignore `/workspaces/agent-skills-toolchain` (the cwd repo) and its CLAUDE.md — unrelated to this task. Do not read or edit it.
4. **Local repro is encouraged** for the pure-Python modules (`tool_parse`, `openai_protocol`, `openai_api`, `file_bench`,
   `web_tools`, `agent_tools`, `system_prompt`): write a small script under `SCRATCH/work/<label>/` that imports from a COPY of
   space-src and demonstrates the behaviour. `app.py` cannot be imported (it loads a 27B model at import time) — reason about it
   from source, or extract the pure function into a scratch file. No network calls to private/internal addresses; test SSRF
   guards by calling the guard functions directly. Never execute anything that needs a GPU.
5. **Scope: engineering only** — reliability, correctness, performance, cost/quota, security hardening, UX, tests,
   deployment hygiene, docs accuracy. **Out of scope:** anything whose purpose is to make the model or its personas better at
   evading the safety guardrails of this or any other AI system, or better at producing harmful content. Treat the persona
   text in `system_prompt.py` as opaque product copy: you may comment on engineering properties only (token cost, conflicts
   with the tool protocol, prompt-injection robustness, maintainability). Do not rewrite or "strengthen" persona directives.
6. Evidence standard: every finding cites `file:line` from space-src and quotes the relevant code. Claims about library or
   platform behaviour cite `libsrc/...:line` or a URL + quote. Say "inferred" when you could not verify. No padding:
   a finding you cannot make concrete is not a finding.

## 4. Facts ALREADY VERIFIED by the scout (build on them; do not re-report them as your own findings)
- F1 **Commit messages describe code that was never committed.** Commits `99ed760`→`17dce0c` claim "measured-rate estimator
  (9.2 tok/s)", "900s cap", "3600s", "4500s", "4h lease cap", "presets default to large GPU". In EVERY revision `app.py` has
  `TOK_PER_SEC = 22.0` and `DURATION_CAP = 600`, and the "Deep think" preset still sets `gpu_size="xlarge"`. Those commits only
  changed UI label strings and the max-tokens slider ceiling (now 262144). The clamp added in 99ed760 was removed two commits later.
- F2 **ZeroGPU `duration` is an up-front reservation checked against remaining quota** (`libsrc/spaces/spaces/zero/client.py`
  ~L138-207): errors "ZeroGPU illegal duration — requested GPU duration (Xs) is larger than the maximum allowed" and
  "quota exceeded (Xs requested vs. Ys left)"; `xlarge` doubles the requested amount; `PRO_QUOTA_MINUTES = 40`.
- F3 Runtime (space_info.json): `devMode: true`; running sha `1545500` ≠ repo HEAD `17dce0c`; two read-only model volumes
  mounted at `/models/...`; `gcTimeout` 172800 s; Space variables set `HF_HOME=/data/hf`, `HF_HUB_CACHE=/data/hf/hub`,
  `HF_HUB_ENABLE_HF_TRANSFER=1`; one Space secret exists named `HF_TOKEN` (so `HF_TOKEN` is in the app's process env).
- F4 **Boot takes ~4.5–5 min and the app restarts a lot** (live_runlog.txt): startup 23:23:31, restarts 23:28:41, 23:33:42,
  23:44:53. Target load = ~4m28s (on-the-fly NF4 quantization of 54 GB bf16 from the mounted volume), then draft, then
  "ZeroGPU tensors packing 22.3G". One restart came 6 s after "speculative draft loaded", i.e. ~5m01s after the previous
  restart; successful boots took 4m29s and 4m57s. Hypothesis (UNVERIFIED): a ~300 s startup watchdog in Dev Mode races the boot.
- F5 Log shows `flash-attn not installed in image; using sdpa`. No log line reports decode speed; "9.2 tok/s" comes only from a commit message.
- F6 The `maintenance/` scripts do not restart the Space: `watch.py` only observes; keepalive is a 12 h Windows scheduled
  task; dependency bump + redeploy is a weekly Windows scheduled task.
- F7 README says "55 tests"; there are 61. README says duration is "capped at 600 s" while the UI text advertises the
  full 262K context and "(up to 10 min lease)".
- F8 Secret scan of the full git history found no hard-coded tokens.

## 5. Output
Return exactly the structured object your prompt asks for. Be specific and terse; quote code; prefer fewer, well-proven
findings over many speculative ones. Put anything you did not get to in `coverage_notes` so gaps are visible.
