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

### Exact commands
### Tunables (defaults from stabilize.py)
### The crop / zoom vs field-of-view tradeoff
### Deciding IF a clip needs stabilization (motion.py)
### Pitfalls that actually bite
### Worked example
