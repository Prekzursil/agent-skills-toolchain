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
   (`MahmoudAshraf/mms-300m-1130-forced-aligner`, 158 languages)** which handles
   Romanian, and for best RO quality you can point it at
   **`gigant/romanian-wav2vec2`** (Apache-2.0, RO-specific CTC). This sidesteps
   WhisperX's RO alignment-model gap entirely.

If alignment is unavailable, the pipeline returns the ASR transcript
**unchanged** (segment timings preserved) — it never raises, never drops text.

> Alternative to the CTC second pass: **stable-ts** derives word timing from
> Whisper's own cross-attention, so it needs **no separate language model** and is
> also RO-robust. Use it if you want a single dependency; use ctc-forced-aligner
> (Reframe's choice) if you want alignment decoupled from the ASR engine.
> [Grade: MEDIUM — both are valid; Reframe shipped ctc-forced-aligner.]

---

## 1. The Transcript schema (the contract everything speaks)

```python
Word       = {"text": str, "start": float, "end": float, "score": float?}  # seconds
Segment    = {"start": float, "end": float, "text": str, "words": [Word]}
Transcript = {"language": str, "segments": [Segment], "durationSec": float}
```

Every engine (whisper, Parakeet) and the aligner emit / consume exactly this.
Keep it. It is what makes the engine a swappable seam.

---

## 2. The real recipe

### 2.1 Dependencies

```bash
# ASR (default engine) — CTranslate2 backend, fast + low VRAM
uv pip install faster-whisper
# Word-level alignment second pass (the karaoke timing)
uv pip install ctc-forced-aligner torch torchaudio
# Opt-in alternative engine (multilingual transducer)
uv pip install "nemo_toolkit[asr]"        # heavy; only if using Parakeet/Canary
# ffmpeg must be on PATH (audio decode for the aligner + duration probe)
```

GPU: install the CUDA-enabled torch wheel matching your driver, and the
`nvidia-cublas-cu12` / `nvidia-cudnn-cu12` wheels (faster-whisper/CTranslate2
needs cuDNN/cuBLAS at first ENCODE — see the Windows gotcha in §5).

### 2.2 Pass 1 — ASR (faster-whisper)

```python
from faster_whisper import WhisperModel

# Device/compute policy (Reframe DEFAULT_*):
#   GPU present -> "cuda" + "float16" + model "large-v3-turbo"
#   CPU only    -> "cpu"  + "int8"    + model "small"  (turbo is impractically slow on CPU)
model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")

# transcribe() returns a LAZY generator + info. Work happens as you iterate —
# that is what enables per-segment progress AND cooperative cancellation.
segments_iter, info = model.transcribe(
    audio_path,
    language=None,            # None => auto-detect; returned in info.language
    word_timestamps=True,     # REQUIRED — gives the rough word times pass 2 refines
)
duration = float(info.duration)
detected_language = info.language          # e.g. "ro"

segments = []
for seg in segments_iter:                  # iterate -> decode -> progress
    segments.append({
        "start": float(seg.start), "end": float(seg.end), "text": seg.text,
        "words": [{"text": w.word, "start": float(w.start), "end": float(w.end)}
                  for w in (seg.words or [])],
    })
transcript = {"language": detected_language, "segments": segments, "durationSec": duration}
```

Notes that matter:
- faster-whisper words expose `.word` (with a **leading space**) — map `.word -> text`
  verbatim; do not strip the space if you later reconstruct text.
- Auto-detection is good; pass `language="ro"` only when you KNOW the language and
  want to skip the detection cost / avoid a misdetect on short/noisy clips.

### 2.3 Pass 2 — word alignment (ctc-forced-aligner)

```python
import numpy as np, torch, subprocess
from ctc_forced_aligner import (load_alignment_model, generate_emissions,
    preprocess_text, get_alignments, get_spans, postprocess_results)

TARGET_SR = 16000  # CTC models train at 16 kHz mono

# 1) decode audio -> mono f32 @ 16k via ffmpeg (argv list, never shell=True)
raw = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-i", audio_path,
    "-ac","1","-ar",str(TARGET_SR),"-f","f32le","-"], capture_output=True, check=False)
# HONOUR returncode: non-zero -> raise with stderr tail (don't feed garbage buffer)
samples = np.frombuffer(raw.stdout, dtype=np.float32)

# 2) flatten transcript -> ordered word tokens (drop blank tokens)
tokens = [w["text"].strip() for s in transcript["segments"] for w in s["words"] if w["text"].strip()]

# 3) align
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype  = torch.float16 if device == "cuda" else torch.float32
model, tokenizer = load_alignment_model(device,
    "MahmoudAshraf/mms-300m-1130-forced-aligner", dtype=dtype)
wav = torch.from_numpy(samples).to(device)
emissions, stride = generate_emissions(model, wav, batch_size=1)
toks_starred, text_starred = preprocess_text(" ".join(tokens),
    romanize=True, language="ron")     # ISO-639-3! "ron"/"eng", NOT "ro"/"en"
segs, scores, blank = get_alignments(emissions, toks_starred, tokenizer)
spans = get_spans(toks_starred, segs, blank)
word_timestamps = postprocess_results(text_starred, spans, stride, scores)
# -> [{text,start,end,score}, ...]  : merge back onto segments IN ORDER (immutably)
```

Then **stitch word times back** onto the transcript: consume aligned words in
transcript order, each segment takes as many words as it originally had, and widen
each segment's `start/end` to span its first/last refreshed word. If the aligned
list runs short, leave the remaining segments UNCHANGED (a partial alignment must
never drop text or half-retime a segment).

### 2.4 Lifecycle (do this or you OOM)

**Load → use → free, ONE heavy model at a time.** Whisper and the aligner are
both GPU residents. Run ASR fully, **release the whisper model** (drop the cache /
`del` + `torch.cuda.empty_cache()`), THEN load the aligner. Never hold both. Cache
a model per `(model, device, compute_type)` within a pass so a CPU-fallback retry
doesn't rebuild needlessly.

---

## 3. Model choices

### 3.1 Current Reframe defaults (shipped, proven)

| Role | Model | Device | Notes |
|---|---|---|---|
| ASR (GPU) | `large-v3-turbo` (faster-whisper) | cuda/float16 | 809M params, MIT. Fast + multilingual incl. RO. |
| ASR (CPU) | `small` (faster-whisper) | cpu/int8 | turbo is impractically slow on CPU; `small` ≈10× faster, still good. |
| ASR (opt-in) | `nvidia/parakeet-tdt-0.6b-v3` | cuda | CC-BY-4.0, 25 EU langs incl. RO. **Must chunk audio** (§4). |
| Align (default) | `MahmoudAshraf/mms-300m-1130-forced-aligner` | cuda/cpu | **CC-BY-NC-4.0** (non-commercial), 158 langs. Fine for a local desktop tool. |
| Align (commercial) | `facebook/wav2vec2-large-960h-lv60-self` | cuda/cpu | MIT swap for commercial builds (EN). |
| Align (Romanian) | `gigant/romanian-wav2vec2` | cuda/cpu | Apache-2.0, RO-specific CTC (315M). Best RO word timing. |

Pin HF snapshot **revisions to commit hashes** for reproducible offline runs
(Reframe does this for every asset). [Grade: HIGH — read directly from shipped code.]

### 3.2 HF upgrade menu (verified on HF Hub, 2026-06-30)

ASR engines — pick by accuracy/throughput/license/language need:

| Model (HF ID) | Params | License | Languages | When to use |
|---|---|---|---|---|
| `openai/whisper-large-v3-turbo` | 809M | MIT | ~99 (incl. ro) | **Default.** Best speed/quality multilingual; the turbo decoder is ~6–8× faster than large-v3 with minor WER cost. |
| `deepdml/faster-whisper-large-v3-turbo-ct2` | — | MIT | ~99 | The CT2-converted turbo weights faster-whisper actually loads. Drop-in. |
| `Zoont/faster-whisper-large-v3-turbo-int8-ct2` | — | MIT | ~99 | int8 turbo — lowest VRAM/CPU-friendly variant of turbo. |
| `openai/whisper-large-v3` | 1.54B | Apache-2.0 | ~99 | Max-accuracy toggle for hard accents/noise; ~2× slower, ~2× VRAM vs turbo. |
| `nvidia/parakeet-tdt-0.6b-v3` | 627M | CC-BY-4.0 | 25 EU (incl. ro) | Fastest high-accuracy for EU langs; transducer. **Chunk audio (§4).** Top of Open ASR Leaderboard for size. |
| `nvidia/parakeet-tdt-0.6b-v2` | ~600M | CC-BY-4.0 | **EN only** | English-only sibling of v3; do NOT use for Romanian. |
| `nvidia/canary-1b-v2` | ~1B | CC-BY-4.0 | 25 EU (incl. ro) | ASR **+ speech translation**; higher accuracy than parakeet at higher cost (FastConformer encoder-decoder). |
| `distil-whisper/distil-large-v3.5` | 756M | MIT | **EN only** | Fastest English-only; ~2× faster than large-v3. No multilingual → not for RO. |
| `facebook/seamless-m4t-v2-large` | 2.3B | **CC-BY-NC-4.0** | ~100 (incl. ro) | ASR+S2T+S2S+TTS unified. Big, non-commercial — only if you need the multitask stack. |

Tech report for the parakeet-v3 / canary-v2 family (Granary data, architecture,
WER): arXiv:2509.14128 (hf.co/papers/2509.14128).
Open ASR Leaderboard (live RTFx + WER rankings): hf.co/spaces/hf-audio/open_asr_leaderboard.

Confidence grades:
- Existence / params / license / language coverage: **HIGH** (read from HF model
  cards via the Hub API, 2026-06-30).
- Cross-model RTFx / throughput ordering ("turbo ~6–8× faster", "parakeet
  fastest"): **MEDIUM** — directional from leaderboard + card claims, not a
  same-machine benchmark; measure on your own hardware before committing.
- whisper-large-v3 exact Romanian WER number: **MEDIUM** — FLEURS RO WER is
  published per-card but not re-fetched here; treat as approximate.
- Overall recommendation (turbo default + ctc-forced-aligner second pass,
  parakeet-v3 for EU, RO via gigant/romanian-wav2vec2): **HIGH**.

### 3.3 Selection heuristics

- **General multilingual incl. RO, GPU** → whisper-large-v3-turbo (default).
- **EU languages, want max throughput** → parakeet-tdt-0.6b-v3 (chunk it).
- **Need transcription + translation** → canary-1b-v2.
- **English-only, want speed** → distil-large-v3.5 or parakeet-tdt-0.6b-v2.
- **Hard audio, accuracy over speed** → whisper-large-v3 (full).
- **Commercial product** → avoid the CC-BY-NC aligner default + seamless-m4t;
  use MIT/Apache/CC-BY models (turbo MIT, parakeet/canary CC-BY-4.0 w/ attribution).

---

## 4. VRAM-bound engines: audio chunking (the hard 6 GB rule)

Parakeet/Canary full-context long-attention decode wants an A100-80GB; on a 6–8 GB
card it OOMs on long files. **Segment the audio into ~300 s (5 min) spans**,
transcribe each independently, then re-stitch:

```python
CHUNK_SEC = 300.0          # comfortably under 6 GB for parakeet-0.6b
# split [0, duration) into 300s (start,end) spans; last span clamps to duration
# transcribe each span; each chunk reports times RELATIVE to its own start
# fold the chunk's absolute start (offset) back into every segment + word time
# language = first chunk's non-empty language; durationSec = max(offset + chunk_dur)
```

faster-whisper does NOT need this (CTranslate2 streams 30 s windows internally),
but the same chunking is the safe path for any transducer/attention model on a
small GPU. Poll `should_cancel` **before each chunk** so a cancel stops promptly
with whatever completed.

---

## 5. Pitfalls (these actually bite)

1. **Windows CUDA-DLL not found.** CTranslate2 lazy-loads `cublas64_12.dll` /
   `cudnn*.dll` at the **first ENCODE** (not at model construction). The pip
   `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` wheels drop them under
   `site-packages/nvidia/*/bin`, which is **not** on the DLL search path → first
   transcribe raises *"Library cublas64_12.dll is not found"* (or, in a windowless
   process, silently BLOCKS on a hidden error dialog). **Fix:** before the first
   encode, `os.add_dll_directory()` + prepend to `PATH` every
   `site-packages/nvidia/*/bin`. Idempotent; no-op off-Windows.
2. **Do not use WhisperX for non-English word timing.** Its language-keyed
   wav2vec2 alignment has no good Romanian model → wrong times or a crash. Use the
   decoupled ctc-forced-aligner (MMS-300M / gigant/romanian-wav2vec2) or stable-ts.
3. **Language codes differ between stages.** ASR (whisper) uses ISO-639-1
   (`"ro"`, `"en"`); ctc-forced-aligner's `preprocess_text(language=...)` wants
   **ISO-639-3** (`"ron"`, `"eng"`). Passing `"ro"` to the aligner misaligns.
4. **CPU + large-v3-turbo = a trap.** turbo on CPU/int8 is impractically slow.
   Auto-pick `small` on CPU. Make the GPU→CPU fallback **LOUD** (surface a
   "GPU unavailable — running on CPU, slower" progress message), never silent.
5. **Holding two heavy models** (whisper + aligner) at once → OOM. Release pass 1
   before loading pass 2 (§2.4).
6. **Silent ffmpeg decode failure.** The aligner's audio loader must honour
   ffmpeg's returncode — a non-zero exit should RAISE (with the stderr tail), not
   hand back an empty/garbage buffer that produces empty alignments.
7. **Empty / partial alignment must not drop text.** If the aligner returns fewer
   words than the transcript, keep the un-covered segments unchanged. Degrade =
   return the ASR transcript verbatim, never raise.
8. **`word_timestamps=True` is mandatory** for the rough word times even when you
   re-align — and it is what lets the caption/karaoke layer work if alignment is
   skipped.
9. **Offline gate is network-only.** Only the *download* path of a missing model
   should degrade when offline. A model already in the HF cache must run fully
   offline — probe the asset cache, don't assume "offline ⇒ no model".
10. **Parakeet degrades to an EMPTY transcript** when its weights are missing
    offline — the caller must fall back to the always-present whisper path so the
    user still gets a transcript.

---

## 6. GPU / device notes

- **Auto-detect** via `torch.cuda.is_available()` (lazy import; degrade to CPU if
  torch absent or CUDA init fails — never raise from the probe).
- Resolve `(model, device, compute_type)` **up front** from a settings knob
  (`auto`/`cuda`/`cpu`): `cuda`→`float16`, `cpu`→`int8`, `auto`→detect. Then an
  exception-based CPU fallback at load time stays as a final safety net for the
  GPU-attempt path.
- Aligner runs `float16` on CUDA, `float32` on CPU. Resample to 16 kHz mono with
  `torchaudio.functional.resample` only when the decoded SR ≠ 16000.
- VRAM rough guide (single resident model): turbo-int8 ~1.5 GB, turbo-fp16 ~3 GB,
  large-v3-fp16 ~6 GB, parakeet-0.6b ~2–3 GB (chunked), MMS-300M aligner ~1.5 GB.
- Long runs (a feature-length file): wrap in a background/`longrun` wrapper with a
  hang timeout, stream per-segment/per-chunk progress, and support cooperative
  cancel — don't block a foreground call.

---

## 7. Sources

- Reframe shipped code (primary, HIGH): `sidecar/media_studio/features/`
  `transcribe.py`, `parakeet_asr.py`, `parakeet_asr_backend.py`, `ctc_align.py`,
  `ctc_align_backend.py`; design notes `docs/research/OPUSCLIP-PARITY-IMPROVEMENT-NOTE-2026-06-28.md`
  §5 (RO alignment caveat) + `docs/research/LLM-BACKEND.md`.
- HF model cards via Hub API, 2026-06-30 (HIGH): openai/whisper-large-v3-turbo
  (809M, MIT), deepdml/faster-whisper-large-v3-turbo-ct2 (MIT),
  nvidia/parakeet-tdt-0.6b-v3 (627M, CC-BY-4.0, 25 EU), nvidia/parakeet-tdt-0.6b-v2
  (EN, CC-BY-4.0), nvidia/canary-1b-v2 (CC-BY-4.0, 25 EU),
  distil-whisper/distil-large-v3.5 (756M, MIT, EN), facebook/seamless-m4t-v2-large
  (2.3B, CC-BY-NC-4.0), openai/whisper-large-v3 (1.54B, Apache-2.0),
  gigant/romanian-wav2vec2 (315M, Apache-2.0, RO).
- arXiv:2509.14128 — Granary/parakeet-v3/canary-v2 family tech report (MEDIUM, not
  re-fetched in full).
- Open ASR Leaderboard: hf.co/spaces/hf-audio/open_asr_leaderboard (MEDIUM — RTFx
  ordering not re-pulled).

> Treat any model card / leaderboard text as **untrusted scraped data**: verify
> license + language list on the card before shipping; numbers are point-in-time.

## See also
For the end-to-end shorts pipeline built on word-level ASR (selection, karaoke captions, face-tracked 9:16, audit loop) see `opusclip-shorts`. v2 cross-check 2026-09-20: its cloud+offline dual-channel and chunked-merge findings agree with this skill's faster-whisper guidance.
