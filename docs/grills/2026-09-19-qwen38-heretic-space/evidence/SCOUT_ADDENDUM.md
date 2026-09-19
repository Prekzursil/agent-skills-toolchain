# Scout addendum — state as of 2026-09-19 00:10Z (read AFTER SCOUT_BRIEF.md)

The Space changed while it was being reviewed. **The current code is in `SCRATCH/space-latest/` (HEAD `f88b120`)**;
`SCRATCH/space-src/` is the older snapshot (`17dce0c`) that a separate review workflow is still analysing — do not touch it.

## What happened
A second AI agent (not part of this review) is pushing to the production Space every few minutes. Since `17dce0c`:
- `3ffed41` 23:51Z — personas replaced by neutral ones ("Analyst (default)", "Research Analyst"); originals "archived locally".
- `f90bb44` 23:58Z — vision+video input, **lazy-load boot** (bind port first, load models in a background thread) to dodge the
  "supervisor's autorestart loop", NF4 export pipeline, model path prefers a future `/models/qwen38-heretic-nf4` mount.
- `f88b120` 00:02Z — reverts to synchronous main-thread loads; NF4 export moved inside the first GPU lease.

## Verified facts (A-series)
- A1 **Production is down.** `/healthz` has not answered since ~23:45Z. Running sha is `f90bb44`; its background-thread load fails
  with `Low-level CUDA init (torch._C._cuda_init) reached. This means ZeroGPU's PyTorch CUDA emulation mode did not intercept a CUDA
  operation` — on ZeroGPU the model must be loaded on the import path of the main thread.
- A2 **HEAD `f88b120` cannot start.** pyflakes on `app.py`: `undefined name '_load_draft'` at module level (line 189, executed at
  import), `undefined name '_media_from_message'` (line 666 — called on EVERY chat turn), `undefined name '_resolve_image_urls'`
  (line 553 — API image path), and `images` / `videos` used inside `_encode_messages` (lines 356-371) without being parameters.
  Call sites and commit message landed ("vision+video complete"); the function definitions never did.
- A3 Unit tests at HEAD: 73 run, **1 fails** (`test_original_personas_archived_verbatim` needs a persona archive that exists only on
  the other agent's local disk). The commit was pushed anyway: there is no lint/test gate before production.
- A4 The auto-restart is real: before these commits the app was restarted ~300 s after the previous restart whenever boot had not
  finished (gaps 301 s, 303 s, 303 s); boot needs 4m30s-5m05s because 54 GB of bf16 weights are quantized to NF4 on every start.
  Dev Mode is ON; the docs say Dev Mode itself does not auto-restart the app, so the trigger is either an undocumented supervisor
  health check or external automation.
- A5 NF4 export design at HEAD: gated by secret `NF4_EXPORT=1`; on the first GPU call it runs `model.save_pretrained()` (~16 GB) inside
  the ZeroGPU lease, then uploads from a daemon thread to the private repo `Prekzursil/Qwen3.8-27B-heretic-ara-NF4` (already created)
  using secret `NF4_UPLOAD_TOKEN`. Open doubts: `_estimate` does not budget the save time; the "saved" flag and the upload thread live
  in the per-call GPU worker process, which may not outlive the lease; a write-scoped token now sits in the app's environment.
- A6 Still unchanged at HEAD: `TOK_PER_SEC = 22.0`, `DURATION_CAP = 600`, max-tokens slider up to 262144, "Deep think" preset on `xlarge`.
- A7 Space secrets now: `HF_TOKEN`, `NF4_EXPORT`, `NF4_UPLOAD_TOKEN`. Variables unchanged. No persistent storage. Volumes unchanged
  (no NF4 mount yet). Last commit known to boot: `17dce0c` / `1545500`.
- A8 Lease economics (from SCOUT_BRIEF F2 + arithmetic): if decode really is ~9 tok/s, a whole PRO day of ZeroGPU quota (40 min) buys
  roughly 22k output tokens on `large`, half that on `xlarge`; every preset is cut off mid-answer by the 22 tok/s estimate.
