<!-- verbatim final report of background subagent afc66d1916d4427a5, saved 2026-09-19 -->

## Coding slot
| repo id | base and arch | params total/active | licence | downloads/likes/updated | coding evidence | 4-bit checkpoint (repo id, GB) | live provider | context |
|---|---|---|---|---|---|---|---|---|
| DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU (source of the NEO-CODER GGUFs) | Qwen3.8-27B fine-tune; qwen3_5 dense VLM | 27.8B / 27.8B | apache-2.0 | 9.7K / 213 / 16 Sep 2026 | The author card has no coding benchmark. It reports ARC-C 0.735 vs base 0.591 (mxfp8). The quantizer's card reports HumanEval pass@1 79.27% FP16 and 79.88% W4A16. KLD 0.0025 at the Heretic step; the model was tuned further afterwards. | JC1DA/Qwen3.8-27B-DavidAU-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NM-DAU-INT4-W4A16, 19.5 GB, auto-round | featherless-ai | 262,144 |
| dpankros/Qwen3-Coder-30B-A3B-Instruct-Heretic | Qwen3-Coder-30B-A3B-Instruct; qwen3_moe, text-only | 30.5B / 3.3B | apache-2.0 | 913 / 3 / 31 Jan 2026 | The base is a code specialist. Its card shows benchmarks only as an image (unverified). KL 0.1789. | none found (bf16 61.1 GB) | none | 262,144 |
| llmfan46/gemma-4-12B-coder-fable5-composer2.5-v1-uncensored-heretic | community coder tune of gemma-4-12B; gemma4_unified | 12.0B dense | apache-2.0 | 1.4K / 11 / 21 Jun 2026 | No coding score in the card sections read. KL 0.0467. | none found (bf16 23.9 GB) | featherless-ai | 256K per card; config unverified |

**Top pick: DavidAU TURBO via the JC1DA checkpoint.**
- It is the only coding-labelled candidate with a transformers-style 4-bit checkpoint, and that checkpoint includes the vision processor files.
- It has a live provider.
- Its chat_template.jinja contains a tool block (opened and checked).
- It uses the architecture the Space already runs.
- It wins on deployability. No card shows a coding gain over its base model.

## Vision slot
| repo id | base and arch | params total/active | licence | downloads/likes/updated | vision evidence | 4-bit checkpoint (repo id, GB) | live provider | context |
|---|---|---|---|---|---|---|---|---|
| llmfan46/gemma-4-31B-it-uncensored-heretic | gemma-4-31B-it; gemma4 dense VLM | 31.3B / 31.3B | apache-2.0 | 100.6K / 129 / 11 Jun 2026 | Base card: MMMU Pro 76.9%, OmniDocBench 1.5 edit distance 0.131, MATH-Vision 85.6%. KL 0.0541. MMLU 85.90 vs 86.50 base. | alonsoko/gemma-4-31b-it-abliterated-heretic-AWQ-W4A16, 19.1 GB, compressed-tensors, vision tower kept in bf16. It quantizes trohrbaugh/gemma-4-31b-it-heretic-ara (KL 0.0120), and its card documents vLLM only. | featherless-ai | 262,144 |
| llmfan46/Qwen3-VL-32B-Instruct-uncensored-heretic | Qwen3-VL-32B-Instruct; qwen3_vl dense | 33.4B / 33.4B | apache-2.0 | 420 / 2 / 9 Apr 2026 | Vision benchmarks appear only as images (unverified). KL 0.0141. MMLU 81.44 vs 82.44 base. Both preprocessor files are present. | none found (bf16 66.7 GB) | none | 262,144 |
| coder3101/Qwen3-VL-32B-Thinking-heretic-v2 | Qwen3-VL-32B-Thinking; qwen3_vl | 33.4B / 33.4B | apache-2.0 | 1.6K / 10 / 17 Jan 2026 | KL 0.0048. No video_preprocessor_config.json in the repo. | none found | featherless-ai | 262,144 |

**Top pick: Gemma-4-31B heretic.**
- It is the only vision candidate whose card quotes document benchmark numbers.
- 4-bit builds exist, and it has a live provider.
- Its vision encoder differs from the Qwen model already in the catalog.
- Its chat template contains tool-declaration macros (opened and checked).
- llmfan46/gemma-4-31B-it-qat-q4_0-uncensored-heretic-GPTQ-Int4 (19.2 GB) ships without processor_config.json, so the processor would have to come from another repo.

## Tool-use and long-context slot
| repo id | base and arch | params total/active | licence | downloads/likes/updated | tool and long-context evidence | 4-bit checkpoint (repo id, GB) | live provider | context |
|---|---|---|---|---|---|---|---|---|
| llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved | Qwen3.6-35B-A3B; qwen3_5_moe hybrid MoE VLM | 35.1B / about 3B | apache-2.0 | 89.7K / 37 / 9 May 2026 | Base card (read via WebFetch): TAU3-Bench 67.2, MCP-Atlas 62.8, MCPMark 37.0, SWE-bench Verified 73.4. KL 0.0015, the lowest seen. | llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-GPTQ-Int4, 22.3 GB | featherless-ai | 262,144; base card says extensible to 1,010,000 |
| darkc0de/Muse-Glimmer-30B-heretic | Muse-Glimmer-30B; muse_glimmer dense VLM | 29.8B / 29.8B | apache-2.0 | 6.8K / 15 / 10 Aug 2026 | Base card: MCP Atlas 75.5, Gaia2 43.3, AA-LCR 80.0, Beam128K 65.1. KL 0.0743. Chat template contains tool macros (opened and checked). | none found (bf16 59.6 GB; only a W8A8 build exists) | none | 131,072 |
| llmfan46/Qwythos-9B-Claude-Mythos-5-1M-uncensored-heretic | empero-ai tune of Qwen3.5-9B; qwen3_5 | 9.4B / 9.4B | apache-2.0 | 20.9K / 8 / 29 Jun 2026 | 7 of 7 on the author's own 7-prompt tool harness. Long context was only "smoke tested at ~137k". KL 0.0123. | not needed (bf16 18.8 GB) | featherless-ai | 1,048,576 via static YaRN x4 over 262,144 |

**Top pick: Qwen3.6-35B-A3B MTP-Preserved.**
- It has the best fidelity to base in the survey (KL 0.0015).
- The tool block was opened and checked in the GPTQ repo's chat_template.jinja.
- The same author publishes a GPTQ-Int4 build, and the bf16 repo has a live provider.
- The config gives 10 full-attention layers, 2 KV heads and head_dim 256. That works out to about 20 KB of bf16 KV cache per token, or about 5.4 GB at 262,144 tokens (derived from config, not measured).
- About 3B active parameters suits ZeroGPU time limits.

## Rejected
- llmfan46/Qwen3-Coder-Next-Uncensored-Heretic: 79.7B, KL 0.1488. The only 4-bit build, trohrbaugh/Qwen3-Coder-Next-heretic-nvfp4, is 47.5 GB and leaves no headroom in 48 GB.
- Solstice-AI/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-NEO-CODER-NVFP4: its coding table (SWE-bench Pro 61.7, QwenSWEBench 79.0, LiveCodeBench v6 90.3) matches the base Qwen/Qwen3.8-27B card number for number. It is not a measurement of the fine-tune. NVFP4 also targets vLLM on Blackwell.
- AEON-7/Qwen3.6-35B-A3B-heretic-NVFP4: 1.4M downloads, but NVFP4 for vLLM on DGX Spark. Its card records a past defect in vision tensor naming.
- DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NEO-CODER-MAX-MTP-GGUF and its mirrors: GGUF only.
- nerkyor/Qwen3.8-27B-EfficientThink-Uncensored-K3-Opus5-Grok4.6-GPT5.6Sol-SFT-SimPO-DFlash2: weights sit in subfolders and there is no root config.json.
- TitleOS/Qwen3-Coder-30B-A3B-IT-Heretic: KL 0.4530, the worst fidelity seen.
- PeetPedro/qwen2.5-coder-32b-heretic-swe-sft: the repo itself lacks the heretic tag.
- auttasak88/AgentWorld-35B-A3B-Heretic: an environment world model, not an agent policy. It ships no vision weights.
- trohrbaugh/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16-heretic: KL 0.0495 and config 262,144, but it is a Mamba-2 hybrid under the OpenMDW licence with no 4-bit build and 230 downloads.
- p-e-w/gpt-oss-20b-heretic-ara-v3: a sound fallback (native MXFP4 13.8 GB, context 131,072, KL 0.0554), but text-only with no provider.
- llmfan46/LongCat-Flash-Lite-Sparse-Ultra-Uncensored-Heretic-Native-MTP-And-LSA-Preserved: 69.1B with custom_code.
- Devstral: a tag-filtered search returned no repository.

## Gaps
- No checkpoint was load-tested. A tag search for "bnb" found only two small Gemma-3 repos, so no finalist has a bitsandbytes 4-bit build. The formats on offer are auto-round, GPTQ and compressed-tensors, and their kernels are unverified on ZeroGPU.
- Every capability benchmark quoted describes the unmodified base model. The two exceptions are the ARC-C and HumanEval figures in the coding row. After processing, the cards report only KL plus MMLU or PIQA.
- The Qwen3-Coder and Qwen3-VL cards publish benchmarks as images, so those numbers are unverified.
- Provider status is a snapshot from 2026-09-19, and featherless-ai was the only provider seen. Download counts come from hub_repo_details.
- The model already listed, heretic-org/Qwen3.8-27B-heretic-ara (KL 0.0535, live on featherless-ai), was also checked. The Qwen3.8-27B base card reports:
  - Coding: SWE-bench Pro 61.7, Terminal Bench 2.1 73.0, LiveCodeBench v6 90.3.
  - Documents: OmniDocBench 1.5 91.1, CharXiv (RQ) 83.7.
  - Agent: CoWorkBench 70.7.
- The only coding figure directly comparable is SWE-bench Pro, which only the two tool-slot models report. The Qwen3.8-27B base score of 61.7 is higher than Qwen3.6-35B-A3B at 49.5 and Muse Glimmer at 51.2.
- Meta's own table ranks Qwen3.6-27B above Gemma4-31B on OmniDocBench v1.5, 77.8 vs 72.5.
- On card evidence, the coding and vision slots are better filled by the model already listed.
- Only the tool-use slot gains something new. The Qwen3.6-35B-A3B pick adds speed (about 3B active parameters). Muse Glimmer adds an MCP Atlas score of 75.5, a benchmark the Qwen3.8 card does not report.