---
title: RVC realtime voice changer project 2026-09-20
type: note
permalink: main/projects/rvc-realtime-voice-changer-project-2026-09-20
tags:
- project
- rvc
- voice-changer
- audio
- elevenlabs
- modal
---

# RVC realtime voice changer (D:\Research\tools\rvc-realtime-voice-changer)

Real-time mic→RVC→virtual-cable voice morph for ElevenLabs; console app
(voice_changer.py), built, trained and verified 2026-09-20. COMPLETE.

- [fact] Vendored, byte-identical, from RVC-Project/Retrieval-based-Voice-Conversion-WebUI
  tag 2.3.260718 (commit 8f2fdbf): infer/* (module/, rtrvc.py, rmvpe.py, hubert.py — the
  2026 refactor is fairseq-free, uses Transformers-format ContentVec from
  assets/hubert_base/), tools/cuda_graph.py, configs/{v1,v2}/*.json + full train/ stack.
  Local shims (NOT upstream): configs/config.py (RVC_DEVICE/RVC_HALF env), i18n/i18n.py.
  Upstream v2 sample rates are 32k/48k ONLY (no 40k v2 — verified at multiple tags).
- [fact] Assets from HF lj1995/VoiceConversionWebUI at repo ROOT (hubert_base/*, rmvpe.pt →
  local assets/rmvpe/rmvpe.pt, pretrained_v2/f0G48k+f0D48k, mute.zip→logs/mute).
- [fact] Measured on RTX 4050 laptop 6GB (torch 2.7.1+cu128, fp16): realtime RTF 0.80 @
  block 100ms no-index; with index@0.82 → RTF 1.05 @100ms, 0.86 @150ms (live preset:
  --block-time 0.15 --extra-time 1.5). Sub-100ms live latency NOT reachable on this GPU;
  floor ~250-300ms. VB-Audio Virtual Cable already installed on the box; app auto-prefers
  CABLE/BlackHole outputs. See docs/BENCHMARK.md.
- [fact] TRAINED MODEL: models/sotu2026.pth + sotu2026.index (v2 48k, e160) trained from
  the user's SOTU 2026 mp3s (25 parts × 30min, single speaker, target f0 median 178.8Hz).
  10 min sliced across parts (skip first 4 min/part). LOCAL training on the 4050 kept
  dying (cuDNN EXECUTION_FAILED at loss_disc.backward — VRAM/thermal; bs6 and bs4 both
  crashed ~e110; laptop throttles to 39W/80C). FIX: scripts/train_modal.py runs the whole
  pipeline on Modal (workspace dariabonk99) — H100, bs32, 160 epochs ≈ 7 min ≈ $0.5,
  artifacts auto-download into models/.
- [fact] Demo conversions (out/demo_output_*_as_sotu2026.wav) run clean end-to-end, but
  YIN reads output f0 median ~69 Hz vs target's 179 Hz — the morph's register sits LOW
  (either undertrained-G register bias from the pretrained base + applause-contaminated
  10-min data, or YIN octave-halving on neural audio; RMVPE-probe attempt was itself
  broken and discarded). Owner listens; remedies: --transpose N to lift, or modal retrain
  with --minutes 25 --epochs 300 (one command, ~$1).
- [decision] Training orchestration = scripts/train_model.py (local, resumable) and
  scripts/train_modal.py (cloud H100, preferred on this box). Offline preview:
  scripts/convert_file.py (same Engine as live streaming).
- [fact] Gotchas hit and fixed (do not re-learn): (1) vendored scripts must run as
  `python -m train.X` with PYTHONPATH=root — direct paths cause train package→train.py
  self-import; (2) train.py requires -c/--if_cache_data_in_gpu; (3) bs≥6 OOMs on 6GB
  (→ local bs4 / modal bs32); (4) streaming reverb needs PADDED overlap-save carry
  (tail len L-1 vs chunk n — slice alone broadcasts wrong); (5) HF asset URLs are
  repo-root paths and preprocessor_config.json is only 225B (size-check threshold <225B);
  (6) modal add_local_dir uses `ignore=` predicate (True=exclude), NOT `condition=`;
  (7) transformers 5.x + torch<2.6 refuses .bin checkpoints (pin transformers==4.46.3
  on modal image); (8) extract_f0 exits 0 even when every file fails — assert stage
  outputs non-empty; (9) faiss IVF nprobe_1 search can return -1 rows → vendored code
  skips retrieval that block (harmless, prints warning).

Related: [[compaction-checkpoint-rvc-voice-changer]]
