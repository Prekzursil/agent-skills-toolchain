# Handoff — uncensored local LLM dual ranking (26.08.2026)

SUCCESS:reports-written. Seed not overwritten. No git commit. No model pulled.

**Original goal:** two markdown reports under `C:\Users\Prekzursil\source\ast-integrate\docs\research`. File 1 unconstrained rank 1–10 ignoring VRAM (tag, GB, method, pull). File 2 this-GPU only from the hardware agent, rank 1–N, explicit NO for 14B+. DD.MM.YYYY dates. Pasted-list audit. Flag UNVERIFIED. Do not invent real=0 / WRONG-TAG pulls.

**Headline:** On 2026 newest open bases, uncensored work is Huihui/Sumandora plus Heretic/ARA. Official Dolphin SFT and official Hermes SFT were NOT FOUND on Qwen 3.5 / 3.6 / 3.8, Gemma 4, or Llama 4.

---

## On-disk proof

| Path | Bytes | Lines | Written |
|---|---|---|---|
| `C:\Users\Prekzursil\source\ast-integrate\docs\research\uncensored-local-llms-unconstrained_2026-08-26.md` | 21805 | 241 | 26.08.2026 05:55:40 |
| `C:\Users\Prekzursil\source\ast-integrate\docs\research\uncensored-local-llms-this-box_2026-08-26.md` | 12894 | 169 | 26.08.2026 05:56:58 |
| `C:\Users\Prekzursil\source\ast-integrate\docs\research\uncensored-local-llms_2026-08-26.md` (seed) | 12093 | 140 | 26.08.2026 04:58:13 **untouched** |

Required sections: File 1 Rank 1–10 + Pasted-list audit + VERIFY log + lens URLs. File 2 Rank 1–N + Explicit NO 14B+ + Pasted-list audit + VERIFY log.

---

## File 1 — unconstrained (ignore VRAM)

Return path: `C:\Users\Prekzursil\source\ast-integrate\docs\research\uncensored-local-llms-unconstrained_2026-08-26.md`

Methods: Dolphin = dataset SFT. Abliteration = Huihui/Sumandora. Heretic/ARA = p-e-w. Hermes = official Nous steerability.

| Rank | Tag | GB | Method | Pull |
|---|---|---|---|---|
| 1 | `huihui_ai/Qwen3.8-abliterated:27b` | 18GB (17GB Q4_K_M + 931MB projector) | Abliteration | `ollama pull huihui_ai/Qwen3.8-abliterated:27b` |
| 2 | `jacokon/qwen3.8-27b-heretic-ara` | 18GB Ollama latest; readme 17GB Q4+mmproj | Heretic/ARA | `ollama pull jacokon/qwen3.8-27b-heretic-ara` |
| 3 | `steelpuddles/hermes-4.3-36B` | 22GB / official GGUF 21.8GB | Hermes | `ollama pull steelpuddles/hermes-4.3-36B` |
| 4 | `coder3101/gemma-4-31B-it-heretic` + mradermacher | Q4_K_M 18.8GB | Heretic/ARA | No Ollama heretic tag; import GGUF |
| 5 | `huihui_ai/gemma-4-abliterated:31b` | 20GB | Abliteration | `ollama pull huihui_ai/gemma-4-abliterated:31b` |
| 6 | `huihui_ai/Qwen3.6-abliterated:27b` | 17GB | Abliteration | `ollama pull huihui_ai/Qwen3.6-abliterated:27b` |
| 7 | `huihui_ai/qwen3.5-abliterated:27b` | 17GB | Abliteration | `ollama pull huihui_ai/qwen3.5-abliterated:27b` |
| 8 | `dphn/Dolphin3.0-R1-Mistral-24B` / overlay `huihui_ai/dolphin3-r1-abliterated:24b` | 14.33 / 14GB | Dolphin (+ overlay) | NOT `dolphin3:24b` |
| 9 | `huihui_ai/llama3.3-abliterated:70b` | 43GB | Abliteration | `ollama pull huihui_ai/llama3.3-abliterated:70b` |
| 10 | `huihui_ai/qwen3.5-abliterated:122B` | 81GB | Abliteration | `ollama pull huihui_ai/qwen3.5-abliterated:122B` |

Evidence:

- #1 VERIFY real=1. `https://ollama.com/huihui_ai/Qwen3.8-abliterated` latest `bdc5e13cd164 · 18GB · 256K · Text, Image`; chips vision/tools/thinking/27b. Same digest as :27b.
- #2 live 26.08.2026. `https://ollama.com/jacokon/qwen3.8-27b-heretic-ara` exists, :latest 18GB. HF `trohrbaugh/Qwen3.8-27B-heretic-ara` 0/100 refusals, KL 0.0535.
- #3 `https://ollama.com/library/hermes4` 404. Last official library is hermes3. RefusalBench 74.60%/72.29%. UNVERIFIED: `ollama pull hermes-4:14b`.
- #4 p-e-w Gemma 4 Heretic is E4B/E2B only (E4B still 42/100). 31B is coder3101 15/100 KL 0.0434. UNVERIFIED listicle 17GB 31B Heretic tag.
- Official dolphin3 VERIFY real=1: 8B 4.9GB digest d5ab9ae8e1f2, five tags, no 24B.
- #9 VERIFY real=1: `694ca93d4b6e · 43GB`, manifest 42520398592 bytes.

Do not pull: `dolphin3:24b`, `hermes4`, `hermes-4:14b`, `mlabonne/gemma-3-27b-it-abliterated` as Ollama, `HausHaus`.

---

## File 2 — this box (RTX 4050 Laptop 6141 MiB)

Path: `C:\Users\Prekzursil\source\ast-integrate\docs\research\uncensored-local-llms-this-box_2026-08-26.md`

Envelope: 6141 MiB VRAM. GPU-full = weights + 1024 MiB KV under 6141. Weights cap 5117 MiB. Proven 7B Q4: installed qwen2.5:7b 4683073952 bytes = 4466 MiB + 1024 KV = 5490, leftover 651.

| Rank | Tag | GB | Method | Fit | Pull |
|---|---|---|---|---|---|
| 1 | `dolphin3:8b` | 4.9 | Dolphin | tight, VERIFY real=1 | `ollama pull dolphin3:8b` |
| 2 | `huihui_ai/qwen2.5-abliterate:7b` | 4.7 | Abliteration | twin of installed 7B; live 4.7GB | `ollama pull huihui_ai/qwen2.5-abliterate:7b` |
| 3 | `dolphin-llama3:8b` | 4.7 | Dolphin 2.9 | live official 4.7GB | `ollama pull dolphin-llama3:8b` |
| 4 | `huihui_ai/qwen2.5-coder-abliterate:7b` | 4.7 | Abliteration | live 4.7GB tools | `ollama pull huihui_ai/qwen2.5-coder-abliterate:7b` |
| 5 | `dolphin-mistral` | 4.1 | Dolphin 2.8 | live 4.1GB | `ollama pull dolphin-mistral` |
| 6 | `huihui_ai/qwen3.5-abliterated:4B` | 3.3 | Abliteration | comfortable, VERIFY real=1 `9acbd90c2645 · 3.3GB` | `ollama pull huihui_ai/qwen3.5-abliterated:4B` |
| 7 | `huihui_ai/qwen3-abliterated:4b` | 2.5 | Abliteration | comfortable | `ollama pull huihui_ai/qwen3-abliterated:4b` |
| 8 | `huihui_ai/qwen3-abliterated:8b` | 5.0 | Abliteration | last-include | `ollama pull huihui_ai/qwen3-abliterated:8b` |

Live-checked 26.08.2026 (not in four-row VERIFY set; pages exist): qwen2.5-abliterate:7b 4.7GB, qwen2.5-coder-abliterate:7b 4.7GB, dolphin-llama3:8b 4.7GB, dolphin-mistral 4.1GB.

No Heretic/Hermes-4 GPU-full on this card.

### Explicit NO for 14B+

Include TRUE 9.0GB `huihui_ai/qwen3-abliterated:14b`. Also NO: all 27B/31B/36B (including VERIFY-true Qwen3.8-abliterated 18GB), Dolphin 24B 14GB, llama3.3:70b 43GB, Mixtral, 13B dash-size, qwen3.5:9b 6.6GB, jaahas 7.4GB, Huihui Gemma 4 e4b 9.6GB / 12b 7.6GB, igorls E4B Q4 5.3GB (over 5117 MiB with KV), gemma3-abliterated:4b listed 8.6GB. 35B-A3B is 24GB on Ollama — not 6 GB because 3B are “active”.

---

## Pasted-list audit

| Pasted claim | Verdict | This GPU |
|---|---|---|
| dolphin3:8b 4.9GB | TRUE real=1 | YES rank 1 |
| huihui_ai/qwen3-abliterated:14b 9.0GB | TRUE | NO 14B+ |
| mlabonne/gemma-3-27b-it-abliterated as Ollama | WRONG-TAG | NO 27B |
| huihui_ai/llama3.3-abliterated:70b 43GB | TRUE real=1 | NO 70B |
| qwen3.8:27b 18GB | TRUE aligned not uncensored | NO 27B |
| huihui_ai/Qwen3.8-abliterated:27b 18GB | TRUE real=1 | NO 27B |
| gemma4:26b 19GB | TRUE aligned | NO 26B |
| dolphin3:24b official | WRONG-TAG | NO |
| MMLU 68.0 vs 68.4 | UNVERIFIED (Dolphin 8B MMLU-PRO 22.13) | n/a |
| HausHaus | WRONG-TAG+UNVERIFIED (real org HauhauCS) | n/a |

No real=0 tags ranked.

UNVERIFIED: MMLU 68.0 vs 68.4; HausHaus; hermes-4:14b; 17GB Gemma 4 31B Heretic listicle; E4B as GPU-full on this card.

---

## VERIFY log

| Claim | real | This GPU |
|---|---|---|
| dolphin3 latest is 8B 4.9GB not 24B | 1 | fits tight |
| Qwen3.8-abliterated latest ~18GB vision | 1 | does not fit |
| qwen3.5-abliterated:4B ~3.3GB | 1 | fits comfortable |
| llama3.3-abliterated:70b ~43GB | 1 | does not fit |

---

## Top picks

- Unconstrained: `ollama pull huihui_ai/Qwen3.8-abliterated:27b` (18GB, Abliteration)
- This box: `ollama pull dolphin3:8b` (4.9GB, Dolphin) or `ollama pull huihui_ai/qwen3.5-abliterated:4B` (3.3GB, comfortable Huihui)

Lens: 8-lens bundle (newest-bases, huihui-catalog, dolphin, hermes, heretic-gemma4, ollama-tags, coding-agents, pasted-audit) + hardware 6141 MiB + VERIFY real=1 + live Ollama pages 26.08.2026.

Primary sources: https://ollama.com/huihui_ai/Qwen3.8-abliterated ; https://ollama.com/jacokon/qwen3.8-27b-heretic-ara ; https://ollama.com/library/dolphin3 ; https://ollama.com/huihui_ai/llama3.3-abliterated ; https://huggingface.co/NousResearch/Hermes-4.3-36B ; https://huggingface.co/trohrbaugh/Qwen3.8-27B-heretic-ara ; https://github.com/Sumandora/remove-refusals-with-transformers ; https://github.com/p-e-w/heretic
