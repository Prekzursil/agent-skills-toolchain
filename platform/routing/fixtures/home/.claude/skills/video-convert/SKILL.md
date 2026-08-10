---
name: video-convert
description: "Use when converting a video/audio file's FORMAT, CODEC, or CONTAINER in media-studio (mp4/mkv/mov/webm/gif, h264/h265/vp9/av1, or audio-only extraction to mp3/m4a/wav/flac/opus) — single file or batch, or normalizing a non-Chromium-playable source for playback (remux vs h264-720p proxy). Covers the real ffmpeg argv builder, codec/CRF/bitrate/pix_fmt choices, faststart, container<->codec legality, and the progress/seek/timebase pitfalls that actually bite. DO NOT use this skill for: cutting/trimming/splitting clips (use reframe-video-cutting), reframing 16:9->9:16 (use reframe), burning subtitles/captions, watermark/logo removal (use video-watermark-removal), or pure thumbnail/frame extraction. Also NOT a general 'run any ffmpeg command' helper — it documents media-studio's specific, frozen convert.* / media.* contracts."
---

# Video Convert (format / codec / container) — media-studio

Convert format/codec/container, extract audio, batch-convert, and produce a Chromium-playable derivative (remux or h264-720p proxy). This skill documents the **real** media-studio implementation — every command below is what the code actually emits. No invented flags.

## Source modules (read these for ground truth)
- `C:/Users/agentuser/Documents/GitHub/Reframe/sidecar/media_studio/ffmpeg.py` — **the argv builder** (`build_convert_argv`), `build_probe_argv`, `ffprobe_duration`, and the progress-streaming `run()`. This is where the convert command is actually assembled.
- `C:/Users/agentuser/Documents/GitHub/Reframe/sidecar/media_studio/features/convert.py` — `convert.start` / `convert.batch` feature layer: pure output-path derivation (`output_path`), audio-ext map, `convert_one` / `convert_batch`, job handlers.
- `C:/Users/agentuser/Documents/GitHub/Reframe/sidecar/media_studio/features/media_compat.py` — `media.playable` / `media.proxy.start`: codec-driven playability `classify`, `build_remux_argv`, `build_proxy_argv`, proxy cache.
- `C:/Users/agentuser/Documents/GitHub/Reframe/sidecar/media_studio/features/export_presets.py` — `exportPresets.*` catalog (platform export targets; aspect + 20-60s window, NOT codec).

## When to use which path (pick fast)
1. **User wants a different format/codec/container, or audio extraction** -> `convert.start` / `convert.batch` (this is "convert"). Builder = `ffmpeg.build_convert_argv` (convert.py:182).

### The convert option contract (frozen — CONTRACTS.md §2)
### The real convert command
### Output path derivation (convert.py:94-125 `output_path`)
### Worked examples
### Pitfalls (the ones that actually bite)
### GPU / HF-model notes
### Confidence
