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
   pass the clip through UNCHANGED with identity keeps `[(0.0, inf)]` and emit a
   notice (see Pitfall 6). You need the total to invert silences into keeps and
   to keep the trailing tail.
2. **Detect silent spans** — run `silencedetect` over the whole clip, parse the
   `silence_start` / `silence_end` lines from **stderr** into `(start, end)`
   spans. A probe/spawn failure returns `[]` (→ keep the whole clip) and emits a
   notice; it never raises.
3. **Invert to KEEP spans** — `keep_spans(silences, total, pad_sec)` computes the
   talking parts between silences, leaving `pad_sec` of silence on each kept edge
   and coalescing keeps whose gap shrank below `2*pad`.
4. **Re-cut + remap** — if anything was removed and there's >1 keep, run a single
   `filter_complex` of one `trim`/`atrim` pair per keep then `concat`. Feed the
   keep list to `remap_cues` so captions land on the compacted timeline.

Wire surface: `silence.trim({videoId|path, noiseDb?, minSilenceSec?, padSec?})
-> {jobId} -> {path, removedSec}`. Also runnable as an EXPORT pre-step
(`settings['silenceTrim']`) before the filler/reframe/caption stages.

### Defaults (from `boundary.py` / `silencetrim.py`)

| Param | Default | Meaning |
|---|---|---|
| `noiseDb` | `-30.0` dB | anything quieter than this counts as silence (`DEFAULT_SILENCE_NOISE_DB`) |
| `minSilenceSec` | `0.5` s | a gap must last this long to be a silence (`DEFAULT_SILENCE_MIN_SEC`) |
| `padSec` | `0.1` s | silence left on each kept edge so cuts aren't clipped (`DEFAULT_PAD_SEC`) |

---

## Exact commands (real argv — no invented flags)

### Stage 1 — probe duration (`ffmpeg.build_probe_argv`)

```bash
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 INPUT.mp4
```

Prints a bare number of seconds. `ffprobe_duration` returns `0.0` if it can't
parse one — which the trim treats as "can't trim safely, pass through".

### Stage 2 — detect silence (`boundary.build_silencedetect_argv`)

```bash
ffmpeg -hide_banner -nostdin -i INPUT.mp4 \
  -af silencedetect=noise=-30.0dB:d=0.5 \
  -f null -
```

- Output goes to `null` (decode + analyze only, no file written).
- The detector lines are on **stderr** (capture stderr, not stdout):
  ```
  [silencedetect @ ...] silence_start: 12.34
  [silencedetect @ ...] silence_end: 15.80 | silence_duration: 3.46
  ```
- Parsed by `_SILENCE_START_RE` / `_SILENCE_END_RE`
  (`silence_start:\s*([0-9]+(?:\.[0-9]+)?)`, same for `end`).
- Each paired start/end → one span. An **unpaired trailing start** (silence
  running to EOF, no `silence_end`) is **ignored** — the re-cut keeps that tail
  rather than guessing its length.

### Stage 3 — re-cut keeps (`fillers.build_segment_cut_argv`)

For keeps `[(0.0, 12.44), (15.70, 30.00)]` (pad already applied), one
`trim`/`atrim` pair per keep, then `concat`:

```bash
ffmpeg -hide_banner -nostdin -y -i INPUT.mp4 \
  -filter_complex "\
[0:v]trim=start=0.000:end=12.440,setpts=PTS-STARTPTS[v0];\
[0:a]atrim=start=0.000:end=12.440,asetpts=PTS-STARTPTS[a0];\
[0:v]trim=start=15.700:end=30.000,setpts=PTS-STARTPTS[v1];\
[0:a]atrim=start=15.700:end=30.000,asetpts=PTS-STARTPTS[a1];\
[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" -c:v libx264 -c:a aac \
  -progress pipe:1 -nostats OUTPUT.mp4
```

Key invariants baked into the builder:
- `setpts=PTS-STARTPTS` (video) and `asetpts=PTS-STARTPTS` (audio) on EVERY
  segment — without these the concatenated timestamps are non-monotonic and the
  player stutters / A-V desyncs.
- `concat=n=N:v=1:a=1` — N must equal the number of keep pairs.
- Re-encodes (`libx264` + `aac`). This is a decode-side, frame-accurate cut, NOT
  a stream copy — that's why edges are exact (see Pitfall 1).
- `-progress pipe:1 -nostats` so `ffmpeg.run` can stream a 0–100% bar.
- argv is a **list**, never `shell=True`; every path is one element so spaces are
  safe.

---

## Pitfalls that actually bite

**1. Stream-copy (`-c copy`) cuts are NOT frame-accurate — don't.** The module
re-encodes via `trim`/`atrim`. `-c copy` only cuts on keyframes, so every cut
edge snaps to the nearest I-frame (often hundreds of ms off) and you'll clip
words or leave dead air. Accept the re-encode for accurate edges.

**2. `setpts`/`asetpts` reset is mandatory.** Each kept segment's PTS must be
rebased to start at 0 before concat. The builder always emits
`setpts=PTS-STARTPTS` / `asetpts=PTS-STARTPTS`. Omit them and concat produces
jumping timestamps → stutter, freezes, A/V drift. This is the single most common
hand-rolled-concat bug.

**3. Captions drift LATE without `remap_cues` — and get ERASED if you remap with
the wrong keep-list.** Every removed interior silence shifts all later cues
earlier on the compacted timeline; feed the SAME keeps to `remap_cues` so cue
times map through `remap_time`. Two real traps documented in the code:
  - On a **pass-through** (nothing removed) the module returns keeps
    `[(0.0, total)]` (a real full-length span), NOT `[]`. `remap_time` over an
    empty keep-list returns `0.0` for *every* time → every caption collapses to
    length 0 and is dropped. The full-length / identity keep maps `t → t`.
  - `trim_clip` returns `[(0.0, float('inf'))]` as the identity keep when it
    can't probe/trim, for the same reason.

**4. `noiseDb` is an amplitude gate, not a voice detector.** `silencedetect`
measures dB below `noise`, period. With background hum, music, HVAC, or room
tone above `-30 dB`, NOTHING reads as silence and nothing gets cut. Conversely a
very quiet talker below the floor gets gutted mid-sentence. There is no VAD here.
Tune `noiseDb` to the actual room: noisy room → raise toward `-20`/`-25 dB`;
clean studio with soft speech → lower toward `-35`/`-40 dB`. If you truly need
speech-vs-noise classification, this module is the wrong tool.

**5. `minSilenceSec` too small = choppy machine-gun jump-cuts.** At `d=0.5`
natural breath pauses survive; drop to `0.2`–`0.3` and you cut between words and
the edit sounds robotic. Raise `minSilenceSec` (and keep `padSec ≈ 0.1`) before
you blame the codec. Padding also coalesces keeps whose removed gap is shorter
than `2*pad`, which further suppresses micro-cuts — that's by design.

**6. Failures are SURFACED, not silent (no-silent-fallback / WU-3).** A missing
ffmpeg, a `silencedetect` spawn failure, or an unprobeable duration each emit a
typed `silencetrim.unavailable` notice (`{type, message, reason}`) via the
`on_notice` sink (routed to `job.progress`), then pass the clip through
unchanged. A legitimate "no dead air to remove" pass-through emits NO notice and
returns `removedSec == 0.0` with the original path. Don't re-add a silent
`{removedSec:0}` no-op — report the skip.

**7. No needless re-encode.** When `removed <= 1e-3` OR `len(keeps) <= 1` the
module returns the ORIGINAL `in_path` untouched (no ffmpeg pass). Mirror this:
don't burn an encode to produce a byte-identical clip.

**8. Trailing silence is intentionally kept.** An unpaired `silence_start` with
no matching `silence_end` (silence to EOF) is ignored by the parser, so the clip
keeps its tail. If you want to also trim a trailing silence, you'd need the
duration to bound it — the module deliberately does not guess.

**9. stderr vs stdout.** `silencedetect` writes to **stderr**; the re-cut
`-progress pipe:1` writes to **stdout**. Capture the right stream for each
(`capture_output=True` then read `.stderr` for detection).

---

## GPU / model notes

- **No model, no GPU, no Hugging Face asset.** silence-trim is pure ffmpeg +
  numpy-free timeline math. It runs anywhere ffmpeg runs. (The PANNs CNN14
  checkpoint and Zenodo download in `audio_saliency.py` belong to the *other*
  module — don't conflate them.)
- ffmpeg/ffprobe are resolved by **absolute path** through
  `ffmpeg.ffmpeg_path` / `ffprobe_path` (bundled or PATH binary), never invoked
  as a bare name through a shell.
- The re-cut is CPU `libx264`/`aac`. If you want NVENC, that's a swap of the
  `-c:v` codec in a fork of `build_segment_cut_argv` — but be aware NVENC edges
  are still frame-accurate here because the cut happens in the decode-side
  `trim` filter, not the encoder.

---

## Worked example

Goal: a 30 s talking-head clip with one long pause from 12.3 s to 15.8 s.

1. Probe → `30.0`.
2. Detect (defaults `-30 dB`, `d=0.5`):
   ```
   silence_start: 12.34
   silence_end:   15.80 | silence_duration: 3.46
   ```
   → spans `[(12.34, 15.80)]`.
3. Invert with `pad_sec=0.1`:
   keep ends at `min(30, 12.34+0.1)=12.44`; next cursor `15.80-0.1=15.70`.
   → keeps `[(0.0, 12.44), (15.70, 30.0)]`.
   `removed_seconds = 30.0 - (12.44 + 14.30) = 3.26 s`.
4. `removed=3.26 > 1e-3` and `len(keeps)=2 > 1` → re-cut with the Stage-3 argv
   above → `OUTPUT.mp4`, `removedSec=3.26`.
5. A caption cue at `start=18.0` (original) → `remap_time(18.0, keeps)`:
   first keep contributes `12.44`; `18.0` is inside the second keep
   `(15.70, 30.0)` → `12.44 + (18.0 - 15.70) = 14.74 s` on the compacted
   timeline. Without the remap it would still say `18.0` and float ~3.26 s late.

Pass-through example: same clip, but the only pause is 0.3 s (< `minSilenceSec`).
Detection yields `[]` → keeps `[(0.0, 30.0)]` → `removed≈0` → return ORIGINAL
path, `removedSec=0.0`, no notice, no re-encode.

---

## Quick reference — the pure functions to lean on

- `parse_silence_spans(stderr) -> [(start,end), ...]` — paired lines only, sorted.
- `keep_spans(silences, total, pad_sec=0.1) -> [(start,end), ...]` — invert + pad
  + coalesce; empty silences → `[(0, total)]`.
- `removed_seconds(keeps, total) -> float` — `total - sum(kept)`, clamped ≥0.
- `trim_clip(in, out, ...) -> (path, removedSec, keeps)` — the whole pipeline;
  returns the keep-list for `remap_cues`.
- `remap_time(t, keeps)` / `remap_cues(cues, keeps)` — re-time captions onto the
  cut timeline (drops zero-length cues, renumbers 1..N).
