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
instant and lossless); **filter when you do not** (re-encode is the price of
tolerating heterogeneity). See the explicit contrast comment at
`reframe_multispeaker.py:724-728` and `director_op_engines.py:339-343`.

---

## Path A — concat DEMUXER (stream copy, fast, lossless)

Used after the reframe pipeline splits a clip into per-segment files that all
share **one codec contract**, then re-joins them.

The codec contract every segment is encoded with (`build_segment_argv`,
`reframe_multispeaker.py:678-713`) — this is what makes the stream-copy join valid:

```
ffmpeg -hide_banner -nostdin -y -ss <start> -i in.mp4 -t <dur> \
  -filter_complex <graph> -map [v] -map 0:a? \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart \
  -progress pipe:1 -nostats seg_000.mp4
```

The join itself (`build_concat_argv`, `reframe_multispeaker.py:716-749`):

```
ffmpeg -hide_banner -nostdin -y -f concat -safe 0 -i list.txt \
  -c copy -movflags +faststart -progress pipe:1 -nostats out.mp4
```

The manifest (`_write_concat_list`, `reframe_multispeaker.py:752-765`) — **one
`file '<abspath>'` line per segment, in timeline order**:

```
file '/abs/path/seg_000.mp4'
file '/abs/path/seg_001.mp4'
```

Non-negotiables this function enforces, each guarding a real failure:
- **Absolute paths** — the manifest must be valid regardless of ffmpeg's CWD.
- **Single-quote escaping** `'` → `'\''` — a path with a quote otherwise
  truncates the manifest line and ffmpeg loads the wrong/short file.
- **`-safe 0`** — required or the demuxer rejects absolute paths outright.
- **`-map 0:a?`** per segment + `-c copy` on join → **tolerates a silent
  source**: it copies whatever streams each piece has. The filter path cannot
  do this (see Pitfalls).

---

## Path B — concat FILTER (re-encode, tolerant)

`build_join_argv` (`director_op_engines.py:331-368`) — append `clips` after
`in_path`, all into one timeline. Each input contributes exactly one v + one a:

```
ffmpeg -hide_banner -nostdin -y -i in.mp4 -i b.mp4 -i c.mp4 \
  -filter_complex "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]" \
  -map [v] -map [a] -c:v libx264 -c:a aac \
  -progress pipe:1 -nostats out.mp4
```

The graph is built programmatically:
`streams = "".join(f"[{i}:v][{i}:a]" for i in range(n))` then
`f"{streams}concat=n={n}:v=1:a=1[v][a]"` (`:350-351`). Output duration = sum of
parts — `director_op_engines.py:342` calls that "the strongest non-no-op proof",
i.e. assert it in any verification.

Input guard (`_require_clips`, `:315-328`): `params['clips']` must be a non-empty
list of non-blank path strings, else `DirectorEngineError` (per-op `failed` +
rollback) — a join with nothing to join is never a silent no-op.

---

## Path C — trim+setpts segment-cut join (one input)

`build_segment_cut_argv` (`fillers.py:351-398`) — carve `keeps` out of ONE clip
and concat the survivors. This is the dead-air / filler-removal apply, but it is
a real intra-clip join and shows the **timestamp-reset discipline** that ALL
filter joins need:

```
ffmpeg -hide_banner -nostdin -y -i in.mp4 -filter_complex \
 "[0:v]trim=start=1.000:end=4.500,setpts=PTS-STARTPTS[v0];\
  [0:a]atrim=start=1.000:end=4.500,asetpts=PTS-STARTPTS[a0];\
  [0:v]trim=start=6.200:end=9.000,setpts=PTS-STARTPTS[v1];\
  [0:a]atrim=start=6.200:end=9.000,asetpts=PTS-STARTPTS[a1];\
  [v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]" \
 -map [v] -map [a] -c:v libx264 -c:a aac -progress pipe:1 -nostats out.mp4
```

Notes from source: spans are filtered to `b > a` and an empty keep-set raises
`ValueError` (`:364-366`); `trim`/`atrim` are **decode-side → frame-accurate**;
parts joined with `;`, the graph order is the play order. After a filter join
that changes durations, captions must be re-timed onto the new compressed
timeline (`remap_time`/`remap_cues`, `fillers.py:305-347`) — the join shifts
every downstream cue.

---

## Path D — EDL / CSV timeline (NO render)

`nle_export.py` turns approved `Project.clips` into an **editable** timeline the
editor imports and renders — no ffmpeg, pure `data -> str`. Use this when the
deliverable is a rough cut, not a file.

- `clips_to_events(clips, fps)` (`:151`): each clip becomes one event with a
  **source window** = the clip's ORIGINAL-video span (`sourceStart -> end`,
  `durationSec` backstops a missing `end`) and a **record window laid
  back-to-back** (`record_cursor` accumulates; each event's record-in is the
  prior record-out — that contiguity is what stacks the clips into a rough cut,
  docstring CONTRACT-NOTE `:23-27`). Zero-length clips are kept with a **1-frame
  minimum** (`:171`) so no approved selection silently vanishes.
- `build_edl` (`:204`): CMX3600, header `FCM: NON-DROP FRAME`, one `V  C` cut per
  event, `* FROM CLIP NAME:` + `* COMMENT:` comment lines.
- `build_csv` (`:236`): frozen `CSV_COLUMNS`, `HH:MM:SS:FF` timecodes, **CRLF**
  line terminator (Excel-friendly) — `export` passes `newline=""` for CSV so the
  CRLF is not doubled (`:305`).
- `fps` MUST be one of `FPS_CHOICES = (24,25,30,60)` — `normalize_fps` raises
  otherwise. Frame math is non-drop: `frames_to_timecode` (`:86`).
- Reel names are sanitized to **≤8 chars, A-Z0-9, uppercase** (`sanitize_reel`
  `:107`), falling back to `AX`/`AX2`… — CMX3600 reel field rules.
- Empty `clips` still writes a valid header-only document (`:296`) — opens as an
  empty-but-importable timeline.

Companion exports (not joins, but the same "assemble for delivery" family):
`package_export.package` (one short → upload ZIP with `upload.json`),
`export_presets` (server-side platform-target catalog: aspect, 20-60 s window,
caption style, reframe engine). Neither concatenates video.

---

## Pitfalls that actually bite

1. **concat FILTER requires EVERY input to have BOTH a video and an audio
   stream.** `concat=n=N:v=1:a=1` references `[i:a]` for each input; a silent
   clip makes the graph fail. If any input may be silent, use the **demuxer**
   path (`-c copy` + `0:a?`), which copies whatever streams exist
   (`reframe_multispeaker.py:724-727`). This is the single biggest gotcha when
   joining arbitrary user clips.

2. **concat DEMUXER requires identical codec / timebase / SAR / pix_fmt across
   ALL parts.** Stream-copy does not resample or rescale. Mismatch →
   A/V drift, frozen frames, or a hard demuxer error. That is exactly why the
   reframe pipeline encodes every segment to the SAME contract
   (libx264/medium/crf18/yuv420p/aac/192k) BEFORE the copy-join
   (`:670-672`). Never `-f concat -c copy` across files you did not encode
   yourself — re-encode (Path B) instead.

3. **Trim without resetting PTS corrupts the join.** Trimmed frames keep their
   original presentation timestamps; concat then overlaps/freezes them. Always
   `setpts=PTS-STARTPTS` (video) and `asetpts=PTS-STARTPTS` (audio) after every
   `trim`/`atrim` (`fillers.py:372-373`). Forgetting one channel desyncs A/V.

4. **stderr pipe-buffer DEADLOCK (the "29-min stuck clip 1/5").** ffmpeg writes
   continuously to stderr (banner, stream info, libass/font logs) even with
   `-nostats`. If you `Popen(stderr=PIPE)` and never read it, the ~64 KB pipe
   fills and the encode blocks **forever**. `ffmpeg.run` drains stderr on a
   daemon thread keeping a bounded 40-line tail for error reporting
   (`ffmpeg.py:254-272`). Use `ffmpeg.run`; do not hand-roll a Popen.

5. **concat-list path safety.** Demuxer manifest needs absolute paths,
   single-quote escaping (`'` → `'\''`), and `-safe 0`. Skip any and ffmpeg
   silently loads the wrong file or refuses the list
   (`_write_concat_list` + `build_concat_argv`).

6. **Input-seek vs frame accuracy.** Path A puts `-ss` BEFORE `-i`
   (decode-then-discard input seek): fast, and crop coordinates stay in source
   pixels (`:673-674`). For frame-accurate cuts within a graph use the
   decode-side `trim` filter (Path C). Do not mix expectations: `-ss` before
   `-i` can land on the nearest keyframe depending on build.

7. **fps must be a member of `FPS_CHOICES`** for EDL/CSV — arbitrary fps raises.
   And EDL record timecodes are contiguous by construction; if you post-edit the
   EDL, keep each record-in = previous record-out or the NLE lays gaps.

8. **`durationSec` = sum of parts**, not max. After a filter concat, verify the
   output duration ≈ Σ input durations (Path B) or Σ keep spans (Path C). A
   no-op join (output == one input length) means the graph silently dropped
   inputs.

9. **`-movflags +faststart`** is set on every mp4 output here (demuxer + segment
   encode) so the moov atom is up front for web/streaming playback. Omitting it
   produces a file that must fully download before it seeks.

---

## GPU / HF-model notes

None of these paths use a GPU or any Hugging Face model. The joins are CPU
`libx264`/`aac` encodes (Paths B/C) or pure stream-copy / pure text (Paths A/D).
The reframe pipeline that PRODUCES the segments uses heavy ML, but the
concat/EDL stage is deliberately ML-free and import-light (`fillers.py:367`
lazy-imports ffmpeg to keep the module light). If a join is slow it is the
libx264 re-encode (Path B/C), not a model — prefer the demuxer (Path A) whenever
the codec contract allows it.

---

## Worked example — join 3 arbitrary user clips into one mp4

Inputs of unknown/mixed codecs, one possibly silent → **Path B is wrong** (the
silent clip breaks `:a=1`). Two correct options:

**Option 1 (robust, what the code does for known-silent inputs): normalize then
demuxer-join.** Re-encode each to the contract, then stream-copy:

```python
from media_studio import ffmpeg
from media_studio.features.reframe_multispeaker import build_concat_argv, _write_concat_list

# 1. encode each input to the SAME contract (libx264/crf18/yuv420p/aac/192k)
#    — reuse build_segment_argv-style argv; map 0:a? so a silent input still works.
# 2. write the manifest in timeline order, then copy-join:
_write_concat_list("list.txt", ["seg_000.mp4", "seg_001.mp4", "seg_002.mp4"])
code = ffmpeg.run(build_concat_argv("list.txt", "joined.mp4"), total_sec=total)
assert code == 0
```

**Option 2 (one pass, all inputs guaranteed to have audio): concat filter.**

```python
from media_studio.features.director_op_engines import build_join_argv
argv = build_join_argv("a.mp4", ["b.mp4", "c.mp4"], "joined.mp4")
# -> ffmpeg ... -filter_complex "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]"
#    -map [v] -map [a] -c:v libx264 -c:a aac ...
code = ffmpeg.run(argv, total_sec=dur_a + dur_b + dur_c)
assert code == 0  # and probe output duration ≈ dur_a+dur_b+dur_c
```

**If the deliverable is an editable rough cut, not a file**, skip ffmpeg entirely:

```python
from media_studio.features import nle_export
nle_export.export(project.clips, "rough_cut.edl", fmt="edl", fps=30, title="Rough Cut")
# contiguous record timecodes lay the approved clips back-to-back; the editor renders.
```

Verify (always): `ffprobe` the joined output's duration and confirm it equals
the sum of inputs (filter) or the encoded segments (demuxer) — a single-frame or
single-clip check is not proof of a correct join.
