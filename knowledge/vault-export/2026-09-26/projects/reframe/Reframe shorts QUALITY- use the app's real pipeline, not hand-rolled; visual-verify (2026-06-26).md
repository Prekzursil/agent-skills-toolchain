---
title: 'Reframe shorts QUALITY: use the app''s real pipeline, not hand-rolled; visual-verify
  (2026-06-26)'
type: note
permalink: main/projects/reframe/reframe-shorts-quality-use-the-apps-real-pipeline-not-hand-rolled-visual-verify-2026-06-26
tags:
- reframe
- quality
- lesson
- caption
- reframe-tracking
- visual-verify
---

# Reframe shorts quality — the real diagnosis + lesson (2026-06-26)

User showed bad shorts (image): crop NOT on the speaker (he's at the frame edge, mostly empty studio, esp. profile shots), subtitles OUT OF BOUNDS (text cut off both edges), bad punctuation (leading ",pentru"), clashing with the source chyron. User frustrated: "i need the APP working properly... didn't you do the research? how did you lose the good knowledge."

## ROOT CAUSE = MY MISTAKE, not the app
The APP ALREADY HAS the good pipeline BUILT + WIRED:
- caption_polish.py (CPL/CPS gate + punctuation/casing) -> threads through features/subtitles.py polish_cues (WIRED).
- ctc_align.py karaoke word-timing (WIRED into transcribe tail, handlers.py:1992).
- parakeet_asr.py, quality_gate.py (DOVER), audio_saliency, emphasis, boundary, fillers — all built (the WU0-WU9 "Advanced moment-finding upgrade" design got implemented).
- shortmaker uses verthor reframe (proper subject-TRACKING) as the engine.
MY DELIVERABLE BYPASSED ALL OF IT with hand-rolled render_worker.py (crude faster-whisper + basic ASS + my static-bias claudeshorts). That's why MY output was bad. LESSON: deliver via the APP's real pipeline (sidecar handlers: shortmaker/subtitles/caption_polish/ctc_align), NEVER hand-rolled scripts.

## SECOND LESSON: VISUALLY VERIFY output (extract frames + Read the PNG) BEFORE claiming done. I declared 20 shorts done without looking; user had to show me. Now: render sample -> ffmpeg extract frames -> Read tool on images -> judge -> iterate.

## REAL APP GAPS (being fixed, branch feat/reframe-quality, wf_bcc86446):
1. verthor (good tracker) needs WSL -> no-WSL machines fall back to claudeshorts, which is jittery (main) OR drift-to-center (my static-bias overcorrection). FIX: make claudeshorts a proper NATIVE smooth speaker-tracker (MediaPipe face + person/pose/motion fallback for profile, heavy EMA alpha~0.12-0.18, interpolated, follows the SUBJECT not frame-center) + make it the DEFAULT (no WSL required; verthor = explicit opt-in). My earlier "jitter fix" (static-bias) was WRONG — overcorrected to static/center.
2. App not provisioned (D:\Program Files install, data empty) -> find-shorts fails. FIX: bootstrap fallback to userData + provision + surface progress/errors.
3. + cancel fix, model-UX simplify (remove heuristic, plain Local/Cloud/Multimodal), progress+ETA (no mystery spinner), all native (no WSL).

## VERIFY GATE: render 3-clip sample (incl. a profile moment) via the REAL pipeline -> extract frames -> Read them -> confirm speaker-tracked + subs-in-bounds + clean-punctuation + no-jitter -> iterate until genuinely good, THEN merge + re-release. DON'T claim done without the visual pass.

## STILL: fleet true-green (wf_8daa6301 / wjrgfy5db) running separately. The full SOTA stack (ViNet/SigLIP/PANNs/SmolVLM) is the LATER heavy phase — not needed for this fix (talking-head: MediaPipe face-track + caption_polish CPL is enough).