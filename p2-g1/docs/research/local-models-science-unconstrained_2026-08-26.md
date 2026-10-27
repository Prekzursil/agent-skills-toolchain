# Local science models — unconstrained (agent brain) (26.08.2026)

*Generated: 26.08.2026 | Scope: **ignore VRAM** | Job: biochem / drug-discovery / Schrödinger copilot / Biomni-like **agent brain** | Sister (this GPU): `local-models-science-this-box_2026-08-26.md` | Confidence: High on tag existence (VERIFY `real=1` for Qwen3.8, MedGemma/TxGemma, and **no** `ollama pull biomni`); Medium on Schrödinger-script quality (no independent Maestro benchmark — **UNVERIFIED** if a blog claims one)*

Rank **native tool-calling** above a bio-tuned 7B that recites PubMed. A local model that cannot tool-call this estate’s stack is a **chat toy**.

---

## What the brain must drive (this estate)

Live science is **phenibut only** (`D:\Research\projects\phenibut`). Mechanism / hypothesis — **no dosing, regimens, sourcing**. Other `D:\Research\projects` children: `tooluniverse-wearables` (orchestration, code lives in `agent-skills-toolchain` `feat/tu-wearables-phase0`), `bolt` (**not** science). No fourth project name. `D:\basic-memory\projects\drug-discovery` exists with an **empty listing** — not a live program.

Must tool-call:

| # | Surface | Calls |
|---|---|---|
| 1 | Schrödinger MCP (`C:\Users\Prekzursil\source\repos\schrodinger-mcp\server.py`, `SCHRODINGER=D:\Program Files\Schrodinger 2026-2`) | `ligprep` / `glide_dock` / `prime_mmgbsa` / `qikprop_admet` / `pdb_fetch` / `pymol_render`; FEP+ **async/Modal** (Linux GPU, not the laptop) |
| 2 | ToolUniverse MCP (`D:\ToolUniverse`) | `find_tools` / `grep_tools` → `get_tool_info(full)` → `execute_tool`. Counts conflict **2526 vs 2206/511 vs ~2526/555** — do not collapse. Do **not** load ~2526 schemas at once (ToolFinderLLM = name+description only). |
| 3 | RDKit MCP | 74 tools |
| 4 | Claude Science | `http://127.0.0.1:8000` only after `cs ensure` **SUCCESS:cs-up**. HTTP **401 = ALIVE**. Slow = WEDGED host-RAM/SQLite (`cs fix`). |
| 5 | scholarly-access / Consensus / EuropePMC / Anelis | cookie jar `C:\Users\Prekzursil\.agents\secrets\enformation-cookies.txt` |
| 6 | optional hosted Biomni | `bm_*` + cookie-broker; rotate on `bm_billing_balance` |

Licensed Schrödinger **2026-2** is on disk (`glide.exe`, `fep_plus.exe`, `desmond.exe`, `jaguar.exe`, `qikprop.exe`, `sitemap.exe`, `prime_mmgbsa.exe`, `watermap.exe`, `ifd-md.exe`) plus kits at `D:\schrodinger` (`26-2.lic`). **License-bypass permanently declined.** GPU FEP+/Desmond/IFD-MD = Modal/Scaleway, not 6 GB laptop.

Live compute (26.08.2026): `modal_scripts`, `atm_gpn_harvest_2026-08-26` (`uwham_result.json`), `atm_rs_harvest_2026-08-26`, `jaguar_a2d`, `scaleway`, `_modal_mirror` (~39GB Schrödinger Linux kit). GABA-B SAR FEP baclofen→phenibut **ΔΔG = +1.74 ± 0.41** (supersedes retired +6.09). ATM-OpenMM R/S **−2.61**. α2δ Ki PMID 26234470. Hub README date 28.06.2026 is **STALE** vs BM 25–26.08.2026: Paper A ATM productions done, UWHAM still required; GPN UWHAM **NO-GO**; Modal remaining **$42.50** usage cap; α2δ FEP later **NO-GO** (neg-control fail).

Targets the brain will dossier via ToolUniverse: **CACNA2D1, GABBR1, GRK4/5, KCTD12/16, TAAR1, GABRD**.

---

## Biomni is hosted. It is not an Ollama tag.

| Claim | Fact (VERIFY `real=1` 26.08.2026) |
|---|---|
| Hosted Biomni Lab | `biomni.phylo.bio` (Phylo Inc). Claude Sonnet 4 + ~150-tool CodeAct (Bowtie2, GATK, AlphaFold, Seurat, …). Billable HPC/GPU sandboxes. 25 `bm_*` tools + local cookie-broker. |
| `ollama pull biomni` | **404.** `https://ollama.com/library/biomni` 404. `/library/biomni-r0` 404. registry `MANIFEST_UNKNOWN`. `/library?q=biomni` → No models. |
| Official local reasoner | HF **only**: `biomni/Biomni-R0-32B-Preview` (Qwen3-32B + RL in E1; 33B; MIT; BF16 repo 131GB; GGUF Q4_K_M **19.9GB**). Serve with SGLang, not `ollama pull biomni`. |
| R0-8B | **NOT** on the official HF org. |
| Blog “R0-32B 0.669 beating Claude 4” | **UNVERIFIED.** |

Honest local analog = open Biomni E1 + R0 **or** `qwen3:32b` as A1, plus **this estate’s MCP stack**. None equals hosted Claude+E1. Claude Science `:8000` is a workbench; `CUSTOM_MODEL_BASE_URL=:8000/v1` is a generic OpenAI-compat hint, not “Biomni local”.

---

## Rank 1–10 (ignore VRAM) — agent brain first

| Rank | Tag | GB | Method/job | Pull |
|---|---|---|---|---|
| **1** | `qwen3.8:27b` (`:latest`) | **18GB** | **Default Ollama agent brain.** Vision + tools + thinking, 256K. HF `Qwen/Qwen3.8-27B`: CoWorkBench 70.7, SWE-bench Pro 61.7, GPQA-D 89.2, TB2.1 73.0. VERIFY `real=1`. | `ollama pull qwen3.8:27b` |
| **2** | `glm-4.7-flash` (library) **or** HF `unsloth/GLM-4.7-Flash-GGUF:Q4_K_M` | **19GB** q4_K_M / **18.3GB** Unsloth / q8_0 **32GB** | Strongest published local **tool-use** card in the 30B class (τ²-Bench **79.5**, BrowseComp 42.8 vs Qwen3-30B 49.0/2.29). Vendor SWE-Verified **59.2%** — best *execute-repair* proxy for `$SCHRODINGER/run.exe`. Parser `glm47`. Needs Ollama ≥0.14.3. **`glm-4.7` (non-flash) library retired 2026-07-15** — do not `ollama pull glm-4.7`. If flash 404s, import the Unsloth GGUF. | `ollama pull glm-4.7-flash` **else** HF GGUF + `ollama create` |
| **3** | `qwen3-coder:30b` | **19GB** | Schrödinger / RDKit **CodeAct**. 30.5B/3.3B, 256K, tools. HF `Qwen/Qwen3-Coder-30B-A3B-Instruct`. `:480b` = **290GB** (250GB RAM floor) — lab cluster only. | `ollama pull qwen3-coder:30b` |
| **4** | `qwen3.6:27b` (`:35b-a3b` **23GB**) | **18GB** / 23GB | Same chips as 3.8 previous gen; MCPMark / MCP-Atlas on the 35B-A3B. Prefer **27B dense** on ~32GB host RAM. | `ollama pull qwen3.6:27b` |
| **5** | HF `biomni/Biomni-R0-32B-Preview` + mradermacher GGUF | **Q4_K_M 19.9GB** / Q5 **23.3GB** / Q8 **34.9GB** / BF16 repo **131GB** | **Only official local biomedical-agent reasoner.** Not an Ollama library tag. Eval1 = 433 instances / 10 bio-reasoning tasks. | **Do not** `ollama pull biomni`. HF GGUF + SGLang / `ollama create` |
| **6** | `qwen3:32b` | **20GB** (`:30b` **19GB** MoE) | Same Qwen3-32B **base as R0, no RL**. Best *library* plug-in for Biomni A1 `source=Ollama`. tools + thinking. | `ollama pull qwen3:32b` |
| **7** | `gemma4:26b` / `:31b` | **19GB** / **20GB** | Native function calling; Tau2 68.2 / 76.9. | `ollama pull gemma4:26b` |
| **8** | `gpt-oss:20b` (`:120b` **65GB**) | **14GB** / 65GB | General agentic + Python tools. Apache-2.0. | `ollama pull gpt-oss:20b` |
| **9** | `steelpuddles/hermes-4.3-36B` / HF `NousResearch/Hermes-4.3-36B-GGUF` | **22GB** / Q4_K_M **21.8GB** | XML `<tool_call>` after `<think>`. Official `hermes3:8b` **4.7GB** is the library tools chip (no thinking). Hermes-4-14B HF GGUF ~9GB — not official Ollama library. | `ollama pull steelpuddles/hermes-4.3-36B` |
| **10** | `qwen3.5:9b` (`:latest`; `:27b` **17GB**) | **6.6GB** / 17GB | RAM-safe VL fallback with tools + thinking. 3.5 latest is **9B not 27B**. | `ollama pull qwen3.5:9b` |

**Default workstation brain (24GB class):** #1.  
**Default Schrödinger execute-repair:** #2 then #3.  
**Default Biomni-like reasoner:** #5 (HF) or #6 (Ollama library).  
**Estate ~32GB RAM:** prefer 18GB tags (#1/#4) over 23GB 35B-A3B.

No local LLM writes correct Schrödinger `run.exe` scripts out of the box. Copilot pattern: **agentic coder (#2/#3) + RAG of Schrödinger Python API 2026-1 + iterate on Job Control stderr**. Glide: `get_glide_job().writeSimplified('dock.in')` then `$SCHRODINGER/glide`. LigPrep: `$SCHRODINGER/ligprep -isd/-ismi -omae -WAIT`. Utility: `$SCHRODINGER/run script.py` / Windows `%SCHRODINGER%\run.exe`. Reject: `pip install schrodinger`; `python job.py` without `run.exe`; invented FEP+ CLI; `-omae *.sdf`.

---

## Science sidecars (not the MCP brain)

These talk SMILES / ADMET / papers. They do **not** replace #1 for ToolUniverse / Schrödinger MCP.

| Rank | Tag | GB | Method/job | Pull |
|---|---|---|---|---|
| S1 | HF `google/txgemma-9b-chat` (bartowski GGUF) | Q4_K_M **5.76GB** / Q8 **9.83GB** / BF16 **18.49GB** | Therapeutics **CHAT** + TDC Drug SMILES / ADMET. Chat at 9B and 27B only; 2B is **predict-only**. VERIFY `real=1` (HF sizes). **No** `ollama.com/library/txgemma` (**404**). | HF GGUF + `ollama create` — **not** `ollama pull txgemma` |
| S2 | `medgemma1.5:4b` / HF `google/medgemma-1.5-4b-it` | **3.3GB** | Medical **CHAT VLM** — figures / lab PDF extraction. Google card **forbids diagnosis / treatment**. | `ollama pull medgemma1.5:4b` |
| S3 | `medgemma:4b` / `:27b` | **3.3GB** / **17GB** | Official Ollama (311.6K downloads). 27B is multimodal, **not** the text-only literature model. Text-only literature pick is HF `google/medgemma-27b-text-it` (PubMedQA 76.8; GGUF Q4_K_M ~**16.5GB**). | `ollama pull medgemma:4b` |
| S4 | HF `OpenDFM/ChemDFM-v1.5-8B` or `ChemDFM-v2.0-14B` / `ChemDFM-R-14B` | ~8B BF16; 14B ~**29.5GB**; R GGUF Q4_K_M **9.1GB** | Chemistry CHAT, SMILES + reactions. **ChemDFN does not exist** (HF/Ollama miss this fetch). | HF — **no official Ollama chemistry/SMILES library model** |
| S5 | HF `AI4Chem/ChemLLM-7B-Chat-1.5-DPO` | ~15.5GB / GGUF **4.71GB** | SMARTS reactions. Blog Ollama `chemllm` tags **UNVERIFIED**. | HF GGUF |
| S6 | `adrienbrault/biomistral-7b` / HF `BioMistral/BioMistral-7B-GGUF` | **4.4GB** / Q4_K_M **4.37GB** | Biomedical CHAT. **2048 ctx, no FC protocol — do not use as MCP brain.** | community Ollama only |
| S7 | HF `aaditya/Llama3-OpenBioLLM-8B` GGUF | Q4_K_M **4.92GB** | Biomedical CHAT. Demo is warfarin pill-splitting — **unsafe chat-doctor**. GPT-4/Med-PaLM SOTA table is self-reported, paper “coming soon” (**UNVERIFIED**). **Not** on `ollama.com/library`. | HF / community `koesn/llama3-openbiollm-8b` **4.9GB** |
| S8 | HF `microsoft/NatureLM-8x7B-Inst` | Q4_K_M **28.5GB** / Inst BF16 **93.5GB** | Generative science MoE. Official collection has **only** 8x7B / 8x7B-Inst. **1B/8B paper-only UNVERIFIED.** | HF GGUF |
| S9 | MolScribe **1.13GB** + RxnScribe **0.43GB**; MolT5-large **3.13GB**; Text+Chem T5 **0.89GB** | as listed | Paper/caption → SMILES. Not chat LLMs. | HF |
| S10 | `meditron:7b` / `:70b` | **3.8GB** / **39GB** | Llama-2 PubMed CPT, **not** instruction-tuned, cutoff Aug 2023, 2K/4K ctx. Completion-over-abstracts only. Authors: not adapted to deliver knowledge safely. | `ollama pull meditron:7b` as completion **only** |

**SKIP as brain:** BioMistral-7B, Meditron-7B, `glm4:9b` (no tools badge), ChemBERTa (encoder-only Fill-Mask, 92.1M), ChemBFN (not chat), OpenBioLLM-70B 141GB, LlaSMol (official LoRA-only). **DECIMER HF card UNVERIFIED** this fetch.

Prompt-lock every medical sidecar to **extract mechanisms/citations**. Never prescribe.

---

## Schrödinger coder ladder (same brain list, coding angle)

| Rank | Tag | GB | Job |
|---|---|---|---|
| 1 | `qwen3-coder:30b` | 19GB | Best workstation Glide/LigPrep script agent. |
| 2 | `glm-4.7-flash` q4_K_M | 19GB | Execute-repair (SWE 59.2). |
| 3 | `qwen2.5-coder:32b` | **20GB** (`:14b` 9.0GB / `:7b` 4.7GB) | Dense Python; 32K Ollama / 128K YaRN. |
| 4 | `devstral:24b` | **14GB** | Multi-file `.in` / launch-script editor. Ollama SWE 46.8% vs HF Devstral-Small-2507 53.6%. |
| 5 | `deepseek-coder-v2:16b` | **8.9GB** | RAM-safe 160K. Year-stale. `:236b` 133GB. |
| 6 | `codestral:22b` | **13GB** | FIM for Glide `.in`, **not** agentic Job Control. |

**NOT picks for Maestro:** ChemLLM / LlaSMol / TxGemma (no `run.exe` evidence; ChemLLM/LlaSMol/TxGemma are not on `ollama.com/library` as Schrödinger copilots).

---

## Commands (copy)

```text
# Default science agent brain (VERIFY real=1)
ollama pull qwen3.8:27b

# Schrödinger execute-repair (if library 404 → Unsloth GGUF)
ollama pull glm-4.7-flash
ollama pull qwen3-coder:30b

# Biomni-like library stand-in (NOT ollama pull biomni)
ollama pull qwen3:32b

# Literature VLM sidecar (not the brain)
ollama pull medgemma1.5:4b

# RAM-safe tools fallback
ollama pull qwen3.5:9b
```

**Do not run:**

```text
ollama pull biomni                 # 404 — hosted Lab is biomni.phylo.bio
ollama pull biomni-r0              # 404
ollama pull txgemma                # 404 — HF google/txgemma-9b-chat GGUF instead
ollama pull glm-4.7                # retired 2026-07-15
ollama pull glm-4.6                # retired
ollama pull chemdfn                # does not exist; chemistry LLM is ChemDFM
ollama pull linq
```

---

## Honourable / large

| Item | GB | Note |
|---|---|---|
| `qwen3.5:122b-a10b` | 81GB | Largest local VL MoE on official Ollama. |
| `llama3.3:70b` | 43GB | General tool-use scale fallback. |
| `frob/minimax-m2.5:230b` | **138GB** | Community local MiniMax. **Official** `minimax-m2.7` / `minimax-m3` Ollama tags are **cloud**, not local. |
| Unsloth `GLM-4.5-Air-GGUF:Q4_K_M` | **73GB** | Native FC+thinking; parser `glm45`. Official `glm-4.7`/`4.6` Ollama retired. |
| GLM-4.6V-Flash 9B | GGUF GB **UNVERIFIED** this fetch | HF multimodal FC. Do not invent a GB. |
| `qwen3.8:27b-q8_0` | 30GB | Same #1, higher fidelity. |

---

## Sources (fetched 26.08.2026)

- https://ollama.com/library/qwen3.8 — VERIFY `real=1`
- https://huggingface.co/Qwen/Qwen3.8-27B · https://ollama.com/library/qwen3.6 · https://ollama.com/library/qwen3-coder · https://ollama.com/library/qwen3.5 · https://ollama.com/library/qwen3
- https://ollama.com/library/glm-4.7-flash · https://huggingface.co/zai-org/GLM-4.7-Flash · https://huggingface.co/unsloth/GLM-4.7-Flash-GGUF · https://ollama.com/library/glm-4.7 (retired)
- https://huggingface.co/biomni/Biomni-R0-32B-Preview · https://huggingface.co/biomni · https://ollama.com/library/biomni **404** — VERIFY `real=1` (no drop-in)
- https://raw.githubusercontent.com/snap-stanford/Biomni/main/README.md · https://docs.biomni.phylo.bio/faq
- https://huggingface.co/google/txgemma-9b-chat · https://huggingface.co/bartowski/google_txgemma-9b-chat-GGUF · https://ollama.com/library/txgemma **404**
- https://ollama.com/library/medgemma · https://ollama.com/library/medgemma1.5 · https://huggingface.co/google/medgemma-1.5-4b-it · https://huggingface.co/google/medgemma-27b-text-it
- https://huggingface.co/OpenDFM/ChemDFM-v1.5-8B · https://huggingface.co/OpenDFM/ChemDFM-v2.0-14B · https://huggingface.co/BioMistral/BioMistral-7B
- https://huggingface.co/aaditya/Llama3-OpenBioLLM-8B · https://ollama.com/library/meditron · https://huggingface.co/epfl-llm/meditron-7b
- https://learn.schrodinger.com/public/python_api/2026-1/api/schrodinger.application.glide.job.html
- https://docs.ollama.com/capabilities/tool-calling.md
- https://zitniklab.hms.harvard.edu/bioagent/api/tooluniverse.tool_finder_llm.html
