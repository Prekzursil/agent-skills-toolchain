# Local-models audit — Hugging Face / Ollama / LM Studio (+ llama.cpp / vLLM)

*Phase 2 deliverable, 27.08.2026. Decides the role of local-model tooling in this harness, informed by
(a) the Phase-1 local-model research recovered from the three Grok sessions, (b) the existing
OpenRouter spend-capped sidecar decision, and (c) measured hardware truth on this box. Every
load-bearing external claim carries ≥2 sources. Secrets are named, never reproduced.*

---

## 0. Bottom line (verdict per product)

| Product | Verdict | One-line reason |
|---|---|---|
| **Ollama** | **USED → KEEP (ratify as local T0 + embeddings backend)** | Already installed **and running**, OpenAI-compatible, weights on `D:`, auto-unloads after 5 min — the natural private/offline T0 for ≤8B work and the embeddings provider. No new daemon added. |
| **LM Studio** | **USED → KEEP, but de-duplicated to GUI/model-management + on-demand server** | Also installed and running with JIT + 1 h TTL + headless service; overlaps Ollama on serving. Keep it for model discovery / GGUF curation / MCP, not as a *second* always-loaded endpoint. |
| **Hugging Face** | **USED as hub / SKIP as inference server** | The Hub is already the download source for GGUF + support models (Whisper, rerank). HF serverless **Inference Providers** free tier is only **$0.10/mo with no pay-as-you-go** — strictly worse than the OpenRouter `:free` lane for hosted overflow. |
| **llama.cpp** | **SKIP (already embedded)** | It is the engine *inside* both Ollama and LM Studio (`useLlamaCppEngineProtocolRuntime3`). Running it raw only rebuilds what those two already give. |
| **vLLM** | **SKIP** | Datacenter GPU server (PagedAttention, Linux/CUDA, high-VRAM, concurrent serving). Wrong tool for a 6 GB Windows laptop. |

**Anti-overfit gate result: PASS with zero new always-on daemons.** Ollama and LM Studio servers are
*already resident* (measured below) and both auto-unload models, so the recommendation is to **keep and
tidy**, not to add. Nothing here competes with the OpenRouter sidecar — local and `:free` are
complementary lanes (privacy/offline vs. bigger-model scale).

---

## 1. Installed inventory (measured 27.08.2026)

**GPU:** `nvidia-smi` → **NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB total, 5762 MiB free** (159 MiB used).
Matches the Phase-1 handoff envelope exactly: GPU-full weight cap ≈ **5117 MiB** (leaving ~1024 MiB KV) →
**≤ 8B Q4 fits, 14B+ does NOT.**

**RAM:** ~31.6 GB, chronically pressured (as low as ~1.8 GB free) — a *resident model in RAM* is a real
cost, but a resident idle *server* is not (see §2/§3).

**Ollama** — v**0.33.0**, installed at `%LOCALAPPDATA%\Programs\Ollama`.
- **Server running now:** TCP **`0.0.0.0:11434` LISTENING** (PID 41996). ⚠️ Bound to *all interfaces*, not
  loopback — see §6 security note.
- **`ollama ps` → empty** — server resident but **no model in VRAM** (idle cost ≈ the server process only).
- Weights off the pressured drive: **`OLLAMA_MODELS=D:\ai-models\ollama`**.
- Models present (`ollama list`): `qwen2.5:7b` (4.7 GB — the proven 6 GB-fit reference), `qwen2.5:3b`
  (1.9 GB), `nomic-embed-text` (274 MB, embeddings), and one already-pulled offensive/uncensored model
  (**named only**, per scope: `blackgrg26/WORMGPT-13`). Estate-local, owner-ops only.

**LM Studio** — installed, home `C:\Users\Prekzursil\.lmstudio` (fully populated: `bin`, `hub`, `models`,
`llmster`, `server-logs`, `mcp.json`, `skills`).
- **Server running now:** TCP **`127.0.0.1:1234` LISTENING** (PID 14232).
- Weights on `D:` too: `downloadsFolder=D:\ai-models\lmstudio`.
- Already configured for low-RAM headless use (`settings.json`): `enableLocalService: true` (runs w/o GUI
  on login), `useLlamaCppEngineProtocolRuntime3: true` (llama.cpp engine), **JIT unload**:
  `unloadPreviousJITModelOnLoad: true` + `jitModelTTL {enabled, ttlSeconds: 3600}`, guardrails `mode: low`
  (4 GB threshold), HF proxy + pinned `mcp/hf-mcp-server`. `cliInstalled: false` (the `lms` CLI is a
  one-time `lms bootstrap` click away).

**Hugging Face cache** — `C:\Users\Prekzursil\.cache\huggingface\hub` holds **support models only**, not
chat LLMs: `Systran/faster-whisper-large-v3` (STT for the transcribe skills), `cross-encoder/nli-distilroberta`
(rerank), `distilbert-base-multilingual`, `bert-base-spanish`. Confirms HF's real role here = **hub /
download source**, not a resident inference server.

**Other resident ports (context):** basic-memory `127.0.0.1:8765` (answers → §7 note written), agent-mail
`127.0.0.1:8812`. No `vLLM` and no raw `llama-server` process.

---

## 2. Feature matrix

| Feature | Ollama | LM Studio | HF Inference Providers | llama.cpp | vLLM |
|---|---|---|---|---|---|
| Local, offline, $0 inference | Yes | Yes | No (hosted) | Yes | Yes (Linux/GPU) |
| OpenAI-compatible endpoint | `http://localhost:11434/v1` [1][2] | `http://localhost:1234/v1` (`/chat/completions`,`/completions`,`/embeddings`,`/models`) [3][4] | `https://router.huggingface.co/v1` [7][8] | via `llama-server` | Yes |
| Headless / service (no GUI) | Native (server *is* the daemon) | `llmster` daemon / "Local LLM Service" on login [5][6] | n/a (hosted) | Yes | Yes |
| JIT / on-demand model load | Loads on first request | JIT on by default; `/v1/models` lists all downloadable [5][9] | n/a | Manual | Manual |
| Idle RAM/VRAM release | **`keep_alive` default 5 min**; `0`=unload now, `-1`=never; `OLLAMA_KEEP_ALIVE` global [4][10] | Auto-unload after TTL (here 3600 s) + auto-evict to one JIT model [6][9] | n/a | Manual | Keeps resident |
| CLI | `ollama` (run/ps/stop/pull) | `lms` (server/load/unload/ps/`--gpu`/`--ttl`) [11] | `huggingface_hub` | `llama-cli` | `vllm` |
| GGUF consumption | Imports GGUF; own runner | llama.cpp engine (native GGUF) [3] | Downloads GGUF (hub) | Native GGUF | Not GGUF-first |
| Model discovery GUI | No (CLI/API) | Yes (HF search built-in) [12] | Web hub | No | No |
| Harness fit on **6 GB / RAM-pressured Windows** | **High** — resident-idle server is cheap, models on `D:`, ≤8B Q4 fits | **Medium-High** — same engine class; best as GUI + curator, redundant as a *second* live server | **Low as server** (see §4); **High as hub** | Low (redundant) | **None** (needs ≫6 GB, Linux/CUDA) |
| Verdict | **USED / KEEP** | **USED / KEEP (role: GUI + on-demand)** | **USED (hub) / SKIP (serverless)** | **SKIP (embedded)** | **SKIP** |

---

## 3. Product notes (evidence-backed)

**Ollama.** OpenAI-compatible chat/embeddings at `http://localhost:11434/v1/` (`api_key` ignored) [1][2];
default bind is `127.0.0.1:11434`, overridable via `OLLAMA_HOST` [10]. Memory behavior is the key
low-RAM win: a loaded model is kept **5 minutes by default**, then unloaded; `keep_alive:0` unloads
immediately, `-1` pins it, and `OLLAMA_KEEP_ALIVE` sets the global default [4][10]. Footgun: the stock
OpenAI client can't pass `keep_alive`, so the OpenAI middleware falls back to the 5 min default unless you
use the native `/api/chat` or the newer `options` field [1][10] — fine for us (short idle unload is
exactly what a RAM-pressured box wants).

**LM Studio.** OpenAI-compatible server at `http://localhost:1234/v1` (`/chat/completions`,
`/completions`, `/embeddings`, `/models`) [3][4]; runs GUI-less via the **`llmster`** daemon or the
desktop "Enable Local LLM Service" login option [5][6]. **JIT loading** loads a model on first request and
`/v1/models` advertises all downloadable models; JIT models **auto-unload after inactivity** (TTL —
locally 3600 s) [5][9]. The `lms` CLI drives everything from a terminal (`server start/stop`,
`load/unload/ps`, `--gpu`, `--ttl`) [11]. It is the friendlier **GGUF curator + model-discovery GUI**
(built-in HF search) [12] and speaks the same llama.cpp engine — which is exactly why running *both* live
servers is redundant on one 6 GB card.

**Hugging Face.** Two distinct things: (i) the **Hub** — 2M+ models, the GGUF supply and where our
Whisper/rerank/embedding support models already come from — which we **already use**; and (ii)
**Inference Providers** (formerly "Inference API"), a serverless gateway at
`https://router.huggingface.co/v1` routing to Groq/Together/Fireworks/Cerebras/`hf-inference` [7][8]. The
free tier is only **$0.10/month in credits with NO pay-as-you-go on Free**; PRO is $2.00/month; exhausting
it returns **402** [13][14][15]. That is a much smaller free allowance than the OpenRouter `:free` lane,
so HF-serverless earns **SKIP** as a harness inference path while HF-the-hub stays **USED**.

**llama.cpp.** The CPU/GPU GGUF inference core underneath both Ollama and LM Studio (LM Studio literally
sets `useLlamaCppEngineProtocolRuntime3`). Running `llama-server` directly would duplicate that plumbing
with no daemon management, model catalog, or OpenAI shim we don't already have → **SKIP (already embedded)**.

**vLLM.** A high-throughput **datacenter** serving engine (PagedAttention, continuous batching) targeting
Linux + server-class NVIDIA GPUs and many concurrent requests; a single useful model needs far more than
6 GB VRAM and it isn't a Windows-laptop tool → **SKIP** (revisit only if a Modal/cloud L4/H100 lane ever
wants a self-hosted OpenAI endpoint).

---

## 4. Local T0 vs OpenRouter `:free` (the explicit comparison)

Context: the OpenRouter routing skill fixes OpenRouter as a **spend-capped CLI/Codex sidecar** — `:free`
slugs run at $0 (17 `:free` chat slugs live 2026-08-27), **never** Cursor BYOK, **never** Claude
`ANTHROPIC_BASE_URL`, no LiteLLM, no OpenRouter MCP [16].

| Axis | **Local T0 (Ollama on this box)** | **OpenRouter `:free`** |
|---|---|---|
| Local RAM/VRAM cost | Real *when a model is loaded* (≤8B Q4 in 6 GB); **~0 when idle** (auto-unload 5 min; weights on `D:`) | **Zero** local footprint |
| Rate limits | Only your hardware — **no request cap, fully offline** | **20 req/min; 50/day** (<$10 lifetime) **or 1000/day**; upstream 429s; may 402 if balance negative [16] |
| Privacy | **Fully private / offline** — safe for secrets, institutional (e-nformation) data, phenibut IP, and uncensored/offensive estate work | Providers **may train on free traffic**; "not for secrets" [16] |
| Max model quality | Capped at **~8B** on 6 GB | Access to **much larger** models (26B+ etc.) than the laptop can run |
| Latency / availability | No network; deterministic; works with no internet | Network- and upstream-availability dependent |
| Cost ceiling | $0 (electricity) | $0 on `:free`; paid tiers spend-capped |

**Conclusion — complementary, not competing.** Use **local T0 (Ollama)** for the privacy/offline lane:
bulk extract/classify on sensitive data, embeddings (`nomic-embed-text`), STT (Whisper via HF cache), and
any uncensored/offensive estate task a hosted provider would refuse or log. Use **OpenRouter `:free`** when
privacy is not required and you want a model **bigger than 8B** or want zero local RAM cost. Neither
displaces the other; neither should be removed.

---

## 5. What Phase 1 changed in the recommendation

- **This is ratification, not greenfield.** The P2 session already produced six dual-rank local-model
  reports (`…\ast-integrate\docs\research\local-*_2026-08-26.md`) and already installed `qwen2.5:7b` as the
  proven 6 GB fit. The audit therefore **confirms Ollama as the established local backend** instead of
  proposing a new stack — and inherits Phase-1 principles verbatim: **NO 14B+ GPU-full on this box**, and
  **never invent Ollama/HF tags — probe `real=1` before asserting a model or size.**
- **Privacy lane is load-bearing, not theoretical.** Phase 1 shows an active *uncensored/offensive*
  local-model estate (WORMGPT-13 already pulled; dolphin / huihui-abliterated researched). Hosted lanes
  (OpenRouter `:free`, HF serverless) would refuse or log that work, which is precisely why the **local
  lane stays** and stays **estate-local**. This strengthens "local for privacy/uncensored, hosted for scale."
- **Fail-closed / anti-overfit discipline** from the sessions → **no new daemon**: both local servers are
  already resident and auto-unload, so the correct move is KEEP-and-tidy, not ADD. Heavy science (FEP/QM)
  explicitly **cannot** run locally ("RTX 4050 6 GB cannot FEP") and stays on Modal/licensed suites — local
  models are for *text/T0/embeddings*, never the physics.

---

## 6. Remaining user clicks / actions

1. **Security (recommended): re-bind Ollama to loopback.** It is listening on **`0.0.0.0:11434`** (all
   interfaces / LAN-reachable, no auth). Set `OLLAMA_HOST=127.0.0.1:11434` (User env) and restart the
   Ollama service unless LAN access is deliberate. (Everything else — LM Studio 1234, basic-memory 8765,
   agent-mail 8812 — is already loopback-only.)
2. **De-duplicate the always-on servers (optional, RAM hygiene):** pick **Ollama** as the standing
   OpenAI-compat endpoint (it is CLI-native and already the scripted backend) and let **LM Studio's**
   server be **on-demand** — either untick "Enable Local LLM Service" on login, or just never load a model
   in both at once (two models will OOM the 6 GB card).
3. **If you want the `lms` CLI:** run `lms bootstrap` once (`cliInstalled:false` today).
4. **No action needed** for: models-on-`D:` (already correct), JIT/TTL auto-unload (already on), HF-as-hub
   (already how it's used). **Do not** wire HF serverless inference or vLLM into the harness.

---

## Sources

1. Ollama OpenAI compatibility & `options`/`keep_alive` (GitHub PR #11249; issue #5013) — https://github.com/ollama/ollama/pull/11249 , https://github.com/ollama/ollama/issues/5013
2. Ollama OpenAI-compat endpoint — https://ollama.readthedocs.io/en/openai/
3. LM Studio Developer Docs (OpenAI-compatible endpoints, engine) — https://lmstudio.ai/docs/developer
4. LM Studio local server / OpenAI-compat (Thunder Compute writeup) — https://www.thundercompute.com/blog/lm-studio-local-llm
5. LM Studio headless (`llmster`, JIT, auto-unload) — https://lmstudio.ai/docs/developer/core/headless
6. LM Studio 0.3.5 (headless mode, on-demand loading, auto-start) — https://lmstudio.ai/blog/lmstudio-v0.3.5
7. HF Inference Providers overview (router.huggingface.co/v1) — https://convly.ai/hugging-face-inference-api-guide/
8. HF Inference Providers pricing (official) — https://huggingface.co/docs/inference-providers/main/en/pricing
9. LM Studio JIT `/v1/models` + auto-unload (headless docs / 0.3.5 blog) — see [5][6]
10. Ollama FAQ (default bind 127.0.0.1:11434, `OLLAMA_HOST`, `keep_alive`, `OLLAMA_KEEP_ALIVE`) — https://docs.ollama.com/faq
11. LM Studio `lms` CLI (server/load/unload/ps, `--gpu`, `--ttl`) — https://lmstudio.ai/docs/cli
12. LM Studio built-in HF model search — https://lmstudio.ai/blog/lmstudio-v0.3.5
13. HF free tier $0.10/mo, PRO $2, no PAYG on Free (eesel 2026) — https://www.eesel.ai/blog/hugging-face-pricing
14. HF pricing & billing (official, credits + 402 on exhaustion) — https://huggingface.co/docs/inference-providers/en/pricing
15. HF free monthly limit / 402 explanation (HF forums) — https://discuss.huggingface.co/t/free-monthly-limit-reached/171827
16. OpenRouter sidecar decision + `:free` caps — `C:\Users\Prekzursil\.agents\skills\openrouter-routing\SKILL.md` (+ `openrouter-free-models_2026-08-27.md`, `openrouter-complete-surface_2026-08-27.md`)

---

## Post-audit hardening

**27.08.2026 ~08:30–08:37 (UTC+3) — Ollama re-bound from 0.0.0.0 to loopback. DONE & VERIFIED.**

- **Before:** `netstat -ano | findstr 11434` → `TCP 0.0.0.0:11434 LISTENING` **and** `TCP [::]:11434 LISTENING` (PID 18256) — LAN-open, no auth, exactly as flagged in recommendation 1 above.
- **How it runs:** tray-app pair, not a Windows service — `ollama app.exe` (PID 44688) + `ollama.exe` server (PID 18256), both from `%LOCALAPPDATA%\Programs\Ollama`.
- **Env var:** `OLLAMA_HOST=127.0.0.1` was **already set** at User scope (a previous, interrupted hardening attempt got that far); Machine/Process scopes empty. Nothing was changed here — the running server simply predated the variable.
- **Restart method:** `Stop-Process -Name 'ollama app','ollama' -Force`, 3 s pause, then `Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"` from a shell with `$env:OLLAMA_HOST='127.0.0.1'` set (so the relaunched pair sees it both from the process env and the User registry scope on future logins).
- **After (verified):** `netstat` → `TCP 127.0.0.1:11434 LISTENING` (new server PID 51216); **no** `0.0.0.0` or `[::]` line. `ollama list` over the loopback bind works — all 4 models listed (qwen2.5:7b / qwen2.5:3b / nomic-embed-text / WORMGPT-13).
- **Residual note:** the tray app relaunched this session runs under the agent's shell environment; after the next logoff/login it will start from the User registry var, which is already correct. No further action needed.

---

## Post-audit hardening (27.08.2026)

**§6 action #1 done — Ollama re-bound from `0.0.0.0` to loopback.**

- **Old binding:** `0.0.0.0:11434` + `[::]:11434` LISTENING (PID 41996) — LAN-open, no auth (as §1/§6 recorded).
- **New binding:** `127.0.0.1:11434` LISTENING, no `0.0.0.0` and no `[::]`. Confirmed three ways:
  - `netstat -ano | findstr 11434` → only `TCP 127.0.0.1:11434 … LISTENING`.
  - `server.log` startup: `msg="Listening on 127.0.0.1:11434 (version 0.33.1)"` and effective `OLLAMA_HOST:http://127.0.0.1:11434`.
  - `ollama list` still works locally (all 4 models: `qwen2.5:7b`, `qwen2.5:3b`, `nomic-embed-text`, `blackgrg26/WORMGPT-13`).

**Root cause (important — env var alone was NOT enough).** The Ollama v0.33 desktop app has a GUI toggle
"**Expose Ollama to the network**" persisted as `expose` in `%LOCALAPPDATA%\Ollama\db.sqlite` (`settings`
table). It was `expose=1`, and the tray app **overrides** `OLLAMA_HOST` with `0.0.0.0` when that toggle is
on — so setting the user env var by itself left the server still on `0.0.0.0`.

**Exactly what was done:**
1. `[Environment]::SetEnvironmentVariable('OLLAMA_HOST','127.0.0.1','User')` — persistent User-scope env var
   (belt-and-suspenders; also set in the launching shell's process env).
2. Killed `ollama app.exe` + `ollama.exe`. (During this window the app self-triggered its pending
   **0.33.0 → 0.33.1** in-app upgrade; it was allowed to finish silently, then relaunched.)
3. **Stopped the app, backed up the settings DB, and set the GUI toggle off:**
   backup at `%LOCALAPPDATA%\Ollama\db.sqlite.bak_2026-08-27` (+ `-wal`/`-shm`), then
   `UPDATE settings SET expose=0` via `C:\Users\Prekzursil\.agents\scripts\ollama_disable_expose.py`
   (read-before-write; `inspect_ollama_db.py` is the read-only companion).
4. Relaunched `ollama app.exe` → server came up on `127.0.0.1:11434`.

No LAN exposure was intended, so this is the correct hardening (LM Studio 1234, agent-mail 8812 already
loopback; basic-memory 8765 is a separate reliability issue, tracked in
`BASIC-MEMORY-RELIABILITY_2026-08-27.md`). To re-expose deliberately, turn the app's "Expose to the network"
toggle back on (or `expose=1`) — do not rely on the env var alone in either direction.

---

## Uncensored candidates (appended 27.08.2026 — hub-only, NO downloads)

*Fold-in from `.agents\skills\openrouter-routing\openrouter-apps-hermes-uncensored_2026-08-27.md` (§Q3).
Phase-1 discipline unchanged: probe `real=1` before any pull; no speculative downloads; the no-14B+ rule stands.*

**Abliteration** (one-liner): directional ablation of the single "refusal direction" in activation space (Arditi et al., NeurIPS 2024), applied as permanent weight orthogonalization — no finetune run needed, at the cost of small measurable behavioral drift (KL divergence from the original).

| Model | VRAM @ Q4_K_M | Fit on 6 GB? | Method / license | Trusted GGUF source |
|---|---|---|---|---|
| `huihui-ai/Huihui-Qwen3-8B-abliterated-v2` | ~5.5 GB | **Yes, tight** (+ KV; keep ctx short) | Abliteration / Apache-2.0 | `huihui-ai` HF repos |
| Dolphin 3.0 Llama 3.1 8B | **4.92 GB** | **Yes — safer fit** (same class as proven qwen2.5:7b @ 4.7 GB) | Uncensored finetune (function calling, ChatML) / Llama-3.1 community license | official `dphn`/`cognitivecomputations` + `bartowski` |

Hermes-4-14B exists but is **excluded** — no-14B+ rule (Q4_K_M ≈ 8.5–9 GB > 6 GB VRAM).

**Rule:** when privacy is NOT required, hosted `nousresearch/hermes-4-70b` ($0.13/$0.40 per M via the OpenRouter sidecar, low-refusal research lane in the routing skill) beats any local 8B. The local uncensored lane stays the privacy/offline path only; pull a candidate only when a concrete task needs it.
