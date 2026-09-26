---
title: 'Reframe V1 visual-verify: 3 real-cause fixes (vidstab/stabilize/RO clitics)
  2026-06-28'
type: note
permalink: main/projects/reframe/reframe-v1-visual-verify-3-real-cause-fixes-vidstab-stabilize-ro-clitics-2026-06-28
tags:
- reframe
- visual-verify
- bugfix
- vidstab
- stabilize
- captions
- romanian
---

# Reframe V1 end-to-end visual verification (2026-06-28)

Drove the REAL sidecar pipeline (`python -m media_studio` JSON-RPC: library.add -> settings.set(cuda/large-v3) -> transcribe.start(ro) -> subtitles.generate -> shortmaker.export) on `videoplayback (4).mp4` (640x360 RO Georgescu interview). 3-clip sample (talking-head 67-88s, wide 1049-1063s, two-shot 2189-2207s) with claudeshorts reframe + karaoke Remotion template + caption_polish, burned, hookTitle=OFF. Output `C:\Users\Prekzursil\Downloads\reframe-romanian-shorts\V1SAMPLE`. Branch fix/vidstab-windows-path merged to local main (90aa3de) in clone `Downloads\reframe-main-clone`.

## Three real-cause fixes (found by extracting frames + READing PNGs)
- [fix] **vidstab Windows path** (stabilize.py + ffmpeg.py): the .trf transforms file was embedded in the ffmpeg filtergraph as a forward-slashed ABSOLUTE path, but the drive colon `C:/...` IS the filter-option separator -> ffmpeg EINVAL (-22), so shortmaker.export CRASHED on every Windows render with stabilize on. No colon-escaping form vidstab accepts survives ffmpeg's 2 unescape passes. FIX = pass the .trf by BARE filename + run ffmpeg with `cwd`=its dir (proven the only working form). `ffmpeg.run` got an opt-in `cwd` kwarg (passed to popen only when set, so test doubles unaffected).
- [fix] **stabilize default-off** (shortmaker.py:956 `get("stabilize", False)`): vidstab was DEFAULT-ON. On static studio / talking-head footage and ANY clip spanning a hard camera cut it computes bogus transforms + optzoom upscales a tiny region -> pixelated/warped faces + empty-studio garbage (visible QUALITY DECREASE). Proven via stab-vs-nostab same-frame comparison: identical moments clean without vidstab. Crop jitter is already killed by reframe smoothing+deadzone, so stabilize is now OPT-IN (shaky handheld only).
- [fix] **RO clitic captions** (shortmaker._cues_for_clip merge + subtitles._split_segment join): faster-whisper emits Romanian clitics as their own hyphen-prefixed word tokens (`vi`+`-l`, `s`+`-a`, `văzut`+`-o`). _cues_for_clip makes ONE cue per word and the karaoke composition renders a space BETWEEN tokens -> burned "vi -l"/"s -a". FIX = fold a `-`-leading token onto the previous cue -> "vi-l". (The burned captions come from `_cues_for_clip`, NOT subtitles.generate — that was the trap; fixed both paths.)

## Key facts / gotchas
- [fact] Karaoke + premium STYLE TEMPLATES = the Remotion engine (render-cli/dist + out/remotion-bundle). Build once: `cd app/render-cli && npm install && npm run bundle`. Set `MEDIA_STUDIO_NODE_EXE` to plain node.exe; Chrome self-resolves (auto-download). captionStyle in {bold,karaoke,clean,bounce,hormozi,neon,tiktok,gradient,impact,mrbeast,pop,serif,fire,subtitle} -> Remotion; else libass. captionPosition only honored by libass (Remotion position is template-default lower-third).
- [fact] GPU faster-whisper needs the CUDA12 runtime DLLs ON PATH: `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*` then prepend `<venv>/Lib/site-packages/nvidia/*/bin` to PATH. ct2 4.8 detects GPU via driver but fails at model-load with "cublas64_12.dll not found" without the wheels. large-v3 (cached) ~10min for 58min audio on RTX 4050.
- [fact] subtitles.generate auto-applies caption_polish via generate_polished (degrade-safe). transcribe.start takes {videoId, language}; device/model via settings.set {transcribeDevice, transcribeModel}.
- [verdict] FINAL: speaker framed (incl wide + two-shot) PASS; captions in-bounds/karaoke/lower-third/RO-diacritics PASS; no title burned PASS; punctuation clean PASS; no jitter (smooth tracking) PASS. Caveat: 360p source has its own broadcaster chyron + inherent softness (not pipeline defects).
- [test] Full sidecar suite 4273 passed +4 new regression tests; 2 pre-existing failures (test_smolvlm2/test_handlers_phase8 model-presence) confirmed unrelated (fail on stashed pristine code).

## Relations
- relates_to [[Reframe real-use feedback: jitter fix + 20 RO shorts + app fixes (2026-06-25)]]
