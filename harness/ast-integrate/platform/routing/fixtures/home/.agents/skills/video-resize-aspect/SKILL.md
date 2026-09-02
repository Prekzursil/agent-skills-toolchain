---
name: video-resize-aspect
description: "Use when changing a video's ASPECT RATIO or RESOLUTION for social delivery (9:16 / 1:1 / 4:5 / 16:9), i.e. turning a horizontal source into a vertical Reel/Short, squaring a clip, or scaling to a fixed canvas. Covers the exact scale + crop (cover) filter math this codebase uses, the SAR/DAR +."
---

# Video resize / aspect-ratio change (geometry layer)

How to change a video's frame size or aspect ratio correctly in the media_studio
sidecar. This is the **pure geometry** layer: dimension math + the ffmpeg
`-vf` filter chain. Subject tracking, beat zoom, and multi-speaker layout sit on
top of it and all funnel through the same `scale=...:flags=lanczos,setsar=1`
primitive documented here.

## Source of truth (read these — every command below is copied from them)

- `sidecar/media_studio/features/aspect.py` — the canonical aspect registry:
  `ASPECT_PRESETS`, `output_dimensions()`, `parse_aspect()`, `even()`. **This is
  the single source of truth for what 9:16 / 1:1 / 4:5 mean.** Both reframe
  engines and the export catalog import it so they can never drift.
- `sidecar/media_studio/features/director_op_engines.py` (`build_reframe_argv`,
  ~L555-588) — the in-engine **center-crop → scale** aspect change.
- `sidecar/media_studio/features/reframe_claudeshorts.py` (`build_reframe_argv`,
  ~L387-420) — the one crop+scale pass with `flags=lanczos,setsar=1` + libx264/aac.
- `sidecar/media_studio/features/reframe_multispeaker.py` (~L559-561) — per-region
  `crop=...,scale=...:flags=lanczos,setsar=1` chain (same primitive, tiled).
- `sidecar/media_studio/ffmpeg.py` — `build_convert_argv` (the generic `scale`
  option), `resolve_binary`, and the progress-streaming `run()` (the stderr-drain
  + out_time pitfalls live here).
- `sidecar/media_studio/features/media_compat.py` (`build_proxy_argv`, ~L243-274)

### 1. The dimension math (from aspect.py — do NOT re-derive)
### 2. The recipe this codebase actually uses: COVER (center-crop → scale)
### 2a. Simple, source-agnostic aspect change (director_op_engines.py)
### director_op_engines.build_reframe_argv  (L570-572)
### 2b. The quality pass (reframe_claudeshorts.py / reframe_multispeaker.py)
### reframe_claudeshorts.build_reframe_argv  (L406-408)
### 2c. Generic scale-only (no aspect change) — ffmpeg.py convert option
### ffmpeg.build_convert_argv (L157-160)
### 3. Pitfalls that actually bite (each maps to repo code/comments)
### 4. "Contain / letterbox-pad" — NOT in this repo (standard ffmpeg, flagged)
### STANDARD FFMPEG (not in this repo) — fit-inside + center-pad to 1080x1920:
### 5. Resize-in-place / scaling effects (zoom.py)
