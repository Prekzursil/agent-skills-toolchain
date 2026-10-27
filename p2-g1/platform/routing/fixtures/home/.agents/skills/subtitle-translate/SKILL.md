---
name: subtitle-translate
description: "Use when translating subtitles/captions to another language and/or generating + exporting SRT/VTT/ASS for a media-studio video — including bilingual (stacked) subs and the audio-dub (TTS) path. Covers the tiered local→hosted MT engine (TranslateGemma GGUF via llama.cpp, language-aware routing +."
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

### RPC surface (what the UI actually calls)
### Recipe A — translate an existing track
### The tiered MT engine (the actual translation model)
### Bilingual (stacked) subtitles
### Recipe B — generate a track from a transcript
### Recipe C — export to SRT / VTT / ASS
### Recipe D — burn or soft-mux captions (caption.py)
### Recipe E — audio dub (TTS) path
### Pitfalls that actually bite
### GPU + Hugging Face model notes
### Worked example
### 1. Build the tiered translator (handler does this via translation.get_translator;
### here we show the pure call). settings carries cloudApiKey/localBaseUrl etc.
