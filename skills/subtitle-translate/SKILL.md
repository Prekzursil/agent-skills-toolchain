---
name: subtitle-translate
description: Use when translating subtitles/captions to another language and/or generating
  + exporting SRT/VTT/ASS for a media-studio video — including bilingual (stacked)
  subs and the audio-dub (TTS) path. Covers the tiered local→hosted MT engine (TranslateGemma
  GGUF via llama.cpp, language-aware routing +.
permalink: dqverify-repo-20261013/skills/subtitle-translate/skill
---

# Subtitle translate / generate / export (+ dub)

This skill is distilled from the REAL media-studio implementation. Every command,
field name, model id, and gotcha below is taken from these source files (read
them when in doubt):

- `media_studio/features/subtitles.py` — the pure track logic: `generate`,
  `edit`, `translate`, `export`, `stack_bilingual`, and the SRT/VTT/ASS
  serializers + parsers + timestamp helpers.
- `media_studio/models/translation.py` — the **TieredTranslator** MT engine
  (tier1/tier2 local GGUF + tier3 hosted), language routing, fallback chain.
- `media_studio/handlers/media_ops.py` — the RPC wire shapes
  (`subtitles.generate/edit/export/translate`).
- `media_studio/features/tts/dub.py` — the audio-dub pipeline (`tts.dub.start`).
- `media_studio/features/ctc_align.py` — word-timing forced alignment (karaoke).
- `media_studio/features/caption.py` — ASS document build + ffmpeg burn/soft-mux argv.
- `media_studio/features/transcribe.py` — faster-whisper (upstream source of cues).

The frozen schemas (CONTRACTS.md §3, identical on both sides):

```
Word          = {text, start, end}
Segment       = {start, end, text, words:[Word]}
Transcript    = {language, segments:[Segment], durationSec}
Cue           = {index, start, end, text}        # +optional speaker / emphasis / emoji
SubtitleTrack = {id, lang, name, format, kind:"soft"|"hard", cues:[Cue]}
```

`FORMATS = ("srt", "ass", "vtt")` (`subtitles.py:44`). `"ssa"` is normalized to
`"ass"` (`_normalize_format`, `subtitles.py:753`).

---

## RPC surface (what the UI actually calls)

From `handlers/media_ops.py` — these are the wire methods, not internal helpers:

| Method | Params | Returns | Sync? |
|---|---|---|---|
| `subtitles.generate` | `{videoId}` | `{track}` | direct (reads stored Transcript, calls `generate_polished`) |
| `subtitles.edit` | `{trackId, cues}` | `{track}` | direct |
| `subtitles.export` | `{trackId, format}` | `{path}` | direct |
| `subtitles.translate` | `{trackId, targetLang, bilingual?, order?}` | `{jobId}` → `job.done {track}` | **long job** (progress streamed) |
| `tts.dub.start` | `{videoId, trackId, engine, voice?, sampleId?, targetLang?}` | `{jobId}` → `{audioTrack, path}` | **long job** |

Note: `subtitles.generate` (the handler) takes a `videoId` and loads the stored
transcript, then calls the PURE `generate_polished(transcript, settings=...)` —
the pure `subtitles.generate` takes a *Transcript*, not a videoId
(`media_ops.py:35`). Speaker labels are prefixed when
`captionSpeakerLabels` is on (`media_ops.py:60`, `format_speaker_prefix`).

---

## Recipe A — translate an existing track

The pure entry point is `subtitles.translate(track, target_lang, *, provider | translator, progress, cancelled)`
(`subtitles.py:343`). It returns a **new** track with the same cue
timings/indices, `lang` updated to `target_lang`; the input is never mutated.
**Exactly one** translation seam must be supplied — an injected `translator`
(`str -> str`) OR a `provider` (wrapped via `make_provider_translator`).

In production the handler does NOT use a single provider — it uses the
**TieredTranslator** (`models/translation.py`) via
`translator.translate_track(track, target_lang, progress=, cancelled=)`
(`media_ops.py:137`). Cues are translated and timings preserved verbatim.

Per-cue translation prompt (`subtitles.py:313` / `translation.py:207`):

```
You are a professional subtitle translator. Translate the user's text into
{lang}. Reply with ONLY the translation — no quotes, no notes, no explanation.
Preserve meaning and keep it concise enough to read as a subtitle.
```

Blank cues short-circuit to blank output with **no** model call
(`make_provider_translator._translate`, `subtitles.py:330`), so empty cues stay
empty and you do not pay for them.

### The tiered MT engine (the actual translation model)

`TieredTranslator` (`translation.py:247`) routes by target language:

- **tier1** `TranslateGemma-4B-it Q4_K_M` (2.49 GB, fully GPU-resident) — fast
  local default for the ~40 high/mid-resource langs in `TIER1_LANGS`
  (`translation.py:102`: ar bg ca cs da de el en es … ro ru … zh).
- **tier2** `TranslateGemma-12B-it Q4_K_M` (7.4 GB, **partial** offload,
  `TIER2_GPU_LAYERS = 24` on a 6 GB card, labelled `SLOW` in progress) — the
  low-resource/quality langs in `TIER2_LANGS` (bn gu is kn ml mr pa sw ta te ur zu).
- **tier3** hosted OpenAI-compatible `CloudProvider` — everything outside the
  table (`DEFAULT_TIER = TIER_HOSTED`), keyed on a non-empty `settings.cloudApiKey`.

`route()` / `fallback_chain()` (`translation.py:172`): the routed tier is tried
first, then the remaining tiers in ascending order (tier1→tier2→tier3). On a
**mid-batch** tier failure the WHOLE batch is retried on the next tier — never a
mixed-tier patchwork (`translate`, `translation.py:302`). The local tiers reach
the GPU only through the injected `ModelRunner` whose `start_server` is
model-identity-aware (switching tier1↔tier2 restarts llama.cpp with the right
GGUF; re-using a tier reuses the live process).

`normalize_lang` (`translation.py:158`): `pt-BR`/`pt_BR`→`pt`, `zh_Hant`→`zh`,
`EN`→`en`; raises `ValueError` on a blank tag so a missing `targetLang` fails
loudly instead of silently routing hosted.

### Bilingual (stacked) subtitles

`subtitles.translate({..., bilingual:true, order:"original-first"|"translation-first"})`
stacks original + translation on two lines in one cue (`stack_bilingual`,
`subtitles.py:405`; `stack_cue_text`, `subtitles.py:392`). The bilingual track is
added as a **NEW** track (source kept); monolingual replaces in place
(`media_ops.py:151`). Translation cues are matched by `index` first, then
positional, so a slight count mismatch degrades gracefully. Result `lang` is
`"<orig>+<trans>"`, name defaults to `"Bilingual (<orig>/<trans>)"`.

---

## Recipe B — generate a track from a transcript

`generate(transcript)` → soft track (`subtitles.py:229`). `cues_from_transcript`
(`subtitles.py:139`) makes one cue per segment, but **splits** any segment
longer than `max_chars=84` chars OR `max_duration=7.0` s on word boundaries
(needs per-word timing) so no caption is a wall of text. Blank segments dropped.

`generate_polished(transcript, settings=...)` (`subtitles.py:264`) is the
handler's default: after cue derivation it runs the WU9 caption-polish pass
(Netflix CPS/CPL/min-gap timing + segmentation gate, plus optional punct/casing,
emphasis-keyword, profanity-mask stages — each skipped when its backend is
absent). `lang` is taken from `transcript.language` (else `"und"`).

For **karaoke-grade word timing**, refine the transcript first with
`ctc_align.align_words(transcript, audio_path, settings=...)`
(`ctc_align.py:395`) BEFORE generating, so cues carry tight per-word boundaries.

---

## Recipe C — export to SRT / VTT / ASS

`export(track, fmt, out_path)` (`subtitles.py:774`) → writes UTF-8, returns the
path. Round-trip parsers: `read_srt` / `read_vtt` / `read_ass` (and `load` /
`track_from_file`). Serializers reindex cues 1..N every time (`reindex`,
`subtitles.py:116`).

Timestamp forms (the #1 source of broken subs — they are NOT interchangeable):

| Format | Helper | Form | Separator |
|---|---|---|---|
| SRT | `format_timestamp_srt` (`:477`) | `HH:MM:SS,mmm` | **comma**, 3-digit ms |
| VTT | `format_timestamp_vtt` (`:483`) | `HH:MM:SS.mmm` | **dot**, 3-digit ms |
| ASS | `format_timestamp_ass` (`:489`) | `H:MM:SS.cc`   | **dot**, **2-digit centiseconds**, 1-digit hours |

`parse_timestamp` (`subtitles.py:499`) accepts comma OR dot and disambiguates
2-digit (centiseconds, ASS) vs 3-digit (milliseconds) fractions **by length** —
so a 2-digit SRT fraction would be mis-read as centiseconds. Always write 3
digits for SRT/VTT.

---

## Recipe D — burn or soft-mux captions (caption.py)

`caption.py` builds the ASS doc (`build_ass`, `:304`) sized to the export canvas
(default 1080×1920 vertical) and renders via ffmpeg. The two argv builders:

**Burn-in** (`build_burn_argv`, `caption.py:476`) — hardcodes pixels (re-encodes
video, audio stream-copied):

```
ffmpeg -hide_banner -nostdin -y -i <clip> \
  -vf subtitles='<escaped ass path>' \
  -c:a copy -progress pipe:1 -nostats <out>
```

**Soft-mux** (`build_softmux_argv`, `caption.py:507`) — selectable subtitle
stream, video+audio stream-copied; **codec depends on the output extension**:

```
ffmpeg -hide_banner -nostdin -y -i <clip> -i <ass> \
  -map 0:v -map 0:a? -map 1:0 \
  -c:v copy -c:a copy -c:s <mov_text|ass> \
  -progress pipe:1 -nostats <out>
```

`scodec = "mov_text"` for `.mp4/.m4v/.mov`, else `"ass"` (`caption.py:519`).

---

## Recipe E — audio dub (TTS) path

`tts.dub.start` (`features/tts/dub.py`) is a **batched** long job whose stage
ORDER is the frozen A4 contract (`run_dub_pipeline`, `dub.py:115`):

1. **translate ALL cues** (batched) → then **`translator.free()`** (unload the MT
   model — never interleave model swaps with synthesis).
2. **synth ALL cues** (one engine session).
3. **align each cue** (frozen recipe: target duration → re-synth → `atempo` ±15%
   → pad) — `features/tts/align.py`.
4. **concat** to a full-length WAV → encode AAC (`-c:a aac -b:a 192k`,
   `build_encode_aac_argv`, `dub.py:216`) → **mux as an AudioTrack**.

The dub translator is the SAME T3 `TieredTranslator`, adapted to a text-based
`translate(texts, target_lang, source_lang) -> texts` + `free()` seam
(`ai_ops.py:_dub_translator`, `:400`). `free()` stops the shared llama server.
If `targetLang` is asked but no translator is wired, the job FAILS with a clear
error (never silently un-translated, `dub.py:146`).

---

## Pitfalls that actually bite

1. **SRT comma vs VTT dot vs ASS centiseconds.** Do not hand-format. Use the
   three `format_timestamp_*` helpers; never copy an SRT `,mmm` into a VTT/ASS
   file. `parse_timestamp` keys ms-vs-cs off the digit count — a 2-digit SRT
   fraction is silently mis-parsed as centiseconds (10× wrong).

2. **WEBVTT header MUST have a trailing blank line.** `to_vtt` emits
   `"WEBVTT\n\n"` (`subtitles.py:573`) — browsers and ffmpeg **reject** a header
   with no blank line before the first cue. Hand-edited VTT that drops it fails
   to load.

3. **ASS override injection.** Raw `{...}` in cue text are ASS override codes —
   a transcript line `{\fake}` or `{\an8}` could blank/reposition the line.
   `escape_ass_text` neutralizes braces. NOTE there are TWO escapers with
   different (intentional) encodings: `caption.py:80` maps `{`→`\{`, `}`→`\}`
   (render path); `subtitles.py:619` maps `{`→`\(`, `}`→`\)` (a brace-FREE,
   *reversible* encoding so round-trip parse restores the literal). Both escape
   `\` FIRST so they never double-process. Don't "simplify" them to one.

4. **Soft-mux codec by container.** MP4/M4V/MOV need `mov_text`; MKV/other keep
   native `ass`. Forcing `-c:s ass` into an `.mp4` makes ffmpeg refuse the mux.
   Burn-in (`-vf subtitles=`) sidesteps this but re-encodes the video.

5. **Clip time re-basing.** When captioning a clip cut from t=120 s of the
   source, cue times are against the ORIGINAL timeline. `caption.build_ass`
   subtracts `source_start` (`rebase_cue_time`, `caption.py:122`) and **skips**
   cues whose end ≤ start after re-base (they lie entirely before the clip,
   `caption.py:442`). Pass the candidate's `sourceStart` or your first caption
   shows at the wrong time / never displays.

6. **ffmpeg filter-path escaping (Windows).** Inside `-vf subtitles=`, `\`, `:`,
   and `'` are special — a `C:\...` path breaks the filtergraph.
   `_escape_filter_path` (`caption.py:461`) wraps in single quotes and escapes
   backslash-first then `:` then `'`. Always pass the ASS via this builder, never
   string-concat a Windows path into the filter.

7. **Translation count mismatch.** The dub pipeline RAISES `DubError` if the
   translator returns a different cue count (`dub.py:165`). `stack_bilingual`
   tolerates a mismatch (index-then-positional match) — pick the right tool.

8. **Offline gate.** The cloud (tier3 / `useCloud`) translate path is refused
   with a typed error when offline (`media_ops.py:122`, `_offline.guard_network`).
   Local llama (tier1/tier2) and `ctc_align` degrade offline-safe; word
   alignment returns the transcript UNCHANGED when the model asset is missing
   AND offline (`ctc_align.py:438`), never raising.

9. **RTL (Arabic/Hebrew) is NOT explicitly handled in the pipeline.** There is
   no BiDi-mark insertion or RTL normalization anywhere in `subtitles.py` /
   `caption.py` — cue text is passed through verbatim. Rendering relies on libass
   (which uses fribidi) for burn-in and on the player's BiDi for soft SRT/VTT.
   Practical consequence: `ar`/`he` translate fine (tier1), but if a downstream
   consumer doesn't run the Unicode BiDi algorithm, mixed RTL+digits/Latin can
   display reordered. If you need guaranteed RTL, verify with a burn-in (libass)
   render, not a raw-text inspection.

10. **Unknown language → hosted tier3 (needs a cloud key).** A target lang not in
    `TIER1_LANGS`/`TIER2_LANGS` routes to tier3 and will fail offline / without
    `cloudApiKey`. Check `route(lang)` before promising a local-only translation.

11. **Immutability.** `translate`, `edit`, `stack_bilingual`,
    `merge_word_times_into_transcript` all return NEW dicts. Don't expect the
    input track to change in place — read the return value.

12. **Cooperative cancel + progress.** `translate` polls `cancelled()` per cue
    and emits `progress(pct, "translated i/total")` (`subtitles.py:369`). A
    cancelled job returns the cues translated so far — partial, not empty.

---

## GPU + Hugging Face model notes

- **MT (TranslateGemma GGUF, llama.cpp):** tier1 4B `translategemma-4b-it.Q4_K_M.gguf`
  (`mradermacher/translategemma-4b-it-GGUF`, pinned commit
  `35a7486e…`, sha256 `81200d03…`, 2.55 GB) and tier2 12B
  `translategemma-12b-it.Q4_K_M.gguf` (pinned commit `fdf84c9f…`, sha256
  `b7aac4b4…`, 7.58 GB) — URLs/hashes pinned in `translation.py:74-90`. Tier2 is
  partial-offload (`TIER2_GPU_LAYERS=24`) for a 6 GB card and labelled `SLOW`.

- **Forced alignment (karaoke word timing):** default
  `MahmoudAshraf/mms-300m-1130-forced-aligner` (**CC-BY-NC-4.0**, 158-lang, fine
  for a local desktop tool; revision pinned `49402e95…`). Commercial swap →
  MIT wav2vec2 ids (`MIT_MODEL_IDS`, `ctc_align.py:108`) via
  `settings['ctcModelId']`. Romanian opt-in `gigant/romanian-wav2vec2`
  (Apache-2.0, `RO_MODEL_IDS`). Audio decoded to mono 16 kHz f32le via ffmpeg
  (`ctc_align.py:338`).

- **ASR (upstream cues):** `faster-whisper large-v3-turbo` on `cuda`/`float16`,
  with CPU fallback to model `small` / `int8` (`transcribe.py:74-82`). On Windows
  the pip-wheel CUDA DLL dirs must be registered or the first encode raises
  `cublas64_12.dll not found` (`_register_cuda_dll_dirs`, `transcribe.py:43`).
  GPU→CPU fallback surfaces a LOUD `job.progress` notice
  (`GPU_FALLBACK_NOTICE`), not silent.

---

## Worked example

Goal: take an English track, produce a Romanian translation, export Romanian SRT
+ a bilingual ASS, and verify timing preserved.

```python
from media_studio.features import subtitles
from media_studio.models import translation

# 1. Build the tiered translator (handler does this via translation.get_translator;
#    here we show the pure call). settings carries cloudApiKey/localBaseUrl etc.
tt = translation.get_translator(settings, runner=model_runner)

# route("ro") -> "tier1" (Romanian is in TIER1_LANGS) => local 4B GGUF, offline-safe.
assert translation.route("ro") == "tier1"

# 2. Translate the track (timings/indices preserved, new track, lang="ro").
ro_track = tt.translate_track(en_track, "ro",
                              progress=lambda p, m: print(p, m),
                              cancelled=lambda: False)

# 3. Verify timing preservation (cardinal correctness check).
assert [(c["start"], c["end"]) for c in ro_track["cues"]] == \
       [(c["start"], c["end"]) for c in en_track["cues"]]

# 4. Export Romanian SRT (HH:MM:SS,mmm) and a bilingual ASS.
subtitles.export(ro_track, "srt", "out/ro.srt")

bi = subtitles.stack_bilingual(en_track, ro_track, order="original-first")
subtitles.export(bi, "ass", "out/en-ro.ass")   # lang="en+ro"
```

Burn the bilingual ASS into a 9:16 clip cut from t=120 s of the source (note the
`source_start` so captions line up):

```python
from media_studio.features.caption import CaptionEngine
CaptionEngine(settings).render(
    "clip.mp4", bi["cues"], "clip_subbed.mp4",
    burn=True, width=1080, height=1920, source_start=120.0,
    total_sec=clip_seconds, on_progress=cb,
)
```

Soft-mux instead (selectable track, no re-encode) — pick `.mkv` to keep native
ASS styling, or `.mp4` to force `mov_text` (styling flattened):

```python
CaptionEngine(settings).render("clip.mp4", bi["cues"], "clip.mkv", burn=False)
```

Verification, not vibes: round-trip the exported file
(`subtitles.load("out/ro.srt")`) and assert the cue count + first/last
timestamps match `ro_track`; for RTL targets (`ar`/`he`) confirm via a burn-in
render (libass/fribidi) rather than trusting raw-text order.