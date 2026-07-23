---
name: video-watermark-removal
description: "Use when removing a static logo, watermark, or TV bug from a video seamlessly (so it is not noticeable it was ever there). PRIMARY method = ProPainter flow-guided temporal inpaint on a TIGHT logo-only mask (pulls REAL background pixels from neighbouring frames -> sharp, no soft haze), CHUNKED in time so it fits a small GPU, with PER-FRAME presence gating so frames where the logo is occluded stay pristine. big-LAMA per-frame is the fast fallback but its fill is visibly SOFT. Plus the pitfalls that bite: tight logo-shaped mask not a generous box (oversized boxes smear faces), chunk long clips to bound RAM, retry transient WSL2 CUDA failures, and PROVE clean with a logo-template NCC gate across the whole timeline (never claim done on a single-frame check). Includes a companion method for a FIXED-PATH animated overlay via cross-clip-average phase masks; still NOT for arbitrary moving watermarks or full-frame logos."
---
# Video Watermark / Logo Removal (seamless)

Remove a **static, semi-transparent logo/bug** from a video so cleanly it is not noticeable it was ever there. Proven on 41 vertical shorts (406x720) end-to-end. The OpusClip-specific instance (watermark spec, download, API) lives in basic-memory: `main/projects/reframe/opus-clip-watermark-removal-lama-inpaint-recipe-ops-lessons-...`. This skill is the **reusable technique**.

## When to use / when NOT
- USE for: a fixed-position (or slowly-varying) opaque/semi-transparent logo over real content (faces, hair, background), where the area behind it is small and not a critical detail.
- DO NOT use for: moving/animated watermarks (need ProPainter/E2FGVI temporal inpaint), full-frame tiled marks, or marks over fine text you must recover (inpainting invents plausible texture, it cannot recover hidden detail).

## Approach decision (pick fast, don't agonize)
1. `ffmpeg delogo` — REJECT for anything visible. Interpolates from the box border → a blur patch. Obviously edited.
2. **ProPainter, flow-guided temporal inpaint — PRIMARY (best quality).** Even for a STATIC logo, the subject moves slightly, so optical-flow propagation copies the REAL background that was exposed in neighbouring frames into the masked region — actual detail recovery, sharp, no soft haze, no flicker. This is the only thing that produced a truly seamless result on real faces/hair. Run it on a **cropped ROI** around the logo (e.g. ~280×200) so VRAM is tiny (~1.4 GB on a 6 GB card), and **chunk in time** (see v4 below) so RAM is bounded.
3. **big-LAMA per-frame — FAST FALLBACK only.** Streams at constant memory, but it *hallucinates* the whole masked region every frame independently → the fill is visibly SOFTER than the surroundings and can flicker. A discerning viewer notices. Use only when ProPainter is unavailable or quality is not critical. (Lesson learned: shipping LAMA here was rejected by the user as "clear image deterioration".)

> **The v4 win in one line:** ProPainter (temporal, real-pixel) + tight logo-shaped per-frame mask + presence gating + time-chunking + an NCC verification gate. Scripts: `scripts/propaint_pipeline.py` (one clip), `scripts/pp_batch.sh` + `scripts/pp_daemon.sh` (batch), `scripts/pp_verify.py` (the gate). big-LAMA scripts (`inpaint_clip.py` etc.) are kept as the fallback.

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
3. **Long GPU batches get hang-reaped as background tasks.** A `run_in_background` job that emits no stdout for minutes (one long clip) looks hung and gets killed. FIX: run the workload fully **detached inside WSL** (`setsid nohup bash pp_daemon.sh > log 2>&1 < /dev/null &`) via a fast-returning foreground call — it survives the launching bridge being killed because WSL2 keeps VM processes alive. Watch it with a **persistent Monitor** tailing the log for per-item DONE/FAILED + a done-sentinel file. Do NOT put `wsl.exe` calls inside the Monitor's own loop (it errors the monitor). Also: a `setsid` daemon survives a naive `pkill` of the launcher — kill the whole process group / the `pp_batch.sh` loop, not just leaf processes, or it keeps spawning clips.
4. **ProPainter OOMs (SIGKILL) on long clips.** ProPainter loads the whole video + all-frame optical flow into RAM at once, so a 150 s / ~4800-frame clip blows past 8 GB and gets SIGKILL'd — even though a 15 s segment runs fine. FIX: process each clip in **time-chunks** (`CORE≈450` frames) with a few **context frames** on each side for temporal propagation; composite only the core frames. Bounds RAM to ~2.2 GB. (`propaint_pipeline.py` does this.)
5. **Static mask over a hook card / intro smears the card text.** Many SaaS clip tools render a big text "hook card" over the first ~5 s of the top clips; the watermark is HIDDEN behind it there (no logo to remove). A mask applied to those frames inpaints the card text into mush. FIX: **per-frame presence gating** — localize the logo POSITION once (it's fixed), but per frame check NCC of the logo template at that fixed bbox; if it's below threshold (logo absent/occluded) emit an EMPTY mask so the frame is left pristine. Position is fixed; only presence varies — never do a per-frame position *search* (it's noisy and misplaces the mask → residual logo).
6. **Never claim "done" on a single-frame check — use a residual GATE.** Build a clean, logo-SPECIFIC template (temporal-median of the logo over a dark-bg clip; a high-pass template that matches *any* white graphic will false-positive on channel branding like a "G" logo). Then for every output clip, sample across the WHOLE timeline and measure NCC of the template at the source-localized position; it must be LOW on every frame (logo gone). `scripts/pp_verify.py` is this gate (exit 1 on any residual). Do NOT use PSNR/SSIM-vs-original (a good fill legitimately differs).

## Secondary / animated overlay marks — the cross-clip-average phase-mask method
Many SaaS clip tools render TWO marks, not one: the static top bug (above) AND a SECONDARY animated mark — e.g. OpusClip's vertical "Created with (.)" on the LEFT edge (~t3-8.5s: the text holds, then the (.) icon scrolls UP and fades). The static-mask method fails on it (it moves), and a generous column smears any subject in that region. The fix exploits that the mark is a **FIXED-POSITION UI OVERLAY, identical (shape, screen coords, animation phase) across ALL clips** at a given playback time — only the CONTENT behind it differs per clip.

- **Cross-clip averaging builds the mask.** For each window frame index k, average frame k over ALL clips: the overlay (present + time-aligned in every clip) stays sharp and white; content (different per clip) blurs to a dim mean (~60-110). Threshold the averaged frame at each k → the overlay footprint AT PHASE k (text + (.) wherever it is), isolated from content. Per-frame PHASE masks (mask each position only in the ~frames the mark is there) let ProPainter fill a small hole from clean neighbour frames → sharp, full-travel coverage, no smear. (`build_phase_masks.py`, `propaint_left_phase.py`.)
- **Two compositing refinements that matter:** (a) fill the (.) ring — it thresholds to a HOLLOW ring; contour-fill + convex-hull → solid disk, else a faint outline survives; (b) brightness-match the fill to the local boundary ring (per-channel offset, clamped ±22) → kills the dark/bright seam when the mark sits over a smooth dark region (e.g. (.) over a suit), without Poisson instability.
- **Per-clip timing variance is the trap.** The fade is NOT perfectly synced across clips (~±1s). The averaged mask is time-locked to the MAJORITY timing, so a clip whose mark fades LATE keeps a residual the mask misses. FIX for the outlier = a clip-specific mask: canonical phase masks + a SHORT past-union (~0.6s, tracks a scrolling icon's lag WITHOUT dragging the mask into now-changed regions — a long past-union inpaints unchanged content → a visible patch) + a static TOP-BAND for text that fades in place and lingers. **Stop masking a region once the animated element has left it**, else you inpaint unchanged background → a dark patch. (`build_mask_clip35.py`.)
- **The one background nothing local can beat: a white mark over a SATURATED-WHITE ANIMATED background** (bright "plexus"/particle graphic). This is the genuine unsolvable-without-source case. Three approaches tried, all fail (don't re-walk these):
  - *ProPainter (flow inpaint):* the mark is present across the whole window → no clean temporal neighbour to copy; the animated bg defeats flow propagation → faint fade-tail trace.
  - *Larger temporal context (big CTXF):* does NOT help (distant frames don't match the fast-moving bg) and can INTRODUCE a colour tint from mismatched far frames.
  - *Alpha-unmixing* `bg=(obs-a*255)/(1-a)` (the "correct" de-watermark for a semi-transparent overlay): fails here because (a) mark and bg share the saturated-white colour → the equation is degenerate where bg≈255, and (b) the fade lag is NON-UNIFORM (text vs icon fade at different rates) so no single glyph time-shift aligns → any misalignment subtracts white at the wrong place = a visible ghost (a forced lag manufactured a clear ghost in an already-clean region).
  Root cause: when the watermark and an animated background share a colour, you cannot separate them locally — you need the un-watermarked SOURCE (paid tier). **FLAG it** (per "remove fully, flag imperfect ones") — don't grind: the prominent mark still removes cleanly, only the sub-second fade tail resists, and it's imperceptible at normal playback (visible only under 3x CLAHE + zoom).
- **Verify the secondary mark SEPARATELY** from the top bug: an all-clips contact sheet of the mark-box crop at each clip's PEAK neutral-white frame (CLAHE-boosted) + a per-clip neutral-white score for triage. High score ≠ residual — it's usually legit broadcaster branding (lower-third chyron) or bright content; CONFIRM visually that no overlay glyph (the "Created with"/(.) signature) appears. (`all_41_leftmark_qc.py`.)

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
All scripts here are **parametrized and non-breaking**: run them with **no args/env** and every
path/constant resolves to the original job defaults; override any of them via the env knobs listed
in each script's header comment (nothing points at a hardcoded personal directory anymore).

**ProPainter pipeline (PRIMARY) + residual-QC gate:**
- `scripts/propaint_pipeline.py <in.mp4> <out.mp4> [start_sec] [dur_sec]` — one clip, chunked temporal inpaint. Env: `TPL_GRAY`, `PP` (ProPainter checkout, default `~/ProPainter`), `DET_THRESH`, `PRES_THRESH`, `CORE`, `CTXF`.
- `scripts/pp_batch.sh` — resumable batch over `$SRC/*.mp4` → `$OUT`. Env: `BASE`, `SRC`, `OUT`, `PIPELINE`, `VENV`, `LOG`.
- `scripts/pp_daemon.sh` — detached retry daemon wrapping the batch (heals transient CUDA faults). Env: `BASE`, `SRC`, `OUT`, `BATCH`, `DONE`, `MAX`.
- `scripts/pp_verify.py` — the "prove it's clean" NCC + sharpness gate (exit 1 on any residual). Env: `RG`, `QC`, `SRC`, `OUT`, `TPL_GRAY`, `NCC_FAIL`, `SHARP_MIN`.
- `scripts/scan_residual.py` — thorough full-timeline residual scan; builds the clean template from `TPL_SRC` at `BBOX`. Env: `RG`, `QC`, `SRC`, `CLN`, `TPL_SRC`, `BBOX`.
- `scripts/_logo_template_example.png` — a **generic example** grayscale logo template (the OpusClip bug these scripts remove), for illustration only; the scripts do not load it by default — point `TPL_GRAY` at your own clean template.

**big-LAMA fallback:** `scripts/inpaint_clip.py`, `scripts/run_batch.sh`, `scripts/retry_until_complete.sh`, `scripts/daemon_launch.sh` (set `BASE`/`SRC`/`MASK`/`OUT`).

The committed defaults document the real razvan_gandu run (private repo). The secondary animated-mark helpers (`build_phase_masks.py`, `propaint_left_phase.py`, `build_mask_clip35.py`, `all_41_leftmark_qc.py`) are described above but not yet generalized into this skill.
