---
name: video-watermark-removal
description: "Use when removing a static logo, watermark, or TV bug from a video seamlessly (so it is not noticeable it was ever there) - the per-frame big-LAMA streaming-inpaint pipeline (localize the logo, build a TIGHT logo-only mask, fill only that region with a feathered composite onto the untouched frame, re-mux original audio), plus the operational pitfalls that actually bite: tight mask not a generous box (oversized boxes smear faces), retry transient WSL2 CUDA/cuFFT failures instead of redesigning, and run long GPU batches as a detached WSL daemon watched by a persistent Monitor to dodge the background hang-reaper. NOT for dynamic/moving watermarks or full-frame logos."
---

# Video Watermark / Logo Removal (seamless)

Remove a **static, semi-transparent logo/bug** from a video so cleanly it is not noticeable it was ever there. Proven on 41 vertical shorts (406x720) end-to-end. The OpusClip-specific instance (watermark spec, download, API) lives in basic-memory: `main/projects/reframe/opus-clip-watermark-removal-lama-inpaint-recipe-ops-lessons-...`. This skill is the **reusable technique**.

## When to use / when NOT
- USE for: a fixed-position (or slowly-varying) opaque/semi-transparent logo over real content (faces, hair, background), where the area behind it is small and not a critical detail.
- DO NOT use for: moving/animated watermarks (need ProPainter/E2FGVI temporal inpaint), full-frame tiled marks, or marks over fine text you must recover (inpainting invents plausible texture, it cannot recover hidden detail).

## Approach decision (pick fast, don't agonize)
1. `ffmpeg delogo` — REJECT for anything visible. It interpolates from the box border → smears a blur patch over hair/edges. Looks obviously edited.
2. **Per-frame AI inpaint with big-LAMA** — DEFAULT. Streams frame-by-frame at constant memory; fills the masked region with plausible texture. This is what works.
3. ProPainter / E2FGVI (temporal) — only if the mark MOVES or the region has strong motion you must keep coherent. They load many/all frames into RAM/VRAM → OOM on small GPUs (a 6 GB card / 8 GB RAM box cannot do a 150 s clip). Measure flicker first: if frame-to-frame diff in the fill is small (< ~1/255), LAMA's per-frame fill is indistinguishable and far cheaper.

## Pipeline
```
localize logo  ->  TIGHT per-clip mask (white rect/shape on black, same WxH)
  ->  per frame: ffmpeg decode rawvideo RGB
                 LAMA fills masked region on a vertical CONTEXT BAND (mask bbox +- ~140px)
                 FEATHERED composite of ONLY the masked region back onto the untouched frame
  ->  x264 (crf 18) -> re-mux ORIGINAL audio (-c:a copy, -shortest)
```
Everything outside the mask stays bit-for-bit original. Keep source WxH and fps.

### 1. Localize
- If the logo is a **fixed overlay** (most SaaS clip tools render it at one position regardless of content): find it ONCE on a confident clip, reuse that mask for all. This is the common case — verify by eye on 2-3 clips.
- General localizer (`scripts/localize_wm.py` here is OpusClip-tuned but the method generalizes): sample N frames, build a **temporal-median** image (static logo persists, moving foreground averages out), multi-scale `cv2.matchTemplate` with `TM_CCOEFF_NORMED` on the logo's **alpha-brightness pattern** (mean-subtracted = background-DC invariant), restrict the search to the band where the logo lives, vote across frames. Low confidence -> DO NOT silently fall back to a big box (see Pitfall 1).

### 2. Mask discipline (the part that makes or breaks it)
- **TIGHT, logo-only.** Cover the logo + a few px, nothing more.
- **Never let the mask touch a facial feature** (eyebrow, eye, mouth) or on-frame text you must keep (source chyrons, captions). Clamp the mask edges away from them. A logo over a forehead is trivial; the same generous box dropped onto a tighter-framed shot will cover an eyebrow and LAMA will smear it into mush.

### 3. Inpaint one clip
`scripts/inpaint_clip.py <in.mp4> <mask.png> <out.mp4> [crf=18]` (needs `big-lama.pt`, see Env). Alters only the mask region, re-muxes original audio.

### 4. Batch + heal transient GPU failures
`scripts/run_batch.sh` (resumable: skips clips whose output exists) + `scripts/retry_until_complete.sh` (re-runs the batch up to N passes until every clip has an output).

## Pitfalls (all hit in practice)
1. **Generous fallback mask smears faces.** When localization confidence is low, a "safe" oversized box reaches into eyes/eyebrows and the inpaint destroys them. FIX: since the logo position is fixed, swap in a tight standard mask from a confident clip and re-run. Tight-logo beats generous-box every time.
2. **cuFFT_EXEC_FAILED / "CUDA error: unknown error" are TRANSIENT, not OOM.** big-LAMA uses Fast Fourier Convolutions, so it leans on cuFFT; on a shared GPU these fail intermittently (~5-10% of clips) even with VRAM free — WSL2 passthrough instability under rapid CUDA-context churn. Each clip is a fresh process so one failure does not poison the next. FIX = a resumable RETRY loop, not a redesign. Confirm transient: the next clip after a failure succeeds.
3. **Long GPU batches get hang-reaped as background tasks.** A `run_in_background` job that emits no stdout for minutes (one long clip) looks hung and gets killed. FIX: run the workload fully **detached inside WSL** (`setsid nohup bash daemon_launch.sh > log 2>&1 < /dev/null &`) via a fast-returning foreground call — it survives the launching bridge being killed because WSL2 keeps VM processes alive. Watch it with a **persistent Monitor** tailing the log for per-item DONE/FAILED + a done-sentinel file. Do NOT put `wsl.exe` calls inside the Monitor's own loop (it errors the monitor).

## QC (do not skip — "seamless" is the whole point)
- Extract a **3x zoom of the watermark region**, before vs after, at >= 2 timestamps. The logo must be gone AND the fill must look like the surrounding texture.
- Spot-check the **hard cases**: logo straddling a hairline/edge, and any shot with tighter framing or a busy background (where a fallback mask may have fired).
- Build a **montage** of the region across spread-out clips to catch surprises in one glance.
- **Programmatically validate every output** before delivery: it has video AND audio streams and a duration within ~0.7 s of the source (catches truncated/corrupt encodes).

## Env (WSL2 + CUDA, the tested setup)
- WSL2 Ubuntu, Python venv (e.g. `~/wm_env`): `torch` (CUDA build, e.g. 2.6+cu124), `opencv-python-headless`, `numpy`. System `ffmpeg` with libx264.
- Model: `big-lama.pt` TorchScript (~196 MB) at `~/wm_models/big-lama.pt`, from the simple-lama-inpainting v0.1.0 GitHub release. Load the `.pt` directly with `torch.jit.load` — do NOT `pip install iopaint`/`simple-lama-inpainting`, they pin Pillow<10 / numpy<2 which fail to build on Python 3.12.
- Perf reference: ~11 fps end-to-end, ~2.3 GB peak VRAM, ~60-90 min for ~40 clips of ~1 min each.

## Reference scripts
`scripts/inpaint_clip.py`, `scripts/run_batch.sh`, `scripts/retry_until_complete.sh`, `scripts/daemon_launch.sh` in this skill are the generalized, parameterized versions (set `BASE`/`SRC`/`MASK`/`OUT` env vars). The original job's copies live in `~/Downloads/razvan_gandu/`.
