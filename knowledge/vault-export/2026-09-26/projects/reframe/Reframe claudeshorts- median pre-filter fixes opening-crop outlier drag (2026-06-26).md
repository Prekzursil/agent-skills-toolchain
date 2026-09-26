---
title: 'Reframe claudeshorts: median pre-filter fixes opening-crop outlier drag (2026-06-26)'
type: note
permalink: main/projects/reframe/reframe-claudeshorts-median-pre-filter-fixes-opening-crop-outlier-drag-2026-06-26
tags:
- reframe
- speaker-tracking
- claudeshorts
- bugfix
- visual-verify
- median-filter
---

# Reframe claudeshorts median pre-filter fix + visual verify (2026-06-26)

Branch `feat/reframe-quality`, commit `0803b2d` (atop `2f7315b` TrackFix), pushed to origin.

## WHAT
Visual-verified the FIXED reframe via the APP's REAL pipeline on 3 RO interview shorts
(Georgescu TV interview, source `videoplayback (4).mp4`, 640x360 low-res TV studio).
Picked 3 moments incl. a PROFILE/off-center one (m05) + a wide two-shot far-right (m10).

## REAL-PIPELINE DRIVER (Downloads/reframe-romanian-shorts/real_pipeline_render.py)
Uses the app's actual modules, NOT hand-rolled:
- CUT (ffmpeg frame-accurate) -> REFRAME via `reframe.get_engine("claudeshorts")` (the
  no-WSL default = FIXED ClaudeShortsReframeEngine) -> CUES via
  `subtitles.cues_from_transcript` + `caption_polish.polish_cues` (Netflix CPL<=42/CPS/
  min-gap gate) -> karaoke `\k` from word timings rendered with the app's EXACT
  `caption.build_ass` style/margins -> burn via `caption.build_burn_argv`.
- TRANSCRIPT GOTCHA: faster-whisper transcript here has `word: None` on EVERY token
  (8954/8954) — only SEGMENT text is populated. So cue text MUST come from segments;
  karaoke word-timing is reconstructed by distributing segment tokens across the
  segment's word-timing spans. The prior hand-rolled worker used `w["word"]` -> empty.

## BUG FOUND + FIXED (the visual pass caught it)
m03 opening (~first 2s) showed the speaker pushed to frame edge / empty studio.
ROOT CAUSE: the zero-phase EMA in `smooth_centers` was SEEDED from the first detected
sample. A single early OUTLIER (t=1.5 cx=0.383, a stray left detection; steady subject
~0.64) dragged the OPENING crop to [182,384] while the face was at 410 (OUT).
FIX: added `median_prefilter` (length-3 sliding median, window shifted INWARD at the ends
so a lone spike AT index 0/n-1 — the opening crop, worst case — is outvoted by steady
neighbours) run BEFORE the forward+backward EMA. Constant track + sustained step returned
unchanged; only single-frame spikes pulled back. Opening moved to [315,517] (on subject).
`MEDIAN_WINDOW=3` constant added.

## VERDICT (honest, frames Read at multiple ts each)
- SPEAKER TRACKED y, incl. profile (m05) + wide two-shot far-right (m10): in frame &
  ~centered (face 0.45-0.65 within the 9:16 frame) throughout. m03 "empty left" is the
  source's own studio graphic behind a center-right speaker (crop IS centered on him) —
  inherent, not a tracking miss.
- SUBS IN BOUNDS y: hooks wrap to <=4 short lines inside MarginL/R=40; karaoke captions
  in bounds. PUNCTUATION clean. NO JITTER: phase-corr frame-to-frame |dx| mean 0.5-1.1px,
  max ~2px on 1080w (sub-2px = steady).
- Residual imperfection: source's own yellow chyron ("GEORGESCU:...") sits just above my
  karaoke caption (mild clutter, readable). Brief t=1-2 right-bias on cuts where the
  speaker is genuinely far-right in the source.

## GATE
WSL `cd .../sidecar && /tmp/msv/bin/python -m pytest --cov=media_studio --cov-branch
--cov-fail-under=100 -q` = 100.00% line+branch, 4098 passed. Pre-commit (ruff lint+format,
gitleaks) clean. pull --rebase clean, normal push (no force).

## LESSON
Visual-verify (extract frames -> Read PNG) CATCHES tracker bugs that 100% unit coverage
misses — the TrackFix passed all tests but had an EMA cold-start outlier-drag only the
rendered opening frames revealed. EMA seeded from sample[0] is fragile to an opening
outlier; a median pre-filter is the cheap robust guard.
