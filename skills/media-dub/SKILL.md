---
name: media-dub
description: Use when producing a local DUB of a video - re-voicing speech into another language (or restyling it same-language) while KEEPING the original speaker's voice, fully offline. Safe-ship engine is Chatterbox-Multilingual (Resemble AI, MIT, 23-lang zero-shot clone); rides media_studio (ASR, CTC word-alignment, ffmpeg atempo duration-fit, ducking, mux). NOT for pure TTS (use speech).
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
                   sourceLang, segments, license, notices}
```

A long job: returns `{jobId}` immediately, streams `job.progress`, and the final
`job.done.result` carries the output path + the license receipt.

- `targetLang` (required) — ISO-639-1 (e.g. `es`, `de`, `ja`).
- `engine` — `chatterbox` (default, safe) | `indextts2` (gated).
- `lipsync` — `latentsync` (gated) | omit.
- `posture` — `personal` (default; local/non-commercial) | `commercial`.
- `allowGated` — owner opt-in to keep a gated engine under a commercial posture.
- `bgPath` — an optional music/ambient bed ducked UNDER the new VO.

## Pipeline (ride the bus)

1. **ASR** — `transcribe_fn(in_path, settings)` -> §3 `Transcript`
   (`{language, durationSec, segments:[{start,end,text,words?,speaker?}]}`).
2. **align** *(optional)* — `align_fn(transcript)` refines word timings via
   `ctc_align`; a miss degrades to segment timings (never raises).
3. **translate** *(optional)* — `translate_fn(text, targetLang, sourceLang)` per
   segment; ABSENT -> `target_text = source_text` (same-language voice re-read).
4. **synthesize** — `synth_fn(text, lang, speaker, target_sec, engine, out_path)`
   -> `(wav_path, synth_sec)`. Chatterbox clones the source speaker and speaks the
   target text. `target_sec` is a duration HINT the native engine (IndexTTS2)
   honors; the timestretch path fits afterward.
5. **duration-fit** — land each clip in its source slot:
   - `timestretch` (Chatterbox-only, SAFE): `atempo_factor(synth_sec, slot_sec)`
     = `synth_sec / slot_sec`, clamped to `[0.5, 2.0]`; `build_atempo_chain`
     decomposes a factor outside `[0.5, 2.0]` into in-range stages (a single
     `atempo` is linear only in that range). A factor within `±0.02` of 1.0 is
     left untouched (no needless re-encode).
   - `native` (IndexTTS2, GATED): trust the synth duration (the engine already
     hit the target) — better quality, no time-stretch artifacts.
6. **assemble** — `build_vo_timeline_argv` places every fitted clip at its source
   start on ONE full-length VO track: a silent `anullsrc` base of `durationSec`,
   each clip `adelay`-ed to its start (ms, stereo), all summed with
   `amix=...:normalize=0` (nothing auto-attenuated).
7. **duck + mux** — `build_dub_mux_argv` stream-copies the source VIDEO
   (`-map 0:v -c:v copy`) and rebuilds the audio: the VO is `loudnorm`-ed to the
   target LUFS; with a `bgPath` the bed is ducked under the VO via
   `sidechaincompress` keyed off the VO (the exact `audiomix` convention).
8. **lip-sync** *(optional, GATED)* — LatentSync re-renders the mouth to match the
   dub. Commercial embed gated on `dub-license`.

## License gate — SHADOW mode (the crux)

`Chatterbox-Multilingual is MIT` -> commercial-safe, the DEFAULT, always admitted.
`IndexTTS2` and `LatentSync` weights are **not confirmed commercial-safe** -> a
commercial embed routes to the **`dub-license`** needsDecision.

`DubLicenseGate.evaluate(requested, posture)` is **advisory (SHADOW)**:
- it is PURE and NEVER raises, blocks, or nags;
- it returns a `LicenseVerdict` (`admitted` / `gated` / `needsDecision` /
  `decisionId="dub-license"`) and LOGS it to a bounded, injected `shadow_log`
  sink (production points this at a separate auto-rotating sink — never the main
  event ledger, per C5(iii));
- `personal` posture admits every engine (local/non-commercial use of the gated
  weights is unrestricted); `commercial` posture flags the gated engines.

`build_dub_plan` uses the verdict only to pick a DEFAULT: under `commercial`
WITHOUT `allowGated` a gated engine is downgraded to Chatterbox + timestretch and
a notice is recorded — the gate never forces this, the plan just defaults safe.
With `allowGated` the owner's choice is honored and the needsDecision is STILL
recorded for them. This is "observe + log, never block."

## Chatterbox's 23 languages

`ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh`
(verify against the Resemble AI model card at wire time). A target outside this
set emits a LOUD notice (never a silent wrong-language dub). **Romanian (`ro`) is
NOT in the set** — Parakeet can ASR it, but Chatterbox cannot yet synthesize it.

## Assets to install (follow-on, out of the single-file build)

- `chatterbox-multilingual` (MIT) — the safe-ship TTS weights + the
  `dub_backend.RealChatterboxSynth` loader (the heavy `synth_fn` seam).
- `indextts2` / `latentsync` — install ONLY after the `dub-license` decision
  resolves them for a commercial embed.

## Pitfalls that actually bite

- **argv-list only, never `shell=True`** — the filter graph + paths are single
  argv elements (CONTRACTS discipline).
- **`atempo` linear range** — one `atempo` only works in `[0.5, 2.0]`; always go
  through `build_atempo_chain` for larger stretches or you get an ffmpeg error.
- **Don't strip the original background** — the safe ship REPLACES the speech with
  the dub VO and optionally ducks a provided bed under it; separating the original
  speaker's voice from music (source separation) is a heavier, separate step — do
  not claim it's done here.
- **Slot overflow** — if a translation is much longer than its slot the clamp to
  2.0x leaves the clip slightly overrunning the next; the fit notice surfaces it.
  Prefer IndexTTS2 native fit (once licensed) for tight lip timing.
- **Shadow sink must never break the dub** — `_observe` swallows a sink failure;
  a logging outage can't fail a render.

## When NOT to use

- Pure narration with no source voice to clone -> `speech`.
- Muxing an already-finished dub/VO track -> `audio-extract-mix`.
- Transcription / subtitles only -> `transcribe` / `caption-burn`.
- Trimming dead air / silence -> `silence-trim`.

## See also
For re-voicing SHORTS produced by `opusclip-shorts` (or long talks before clipping), chain: `opusclip-shorts` (clip+captions) -> this skill (dub) -> re-burn captions.
