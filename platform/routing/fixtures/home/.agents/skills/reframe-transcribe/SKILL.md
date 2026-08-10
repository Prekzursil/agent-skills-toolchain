---
name: reframe-transcribe
description: "Use when transcribing speech from audio/video to text with WORD-LEVEL timing (for captions, karaoke subtitles, clip-boundary snapping, or diarization). The proven local pipeline is faster-whisper (large-v3-turbo on GPU / small on CPU) for the transcript, then a SEPARATE ctc-forced-aligner second."
---

# Transcribe (speech to timed text)

Goal: turn an audio/video file into a **Transcript** — language + segments +
**per-word `{text, start, end}`** — that is accurate, correctly timed at the word
level, and degrades loudly (never silently) when a GPU or model is missing.

This skill distills the **real, shipped** pipeline from Reframe
(`sidecar/media_studio/features/transcribe.py`, `parakeet_asr.py`,
`ctc_align.py` + their `_backend.py` siblings) plus current Hugging Face model
options. The architecture is deliberately **two passes**, and the single most
important design decision is *why it is not WhisperX*.

---

## 0. The headline decision: two passes, NOT WhisperX

WhisperX = faster-whisper + a bundled forced-alignment stage + optional pyannote.
Its alignment stage loads a **language-specific wav2vec2** model keyed by the
detected language. That is the trap:

- **Romanian (and many non-EN languages) have no good/any bundled wav2vec2
  alignment model in WhisperX's map** → it either falls back to a wrong model,
  produces garbage word times, or crashes outright on the missing key.
- It couples ASR and alignment, so you cannot swap ASR engines independently.

**Reframe's fix (adopt this):** keep ASR and alignment as **two independent
seams**:

1. **ASR pass** → faster-whisper (default) or Parakeet (opt-in) → segment + rough
   word times in the `Transcript` schema.
2. **Alignment pass** → a *separate* `ctc-forced-aligner` (MahmoudAshraf) call
   that re-derives word boundaries. Its **default model is MMS-300M

### 1. The Transcript schema (the contract everything speaks)
### 2. The real recipe
### 2.1 Dependencies
### ASR (default engine) — CTranslate2 backend, fast + low VRAM
### Word-level alignment second pass (the karaoke timing)
### Opt-in alternative engine (multilingual transducer)
### ffmpeg must be on PATH (audio decode for the aligner + duration probe)
### 2.2 Pass 1 — ASR (faster-whisper)
### Device/compute policy (Reframe DEFAULT_*):
### GPU present -> "cuda" + "float16" + model "large-v3-turbo"
### CPU only    -> "cpu"  + "int8"    + model "small"  (turbo is impractically slow on CPU)
### transcribe() returns a LAZY generator + info. Work happens as you iterate —
