---
name: opusclip-shorts
description: Turn a long talk/conference recording into OpusClip-style vertical (9:16) shorts with karaoke word-by-word captions — chunked ASR under the 900s MCP timeout, word-timeline merging, viral-moment selection, dedupe against an existing OpusClip set, timing-preserving caption correction, OpenCV face-tracked auto-reframe, two-layer ASS active-word captions, #N file naming and a chronologically ordered final list with source ranges and durations. Use when the user asks to "make shorts", "clip like OpusClip", add karaoke/captions to segments, or reconcile/dedupe/audit an existing shorts set.
---

# OpusClip-style shorts pipeline

End-to-end recipe (validated 2026-09-19 on a 93-min Romanian conference, producing 6 shorts reconciled against 44 existing OpusClip outputs). Reference implementation: `render_final.py` bundled next to this SKILL.md (validated 2026-09-19, end-to-end).

## 0. Preconditions
- ffmpeg/ffprobe, Python with `cv2` (OpenCV) + `numpy`, video-agent-kit MCP (`speech_transcribe`, `inspect_media`).
- **MCP calls die at 900s** — never feed a >93-min / >2GB file to a single tool call. Do everything chunked. `video_ingest` on a 2GB file times out: sample frames with `video_read_frames` / ffmpeg instead.

## 1. Inspect + identify
1. `inspect_media` → duration, fps, resolution, audio.
2. Sample ~8 frames across the timeline (`video_read_frames`, then `ffmpeg` for more) → identify event, speakers, **language** (read signs/slides). Set ASR language code accordingly (e.g. `ro`).

## 2. Word-level transcript (chunked)
1. Split audio with ffmpeg into **12-min (720s) chunks with 4s overlap** (16 kHz mono WAV):
   `ffmpeg -ss S -t D -i SRC -vn -ac 1 -ar 16000 -c:a pcm_s16le chunkI.wav` (chunk i starts at `i*720-4`).
2. `speech_transcribe` per chunk (own `output_json` each!). ~50s per 12-min chunk; run 4-6 in parallel.
3. **Merge with boundary rule:** chunk i contributes words with `end <= (i+1)*720`; chunk i+1 contributes words with `end > i*720`. A word spanning a boundary is taken from the later chunk (its copy is complete). Produces one `words.json` (`t,e,w` per word).

## 3. Select moments
- Build a readable transcript (group words at >0.9s gaps) and read it fully.
- Pick self-contained, punchy 20-70s moments (aphorisms, stories, jokes). Anchor start/end phrases, resolve to word indices (`find(phrase)` on the merged timeline), pad start −0.45s / end +0.55s, never overlapping a neighbor word.

## 4. Reconcile with an existing OpusClip set (if any)
1. Transcribe every existing short (`language=ro` etc.).
2. Locate each on the master timeline: normalized-token sliding-window match of first/last 8 words (strip diacritics for matching; threshold conf ≥0.5; fallback = middle window). **Range = first-word match start .. start + real file duration** (matched spans can be inflated by repeated phrases).
3. Audit: mutual overlaps >4s among theirs; overlaps of mine vs theirs. Drop/trim any of mine >~30% covered. Flag their internal duplicates (compilations containing other shorts).

## 5. Caption correction (timing-preserving)
Dump per-clip token ids; hand-write `corrections.json` = `{clip: {token_id: "fixed word", ...}}`. Empty string drops a filler. Only 1:1 token edits keep the karaoke map valid. Fix names (Mișkin, Quijote), garbles (radiofonul, lumânare), colloquial elisions (timpul, ceasul, veacul), drop "ă/da" fillers. Uppercase at render time.

## 6. OpusClip caption pattern (verified from real outputs)
UPPERCASE, extra-bold sans (**Arial Black** on Windows), white words + **exactly one active word in yellow-green #D8E235** (slightly scaled up, pops in/out), thin black outline (3px) + soft shadow, lower-third (~MarginV 420 in 1080×1920), 1-4 words/line, no background box, no hook UI.
- **Two-layer ASS trick**: Layer 0 = plain white line. Layer 1 = same line, each word wrapped
  `{\alpha&HFF&\fscx80\fscy80\t(a,a+70,\alpha&H00&\fscx112\fscy112)\t(a+70,a+240,\fscx100\fscy100)\t(b,b+70,\alpha&HFF&\fscx80\fscy80)}WORD`
  with `a,b` = word start/end ms relative to event. Colors: Primary/Secondary `&H0035E2D8`, white `&H00FFFFFF`. Cues: split at gaps >0.65s / >3.2s / ≥4 words / >26 chars.
- Write ASS as UTF-8 BOM (`utf-8-sig`).

## 7. Face-tracked 9:16 render
1. Track: cv2 read clip at start; Haar frontal+profile (with flipped pass for turned heads) every 12th frame at 640×360; score = area − 1.2·|dist to prev|; median-smooth ±2s; interp to per-frame; ease (deadband <25px, follow 0.06/0.02); clamp to [0, 1280−405]. Seed from one sampled frame per clip.
2. Render per clip (two chained ffmpeg processes, python in the middle):
   - p1: `ffmpeg -ss S -t D -i SRC -map 0:v -f rawvideo -pix_fmt bgr24 -` (stdout)
   - python: read exact `1280*720*3` bytes/frame (loop until full!), crop `frame[:, x:x+405]`, resize to 1080×1920 LANCZOS4, write to p2
   - p2: inputs `-f rawvideo -pix_fmt bgr24 -s 1080x1920 -r 25 -i -` **+ file for audio**; `-vf "ass=subs.ass,unsharp=5:5:0.35:3:3:0.0" -af "loudnorm=I=-16:TP=-1.5:LRA=11"`; x264 crf 19, aac 192k, `+faststart`, `-metadata language=ron`.
   - p1 "Broken pipe" at the end is expected/harmless (you stop at exactly `len(xs)` frames).
   - **The rawvideo `-s` must be 1080x1920 (post-crop), not the source size** — the #1 garbage-output bug.
3. Poster: grab frame at 45% duration.

## 8. Naming, list, QC
- Files `#N Title.mp4` where **`#N` = chronological rank of the segment's start in the full video** (user requirement: the tag itself reflects source order). When reconciling with an existing set, renumber ALL files (two-phase rename via `.tmp` to avoid collisions) and write an old→new map. Tie at equal starts → earlier end first. Titles match the existing set's language/style (English hooks like OpusClip's), underscore for ":", no apostrophes (safer).
- Final list ordered by **source start time**: `#N Title — H:MM:SS–H:MM:SS (duration in "X minutes and Y seconds" prose)`, each row tagged opusclip/new, duplicate flags. Overlap check = per-adjacent-row `min(e,prev_e) − max(s,prev_s)`, not cumulative.
- QC: ffprobe all outputs (1080×1920, dur matches); poster montage → vision check (speaker centered, one highlighted word, diacritics render, no glitch).

## Gotchas log
- Filenames with U+2019 ' or & break bash glob/ffmpeg on Git Bash → orchestrate file handling in Python.
- Romanian „…" quotes inside Python double-quoted strings = SyntaxError; use plain text.
- `durs` lookup: OpusClip files are `#1`, not `#01`.
- ASR chunk 0 goes to default `out/transcript.json` unless `output_json` is set.
- vision: `Read` on images offloads to CDN; verify via `mcp__4_5v_mcp__analyze_image` with the returned URL.
