# Local deep research — unconstrained ranking (26.08.2026)

*Generated: 26.08.2026 | Scope: **ignore VRAM** | Sister (this GPU): `local-deep-research-this-box_2026-08-26.md` | Confidence: High on tag existence for VERIFY=`real=1` rows and live Ollama/HF cards fetched 26.08.2026; Medium on “best” order (no independent multi-hop eval run here)*

This file is **hardware-independent**. A 27B / 104B “king” is not an RTX 4050 6 GB pick. Do not mix the two lists.

Estate job: FACT-style multi-hop over phenibut literature (~400 PDFs in `D:\Research\projects\phenibut\corpus\00_English_originals`), ToolUniverse dossiers, and scholarly-access/Anelis — **not** a generic chatbot. Retrieval is a **second** model. Ollama `num_ctx` defaults 4k/32k/256k by VRAM — set it.

---

## Rank 1–10 (ignore VRAM)

Rank = **2026 reasoning × native context × tools/thinking × grounded citations**. Bigger is not automatically better (Scout’s 10M window is weaker 2026 reasoning; cutoff Aug 2024).

| Rank | Tag | GB | Method/job | Pull |
|---|---|---|---|---|
| **1** | `qwen3.8:27b` (`:latest`) | **18GB** (q8_0 / mtp-q8_0 **30GB**; bf16 **56GB**) | Dense VL research brain: vision + tools + thinking, 256K listed (HF 262 144 native / 1M YaRN). Official 2026-08-14 card. VERIFY `real=1`. | `ollama pull qwen3.8:27b` |
| **2** | `qwen3.6:35b` (`:35b-a3b` / `:latest`) | **23GB** (`:27b` **18GB** dense) | MoE 35B/3B VL; iterative outline-then-search; `preserve_thinking`; parser `qwen3_coder`. | `ollama pull qwen3.6:35b` |
| **3** | `gemma4:31b` | **20GB** (`:26b` **19GB**) | Strongest published **local needle**: MRCR v2 8-needle 128k = **66.4%**. Heavy KV. HLE-with-search 26.5%. No citation API. | `ollama pull gemma4:31b` |
| **4** | `command-r-plus` (`:104b`) | **59GB** (`:104b-08-2024-q4_K_M` **63GB**) | Unique live Ollama **native citations** (accurate/fast + `<co>` spans). 104B, 128K, CC-BY-NC. | `ollama pull command-r-plus` |
| **5** | `command-a` (`:111b`) | **67GB** | Mar 2025 successor; RAG-trained; `enable_citations=True`; Ollama lists 16K, HF 256K. CC-BY-NC. | `ollama pull command-a` |
| **6** | `qwen3:30b-thinking` | **19GB** | Thinking-only 256K research planner (Qwen3-30B-A3B-Thinking-2507; AIME25 85.0). Hybrid sibling `qwen3:32b` **20GB**. | `ollama pull qwen3:30b-thinking` |
| **7** | `gpt-oss:20b` | **14GB** | 21B/3.6B MXFP4, effort low/med/high, native tools, Apache-2.0. Plans + tool loops without 59GB. | `ollama pull gpt-oss:20b` |
| **8** | `llama4:scout` (`:16x17b`) | **67GB** | Longest window (**10M**) for stuffing corpora. Weaker 2026 reasoning (cutoff Aug 2024). Reads sources; **does not cite**. | `ollama pull llama4:scout` |
| **9** | `gpt-oss:120b` | **65GB** | 117B/5.1B, 128K, native tools. One 80GB-class GPU. Scale, not needle-SOTA. | `ollama pull gpt-oss:120b` |
| **10** | `command-r:35b` (`:latest`) | **19GB** | Same citation stack as R+ at 24GB-class; 128K; RAG + tools; ~1.5M pulls. | `ollama pull command-r:35b` |

**Default if you can buy a 24 GB card:** #1.  
**Default if the job is “quote the PDF with spans”:** #4 (or #10 on 24 GB).  
**Default if the job is stuffing 10M tokens of dumps:** #8, then a 27B reasoner.  
**Default research planner (thinking-only):** #6.

### Rank notes (do not skip)

**#1 Qwen3.8-27B.** Confirmed 26.08.2026: `https://ollama.com/library/qwen3.8` live (not 404); Models table `qwen3.8:latest` / `:27b` / `:27b-mlx` **18GB**; 827.3K downloads; updated 1 week ago. HF `Qwen/Qwen3.8-27B`. vs Qwen3.6-27B: SWE-Pro 61.7 vs 53.5, HLE 30.8 vs 24.0, CoWorkBench 70.7 vs 61.0, OSWorld-Verified 84.3 vs 63.9. Terminal Bench 2.1 **73.0**. Chips: vision + tools + thinking. Launch targets: Claude Code / OpenCode / Hermes / OpenClaw. **No official Ollama 3.8 MoE tag** — the 2.4T-A95B is HF-only (see honourable).

**#2 Qwen3.6-35B-A3B.** Official library latest = 35b-a3b 23GB MoE (3B active, VL). Dense `:27b` 18GB if you want the previous VL at the same blob size as #1. HF `Qwen/Qwen3.6-35B-A3B`: MCPMark 37.0, MCP-Atlas 62.8.

**#3 Gemma 4 31B.** HF `google/gemma-4-31B-it`. Needle score is the published local SOTA; KV cache is the tax. Pair with a citer (#4/#10) if the output must be grounded.

**#4 / #5 / #10 Command family.** Still the **only** live Ollama generators with a native citation template. CC-BY-NC. `command-r-search` is **NOT a model** (`ollama.com/library/command-r-search` **404** this fetch) — it is Simon Willison’s `llm` plugin for the Cohere **API**. Do not pull it. Command R7B (5.1GB) is the commodity-GPU citer — this-box file, not this list.

**#6 Thinking planner.** `qwen3:30b-thinking` is thinking-only. Hybrid `qwen3:32b` 20GB if you need tools + think in one process. Older `qwq:32b` 20GB — do not prefer it over 2507.

**#7 / #9 gpt-oss.** Apache-2.0, native tools. 20B is the workstation default; 120B is the 80GB-GPU default. Keep MiniMax-style interleaved think in history if you swap stacks.

**#8 Scout.** Use as the **dump window**, not the reasoner. Pair with #1. Llama 4 Maverick is 245GB — not ranked here.

---

## RAG sidecar (not a 1–10 researcher)

| Role | Tag | GB | Pull | Notes |
|---|---|---|---|---|
| Retriever SOTA (live Ollama) | `qwen3-embedding:8b` | **4.7GB** (`:0.6b` **639MB**) | `ollama pull qwen3-embedding:8b` | 32–40K seq; MTEB-multi 70.58 on 0.6B line. |
| Reranker | HF `Qwen/Qwen3-Reranker-8B` | (HF) | **No** `ollama.com/library/qwen3-reranker` (**404**) | Import GGUF / vLLM. |
| FACT sentence Yes/No | `bespoke-minicheck:7b` | **4.7GB** | `ollama pull bespoke-minicheck` | MiniCheck. |
| Atomic claims | HF `rishanthrajendhran/VeriFastScore` | 8B | **No Ollama tag** | Llama-3.1-8B, Apache-2.0. |
| RAG faithfulness | HF `PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct` | 8B | **No Ollama tag** | PASS/FAIL judge. |
| Tiny embed (already on this estate) | `nomic-embed-text` | **274MB** | installed | Not 2026 SOTA. Also `embeddinggemma:300m` 622MB, `bge-m3` 1.2GB. |

Qwen3 / 3.5 / 3.8, Scout, and Gemma 4 **have no official citation template** — prompt-cited only. OCC-RAG-0.6B (`occ-ai/OCC-RAG-0.6B`) is the Qwen citation/abstain specialist (**HF only**, GB **UNVERIFIED** this fetch). No live model named **RACE verifier** was found (**UNVERIFIED** / absent).

Linq: `ollama.com/library/linq` **404**. HF `Linq-AI-Research/Linq-Embed-Mistral` 7B F16 14.22GB is historical MTEB (2024-05-29), not a 2026 Ollama pull.

---

## Commands (copy)

```text
# 1  2026 local research default (VERIFY real=1)
ollama pull qwen3.8:27b

# 2  MoE outline-then-search
ollama pull qwen3.6:35b

# 3  needle / long-doc
ollama pull gemma4:31b

# 4–5  native citations (CC-BY-NC)
ollama pull command-r-plus
ollama pull command-a

# 6–7  planners
ollama pull qwen3:30b-thinking
ollama pull gpt-oss:20b

# 8–10  dump window / scale / 24GB-class citer
ollama pull llama4:scout
ollama pull gpt-oss:120b
ollama pull command-r:35b

# RAG
ollama pull qwen3-embedding:8b
ollama pull bespoke-minicheck
```

Set context explicitly:

```text
ollama run qwen3.8:27b
# then: /set parameter num_ctx 32768   (or 131072 / 262144 if RAM allows)
```

**Do not run:**

```text
ollama pull command-r-search     # 404 — CLI plugin, not a model
ollama pull linq                 # 404
ollama pull qwen3-reranker       # 404 this fetch
ollama pull qwen3-vl-embedding   # 404; HF-only Qwen3-VL-Embedding-8B
ollama pull command-a-vision     # 404
ollama pull glm-5                # retired / no live local Ollama tag (HF zai-org/GLM-5.2 is 1M MIT)
ollama pull qwen3:14b            # stale blog “research default”; 40K listed, not 3.8
```

---

## Honourable mentions (not top 10)

| Item | GB | Why not 1–10 |
|---|---|---|
| `qwen3.5:122b-a10b` | **81GB** | Largest **local VL MoE** on official Ollama. Older than 3.8. `:397b-cloud` is cloud, no local GB. |
| HF `Qwen/Qwen3.8-2.4T-A95B` | Unsloth GGUF **397GB–4.89TB** | Max-class, text-only, qwen3.8-max license. **Not** `ollama.com/library`. Hosted Qwen3.8-Max adds vision. |
| HF `zai-org/GLM-5.2` | (HF, 1M ctx, MIT) | Real card. **No** live Ollama `glm-5` / `glm-4.6` local tag (retired). |
| `qwen3.8:27b-q8_0` | **30GB** | Same #1 denser quant, not a different brain. |
| `qwen3.8:27b-mlx` | **18GB** | Apple Silicon official MLX. |
| `magistral:24b` | **14GB** | Magistral Small 2506 Apache-2.0; AIME24 70.68 / AIME25 62.76; cap ~40k. Medium is API-only. |
| `deepseek-r1:32b` | **20GB** | Distill-Qwen-32B (AIME24 72.6). Full `deepseek-r1:671b` **404GB**. Prefer #6 for 2026 Qwen thinking. |
| `qwen3-next:80b-a3b-thinking` | **50GB** | AIME25 87.8. |
| `qwen3:235b-thinking` | **142GB** | AIME25 92.3. |
| `qwen3.5:9b` (`:latest` **6.6GB**) | 6.6GB | Daily laptop agent; not unconstrained research SOTA. Ollama 3.5 latest is **9B not 27B**. |
| `llama3-chatqa:8b` | **4.7GB** | RAG chat, not 2026 SOTA. |
| `huihui_ai/command-r7b-abliterated` | **5.1GB** | RAG template still present; citation quality vs stock **UNVERIFIED**. No Command R+ uncensored library tag. |

Stale: blogs that pick **Qwen3-14B** as the 2026 research default (Ollama `qwen3:14b` is 40K). Community uncensored/Whittle MoE names are **not** official library tags.

---

## Estate note (RAM ≠ VRAM)

This ranking **ignores VRAM**. This estate still has ~32 GB host RAM under chronic pressure. Practical *local* unconstrained default on **this machine’s RAM** is still **#1 18GB**, not Scout 67GB. 67GB+ tags need another box. GPU-full on the RTX 4050 is the sister file.

---

## Sources (fetched 26.08.2026)

- https://ollama.com/library/qwen3.8 — VERIFY `real=1`
- https://huggingface.co/Qwen/Qwen3.8-27B
- https://ollama.com/library/qwen3.6 · https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- https://ollama.com/library/gemma4 · https://huggingface.co/google/gemma-4-31B-it
- https://ollama.com/library/llama4 · https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct
- https://ollama.com/library/gpt-oss · https://huggingface.co/openai/gpt-oss-20b · https://huggingface.co/openai/gpt-oss-120b
- https://ollama.com/library/qwen3.5 · https://ollama.com/library/qwen3 · https://ollama.com/library/qwen3-next · https://ollama.com/library/qwq
- https://ollama.com/library/command-r-plus · https://ollama.com/library/command-a · https://ollama.com/library/command-r · https://ollama.com/library/command-r7b
- https://huggingface.co/CohereLabs/c4ai-command-r-plus · https://huggingface.co/CohereLabs/c4ai-command-a-03-2025
- https://ollama.com/library/qwen3-embedding · https://huggingface.co/Qwen/Qwen3-Embedding-8B · https://huggingface.co/Qwen/Qwen3-Reranker-8B
- https://ollama.com/library/bespoke-minicheck · https://huggingface.co/bespokelabs/Bespoke-MiniCheck-7B
- https://huggingface.co/rishanthrajendhran/VeriFastScore · https://huggingface.co/PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct
- https://huggingface.co/occ-ai/OCC-RAG-0.6B · https://huggingface.co/zai-org/GLM-5.2
- https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B · https://huggingface.co/unsloth/Qwen3.8-2.4T-A95B-GGUF
- https://docs.ollama.com/context-length · https://docs.ollama.com/capabilities/tool-calling
- 404 this fetch: `/library/command-r-search` · `/library/linq` · `/library/qwen3-reranker` · `/library/qwen3-vl-embedding` · `/library/command-a-vision`
