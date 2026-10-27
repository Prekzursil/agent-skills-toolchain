# Uncensored local LLMs — dual ranking (26.08.2026)

*Generated: 26.08.2026 | Sources: 22 | Providers: grok web_search + web_fetch + nvidia-smi + ollama CLI | Confidence: Medium-High*
*This is the seed report. The `uncensored-local-llm-research` workflow re-derives both rankings with 8 live lenses + adversarial tag checks.*

Two rankings, on purpose:

1. **Unconstrained** — best of the best if VRAM/RAM/money are not the limit.
2. **This box** — RTX 4050 Laptop **6 GB**, ~31.6 GB RAM under pressure, Ollama **0.32.15** already installed.

Do not mix them. A 27B “king” is not a laptop pick.

---

## Part A — Best of the best (hardware-independent)

Assume a 24–48 GB GPU (or dual 24 GB / 64 GB unified). Rank by **base-model freshness × refusal removal quality × agent/coding usefulness**, not by who shouts “zero refusal” the loudest.

### A0. How “uncensored” is actually made

| Method | What it is | Quality risk | Examples |
|---|---|---|---|
| **Dataset uncensored (Dolphin)** | Trained without refusal data; you own the system prompt | Lowest surgery damage | `dolphin3:8b`, Dolphin 3.0 Mistral 24B / R1 |
| **Steerability (Hermes)** | Aligned to *you*, low RefusalBench, not marketed as NSFW | Residual refusals possible | Hermes 4 14B/70B, Hermes 4.3 36B |
| **Abliteration (Huihui / Sumandora)** | Wipe the refusal direction in weights | Crude; leftover refusals or junk GGUFs | `huihui_ai/qwen3-abliterated`, Qwen3.5/3.8, Llama 3.3 70B |
| **Heretic / ARA** | Targeted ablation (p-e-w/heretic), often lower KL vs base | Newer; quality varies by card | Gemma 4 31B/26B-A4B/E4B heretic |

Abliteration is faster. Dolphin/Hermes usually keep more of the base model’s brain. “Heretic” is the 2026 compliance-max class, not automatically the smartest. `[B.corrob x3.2026]`

### A1. Overall ranking (unconstrained)

| Rank | Pick | Why it wins | VRAM Q4 (approx) | Pull / card |
|---|---|---|---|---|
| **1** | **Qwen 3.8 27B Abliterated** | Newest dense open base (Aug 2026), vision, coding, agents, Apache-lineage. Huihui abliteration is live. | ~18 GB | `ollama run huihui_ai/Qwen3.8-abliterated` (18 GB, 256K, vision+tools+thinking) |
| **2** | **Qwen 3.5 27B Abliterated** | Track record since early 2026; Featherless default for general uncensored work | ~17 GB | `ollama run huihui_ai/qwen3.5-abliterated:27b` |
| **3** | **Gemma 4 26B-A4B Uncensored / Heretic** | MoE ~4B active → fast for its size; expert-wise uncensor reports ~0.7% refusal | ~12–16 GB weights | HF `TrevorJS/gemma-4-26B-A4B-it-uncensored` / llmfan46 heretic GGUFs |
| **4** | **Gemma 4 31B Heretic** | Strongest Gemma 4 dense uncensored; vision | ~17 GB Q4 | `llmfan46/gemma-4-31B-it-uncensored-heretic` |
| **5** | **Dolphin 3.0 R1 Mistral 24B** | Best *finetune* uncensored, function calling, R1 traces; Apache 2.0 | ~14–18 GB | HF `dphn/Dolphin3.0-R1-Mistral-24B`; Ollama community tags, not `dolphin3:24b` in the official library |
| **6** | **Gemma 3 27B IT Abliterated (mlabonne)** | 2025–26 community consensus; vision; some GGUF v2 quants were junk — use known-good GGUF | ~16 GB | HF `mlabonne/gemma-3-27b-it-abliterated` |
| **7** | **Hermes 4.3 36B** | Best *steerable* agent brain (tool_call native); Apache 2.0; not a gore/NSFW specialist | ~22 GB | GGUF import; no one-line official `hermes4:36b` in Ollama library |
| **8** | **Llama 3.3 70B Abliterated** | Local ceiling for Llama-family uncensored | **43 GB** | `ollama run huihui_ai/llama3.3-abliterated:70b` |
| **9** | **DeepSeek-R1 Distill 70B Abliterated** | Uncensored chain-of-thought at 70B | ~43 GB | `ollama run huihui_ai/deepseek-r1-abliterated:70b` |
| **10** | **Qwen 3.5 122B Abliterated** | Huihui catalog ceiling (81 GB) | 81 GB | `huihui_ai/qwen3.5-abliterated:122B` — lab only |

**Default if you can buy a 24 GB card tomorrow:** `#1 Qwen 3.8 27B Abliterated`.  
**Default if you want no-surgery uncensored:** `#5 Dolphin 3.0 R1 Mistral 24B`.  
**Default if you want speed at 16 GB:** `#3 Gemma 4 26B-A4B`.  
**Default if you want 70B prose:** `#8 Llama 3.3 70B Abliterated` (48 GB+).

### A2. By job (unconstrained)

| Job | Winner | Runner-up |
|---|---|---|
| Coding + agents | Qwen 3.8 27B Abliterated | Qwen 3.5 27B Abliterated / Hermes 4.3 36B |
| General chat / reasoning | Qwen 3.5 27B Abliterated | Qwen 3.8 27B |
| Vision + uncensored | Qwen 3.8 27B or Gemma 4 31B Heretic | Gemma 3 27B Abliterated |
| Roleplay / fiction | Mistral Small 3.2 Abliterated 24B or Dolphin 3 Mistral 24B | Hermes 4 70B (steerable, less “unhinged”) |
| Maximum compliance | Gemma 4 Heretic / “E4B Ultra” class | gpt-oss-20b-heretic variants |
| Uncensored thinking | DeepSeek-R1 Abliterated 70B (or 32B distill) | Qwen3 thinking tags |
| Function calling without surgery | Hermes 4.x | Dolphin 3 R1 24B |

### A3. VRAM ladder (unconstrained, Q4_K_M-ish)

| VRAM | Best uncensored pick | Command |
|---|---|---|
| 8 GB | Dolphin 3 8B **or** Qwen3 Abliterated 8B | `ollama pull dolphin3:8b` / `huihui_ai/qwen3-abliterated:8b` |
| 12–16 GB | Qwen3 Abliterated 14B (~9 GB) | `ollama pull huihui_ai/qwen3-abliterated:14b` |
| 16–24 GB | Qwen 3.8 27B Abliterated (18 GB) **or** Gemma 4 26B-A4B | `ollama pull huihui_ai/Qwen3.8-abliterated` |
| 24 GB | Qwen 3.5 27B / Dolphin 3 Mistral 24B / Hermes 4.3 36B Q4 | see above |
| 48 GB | Llama 3.3 70B Abliterated (43 GB) | `ollama pull huihui_ai/llama3.3-abliterated:70b` |
| 80 GB+ | Qwen 3.5 122B Abliterated | `huihui_ai/qwen3.5-abliterated:122B` |

This ladder is what the other AI’s table was trying to be. **This box is not on it** (6 GB is below the 8 GB row).

### A4. Fact-check of the pasted “definitive” table

| Pasted claim | Verdict |
|---|---|
| `ollama pull dolphin3:8b` | **True.** Official library, 4.9 GB, Q4_K_M, 128K, Llama 3.1 8B. |
| `huihui_ai/qwen3-abliterated:14b` | **True tag, 9.0 GB.** Fine for 12–16 GB cards. |
| `mlabonne/gemma-3-27b-it-abliterated` as an Ollama pull | **HF true.** Official Ollama library tag is **not** that string; use HF GGUF or a known clone. Some v2 GGUFs were reported unusable. |
| `huihui_ai/llama3.3-abliterated:70b` | **True.** 43 GB, 128K, 47k pulls. |
| Qwen 3.8-27B Uncensored | **True (Aug 2026).** `huihui_ai/Qwen3.8-abliterated` 18 GB, 31.9k pulls, updated ~1 week ago. |
| Gemma 4 / 26B-A4B / E4B Heretic | **True in 2026.** Not all names in the paste map to one Ollama tag. |
| MMLU 68.0 vs 68.4 | Author-reported on Gemma 3 27B abliteration; **not re-run here**. |
| `dolphin3:24b` as official tag | **Weak.** Official `dolphin3` is **8B only**. 24B is HF + community Ollama namespaces (`aia/`, `Jotschi/`). |
| “HausHaus zero refusal on anything” | Marketing / **UNVERIFIED**. |

---

## Part B — Best of the best **on this hardware**

**Measured 26.08.2026**

- GPU: NVIDIA GeForce **RTX 4050 Laptop, 6141 MiB** (~6.0 GB), driver 610.88
- RAM: ~31.6 GB, chronic pressure (G-1 workflow `p2-g1-until-green-3` currently 30-wide)
- Runtime: **Ollama 0.32.15** at `C:\Users\Prekzursil\AppData\Local\Programs\Ollama\ollama.exe`
- Already pulled: `qwen2.5:7b` (4.7 GB), `qwen2.5:3b` (1.9 GB), `nomic-embed-text` (274 MB), `blackgrg26/WORMGPT-13` (size `-`, treat as broken)
- LM Studio models dir: empty. HF hub cache: ASR/embeddings only.

Rule: GPU-full needs **weights + ~1–1.5 GB KV/runtime ≤ 6 GB**. File size ≥ 6 GB does not GPU-fit.

### B1. Ranking for *this* card

| Rank | Pick | Size | Fit | Why |
|---|---|---|---|---|
| **1** | `huihui_ai/qwen3.5-abliterated:4B` | **3.3 GB** | Comfortable GPU-full, vision+tools+thinking, 256K | Newest uncensored family that actually fits |
| **2** | `dolphin3:8b` | **4.9 GB** | Tight GPU-full at short context | Best no-surgery uncensored 8B; official tag |
| **3** | `huihui_ai/qwen3-abliterated:8b` | **5.0 GB** | Tight GPU-full | Best current-gen 8B abliterated (Qwen3 thinking/tools) |
| **4** | `huihui_ai/qwen3-abliterated:4b` | **2.5 GB** | Easy GPU-full | Older Qwen3; more headroom than 8B |
| **5** | Keep `qwen2.5:7b` | 4.7 GB | Proven on this GPU | Aligned **control** for A/B, not uncensored |
| **6** | Gemma 4 E4B Heretic GGUF (if ≤5.5 GB quant) | ~5.5 GB | Maybe | Only Gemma 4 class that might GPU-fit; verify bytes before pull |
| — | `huihui_ai/qwen3.5-abliterated:9b` | **6.6 GB** | **No** | Weights > VRAM |
| — | `huihui_ai/qwen3-abliterated:14b` | **9.0 GB** | **No** GPU-full | Offload only, when G-1 is idle |
| — | Anything 27B / 31B / 35B / 70B | 17–43 GB | **No** | Other machine |

**Do not pull both Dolphin 8B and Qwen3 8B at once.** One 5 GB model + KV + the live G-1 fleet will spill.

### B2. Commands for this box (after G-1 calms)

```text
ollama pull huihui_ai/qwen3.5-abliterated:4B
ollama run  huihui_ai/qwen3.5-abliterated:4B
```

Optional 8B bake-off (pick one):

```text
ollama pull dolphin3:8b
# or
ollama pull huihui_ai/qwen3-abliterated:8b
```

Keep short context on 8B (`num_ctx` 2048–4096) so KV does not shove layers to CPU.

### B3. Offload later (not now)

When RAM is free: `huihui_ai/qwen3-abliterated:14b` (9 GB) with CPU split. Expect a few tok/s and RAM fights. Qwen 3.5 35B-A3B is 24 GB on Ollama — not 6 GB just because 3B are “active”.

### B4. Estate gem-hunt (local-AI only)

| ID | Find | Rec |
|---|---|---|
| G0 | Pull Qwen 3.5 Abliterated **4B** as default uncensored | TIER-0 after G-1 |
| G1 | Bake-off Dolphin 8B vs Qwen3 Abliterated 8B (20 prompts); keep one | Strong |
| G2 | Keep `qwen2.5:7b` as aligned control | Keep |
| G3 | Delete/ignore `blackgrg26/WORMGPT-13` | Prune |
| G4 | Do not add vLLM/SGLang on 6 GB | Skip |
| G5 | Later: Ollama OpenAI-compat `127.0.0.1:11434` as sidecar | Strong |

---

## Sources

1. Local `nvidia-smi` + `ollama list` 26.08.2026 — tier A
2. https://ollama.com/huihui_ai/Qwen3.8-abliterated — 18 GB, 31.9k pulls — tier B
3. https://ollama.com/huihui_ai/qwen3.5-abliterated — 4B=3.3 GB, 9b=6.6 GB, 27b=17 GB, 35b=24 GB, 122B=81 GB — tier B
4. https://ollama.com/huihui_ai/qwen3-abliterated — 8b=5.0 GB, 14b=9.0 GB — tier B
5. https://ollama.com/library/dolphin3 — 4.9 GB official 8B — tier B
6. https://huggingface.co/mlabonne/gemma-3-27b-it-abliterated — tier B
7. https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated — 16.08.2026 — tier B
8. https://ollama.com/huihui_ai/llama3.3-abliterated — 43 GB — tier B
9. https://huggingface.co/dphn/Dolphin3.0-Mistral-24B — official 24B; Ollama `dolphin3` is 8B-only — tier B
10. https://huggingface.co/llmfan46/gemma-4-31B-it-uncensored-heretic — tier B
11. https://featherless.ai/blog/best-uncensored-ai-models-2026 — Qwen3.5-27B vs Gemma 4 26B-A4B — tier C
12. https://apidog.com/blog/best-uncensored-llms/ — Qwen 3.8-27B as 16–24 GB default — tier C
13. https://localaimaster.com/blog/best-uncensored-local-llms — source of the pasted table — tier C
14. https://github.com/Sumandora/remove-refusals-with-transformers — abliteration — tier B
15. https://github.com/p-e-w/heretic — Heretic — tier B
16. https://huggingface.co/unsloth/Hermes-4-70B-GGUF — Hermes 4 — tier B
17. https://ollama.com/library/mistral-small3.2:24b — 15 GB aligned 24B — tier B
18. r/LocalLLaMA Gemma 3 abliterated GGUF junk reports — tier C
19. https://huggingface.co/huihui-ai/DeepSeek-R1-Distill-Llama-70B-abliterated — tier B
20. https://localaimaster.com/blog/ollama-model-ram-vram-table — VRAM formula — tier C
21. https://www.reddit.com/r/ollama/comments/1s9t3pu/ — anecdotal Qwen3.5 vs R1 — tier C
22. https://huggingface.co/DavidAU/gemma-4-E4B-it-The-DECKARD-HERETIC-UNCENSORED-Thinking — E4B heretic — tier B

## Methodology

Sub-questions: unconstrained ranking; this-GPU ranking; tag existence; method (Dolphin vs abliteration vs Heretic); pasted-list audit.

Firecrawl/Exa/Tavily/Perplexity MCP were **DOWN in this Grok session** (only basic-memory, frida-mcp, tasks). Full M-16 harness was not used. A follow-up workflow (`uncensored-local-llm-research`) re-runs 8 lenses + adversarial tag checks.

No model was pulled. G-1 30-wide repair was left running.
