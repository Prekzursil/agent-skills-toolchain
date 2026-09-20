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

## Burn vs soft-mux — the tradeoff (decide first)
| | Burn (hardsub) | Soft-mux |
|---|---|---|
| ffmpeg | `-vf subtitles=...` (libass rasterises) | `-map 0 -map 1 -c copy -c:s ...` |
| Video | **RE-ENCODED** (lossy, slow) | **stream-copied** (lossless, fast) |
| Removable later | No — `tracks.strip` refuses a `kind=="hard"` track | Yes — `tracks.strip` negative-maps the sub stream |
| Styling fidelity | Full ASS (colour, karaoke, pop, box) | Native ASS only in MKV; **MP4/MOV downgrade to `mov_text`** = plain text, no styling |
| Player support | Universal (it's just pixels) | Needs a player/track-selector |
| Use when | Social/vertical export, karaoke, any styled look, MP4 delivery | Archival, multi-language toggle, keep original bytes |

Rule of thumb from the code: anything that needs the OpusClip look, karaoke, hook card, or a styled override and ships as MP4 -> **burn**. A toggleable subtitle in an MKV -> **soft-mux**.

## Recipe (the real flow, from `CaptionEngine.render`)
```
cues {index,start,end,text[,words,emphasis,emoji]}
  -> (optional) caption_polish.polish_cues   # Netflix CPS/CPL split + punct/casing/emphasis/profanity
  -> build_ass(...) OR build_karaoke_ass(...) # ASS document sized PlayResX x PlayResY
       - re-base every cue time by source_start  (clip offset in the ORIGINAL video)
       - escape cue text against ASS override injection
       - resolve CaptionOverride onto Style: Default (font/size/colour/outline/box/band/uppercase)
  -> write to a temp .ass sidecar (UTF-8, newline="")  # argv-passed, never piped through a shell
  -> ffmpeg:  burn  = build_burn_argv     (subtitles= filter, libass; -c:a copy)
              softmux= build_softmux_argv  (map both, -c:v/-c:a copy, -c:s mov_text|ass)
  -> CaptionError on non-zero exit; temp .ass unlinked in finally
```

### Exact ffmpeg argv — BURN (`caption.build_burn_argv`)
```
ffmpeg -hide_banner -nostdin -y -i <clip> -vf subtitles='<escaped_ass_path>' \
       -c:a copy -progress pipe:1 -nostats <out>
```
Note: there is **no `-c:v`** — ffmpeg picks the container default encoder (libx264 for `.mp4`) at its **default CRF (~23)**. If you need quality/bitrate control you must extend the argv; the burn builder does not expose it.

### Exact ffmpeg argv — SOFT-MUX (`caption.build_softmux_argv`)
```
ffmpeg -hide_banner -nostdin -y -i <clip> -i <ass> \
       -map 0:v -map 0:a? -map 1:0 \
       -c:v copy -c:a copy -c:s <scodec> -progress pipe:1 -nostats <out>
```
`scodec` = `mov_text` for `.mp4/.m4v/.mov`, else `ass` (MKV keeps native styling). `tracks.build_soft_mux_argv` is the variant that maps `-map 0 -map 1 -c copy` and tags `-metadata:s:s:0 language=<lang>`.

### STRIP a soft sub (`tracks.build_strip_argv`)
```
ffmpeg ... -i <in> -map 0 -map -0:s:<index> -c copy -progress pipe:1 -nostats <out>
```
Re-mux that negatively-maps one subtitle stream. A burned (`kind=="hard"`) track raises `HardSubtitleError` — there is no stream to remove.

## ASS document structure (`build_ass`)
- `[Script Info]`: `PlayResX/PlayResY = width/height` (default **1080x1920**), `WrapStyle: 0`, `ScaledBorderAndShadow: yes`. libass lays out for the EXACT export canvas — get this wrong and font size/margins scale wrong.
- `[V4+ Styles]` `Style: Default`: white fill, black outline + drop shadow. Base font `Arial`, `font_size = max(12, round(height*0.045))` then `* size_scale`. Bottom-centred (`Alignment 2`) with L/R margin 40 and `MarginV = max(10, round(height*0.06))`.
- Body cue events; optional `HookTitle` (top-anchored headline) or `HookCard` (white opaque box, first ~5 s) emitted FIRST so it draws above the captions.
- Output uses **LF** line endings (determinism; libass accepts LF).

## libass styling fields you actually touch (`CaptionOverride` -> `ResolvedCaptionStyle`)
The additive tuning patch (`apply_override`) resolves ~8 primitives on top of the base, each degrading independently to the template default (never raises):
- `fontFamily` — must be in `CURATED_CAPTION_FONTS` (Inter, Roboto, Open Sans, Noto Sans, Lato, Nunito, Montserrat, Poppins, Oswald, **Anton**, **Bebas Neue**, Archivo Black, DejaVu Sans) or it is dropped back to `Arial`. `DejaVu Sans` is libass's always-present fallback.
- `sizeScale` — clamped to **0.6 .. 1.8**, multiplies the canvas-derived base size.
- `textColor` / `spokenColor` -> `PrimaryColour`; `activeColor` -> `SecondaryColour`. Bad hex dropped.
- `box: true` -> `BorderStyle=3` (opaque box using `BackColour`); `outline: true/false` -> `BorderStyle=1`, width 3/0. Box wins over outline.
- `positionBand` -> top=8 / center=5 / bottom=2 (centre is libass-centred, MarginV ignored).
- `uppercase: true` -> all-caps.

### ASS colour format — the silent-wrong-colour trap (`hex_to_ass_color`)
ASS colours are **`&HAABBGGRR`** — alpha + **B,G,R reversed vs CSS `#RRGGBB`**, AND the alpha byte is **inverted** (`00` = opaque, `FF` = transparent). So `#FF0000` (red) -> `&H000000FF&`, `#123456` -> `&H00563412&`. Getting the byte order wrong renders the wrong colour with **no crash**. Tests pin the exact `&H...` string per input hex.

## Karaoke preset (`caption_karaoke.build_karaoke_ass`, style id `opusclip-karaoke`)
The flat override fields cannot express the per-word colour + scale-pop, so this is a SEPARATE ASS builder routed from `CaptionEngine.render(..., karaoke=True)`. The standard `build_ass` stays byte-identical to V1.
- One `Dialogue` event **per spoken word** over that word's `[start,end]`, showing the whole 1-4 word line with the active word wrapped in an inline block:
  `{\1c<colour>\t(0,120,\fscx115\fscy115)}WORD{\r}` — alternating active colour + a grow-pop over the first `KARAOKE_POP_MS` (120 ms), then `\r` reset back to the white-fill Style default.
- Active colour alternates **yellow `&H0000FFFF&` -> green `&H0000FF00&`** by absolute word order (skipped words still advance the index so the alternation stays stable).
- Look: font **Anton**, bold, `BorderStyle=1` (outline+shadow, NOT a box), outline width 4, shadow 2, all-caps, `font_size = max(12, round(height*0.05))`, 1-4 words/line.
- Safe area (9:16): default **bottom** band clears the bottom ~18% (`SAFE_AREA_BOTTOM_FRACTION`) -> lower-mid, off the platform UI; top clears ~10%; side margin 6% of width.
- **Word timing**: prefers the cue's aligned `words` list (karaoke-grade). With NO word timing it whitespace-splits the cue text and distributes the `[start,end]` window EVENLY — a documented degrade, not a silent failure.

## Caption polish (`caption_polish.polish_cues`) — run BEFORE building the ASS
Pure Netflix timing gate (always applied) + three optional model seams (skipped when their backend is `None`):
- CPS cap: children 13 / English 20 / other 17, user `maxCps` clamped 10..30. CPL <= 42, <= 2 lines, min gap 2 frames (at 30 fps).
- `enforce_cps_cpl` splits/retimes a too-long cue into proportional slices; `enforce_min_gap` pulls each `end` back to keep the gap. Honest about limits: proportional splitting CANNOT make a genuinely too-fast cue readable (that needs more on-screen time upstream) — CPL is always enforced, CPS is the capacity floor.
- Punct+casing = sherpa-onnx CT-Transformer, HF repo `lorneluo/sherpa-onnx-online-punct-en-2024-08-06` @ `aad05f2d2818122135b0667806628019cb923e84` (~30 MB, EN-only, Apache-2.0; the original csukuangfj repo 404s — re-pointed). KeyBERT (all-MiniLM) for emphasis keywords; alt-profanity-check for masking. All lazy-imported; absent model => stage skipped.

## Pitfalls that actually bite
1. **ASS override injection.** Cue/hook text is transcript/model-derived. `{...}` is an ASS override block; a line like `{\an8}` could reposition or blank text. `escape_ass_text` escapes `\` FIRST (else the backslashes it adds for braces get doubled), then `{`->`\{`, `}`->`\}`, real newlines -> `\N`. NEVER hand-assemble Dialogue text without this.
2. **Re-base cue times or captions never show.** Cues are timed against the ORIGINAL video; a clip cut from t=120 s must subtract `source_start` so its first caption is at clip-local t=0, not t=120 (which would never display). Pass the candidate's `sourceStart`. Cues whose end <= start after re-base are dropped.
3. **ASS colour byte-swap** (see above) — `&HAABBGGRR`, BGR reversed, inverted alpha. Silent wrong colour, no crash.
4. **Windows path escaping inside the `subtitles=` filter.** Inside `-vf`, `\`, `:` (drive letter `C:`), `'` and `[]` are filtergraph-special. `_escape_filter_path` wraps in single quotes and escapes `\`->`\\`, `:`->`\:`, `'`->`\'`. A raw `C:\a b\subs.ass` otherwise breaks the filtergraph parse. The .ass is always passed as an argv path, never a shell string.
5. **Burn RE-ENCODES; there is no `-c:v` in the burn argv** -> ffmpeg uses the container default encoder at default CRF (~23). Expect generation loss and slow encode. Soft-mux is lossless `-c copy`. If burning to MP4 needs a target quality, extend the argv yourself.
6. **MP4 soft-mux silently downgrades to `mov_text`** — ASS styling/karaoke/box are LOST (plain text only). To keep styling in an MP4 you must BURN. Soft-mux into MKV (`-c:s ass`) preserves it.
7. **Font must be installed for libass to use it.** `Anton`/`Bebas Neue` (karaoke/condensed looks) and the curated list are the burn-in fontconfig allowlist; if the face is missing on the host, libass falls back (to `DejaVu Sans`) and the burn looks wrong — and the override layer drops any non-curated font to `Arial` before that. Verify the curated fonts are present in the burn environment.
8. **`uppercase` must transform per-slice BEFORE escaping, never the assembled string.** Upper-casing the assembled line would corrupt an inserted `{\b1}` into `{\B1}` (a broken override). `render_cue_text` upper-cases each raw slice independently so emphasis/span offsets stay aligned.
9. **stderr pipe deadlock (the "stuck clip" trap).** ffmpeg chats continuously on stderr even with `-nostats` (banner, stream info, libass FONT logs). `ffmpeg.run` captures `stderr=PIPE` and **drains it on a daemon thread**; if you build your own subprocess and never read stderr, the ~64 KB pipe fills and the encode BLOCKS forever. Always drain stderr (or let `ffmpeg.run` do it). `-progress pipe:1` feeds the progress parser on stdout.
10. **argv list only — never `shell=True`.** `ffmpeg.run` raises `TypeError` on a shell string. Paths with spaces are safe because every element is a separate argv item.
11. **A burned track cannot be stripped.** `tracks.strip` raises `HardSubtitleError` for `kind=="hard"`. Burn is irreversible; only soft-muxed streams are removable.
12. **Hook title/card timing.** Hook title spans the whole clip (`total_sec`, else last cue / 60 s floor). Hook card is time-boxed to ~first 5 s. Emit them as the FIRST events so they layer above body captions.

## GPU / model notes
- Burn/soft-mux/strip are **pure ffmpeg/libass — CPU, no GPU, no HF model.** Burn is the slow step (full video re-encode); soft-mux/strip are near-instant stream-copies.
- The only model dependency is the OPTIONAL `caption_polish` pass: sherpa-onnx punct model (~30 MB, pinned HF revision above), KeyBERT all-MiniLM, alt-profanity-check. All lazy; absent => that stage is skipped, the timing gate still runs. None require a GPU.

## Worked example — burn OpusClip karaoke onto a 9:16 clip
A clip cut from t=120 s of the source, with word-aligned cues, exported at 1080x1920:
```python
from media_studio.features.caption import CaptionEngine

engine = CaptionEngine(settings={"ffmpegPath": "ffmpeg"})  # runner defaults to ffmpeg.run
out = engine.render(
    clip_path="clip.mp4",
    cues=cues,                # [{index,start,end,text,words:[{text,start,end}]}, ...]
    out_path="clip-karaoke.mp4",
    burn=True,                # hardsub (MP4 -> styling MUST be burned, not mov_text)
    width=1080, height=1920,
    source_start=120.0,       # re-base: clip-local t=0 == source t=120s
    karaoke=True,             # -> caption_karaoke.build_karaoke_ass (Anton, yellow/green pop)
    total_sec=58.0,           # source duration for progress -> pct
    on_progress=lambda pct, msg: print(f"{pct:.0f}% {msg}"),
)
```
Under the hood this builds the karaoke ASS (per-word events, alternating accent + scale-pop, lower-mid safe area), writes a temp `.ass`, and runs:
```
ffmpeg -hide_banner -nostdin -y -i clip.mp4 \
       -vf subtitles='clip-karaoke.ass' -c:a copy -progress pipe:1 -nostats clip-karaoke.mp4
```
A non-zero exit raises `CaptionError`; the temp `.ass` is unlinked regardless.

To instead keep a removable English track in an MKV (lossless, styling preserved):
```python
out = engine.render("clip.mkv", cues, "clip-sub.mkv", burn=False,
                    width=1080, height=1920, source_start=120.0)
# -> ffmpeg ... -i clip.mkv -i <ass> -map 0:v -map 0:a? -map 1:0 \
#       -c:v copy -c:a copy -c:s ass -progress pipe:1 -nostats clip-sub.mkv
```
(For MP4 this would emit `-c:s mov_text` and the karaoke styling would be lost — burn for MP4.)

## See also
`opusclip-shorts` owns the END-TO-END long-video -> karaoke shorts pipeline (selection, tracking, timing, QC) and consumes these burn rules when rendering standalone; its karaoke engine is the single-layer timed color-flip in this repo's own `render_final.py`. Cross-checked 2026-09-20: both techniques are single-layer/layout-safe.
