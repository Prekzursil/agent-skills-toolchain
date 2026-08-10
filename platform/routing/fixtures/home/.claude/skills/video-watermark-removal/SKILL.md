---
name: video-watermark-removal
description: "Use when removing a static logo, watermark, or TV bug from a video seamlessly (so it is not noticeable it was ever there). PRIMARY method = ProPainter flow-guided temporal inpaint on a TIGHT logo-only mask (pulls REAL background pixels from neighbouring frames -> sharp, no soft haze), CHUNKED in time so it fits a small GPU and avoids OOM, with PER-FRAME presence gating so frames where the logo is occluded (e.g. a hook card) are left pristine. big-LAMA per-frame is the fast fallback but its fill is visibly SOFT. Plus the pitfalls that actually bite: tight logo-shaped mask not a generous box (oversized boxes smear faces), don't inpaint frames where the logo is absent, chunk long clips to bound RAM, retry transient WSL2 CUDA failures, run as a detached WSL daemon watched by a persistent Monitor, and PROVE clean with a logo-template NCC gate across the whole timeline (never claim done on a single-frame check). Includes a companion method for a FIXED-PATH animated overlay (fades or scrolls along a fixed screen path, identical across many clips) via cross-clip-average phase masks; still NOT for arbitrary moving watermarks or full-frame logos."
---

# Video Watermark / Logo Removal (seamless)

Remove a **static, semi-transparent logo/bug** from a video so cleanly it is not noticeable it was ever there. Proven on 41 vertical shorts (406x720) end-to-end. The OpusClip-specific instance (watermark spec, download, API) lives in basic-memory: `main/projects/reframe/opus-clip-watermark-removal-lama-inpaint-recipe-ops-lessons-...`. This skill is the **reusable technique**.

## When to use / when NOT
- USE for: a fixed-position (or slowly-varying) opaque/semi-transparent logo over real content (faces, hair, background), where the area behind it is small and not a critical detail.
- DO NOT use for: moving/animated watermarks (need ProPainter/E2FGVI temporal inpaint), full-frame tiled marks, or marks over fine text you must recover (inpainting invents plausible texture, it cannot recover hidden detail).

## Approach decision (pick fast, don't agonize)
1. `ffmpeg delogo` — REJECT for anything visible. Interpolates from the box border → a blur patch. Obviously edited.
2. **ProPainter, flow-guided temporal inpaint — PRIMARY (best quality).** Even for a STATIC logo, the subject moves slightly, so optical-flow propagation copies the REAL background that was exposed in neighbouring frames into the masked region — actual detail recovery, sharp, no soft haze, no flicker. This is the only thing that produced a truly seamless result on real faces/hair. Run it on a **cropped ROI** around the logo (e.g. ~280×200) so VRAM is tiny (~1.4 GB on a 6 GB card), and **chunk in time** (see v4 below) so RAM is bounded.

### Pipeline
### 1. Localize
### 2. Mask discipline (the part that makes or breaks it)
### 3. Inpaint one clip
### 4. Batch + heal transient GPU failures
### Pitfalls (all hit in practice)
### Secondary / animated overlay marks — the cross-clip-average phase-mask method
### QC (do not skip — "seamless" is the whole point)
### Env (WSL2 + CUDA, the tested setup)
### Reference scripts
