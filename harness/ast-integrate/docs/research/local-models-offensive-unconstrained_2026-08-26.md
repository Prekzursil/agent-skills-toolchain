# Local offensive models — unconstrained (authorized lab) (26.08.2026)

*Generated: 26.08.2026 | Scope: **ignore VRAM** | Job: authorized red-team / pentest / RE **assist** on owner-controlled systems | Sister (this GPU): `local-models-offensive-this-box_2026-08-26.md` | Confidence: High on tag existence (VERIFY `real=1` for Qwen3.8, WhiteRabbitNeo/DeepHat, dolphin3=8B not 24B, Foundation-Sec); Medium on “best” quality order (no CyberMetric re-run here)*

**Quality over shock.** Tool-calling 27Bs beat heretic 8Bs that hallucinate CVEs. Pair any local brain with on-disk corpora — do **not** treat an 8B as CVE ground truth.

Owner-ops **estate-local only**. No third-party attack recipes in this file. No exploit PoCs. Cite `D:\knowledge`, not invented CVEs.

---

## Estate offensive surface (cite these; do not invent)

Seven clones, all present (`CORPORA.md` / `D:\knowledge`):

| Corpus | Path |
|---|---|
| HackTricks | `D:\knowledge\hacktricks` |
| GTFOBins | `D:\knowledge\gtfobins` |
| LOLBAS | `D:\knowledge\lolbas` |
| Atomic Red Team | `D:\knowledge\atomic-red-team` |
| OWASP WSTG | `D:\knowledge\owasp-wstg` |
| OWASP CheatSheets | `D:\knowledge\owasp-cheatsheets` |
| PayloadsAllTheThings | `D:\knowledge\payloadsallthethings` |

Skills on this estate (assist, not a shopping list of attacks): `hacktricks`, `hacktricks-api`, `secsearch`, `hexstrike-ai-*`, `cyberstrike`, `frida`, `ghidra-*`, `ida-*`, `binary-ninja`, `angr`, `capa-triage`, `malware-analysis-triage`.

A useful local model here: follows tool-call schemas, does not refuse **authorized** dual-use, and **retrieves** from those corpora.

---

## Rank 1–10 (ignore VRAM) — quality first

Rank = **tool-calling × 2026 reasoning × published cyber/SWE evidence × documented framework fallback**. Low-refusal domain models are **last**, not first.

| Rank | Tag | GB | Method/job | Pull |
|---|---|---|---|---|
| **1** | `qwen3.8:27b` (`:latest`) | **18GB** | **Quality default.** Vision + tools + thinking, 256K. SWE-Pro 61.7, TB2.1 73.0. Cite NVD/MITRE/`D:\knowledge` — do not freewheel CVEs. VERIFY `real=1`. | `ollama pull qwen3.8:27b` |
| **2** | `glm-4.7-flash` q4_K_M | **19GB** (q8_0 **32GB**) | Vendor SWE-Verified **59.2** (vs Thinking-2507 22.0, gpt-oss-20b 34.0). Best local **RE / code-assist** execute-repair. Parser `glm47`. **`glm-4.7` (non-flash) retired.** If flash 404s: Unsloth GGUF **18.3GB**. | `ollama pull glm-4.7-flash` **else** HF GGUF |
| **3** | `qwen3-coder:30b` | **19GB** | 256K RE specialist (30.5B/3.3B). PentestGPT CCR think/longContext example. No SWE% on the card. `:next` Q4 ~52GB SWE 70.6 *asterisk*. | `ollama pull qwen3-coder:30b` |
| **4** | `qwen3.6:27b` (`:35b` **23GB**) | **18GB** / 23GB | Same agent chips, previous gen. Prefer 27B dense on 32GB RAM. OffSec-35B (below) is a merge on the 35B-A3B **base**, not a TUI default. | `ollama pull qwen3.6:27b` |
| **5** | `mixtral:8x7b` | **26GB** | Best **original** open-weight CyberMetric (IEEE CSR 2024): **91.10% / 87.00%** on 2k/10k Q. Humans ~72% on 80Q. | `ollama pull mixtral:8x7b` |
| **6** | `qwen3:32b` / `qwen3:30b` | **20GB** / **19GB** | Hybrid think + tools. `deepseek-r1:32b` **20GB** is the distill reasoner (full-R1 TACTL >90% is **not** the distill — distill TACTL **UNVERIFIED**). | `ollama pull qwen3:32b` |
| **7** | HF `fdtn-ai/Foundation-Sec-8B-Reasoning` | Q4_K_M **4.92GB** / Q8 **8.54GB** / BF16 ~**16GB** | **Strongest confirmed open 8B cyber stack** (2026-01-28 SFT+RLVR). CTI-MCQA 0.691 / CTI-RCM 0.753. Llama-3.1-8B CPT ~5.1B tokens. **No** `ollama.com/library/foundation-sec` (**404**). Community `FenkoHQ/Foundation-Sec-8B` **16GB**. Instruct sibling 2025-08-01. VERIFY `real=1`. | HF GGUF **or** `ollama pull FenkoHQ/Foundation-Sec-8B` (16GB F16-class) |
| **8** | `gpt-oss:20b` (`:120b` **65GB**) | **14GB** / 65GB | PentestGPT CCR **documented** localLLM (`openai/gpt-oss-20b`). Native tools + effort. Apache-2.0. | `ollama pull gpt-oss:20b` |
| **9** | `qwen2.5:72b` | **47GB** (`:32b` **20GB**) | CAI **documented** local default `ollama/qwen2.5:72b`. Qwen2.5-7B-Instruct CyberMetric-10k **83.56%** (Red Hat 2025) is the 7B sibling — this-box file. CAI itself archived 2026-08-22; default alias is `alias1` (cloud), **not** an Ollama tag. | `ollama pull qwen2.5:72b` |
| **10** | `DeepHat/DeepHat-V1-7B` | **15GB** F16 / HF BF16 ~**15.2GB** / GGUF Q4_K_M **4.68–4.8GB** | Confirmed dual-use uncensored (ex-**WhiteRabbitNeo**). Qwen2.5-Coder-7B finetune, 32k/131k YaRN, Apache-2.0 + DeepHat rider (**no military use**). VERIFY `real=1`. **Deep Hat V2 30B MoE is proprietary — no HF/Ollama tag.** Ranked last among the 10 because low-refusal ≠ high CTI quality (CTIBench Llama-3-8B ATE F1 0.16). | `ollama pull DeepHat/DeepHat-V1-7B` (F16) **or** GGUF Q4 |

**Default quality brain:** #1.  
**Default RE/code:** #2 then #3.  
**Default cyber-tuned 8B:** #7 (HF GGUF).  
**Default dual-use uncensored:** #10 — then **verify every CVE** against `D:\knowledge` + NVD.

### Rank notes

**Frameworks do not default to local.** PentestGPT v1.0 drives Claude Code or Codex. Legacy example: `pentestgpt-legacy --reasoning-model ollama:qwen3` (`registry.py` has **no** pinned Ollama id; auto-picks claude-opus then gpt-5.5). CCR template: localLLM `gpt-oss-20b` + `qwen3-coder-30b`. Older `llama3.1:latest` is **stale**. HexStrike is MCP tools only (discussion #113: any MCP client); community `qwen3:8b/14b` and `qwen2.5:7b` as HexStrike brains are **UNVERIFIED-as-official**. CyberStrike TUI example is Claude Sonnet 4; Ollama docs: `ollama pull llama3.3` then `--model ollama/llama3.3` (**43GB**). `alias1` / `alias2-mini` are **not** Ollama/HF library tags.

**Abliteration is refusal-strip, not a capability bump.** Confirmed overlays (owner-lab only):

| Tag | GB | Note |
|---|---|---|
| `huihui_ai/Qwen3.8-abliterated:27b` | **18GB** | VERIFY `real=1` (`:latest` = `:27b` = 18GB, 32K downloads). Same #1 base, layers 18–51 ablated. |
| `huihui_ai/gpt-oss-abliterated:20b` | **14GB** (`:120b` **88GB**) | 356K pulls on the family. |
| `svjack/gpt-oss-20b-heretic` | **16GB** | Heretic 20B + tools. Skip `second_constantine/gpt-oss-u:20b` if tools required (**tools NOT working**). |
| `brianmatzelle/gpt-oss-heretic:120b` | **65GB** | Tools verified. `seamon67` twin 65GB. **No** `ollama.com/library/gpt-oss-heretic`. |
| `dolphin3:latest` | **4.9GB** | Official library is Llama 3.1 **8B only**. VERIFY `real=1` (not 24B). HF `dphn/Dolphin3.0-Mistral-24B` Q4 **14.4GB** is the 24B (not `ollama pull dolphin3:24b`). |
| HF `heretic-org/Qwen3.8-27B-heretic-ara` | (HF) | 0/100 refusals, **no Ollama tag**. |
| `huihui_ai/deepseek-r1-abliterated` | 1.5b 1.1GB … 32b 20GB / 70b 43GB | Distill family. |

HF heretic refusal cards: p-e-w 20B still **58/100** refusals KL 0.96; coder3101 **19/100** KL 0.2933; kldzj 120B **19/100** KL 0.92. Abliterated “0% refusal + same MMLU” claims **UNVERIFIED**.

**Skip uncensored forks for RE** when official weights exist (code-exploit lens). Official > abliterated for code quality.

---

## Honourable / not 1–10 / defensive

| Item | GB | Why |
|---|---|---|
| `qwen2.5:32b` | 20GB | Sibling of CyberMetric 7B 83.56%. |
| `mistral-small:24b` | 14GB | Quality generalist. |
| `hermes3:8b` / `:70b` | 4.7 / 40GB | Steerable + tools. |
| `granite3.3:8b` | 4.9GB | CyberMetric 8B-class (~83.61% Granite-3.0-8B avg, Red Hat 2025). |
| HF `dphn/Dolphin3.0-Mistral-24B` Q4 | 14.4GB | Uncensored 24B. **Not** official `dolphin3`. |
| `llama3.3:70b` | 43GB | CyberStrike Ollama example. |
| `qwen3:8b` | 5.2GB | PentestGPT README `ollama:qwen3` local example. |
| `qwen2.5-coder:32b` / `:7b` | 20 / 4.7GB | FIM. |
| `deepseek-coder-v2:16b` | 8.9GB | Year stale. |
| `qwen3-coder-next` Q4 | ~52GB | SWE 70.6 asterisk. |
| HF `segolilylabs/Lily-Cybersecurity-7B-v0.2` GGUF | Q4 **4.37GB** | Older 22k-pair SFT. **No** official Ollama library tag. |
| HF `trendmicro-ailab/Llama-Primus-Merged` | 8B BF16 (GB **not on card**) | CPT 2.77B tokens. |
| `Trendyol/Trendyol-Cybersecurity-LLM-v2-70B-Q4_K_M` | **42.5GB** | **Defense-first**, not offensive. |
| `ollama llama-guard3:8b` / `:1b` | 4.9 / 1.6GB | **DEFENSIVE only.** Also HF Llama-Guard-4-12B. Do not rank as offensive. |
| `WhiteRabbitNeo/WhiteRabbitNeo-V3-7B` | **15GB** F16 | Pre-rebrand name of #10. Library `/library/whiterabbitneo` **404**; org path live. Also WRN-2.5-Qwen 15.2GB BF16 / Ollama 4.5GB Q4-class; Llama-3.1-WRN-2-70B 141GB / bartowski Q4 **42.52GB**. 2024 13B/33B/7B-v1.5a are **not successors**. |
| `oyildirim/CyberStrike-OffSec-35B` | BF16 **70.2GB** / GGUF Q4 **21.7GB** | Companion merge, **not** TUI default. Advertised GGUF **DEPRECATED/broken** on the HF card (0/24 real tool calls). |
| `cisco-ai/SecureBERT2.0-base` | 150M | Encoder, not a chat/agent brain. |
| Prime Intellect `INTELLECT-3` | 106B MoE | **General**, not cyber-tuned. No Prime Intellect security LLM this fetch. |
| CyberPal 2.0 weights | — | **UNVERIFIED** (eval dataset only). |
| Deep Hat V2 30B | — | Proprietary. Aug 2025 OSS-V2 comment **UNVERIFIED** as released. |

**Broken / do not pull:** `blackgrg26/WORMGPT-13:latest` (size dash, no model layer, remote 123B stub).

---

## Commands (copy)

```text
# Quality default (VERIFY real=1)
ollama pull qwen3.8:27b

# RE / execute-repair
ollama pull glm-4.7-flash
ollama pull qwen3-coder:30b

# CyberMetric original open-weight
ollama pull mixtral:8x7b

# Documented framework locals
ollama pull gpt-oss:20b
ollama pull qwen2.5:72b

# Dual-use (ex-WhiteRabbitNeo) — VERIFY real=1
ollama pull DeepHat/DeepHat-V1-7B
# old name, same family:
# ollama pull WhiteRabbitNeo/WhiteRabbitNeo-V3-7B

# Optional refusal overlay on #1 (owner-lab)
ollama pull huihui_ai/Qwen3.8-abliterated:27b
```

**Do not run:**

```text
ollama pull dolphin3:24b                 # WRONG-TAG — library is 8B (VERIFY real=1)
ollama pull glm-4.7                      # retired
ollama pull gpt-oss-heretic              # no official library tag
ollama pull foundation-sec               # library 404; use HF GGUF or FenkoHQ
ollama pull whiterabbitneo               # /library/ 404; use DeepHat/ or WhiteRabbitNeo/ org
ollama pull blackgrg26/WORMGPT-13        # broken stub
```

---

## How to use (authorized, no recipes)

1. Load #1 (or #2 for code).
2. Retrieve from `D:\knowledge\*` + NVD/MITRE — **then** reason.
3. HexStrike/Frida/Ghidra are **tools**; the LLM is the schema-following brain.
4. Foundation-Sec-Reasoning (#7) for CTI MCQ / mapping — still verify CWE/ATT&CK (CTIBench: small models fail CVE→CWE).
5. DeepHat/WRN (#10) when aligned models refuse *authorized* owner-ops. Expect higher hallucination; check every identifier.
6. Llama Guard is the **deny** companion, not an offensive rank.

No exploit payloads, no third-party targeting, no CVE invention.

---

## Sources (fetched 26.08.2026)

- https://ollama.com/library/qwen3.8 — VERIFY `real=1`
- https://huggingface.co/Qwen/Qwen3.8-27B · https://ollama.com/library/qwen3.6 · https://ollama.com/library/qwen3-coder · https://ollama.com/library/qwen3 · https://ollama.com/library/qwen2.5
- https://ollama.com/library/glm-4.7-flash · https://huggingface.co/zai-org/GLM-4.7-Flash · https://ollama.com/library/glm-4.7 (retired)
- https://ollama.com/library/mixtral · https://ollama.com/library/gpt-oss · https://ollama.com/library/hermes3 · https://ollama.com/library/granite3.3 · https://ollama.com/library/dolphin3 — VERIFY `real=1` (8B)
- https://huggingface.co/fdtn-ai/Foundation-Sec-8B-Reasoning — VERIFY `real=1`
- https://huggingface.co/DeepHat/DeepHat-V1-7B · https://ollama.com/DeepHat/DeepHat-V1-7B · https://ollama.com/WhiteRabbitNeo/WhiteRabbitNeo-V3-7B — VERIFY `real=1`
- https://www.deephat.ai/ · https://huggingface.co/bartowski/WhiteRabbitNeo_WhiteRabbitNeo-V3-7B-GGUF
- https://ollama.com/huihui_ai/Qwen3.8-abliterated — VERIFY `real=1`
- https://github.com/GreyDGL/PentestGPT · https://github.com/aliasrobotics/cai · https://github.com/0x4m4/hexstrike-ai/discussions/113 · https://docs.cyberstrike.io/docs/providers
- https://arxiv.org/abs/2402.07688 (CyberMetric) · https://arxiv.org/abs/2406.07599 (CTIBench) · https://arxiv.org/abs/2504.21039 (Foundation-Sec)
- https://huggingface.co/PrimeIntellect/INTELLECT-3 (not cyber-tuned)
- https://ollama.com/library/llama-guard3 (defensive)
