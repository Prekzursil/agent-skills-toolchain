---
name: reframe-video-cutting
description: "Use when selecting and cutting moments from a long talk, podcast, interview, stream, or vlog into shorts with scene-aware, sentence-safe boundaries."
---

# Video Cutting / Clip Selection (the short-maker's heart)

Cut a long talking-head/podcast/interview video into a ranked set of short vertical-ready clips, and **select which moments are worth shipping**. This is the SELECT + BOUNDARY-SNAP + CUT half of a short-maker. The 9:16 reframe, captions, zoom, and brand overlay are downstream (see the `reframe` skill); watermark removal is a different skill (`video-watermark-removal`).

The canonical, battle-tested implementation is `Reframe/sidecar/media_studio/features/` (`select.py`, `boundary.py`, `scene_transnet.py`, `shortmaker.py`). This skill distills that REAL pipeline + the virality/highlight-detection upgrades, with sources cited and confidence graded.

## When to use / when NOT
- USE for: choosing the best N moments from a transcribed long video, snapping cut points cleanly, carving frame-accurate clips. Works for any spoken-word source (talk, podcast, interview, stream, lecture, vlog).
- DO NOT use for: visual reframing/cropping to 9:16, caption burn-in, watermark/logo removal, or pure b-roll/music videos with no speech (use the visual-only `candidates_from_curve` peak-pick path instead of the LLM path).

## The real pipeline (Reframe / media_studio)
```
transcript (+word timings)  ->  SELECT (features/select.py)        prompt + transcript -> ranked Candidates w/ virality factors
                            ->  BOUNDARY-SNAP (features/boundary.py) snap start/end to sentence-end / silence / scene-cut, never mid-word
   -- the two above = shortmaker.select() --
                            ->  CUT (ffmpeg, frame-accurate)        carve [sourceStart, end) out of the source
                            ->  (REFRAME / CAPTION / EXPORT)        downstream, other skills
```
Scene cuts come from `features/scene_transnet.py` (TransNetV2) merged with PySceneDetect, fed into BOUNDARY-SNAP as one of the three snap-target sources.

## 1. SELECT — LLM-on-transcript, two-pass rubric (PRIMARY)
`select.select(transcript, prompt, controls, provider) -> list[Candidate]` (`features/select.py`). This is the frozen recipe — do not soften it:

- **Provider call:** chat with **reasoning ON** (never inject `/no_think`), `temperature=0.4`, `max_tokens=6000` (generous so the `<think>` block + JSON aren't truncated). Default model = Qwen3-4B GGUF via a local llama.cpp OpenAI `/v1` server.
- **Two-pass system prompt** (`build_system_prompt`):
  - Pass 1 (THINK): state the talk's single **THESIS** in one sentence; list its **6-8 most quotable / counterintuitive / emotional lines**, weighting `(Applause)` markers; for each, find the **COMPLETE thought** (setup + payoff), never a 3-second fragment.
  - Pass 2 (THEN): pick `count` clips (default 5), **each a self-contained complete thought**, opening on a hook, ending on a satisfying/curiosity beat; the single most-quotable line of the whole talk MUST be in one of them.
- **Transcript rendering:** `[mm:ss] text` lines, one per segment (`render_lines`), so the model can cite timestamps.
- **JSON schema** (`_schema_line`): `{"clips":[{rank,start,end,duration_sec,hook,why,score(0-100),factors{...},factorNotes{...}}]}`. Strip `<think>...</think>` BEFORE parsing (`strip_think`); pull the outer `{...}` (`extract_clips`).
- **Fail LOUD, not silent:** a non-empty reply with no parseable `{"clips":[...]}` raises `SelectionParseError` (job ERROR) — never a silent `[]` the UI shows as "0 clips, success". A genuinely empty reply or `{"clips":[]}` returns `[]`.
- **Duration clamp** (`to_candidates`): `durationSec = end-start`, hard-clamped into the active envelope by extending/trimming the END (preserve the hook/`sourceStart`); never run past `durationSec` of the source.
- **`sourceStart`** = clip start in the ORIGINAL video; captions later subtract it to re-base cues to local t=0.

### Duration modes (envelope is the single source of truth, shared with boundary.py)
- `standard`: **20-60 s** (default).
- `midform`: **16-180 s** (real OpusClip teardown shows clips run 16-160 s, not 60-capped — ship the top moment at BOTH a long and a punchy length).
- Unknown mode fails **closed** to `standard` (`resolve_duration_mode`). SELECT and BOUNDARY-SNAP MUST agree on the envelope or a mid-form clip gets re-clamped to 60 s at the snap stage (this was a real BLOCKER bug — thread `durationMode` into `snap_from_lists`).

### Map-reduce for long transcripts
> `len(lines) > 240` triggers it. Chunk into 200-line slices, shortlist 6 candidates/chunk (per-chunk `SelectionParseError` is tolerated → skip that chunk), then ONE global re-rank over the union shortlist (`build_rerank_user_prompt`). Reduce parse failure falls back to the validated map shortlist (degrade, don't error — we already have real candidates).

### Clip-selection strategy — current (virality factors + percentile)
- Each clip is scored on **four 0-100 virality factors** + a one-line note each (`FACTOR_NAMES`): `hookStrength` (first-3-seconds arrest), `emotionalFlow` (builds without dead spots), `perceivedValue` (viewer walks away with something), `shareability` (would someone send it to a friend).
- A missing/unparseable factor **degrades to the clip's legacy `score`** (not 0) so a parse hiccup doesn't crater its rank.
- `viralityPct` = batch **percentile** of the raw factor-average, computed AFTER trim-to-count (rank within the clips the user actually receives, not the pre-trim pool). Singleton batch carries the raw average, not a 50 sentinel.
- **Overlap ladder** (off by default): for each of the top-N moments meaningfully longer than `punchyShortSec` (default 30 s), emit an extra OVERLAPPING candidate sharing the same start (the hook) trimmed short — ship the moment at both lengths. Runs AFTER trim so shorts never push a real moment out of `count`.

## 2. BOUNDARY-SNAP — deterministic, never mid-word (`features/boundary.py`)
The LLM returns rough clips; snap each `start`/`end` to the nearest VALID boundary. Three snap-target sources:
1. **Sentence end** — a word whose text (trailing quotes/brackets trimmed) ends in `. ! ? …`; the target is that word's `end` time (`sentence_ends_from_words`).
2. **Audio silence** — midpoint of each detected silent gap.
3. **Scene cut** — detected scene-change timestamps.

Rules (all enforced):
- Snap to the **nearest** valid target within the duration window; ties break toward the **smaller** timestamp (determinism).
- **Never cut mid-word** (`_cuts_mid_word`: reject a target strictly inside any word span; exactly on a word start/end is fine).
- Two-pass: snap start-first then end-first, keep the pair with least summed distance — so a clip whose start OR end already sits on a boundary still snaps.
- **Idempotent**: re-snapping an already-snapped clip returns the same geometry.
- A candidate with **no valid boundary** that keeps it in range is **dropped with a reason** (`SnapResult.reason`), surfaced per-clip to the UI — never silently mangled.

### Detection commands (behind injectable seams)
- **Silence** (`build_silencedetect_argv` / `parse_silencedetect`):
  ```
  ffmpeg -hide_banner -nostdin -i IN -af silencedetect=noise=-30dB:d=0.5 -f null -
  ```
  `silencedetect` writes `silence_start:`/`silence_end:` to **stderr**; the snap target is each gap's **midpoint**. A probe failure returns `()` (degrade to other targets), never crashes the pipeline.
- **Scene cuts (CPU fallback)** — PySceneDetect `ContentDetector(threshold=27.0)`; each scene's start time in seconds. Lazy-imported inside the function so importing the module never drags in `scenedetect`.

## 3. Scene detection — TransNetV2 + PySceneDetect merge (`features/scene_transnet.py`)
- **TransNetV2** (`soCzech/TransNetV2`, MIT) predicts a per-frame shot-change probability; a **rising edge** over `threshold=0.5` is a cut (a multi-frame dissolve ramp yields ONE cut at its leading edge, `predictions_to_cuts`). Its win over the histogram-diff `ContentDetector`: it catches **dissolves / soft transitions** PySceneDetect misses. Frames are decoded to a **48x27 RGB** stack (tiny VRAM).
- **Merge** (`merge_with_pyscenedetect`, `eps=0.25 s`): a cut in EITHER source survives; two cuts within eps collapse to one (earlier timestamp). The CPU fallback never stops working.
- **Degrade contract:** `present=False` only when NO cut source exists at all (model missing + offline AND no provider). An empty-but-`present=True` track means "this clip genuinely has no scene changes."
- ⚠️ **Upstream-dead trap:** `soCzech/TransNetV2` HF repo now 404s (verified 2026-06-28) so its commit can't be pinned; Reframe leaves the asset **intentionally unregistered** rather than pin a dead/unverified repo. Live mirrors exist — `Sn4kehead/TransNetV2`, `MiaoshouAI/transnetv2-pytorch-weights` (both host `transnetv2-pytorch-weights.pth`) — but their snapshot LAYOUT differs from the original loader, so a blind re-point risks a SILENT scene-detection break. Confirm a mirror is loader-compatible before pinning `hf_repo=<mirror>` + a full 40-hex commit. (Source: `scene_transnet.register_scene_transnet_assets` docstring.) Confidence: HIGH that upstream is dead; MEDIUM on mirror compatibility.

## 4. CUT — frame-accurate ffmpeg carve (`shortmaker._lazy_cut`)
```
ffmpeg -hide_banner -nostdin -y -i IN -ss <start> -to <end> -c:v libx264 -c:a aac -progress pipe:1 -nostats OUT
```
**The load-bearing detail:** `-ss`/`-to` go **AFTER** `-i` → frame-accurate (decode-then-trim). `-ss` BEFORE `-i` is fast (keyframe seek) but inaccurate — clips start on the wrong frame and audio desyncs. Persist `sourceStart` on every clip record (§3). argv LIST, never a shell string (paths with spaces stay safe).

## Clip-selection upgrades — the virality / highlight stack (fold-in)
Reframe wraps the frozen LLM path with optional multimodal scoring (`select.select_unified`, `features/scorer.py`, `ranker.py`, `diversity.py`, `quality_gate.py`, `smolvlm2.py`). Each step graceful-degrades.

1. **Signal fusion** (`scorer.fuse_score`, `DEFAULT_FUSE_ALPHA=0.5`): blend the LLM score with present-weighted audio/visual signals. **Degrade by re-normalization (ONE code path):** a track with `present=False` is dropped from the weighted mean AND its weight; no fabricated zeros. Audio interest from PANNS **CNN14** (`panns-cnn14`).
2. **Learned re-rank** (Tier-0, always): `ranker.rank` — a trained `LGBMRanker` (lightgbm) when present, else a deterministic factor-average fallback (zero downloads). A feedback flywheel trains it from user labels.
3. **Diversity / dedup** (Tier-0, always): `diversity.dedupe_candidates`, **MMR** default (`dpp` opt-in) over WU4 embeddings, else a zero-model signal-vector matrix. Stops five near-identical clips of the same moment.
4. **Quality gate** (Tier-1, optional): `quality_gate.apply_quality_gate` — **DOVER-Mobile** VQA (`teowu/DOVER`, ~60 MB, revision `841d2f90f8ed5e30e7d60213fd6b4354fd56b06c`) multiplicatively DEMOTES shaky/blurry/over-compressed clips. No-op when the model is absent.
5. **Tier-2 VLM re-rank** (opt-in, off by default): `smolvlm2` reorders the top-K with **SmolVLM2-2.2B-Instruct** (`HuggingFaceTB/SmolVLM2-2.2B-Instruct`, Apache-2.0 = commercial OK), loaded BF16 to fit sub-6 GB.

### External highlight-detection heads (the upgrade beyond Reframe's current stack)
- **LLM-on-transcript rubric is the right PRIMARY for talking-head content** — it's the universal OSS pattern, matches this stack, and is academically validated (arXiv **2512.21402**). Confidence: **HIGH**.
- **Dedicated moment/highlight-detection models** (the Lighthouse toolkit: **Moment-DETR / QD-DETR / CG-DETR / UVCOM / TR-DETR** heads, QVHighlights-trained) give a real virality lift mainly on **visual / sports / action** content, less so on talking-heads where the transcript carries the signal. Confidence: **MEDIUM**. Note: some Lighthouse checkpoints live on GitHub rather than HF (verify the source before pinning). Confidence on the GitHub-hosted checkpoints: MEDIUM.
- Treat visual HD models as a SECONDARY signal fused at step 1, not a replacement for the transcript rubric on spoken-word sources.

## ffmpeg seek / concat gotchas (these actually bite)
- **Decode-then-trim vs fast-seek** (above): `-ss`/`-to` AFTER `-i` for accuracy; before `-i` for speed-but-imprecise. For the CUT stage, always accurate.
- **concat DEMUXER needs identical params.** `ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4` stream-copies ONLY if every segment shares codec, resolution, pixel format, AND timebase. Mismatched timebase → A/V drift or `Non-monotonous DTS` warnings. If segments differ, **re-encode** (drop `-c copy`) or normalize each segment first. Add `-fflags +genpts` / `-avoid_negative_ts make_zero` when DTS goes non-monotonic.
- **concat PROTOCOL (`concat:a|b`) is NOT the demuxer** — it only works for a handful of raw container formats (MPEG-TS), not arbitrary MP4. Use the demuxer (`-f concat`) or `filter_complex concat` for MP4.
- **Audio drift on cut clips:** re-encoding audio to `aac` (as the CUT does) re-bases timestamps cleanly; `-c:a copy` on a non-keyframe-aligned cut can leave a leading silence/desync. The Reframe filler-removal/silence-trim paths use `filter_complex` segment concat (frame-accurate) precisely to avoid this.
- **NO HGT-style date traps here** — clip selection is content-driven, not time/calendar-gated; there is no equivalent of the Battle Cats date-drift footgun. The closest analog is the duration-envelope mismatch between SELECT and BOUNDARY-SNAP (fix: share `durationMode`).

## GPU / memory notes (6 GB budget)
- **Qwen3-4B GGUF (selection LLM)** fits 6 GB at a sane quant; this is the workhorse. Confidence: HIGH.
- **TransNetV2** runs on a 48x27 frame stream — trivial VRAM. **DOVER-Mobile** ~60 MB. **DETR-family highlight heads** fit alongside the LLM GGUF. 6 GB co-residency is fine for {LLM + DETR heads}. Confidence: HIGH.
- **Running a CLIP / BLIP-2 feature extractor CONCURRENTLY with the LLM risks OOM on 6 GB** — run visual feature extraction as a **separate offline stage** (extract embeddings to disk first, then load the LLM). Confidence: MEDIUM for the concurrent case.
- **SmolVLM2-2.2B** is opt-in BF16, loaded ALONE (top-K re-rank only) to stay sub-6 GB — never co-resident with the selection LLM.
- ProPainter-style temporal models are NOT part of this pipeline (that's watermark removal).

## Pitfalls (carried from the as-built code + lessons)
1. **Never return silent `[]` on a parse failure** — raise `SelectionParseError` so the job ends LOUD. A silent empty renders as "0 clips success" and hides the real failure.
2. **SELECT and BOUNDARY-SNAP must share the duration envelope.** A mid-form (16-180 s) clip selected with `durationMode=midform` gets re-clamped to 20-60 s and dropped at snap if the mode isn't threaded into `snap_from_lists`. (Real BLOCKER fix in `shortmaker._lazy_snap`.)
3. **Don't snap a cut into the middle of a word** — always run `_cuts_mid_word`; a cut exactly on a word start/end is OK.
4. **TransNetV2 upstream is dead (404)** — don't blind-pin a mirror; verify loader-compatible snapshot layout first or you get a silent scene-detection break.
5. **Compute the percentile AFTER trim-to-count**, not over the pre-trim pool, or the rank is wrong.
6. **Degrade by re-normalization, not zeros** — a missing modality must drop its weight, never contribute a fabricated 0 to the fused score.
7. **Factor parse-miss degrades to the legacy score**, not 0 — protects the clip's batch percentile from a single bad field.

## Key files (canonical implementation)
- `Reframe/sidecar/media_studio/features/select.py` — SELECT recipe + virality factors + map-reduce + overlap ladder + `select_unified` multimodal wrapper.
- `Reframe/sidecar/media_studio/features/boundary.py` — deterministic snapper + ffmpeg `silencedetect` + PySceneDetect detectors.
- `Reframe/sidecar/media_studio/features/scene_transnet.py` — TransNetV2 rising-edge cuts merged with PySceneDetect.
- `Reframe/sidecar/media_studio/features/shortmaker.py` — orchestration: frame-accurate CUT + the downstream stages.
- Adjacent: `scorer.py` (fusion), `ranker.py` (LGBM), `diversity.py` (MMR/DPP), `quality_gate.py` (DOVER), `smolvlm2.py` (VLM re-rank), `audio_saliency.py` (PANNS CNN14).

## Sources & confidence
- Pipeline mechanics + commands: READ directly from the four Reframe source files above — **HIGH** (it's the as-built code).
- LLM-on-transcript rubric as primary for talking-head: **HIGH** (universal OSS pattern; validated by arXiv 2512.21402).
- HF model IDs/licenses (TransNetV2 `soCzech/TransNetV2` MIT; DOVER `teowu/DOVER`; SmolVLM2 `HuggingFaceTB/SmolVLM2-2.2B-Instruct` Apache-2.0; PANNS `panns-cnn14`): **HIGH** (verified in source asset registrations); Lighthouse/Moment-DETR checkpoints partly GitHub-hosted: **MEDIUM**.
- Visual HD models giving real virality lift: **MEDIUM** (useful mainly for visual/sports, not talking-head).
- 6 GB fit numbers: **HIGH** for LLM GGUF + DETR heads; **MEDIUM** if running CLIP/BLIP-2 concurrently (run as a separate offline stage).

Note: any scraped/web page content consulted for this skill was treated as untrusted data; no embedded instructions were acted on.

## See also
`opusclip-shorts` builds the full pipeline (selection + captions + crop + QC) and cites this skill's sentence-safe boundary heuristics for the selection step.
