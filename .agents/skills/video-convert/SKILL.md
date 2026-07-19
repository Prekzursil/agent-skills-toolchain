---
name: video-convert
description: "Use when converting a video/audio file's FORMAT, CODEC, or CONTAINER in media-studio (mp4/mkv/mov/webm/gif, h264/h265/vp9/av1, or audio-only extraction to mp3/m4a/wav/flac/opus) — single file or batch, or normalizing a non-Chromium-playable source for playback (remux vs h264-720p proxy). Covers."
---

# Video Convert (format / codec / container) — media-studio

Convert format/codec/container, extract audio, batch-convert, and produce a Chromium-playable derivative (remux or h264-720p proxy). This skill documents the **real** media-studio implementation — every command below is what the code actually emits. No invented flags.

## Source modules (read these for ground truth)
- `C:/Users/Prekzursil/Documents/GitHub/Reframe/sidecar/media_studio/ffmpeg.py` — **the argv builder** (`build_convert_argv`), `build_probe_argv`, `ffprobe_duration`, and the progress-streaming `run()`. This is where the convert command is actually assembled.
- `C:/Users/Prekzursil/Documents/GitHub/Reframe/sidecar/media_studio/features/convert.py` — `convert.start` / `convert.batch` feature layer: pure output-path derivation (`output_path`), audio-ext map, `convert_one` / `convert_batch`, job handlers.
- `C:/Users/Prekzursil/Documents/GitHub/Reframe/sidecar/media_studio/features/media_compat.py` — `media.playable` / `media.proxy.start`: codec-driven playability `classify`, `build_remux_argv`, `build_proxy_argv`, proxy cache.
- `C:/Users/Prekzursil/Documents/GitHub/Reframe/sidecar/media_studio/features/export_presets.py` — `exportPresets.*` catalog (platform export targets; aspect + 20-60s window, NOT codec).

## When to use which path (pick fast)
1. **User wants a different format/codec/container, or audio extraction** -> `convert.start` / `convert.batch` (this is "convert"). Builder = `ffmpeg.build_convert_argv` (convert.py:182).
2. **User just wants a file to PLAY in the app and it won't** (HEVC, WMV, MPEG-2, or h264-in-MKV) -> `media.playable` then `media.proxy.start`. The verdict is **codec-driven, not extension-driven** (media_compat.py:162 `classify`):
   - all streams Chromium-playable AND container playable -> `playable` (play original, build nothing).
   - all streams playable but container isn't (e.g. h264-in-MKV) -> `remux` (`-c copy` into mp4, cheap).
   - ANY stream unplayable (HEVC even inside MKV) -> `proxy` (h264 720p transcode).
   Playable video codecs: `h264, vp8, vp9, av1`; audio: `aac, mp3, opus, vorbis, flac, pcm_*` (media_compat.py:59-61). Anything else => proxy.

## The convert option contract (frozen — CONTRACTS.md §2)
`convert.start({videoId|path, options, out?})` / `convert.batch({items:[...]})`. `options` keys (convert.py:23-25, consumed in ffmpeg.py:122-169):

| key | effect in argv | notes |
|-----|----------------|-------|
| `container` | output **extension** only (mp4/mkv/mov/webm/gif/...) | ffmpeg picks the muxer from the out file extension. NOT validated against codec. |
| `vcodec` | `-c:v <vcodec>` | e.g. `libx264`, `libx265`, `libvpx-vp9`, `libaom-av1`. Omit => ffmpeg default for the container. |
| `acodec` | `-c:a <acodec>` | e.g. `aac`, `libmp3lame`, `libopus`. |
| `crf` | `-crf <crf>` | video path only. NOT clamped/validated. Encoder-specific scale. |
| `scale` | `-vf scale=W:H` | accepts `"1280:720"` OR `"1280x720"` (`x` -> `:`, ffmpeg.py:159). |
| `fps` | `-r <fps>` | output frame rate. |
| `audioOnly` | adds `-vn`, drops all video flags | extract audio. Only `acodec` applies. |
| `audioFormat` | drives the output **extension** (not a codec flag) | mapped to ext in convert.py:61-84. |

There is **no bitrate, no preset, no pix_fmt, no -map, no faststart** key. If you need those, the convert path does not provide them — see Pitfalls 1, 2, 5.

## The real convert command
`ffmpeg.build_convert_argv(in, out, options, settings)` produces exactly (ffmpeg.py:137-169):

```
ffmpeg -hide_banner -nostdin -y -i <in>
   [ -vn ]                              # audioOnly
   [ -c:v <vcodec> ]                    # video path only
   [ -c:a <acodec> ]
   [ -crf <crf> ]                       # video path only
   [ -vf scale=<W>:<H> ]                # video path only; "WxH" normalized to "W:H"
   [ -r <fps> ]                         # video path only
   -progress pipe:1 -nostats <out>
```

- Always argv **list**, never `shell=True` (paths with spaces are one element — safe). The binary is resolved settings.ffmpegPath -> `MEDIA_STUDIO_FFMPEG` env -> bundled `resources/bin/` -> PATH (ffmpeg.py:48-92).
- `-progress pipe:1 -nostats` makes stdout a `key=value` stream; `run()` (ffmpeg.py:224) turns `out_time*` into a 0-100 pct against the ffprobe duration.

### Output path derivation (convert.py:94-125 `output_path`)
- explicit `out` -> used verbatim (caller owns the name).
- else `<in stem>.<ext>` in the **source's own directory**, where `ext` = `audioFormat` ext when `audioOnly`, else `container` ext.
- if the derived dest equals the source (same dir+stem+ext, e.g. re-encoding `a.mp4` -> mp4 in place) it becomes `<stem>.converted.<ext>` so it never clobbers the original.
- audioFormat->ext map (convert.py:61-76): `mp3/libmp3lame`->mp3, `aac/m4a/alac`->m4a, `wav/pcm`->wav, `flac`->flac, `opus/libopus`->opus, `vorbis/libvorbis/ogg`->ogg, `ac3`->ac3. Unknown value used **verbatim** as the extension (default video `mp4`, default audio `m4a`).

## Worked examples

**1. Re-encode an MKV to a web-friendly mp4 (h264 + aac, CRF 20, 720p):**
```jsonc
// convert.start params
{ "path": "C:/clips/raw recording.mkv",
  "options": { "container": "mp4", "vcodec": "libx264", "acodec": "aac",
               "crf": 20, "scale": "1280x720" } }
```
Emitted argv (note the space in the path is one safe element):
```
ffmpeg -hide_banner -nostdin -y -i "C:/clips/raw recording.mkv" \
   -c:v libx264 -c:a aac -crf 20 -vf scale=1280:720 \
   -progress pipe:1 -nostats "C:/clips/raw recording.mp4"
```
> Add `pix_fmt yuv420p` + faststart yourself if this must stream/play everywhere — the convert builder does NOT (Pitfalls 1 & 2). If you can, prefer routing such "make it play" cases through `media.proxy.start`, which DOES set both.

**2. Extract audio to mp3:**
```jsonc
{ "path": "C:/clips/talk.mp4", "options": { "audioOnly": true, "audioFormat": "mp3", "acodec": "libmp3lame" } }
```
-> `ffmpeg -hide_banner -nostdin -y -i talk.mp4 -vn -c:a libmp3lame -progress pipe:1 -nostats talk.mp3`

**3. Batch convert a folder to mp4:** `convert.batch({items:[{path,options},...]})`. Progress is spread evenly: item *i* of *n* reports `(i*100 + per_item_pct)/n` (convert.py:219-225), so a 4-item batch climbs 0->25->50->... Cancellation is honored **between** items and within an item.

**4. Make a non-playable source playable (the proxy path):** call `media.playable({videoId})`; if `{playable:false, reason:"video codec not Chromium-playable: hevc"}`, call `media.proxy.start({videoId})`. It runs the **proxy** transcode (media_compat.py:243-281):
```
ffmpeg -hide_banner -nostdin -y -i <in> -map 0:v:0 -map 0:a:0? \
   -c:v libx264 -preset veryfast -crf 23 -vf scale=-2:720 -pix_fmt yuv420p \
   -c:a aac -b:a 128k -movflags +faststart -progress pipe:1 -nostats <out>
```
For h264-in-MKV it instead **remuxes** (media_compat.py:210-240): `-map 0 -map -0:s -map -0:d -map -0:t -c copy -movflags +faststart` (drops subtitle/data/attachment streams that aren't mp4-legal under stream copy). Result is cached at `%APPDATA%/media-studio/proxies/<videoId>-<mtime_ns>.mp4`; the mtime IS the cache invalidation (re-edit the source -> new path; stale siblings evicted). The original is always kept for convert/export — the proxy is playback-only.

## Pitfalls (the ones that actually bite)

1. **No `pix_fmt` in convert -> may not play in Chromium/QuickTime.** `build_convert_argv` never sets `-pix_fmt`. x264 will happily emit `yuv444p` or 10-bit for some inputs/options, which the Electron renderer (and Safari/QuickTime) refuse to decode. The proxy path forces `yuv420p` for exactly this reason (media_compat.py:269). If a converted mp4 "won't play", suspect chroma/bit-depth first. Workaround: pass it through `media.proxy.start`, or add `-pix_fmt yuv420p` if you build the argv directly.

2. **No `-movflags +faststart` in convert -> mp4 not progressively streamable.** convert output keeps the `moov` atom at the END, so a `<video>` tag can't begin until the whole file is fetched. Remux and proxy add `+faststart` (media_compat.py:235, 275); plain convert does not. Fine for local files; bad for serve-over-HTTP.

3. **Container/codec legality is NOT validated.** `container` only sets the output extension; the muxer is chosen from it. `container:"webm"` + `vcodec:"libx264"` makes ffmpeg fail ("Only VP8/VP9/AV1... supported for WebM"); `container:"mp4"` + `vcodec:"libvpx-vp9"` is also illegal. The failure surfaces as a non-zero exit -> `RuntimeError` (convert.py:189). Match codec to container: mp4/mov -> h264/h265/av1 + aac; webm -> vp8/vp9/av1 + opus/vorbis; mkv -> almost anything.

4. **GIF needs special handling the convert builder doesn't give you.** `container:"gif"` just changes the extension; without a palette filter ffmpeg uses a generic 256-color quantization -> banding/dither artifacts, and audio flags are meaningless. For a quality GIF you need a two-pass `palettegen`/`paletteuse` filtergraph, which this contract can't express. Treat GIF export as out-of-scope for plain convert.

5. **`-progress pipe:1` puts the progress stream on STDOUT — never `capture_output` without draining stderr.** `run()` (ffmpeg.py:246-272) captures stderr=PIPE and **drains it on a daemon thread**. ffmpeg chats continuously on stderr even with `-nostats` (banner, stream info, font logs); if you ever rebuild this and forget to drain, the ~64KB stderr pipe fills and the encode **blocks forever** — this was the real "stuck at clip 1/5 for 29 min" bug (ffmpeg.py:254-258). On non-zero exit the last ~8 stderr lines are logged for diagnosis.

6. **`out_time_ms` is actually MICROSECONDS.** ffmpeg's `-progress` field is historically mislabeled; the code divides by `1_000_000`, not `1000` (ffmpeg.py:202-218). If you parse progress yourself, don't trust the field name.

7. **A failed/zero duration probe degrades progress to coarse, it does NOT fail the job.** `convert_one` swallows a probe exception and sets `total_sec=0` (convert.py:176-180); with no total, `run()` can't compute a percentage and only emits the final `100.0 / "done"` on `progress=end`. Long convert with a "frozen at 0%" bar usually means ffprobe couldn't read a duration (streaming source, no container duration) — the encode is still progressing.

8. **`media.playable` is codec-driven; extension lies.** A `.mp4` containing HEVC is `proxy`, and a `.mkv` containing h264 is `remux`, not `playable`. Also: ffprobe reports BOTH `.webm` and `.mkv` as `matroska,webm` (one demuxer), so classify disambiguates by file extension (media_compat.py:148-159) — a real `.webm` whose streams pass is playable, `.mkv` goes to remux. Never decide playability from the extension.

9. **Re-encoding in place is auto-renamed, not blocked.** `a.mp4` -> mp4 in the same dir becomes `a.converted.mp4` (convert.py:122-124). If you expected to overwrite, pass an explicit `out`. Conversely an explicit `out` is verbatim with `-y` -> it WILL overwrite whatever is there.

10. **No `-map` on convert -> default-stream selection.** convert relies on ffmpeg's implicit stream mapping (best video + best audio of the chosen codecs). Multi-audio / multi-subtitle sources lose the non-default tracks. The remux path is the only one that explicitly maps (`-map 0` minus subs/data/attachments). If track preservation matters, convert is the wrong tool.

11. **`exportPresets` are platform/aspect targets, NOT codec settings.** `export_presets.py` stores `{aspect, minSec, maxSec, count, captionStyle, reframeEngine}` with the window hard-clamped to 20-60s (export_presets.py:54-55, 137-138) and aspect guarded to the curated social set (9:16/1:1/4:5). They feed the short-maker/reframe pipeline, not `convert.*`. Don't conflate "export preset" with "convert options" — they share no fields.

## GPU / HF-model notes
- **No GPU, no HF model is involved.** Convert, remux, and proxy are pure CPU ffmpeg (`libx264 -preset veryfast` for the proxy). There is no NVENC/QSV/VAAPI hardware-encode path in the contract; adding `-c:v h264_nvenc` would require routing it through `vcodec` and a matching ffmpeg build, and it is unvalidated. For batch throughput, parallelism is the lever, not hardware encode — but note `convert_batch` runs items **sequentially** within one job (convert.py:215-238); concurrency would be at the job-registry level.

## Confidence
HIGH — every command, option key, codec table, cache path, and pitfall is read directly from the four cited source files (ffmpeg.py, convert.py, media_compat.py, export_presets.py). The convert builder, proxy/remux argvs, ext maps, window clamp, and the stderr-drain/microsecond/faststart/pix_fmt gaps are verbatim from the code. Behavior of ffmpeg muxers (container/codec legality, GIF palette) is standard ffmpeg, noted as such where the media-studio contract does not enforce it.
