# Uncensored local LLMs — this box only (26.08.2026)

*Generated: 26.08.2026 | Scope: **RTX 4050 Laptop 6141 MiB only** | Sister file (ignore VRAM): `uncensored-local-llms-unconstrained_2026-08-26.md` | Confidence: High on the GPU-full envelope and on VERIFY=`real=1` tags; Medium-High on hardware-agent 7B/8B twins after live Ollama pages the same day*

Do **not** mix this list with the unconstrained ranking. A 27B “king” is not a laptop pick.

---

## Hardware envelope (measured)

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce **RTX 4050 Laptop** |
| VRAM | **6141 MiB** (~6.0 GB) |
| GPU-full rule | weights + **1024 MiB KV** must stay under 6141 |
| Weights cap | **5117 MiB** |
| Proven 7B Q4 envelope | installed `qwen2.5:7b` **4 683 073 952 bytes** (listed 4.7GB) = **4466 MiB** + 1024 KV = **5490**, leftover **651 MiB** |
| Already installed | aligned `qwen2.5:7b` 4.7GB, `qwen2.5:3b` 1.9GB, `nomic-embed-text` |
| Broken local tag | community **13B** with dash size and no GGUF — treat as broken, do not use |
| Runtime | Ollama (estate: 0.32.15) |

**File size ≥ 6 GB does not GPU-fit.** `9b` / `12b` / `14b+` are off this card even when “only 3.8B experts are active”.

Keep `qwen2.5:7b` as the **aligned control** for A/B. It is not uncensored.

---

## Rank 1–N — only models that GPU-fit this card

Hardware-agent order first (1–5 + comfortable + last-include), then two extras that also fit and were live-checked. Method tags: **Dolphin** / **Abliteration** (Huihui/Sumandora) / **Heretic** / **Hermes**. No Heretic or official Hermes 4 weights fit this GPU-full cap.

| Rank | Tag | GB | Method | Fit | Pull |
|---|---|---|---|---|---|
| **1** | `dolphin3:8b` (`:latest`) | **4.9GB** Q4_K_M | **Dolphin** (dataset + steerability) | Tight GPU-full, short ctx. Best uncensored on this card. VERIFY `real=1`. | `ollama pull dolphin3:8b` |
| **2** | `huihui_ai/qwen2.5-abliterate:7b` (`:latest`) | **4.7GB** | **Abliteration** | Twin of installed aligned 7B. Same proven envelope. Live page 26.08.2026: 4.7GB, 32K, tools. | `ollama pull huihui_ai/qwen2.5-abliterate:7b` |
| **3** | `dolphin-llama3:8b` (`:latest`) | **4.7GB** | **Dolphin** 2.9 (Llama 3) | GPU-full. Official library, 8K default ctx (not 128K). Live 26.08.2026. | `ollama pull dolphin-llama3:8b` |
| **4** | `huihui_ai/qwen2.5-coder-abliterate:7b` (`:latest`) | **4.7GB** | **Abliteration** | GPU-full. Tools chip. Coding twin of #2. Live 26.08.2026. | `ollama pull huihui_ai/qwen2.5-coder-abliterate:7b` |
| **5** | `dolphin-mistral` (`:7b` / `:latest`) | **4.1GB** | **Dolphin** 2.8 (Mistral 0.2) | GPU-full with more KV headroom than 8B. 32K. Live 26.08.2026. | `ollama pull dolphin-mistral` |
| **6** | `huihui_ai/qwen3.5-abliterated:4B` | **3.3GB** | **Abliteration** | **Comfortable** GPU-full. Newest uncensored family that actually fits. VERIFY `real=1` (`9acbd90c2645 · 3.3GB`, Q4_K_M, 4.54B, 256K Text+Image). | `ollama pull huihui_ai/qwen3.5-abliterated:4B` |
| **7** | `huihui_ai/qwen3-abliterated:4b` | **2.5GB** | **Abliteration** | **Comfortable** GPU-full. Older Qwen3. Hardware-agent comfortable pick. | `ollama pull huihui_ai/qwen3-abliterated:4b` |
| **8** | `huihui_ai/qwen3-abliterated:8b` (`:latest` on that name) | **5.0GB** | **Abliteration** | **Last-include.** At the 5117 MiB weights cap. Short `num_ctx` only. | `ollama pull huihui_ai/qwen3-abliterated:8b` |

Optional same-size overlay on #1 (do **not** keep both pulled at once): `huihui_ai/dolphin3-abliterated:8b` **4.9GB** — Dolphin **plus** Huihui/Sumandora second layer. `ollama pull huihui_ai/dolphin3-abliterated:8b`.

**Do not pull both Dolphin 8B and Qwen3 8B at once.** One ~5 GB model + KV + the live G-1 fleet will spill.

On 8B keep `num_ctx` 2048–4096 so KV does not shove layers to CPU.

### Default on this box

- **Want the best uncensored 8B that is an official library tag:** #1 `dolphin3:8b`.
- **Want headroom + newest Huihui family + vision:** #6 `qwen3.5-abliterated:4B` (3.3GB).
- **Want a drop-in uncensored twin of the already-installed 7B:** #2 `qwen2.5-abliterate:7b`.
- **Want code on this GPU:** #4 `qwen2.5-coder-abliterate:7b`.

There is **no** GPU-full Heretic 31B/26B/E4B and **no** GPU-full Hermes 4.3/14B/70B on this card (see NO list).

---

## Commands (this box)

```text
# Comfortable newest Huihui that fits (VERIFY real=1)
ollama pull huihui_ai/qwen3.5-abliterated:4B
ollama run  huihui_ai/qwen3.5-abliterated:4B

# Best official uncensored 8B — tight ctx only (VERIFY real=1)
ollama pull dolphin3:8b

# Twin of installed qwen2.5:7b
ollama pull huihui_ai/qwen2.5-abliterate:7b

# Coding twin
ollama pull huihui_ai/qwen2.5-coder-abliterate:7b

# Older Dolphin, more VRAM leftover
ollama pull dolphin-mistral

# Last-include current-gen 8B abliterated (pick ONE 8B)
ollama pull huihui_ai/qwen3-abliterated:8b
```

**Do not run on this GPU (wrong tag and/or too big):**

```text
ollama pull dolphin3:24b
ollama pull dolphin3:8b-llama3.1-q8_0      # 8.5GB
ollama pull dolphin3:8b-llama3.1-fp16      # 16GB
ollama pull huihui_ai/qwen3-abliterated:14b
ollama pull huihui_ai/qwen3.5-abliterated:9b
ollama pull huihui_ai/Qwen3.8-abliterated:27b
ollama pull huihui_ai/llama3.3-abliterated:70b
ollama pull hermes4
ollama pull mlabonne/gemma-3-27b-it-abliterated
```

---

## Explicit NO list — 14B+ (and everything else that misses GPU-full)

Hardware agent: **exclude 14B+, 13B, Mixtral, 70B**, and the dash-size 13B pull. Extended from the 8-lens GB tables so a 14B is never “maybe if I offload”.

### 14B+ — never GPU-full on 6141 MiB

| Tag / card | GB | Why NO |
|---|---|---|
| `huihui_ai/qwen3-abliterated:14b` | **9.0GB** | 14.8B. Pasted-list TRUE tag, still over cap. |
| `huihui_ai/qwen3-abliterated:16b` | 9.8GB | 14B+ class |
| `huihui_ai/qwen2.5-abliterate:14b` | 9.0GB | 14B |
| `huihui_ai/qwen2.5-coder-abliterate:14b` | 9.0GB | 14B |
| `huihui_ai/qwen2.5-abliterate:32b` / coder `:32b` | 20GB | 32B |
| `huihui_ai/qwen2.5-abliterate:72b` | 47GB | 72B |
| HF `NousResearch/Hermes-4-14B` bartowski Q4_K_M | **9.00GB** | 14B. **UNVERIFIED** as `hermes-4:14b` Ollama tag. |
| `huihui_ai/qwen3.5-abliterated:27b` / `:35b-a3b` / `:122B` | 17 / 24 / 81GB | 27B+ |
| `huihui_ai/Qwen3.6-abliterated:27b` / `:35b` | 17 / 24GB | 27B+ |
| `huihui_ai/Qwen3.8-abliterated:27b` (`:latest`) | **18GB** | VERIFY `real=1` and still **NO** on this GPU. |
| `jacokon/qwen3.8-27b-heretic-ara` | 18GB latest / 14GB iq3 | 27B Heretic. NO. |
| `huihui_ai/gemma-4-abliterated:26b` / `:31b` | 18 / 20GB | 26B / 31B |
| coder3101 / mradermacher Gemma 4 31B / 26B-A4B Heretic GGUF | 18.8 / 16.9GB | 14B+ |
| TrevorJS Gemma 4 31B GGUF | 18.7GB | 31B |
| `huihui_ai/gemma3-abliterated:12b` / `:27b` | 24 / 55GB | 12B listed 24GB; 27B 55GB |
| HF `mlabonne/gemma-3-27b-it-abliterated` GGUF | 16.5GB | 27B. Also **WRONG-TAG** as Ollama pull. |
| `dphn/Dolphin3.0-Mistral-24B` / R1 24B bartowski | 14.33GB | 24B. Official `dolphin3:24b` is **WRONG-TAG**. |
| `huihui_ai/dolphin3-r1-abliterated:24b` | 14GB | 24B |
| `steelpuddles/hermes-4.3-36B` / official GGUF Q4_K_M | 22 / 21.8GB | 36B |
| `huihui_ai/llama3.3-abliterated:70b` | **43GB** | VERIFY `real=1`. 70B. Needs ~48GB+ class VRAM. |
| `dolphin-llama3:70b` | 40GB | 70B |
| `huihui_ai/deepseek-r1-abliterated:14b` / `:32b` / `:70b` | 9.0 / 20 / 43GB | 14B+ |
| `huihui_ai/qwen3-abliterated:30b` / `:32b` / `:235b` | 19 / 20 / 112GB | 14B+ |
| Llama 4 Scout / Maverick uncensored | ~65 / ~232GB HF-only | No Ollama uncensored tag. Far over cap. |
| Hermes-4-70B / 405B Q4 | 42.5 / 243GB | 70B / 405B |
| Mixtral (any) | typically ≥26GB Q4 | Hardware-agent exclude |

### Also NO — under 14B but weights still miss the 5117 MiB cap

| Tag | GB | Why NO |
|---|---|---|
| `huihui_ai/qwen3.5-abliterated:9b` | **6.6GB** | Weights > VRAM |
| `jaahas/qwen3.5-uncensored:9b` | 7.4GB | Weights > VRAM. HauhauCS, not the four named methods. |
| `huihui_ai/gemma-4-abliterated:12b` | 7.6GB | Weights > VRAM |
| `huihui_ai/gemma-4-abliterated:e4b` | 9.6GB | Weights > VRAM |
| `igorls/gemma-4-12B-it-heretic-GGUF:latest` | 7.4GB | Weights > VRAM |
| `igorls/gemma-4-E4B-it-heretic-GGUF:Q4_K_M` | **5.3GB** | Over 5117 MiB weights cap once KV is reserved. **Not GPU-full.** Q8_0 8.0GB also NO. |
| mradermacher `gemma-4-E4B-it-heretic-GGUF` Q4_K_M | **5.4GB** | Same: over cap. p-e-w E4B is still 42/100 refusals anyway. |
| `huihui_ai/gemma3-abliterated:4b` (`:latest`) | **8.6GB** | Over VRAM despite “4b” in the name |
| 13B community / dash-size pull | size `-` | Broken, no GGUF. Hardware-agent exclude. |
| `dolphin3` q8_0 / fp16 | 8.5 / 16GB | Wrong quant for 6 GB |

Offload-later (not now, RAM is under pressure): `huihui_ai/qwen3-abliterated:14b` 9.0GB with CPU split. Expect a few tok/s. **Qwen 3.5 35B-A3B is 24GB on Ollama — not 6 GB just because 3B are “active”.**

---

## Pasted-list audit (this GPU)

Same pasted shortlist as the unconstrained file. Extra column: **does it GPU-fit 6141 MiB?**

| Pasted claim | Tag verdict | This GPU |
|---|---|---|
| `ollama pull dolphin3:8b` · 4.9GB | **TRUE** (VERIFY `real=1`). Dolphin-style Llama 3.1 8B. Official library, 5 tags, no 24B. | **YES — rank 1**, tight ctx |
| `huihui_ai/qwen3-abliterated:14b` · 9.0GB | **TRUE** tag. Huihui/Sumandora. | **NO — 14B+** |
| `mlabonne/gemma-3-27b-it-abliterated` as Ollama pull | **WRONG-TAG**. HF exists (GGUF 16.5GB). No official library tag. | **NO — 27B** |
| `huihui_ai/llama3.3-abliterated:70b` · 43GB | **TRUE** (VERIFY `real=1`). | **NO — 70B**, ~48GB+ class |
| `qwen3.8:27b` · 18GB | **TRUE** tag, **aligned** (not uncensored). Sibling `huihui_ai/Qwen3.8-abliterated:27b` 18GB is the uncensored one. | **NO — 27B** |
| `huihui_ai/Qwen3.8-abliterated:27b` · 18GB | **TRUE** (VERIFY `real=1`). Vision+tools+thinking. | **NO — 27B** |
| `gemma4:26b` · 19GB | **TRUE** tag, **aligned** MoE. Not `26b-a4b`. | **NO — 26B** |
| `dolphin3:24b` official | **WRONG-TAG**. 24B is HF `dphn/` + `ollama create` ~13GB. | **NO** (and the tag does not exist) |
| MMLU 68.0 vs 68.4 | **UNVERIFIED**. Dolphin3.0-Llama3.1-8B card lists MMLU-PRO **22.13**. | n/a |
| “HausHaus” zero-refusal | **WRONG-TAG + UNVERIFIED**. Real org **HauhauCS**. | n/a; their 9B 7.4GB is also **NO** on this GPU |

**Skip as pulls:** `mlabonne/gemma-3-27b-it-abliterated`, `dolphin3:24b`, `HausHaus`.

No WRONG-VRAM on the quoted disk sizes. 70B at 43GB is not a 6 GB fit.

---

## VERIFY log (this session)

| Claim | real | This GPU |
|---|---|---|
| Official `dolphin3` latest is 8B 4.9GB, not 24B | **1** | Fits tight (rank 1) |
| `huihui_ai/Qwen3.8-abliterated` latest ~18GB with vision | **1** | **Does not fit** |
| `huihui_ai/qwen3.5-abliterated:4B` ~3.3GB | **1** | Fits comfortable (rank 6) |
| `huihui_ai/llama3.3-abliterated:70b` ~43GB | **1** | **Does not fit** |

Hardware-agent tags live-checked 26.08.2026 (not in the four-row VERIFY set, but pages exist): `huihui_ai/qwen2.5-abliterate:7b` 4.7GB; `huihui_ai/qwen2.5-coder-abliterate:7b` 4.7GB; `dolphin-llama3:8b` 4.7GB; `dolphin-mistral:latest` 4.1GB. No `real=0` tag was ranked.

**UNVERIFIED on this box (do not invent a fit):** Gemma 4 E4B “maybe if ≤5.5 GB”; any Heretic 31B 17 GB listicle tag; `hermes-4:14b` as an Ollama pull; MMLU 68.0 vs 68.4.

---

## Sources

Hardware envelope: hardware agent 26.08.2026 (nvidia-smi 6141 MiB, installed `qwen2.5:7b` byte size).

Live Ollama pages 26.08.2026:

- https://ollama.com/library/dolphin3
- https://ollama.com/library/dolphin3:8b
- https://ollama.com/library/dolphin3/tags
- https://ollama.com/library/dolphin-llama3
- https://ollama.com/library/dolphin-mistral
- https://ollama.com/huihui_ai/qwen2.5-abliterate
- https://ollama.com/huihui_ai/qwen2.5-coder-abliterate
- https://ollama.com/huihui_ai/qwen3-abliterated
- https://ollama.com/huihui_ai/qwen3-abliterated:14b
- https://ollama.com/huihui_ai/qwen3.5-abliterated
- https://ollama.com/huihui_ai/Qwen3.8-abliterated
- https://ollama.com/huihui_ai/llama3.3-abliterated
- https://ollama.com/huihui_ai/dolphin3-abliterated/tags

Lens bundle (same URLs as the unconstrained report): Huihui catalog, Dolphin, Hermes, Heretic/Gemma 4, Ollama tags, coding-agents, pasted-audit.

- https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B
- https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B-GGUF
- https://huggingface.co/dphn/Dolphin3.0-Mistral-24B
- https://huggingface.co/huihui-ai/Qwen3-14B-abliterated
- https://huggingface.co/huihui-ai/Llama-3.3-70B-Instruct-abliterated
- https://erichartford.com/uncensored-models
- https://github.com/Sumandora/remove-refusals-with-transformers
- On-disk: `C:\Users\Prekzursil\.grok\dolphin-lens-handoff_2026-08-26.md`
- On-disk: `C:\Users\Prekzursil\.grok\ollama-llama33-abliterated-70b-size-handoff_2026-08-26.md`

No model was pulled in this write-up. Do not start a 4.9GB pull while G-1 is RAM-heavy.
