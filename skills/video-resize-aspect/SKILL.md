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
  — the `scale=-2:720` even-width playback-proxy pattern.
- `sidecar/media_studio/features/zoom.py` — `zoompan` (resize-in-place / Ken Burns).
- `sidecar/media_studio/features/panorama_stitch.py` — tall-canvas composite for
  scrolling reconstruction (OpenCV, not ffmpeg scaling).

---

## 1. The dimension math (from aspect.py — do NOT re-derive)

The curated social aspects are all **1080-wide** (OpusClip / IG / TikTok delivery):

| aspect | output (w×h) | use |
|--------|-------------|-----|
| `9:16` | **1080×1920** | Reels / TikTok / Shorts / Stories (DEFAULT) |
| `1:1`  | **1080×1080** | Instagram feed (square) |
| `4:5`  | **1080×1350** | Instagram / Facebook feed (portrait) |

`output_dimensions(aspect)` returns those three from `ASPECT_PRESETS` directly.
For **any other** positive ratio it falls back to "fit the long edge to 1920,
round the short edge to even":

```python
# aspect.py output_dimensions() — generic fallback (e.g. 16:9 -> 1920x1080, 3:4 -> 1440x1920)
w, h = parse_aspect(norm)
if h >= w:   # portrait/square: fix HEIGHT
    return even(round(1920 * (w / h))), 1920
else:        # landscape: fix WIDTH
    return 1920, even(round(1920 * (h / w)))
```

`even(n)` rounds **up** to the nearest even value. **This is not cosmetic** —
libx264 (yuv420p, 4:2:0 chroma subsampling) requires both dimensions even or the
encode fails. Always size through `output_dimensions`/`even`, never hand-pick odd
numbers.

`parse_aspect` accepts `"W:H"` **or** `"WxH"` (it `.replace("x", ":")`) and
fails loud (`ValueError`) on anything that is not two positive integers. The
export catalog uses `require_supported_aspect()` to reject parseable-but-uncurated
ratios (e.g. `16:9`) so it can only ever persist a render target the pipeline offers.

---

## 2. The recipe this codebase actually uses: COVER (center-crop → scale)

**Key fact, stated up front for honesty:** the reframe engines **do not
letterbox/pad**. To hit a new aspect they carve a centered window of the *target*
ratio out of the source (cover/fill) and then scale that window to the canvas.
Nothing is padded; edges are cropped away. (`pad=` appears nowhere for video in
this repo — only `apad` for audio.)

### 2a. Simple, source-agnostic aspect change (director_op_engines.py)

```python
# director_op_engines.build_reframe_argv  (L570-572)
aw, ah = _aspect_ratio(aspect)                 # e.g. 9,16
width, height = _reframe.output_dimensions(aspect)   # 1080,1920
vf = f"crop=ih*{aw}/{ah}:ih,scale={width}:{height}"
```

Exact argv (paths are single argv elements — never `shell=True`):

```
ffmpeg -hide_banner -nostdin -y -i <in> \
  -vf "crop=ih*9/16:ih,scale=1080:1920" \
  -c:a copy -progress pipe:1 -nostats <out>
```

Why `crop=ih*aw/ah:ih`: it is driven by **input height (`ih`)**, so the crop
window is `(ih·aw/ah) × ih` — the largest centered rectangle of the target ratio
that fits any input size. ffmpeg's `crop` defaults to centered when x/y are
omitted. Then `scale` maps it to the contract dimensions. The result genuinely
has the target aspect — never a no-op.

### 2b. The quality pass (reframe_claudeshorts.py / reframe_multispeaker.py)

When the crop window is computed by a tracker (or x drifts over time), the same
primitive carries `flags=lanczos` + `setsar=1`:

```python
# reframe_claudeshorts.build_reframe_argv  (L406-408)
vf = (
    f"crop={crop['w']}:{crop['h']}:'{x_expr}':{crop['y']},"
    f"scale={out_w}:{out_h}:flags=lanczos,setsar=1"
)
```

```
ffmpeg -hide_banner -nostdin -y -i <in> \
  -vf "crop=W:H:'<x_expr>':Y,scale=1080:1920:flags=lanczos,setsar=1" \
  -c:v libx264 -c:a aac -progress pipe:1 -nostats <out>
```

Two non-obvious bits:
- **`flags=lanczos`** — high-quality downscale. The default (bilinear) softens
  text/faces; for a 1920-tall source → 1080 this is a visible difference. Use it
  on every social downscale.
- **`setsar=1`** — see pitfall #2; this is the one that bites.
- The crop **x expression is single-quoted** (`'...'`) inside the filter string
  because its `if(...)` form contains commas that would otherwise be parsed as
  filter-arg separators. Because this is an argv list (no shell), the quotes
  reach ffmpeg verbatim — do **not** strip them.

### 2c. Generic scale-only (no aspect change) — ffmpeg.py convert option

The convert feature exposes a free-form `scale`:

```python
# ffmpeg.build_convert_argv (L157-160)
vf.append(f"scale={str(scale).replace('x', ':')}")   # accepts "1280:720" or "1280x720"
```

For a **pure resize that preserves aspect with an even result**, use `-2`
(media_compat proxy pattern):

```
# media_compat.build_proxy_argv (L268) — scale to 720 tall, width auto-even, universal decode
ffmpeg ... -vf "scale=-2:720" -pix_fmt yuv420p -c:v libx264 -preset veryfast -crf 23 ...
```

`scale=-2:H` keeps the source aspect and forces the auto-computed dimension to a
**multiple of 2** (`-1` would allow odd → encode failure). Use `-2`, not `-1`.

---

## 3. Pitfalls that actually bite (each maps to repo code/comments)

1. **Odd dimensions → encode failure.** h264 + yuv420p needs even W and H. Always
   route sizes through `aspect.even()` / `output_dimensions()`, and use `scale=-2:…`
   (not `-1`) for auto dimensions. (`aspect.py:even`, `media_compat.py:246`.)

2. **Missing `setsar=1` → stretched output (SAR/DAR trap).** If the *source* has a
   non-square pixel aspect ratio (SAR ≠ 1, common in DV/anamorphic/broadcast),
   `scale` changes the storage dimensions but the stream's SAR rides along, so the
   player applies it again and the picture comes out squished or stretched. Both
   quality engines append **`setsar=1`** after `scale` to reset pixel aspect to
   square so DAR == W:H. Add it to any aspect-changing scale.
   (`reframe_claudeshorts.py:408`, `reframe_multispeaker.py:561`.)

3. **Cover-crop discards edges.** Because the engines crop-to-cover (§2), a
   horizontal source → 9:16 loses the left/right thirds. That is *intended* for
   subject-tracked reframe but surprising for a "just make it vertical" request —
   if the user needs the whole frame visible, that is a **contain/pad** job, which
   this repo does not do (see §4).

4. **stderr-pipe deadlock on long encodes ("stuck clip 1/5").** `ffmpeg.run()`
   captures `stderr=PIPE`; ffmpeg chats on stderr even with `-nostats` (banner,
   stream info, libass/font logs). If you `PIPE` stderr and never read it, the
   ~64 KB pipe buffer fills and the encode **blocks forever**. `run()` drains
   stderr on a daemon thread (keeping a 40-line tail for error reporting). If you
   spawn ffmpeg yourself, drain stderr or don't pipe it. (`ffmpeg.py:254-272`.)

5. **`out_time_ms` is microseconds, not milliseconds.** ffmpeg's `-progress`
   stream mislabels it. `_pct_from_progress` divides `out_time_ms`/`out_time_us`
   by `1_000_000.0`. Don't treat it as ms. (`ffmpeg.py:202-218`.)

6. **Always argv-list, never `shell=True`.** Every builder returns a list; paths
   with spaces are one element and just work. `run()` raises `TypeError` if handed
   a shell string. (`ffmpeg.py:243`, `reframe.py` contract.)

7. **`-progress pipe:1 -nostats` is required for the progress UI.** It routes the
   key=value progress stream to stdout so `run()` can parse a real percentage;
   without it you get coarse/no progress. Every builder includes it.

8. **`-y` overwrites; output-path collision guard.** Builders pass `-y`. The
   convert feature adds a `.converted` infix when the derived dest equals the
   source so a re-encode never clobbers the original. (`convert.py:output_path`.)

9. **(verthor/WSL engine only) never pipe the script via stdin.** The WSL verthor
   adapter passes the script as an argv element (`wsl bash <script> …`); piping it
   `tr | bash` over stdin corrupts mediapipe (it reads stdin). Not a scaling issue
   but it lives in the same `reframe.py` and will eat hours if hit.

---

## 4. "Contain / letterbox-pad" — NOT in this repo (standard ffmpeg, flagged)

This codebase only does **cover** (§2). If a task genuinely needs the whole source
frame visible inside the target canvas (black bars), that is the standard ffmpeg
`scale … force_original_aspect_ratio=decrease` + `pad` idiom. It is **not present
in media_studio** — use it only as an explicit, separate path and say so:

```
# STANDARD FFMPEG (not in this repo) — fit-inside + center-pad to 1080x1920:
ffmpeg -i <in> -vf \
 "scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,\
  pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1" \
 -c:v libx264 -c:a copy <out>
```

`force_original_aspect_ratio=decrease` scales to fit *inside* the box; `pad`
centers it and fills the rest. Mirror image of the repo's cover-crop. Keep
`flags=lanczos` and `setsar=1` for the same reasons as §2/§3.

---

## 5. Resize-in-place / scaling effects (zoom.py)

For a **subtle scale animation that keeps the frame size constant** (Ken-Burns
slow push + punch-in on beats), use `zoompan`, not a one-shot scale:

```python
# zoom.build_zoom_filter — keeps s=WxH, centers the zoom window
f"zoompan=z='<z_expr>':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps}"
```

Notes: `d=1` = one output frame per input frame (otherwise zoompan holds frames
and stutters); `s=WxH` fixes output size; `fps` must match the timebase the
`on`-based `z` expression assumes (DEFAULT_FPS = 30, the §4 vertical pipeline
rate). Zoom is video-only — `build_zoom_argv` re-encodes video (`libx264`) and
**stream-copies audio** (`-c:a copy`). Z is clamped to `MAX_ZOOM = 1.5` so the
crop never starves the frame.

---

## 6. Worked example: horizontal 1920×1080 → vertical 9:16 Reel

Goal: turn a landscape clip into a 1080×1920 vertical for Reels, cover-crop
(repo default), best quality.

1. Resolve dimensions (don't hardcode):
   ```python
   from media_studio.features import aspect
   w, h = aspect.output_dimensions("9:16")   # (1080, 1920)
   ```
2. Build the argv (cover-crop → lanczos scale → setsar):
   ```
   ffmpeg -hide_banner -nostdin -y -i input_1920x1080.mp4 \
     -vf "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos,setsar=1" \
     -c:v libx264 -c:a copy -progress pipe:1 -nostats output_1080x1920.mp4
   ```
   - `crop=ih*9/16:ih` → `crop=607.5≈608:1080` centered (the 9:16 slice of a
     1080-tall frame). The left/right of the landscape frame is dropped — expected.
   - `scale=…:flags=lanczos` → high-quality up to 1080×1920.
   - `setsar=1` → square pixels so the player shows true 9:16.
3. Run it through `ffmpeg.run(argv, total_sec=ffprobe_duration(in))` so progress
   is a real percentage and stderr is drained (no deadlock).

If instead the whole landscape frame must stay visible (bars top/bottom), switch
to the §4 contain/pad recipe and tell the user the repo's reframe engines don't
do that.

---

## Quick checklist before shipping a resize

- [ ] Dimensions from `aspect.output_dimensions()` (even, curated). 
- [ ] `flags=lanczos` on any downscale.
- [ ] `setsar=1` after any aspect-changing `scale`.
- [ ] `scale=-2:H` (not `-1`) for aspect-preserving auto-size.
- [ ] argv list, `-y`, `-progress pipe:1 -nostats`.
- [ ] stderr drained if you spawn ffmpeg yourself.
- [ ] cover-crop vs contain-pad decision made explicit (repo = cover only).
