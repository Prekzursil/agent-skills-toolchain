---
title: 'Reframe real-use feedback: jitter fix + 20 RO shorts + app fixes (2026-06-25)'
type: note
permalink: main/projects/reframe/reframe-real-use-feedback-jitter-fix-20-ro-shorts-app-fixes-2026-06-25
tags:
- reframe
- jitter
- deliverable
- shorts
- bugfix
- user-feedback
---

# Reframe real-use feedback after installing v0.1.0 (2026-06-25)

User installed Reframe to D:\Program Files\Reframe - Media Studio, tried to make shorts, hit issues. Directives:

## ROOT CAUSES FOUND
- **find-shorts failed** = first-run bootstrap NEVER provisioned: D:\Program Files\Reframe - Media Studio\data is EMPTY (no envs/models, no .media-studio-env.json, no gguf). No LLM/whisper -> AI moment-finding fails. (data dir tested WRITABLE, so bootstrap just never ran/completed — surface it + provision.)
- **jobs can't cancel** = real cancel bug.
- **model-choice confusing** = real UX gap (user wants plain-language Local/Cloud/Multimodal; REMOVE the no-model/heuristic option — "2 shouldn't be an option, that's bad").
- **JITTER (user-emphasized)**: original videoplayback(4) is NOT jittery, but the 9:16 reframe introduces camera motion. ROOT CAUSE (in reframe_claudeshorts.py): samples face-center per time-window + ffmpeg crop=W:H:x(t); jitter from noisy per-window face detection + SMOOTH_ALPHA=0.35 (too loose) + likely STEPPED (non-interpolated) crop-x between keyframes (teleport at window boundaries). FIX: stronger smoothing + DEADZONE (no move unless subject moves >6-8% width -> static crop for a sitting speaker) + smooth interpolation + static-bias + vidstab DEFAULT-ON. Stabilization should ALWAYS be on (user: nobody wants jitter).

## "FIRST INSTALL" CLARIFICATION: %APPDATA%\media-studio (10MB) is NOT a 2nd install — it's Electron userData (caches/Local-Storage), auto-created. Only ONE real install (D:). Not deleting (no settings.json/keys there; harmless). Can clear as cache-reset if user wants.

## DELIVERABLE: 20 Romanian shorts from videoplayback(4).mp4 (640x360!, 25fps, ~58min, lang und->ro). User chose: local Qwen + AI-select (option 1). Karaoke subtitles, NO quality decrease, NO jitter. HONEST: 360p source = quality ceiling; preserve (crop 9:16 -> lanczos 1080x1920, x264 crf18), don't upscale-blur. Deliverable uses ASS \\k karaoke (node-free, robust) + the FIXED reframe. Output -> C:\Users\Prekzursil\Downloads\reframe-romanian-shorts\ (plan.json + transcript.json + short_*.mp4). Selection via LLM editorial reasoning over the RO transcript (= the AI selection); qwen provisioned separately in the app fix so the user's local-model path works.

## PROGRAM: wf_d794f74f (branch feat/reframe-quality): Phase Jitter (root-cause+fix+sample) -> Deliver (prep transcribe+select ∥ 4 render workers) ∥ AppFix (bootstrap-fallback-to-userData + cancel-fix + model-UX-simplify + stabilize-default-on) -> Verify+merge. TDD 100% both gates.

## ALSO RUNNING: momentstudio Angular->100% (wf_444b136f / w0hoxu5m1) for 13/13 fleet. Reframe v0.1.0 already released; this program improves it -> will need a v0.1.1 re-release + installer rebuild after merge.