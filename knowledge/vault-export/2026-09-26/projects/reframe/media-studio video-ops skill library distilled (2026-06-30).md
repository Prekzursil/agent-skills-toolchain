---
title: media-studio video-ops skill library distilled (2026-06-30)
type: note
permalink: main/projects/reframe/media-studio-video-ops-skill-library-distilled-2026-06-30
tags:
- skills
- video
- media-studio
- distilled
- reframe
- transcribe
- ffmpeg
---

# media-studio video-ops skill library — distilled to ~/.claude/skills (2026-06-30)

User: "there is more apart from reframe-transcribe, reframe-video-cutting — cut, join, resize, translate, etc." → distilled the FULL video-operations family from the REAL media_studio source (sidecar/media_studio/features/*), each a robust SKILL.md modeled on video-watermark-removal (real ffmpeg argv + pitfalls + GPU/HF pins, verbatim-cited from source). HIGH confidence, no invented commands.

## INSTALLED skills (~/.claude/skills/<name>/SKILL.md)
- **reframe-transcribe** — faster-whisper(large-v3-turbo GPU/small CPU) + SEPARATE ctc-forced-aligner for word timing (NOT WhisperX — crashes on Romanian); HF upgrades whisper-v3-turbo/parakeet-tdt-0.6b-v3/canary-1b-v2.
- **reframe-video-cutting** — LLM-on-transcript 2-pass virality rubric + deterministic boundary-snap (sentence/silence/scene) + TransNetV2+PySceneDetect; ffmpeg seek/concat gotchas; Lighthouse/Moment-DETR/DOVER/SmolVLM2 upgrades.
- **video-join-concat** — concat-demuxer vs concat-filter; codec/timebase/SAR mismatch; real argv from director_op_engines.py/reframe_multispeaker.py/fillers.py (the named nle_export/timeline are metadata-only, flagged honestly).
- **video-resize-aspect** — scale/pad/crop/aspect; h264-even-dims, setsar=1 stretch trap, -2 not -1, microsecond out_time_ms, 64KB stderr-pipe deadlock. (repo does cover-crop only; pad/contain flagged as standard-ffmpeg-not-in-repo.)
- **subtitle-translate** — translate/generate/export SRT-VTT-ASS + dub; TranslateGemma GGUF pins, MMS-300m aligner (CC-BY-NC) + RO overrides; RTL = verified absence (relies on libass/fribidi).
- **video-convert** — format/codec/container + batch + proxy; convert path sets NO pix_fmt/faststart (pitfall); CRF/preset/faststart.
- **video-stabilize** — vidstab detect+transform 2-pass; motion.py energy-gate; GPL libvidstab often missing (probe ffmpeg -filters), Windows `:`-separator break, optzoom crop↔FOV.
- **silence-trim** — silencedetect (noiseDb -30/minSilence 0.5/pad 0.1) → trim+concat + remap_cues so captions don't drift; pass-through returns keeps [(0,total)] not [].
- **caption-burn** — hardsub(libass/ASS) vs soft-mux(mov_text downgrade); karaoke per-word Dialogue + colour byte-swap (&H..); burn=irreversible (tracks.strip refuses kind=hard).
- **audio-extract-mix** — extract/mix/replace/duck + loudnorm LUFS -14; negative-map stream preserve; PANNs decode.
- **design-sync** (forged) — @dsCard bundle + DesignSync push flow (create_project→finalize_plan→write_files, main-session-pushes) + validate_cards.mjs.
PRE-EXISTING related: reframe (9:16), video-watermark-removal (ProPainter/big-LAMA logo inpaint).

Source bundles retained: scratchpad/distilled-skills/<name>/. Reframe HF-model adopt list + design-harness adopt/forge list in [[design-reframe-intel synthesis]] (task w6gauab69 output).
