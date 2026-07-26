---
name: video-stabilize
description: "Use when stabilizing a shaky / handheld / camera-shake video so it looks steadied (locked-down or smooth-pan). PRIMARY method = ffmpeg libvidstab TWO-PASS — vidstabdetect (analyze → writes a .trf transforms file) then vidstabtransform (read the .trf → render the steadied clip), with adaptive."
---

# Video stabilization (ffmpeg libvidstab, 2-pass)

Steady a shaky clip. Real implementation lives in
`media_studio/features/stabilize.py` (the 2-pass vidstab engine) with the
motion-measurement helper in `media_studio/features/motion.py`. Both go through
the shared drained ffmpeg seam `media_studio/ffmpeg.py:run`. **Every ffmpeg argv
below is copied from those modules — nothing here is invented.**

## When to use vs NOT

USE it when the footage is genuinely shaky: handheld walking, body-cam, drone
buffeting, gimbal-less phone video, or any clip whose `motion.py` energy curve is
high *and erratic* (high-frequency jitter, not a smooth pan).

Do NOT use it when:
- The camera is on a tripod / locked-down — there is nothing to correct and the
  adaptive crop only throws away pixels.
- The motion is *intentional*: deliberate whip-pans, dolly moves, fast sports
  action. vidstab will fight the move and produce an uncanny "floaty" result.
- The shake is **rolling-shutter jello** (skew/wobble of vertical lines).
  vidstab models translation + rotation, not per-scanline shear — it will not fix
  jello and may amplify it. Use a deshake/rolling-shutter tool instead.
- The frames are motion-blurred from the shake itself. Stabilization re-aligns
  blurred frames; it cannot un-blur them. Re-shoot.
- ffmpeg has no libvidstab (see Pitfall 1) — then it is reported as unavailable,
  the clip is passed through unchanged, never silently "stabilized".

## The two passes (this is the whole method)

libvidstab cannot stabilize in one shot — it must first *analyze* the whole clip
to learn the camera trajectory, then *transform* against that trajectory:

```
PASS 1  vidstabdetect    decode → write transforms file (.trf)   [no video out]
PASS 2  vidstabtransform read .trf → render steadied clip
```

The `.trf` is an intermediate written next to the output (`<out>.trf`) and
cleaned up afterwards (`stabilize.py: StabilizeEngine._trf_path` / the `finally`
unlink). Progress is split 0–50 % (detect) / 50–100 % (transform).

### Exact commands

These are exactly what `build_detect_argv` / `build_transform_argv` emit
(`stabilize.py` lines ~115–184), with the default tunables.

PASS 1 — analyze (writes `out.trf`, produces no video via `-f null -`):

```bash
ffmpeg -hide_banner -nostdin -y -i IN.mp4 \
  -vf "vidstabdetect=shakiness=5:accuracy=15:result=OUT.trf" \
  -f null -progress pipe:1 -nostats -
```

PASS 2 — transform (reads `out.trf`, re-encodes h264, copies audio):

```bash
ffmpeg -hide_banner -nostdin -y -i IN.mp4 \
  -vf "vidstabtransform=input=OUT.trf:smoothing=10:optzoom=1" \
  -c:v libx264 -c:a copy -progress pipe:1 -nostats OUT.mp4
```

Notes baked into the source:
- `-f null -` on PASS 1: the detect pass only needs the `.trf`; decoding to null
  makes it fast (no encode).
- `-c:a copy` on PASS 2: the soundtrack is never touched by the pre-step.
- `-progress pipe:1 -nostats`: lets `ffmpeg.run` drain stdout (see Pitfall 4).
- `-nostdin`: stabilize is a pipeline pre-step; never let ffmpeg grab the TTY.

## Tunables (defaults from stabilize.py)

Read from `settings` by `_stab_settings`, each coerced to `int` so a stray wire
string can never reach the filter expression unparsed:

| setting key     | filter param | default | meaning |
|-----------------|--------------|---------|---------|
| `stabShakiness` | `shakiness`  | 5 (1–10) | how shaky the input is; raise for very jittery footage |
| `stabAccuracy`  | `accuracy`   | 15 (1–15) | detection accuracy; 15 = max (slowest analyze) |
| `stabSmoothing` | `smoothing`  | 10 | smoothing window in frames *before+after*; higher = steadier but more "locked-down"/floaty |
| `stabOptzoom`   | `optzoom`    | 1 | adaptive zoom mode — 1 crops/zooms just enough to hide the black borders the warp introduces |

### The crop / zoom vs field-of-view tradeoff

Warping each frame to cancel shake exposes empty (black) edges. `optzoom=1`
adaptively zooms in so those edges are pushed off-screen — the cost is **lost
field of view** and a slight resolution hit (you are upscaling a crop). The
steadier you ask for (higher `smoothing`), the more the trajectory deviates from
each raw frame, the *more* it must zoom, the *more* FOV you lose. So:
- Mild shake → low smoothing, minimal zoom, FOV mostly preserved.
- Violent shake → either accept a heavier crop (higher zoom) or accept residual
  black border judder. There is no free steadiness.
- `optzoom=0` would leave the borders visible (you'd have to crop in post). The
  module deliberately defaults to adaptive `optzoom=1`.

## Deciding IF a clip needs stabilization (motion.py)

`motion.py` measures per-window **motion energy** so you can gate stabilization
(and avoid "stabilizing" a tripod shot). Two pure measures, zero model downloads:

- `frame_diff_energy(prev, cur)` — mean `cv2.absdiff` / 255 → `[0,1]` (the floor
  default, `mode="absdiff"`).
- `farneback_flow_magnitude(prev_gray, cur_gray)` — mean dense optical-flow
  magnitude via `cv2.calcOpticalFlowFarneback(prev, cur, None, 0.5, 3, 15, 3, 5,
  1.2, 0)`, squashed `m/(m+1)` into `[0,1)` (`mode="flow"`, denser / more robust
  to illumination flicker).

`compute_motion_signals(path, duration, mode=...)` samples one frame per window
midpoint, scores adjacent pairs, min-max normalizes, and returns a `SignalTrack`.
Heuristic: a clip with *sustained high* motion energy that is *erratic* (not a
single smooth ramp) is a stabilize candidate; uniformly low energy = tripod =
skip. Note the normalized curve is **relative within the clip** — a flat
high-shake clip min-max-normalizes toward 0, so look at the raw `meta["raw"]`
magnitudes, not just the normalized `value`, when thresholding shake absolutely.

## Pitfalls that actually bite

1. **libvidstab is a GPL *build* option — it is often missing.**
   `vidstabdetect`/`vidstabtransform` exist only when ffmpeg was compiled
   `--enable-libvidstab`. A stripped/LGPL bundle has neither. The module probes
   with `ffmpeg -hide_banner -filters` (`vidstab_available`) and, if missing,
   emits the typed notice `stabilize.unavailable` and **passes the clip through
   unchanged** — the skip is always *reported*, never swallowed
   (`make_unavailable_notice` / `stabilize_clip`). Fix = rebuild/bundle ffmpeg
   with `--enable-libvidstab`. Verify yourself:
   ```bash
   ffmpeg -hide_banner -filters | grep vidstab
   ```
   Expect both `vidstabdetect` and `vidstabtransform`. The dev-host PATH ffmpeg
   (winget/gyan build) has it; a shipped LGPL bundle would not.

2. **Windows `C:\` paths break vidstab's `:` option separator.**
   vidstab uses `:` to separate filter options, so a Windows `.trf` path like
   `C:\out\clip.trf` makes ffmpeg read `C` as an option and `\out\clip.trf` as a
   value → garbage. The module forward-slashes the trf path before building the
   filter string: `str(trf_path).replace("\\", "/")` (both `build_detect_argv`
   and `build_transform_argv`). Always pass the `.trf` with forward slashes.

3. **The two passes MUST agree on the .trf and the input.** PASS 2's
   `input=<trf>` must be the file PASS 1 wrote with `result=<trf>`, and both must
   decode the *same* source. If PASS 1 failed/partial, the `.trf` is stale or
   empty and PASS 2 silently under-corrects. The engine treats a non-zero exit
   from *either* pass as fatal (`StabilizeError`, e.g. "vidstabdetect failed
   (ffmpeg exit N)") rather than rendering against a bad `.trf`.

4. **Never re-implement the ffmpeg drain.** Both passes go through
   `media_studio/ffmpeg.py:run`, which streams `-progress pipe:1` and drains
   stdout. This is the "29-min-freeze lesson": an undrained ffmpeg pipe fills its
   OS buffer and the process *hangs* on a long clip. That is why the argv carry
   `-progress pipe:1 -nostats` and why you must not call ffmpeg with a naive
   blocking `subprocess` that ignores stdout.

5. **Re-encode + timebase.** PASS 2 re-encodes video to `libx264` (the warp
   makes copy impossible) but does `-c:a copy`. If the source has variable frame
   rate or odd timebase, the analyze pass counts frames against the source
   timeline; a VFR source can drift. For pathological VFR, normalize fps before
   PASS 1 (`-r`/`fps` filter) so detect and transform share one frame grid.

6. **Don't stabilize twice / don't stabilize what you'll re-crop blindly.**
   Stabilization is a *pre-step* before reframe (`stabilize_clip` is called
   BEFORE reframe when `settings['stabilize']` is on). Running it after a reframe
   crop wastes the FOV budget twice. Order: stabilize → reframe.

7. **GPU note.** libvidstab is **CPU-only** (no CUDA path); the analyze pass is
   the slow part and scales with `accuracy`. There is **no Hugging Face model**
   on the default path — vidstab is a native ffmpeg filter and `motion.py`'s
   floor is pure OpenCV (in the venv, zero downloads). A higher-accuracy flow
   model (NeuFlow_v2, Apache-2.0, manifest #7) is only an *optional* injectable
   `MotionBackend` seam in `motion.py` for *measuring* motion — it does not do
   the stabilizing.

## Worked example

Steady `walk.mp4` (handheld, visibly jittery), default tunables, on Windows.

1. Probe availability (Pitfall 1):
   ```bash
   ffmpeg -hide_banner -filters | grep vidstab
   # vidstabdetect / vidstabtransform both listed → proceed
   ```
2. PASS 1 — analyze (note forward-slashed trf path, Pitfall 2):
   ```bash
   ffmpeg -hide_banner -nostdin -y -i "C:/clips/walk.mp4" \
     -vf "vidstabdetect=shakiness=5:accuracy=15:result=C:/clips/walk.stabilized.trf" \
     -f null -progress pipe:1 -nostats -
   ```
3. PASS 2 — transform (reads the same trf, h264 + audio copy):
   ```bash
   ffmpeg -hide_banner -nostdin -y -i "C:/clips/walk.mp4" \
     -vf "vidstabtransform=input=C:/clips/walk.stabilized.trf:smoothing=10:optzoom=1" \
     -c:v libx264 -c:a copy -progress pipe:1 -nostats "C:/clips/walk.stabilized.mp4"
   ```
4. Delete `walk.stabilized.trf` (the engine does this in a `finally`).
5. Inspect: edges should not show black/judder (optzoom hid them); the subject
   should feel locked. If it feels too "floaty"/locked-down, lower `smoothing`
   (e.g. 5); if residual jitter remains, raise `shakiness` (e.g. 8).

In-process the whole thing is one call —
`StabilizeEngine(settings).stabilize(in_path, out_path)` — or, as the
pipeline pre-step, `stabilize_clip(in_path, out_path, settings=..., on_notice=...)`
which returns the *original* path (plus a typed notice) when libvidstab is
absent. The RPC `stabilize.run({videoId|path})` returns
`{path, stabilized: bool[, notice]}`.
