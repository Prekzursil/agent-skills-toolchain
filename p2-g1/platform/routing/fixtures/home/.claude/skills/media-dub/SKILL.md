---
name: media-dub
description: >-
  Use when producing a local DUB of a video — re-voicing the speech into another
  language (or restyling it in the same language) while KEEPING the original
  speaker's voice, fully offline. The safe-ship engine is Chatterbox-Multilingual
  (Resemble AI, MIT, 23-language zero-shot voice clone); the pipeline rides the
  existing media_studio substrate (Parakeet/whisper ASR -> CTC word-alignment ->
  ffmpeg `atempo` duration-fit -> `sidechaincompress` ducking -> mux). Covers the
  `dub.start` RPC, the ASR->translate->synth->fit->assemble->duck+mux stages, the
  per-segment `atempo` time-stretch that lands each clip in its source slot, the
  full-length VO track assembled with `adelay`+`amix`, and the LICENSE gate: an
  optional IndexTTS2 native-duration-control engine and an optional LatentSync
  lip-sync are COMMERCIAL-embed-gated on the `dub-license` needsDecision — the
  gate runs in SHADOW mode (observe + log, never blocks), and a commercial build
  defaults to Chatterbox-only unless the owner explicitly opts in (`allowGated`).
  Do NOT use for: pure TTS narration with no source voice to clone (use the
  `speech` skill); muxing an ALREADY-finished dub track (use audio-extract-mix);
  transcription/subtitle generation only (use transcribe/caption); or lip-sync
  without a dub. Source of truth: media_studio/features/dub.py.
---

# media-dub — local voice-clone dubbing (Chatterbox safe ship)

Distilled from the REAL implementation. Cite these when in doubt:

- `media_studio/features/dub.py` — the whole feature: the `dub.start` RPC, the
  `DubLicenseGate` (SHADOW), `build_dub_plan`, the `atempo` fit, the VO-timeline
  and duck/mux argv builders, and `run_dub_pipeline` (the end-to-end orchestrator).
- Substrate it RIDES (do not reinvent) — from the media_studio package
  (`sidecar/media_studio/features/` in the Reframe checkout):
  - `transcribe.py` / `parakeet_asr.py` — ASR to the §3 `Transcript` schema.
  - `ctc_align.py` — karaoke-grade word-timing refinement (optional 2nd pass).
  - `audiomix.py` — the `sidechaincompress` -> `amix` -> `loudnorm` duck/mux graph
    (`build_mix_filter`); the dub mux uses the identical convention + labels.

Evidence: gem-hunt MASTER **E.3** — "Local dubbing stack — biggest missing flagship
feature: Chatterbox-Multilingual (MIT, 23-lang clone) + IndexTTS2 duration-control
+ optional LatentSync lip-sync; the whole substrate (Parakeet+CTC+ducking+mux)
exists. *[verify IndexTTS2 weights license before commercial embed; Chatterbox
alone is the safe ship.]*" · COUNCIL **C5** (risk-tiered SHADOW ladder — a
heuristic/nagging/blocking gate ships observe-and-log FIRST).

## Wire surface (NET-NEW)

```
dub.start({videoId|path, targetLang, sourceLang?, engine?, durationFit?,
           lipsync?, posture?, allowGated?, bgPath?})
    -> {jobId} -> {path, engine, durationFit, lipsync, targetLang,

### Pipeline (ride the bus)
### License gate — SHADOW mode (the crux)
### Chatterbox's 23 languages
### Assets to install (follow-on, out of the single-file build)
### Pitfalls that actually bite
### When NOT to use
