<!-- verbatim final report of background subagent ab46af82130a75ec9, saved 2026-09-19 -->

Repo ids below resolve at `https://hf.co/<repo id>`. All dates are 2026. Benchmark numbers are as reported on the model cards; I ran nothing.

## Shortlist

| Repo | Base, arch | Params total/active | Licence | DL / likes / updated | Capability evidence | 4-bit checkpoint | MTP head | Provider | Context |
|---|---|---|---|---|---|---|---|---|---|
| `llmfan46/Qwen3.8-27B-Ultra-Uncensored-Heretic-Native-MTP-Preserved` | Qwen/Qwen3.8-27B; qwen3_5 dense hybrid, VL | 27.36B + 0.42B MTP; dense | Apache-2.0 | 936 / 10 / 31 Aug | KL 0.0244; MMLU (7,021 q) 83.42→82.82% | `llmfan46/Qwen3.8-27B-Ultra-Uncensored-Heretic-Native-MTP-Preserved-GPTQ-Int4`, 19.56 GB | yes, aux file 0.85 GB | none | 262,144 |
| `heretic-org/Qwen3.8-27B-heretic-ara` (default) | same | same | Apache-2.0 | 10.0K / 39 / 15 Aug | KL 0.0535; no benchmark on this checkpoint | `JC1DA/Qwen3.8-27B-heretic-ara-W4A16` (auto-round, made from the identical trohrbaugh twin), 19.55 GB | yes, 0.85 GB | featherless-ai | 262,144 |
| `DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU` | Qwen3.8-27B multi-stage Unsloth tune | 27.78B dense | Apache-2.0 | 9.7K / 213 / 16 Sep | mxfp8, instruct mode: ARC-C 0.735 vs base 0.591, HellaSwag 0.832 vs 0.746. KL 0.0025 at the ablation step only. JC1DA FP16: MMLU 86.89, BBH 89.94, HumanEval 79.27, no base run | `JC1DA/Qwen3.8-27B-DavidAU-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU-INT4-W4A16` (auto-round), 19.55 GB | yes | featherless-ai | 262,144 |
| `DavidAU/Qwen3.8-27B-TWIN-TURBO-Fable-Cold-Fusion-709-L-Uncensored` | tune of the row above | 27.78B dense | Apache-2.0 | 1.2K / 65 / 16 Sep | ARC-C 0.709, below TURBO; KL 0.0025; "1/2–1/20 thinking tokens" claim unmeasured | none found | yes | none | 262,144 |
| `nerkyor/Qwen3.8-27B-EfficientThink-Uncensored-K3-Opus5-Grok4.6-GPT5.6Sol-SFT-SimPO-DFlash2` | Qwen3.8-27B + LoRA SFT (1,905 ex) + SimPO (110 pairs) | 27B dense | Apache-2.0 | 45.8K / 36 / 12 Sep | same harness vs base: GPQA-D 82.83→86.36%, MMLU-500 90.20→88.40%, LCB-100 69→74; mean reasoning tokens −6.6% / −9.4% / +2.9%; no KL | subfolder `NVFP4/AWQ-W4A16/` (compressed-tensors), 20.77 GB | absent in `BF16/`; official MTP bundled in quant packages | none | 262,144; evaluated at 65,536 |
| `gorbatjovy/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-heretic` | DavidAU Cold-Fusion GAIN V1.1 | 27.78B dense | Apache-2.0 | 481 / 6 / 24 Aug | KL 0.0315 vs its parent; W4A16 vs BF16: PPL 7.660 vs 7.537, GSM8K-100 93 vs 95%, tool calls 10/12 vs 11/12 | `gorbatjovy/Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-heretic-W4A16` (compressed-tensors), 16.53 GB listed; card says ~19 | yes, 0.85 GB | none | 262,144 |
| `llmfan46/gemma-4-31B-it-uncensored-heretic` | google/gemma-4-31B-it; gemma4 dense VL | 31.27B dense | Apache-2.0 | 100.6K / 129 / 11 Jun | KL 0.0541; MMLU 86.50→85.90% | `llmfan46/gemma-4-31B-it-qat-q4_0-uncensored-heretic-GPTQ-Int4`, 19.20 GB (QAT sibling); `alonsoko/gemma-4-31b-it-abliterated-heretic-AWQ-W4A16`, 19.07 GB, is built from trohrbaugh's variant (KL 0.0120) | none in listing | featherless-ai | 256K per AWQ card |
| `llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved` | Qwen/Qwen3.6-35B-A3B; qwen3_5_moe, 8 of 256 experts, VL | 35.11B / A3B by name | Apache-2.0 | 89.7K / 37 / 9 May | KL 0.0015; MMLU 83.71→83.39% | `llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-GPTQ-Int4`, 22.34 GB | yes, 1.69 GB | featherless-ai | 262,144 |

The stock Qwen3.8 chat template (8.9 KB) supports XML tool calls, `enable_thinking` and `reasoning_effort`.

## Recommendation for this slot

**Top pick: `llmfan46/Qwen3.8-27B-Ultra-Uncensored-Heretic-Native-MTP-Preserved`, served from its GPTQ-Int4.**
- It uses the same base as the current default at under half the reported KL (0.0244 vs 0.0535).
- It is the only plain Qwen3.8 entry with a measured base-versus-variant delta (MMLU −0.60 pp).
- Its first-party 4-bit checkpoint keeps vision and the MTP head.
- Risks: adoption is low and the author reports hitting a storage cap.
- The repo also replaces the stock chat template with a 28.9 KB rewrite (`qwen3.8-safe-v3.1`, xml/json tool formats).
- Measure before trusting the card:
  - a render-diff of that template against stock on tool-call and multi-turn thinking cases;
  - GPQA, LiveCodeBench and IFEval on the GPTQ build versus base at equal token caps;
  - MTP acceptance rate.

**Runner-up: `nerkyor/…EfficientThink…`.**
- It has the strongest evidence in the slot: a same-harness comparison with the official base, reasoning-token distributions, and documented training hyperparameters.
- Costs:
  - MMLU drops 1.8 pp and no KL is reported.
  - There is no root `config.json`, so the loader needs `subfolder=`.
  - The AWQ build is validated on vLLM only.
  - `PACKAGE_MANIFEST.json` still reads `SMOKE_REQUIRED` and `publication: false`, with stale filenames.
- Measure first: a transformers load of the AWQ subfolder, tool calling, and an independent rerun of the three suites.

**DavidAU TURBO** needs independent thinking-mode benchmarks before promotion.
- Its gains are 0-shot instruct-mode scores on MLX mxfp8.
- All three DavidAU configs, and JC1DA's W4A16, ship `"use_cache": false`, which transformers must override.
- TWIN-TURBO's template embeds persona system-prompt blocks for its switchable modes, and its card acknowledges tool-calling issues.

## Rejected

- `DavidAU/Qwen3.8-27B-TWIN-TURBO-Fable-Cold-Fusion-709-ULTRA-HERETIC-Uncensored`: weaker than its siblings on its own card (ARC-C 0.699; KL 0.0397 vs 0.0025). Its only 4-bit is `TheUnderscore/…-W4A16-AWQ` (19.55 GB), one day old with 0 downloads.
- `coder3101/Qwen3.8-27B-heretic-ara`: no MTP tensors in the index, a single 49.8 GB shard, and its KL 0.0349 is beaten by llmfan46.
- `CtrlCreeper/Qwen3.8-27B-Cold-Fusion-Heretic-Fable-Heretic`: a NuSLERP merge with no benchmarks or KL, MLX/GGUF quants only, and a `.DS_Store` committed.
- `trohrbaugh/Qwen3.8-27B-heretic-ara`: duplicate of heretic-org (identical shard sizes, parameters and KL).
- `Solstice-AI/…-NVFP4` family: claims are unverifiable. Its "TURBO" table repeats base Qwen3.8-27B's official numbers (SWE-bench Pro 61.7, QwenSWEBench 79.0).
- `darkc0de/Muse-Glimmer-30B-heretic` (29.78B): KL 0.0743 is the highest seen. Its base trails Qwen3.8-27B in Qwen's table (Terminal Bench 51.7 vs 73.0). Only NVFP4/exl3/GGUF quants exist.
- `0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored`: text-only, 26.9B; the vision tower and MTP head are dropped.
- `trohrbaugh/Qwen3.8-Flash-Next-heretic-2` (177.4B) and `s-zaizen/DeepSeek-V4.1-Flash-Abliterated` (763.2B listed): too large for 48 GB at 4-bit.
- `llmfan46/LongCat-Flash-Lite-Sparse-…` (69.1B): outside the 20–45B class and requires custom_code.
- `p-e-w/gpt-oss-20b-heretic` and `Olafangensan/GLM-4.7-Flash-heretic`: text-only and untouched since Nov 2025 and Jan 2026 respectively.
- `akumaburn/Swift-Qwen3.8-27b-heretic` and `charlinoss/heretic-nvidia`: licence "other", no downloads, days old.
- `soyaakinohara/K2-Horizon-32B-heretic`: requires custom_code, text-only, 528 downloads.

## Gaps

- Harnesses differ between cards, so rows are not like-for-like.
- DavidAU's KL covers the ablation step only, not the final weights versus the Qwen base.
- DavidAU's token-reduction claims have no measurement table.
- Tool calling was measured only by gorbatjovy, on 12 cases.
- Whether Heretic was actually applied to nerkyor's model is unverified. Its documented pipeline is SFT→SimPO.
- Transformers loading of the compressed-tensors builds (gorbatjovy, nerkyor, alonsoko) is unverified. Those cards document vLLM only.
- Download counts are details-page values. The search listing showed lower figures for the same repos, and the counting window is unknown.
- Gemma's 256K context comes from the AWQ card; its config was not opened.
- The 1M context extension is unverified for any variant.
- Provider status is a snapshot from 19 Sep 2026.