---
name: audio-extract-mix
description: "Use when extracting, mixing, replacing, ducking, loudness-normalizing, muxing, or analyzing a video or clip audio track with ffmpeg."
---

# audio-extract-mix

Extract / mix / replace / duck / loudness-normalize audio on a clip, the way the
Reframe media_studio sidecar actually does it. Every command below is copied from
real source — no invented flags.

## Source modules (read these for ground truth)

- `sidecar/media_studio/features/audiomix.py` — `audiomix.merge` (duck→mix→loudnorm)
  + `audiomix.normalize` (loudnorm only). Owns `build_mix_filter`,
  `build_mix_argv`, `build_loudnorm_argv`, `PLATFORM_LOUDNESS`,
  `resolve_loudness_target`.
- `sidecar/media_studio/features/tracks_audio.py` — `tracks.audio.{list,mux,replace,strip}`.
  Owns `build_mux_argv`, `build_replace_argv`, `build_strip_audio_argv`,
  `probe_streams`, `original_tracks_from_probe`.
- `sidecar/media_studio/features/audio_saliency.py` — PANNs CNN14 audio tagging +
  pure RMS `loudness_curve`. Owns `compute_audio_signals`, `peak_windows`,
  `sample_windows`, the decode argv in `_default_audio_loader`.
- `sidecar/media_studio/ffmpeg.py` — the shared seam: `ffmpeg_path` /
  `ffprobe_path` (resolve binary by absolute path), `run` (argv-list Popen,
  both pipes drained, `-progress` parsing, cooperative cancel),
  `ffprobe_duration` (drives the progress %).

The whole module follows one law (audiomix.py docstring, CONTRACTS §4/§6/§7):
**argv LISTS only, never `shell=True`**; the filter graph and every path is a
single argv element; the ffmpeg binary is resolved by absolute path; both stdout
and stderr are drained by the shared `run`. Keep that when you hand-run these.

### Recipe 1 — Mix a music bed / VO UNDER speech with sidechain ducking + loudnorm
### Recipe 2 — Loudness-normalize an export (no bed)
### Per-platform LUFS targets (`PLATFORM_LOUDNESS`, audiomix.py:67-80)
### Recipe 3 — Extract / decode audio to raw samples
### Recipe 4 — Mux / replace / strip an audio track (preserve everything else)
### Pitfalls that actually bite
### GPU / HF-model notes (audio_saliency only)
### Worked example: lay a -10 dB music bed under a TikTok clip at -14 LUFS
