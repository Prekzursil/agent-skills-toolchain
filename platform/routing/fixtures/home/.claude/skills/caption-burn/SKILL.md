---
name: caption-burn
description: "Use when BURNING captions / subtitles / karaoke INTO a video as hardcoded pixels (hardsub) via libass through ffmpeg, OR soft-muxing them as a selectable, removable subtitle track. Covers ASS document generation sized to the export canvas, libass styling (font / size / colour / outline / box), the OpusClip word-by-word KARAOKE preset (per-word alternating yellow/green + scale-pop), hook-title / hook-card overlays, the CaptionOverride tuning patch, safe-area placement for 9:16, and the Netflix CPS/CPL/min-gap polish pass. Burn = lossy re-encode, permanent, styling survives anywhere; soft-mux = lossless stream-copy, toggleable, but loses ASS styling in MP4 (mov_text). NOT for moving/animated watermark removal (use video-watermark-removal), NOT for transcription/cue generation (this consumes an existing cue list), NOT for repositioning an already-burned track (burned pixels are permanent — re-burn from source). Source of truth: media_studio/features/caption.py, caption_karaoke.py, caption_override.py, caption_polish.py, tracks.py."
---

# Caption Burn (hardsub) & Soft-mux — libass / ffmpeg

Render an existing **cue list** onto a video, either **burned in** (hardcoded pixels, permanent, re-encode) or **soft-muxed** (a selectable, removable subtitle stream, stream-copy). This is the libass/ASS path; the styled/karaoke output path is libass burn (mov_text cannot carry the styling).

Source modules read (cite these, do not invent commands):
- `media_studio/features/caption.py` — `CaptionEngine`, `build_ass`, escaping, `build_burn_argv`/`build_softmux_argv`, hook title/card, karaoke routing.
- `media_studio/features/caption_karaoke.py` — OpusClip word-by-word karaoke ASS preset.
- `media_studio/features/caption_override.py` — `CaptionOverride` -> `ResolvedCaptionStyle`, the ASS colour byte-swap.
- `media_studio/features/caption_polish.py` — Netflix CPS/CPL/min-gap + punct/casing/emphasis/profanity polish.
- `media_studio/features/tracks.py` — `tracks.burn` / `soft_mux` / `strip` RPC + the simpler V1 ASS builder.
- `media_studio/ffmpeg.py` — the shared `run()` (argv-only, stderr-drain) and `ffmpeg_path()`.

## When to use / when NOT
- USE for: painting transcript cues into a clip (standard captions, styled captions, OpusClip karaoke), adding a hook-title/hook-card headline, or muxing a removable subtitle track.
- DO NOT use for: removing a logo/watermark (`video-watermark-removal`); generating the cues themselves (this skill consumes `{index,start,end,text}` cues already produced upstream); moving a caption that is already burned in (pixels are baked — change the position/style and re-burn from the original source); soft-muxing styled ASS into an MP4 and expecting the styling to survive (MP4 only carries `mov_text`, which drops ASS overrides — burn instead).

### Burn vs soft-mux — the tradeoff (decide first)
### Recipe (the real flow, from `CaptionEngine.render`)
### Exact ffmpeg argv — BURN (`caption.build_burn_argv`)
### Exact ffmpeg argv — SOFT-MUX (`caption.build_softmux_argv`)
### STRIP a soft sub (`tracks.build_strip_argv`)
### ASS document structure (`build_ass`)
### libass styling fields you actually touch (`CaptionOverride` -> `ResolvedCaptionStyle`)
### ASS colour format — the silent-wrong-colour trap (`hex_to_ass_color`)
### Karaoke preset (`caption_karaoke.build_karaoke_ass`, style id `opusclip-karaoke`)
### Caption polish (`caption_polish.polish_cues`) — run BEFORE building the ASS
### Pitfalls that actually bite
### GPU / model notes
