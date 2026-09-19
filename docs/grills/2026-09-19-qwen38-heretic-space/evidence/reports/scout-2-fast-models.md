<!-- verbatim final report of background subagent aa31d545682c0e9e5, saved 2026-09-19 -->

## Shortlist

Speed-up is 27B ÷ active parameters at equal 4-bit precision. It is an estimate and an upper bound; nothing was run. Downloads are the figures from each repo's details page.

| Repo | Base / arch | Total / active | Est. speed-up | Licence | DL / likes / updated | Capability evidence | 4-bit checkpoint | Live provider | Context |
|---|---|---|---|---|---|---|---|---|---|
| [llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved](https://hf.co/llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved) | Qwen3.6-35B-A3B; `qwen3_5_moe`, 256 experts, top-8 + 1 shared, vision, MTP head (`mtp_num_hidden_layers: 1`) | 35.1B / 3B | ≤9× (est.) | Apache-2.0 | 89.7K / 37 / 9 May 2026 | KL 0.0015; MMLU 83.71→83.39 (card). Base card: MMLU-Pro 85.2 vs 86.1 for Qwen3.5-27B, GPQA 86.0 vs 85.5, LCB v6 80.4 vs 80.7 | [llmfan46/…-MTP-Preserved-GPTQ-Int4](https://hf.co/llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-GPTQ-Int4), 22.34 GB | featherless-ai | 262,144 |
| [p-e-w/gpt-oss-20b-heretic-ara-v3](https://hf.co/p-e-w/gpt-oss-20b-heretic-ara-v3) | gpt-oss-20b; `gpt_oss`, 32 experts, top-4, text-only, no MTP | 21B / 3.6B | ≤7.5× (est.) | Apache-2.0 | 4.1K / 34 / 5 Mar 2026 | KL 0.0554; no benchmark deltas on card; base card states native function calling and the harmony format | The repo itself is MXFP4, 13.76 GB | none listed | 131,072 |
| [coder3101/gemma-4-26B-A4B-it-heretic](https://hf.co/coder3101/gemma-4-26B-A4B-it-heretic) | gemma-4-26B-A4B-it; `gemma4`, 128 experts, top-8, vision, no MTP | 25.2B / 3.8B | ≤7.1× (est.) | Apache-2.0 | 122.2K / 100 / 14 Apr 2026 | KL 0.0499; base card: MMLU-Pro 82.6, GPQA-D 82.3, LCB v6 77.1, Tau2 68.2 | [louismuk/gemma-4-26B-A4B-heretic-AWQ](https://hf.co/louismuk/gemma-4-26B-A4B-heretic-AWQ), 17.19 GB; its card says vLLM only, and it was built from llmfan46's variant | featherless-ai | 262,144 |
| [coder3101/LFM2.5-8B-A1B-heretic](https://hf.co/coder3101/LFM2.5-8B-A1B-heretic) | LFM2.5-8B-A1B; `lfm2_moe`, 32 experts, top-4, text-only | 8.3B / 1.5B | ≤18× (est.) | LFM 1.0 ("other") | 230 / 4 / 6 Jun 2026 | KL 0.0239; no benchmark numbers read | None needed: bf16 is 16.94 GB | none listed | 128,000 |
| [llmfan46/Qwen3.5-9B-ultra-uncensored-heretic](https://hf.co/llmfan46/Qwen3.5-9B-ultra-uncensored-heretic) | Qwen3.5-9B; dense `qwen3_5`, vision, MTP head | 9.4B dense | ~2.9× (est.) | Apache-2.0 | 8.7K / 17 / 12 Jul 2026 | KL 0.0241; PIQA 0.7943→0.7960; base card: MMLU-Pro 82.5, GPQA-D 81.7, LCB v6 65.6 | None found; bf16 is 18.82 GB | none listed | 262,144 |
| [llmfan46/gemma-4-E4B-it-uncensored-heretic](https://hf.co/llmfan46/gemma-4-E4B-it-uncensored-heretic) | gemma-4-E4B-it; dense with per-layer embeddings, text/image/audio | 8.0B / 4.5B effective | ~6× (est.) | Apache-2.0 | 617.9K / 7 / 4 May 2026 | KL 0.0043; MMLU 69.46→68.97; PIQA 86.02→85.58 | None needed: bf16 is 15.99 GB | none listed | 128K |
| [heretic-org/Qwen3-4B-Instruct-2507-heretic](https://hf.co/heretic-org/Qwen3-4B-Instruct-2507-heretic) | Qwen3-4B-Instruct-2507; dense `qwen3`, text-only | 4.0B dense | ~6.7× (est.) | Apache-2.0 | 28.9K / 15 / 14 Feb 2026 | KL 0.0741; no benchmark deltas | None needed: bf16 is 8.04 GB | featherless-ai | 262,144 |

- **bitsandbytes 4-bit on these MoE architectures is unverified and probably ineffective.**
  - The transformers v5.17 bnb doc says the conversion targets `torch.nn.Linear` layers.
  - The Qwen3.6 and Gemma-4 checkpoints store experts as fused `experts.gate_up_proj` tensors, so the experts would likely stay in bf16.
- **Chat templates:** every shortlisted repo ships a `chat_template.jinja`. Tool calling is stated on the base cards for all seven.

## Recommendation for this slot

The hardware has changed since the 27B figure was measured. The ZeroGPU docs now give `large` as half an RTX Pro 6000 Blackwell with 48 GB, and `xlarge` as 96 GB at 2× quota.

**Top pick: Qwen3.6-35B-A3B MTP-Preserved, served from its GPTQ-Int4 checkpoint (22.34 GB).**
- **Why:** its base card puts it within about one point of the dense Qwen3.5-27B while activating 3B parameters. It has the lowest KL found and an MMLU change of −0.32 points. It also brings vision, tool calling, 262K context and a live provider for A/B checks.
- **Size:** bf16 is 71.9 GB, so 4-bit is mandatory on `large`.
- **Measure first:**
  1. It loads under transformers with gptqmodel on ZeroGPU, and `get_memory_footprint()` is about 22 GB.
  2. Batch-1 decode speed with `experts_implementation` set to `batched_mm` versus `eager`.
  3. Cold-load time inside the `@spaces.GPU` duration.

**Runner-up: p-e-w/gpt-oss-20b-heretic-ara-v3.**
- **Why:** it is the only MoE here with a documented native 4-bit transformers path, so it carries the lowest integration risk. The transformers docs list MXFP4 as supported for gpt-oss, needing `kernels` and Triton ≥ 3.4. The checkpoint is 13.76 GB.
- **Trade-offs:** text-only, 131K context, and KL 37× higher than the top pick.
- **Measure first:** that the MXFP4 kernels engage on the Blackwell slice rather than falling back to a bf16 dequantise, and that harmony-format output renders correctly.

**Fallbacks.** If both fail, the dense Qwen3.5-9B on the existing bnb path gives about 3×. LFM2.5-8B-A1B in bf16 has the highest estimated ratio, but its capability evidence is thin and its licence is not Apache.

**Why the ratios are upper bounds.** At 9 tok/s × about 14 GB of 4-bit weights, the current stack moves roughly 0.13 TB/s. It is therefore probably overhead-bound, and active-parameter ratios will overstate the real gain.

## Rejected

- trohrbaugh/GLM-4.7-Flash-heretic (30B-A3B, MIT, KL 0.0393, MTP layer, 202,752 context): bf16 is 59.9 GB, over 48 GB, and no heretic 4-bit safetensors were found.
- AEON-7/Qwen3.6-35B-A3B-heretic-NVFP4 (23.35 GB): its card documents vLLM serving only.
- genevera/Qwen3.6-35B-A3B-Abliterated-Heretic-AWQ-4bit (20.74 GB): the card reads as auto-generated, and its loading claim is unverified.
- trohrbaugh/Qwen3.8-Flash-Next-heretic-2: 177.4B parameters, licence "other".
- p-e-w/gpt-oss-20b-heretic (v1): KL 0.96 and about 42 GB in bf16.
- MuXodious/gpt-oss-20b-RichardErkhov-heresy: KL 0.0802, worse than ara-v3; its card evidence is out of scope.
- llmfan46/gemma-4-12B-it-uncensored-heretic: KL 0.1203 for only about 2.25× estimated.
- trohrbaugh/Qwen3.5-9B-heretic-v2: KL 0.0793, against 0.0241 for llmfan46's build of the same base.
- The Nemotron-3.5-Lightning-30B-A3B and llm-jp-4-32b-a3b heretic builds: bf16 only, at 0–230 downloads.
- Tencent-Hy-30B-A3B heretic builds: translation-specialised, and no 4-bit safetensors build was found.
- GGUF-only repos (DavidAU, SC117 Ornith-1.5-35B-A3B, mradermacher): not transformers-loadable without dequantising.
- "Qwen3.8-9B" heretic GGUFs: a community distill, and the source repo `rohit267/…` returned not found.

## Gaps

- bnb, GPTQ and AWQ loading of MoE experts under plain transformers on ZeroGPU: unverified. vLLM on ZeroGPU was not checked.
- Whether transformers `generate()` uses MTP heads: unverified. Assume no gain.
- Base-card benchmarks for Qwen3.6-35B-A3B and Qwen3.5-9B came through a WebFetch summary, not the raw card text.
- The search listing and the details page disagree on downloads (for example 4.2K versus 75.6K). I used the details-page figure.
- LongCat-Flash-Lite heretic was not inspected.
- LFM2.5 base benchmark numbers were not read.
- No speed was measured.