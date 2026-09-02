---
name: reframe-video-cutting
description: "Use when selecting and cutting moments from a long talk, podcast, interview, stream, or vlog into shorts with scene-aware, sentence-safe boundaries."
---

# Video Cutting / Clip Selection (the short-maker's heart)

Cut a long talking-head/podcast/interview video into a ranked set of short vertical-ready clips, and **select which moments are worth shipping**. This is the SELECT + BOUNDARY-SNAP + CUT half of a short-maker. The 9:16 reframe, captions, zoom, and brand overlay are downstream (see the `reframe` skill); watermark removal is a different skill (`video-watermark-removal`).

The canonical, battle-tested implementation is `Reframe/sidecar/media_studio/features/` (`select.py`, `boundary.py`, `scene_transnet.py`, `shortmaker.py`). This skill distills that REAL pipeline + the virality/highlight-detection upgrades, with sources cited and confidence graded.

## When to use / when NOT
- USE for: choosing the best N moments from a transcribed long video, snapping cut points cleanly, carving frame-accurate clips. Works for any spoken-word source (talk, podcast, interview, stream, lecture, vlog).
- DO NOT use for: visual reframing/cropping to 9:16, caption burn-in, watermark/logo removal, or pure b-roll/music videos with no speech (use the visual-only `candidates_from_curve` peak-pick path instead of the LLM path).

## The real pipeline (Reframe / media_studio)
```
transcript (+word timings)  ->  SELECT (features/select.py)        prompt + transcript -> ranked Candidates w/ virality factors
                            ->  BOUNDARY-SNAP (features/boundary.py) snap start/end to sentence-end / silence / scene-cut, never mid-word
   -- the two above = shortmaker.select() --

### 1. SELECT — LLM-on-transcript, two-pass rubric (PRIMARY)
### Duration modes (envelope is the single source of truth, shared with boundary.py)
### Map-reduce for long transcripts
### Clip-selection strategy — current (virality factors + percentile)
### 2. BOUNDARY-SNAP — deterministic, never mid-word (`features/boundary.py`)
### Detection commands (behind injectable seams)
### 3. Scene detection — TransNetV2 + PySceneDetect merge (`features/scene_transnet.py`)
### 4. CUT — frame-accurate ffmpeg carve (`shortmaker._lazy_cut`)
### Clip-selection upgrades — the virality / highlight stack (fold-in)
### External highlight-detection heads (the upgrade beyond Reframe's current stack)
### ffmpeg seek / concat gotchas (these actually bite)
