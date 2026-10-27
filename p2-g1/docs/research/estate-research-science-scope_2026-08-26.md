# Estate research / science / offensive scope (26.08.2026)

*Generated: 26.08.2026 | Inventory of this machine’s research surface so local-model rankings have a real job, not a generic “science LLM” list. Not a G-1 2007 claim. No git commit.*

This is the **scope map**. Dual-rank local-model reports (unconstrained vs RTX 4050 6 GB) are produced by the `/local-deep-research` workflow into sibling files under this folder.

---

## What “research” means on this box

Three layers, not one dump:

| Layer | Path / surface | Role |
|---|---|---|
| **Computational science hub** | `D:\Research` (`noosphere · atlas · lyceum`) | Git monorepo. Flagship **phenibut** comp-pharm. Second project **tooluniverse-wearables**. Also `bolt`. |
| **Semantic memory** | `D:\basic-memory` (MCP `127.0.0.1:8765`) | Durable notes: phenibut compounds/targets/DDI, Biomni maps, CSIE backends, harness decisions. |
| **Agent research harness** | `~/.claude/skills/deep-research` + Grok `/deep-research` | FACT/RACE-style multi-source research. Grok built-in is web-claim/verify. This file + `/local-deep-research` is the **local-model** expansion. |

`~/Cowork/` is an **archive**, not the dump. Project receipts for phenibut go in `D:\Research\projects\phenibut\docs\` and `compute\`.

---

## `D:\Research` evaluation

**Purpose (from its README):** self-contained computational-research hub. Organizing rule: every folder carries a README. Provenance over assertion (PMID / ChEMBL / run-log). Secrets never committed. Bulk binaries on Google Drive (`!!!★DATA-ON-GDRIVE/MANIFEST.md`).

**Projects (measured 26.08.2026):**

| Project | What it is |
|---|---|
| `projects/phenibut/` | Main program: docs, compute, corpus, memory, Modal Schrödinger kit under `_modal_mirror` (~39 GB, gitignored). `docs/` still active 26.08.2026. |
| `projects/tooluniverse-wearables/` | ToolUniverse + wearables. |
| `projects/bolt/` | Present as a third project directory. |
| `tools/` | Small reusable claude-compute harness. |
| `consensus-downloads/` | Literature pulled via Consensus. |

**Tooling named in the hub README (status dated 28.06.2026 — treat as stale vs live notes):**

- Schrödinger Suite **2026-2 (Build 121)** — Glide, Prime/MM-GBSA, FEP+, SiteMap, Jaguar, Desmond. MCP `schrodinger`. License portable across Modal accounts. **License-bypass route permanently declined.**
- Modal — cloud GPU for FEP+/Desmond + ATM-OpenMM.
- ToolUniverse (README said 2,526 tools; phenibut-compchem skill says 2,206 — **do not collapse**; workflow must re-count live).
- RDKit, ATM-OpenMM, basic-memory.

**Safety boundary:** mechanism / hypothesis generation only. No dosing, regimens, titration, sourcing, or personalized medical guidance.

**Staleness:** hub README “current status” is **28.06.2026** (GABA-B SAR FEP **+1.74 ± 0.41**; α2δ pose-fix FEP-ready). Live basic-memory notes from **25–26.08.2026** are ahead of that README (Paper A ATM/UWHAM, GPN, Modal remaining $42.50 usage cap). Ranking local models against “what science happens here” must use the **notes + `projects/phenibut/docs/`**, not the June README alone.

**Sister trees on D:**

| Path | Role |
|---|---|
| `D:\schrodinger`, `D:\sch_install`, `D:\Program Files\Schrodinger 2026-2` | Licensed suite install (authoritative env `SCHRODINGER`). |
| `D:\ToolUniverse` | Local ToolUniverse checkout. |
| `D:\ai-models` | `lmstudio/`, `ollama/` model stores. |
| `D:\knowledge` | Offline security corpora: HackTricks, GTFOBins, LOLBAS, Atomic Red Team, OWASP WSTG + CheatSheets, PayloadsAllTheThings. |
| `D:\fep_c3_rundir` | FEP run directory. |
| `D:\basic-memory\phenibut\` | compounds, targets, ddi, analogs, tooluniverse, verifications, adjudications. |
| `D:\basic-memory\research\` | Biomni hosted API maps, CSIE compute backends, uncensored-local-LLMs 26.08.2026. |
| `D:\basic-memory\projects\` | `drug-discovery`, `claude-science`, `phenibut`, harness, gem-hunt, many others. |

---

## Biomni vs local science stack (do not confuse)

**Biomni Lab** (`biomni.phylo.bio`, Phylo) is a **hosted** biomedical agent with HPC/GPU sandboxes. This estate drives it through cloud-hub `bm_*` tools + a local cookie-broker. It is **not** a GGUF you pull with Ollama. Skill: `drive-biomni-lab`. Notes: `research Biomni hosted MCP connector feasibility 2026-07-07.md`.

**Local analog (what a “Biomni-like local model” must actually drive):**

| Piece | Local surface |
|---|---|
| Compchem / life-science UI | Claude Science WSL2 daemon `127.0.0.1:8000` (`claude-science-local`; HTTP 401 = alive) |
| Structure / FEP / ADMET | Schrödinger MCP + PyMOL 3.1.7 Incentive |
| 2k+ bio tools | ToolUniverse MCP (`find_tools` → `execute_tool`) |
| Chemistry descriptors | RDKit MCP (74 tools) |
| Literature | scholarly-access, Consensus, EuropePMC/OpenAlex via ToolUniverse; Anelis Plus cookie jar already on disk |
| Agent brain | **this ranking** — local LLM that can tool-call that stack |

A local model that cannot tool-call is a chat toy next to this stack. Rank **agent/tool models** above “bio-tuned 7B that recites PubMed.”

---

## Science / drug-discovery session extent (measured, not guessed)

Active skills on this estate that define the science scope:

`phenibut-compchem`, `schrodinger-maestro-driver`, `structure-based-screening`, `comp-pharm-cascade`, `compchem-validators`, `qdx-rush`, `mol-filters`, `cheminformatics-rdkit`, `tooluniverse`, `create-tooluniverse-skill`, `drug-discovery-literature-bridge`, `consensus-tooluniverse-research`, `biomedical-paper-triage`, `scholarly-literature-review`, `oa-pdf-retrieval`, `claude-science-local`, `drive-biomni-lab`.

Phenibut program shape (from skills + hub, not a new experiment): GABA-B (7EB2/7C7Q/6UO8) Glide → MM-GBSA → FEP+; α2δ pose-fix; enantioselectivity; DDI; ToolUniverse target dossiers (CACNA2D1, GABBR1, GRK4/5, KCTD12). Schrödinger GPU jobs (IFD-MD, FEP+, Desmond) are **Linux/Modal**, not the 6 GB laptop.

Grok `/deep-research` (built-in) is a **web claim/verify workflow**, not a local-model picker. Claude `deep-research` skill is the FACT/RACE harness over Exa/Tavily/SearXNG/scholarly-access/ToolUniverse. **Gap this expansion fills:** pick **which local weights** sit under those harnesses when cloud quota is tight.

---

## Offensive / red-team / pentest scope (estate-local)

Authorized by owner-ops for **this machine and owned targets**. Local knowledge:

- `D:\knowledge` corpora (HackTricks, GTFOBins, LOLBAS, Atomic Red Team, OWASP, PayloadsAllTheThings)
- Skills: `hacktricks`, `hacktricks-api`, `secsearch`, `hexstrike-ai-*`, `cyberstrike`, `frida`, `ghidra-*`, `ida-*`, `binary-ninja`, `angr`, `capa-triage`, `malware-analysis-triage`

A “best offensive local model” here must: follow tool-call schemas, not refuse dual-use *authorized* work, and cite local corpora instead of inventing CVEs. WhiteRabbitNeo / abliterated Qwen / Dolphin are candidates to **verify live**, not a shopping list from 2024 blogs.

---

## Hardware envelope (do not mix into unconstrained ranks)

Last measured this session: **RTX 4050 Laptop, 6141 MiB**. GPU-full cap ≈ weights + 1024 MiB KV under 6141 → weights **≤ 5117 MiB**. Installed aligned control: `qwen2.5:7b` ~4.4 GB. 14B+ is **NO** for GPU-full on this card (offload/CPU is a different rank, label it).

---

## Deliverables the workflow must write

Under `C:\Users\Prekzursil\source\ast-integrate\docs\research\` (never overwrite; `_v2`/`_v3`):

1. `local-deep-research-unconstrained_YYYY-MM-DD.md`
2. `local-deep-research-this-box_YYYY-MM-DD.md`
3. `local-models-science-unconstrained_YYYY-MM-DD.md` (biochem, drug discovery, Schrödinger/Biomni-like **agent brain**)
4. `local-models-science-this-box_YYYY-MM-DD.md`
5. `local-models-offensive-unconstrained_YYYY-MM-DD.md`
6. `local-models-offensive-this-box_YYYY-MM-DD.md`

Each unconstrained file: rank 1–10, tag, GB, method, pull, URLs. Each this-box file: only GPU-full fits, explicit NO for 14B+. Flag UNVERIFIED. Do not invent Ollama tags.

This estate-scope file is the seventh artifact; the workflow may append a VERIFY log, not replace it.

---

## VERIFY log (appended 26.08.2026)

Inventory above is **unchanged**. Dual-rank reports written the same day (never overwrite; these names did not already exist):

| # | Path |
|---|---|
| 1 | `C:\Users\Prekzursil\source\ast-integrate\docs\research\local-deep-research-unconstrained_2026-08-26.md` |
| 2 | `C:\Users\Prekzursil\source\ast-integrate\docs\research\local-deep-research-this-box_2026-08-26.md` |
| 3 | `C:\Users\Prekzursil\source\ast-integrate\docs\research\local-models-science-unconstrained_2026-08-26.md` |
| 4 | `C:\Users\Prekzursil\source\ast-integrate\docs\research\local-models-science-this-box_2026-08-26.md` |
| 5 | `C:\Users\Prekzursil\source\ast-integrate\docs\research\local-models-offensive-unconstrained_2026-08-26.md` |
| 6 | `C:\Users\Prekzursil\source\ast-integrate\docs\research\local-models-offensive-this-box_2026-08-26.md` |

Hardware used in this-box files: RTX 4050 Laptop **6141 MiB**; GPU-full weights **≤ 5117 MiB**; **NO 14B+**. Installed aligned control `qwen2.5:7b` ~4.4GB. Broken stub flagged: `blackgrg26/WORMGPT-13`.

### Probe results (real=1 / do-not-invent)

| Probe | real | Evidence (fetched 26.08.2026) |
|---|---|---|
| `ollama.com/library/qwen3.8` **or** `huihui_ai/Qwen3.8-abliterated` exists with a GB size | **1** | `/library/qwen3.8` live: `qwen3.8:latest` / `:27b` / `:27b-mlx` **18GB**; 827.3K downloads. `huihui_ai/Qwen3.8-abliterated:latest` / `:27b` **18GB**; 32K downloads. |
| WhiteRabbitNeo has a current HF or Ollama tag (not only 2024 blogs) | **1** | Live Ollama `WhiteRabbitNeo/WhiteRabbitNeo-V3-7B:latest` **15GB** (7757 downloads). HF V3-7B now renders as `DeepHat/DeepHat-V1-7B` (Aug 14 2025, 13232 DL/mo). `/library/whiterabbitneo` **404** — that library path is an error, not the org tag. |
| TxGemma **or** MedGemma exists on HF or Ollama with a quoted size | **1** | HF `google/txgemma-27b-predict` 27B; MedGemma Ollama `medgemma:4b` **3.3GB** / `:27b` **17GB**. Negative control: `/library/txgemma` **404**. |
| Official `ollama.com/library/dolphin3` latest is **8B not 24B** | **1** | Title “Dolphin 3.0 Llama 3.1 8B”; `dolphin3:latest` **4.9GB**; tags all `8b-*`; digest `d5ab9ae8e1f2`. Do not invent `dolphin3:24b`. |
| Foundation-Sec (or similarly named) has a live HF or Ollama page | **1** | HF `fdtn-ai/Foundation-Sec-8B` live (8B, Apr 28 2025) plus Instruct (Aug 1 2025) and Reasoning (Jan 28 2026). `/library/foundation-sec` **404**. Community `FenkoHQ/Foundation-Sec-8B` **16GB**. |
| No `ollama pull biomni` as a drop-in Biomni Lab replacement | **1** | `/library/biomni` **404**; `/library/biomni-r0` **404**; registry `MANIFEST_UNKNOWN`. Hosted Lab is `biomni.phylo.bio`. Official local reasoner is HF `biomni/Biomni-R0-32B-Preview` (33B, SGLang) — not an Ollama tag. |

**Do not invent (404 / absent this fetch):** `command-r-search` (CLI plugin, not a model), `linq`, `qwen3-reranker`, `qwen3-vl-embedding`, `command-a-vision`, `txgemma` library, `glm-4.7` (retired 2026-07-15; flash is a different name), `chemdfn` (use ChemDFM), Deep Hat V2 open weights, RACE verifier, NatureLM 1B/8B, CyberPal 2.0 weights, official `gpt-oss-heretic` library tag.

No git commit.
