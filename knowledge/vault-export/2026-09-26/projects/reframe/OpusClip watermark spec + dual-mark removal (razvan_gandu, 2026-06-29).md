---
title: OpusClip watermark spec + dual-mark removal (razvan_gandu, 2026-06-29)
type: report
permalink: main/projects/reframe/opus-clip-watermark-spec-dual-mark-removal-razvan-gandu-2026-06-29
tags:
- opusclip
- watermark
- propainter
- reframe
- razvan_gandu
- video
---

# OpusClip watermark spec + dual-mark removal (razvan_gandu)

Job: remove ALL OpusClip watermarks from 41 Romanian-politics vertical shorts (406x720, 30fps) in `~/Downloads/razvan_gandu/`, ~0 deterioration. Deliverable: `gdrive:shorts_d/` (original `Razvan_Dumitrescu_Ai_aflat_Ionut_Cristache_FULL.mp4` at root + 41 ordered clips in `shorts/`). Reusable technique → skill `video-watermark-removal` (updated 2026-06-29 with the dual-mark section).

## OpusClip renders TWO watermarks (free tier)
1. **Top bug:** static "(.) OpusClip" logo, top-center, persistent. Semi-transparent.
2. **Secondary animated mark:** vertical "Created with (.)" on the LEFT edge, ~t3.0-8.5s playback: the text holds, then the (.) icon scrolls UP the left edge and fades out. **Per-clip fade timing varies ~±1s** (not frame-synced across exports).

**No free clean source exists.** The watermark is **render-baked server-side into BOTH the preview and the export** on the free tier — it is NOT a client overlay you can scrape pre-render. A clean export requires a paid upgrade. (Do NOT pay/upgrade on the user's account — that is a financial action the user must do themselves.)

## Removal method (what worked)
- **Top bug:** ProPainter flow-guided temporal inpaint, tight logo mask, time-chunked, NCC-template verified 0/41. (v2 set.)
- **Secondary mark:** the **cross-clip-average phase-mask** method (the mark is a FIXED-POSITION overlay, identical across all clips at a given playback time; only content behind differs). Average frame-k over all clips → overlay stays sharp/white, content blurs dim → threshold → per-frame PHASE mask of the overlay footprint → ProPainter fills small per-frame holes from clean neighbours. Refinements: fill the (.) ring to a solid disk; brightness-match the fill to the boundary ring (±22) to kill the seam over a dark suit.
- **38 clips** (mark over dark/simple bg): clean via the generous-column / phase-mask path.
- **Clips 12, 25:** the subject sits in the left region → per-frame phase masks (tight) → verified PERFECT.
- **Clip 35 (the one hard case, FLAGGED):** mark over a SATURATED-WHITE ANIMATED plexus background + a ~1.5s-late fade. ProPainter has no clean temporal neighbour (mark present whole window) and color can't separate opaque-white mark from saturated-white animated content. Best version (`test_35d`): prominent text + (.) fully removed, ⊙-over-suit clean, suit-patch artifact fixed via a per-clip mask (short ~0.6s past-union for the scrolling icon + static top-band for lingering text + stop-masking-the-suit-once-the-icon-leaves). Residual = a FAINT fade-tail trace at 7.6-8.2s, **imperceptible at normal playback** (only visible under 3x CLAHE + zoom). Flagged per user's "remove fully, flag imperfect ones".

## Verification
- All-41 left-mark contact sheet (`all_41_leftmark_qc.py`): peak neutral-white frame per clip, CLAHE-boosted. **No "Created with"/(.) glyph in any of the 41.** High neutral-white scores were all legit broadcaster branding ("Gândul prezintă / AI AFLAT cu IONUȚ CRISTACHE" lower-third — KEPT, it is original content, not a watermark) or bright scenes (clip 13 white bg, white shirts).
- Top bug: NCC gate 0/41 (v2; left-mark removal only touches the left ROI so top region is unchanged in v3).
- Final: gdrive `shorts/` re-uploaded with v3 (rclone check = 0 differences, 41 hash-matched).

## Outcome
**40/41 perfect; clip 35 carries a faint sub-second fade-tail trace** over its animated-plexus background (flagged, imperceptible at normal speed). Original purpose: FB Reels auto-upload + a future agent analyzing how OpusClip composes/styles its shorts. Scripts in `~/Downloads/razvan_gandu/`: `build_phase_masks.py`, `propaint_left_phase.py`, `build_mask_clip35.py`, `all_41_leftmark_qc.py`, `pp_verify.py`.

## Clip 35 — pushed further (2026-06-29), 3 approaches tried, all fail (don't re-walk)
Asked to push the one flagged clip. Confirmed test_35d is the ceiling for a local method:
- **Larger ProPainter context (CTXF=200):** no tail improvement + introduced a green/olive tint on the suit (distant frames don't match the fast-moving plexus → flow degrades with temporal distance).
- **Alpha-unmixing** `bg=(obs-a*255)/(1-a)` with the sharp per-phase alpha glyph from dark clips: auto-lag estimate failed (d=0 — the plexus is itself neutral-bright so the self-gate isn't mark-specific); forcing lag=30 (1s) manufactured a clear ⊙ GHOST in the already-clean suit and still didn't fix the top tail. Root failure: (a) mark + plexus share the saturated-white colour → the unmix equation is degenerate where bg≈255; (b) the fade lag is NON-UNIFORM (text vs icon fade at different rates) so no single time-shift aligns the glyph → misalignment subtracts white at the wrong place = ghost.
- **Lesson:** when a white watermark sits over a SATURATED-WHITE ANIMATED background, neither flow-inpainting (no clean temporal neighbour) nor alpha-matting (degenerate colour + non-uniform lag) can separate them locally. The only true fix is the un-watermarked SOURCE (paid tier). Captured in the `video-watermark-removal` skill's negative-results bullet. test_35d (prominent mark gone, suit clean, faint sub-second tail) is final; gdrive holds it (hash a984e82b...).