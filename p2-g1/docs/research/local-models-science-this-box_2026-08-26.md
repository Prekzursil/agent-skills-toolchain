# Local science models — this box only (26.08.2026)

*Generated: 26.08.2026 | Scope: **RTX 4050 Laptop 6141 MiB GPU-full only** | Job: phenibut agent brain that **tool-calls** Schrödinger / ToolUniverse / RDKit / Claude Science / scholarly-access | Sister (ignore VRAM): `local-models-science-unconstrained_2026-08-26.md` | Confidence: High on envelope + installed `qwen2.5:7b` tools; High that **14B+ GPU-full is NO**; High that `ollama pull biomni` is 404*

Do **not** mix this list with the unconstrained ranking. **Explicit NO 14B+.** A 5.76GB TxGemma-9B Q4 is also **over cap**. A bio-tuned 7B that cannot emit `tool_calls` is a chat toy next to this stack.

---

## Hardware envelope (measured)

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce **RTX 4050 Laptop** |
| VRAM | **6141 MiB** |
| GPU-full rule | weights + **1024 MiB KV** < 6141 → weights **≤ 5117 MiB** (~5.36 GB SI) |
| Proven tools envelope | installed `qwen2.5:7b` **4466 MiB** Q4_K_M (listed ~4.4–4.7GB) + KV = **5490**, leftover **651 MiB** |
| Already installed | `qwen2.5:7b` (tools-confirmed), `qwen2.5:3b` 1.9GB, `nomic-embed-text` |
| Broken | `blackgrg26/WORMGPT-13:latest` — size dash, no weights. Ignore. |
| Schrödinger GPU jobs | FEP+ / Desmond / IFD-MD are **Linux/Modal**, not this 6 GB laptop. Local brain **proposes** and calls MCP; Modal runs the GPU physics. |

**9B / 14B+ do not GPU-fit** even as MoE. `qwen3.5:9b` **6.6GB** is NO. `qwen3.8:27b` **18GB** is unconstrained #1, not this file.

---

## Rank 1–N — science/tool-calling that FIT

Hardware-agent order: installed `qwen2.5:7b` → `qwen2.5-coder:7b` → `phi4-mini` or `qwen3:4b`. Sidecars after the brain.

| Rank | Tag | GB | Method/job | Pull |
|---|---|---|---|---|
| **1** | `qwen2.5:7b` | **~4.4–4.7GB** | **INSTALLED. Tools-confirmed.** Default MCP brain on this card for `find_tools` → `execute_tool`, Schrödinger MCP, RDKit 74, scholarly-access. | already on disk |
| **2** | `qwen2.5-coder:7b` | **4.7GB** | Code-shaped args: LigPrep/Glide `.in`, RDKit Python, `%SCHRODINGER%\run.exe` repair. Still a 7B — it will **not** emit correct Job Control first try; iterate on stderr. | `ollama pull qwen2.5-coder:7b` |
| **3** | `qwen3:4b` (`:4b-thinking`) | **2.5GB** | Current-gen thinking, 256K listed. Comfortable GPU-full. Mechanism/hypothesis planner, then hand off to #1 for tools. | `ollama pull qwen3:4b` |
| **4** | `phi4-mini` | **2.5GB** | Comfortable helper; short-form tool args. | `ollama pull phi4-mini` |
| **5** | `hermes3:8b` | **4.7GB** | Official Ollama **tools** chip (no thinking). Native `<tool_call>`. Tight 8B. | `ollama pull hermes3:8b` |
| **6** | `llama3.1:8b` | **4.9GB** | General 8B. Tight GPU-full, short ctx. Weaker 2026 tool loop than #1. | `ollama pull llama3.1:8b` |
| **7** | `mistral:7b` | **4.4GB** | GPU-full with more KV leftover than 8B. Older instruct. | `ollama pull mistral:7b` |
| **8** | `qwen2.5:3b` | **~1.9GB** | **INSTALLED.** Tiny helper when host RAM is dying. | already on disk |
| **9** | `medgemma1.5:4b` / `medgemma:4b` | **3.3GB** | Literature / figure **sidecar**, not the brain. Extract mechanisms from PDFs. Google forbids diagnosis/treatment. VERIFY `real=1` (Ollama 3.3GB + HF sizes). | `ollama pull medgemma1.5:4b` |
| **10** | `llama3.2:3b` | (3B class; FIT) | Last-include tiny instruct. Prefer #8 if already installed. | `ollama pull llama3.2:3b` |

Optional FIT sidecars (not brains):

| Tag | GB | Job | Pull |
|---|---|---|---|
| HF ChemLLM-7B GGUF | **4.71GB** | SMARTS/reactions talk | HF GGUF + `ollama create` — no official Ollama chemistry library model |
| community `adrienbrault/biomistral-7b` | **4.4GB** | Biomedical QA, **2048 ctx, no FC** — last-include sidecar only | community; **do not** make it the MCP brain |
| `command-r7b` | **5.1GB** | Native citations over retrieved papers. Tight. CC-BY-NC. | `ollama pull command-r7b` |
| HF OpenBioLLM-8B GGUF | **4.92GB** | **Avoid as doctor** (warfarin-splitting demo). Prompt-lock to mechanisms if used at all. | not official library |
| `meditron:7b` | **3.8GB** | Completion-over-abstracts only (2K ctx, not chat). | `ollama pull meditron:7b` |
| MolScribe / RxnScribe / MolT5 / Text+Chem T5 | 0.43–3.13GB | caption/figure → SMILES | HF, not Ollama chat |

Do **not** load BioMistral or Meditron as the ToolUniverse brain. Do **not** load ~2526 ToolUniverse schemas into a 7B context; use `find_tools` name+description first.

### Default on this box

- **MCP brain:** #1 installed `qwen2.5:7b`.
- **Schrödinger/RDKit scripts:** swap #2 `qwen2.5-coder:7b`.
- **Thinking / SAR hypothesis:** #3 `qwen3:4b`, then tools on #1.
- **Paper figures:** #9 `medgemma1.5:4b`.
- **Citations:** tight swap to `command-r7b`.

On 8B keep `num_ctx` 2048–4096. Claude Science `127.0.0.1:8000`: HTTP **401 means ALIVE**. Do not “fix” a 401 by killing the daemon. Slow = WEDGED (`cs ensure` / `cs fix`).

Hosted Biomni (`bm_*`) stays **cloud**. It is not replaced by anything in this table.

---

## Explicit NO (14B+ and over-cap)

| Tag | GB | Why NO |
|---|---|---|
| `qwen3.8:27b` | **18GB** | Unconstrained default brain. |
| `glm-4.7-flash` / Unsloth GLM-4.7-Flash Q4 | **19 / 18.3GB** | Best local tool-use card — not 6 GB. |
| `qwen3-coder:30b` | **19GB** | Best Maestro copilot — not 6 GB. `:480b` 290GB absurd here. |
| `qwen3.6:27b` / `:35b` | 18 / 23GB | |
| `qwen3:32b` / `:30b` | 20 / 19GB | Biomni A1 stand-in. |
| HF `biomni/Biomni-R0-32B-Preview` Q4 | **19.9GB** | Only official local Biomni reasoner — still 32B. **Also** `ollama pull biomni` is **404**. |
| `qwen3.5:9b` | **6.6GB** | Over 5117 MiB. |
| `qwen3:14b` / `qwen2.5-coder:14b` | **9.3 / 9.0GB** | 14B+. |
| HF `google/txgemma-9b-chat` Q4_K_M | **5.76GB** | Over cap (~5.76 GB > 5.36 GB SI). 27B-chat 16.6GB+ also NO. **No** `ollama pull txgemma` (404). |
| `medgemma:27b` | **17GB** | Literature 27B is unconstrained / HF text-it ~16.5GB. |
| ChemDFM-v2.0-14B / ChemDFM-R Q4 | ~29.5 / **9.1GB** | 14B+. |
| NatureLM-8x7B-Inst Q4 | **28.5GB** | 1B/8B NatureLM **UNVERIFIED**. |
| `gpt-oss:20b` | **14GB** | |
| `devstral:24b` / `codestral:22b` / `deepseek-coder-v2:16b` | 14 / 13 / **8.9GB** | 16B+ NO. Coder-V2 Lite is 16B. |
| Hermes-4-14B / Hermes-4.3-36B | ~9 / 22GB | 14B+. Use `hermes3:8b` only. |
| `llama3.3:70b` / OpenBioLLM-70B | 43 / 141GB | |
| MiniMax official Ollama | cloud | `m2.7` / `m3` are **cloud**, not local. `frob/minimax-m2.5:230b` 138GB NO. |

CPU/offload of 14B+ is **not** GPU-full. Do not report it as a this-box science win. This laptop does **not** run FEP+ / Desmond / IFD-MD; those stay Modal.

---

## Commands (this box)

```text
# Brain already installed
ollama run qwen2.5:7b

# Schrödinger / RDKit script twin
ollama pull qwen2.5-coder:7b

# Thinking planner with KV headroom
ollama pull qwen3:4b

# Official tools chip (pick ONE 8B)
ollama pull hermes3:8b

# Literature VLM sidecar
ollama pull medgemma1.5:4b
```

**Do not run on this GPU:**

```text
ollama pull qwen3.8:27b
ollama pull qwen3-coder:30b
ollama pull qwen3.5:9b
ollama pull qwen3:14b
ollama pull medgemma:27b
ollama pull gpt-oss:20b
ollama pull biomni              # 404 — hosted biomni.phylo.bio
ollama pull txgemma             # 404; 9B Q4 5.76GB would not GPU-full anyway
ollama pull glm-4.7             # retired
ollama pull chemdfn             # does not exist
```

---

## Phenibut loop on 6 GB (honest)

1. Hypothesis / SAR in `qwen3:4b` or installed `qwen2.5:7b` (mechanism only).
2. ToolUniverse: `find_tools` → `get_tool_info` → `execute_tool` for CACNA2D1 / GABBR1 / GRK4/5 / KCTD12/16 / TAAR1 / GABRD dossiers.
3. Schrödinger MCP on **Windows CPU/Maestro path** for LigPrep / Glide / QikProp / Prime-MMGBSA; FEP+ launch scripts for **Modal**.
4. RDKit MCP for descriptors/filters.
5. Literature: scholarly-access / Anelis cookie jar; MedGemma 4B for figure extraction.
6. Optional: hosted Biomni `bm_*` (cloud, watch `bm_billing_balance`). Modal remaining **$42.50** cap as of 26.08.2026 BM notes.

None of this is clinical advice.

---

## Sources

Hardware FIT list this session. Science cards 26.08.2026 as in `local-models-science-unconstrained_2026-08-26.md`. Estate inventory: `estate-research-science-scope_2026-08-26.md` + `estate-lens-handoff_2026-08-26.md`. VERIFY `real=1`: MedGemma/TxGemma exist with quoted sizes; `ollama.com/library/biomni` 404; `ollama.com/library/txgemma` 404.
