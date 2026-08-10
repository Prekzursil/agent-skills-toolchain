---
name: video-join-concat
description: "Use when joining/concatenating multiple video clips into ONE output, or assembling approved clips into an editable NLE timeline (CMX3600 EDL / CSV for Premiere/Resolve). Covers the two real media_studio ffmpeg paths — concat DEMUXER (stream-copy, instant, lossless, needs identical."
---

# video-join-concat

Joining clips in media_studio is **two unrelated jobs** that people conflate:

1. **Render a single joined video** (one `.mp4` out) — ffmpeg, two algorithms.
2. **Emit an editable timeline** (EDL/CSV) — pure text, no ffmpeg, the NLE renders.

Pick the right one first. Re-encoding to produce an `.mp4` when the user wanted
an editable rough cut is the most common waste; emitting an EDL when they wanted
a finished file is the opposite mistake.

All ffmpeg here goes through one runner, `media_studio.ffmpeg.run` (argv list
only, never `shell=True`), and every argv ends with `-progress pipe:1 -nostats`
so progress is parsable. Source of truth:
`sidecar/media_studio/ffmpeg.py`.

---

## Decision: which join

| Want | Use | Source |
|---|---|---|
| Stitch pieces you ENCODED YOURSELF with one codec contract | **concat demuxer** `-f concat -c copy` | `features/reframe_multispeaker.py:716` `build_concat_argv` |
| Join ARBITRARY user clips (unknown/mismatched codecs, res, fps) | **concat filter** `filter_complex …concat=n=N:v=1:a=1` (re-encode) | `features/director_op_engines.py:331` `build_join_argv` |
| Cut spans OUT of ONE clip and re-join the kept parts | **trim+setpts concat filter** | `features/fillers.py:351` `build_segment_cut_argv` |
| Hand an editor a back-to-back rough cut (no render) | **CMX3600 EDL / CSV** | `features/nle_export.py` `build_edl` / `build_csv` |

Rule of thumb baked into the code: **demuxer when you control the inputs**
(every segment was just encoded to libx264/aac/yuv420p, so a stream-copy join is

### Path A — concat DEMUXER (stream copy, fast, lossless)
### Path B — concat FILTER (re-encode, tolerant)
### Path C — trim+setpts segment-cut join (one input)
### Path D — EDL / CSV timeline (NO render)
### Pitfalls that actually bite
### GPU / HF-model notes
### Worked example — join 3 arbitrary user clips into one mp4
### 1. encode each input to the SAME contract (libx264/crf18/yuv420p/aac/192k)
### — reuse build_segment_argv-style argv; map 0:a? so a silent input still works.
### 2. write the manifest in timeline order, then copy-join:
### -> ffmpeg ... -filter_complex "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]"
### -map [v] -map [a] -c:v libx264 -c:a aac ...
