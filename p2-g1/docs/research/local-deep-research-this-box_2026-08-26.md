# Local deep research — this box only (26.08.2026)

*Generated: 26.08.2026 | Scope: **RTX 4050 Laptop 6141 MiB GPU-full only** | Sister (ignore VRAM): `local-deep-research-unconstrained_2026-08-26.md` | Confidence: High on the GPU-full envelope and on VERIFY=`real=1` tags; Medium on 5.1–5.2GB “tight” rows (formula-FIT, WDDM spill risk)*

Do **not** mix this list with the unconstrained ranking. **14B+ GPU-full is NO.** `qwen3.5:9b` (6.6GB) is also NO.

---

## Hardware envelope (measured)

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce **RTX 4050 Laptop** |
| VRAM | **6141 MiB** (~6.0 GB) |
| GPU-full rule | weights + **1024 MiB KV** must stay under 6141 |
| Weights cap | **5117 MiB** (~5.36 GB SI) |
| Proven 7B Q4 envelope | installed `qwen2.5:7b` **4466 MiB** Q4_K_M + 1024 KV = **5490**, leftover **651 MiB** |
| Already installed | `qwen2.5:7b` ~4.4GB (tools, 32K), `qwen2.5:3b` 1.9GB, `nomic-embed-text` 262 MiB embed-only |
| Broken local tag | `blackgrg26/WORMGPT-13:latest` — size dash, no model layer, remote 123B stub. A real 13B would not GPU-full anyway. **Do not use.** |
| Runtime | Ollama; set `num_ctx` (defaults 4k/32k/256k by VRAM) |

**File size ≥ 6 GB does not GPU-fit.** 9B / 12B / **14B+** are off this card even when “only 3B experts are active”. 5.2GB tags (`qwen3:8b`, `deepseek-r1:8b`) are **formula-FIT but tight** on this WDDM laptop.

Keep `qwen2.5:7b` as the **aligned control**. Do not pull two ~5GB models at once with the live G-1 fleet.

---

## Rank 1–N — only GPU-full research fits

Order from the hardware-agent brief: `qwen3:4b` → installed `qwen2.5:7b` → `deepseek-r1:7b`, then citation / vision / RAG sidecars that also fit.

| Rank | Tag | GB | Method/job | Pull |
|---|---|---|---|---|
| **1** | `qwen3:4b` (thinking variant `qwen3:4b-thinking`) | **2.5GB** | Current-gen **thinking**, 256K listed. Comfortable GPU-full + KV headroom. Best *research planner* on this card. | `ollama pull qwen3:4b` |
| **2** | `qwen2.5:7b` (`:latest`) | **~4.4–4.7GB** | **INSTALLED.** Tools-confirmed Q4_K_M, 32K. Aligned control and daily multi-hop agent. | already on disk (`ollama pull qwen2.5:7b`) |
| **3** | `deepseek-r1:7b` | **4.7GB** | R1 distill (Qwen-7B). CoT research plans when #1 is too small. | `ollama pull deepseek-r1:7b` |
| **4** | `llama3.1:8b` | **4.9GB** | General 8B reader. Tight GPU-full, short `num_ctx`. Stale as a 2026 default; still a documented local fallback. | `ollama pull llama3.1:8b` |
| **5** | `command-r7b:7b` (`:latest`) | **5.1GB** | **Smallest native citer** (tokenizer still has `chat_template.rag`). Ollama lists 8K; HF 128K. Tight. CC-BY-NC. | `ollama pull command-r7b` |
| **6** | `gemma3:4b` | **3.3GB** | Vision for paper figures / PDF pages. Not Gemma 4 (31B is 20GB — **NO**). | `ollama pull gemma3:4b` |
| **7** | `phi4-mini` | **2.5GB** | Comfortable GPU-full helper; short-form synthesis. | `ollama pull phi4-mini` |
| **8** | `qwen3-embedding:8b` | **4.7GB** (`:0.6b` **639MB**) | Live Ollama retriever SOTA. **Swap** with the chat model — both 4.7GB will not GPU-full together. Prefer `:0.6b` while #2 is loaded. | `ollama pull qwen3-embedding:0.6b` |
| **9** | `bespoke-minicheck:7b` | **4.7GB** | FACT sentence Yes/No verifier (MiniCheck). Sidecar, not the researcher. Swap in. | `ollama pull bespoke-minicheck` |
| **10** | `qwen3:8b` / `deepseek-r1:8b` | **5.2GB** | Last-include hybrid think (`qwen3:8b` = R1-0528-Qwen3-8B sibling on the R1 line at 5.2GB, AIME24 86.0). **Tight.** Short ctx only. Pick **one**. | `ollama pull qwen3:8b` |

Optional same-size RAG chat: `llama3-chatqa:8b` **4.7GB** — not 2026 SOTA. Tiny embeds already installed: `nomic-embed-text`. Also FIT: `embeddinggemma:300m` 622MB, `bge-m3` 1.2GB.

Uncensored citer (quality **UNVERIFIED** vs stock): `huihui_ai/command-r7b-abliterated` **5.1GB** — RAG template still present.

### Default on this box

- **Want thinking + headroom:** #1 `qwen3:4b`.
- **Want tools on weights already on disk:** #2 `qwen2.5:7b`.
- **Want native citations:** #5 `command-r7b` (tight; do not leave #2 loaded).
- **Want RAG while chatting:** #8 `:0.6b` (639MB) + #2, **not** the 4.7GB embed + 4.7GB chat.
- **Want FACT check:** swap #9.

On 8B / 5.1GB keep `num_ctx` 2048–4096 so KV does not shove layers to CPU.

---

## Explicit NO (14B+ and over-cap)

**Do not GPU-full these on this card.** Offload/CPU is a different rank (label it); it is not this file.

| Tag | GB | Why NO |
|---|---|---|
| `qwen3:14b` | **9.3GB** | 14B+. Stale blog “research default”. |
| `deepseek-r1:14b` | **9.0GB** | 14B+. |
| `qwen3.5:9b` | **6.6GB** | Over 5117 MiB. Ollama 3.5 latest is 9B, not a 6GB fit. |
| `qwen3.8:27b` | **18GB** | Unconstrained #1. Not this GPU. |
| `qwen3.6:35b` / `:27b` | 23 / 18GB | Unconstrained. |
| `gemma4:31b` / `:26b` | 20 / 19GB | Needle SOTA is unconstrained. |
| `command-r:35b` / `command-r-plus` / `command-a` | 19 / 59 / 67GB | Native citations at 24GB+ class. |
| `llama4:scout` | **67GB** | 10M window. |
| `gpt-oss:20b` / `:120b` | 14 / 65GB | 20B is **14GB** — NO GPU-full. |
| `qwen3:30b-thinking` / `:32b` | 19 / 20GB | Planners for a workstation. |
| `qwen3-embedding:8b` **together with** a 7B chat | 4.7+4.4GB | Each FIT alone; both together **NO**. |
| `blackgrg26/WORMGPT-13:latest` | size dash | **Broken stub**, not a 13B. |

CPU/offload of 14B is allowed only if you explicitly accept 1–4 tok/s and host-RAM death. That is **not** GPU-full and must not be reported as a this-box success.

---

## Commands (this box)

```text
# Comfortable current-gen thinker (default research planner)
ollama pull qwen3:4b
ollama run  qwen3:4b

# Already installed aligned control (tools)
ollama run qwen2.5:7b

# CoT distill
ollama pull deepseek-r1:7b

# Native citations — tight; unload the 7B first
ollama pull command-r7b

# Vision for figures
ollama pull gemma3:4b

# RAG while 7B is loaded
ollama pull qwen3-embedding:0.6b

# FACT sidecar (swap, do not dual-load)
ollama pull bespoke-minicheck

# Last-include 8B thinker — pick ONE 8B, short ctx
ollama pull qwen3:8b
```

**Do not run on this GPU:**

```text
ollama pull qwen3:14b
ollama pull deepseek-r1:14b
ollama pull qwen3.5:9b
ollama pull qwen3.8:27b          # unconstrained king; 18GB
ollama pull gpt-oss:20b          # 14GB
ollama pull command-r-search     # 404 — not a model
ollama pull linq                 # 404
ollama pull blackgrg26/WORMGPT-13
```

---

## Suggested loop on 6 GB

1. Embed the phenibut corpus / notes with `qwen3-embedding:0.6b` (or installed `nomic-embed-text`).
2. Multi-hop with `qwen3:4b` or installed `qwen2.5:7b` (`num_ctx` 4096–8192).
3. If the answer must carry citation spans, **unload** and run `command-r7b` over retrieved chunks.
4. Optional FACT: swap `bespoke-minicheck:7b` for Yes/No support of each sentence.
5. Do not ask any of these models to **dose** or treat. Mechanism / literature only.

---

## Sources

Hardware envelope and FIT list: this session’s GPU probe (RTX 4050 6141 MiB; installed `qwen2.5:7b` 4466 MiB). Tags from 26.08.2026 Ollama/HF cards cited in `local-deep-research-unconstrained_2026-08-26.md`. VERIFY `real=1` on `qwen3.8` does **not** make `:27b` a this-box pull.
