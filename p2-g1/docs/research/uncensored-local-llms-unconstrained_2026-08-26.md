# Uncensored local LLMs — unconstrained ranking (26.08.2026)

*Generated: 26.08.2026 | Scope: **ignore VRAM** | Sources: 8-lens bundle (newest-bases, huihui-catalog, dolphin, hermes, heretic-gemma4, ollama-tags, coding-agents, pasted-audit) plus live Ollama pages the same day | Confidence: High on tag existence for VERIFY=`real=1` rows; Medium on “best” quality order (no independent eval run here)*

This file is **hardware-independent**. A 27B “king” is not a 6 GB laptop pick. The this-box ranking lives in `uncensored-local-llms-this-box_2026-08-26.md`.

Do not mix the two.

---

## How “uncensored” is labelled here

| Method tag | What it is | Not |
|---|---|---|
| **Dolphin** | Refusal-filtered SFT + user-owned system prompt (dataset uncensored) | Abliteration, Heretic, Hermes weights |
| **Abliteration** | Huihui/Sumandora `remove-refusals-with-transformers` (weight-space refusal wipe) | Dolphin SFT, official Hermes, Heretic/ARA |
| **Heretic / ARA** | p-e-w/heretic training-free ablation, often with Arbitrary-Rank Ablation | Huihui Ollama tags (those are Sumandora) |
| **Hermes** | Official Nous steerability + native `<tool_call>` / JSON; RefusalBench, not marketed as NSFW | Dolphin, Huihui, Heretic forks |

On **2026 newest open bases** (Qwen 3.5 / 3.6 / 3.8, Gemma 4, Llama 4): live uncensored work is **Huihui/Sumandora plus Heretic/ARA**. Official Dolphin SFT and official Nous Hermes SFT were **NOT FOUND** on those bases this fetch. Hermes 4 is still Llama-3.1-70B / 405B plus Hermes-4.3-36B on Seed-OSS. Official Ollama `dolphin3` is Llama 3.1 **8B only**.

---

## Rank 1–10 (ignore VRAM)

Rank = **base freshness × refusal-removal quality × agent/coding usefulness**. Bigger is not automatically better (Hermes-4-405B RefusalBench-reason 57.10% loses to Hermes-4.3-36B 72.29%).

| Rank | Tag | GB (Q4-class) | Method | Pull |
|---|---|---|---|---|
| **1** | `huihui_ai/Qwen3.8-abliterated:27b` (`:latest`) | **18GB** (blob 17GB Q4_K_M + 931MB projector) | Abliteration (Huihui/Sumandora) | `ollama pull huihui_ai/Qwen3.8-abliterated:27b` |
| **2** | `jacokon/qwen3.8-27b-heretic-ara` (`:latest`) | **18GB** Ollama row; publisher readme **17GB** Q4_K_M+mmproj | Heretic/ARA | `ollama pull jacokon/qwen3.8-27b-heretic-ara` |
| **3** | `steelpuddles/hermes-4.3-36B` / HF `NousResearch/Hermes-4.3-36B` | **22GB** Ollama / official GGUF **Q4_K_M 21.8GB** (BF16 72.31GB) | Hermes (official steerability) | `ollama pull steelpuddles/hermes-4.3-36B` |
| **4** | HF `coder3101/gemma-4-31B-it-heretic` + `mradermacher/gemma-4-31B-it-heretic-GGUF` | **Q4_K_M 18.8GB** / Q8_0 32.7GB | Heretic/ARA | **No Ollama heretic tag.** Import GGUF. Ollama fallback is #5 (Sumandora, not Heretic). |
| **5** | `huihui_ai/gemma-4-abliterated:31b` | **20GB** (`:12b` 7.6GB / `:e4b` 9.6GB) | Abliteration (Huihui/Sumandora) | `ollama pull huihui_ai/gemma-4-abliterated:31b` |
| **6** | `huihui_ai/Qwen3.6-abliterated:27b` | **17GB** (`:35b` is 24GB — skip for long tool loops) | Abliteration (Huihui/Sumandora) | `ollama pull huihui_ai/Qwen3.6-abliterated:27b` |
| **7** | `huihui_ai/qwen3.5-abliterated:27b` (`:latest`) | **17GB** | Abliteration (Huihui/Sumandora) | `ollama pull huihui_ai/qwen3.5-abliterated:27b` |
| **8** | HF `dphn/Dolphin3.0-R1-Mistral-24B` + bartowski Q4_K_M; Ollama overlay `huihui_ai/dolphin3-r1-abliterated:24b` | **14.33GB** GGUF / **14GB** Huihui Ollama | Dolphin SFT (R1 traces). Overlay = Dolphin **plus** Abliteration | **Do not** `ollama pull dolphin3:24b`. Use `ollama pull huihui_ai/dolphin3-r1-abliterated:24b` **or** HF GGUF + `ollama create` (~13GB) |
| **9** | `huihui_ai/llama3.3-abliterated:70b` (`:latest`) | **43GB** Q4_K_M (VERIFY `real=1`) | Abliteration (Huihui/Sumandora) | `ollama pull huihui_ai/llama3.3-abliterated:70b` |
| **10** | `huihui_ai/qwen3.5-abliterated:122B` | **81GB** | Abliteration (Huihui/Sumandora) | `ollama pull huihui_ai/qwen3.5-abliterated:122B` |

**Default if you can buy a 24 GB card:** #1.  
**Default if you want measured 0/100 refusals on the same 27B base:** #2.  
**Default if you want Apache steerability, not surgery:** #3.  
**Default if you want no-surgery uncensored chat/reasoning:** #8 (HF, not official `dolphin3`).  
**Default 70B Llama-family Ollama tag:** #9.

### Rank notes (do not skip)

**#1 Qwen 3.8-27B Huihui.** Newest dense open VLM used as the local coding-agent brain (Hermes Agent / OpenCode / Claude Code / OpenClaw). Ollama chips: vision + tools + thinking. VERIFY `real=1` on 26.08.2026: `huihui_ai/Qwen3.8-abliterated:latest` = `bdc5e13cd164 · 18GB · 256K · Text, Image`. Same digest as `:27b` / `:27b-q4_K_M`. HF: `huihui-ai/Huihui-Qwen3.8-27B-abliterated` and GGUF UD-Q4_K_XL 17.4GB. Other quants on the same name: `:27b-q2_K` 12GB, `:27b-q8_0` 30GB, `:27b-q8_0_L` 40GB, `:27b-bf16` 56GB.

**#2 Qwen 3.8-27B Heretic/ARA.** HF `trohrbaugh/Qwen3.8-27B-heretic-ara` reports **0/100 refusals, KL 0.0535**. Community Ollama `jacokon/qwen3.8-27b-heretic-ara` is live (vision/tools/thinking; 256 downloads, updated 3 days as of 26.08.2026). Models row `:latest` = **18GB**; readme table lists Q4_K_M+mmproj as **17 GB** (same 17+projector rounding as Huihui). Also `:iq3_m` 14GB and `:q3_k_m` 14GB. This is **not** a Huihui tag.

**#3 Hermes 4.3 36B.** Apache-2.0 on Seed-OSS-36B-Base. Official HF BF16 72.31GB; **official GGUF only for 4.3** (Q4_K_M 21.8GB, Q8_0 38.4GB). RefusalBench (Nous, not arXiv 2605.21545): **74.60% non-reason / 72.29% reason** vs Hermes-4-70B-reason 59.50% vs 405B-reason 57.10% vs GPT-4o 17.67%. **No official Ollama `hermes4` tag** (`ollama.com/library/hermes4` 404 this fetch). Last official library family is `hermes3` (8b 4.7GB / 70b 40GB / 405b 229GB). Community: `steelpuddles/hermes-4.3-36B` 22GB. **UNVERIFIED:** `ollama pull hermes-4:14b`. Third-party Heretic (not official): `arnomatic/Hermes-4.3-36B-heretic` 6/100 vs 81/100.

**#4 Gemma 4 31B Heretic/ARA.** Working family is **`coder3101/gemma-4-heretic`**, not p-e-w’s own 31B (p-e-w has **E4B/E2B only**; E4B still 42/100 refusals). coder3101 31B: 15/100 refusals, KL 0.0434. mradermacher Q4_K_M **18.8 GB**. TrevorJS 31B GGUF Q4_K_M 18.7GB is grimjim biprojection + EGA, **not** Heretic. **UNVERIFIED:** listicle “31B Heretic 17 GB” (`locallyuncensored.com/blog/gemma-4-local-guide.html`). HF `trohrbaugh/gemma-4-31b-it-heretic-ara`: 5/100, KL 0.012, **no Ollama library tag**.

**#5 Huihui Gemma 4.** Easy one-command family: `huihui_ai/gemma-4-abliterated` `:e2b` 7.2GB, `:e4b` 9.6GB, `:12b` 7.6GB, `:26b` 18GB, `:31b` 20GB. **986K pulls** on the 31B line in the newest-bases lens. Huihui **26B experts are not ablated**. For MoE expert ablation use TrevorJS `gemma-4-26B-A4B-it-uncensored` (EGA), not the Huihui `:26b` tag.

**#6 / #7 Qwen 3.6 then 3.5 27B Huihui.** 3.6: `huihui_ai/Qwen3.6-abliterated:27b` 17GB, 340.1K pulls, tools. 3.5: `huihui_ai/qwen3.5-abliterated:27b` 17GB, **567.3K pulls**, 256K vision — most-used uncensored Qwen Ollama tag. Dense 27B is preferred over `qwen3.5-abliterated:35b-a3b` 24GB MoE for multi-step tools.

**#8 Dolphin 3.0 R1 24B.** Official uncensored method = dataset + steerability, **not** surgery. Base `mistralai/Mistral-Small-24B-Base-2501`. BF16 tree 47.2GB. Bartowski Q4_K_M **14.33GB**, Q4_0 13.49GB, Q8_0 25.05GB. R1 = 3 epochs on ~800k Dolphin-R1. ChatML. Temp 0.05–0.1. **Official `ollama.com/library/dolphin3` has no 24B tag** (VERIFY `real=1`: latest/8b = 4.9GB, digest `d5ab9ae8e1f2`, 5 tags). Huihui second layer: `huihui_ai/dolphin3-r1-abliterated:24b` 14GB.

**#9 Llama 3.3 70B Huihui.** VERIFY `real=1`: `694ca93d4b6e · 43GB ·` Q4_K_M, 70.6B, 128K. Manifest model layer 42 520 398 592 bytes. Other tags on the same page: q2_K 26GB, q8_0 75GB, fp16 141GB. Needs ~48GB+ class VRAM. **Not a 24GB fit.**

**#10 Qwen 3.5 122B Huihui.** Catalog ceiling with a real Ollama tag (81GB). 397B is **HF-only GGUF**, no Ollama tag, no GB on the card. Skip `huihui3.5:67b` 89GB — **explicitly not ablated**.

---

## Commands (copy)

```text
# 1  newest 27B abliterated agent overlay (VERIFY real=1)
ollama pull huihui_ai/Qwen3.8-abliterated:27b

# 2  same base, Heretic/ARA (0/100 on HF card)
ollama pull jacokon/qwen3.8-27b-heretic-ara

# 3  official Hermes 4.3 — community Ollama, not library/hermes4
ollama pull steelpuddles/hermes-4.3-36B
# last official Nous library tag (older gen):
# ollama pull hermes3

# 5  Gemma 4 31B Huihui (Sumandora). Heretic 31B has no Ollama tag — use HF GGUF for #4
ollama pull huihui_ai/gemma-4-abliterated:31b

# 6–7
ollama pull huihui_ai/Qwen3.6-abliterated:27b
ollama pull huihui_ai/qwen3.5-abliterated:27b

# 8  Dolphin R1 24B overlay (NOT dolphin3:24b)
ollama pull huihui_ai/dolphin3-r1-abliterated:24b

# 9–10  70B / 122B
ollama pull huihui_ai/llama3.3-abliterated:70b
ollama pull huihui_ai/qwen3.5-abliterated:122B
```

**Do not run:**

```text
ollama pull dolphin3:24b              # WRONG-TAG — library is 8B only
ollama pull hermes4                   # 404 this fetch
ollama pull hermes-4:14b              # UNVERIFIED
ollama pull mlabonne/gemma-3-27b-it-abliterated   # WRONG-TAG as Ollama pull
ollama pull HausHaus                  # WRONG-TAG; real org is HauhauCS
```

---

## Honourable mentions (not top 10 pulls)

| Item | GB | Method | Why not ranked as a pull |
|---|---|---|---|
| HF `NousResearch/Hermes-4-70B` + LM Studio Q4_K_M | 42.5GB (BF16 141.12GB) | Hermes | Strong 70B steerability; no official `hermes4` Ollama tag. Heretic fork `hrktos-37/Hermes-4-70B-heretic` 26/100 vs 47/100, **not official**. |
| HF `NousResearch/Hermes-4-405B` + LM Studio Q4_K_M | 243GB (BF16 811.72GB) | Hermes | Ceiling size; **worse** RefusalBench-reason than 4.3-36B. |
| HF `NousResearch/Hermes-4-14B` + bartowski Q4_K_M | 9.00GB (BF16 29.55GB) | Hermes | Apache 14B; **UNVERIFIED** as `hermes-4:14b` Ollama tag. |
| HF `Iambackup/Llama-4-Maverick-17B-128E-Instruct-Projected-Abliterated-GGUF` | ~232GB Maverick / ~65GB Scout | Abliteration (projected) | **HF-only. No Ollama uncensored library tag.** Official `llama4:scout` 67GB / `llama4:maverick` 245GB are **aligned**. |
| `huihui_ai/deepseek-r1-abliterated:70b` | 43GB (`:32b` 20GB, `:8b` 5.0GB latest) | Abliteration | Uncensored CoT distill. No 671B abliterated tag. |
| `coder3101/gemma-4-26B-A4B-it-heretic` + mradermacher Q4_K_M | 16.9GB | Heretic/ARA | 11/100, KL 0.0499. Huihui `:26b` 18GB does **not** ablate experts. |
| `igorls/gemma-4-12B-it-heretic-GGUF:latest` | 7.4GB (Q8_0 13GB) | Heretic/ARA | 0/100 genuine refusals, KL 0.0284. Small for this unconstrained list. |
| `Blackfrost-AI/Qwen3.8-27B-ABLITERATED-GGUF` Q4_K_M | 16.8GB | Heretic-family / llama.cpp | Confirmed GGUF; **not** official Ollama. `OBLITERATUS/Qwen3.8-27B-OBLITERATED` same class. |
| `jaahas/qwen3.5-uncensored:9b` | 7.4GB | HauhauCS (not the four named methods) | Not Dolphin / Hermes / Huihui / Heretic. |
| `huihui_ai/qwen3-abliterated:32b` / `:235b` | 20GB / 112GB | Abliteration | Older Qwen3 line; 74 tags, 258K pulls. |

**Missing on 2026 bases (do not invent):** Dolphin SFT and official Hermes SFT on Qwen 3.5 / 3.6 / 3.8, Gemma 4, or Llama 4. No uncensored Qwen 3.8-2.4T. No official Ollama `heretic` library tags. Aligned baselines people actually run under agents: `qwen3.8:27b` 18GB, `qwen3.6:27b` 18GB, `qwen3.5` 18.4M pulls — **not uncensored**.

Abliteration can add yes-man drift. That is community commentary, **UNVERIFIED as a formal score**.

---

## Pasted-list audit

Pasted shortlist from the seed table / `localaimaster` listicle. Verdicts are from the pasted-audit lens + VERIFY fetches on 26.08.2026.

| Pasted claim | Verdict | Evidence |
|---|---|---|
| `ollama pull dolphin3:8b` · 4.9GB · Llama 3.1 8B · Dolphin-style | **TRUE** | VERIFY `real=1`. Library heading “Dolphin 3.0 Llama 3.1 8B”. `dolphin3:latest` = `dolphin3:8b` = `d5ab9ae8e1f2` · 4.9GB · Q4_K_M · 8.03B · 128K. Five tags only. ~4M pulls. |
| `huihui_ai/qwen3-abliterated:14b` · 9.0GB | **TRUE** | Huihui/Sumandora. HF `huihui-ai/Qwen3-14B-abliterated`. Publisher 320/320 vs 76.88% base. |
| `mlabonne/gemma-3-27b-it-abliterated` as an **Ollama pull** | **WRONG-TAG** | HF exists (27B; GGUF Q4_K_M 16.5GB; layerwise/Sumandora; >90% acceptance **claimed**). No official `ollama.com/library` tag. Community clones only (`huihui_ai/gemma3-abliterated:27b`, `HammerAI/gemma-3-27b-abliterated`). |
| `huihui_ai/llama3.3-abliterated:70b` · 43GB | **TRUE** | VERIFY `real=1`. HTTP 200. `694ca93d4b6e · 43GB`. Manifest 42520398592 bytes. |
| `qwen3.8:27b` · 18GB · Qwen 3.8-27B | **TRUE tag, aligned (not uncensored)** | HF `Qwen/Qwen3.8-27B`. 18GB = 17GB Q4_K_M + 931MB projector. Abliterated sibling is `huihui_ai/Qwen3.8-abliterated:27b` 18GB. |
| `huihui_ai/Qwen3.8-abliterated:27b` · 18GB | **TRUE** | VERIFY `real=1`. Vision + tools + thinking. |
| `gemma4:26b` · 19GB · Gemma 4 26B-A4B | **TRUE tag, aligned (not uncensored)** | HF `google/gemma-4-26B-A4B-it` 25.2B/3.8B active. Ollama tag is `gemma4:26b` **not** `26b-a4b`. Official MMLU Pro 82.6%. |
| `dolphin3:24b` official library | **WRONG-TAG** | Library tags are 8B only (4.9 / 8.5 / 16GB). 24B is HF `dphn/Dolphin3.0-Mistral-24B` via `ollama create` (~13GB). |
| MMLU 68.0 vs 68.4 | **UNVERIFIED** | Not on these cards. Dolphin3.0-Llama3.1-8B lists MMLU-PRO **22.13**. Meta Llama 3.1 8B Instruct is 69.4 5-shot. Unsloth ~68.2. |
| “HausHaus” zero-refusal | **WRONG-TAG + UNVERIFIED** | Real org is **HauhauCS**. HF `HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF` (vendor 0/465). Independent forensic blog disputes lossless/zero on small sizes. Heretic-ARA reports 0/100 on Qwen3.8-27B. |
| Disk sizes quoted above | **No WRONG-VRAM** on those quoted sizes | 70B at 43GB is **not** a 24GB fit. |

**Skip as pulls:** `mlabonne/gemma-3-27b-it-abliterated`, `dolphin3:24b`, `HausHaus`.

---

## VERIFY log (this session)

| Claim | real | Quote |
|---|---|---|
| Official `dolphin3` latest is 8B 4.9GB, not 24B | **1** | `dolphin3:latest` 4.9GB; tags page 5 models; no 24B tag |
| `huihui_ai/Qwen3.8-abliterated` latest ~18GB with vision | **1** | `Qwen3.8-abliterated:latest` 18GB · 256K · Text, Image · chips vision/tools/thinking/27b |
| `huihui_ai/qwen3.5-abliterated:4B` ~3.3GB | **1** | `9acbd90c2645 · 3.3GB` Q4_K_M 4.54B (used on the this-box list) |
| `huihui_ai/llama3.3-abliterated:70b` ~43GB | **1** | `694ca93d4b6e · 43GB`; manifest 42520398592 bytes |

No `real=0` tags were promoted into the rank table.

---

## Sources (lens bundle)

- https://ollama.com/library/qwen3.5
- https://ollama.com/library/qwen3.6
- https://ollama.com/library/qwen3.8
- https://ollama.com/library/qwen3.8:27b
- https://ollama.com/library/gemma4
- https://ollama.com/library/llama4
- https://ollama.com/library/dolphin3
- https://ollama.com/library/dolphin3:8b
- https://ollama.com/library/dolphin3/tags
- https://ollama.com/library/hermes3
- https://ollama.com/library/hermes4
- https://ollama.com/huihui_ai
- https://ollama.com/huihui_ai/Qwen3.8-abliterated
- https://ollama.com/huihui_ai/Qwen3.6-abliterated
- https://ollama.com/huihui_ai/qwen3.5-abliterated
- https://ollama.com/huihui_ai/qwen3.5-abliterated/tags
- https://ollama.com/huihui_ai/qwen3-abliterated
- https://ollama.com/huihui_ai/qwen3-abliterated/tags
- https://ollama.com/huihui_ai/qwen3-abliterated:14b
- https://ollama.com/huihui_ai/llama3.3-abliterated
- https://ollama.com/huihui_ai/llama3.3-abliterated/tags
- https://ollama.com/huihui_ai/deepseek-r1-abliterated/tags
- https://ollama.com/huihui_ai/gemma3-abliterated/tags
- https://ollama.com/huihui_ai/gemma-4-abliterated
- https://ollama.com/huihui_ai/dolphin3-abliterated/tags
- https://ollama.com/huihui_ai/dolphin3-r1-abliterated/tags
- https://ollama.com/jacokon/qwen3.8-27b-heretic-ara
- https://ollama.com/steelpuddles/hermes-4.3-36B
- https://ollama.com/HammerAI/hermes-4.3
- https://ollama.com/igorls/gemma-4-E4B-it-heretic-GGUF
- https://ollama.com/igorls/gemma-4-12B-it-heretic-GGUF
- https://ollama.com/jaahas/qwen3.5-uncensored
- https://huggingface.co/Qwen/Qwen3.5-27B
- https://huggingface.co/Qwen/Qwen3.6-27B
- https://huggingface.co/Qwen/Qwen3.8-27B
- https://huggingface.co/google/gemma-4-31B-it
- https://huggingface.co/google/gemma-4-26B-A4B-it
- https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct
- https://huggingface.co/huihui-ai
- https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated
- https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF
- https://huggingface.co/huihui-ai/Huihui-Qwen3.6-27B-abliterated
- https://huggingface.co/collections/huihui-ai/qwen35-abliterated
- https://huggingface.co/collections/huihui-ai/qwen38-abliterated
- https://huggingface.co/collections/huihui-ai/qwen3-abliterated
- https://huggingface.co/collections/huihui-ai/gemma-4-abliterated
- https://huggingface.co/collections/huihui-ai/gemma3-abliterated-67d8127b4f273d6f4f0775ba
- https://huggingface.co/collections/huihui-ai/deepseek-r1-abliterated-6790ea12ce8c8c4e5df51b7f
- https://huggingface.co/huihui-ai/Llama-3.3-70B-Instruct-abliterated
- https://huggingface.co/huihui-ai/Qwen3-14B-abliterated
- https://huggingface.co/huihui-ai/gemma-3-12b-it-abliterated
- https://huggingface.co/huihui-ai/Huihui-gemma-4-31B-it-abliterated
- https://huggingface.co/huihui-ai/Huihui-gemma-4-26B-A4B-it-abliterated
- https://huggingface.co/huihui-ai/Huihui-gemma-4-E4B-it-abliterated
- https://huggingface.co/huihui-ai/Dolphin3.0-Llama3.1-8B-abliterated
- https://huggingface.co/huihui-ai/Dolphin3.0-R1-Mistral-24B-abliterated
- https://huggingface.co/trohrbaugh/Qwen3.8-27B-heretic-ara
- https://huggingface.co/trohrbaugh/gemma-4-31b-it-heretic-ara
- https://huggingface.co/heretic-org/Qwen3.8-27B-heretic-ara
- https://huggingface.co/heretic-org/models
- https://huggingface.co/p-e-w
- https://huggingface.co/p-e-w/gemma-4-E4B-it-heretic
- https://huggingface.co/p-e-w/gemma-4-E2B-it-heretic-ara
- https://huggingface.co/collections/coder3101/gemma-4-heretic
- https://huggingface.co/coder3101/gemma-4-31B-it-heretic
- https://huggingface.co/coder3101/gemma-4-26B-A4B-it-heretic
- https://huggingface.co/coder3101/gemma-4-E4B-it-heretic
- https://huggingface.co/mradermacher/gemma-4-31B-it-heretic-GGUF
- https://huggingface.co/mradermacher/gemma-4-26B-A4B-it-heretic-GGUF
- https://huggingface.co/mradermacher/gemma-4-E4B-it-heretic-GGUF
- https://huggingface.co/igorls/gemma-4-E4B-it-heretic
- https://huggingface.co/TrevorJS/gemma-4-31B-it-uncensored
- https://huggingface.co/TrevorJS/gemma-4-31B-it-uncensored-GGUF
- https://huggingface.co/TrevorJS/gemma-4-26B-A4B-it-uncensored
- https://huggingface.co/NousResearch/Hermes-4-14B
- https://huggingface.co/NousResearch/Hermes-4.3-36B
- https://huggingface.co/NousResearch/Hermes-4-70B
- https://huggingface.co/NousResearch/Hermes-4-405B
- https://huggingface.co/collections/NousResearch/hermes-4-collection-68a731bfd452e20816725728
- https://huggingface.co/NousResearch/Hermes-4.3-36B-GGUF
- https://huggingface.co/NousResearch/Hermes-4-14B-FP8
- https://huggingface.co/NousResearch/Hermes-4-405B-FP8
- https://huggingface.co/lmstudio-community/Hermes-4-70B-GGUF
- https://huggingface.co/lmstudio-community/Hermes-4-405B-GGUF
- https://huggingface.co/bartowski/NousResearch_Hermes-4-14B-GGUF
- https://huggingface.co/arnomatic/Hermes-4.3-36B-heretic
- https://huggingface.co/hrktos-37/Hermes-4-70B-heretic
- https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B
- https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B-GGUF
- https://huggingface.co/dphn/Dolphin3.0-Mistral-24B
- https://huggingface.co/dphn/Dolphin3.0-R1-Mistral-24B
- https://huggingface.co/collections/cognitivecomputations/dolphin-30-677ab47f73d7ff66743979a3
- https://huggingface.co/bartowski/cognitivecomputations_Dolphin3.0-Mistral-24B-GGUF
- https://huggingface.co/bartowski/cognitivecomputations_Dolphin3.0-R1-Mistral-24B-GGUF
- https://huggingface.co/datasets/QuixiAI/dolphin-r1
- https://huggingface.co/dphn/Dolphin3.0-Llama3.2-1B
- https://huggingface.co/dphn/Dolphin3.0-Llama3.2-3B
- https://huggingface.co/mradermacher/Dolphin3.0-Llama3.2-1B-GGUF
- https://huggingface.co/dphn/Dolphin-X1-8B
- https://huggingface.co/mlabonne/gemma-3-27b-it-abliterated
- https://huggingface.co/mlabonne/gemma-3-27b-it-abliterated-GGUF
- https://huggingface.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive
- https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF
- https://huggingface.co/Iambackup/Llama-4-Maverick-17B-128E-Instruct-Projected-Abliterated-GGUF
- https://huggingface.co/Blackfrost-AI/Qwen3.8-27B-ABLITERATED-GGUF
- https://huggingface.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED
- https://huggingface.co/RedHatAI/Llama-3.1-8B-Instruct
- https://github.com/Sumandora/remove-refusals-with-transformers
- https://github.com/p-e-w/heretic
- https://github.com/TrevorS/gemma-4-abliteration
- https://nousresearch.com/introducing-hermes-4-3/
- https://arxiv.org/abs/2508.18255
- https://erichartford.com/uncensored-models
- https://unsloth.ai/docs/models/qwen3.8
- https://unsloth.ai/docs/basics/dynamic-3.0-ggufs
- https://nathan.sapwell.net/posts/hauhaucs-abliteration-analysis/
- https://locallyuncensored.com/blog/gemma-4-local-guide.html (**UNVERIFIED** 17 GB Heretic tag)
- https://x.com/Teknium/status/2088912079558439041
- https://www.reddit.com/r/hermesagent/comments/1voapha/qwen_38_release_megathread/
- https://www.xda-developers.com/biggest-local-llm-machine-useless-cant-call-single-tool-how-many-parameters/
- https://www.heise.de/news/Wirklich-alles-lokal-Hermes-Agent-und-Qwen-3-6-11361489.html
- On-disk: `C:\Users\Prekzursil\.grok\dolphin-lens-handoff_2026-08-26.md`
- On-disk: `C:\Users\Prekzursil\.grok\ollama-llama33-abliterated-70b-size-handoff_2026-08-26.md`

No model was pulled in this write-up.
