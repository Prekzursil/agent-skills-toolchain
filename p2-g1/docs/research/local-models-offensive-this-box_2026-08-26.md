# Local offensive models — this box only (26.08.2026)

*Generated: 26.08.2026 | Scope: **RTX 4050 Laptop 6141 MiB GPU-full only** | Job: authorized estate-local pentest/RE **assist** | Sister (ignore VRAM): `local-models-offensive-unconstrained_2026-08-26.md` | Confidence: High on envelope; High that **14B+ GPU-full is NO**; High that official `DeepHat/DeepHat-V1-7B` **15GB F16 does not GPU-full** (use Q4 GGUF ~4.7GB); High that `WORMGPT-13` is a broken stub*

Do **not** mix this list with the unconstrained ranking. **Explicit NO 14B+.** Quality over shock: installed `qwen2.5:7b` beats a heretic 8B that invents CVEs. Cite `D:\knowledge` (hacktricks, gtfobins, lolbas, atomic-red-team, owasp-wstg, owasp-cheatsheets, payloadsallthethings). No third-party attack recipes. No exploit payloads.

---

## Hardware envelope (measured)

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce **RTX 4050 Laptop** |
| VRAM | **6141 MiB** |
| Weights cap | **5117 MiB** (weights + 1024 MiB KV < 6141) |
| Proven envelope | installed `qwen2.5:7b` **4466 MiB** Q4_K_M |
| Already installed | `qwen2.5:7b` (tools), `qwen2.5:3b`, `nomic-embed-text` |
| Broken | `blackgrg26/WORMGPT-13:latest` — size **dash**, no model layer, remote **123B stub**. A real 13B would not GPU-full anyway. **Do not pull.** |
| 5.2GB tags | `qwen3:8b` / `deepseek-r1:8b` formula-FIT but **tight** on WDDM |

Official Ollama `DeepHat/DeepHat-V1-7B:latest` is **15GB F16** — **NO GPU-full**. WhiteRabbitNeo V3-7B latest is the same **15GB**. The FIT path is **GGUF Q4_K_M ~4.68–4.8GB** via `ollama create`.

---

## Rank 1–N — offensive assists that FIT

Hardware-agent order: installed `qwen2.5:7b` → `qwen2.5-coder:7b` or `dolphin-llama3:8b`, plus `qwen3:4b`.

| Rank | Tag | GB | Method/job | Pull |
|---|---|---|---|---|
| **1** | `qwen2.5:7b` | **~4.4–4.7GB** | **INSTALLED. Tools-confirmed.** Quality default on this card. Schema-following brain for HexStrike MCP / local corpora RAG. HexStrike blog `OPENAI_MODEL=qwen2.5:7b` is **UNVERIFIED-as-official** — still the right *size*. | already on disk |
| **2** | `qwen2.5-coder:7b` | **4.7GB** | RE / script assist, FIM. Twin of #1. Iterate on tool stderr; do not emit exploit PoCs. | `ollama pull qwen2.5-coder:7b` |
| **3** | `dolphin-llama3:8b` (`:latest`) | **4.7GB** | Dolphin 2.9 (Llama 3). GPU-full uncensored chat. Official library, 8K default ctx (not 128K). | `ollama pull dolphin-llama3:8b` |
| **4** | `qwen3:4b` | **2.5GB** | Current-gen thinking, comfortable KV. Planner; hand off to #1 for tools. | `ollama pull qwen3:4b` |
| **5** | `dolphin3:8b` (`:latest`) | **4.9GB** | Official Dolphin 3.0 Llama 3.1 **8B** (VERIFY `real=1` — **not** 24B). Tight GPU-full, short ctx. Best *official library* uncensored 8B. | `ollama pull dolphin3:8b` |
| **6** | `hermes3:8b` | **4.7GB** | Official tools chip (no thinking). Steerable `<tool_call>`. | `ollama pull hermes3:8b` |
| **7** | HF GGUF `bartowski/WhiteRabbitNeo_WhiteRabbitNeo-V3-7B-GGUF` **or** `mradermacher/DeepHat-V1-7B-GGUF` Q4_K_M | **4.68GB** / **4.8GB** | Dual-use (ex-WhiteRabbitNeo / DeepHat-V1-7B). VERIFY `real=1` on the **family**, but **not** the 15GB F16 Ollama tag. Apache-2.0 + DeepHat/WRN rider. Higher hallucination — verify every CVE against `D:\knowledge`. | GGUF + `ollama create` — **do not** `ollama pull DeepHat/DeepHat-V1-7B` on this GPU (15GB) |
| **8** | HF `fdtn-ai/Foundation-Sec-8B-Reasoning-Q4_K_M-GGUF` | **4.92GB** | Best confirmed open **cyber reasoner** that fits (CTI-MCQA 0.691 / CTI-RCM 0.753). No official Ollama library tag (**404**). Instruct Q4 also ~4.92GB. Community FenkoHQ port is **16GB** — **NO**. | HF GGUF + `ollama create` |
| **9** | `granite3.3:8b` | **4.9GB** | CyberMetric 8B-class. Tight. Aligned IBM. | `ollama pull granite3.3:8b` |
| **10** | `qwen3:8b` | **5.2GB** | PentestGPT README local example `ollama:qwen3`. Last-include **tight**. Pick **one** 8B. | `ollama pull qwen3:8b` |

Optional FIT (not extra ranks):

| Tag | GB | Job | Pull |
|---|---|---|---|
| `huihui_ai/qwen2.5-abliterate:7b` | **4.7GB** | Uncensored twin of installed #1. Live 26.08.2026: 4.7GB, 32K, tools. | `ollama pull huihui_ai/qwen2.5-abliterate:7b` |
| `huihui_ai/qwen2.5-coder-abliterate:7b` | **4.7GB** | Uncensored twin of #2. | `ollama pull huihui_ai/qwen2.5-coder-abliterate:7b` |
| HF Lily-Cybersecurity-7B-v0.2 GGUF | **4.37GB** | Older 22k-pair SFT. No official Ollama library tag. | HF GGUF |
| `llama3.1:8b` | **4.9GB** | Stale PentestGPT `OLLAMA_MODEL`. Tight. | `ollama pull llama3.1:8b` |
| `llama-guard3:1b` / `:8b` | **1.6 / 4.9GB** | **DEFENSIVE** companion only. Not an offensive rank. | `ollama pull llama-guard3:1b` |
| `huihui_ai/command-r7b-abliterated` | **5.1GB** | Uncensored RAG template; citation quality **UNVERIFIED**. Tight. | `ollama pull huihui_ai/command-r7b-abliterated` |
| `huihui_ai/deepseek-r1-abliterated:7b` / `:8b` | **4.7 / 5.0GB** | Refusal-strip CoT. `:8b` tight. | Huihui org |

Do **not** pull both Dolphin 8B and Qwen3 8B at once. One ~5GB model + KV + the live fleet will spill.

### Default on this box

- **Want quality + tools already on disk:** #1 `qwen2.5:7b`.
- **Want RE/scripts:** #2 `qwen2.5-coder:7b`.
- **Want official uncensored 8B:** #5 `dolphin3:8b` (tight ctx).
- **Want DeepHat/WRN dual-use:** #7 **Q4 GGUF**, never the 15GB F16 tag.
- **Want cyber-tuned CTI:** #8 Foundation-Sec-Reasoning Q4 GGUF.

On 8B keep `num_ctx` 2048–4096.

---

## Explicit NO (14B+ and over-cap)

| Tag | GB | Why NO |
|---|---|---|
| `qwen3.8:27b` / Huihui abliterated 27B | **18GB** | Unconstrained quality default. |
| `glm-4.7-flash` | **19GB** | Best local SWE/RE card. |
| `qwen3-coder:30b` | **19GB** | 256K RE specialist. |
| `gpt-oss:20b` / heretic 20B | **14 / 16GB** | PentestGPT CCR localLLM — still 14GB+. |
| `qwen2.5:72b` | **47GB** | CAI documented local. |
| `llama3.3:70b` | **43GB** | CyberStrike Ollama example. |
| `mixtral:8x7b` | **26GB** | CyberMetric 91%. |
| `qwen3:14b` / `deepseek-r1:14b` / `qwen2.5-coder:14b` | **9.3 / 9.0 / 9.0GB** | **14B+.** HexStrike community 14B reports **UNVERIFIED-as-official** and would not GPU-full anyway. |
| `qwen3.5:9b` | **6.6GB** | Over cap. |
| `DeepHat/DeepHat-V1-7B:latest` (Ollama) | **15GB F16** | Same weights as WRN-V3. Use Q4 GGUF (#7). |
| `WhiteRabbitNeo/WhiteRabbitNeo-V3-7B:latest` | **15GB F16** | Same. `/library/whiterabbitneo` **404**. |
| Llama-3.1-WRN-2-70B Q4 | **42.52GB** | |
| `FenkoHQ/Foundation-Sec-8B` | **16GB** | Community F16-class. Use official **Q4 4.92GB** GGUF instead. |
| `dolphin3:24b` | — | **WRONG-TAG.** Official dolphin3 is 8B (VERIFY `real=1`). HF Dolphin3.0-Mistral-24B Q4 is **14.4GB** — also NO GPU-full. |
| OffSec-35B GGUF Q4 | **21.7GB** | Deprecated/broken tool calls on card. |
| Deep Hat V2 30B | — | Proprietary; no public tag. |
| `blackgrg26/WORMGPT-13:latest` | size dash | **Broken stub** (advertised 13B, remote 123B, no weights). |

CPU/offload of 14B+ is **not** this file.

---

## Commands (this box)

```text
# Quality default already installed
ollama run qwen2.5:7b

# RE twin
ollama pull qwen2.5-coder:7b

# Comfortable thinker
ollama pull qwen3:4b

# Official uncensored 8B — tight ctx, pick ONE 8B
ollama pull dolphin3:8b

# Optional uncensored twin of installed 7B
ollama pull huihui_ai/qwen2.5-abliterate:7b

# Defensive companion (not an offensive rank)
ollama pull llama-guard3:1b
```

DeepHat/Foundation-Sec on this GPU (GGUF, not the 15–16GB tags):

```text
# Example only — import the Q4 GGUF then:
# ollama create deephat-v1-7b-q4 -f Modelfile
# ollama create foundation-sec-8b-reason-q4 -f Modelfile
```

**Do not run on this GPU:**

```text
ollama pull qwen3.8:27b
ollama pull qwen3-coder:30b
ollama pull gpt-oss:20b
ollama pull qwen3:14b
ollama pull qwen3.5:9b
ollama pull DeepHat/DeepHat-V1-7B          # 15GB F16
ollama pull WhiteRabbitNeo/WhiteRabbitNeo-V3-7B   # 15GB F16
ollama pull FenkoHQ/Foundation-Sec-8B      # 16GB
ollama pull dolphin3:24b                   # WRONG-TAG
ollama pull blackgrg26/WORMGPT-13          # broken stub
ollama pull glm-4.7                        # retired; flash is 19GB anyway
```

---

## Authorized use (no recipes)

1. Brain = #1 (tools) or #2 (code). Retrieve from `D:\knowledge\*` before answering.
2. Dual-use overlay (#3/#5/#7) only when aligned models refuse **owner-ops on this machine**. Check every CVE/CWE/ATT&CK id.
3. Foundation-Sec-Reasoning (#8) for CTI mapping — still verify (CTIBench: 8B-class ATE F1 is poor).
4. Llama Guard is the **block** path, not a pentest brain.
5. HexStrike/CyberStrike/PentestGPT: local fallbacks in READMEs are larger than this GPU; this table is what actually **fits**.

Owner-ops estate-local only. No third-party targeting.

---

## Sources

Hardware FIT this session. Offensive cards 26.08.2026 as in `local-models-offensive-unconstrained_2026-08-26.md`. VERIFY `real=1`: Qwen3.8 library; WhiteRabbitNeo/DeepHat org tags; dolphin3 is 8B; Foundation-Sec HF live; `/library/foundation-sec` 404; `/library/whiterabbitneo` 404; `/library/gpt-oss-heretic` 404.
