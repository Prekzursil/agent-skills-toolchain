---
name: silence-trim
description: "Use when removing long silence, dead air, or filler pauses from speech video while preserving natural padding and synchronized captions."
---

# silence-trim — remove dead air with `silencedetect` + keep-span re-cut

Distilled from the REAL media-studio implementation. Cite these when in doubt:

- `sidecar/media_studio/features/silencetrim.py` — detect → invert → re-cut, the
  `silence.trim` RPC, the no-silent-fallback notice.
- `sidecar/media_studio/features/boundary.py` — `build_silencedetect_argv`,
  the `silence_start`/`silence_end` regexes, the dB / min-duration defaults.
- `sidecar/media_studio/features/fillers.py` — `build_segment_cut_argv`
  (the `trim`/`atrim`+`concat` re-cut), `remap_time` / `remap_cues` (cue re-time).
- `sidecar/media_studio/ffmpeg.py` — `build_probe_argv` (ffprobe duration),
  `run` (drained `-progress` runner), binary resolution by absolute path.
- `sidecar/media_studio/features/cues.py` — `word_cues` (the WORD-level cue
  shape `{index,start,end,text}` that `remap_cues` re-times).

This is NOT audio_saliency. `audio_saliency.py` scores *interest* (laughter /
applause / music / loudness) with a PANNs CNN14 model for the short-maker's
unified scorer. silence-trim is amplitude-only timeline surgery: it never loads a
model, never tags events, and only removes/keeps spans of time.

---

## The recipe (4 stages — exactly what the module does)

```
duration  -> detect (silencedetect) -> invert (keep_spans + pad) -> re-cut (trim/atrim+concat)
                                                                  \-> remap_cues (re-time captions)
```

1. **Probe duration** — `ffprobe` for `format=duration`. If it fails or is ≤0,

### Defaults (from `boundary.py` / `silencetrim.py`)
### Exact commands (real argv — no invented flags)
### Stage 1 — probe duration (`ffmpeg.build_probe_argv`)
### Stage 2 — detect silence (`boundary.build_silencedetect_argv`)
### Stage 3 — re-cut keeps (`fillers.build_segment_cut_argv`)
### Pitfalls that actually bite
### GPU / model notes
### Worked example
### Quick reference — the pure functions to lean on
