---
name: audio-extract-mix
description: 'Use when you need to EXTRACT, MIX, REPLACE, DUCK, or LOUDNESS-NORMALIZE
  audio on a video/clip with ffmpeg — e.g. pull a wav out of a clip, lay a music bed
  or VO UNDER a speaker so it auto-dips when they talk (sidechain ducking), normalize
  an export to a per-platform LUFS target (-14 for TikTok/Reels/Shorts/YouTube, -23
  EBU R128 broadcast, -24 ATSC), mux/replace/strip an audio track while preserving
  all other streams, or turn the soundtrack into laughter/applause/ music/loudness
  saliency signals. The exact filter graphs, argv lists, codec/map choices, and the
  pitfalls that actually bite (amix auto-attenuation, -shortest duration, stream-index
  = list-order coupling, mono/32k decode for PANNs, loudnorm single-pass drift) come
  from the real media_studio source cited below. Do NOT use for: per-word transcription/alignment
  (use ASR/CTC modules), TTS dub GENERATION (this only muxes a finished dub), pitch/tempo
  time-stretch, or pure visual edits. Do NOT use as a generic "run ffmpeg" reference
  — it is scoped to these audio ops with the project''s frozen wire surface.'
permalink: dqverify-repo-20261013/skills/audio-extract-mix/skill
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

---

## Recipe 1 — Mix a music bed / VO UNDER speech with sidechain ducking + loudnorm

This is `audiomix.merge`. The entire operation is ONE `-filter_complex` graph
with two inputs: `0` = the clip, `1` = the bg bed.

The graph (`build_mix_filter`, audiomix.py:146-152), with defaults
`bg_gain_db=-10.0`, `duck_threshold=0.03`, `duck_ratio=8.0`,
`I=-14:TP=-1.5:LRA=11`:

```
[1:a]volume=-10.0dB[bg];
[0:a]asplit=2[fg_key][fg_mix];
[bg][fg_key]sidechaincompress=threshold=0.03:ratio=8.0[ducked];
[fg_mix][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mixed];
[mixed]loudnorm=I=-14.0:TP=-1.5:LRA=11.0[out]
```

What each stage does:
1. `volume=<bg_gain_db>dB` pre-attenuates the bed (negative dB = quieter).
2. `asplit=2` forks the foreground: one copy is the **sidechain key**, one is mixed.
3. `sidechaincompress` ducks the bed keyed off the speaker — bed dips when they
   talk, swells back in gaps. `threshold` (0..1 linear) = how loud the speaker
   must get to trigger ducking; `ratio` = gain-reduction strength.
4. `amix` SUMS foreground + ducked bed. `normalize=0` is **load-bearing**:
   without it amix divides each input by N, halving the foreground. `dropout_transition=0`
   stops a gain ramp when one input ends. `duration=first` ties length to the clip.
5. `loudnorm` does the final EBU R128 leveling to the platform LUFS target.

Full argv (`build_mix_argv`, audiomix.py:183-207):

```bash
ffmpeg -hide_banner -nostdin -y \
  -i clip.mp4 \
  -i bed.mp3 \
  -filter_complex "[1:a]volume=-10.0dB[bg];[0:a]asplit=2[fg_key][fg_mix];[bg][fg_key]sidechaincompress=threshold=0.03:ratio=8.0[ducked];[fg_mix][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mixed];[mixed]loudnorm=I=-14.0:TP=-1.5:LRA=11.0[out]" \
  -map 0:v -map "[out]" \
  -c:v copy -c:a aac \
  -shortest \
  -progress pipe:1 -nostats \
  out.mp4
```

Key choices: **video is stream-copied** (`-map 0:v -c:v copy`) — only audio is
rebuilt and re-encoded to AAC. `-shortest` + `duration=first` trims a longer bed
to the clip. `ffmpeg` here means the absolute path from `ffmpeg.ffmpeg_path(settings)`.

Wire surface: `audiomix.merge({videoId|path, bgPath, bgGainDb?, duckThreshold?,
duckRatio?, loudnessTarget?, loudnessTp?, loudnessLra?, platform?}) -> {jobId} -> {path}`.

---

## Recipe 2 — Loudness-normalize an export (no bed)

This is `audiomix.normalize` / `build_loudnorm_argv` (audiomix.py:225-247). Uses
`-af` (single audio stream), not `-filter_complex`:

```bash
ffmpeg -hide_banner -nostdin -y \
  -i in.mp4 \
  -map 0:v? -map 0:a \
  -c:v copy -c:a aac \
  -af "loudnorm=I=-14.0:TP=-1.5:LRA=11.0" \
  -progress pipe:1 -nostats \
  out.mp4
```

Note `-map 0:v?` (the `?` makes video optional — works on audio-only inputs too).
Wire: `audiomix.normalize({videoId|path, loudnessTarget?, loudnessTp?,
loudnessLra?, platform?}) -> {jobId} -> {path}`.

### Per-platform LUFS targets (`PLATFORM_LOUDNESS`, audiomix.py:67-80)

Pass `platform` instead of hard-coding the number; an explicit `loudnessTarget`
still overrides it. `resolve_loudness_target` is **fail-loud** — an unknown
platform raises `INVALID_PARAMS`, never a silent fallback (so a typo can't ship
audio at the wrong loudness).

| platform | LUFS (I) |
|---|---|
| tiktok / reels / shorts / instagram / facebook / youtube / x / twitter / spotify | **-14.0** |
| broadcast / ebu | **-23.0** (EBU R128) |
| atsc | **-24.0** (ATSC A/85) |

`TP` defaults to -1.5 dBTP, `LRA` to 11 LU regardless of platform.

---

## Recipe 3 — Extract / decode audio to raw samples

There is no `extract.wav` wire method; extraction lives inside
`audio_saliency._default_audio_loader` (audio_saliency.py:343-360), which decodes
to **mono float32 @ 32 kHz** (the rate PANNs CNN14 was trained on, `TARGET_SR`):

```bash
ffmpeg -hide_banner -nostdin \
  -i in.mp4 \
  -ac 1 -ar 32000 -f f32le -
```

stdout is read straight into numpy: `np.frombuffer(raw, dtype=np.float32)`. To
adapt for a real WAV file, swap `-f f32le -` for an output path (e.g. `-vn
out.wav`) and pick your `-ar`/`-ac`. Keep `-vn` to drop video when extracting.

---

## Recipe 4 — Mux / replace / strip an audio track (preserve everything else)

These keep ALL other streams under stream copy — nothing re-encoded, nothing
silently dropped (tracks_audio.py docstring, A2/A6 lesson).

**Mux** a new audio stream (`build_mux_argv`, tracks_audio.py:184-203):
`-map 0` keeps every source stream (video + all existing audio + all subtitles),
`-map 1:a` appends the new audio, `-c copy` re-encodes nothing. Language is tagged
on the NEW stream's audio index `existing_audio_count`:

```bash
ffmpeg -hide_banner -nostdin -y \
  -i in.mp4 -i dub.aac \
  -map 0 -map 1:a -c copy \
  -metadata:s:a:1 language=es \
  -progress pipe:1 -nostats \
  out.mp4
```

**Replace** stream `a:<n>` (`build_replace_argv`, tracks_audio.py:223-244):
`-map 0` then NEGATIVE-map the one stream out, then append the replacement:

```bash
ffmpeg -hide_banner -nostdin -y \
  -i in.mp4 -i new.aac \
  -map 0 -map -0:a:1 -map 1:a -c copy \
  -metadata:s:a language=es \
  -progress pipe:1 -nostats \
  out.mp4
```

**Strip** stream `a:<n>` (`build_strip_audio_argv`, tracks_audio.py:261-278):
just the negative map, copy the rest:

```bash
ffmpeg -hide_banner -nostdin -y \
  -i in.mp4 \
  -map 0 -map -0:a:1 -c copy \
  -progress pipe:1 -nostats \
  out.mp4
```

Wire surface (names FROZEN by CONTRACTS A2):
- `tracks.audio.list({videoId}) -> {audioTracks:[AudioTrack]}`
- `tracks.audio.mux({videoId, path, lang, name, kind}) -> {audioTrack}`
- `tracks.audio.replace({videoId, audioTrackId, path}) -> {audioTrack}`
- `tracks.audio.strip({videoId, audioTrackId}) -> {path}`

`AudioTrack {id, lang, name, kind:"original"|"dub", voice?, path}`.

---

## Pitfalls that actually bite

1. **`amix` auto-attenuates — you MUST pass `normalize=0`.** ffmpeg's `amix`
   divides each input by the input count, so a 2-input mix halves your
   foreground. The graph sets `normalize=0` precisely because the bed is already
   ducked and loudnorm does final leveling (audiomix.py:142-144). Drop it and the
   speaker goes quiet.

2. **Stream-index = list-order coupling.** `tracks.audio.replace`/`strip` derive
   the container `a:<n>` index from the track's POSITION in `Project.audioTracks`
   (`audio_track_index`, tracks_audio.py:136-141). Originals are seeded in ffprobe
   stream order and dubs appended as muxed, so order MUST mirror the freshest
   derivative. Reorder the list out of band and you'll negative-map the wrong
   stream. The seed only runs once (skips if any `kind=="original"` row exists,
   tracks_audio.py:378).

3. **`-shortest` alone is not enough for a music bed.** Length is tied to the clip
   by BOTH `-shortest` AND `duration=first` inside `amix`. A bed shorter than the
   clip won't loop — it just ends (`dropout_transition=0` prevents a gain bump at
   that point). If you want a looping bed, add `-stream_loop -1` before the bed
   `-i`, which is NOT in the stock argv.

4. **loudnorm here is SINGLE-PASS (dynamic).** `build_loudnorm_argv` runs one-pass
   `loudnorm` — it adapts in real time and can drift / pump on material with wide
   dynamics, and won't hit the integrated target as precisely as two-pass. For a
   precise master you'd run loudnorm once with `print_format=json`, capture
   `measured_I/TP/LRA/thresh/offset`, then feed them back (`measured_I=…:linear=true`).
   The module deliberately keeps one pass for speed in a job pipeline. Know the
   tradeoff before claiming "broadcast-exact".

5. **Negative map order matters.** In replace, `-map 0` must come BEFORE
   `-map -0:a:1` before `-map 1:a`. ffmpeg applies maps in sequence; reordering can
   leave the stream you meant to drop, or fail to append. Copy the exact order.

6. **`-c:v copy` requires a compatible container.** The mix/normalize paths copy
   video and write `.mp4`. Copying e.g. VP9/WebM video into `.mp4` will fail —
   stream copy can't transcode. The source always outputs `.mp4` because the
   library is H.264/AAC; match that or re-encode video explicitly.

7. **Language metadata target differs between ops.** mux tags
   `-metadata:s:a:<existing_count>` (the specific new stream); replace tags
   `-metadata:s:a` (all audio). That's intentional — mux adds one stream among
   many; replace swaps the stream set. Don't "normalize" them to the same form.

8. **probe / duration failures degrade gracefully, never crash.** `probe_streams`
   returns `{}` on any ffprobe failure (tracks_audio.py:300-306); `ffprobe_duration`
   returns 0.0; a 0.0 total just coarsens the progress % (audiomix.py:313-314).
   So a missing/garbage probe won't fail the op — but your progress bar will be
   flat. Don't read "0%" as a hang.

9. **`-nostdin` is mandatory in a pipeline.** Every argv sets `-nostdin` so ffmpeg
   never blocks reading the controlling terminal, plus `-progress pipe:1 -nostats`
   so the shared `run` parses machine-readable `out_time`/`progress` lines instead
   of the human stderr bar. If you hand-run without `-nostdin`, a backgrounded
   ffmpeg can stall waiting on stdin.

---

## GPU / HF-model notes (audio_saliency only)

- **Model:** PANNs CNN14 AudioSet tagger (`ASSET_NAME="panns-cnn14"`, MIT,
  ~300 MB, CPU-designed — **no GPU required**). Pinned checkpoint on Zenodo:
  `Cnn14_mAP=0.431.pth`, sha256 `0dc499e40e9761ef5ea061ffc77697697f277f6a960894903df3ada000e34b31`
  (audio_saliency.py:79-87). Verified against the asset before use.
- **Decode contract for the model:** mono, 32 kHz, float (`TARGET_SR=32000`).
  Feed any other rate and the tag probabilities are garbage — the loader enforces
  `-ac 1 -ar 32000` (Recipe 3). Don't skip the resample.
- **Degrade rules (NEVER fabricate, NEVER raise)** (`compute_audio_signals`,
  audio_saliency.py:405-485):
  - No / silent audio → tag channels (audioSalience/laughter/applause/music)
    `present=False`; `loudness` is `present=True` with a single honest `0.0`
    window (silence is measured, not faked).
  - Offline AND model missing → tag channels `present=False`; loudness still runs
    (it needs no model). Online-but-missing falls through (a real backend would
    download).
  - Cancelled before tagging → tag channels absent; whatever loudness computed is
    returned.
- **Channels** (`AUDIO_CHANNELS`): `audioSalience` (DERIVED = per-window max over
  the event classes), `laughter` (AudioSet idx 16), `applause` (63), `music` (137),
  `loudness` (pure RMS, no model — always present). Indices are FROZEN so a model
  swap can re-map without touching the pure windowing logic.
- **Windowing:** `sample_windows(duration, win_sec=1.0, hop_sec=1.0)` is the
  shared grid every Phase-8 module aligns to; values are min-max normalized to
  0..1 per channel (`loudness_curve` / `peak_windows`). A flat/silent track
  normalizes to all zeros — an honest "no relative peak".

---

## Worked example: lay a -10 dB music bed under a TikTok clip at -14 LUFS

Goal: mix `lofi.mp3` under `clip.mp4`, duck it when the speaker talks, export at
the TikTok loudness target.

1. Resolve the target loudness from the platform (don't hard-code -14):
   `resolve_loudness_target("tiktok")` → `-14.0` (raises on a typo like `"tik-tok"`).
2. Build + run the merge graph (Recipe 1) with `platform="tiktok"`:

```bash
ffmpeg -hide_banner -nostdin -y \
  -i clip.mp4 -i lofi.mp3 \
  -filter_complex "[1:a]volume=-10.0dB[bg];[0:a]asplit=2[fg_key][fg_mix];[bg][fg_key]sidechaincompress=threshold=0.03:ratio=8.0[ducked];[fg_mix][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mixed];[mixed]loudnorm=I=-14.0:TP=-1.5:LRA=11.0[out]" \
  -map 0:v -map "[out]" -c:v copy -c:a aac -shortest \
  -progress pipe:1 -nostats \
  clip-mixed-1751299200.mp4
```

3. Verify: speaker stays dominant (bed dips under speech, swells in gaps),
   output duration == clip duration (bed trimmed by `-shortest`), and integrated
   loudness lands near -14 LUFS — re-measure with a loudnorm analysis pass
   (`ffmpeg -i out.mp4 -af loudnorm=I=-14:print_format=summary -f null -`) rather
   than trusting the single-pass result (pitfall #4). The output name is
   `<stem>-mixed-<unixtime>.mp4` (`AudioMix._out_path`, audiomix.py:306-309).

Tuning knobs if the bed is too aggressive / not aggressive enough: lower
`bgGainDb` (e.g. `-14`) to make the bed quieter overall; raise `duckThreshold`
so quiet speech doesn't trigger ducking; raise `duckRatio` for a deeper dip.