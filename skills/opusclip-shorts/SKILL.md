---
name: opusclip-shorts
description: Turn a long talk/conference recording into OpusClip-style vertical (9:16) shorts with karaoke word-by-word captions — chunked ASR under the 900s MCP timeout, word-timeline merging, viral-moment selection, dedupe against an existing OpusClip set, timing-preserving caption correction, OpenCV face-tracked auto-reframe, single-layer timed color-flip ASS captions (one subtitle block, one active word), #N file naming and a chronologically ordered final list with source ranges and durations. Use when the user asks to "make shorts", "clip like OpusClip", add karaoke/captions to segments, or reconcile/dedupe/audit an existing shorts set.
---

# OpusClip-style shorts pipeline

End-to-end recipe (validated 2026-09-19 on a 93-min Romanian conference, producing 6 shorts reconciled against 44 existing OpusClip outputs). Bundled scripts: `render_final.py` (render), `merge_chunks.py` (audio split + word-timeline merge), `plan_clips.py` (anchor clip planning, OpusClip-set location, overlap audit, renumber map) (validated 2026-09-19, end-to-end).

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
UPPERCASE, extra-bold sans (**Arial Black** on Windows), white words + **exactly one active word in yellow-green #D8E235** (spoken words revert to white), thin black outline (3px) + soft shadow, lower-third (~MarginV 420 in 1080x1920), 1-4 words/line, no background box, no hook UI.
- **SINGLE-LAYER recipe (correct — validated 12/12 frames clean):** ONE Dialogue per cue,
  per-word timed color flip:
  `{	(a,a+30,\c&H35E2D8&scx106scy106)	(b,b+150,\c&HFFFFFF&scx100scy100)}WORD `
  with a/b = word start/end ms relative to event start. Color changes cannot shift layout,
  so there is always exactly ONE subtitle block.
- **ANTI-PATTERN (owner-reported defect 2026-09-19):** a white base layer + a highlighted
  overlay layer — the layers wrap differently and render as TWO stacked/duplicated subtitle
  lines. Same family: alpha-pop overlays (alpha+scale per word) — layout drift.
- Cues: split at gaps >0.65s / >3.2s / >=4 words / >26 chars.
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

## Offline whisper gotchas (measured on this box, 2026-09-19)
- Run whisper ONLY in a subprocess (bundled pattern: local_asr_worker.py). In-process:
  (1) DLL-loader deadlock risk (av imported twice), (2) decode hangs in the MCP executor thread.
- ALWAYS `stdin=subprocess.DEVNULL` for python children of an MCP server — inherited
  overlapped stdin handles from the harness exec layer block python grandchildren
  (ffprobe children are unaffected). Symptom: child hangs at zero CPU until timeout.
- CUDA is opt-in (`VE_ASR_LOCAL_DEVICE=cuda`): lazy CUDA init hangs without cuDNN DLLs.
- Validated: 40s Romanian → 33s wall, 71 words, word timestamps, quality ≥ cloud channel.

## Caption accuracy validation loop (mandatory before delivery)
1. Transcribe each RENDERED short with the strongest ASR available (online channel).
2. Time-align caption tokens vs heard words (nearest within +/-0.6s) and diff with
   normalized tokens (strip diacritics+punctuation). 3. Judge every mismatch — the
   validation ASR errs too (both runs may hear "românare" where truth is "lumânare");
   fix only true garbles as 1:1 token edits in corrections.json, then re-render.
   Verified catches: a duplicated "ale ale cărora" from an earlier bad fix, and a
   mis-reconstructed "casetofon" sentence.

## Gotchas log
- Filenames with U+2019 ' or & break bash glob/ffmpeg on Git Bash → orchestrate file handling in Python.
- Romanian „…" quotes inside Python double-quoted strings = SyntaxError; use plain text.
- `durs` lookup: OpusClip files are `#1`, not `#01`.
- ASR chunk 0 goes to default `out/transcript.json` unless `output_json` is set.
- vision: `Read` on images offloads to CDN; verify via `mcp__4_5v_mcp__analyze_image` with the returned URL.

## ASR channel choice — ASK AT INVOCATION (owner requirement)
When this skill starts, ASK the user which speech channel to use (default suggestion: online if
inside ZCode, offline otherwise). One question, then proceed:
- **online** — ByteDance Seed-ASR via the ZCode Coding-Plan entitlement (best quality, word
  timestamps, metered by the plan)
- **offline** — local faster-whisper large-v3-turbo (free, unmetered, near-SOTA, word timestamps,
  CUDA on this box)

## Online-channel audit (how it actually works — reverse-engineered 2026-09-19)
- Endpoint: `POST {ZCODE_BASE_URL}/api/v1/mcp/server/video_edit` (Streamable HTTP MCP, Z.ai origin).
- Auth: identity headers are minted by the ZCode host PER TOOL CALL and delivered in MCP
  `params._meta` under `com.zcode/official-mcp-auth` ({ok, headers} or {ok:false, reason}).
  Reasons enum: official_auth_unavailable / official_auth_plan_required / official_mcp_origin_untrusted.
  JWTs rotate mid-session; 401 must not be retried in-process (fresh headers arrive with the next call).
- Entitlement: Coding Plan ONLY — Start Plan and API-key connections are explicitly ineligible.
  No exportable key exists: `~/.zcode/v2/coding-plan-cache.json` stores only plan-eligibility status.
  => The channel is usable ONLY from inside a live ZCode session. Metering is server-side on the
  plan; there is deliberately no client-side path around it. Don't try; use offline for unmetered.

## Making online work in EVERY harness (speech-relay)
`VE_SPEECH_MCP_URL` is the designed topology for non-ZCode hosts ("credentials stay server-side").
Since the credential minter is the ZCode host itself, the relay brokers through it:
- Any harness: `python speech_relay_client.py transcribe <audio> <out.json> [--language ro]`
  (drops `~/.agents/speech-relay/queue/<id>.job.json`, polls `results/<id>.result.json`).
- PRIMARY = on-demand: after submitting jobs, ask any live ZCode agent "drain the speech
  relay queue" — it calls the host-authenticated video-edit MCP per job and writes results.
  Zero idle cost, instant when you're around.
- NO scheduled automation by default (owner preference: zero idle chatter). If a safety net
  is ever wanted: CronCreate "Speech relay safety sweep" (e.g. hourly "0 * * * *") with the
  drain prompt above — remember every tick is a visible session message, so prefer on-demand.
- **Inside ZCode, skip the queue entirely**: call speech_transcribe directly (host-authenticated,
  same latency as interactive). The queue exists for OTHER harnesses only. The offline
  provider=local channel also works everywhere with no relay at all.

## Portability & dependencies (any harness)
- Registered harness-wide as stdio MCP **`video-agent-kit`** pointing at the LOCAL PATCHED COPY
  `~/.agents/mcp-servers/video-agent-kit/` (gitignored; survives plugin-cache version bumps).
  Patch adds offline provider: `speech_transcribe(provider="local")` → faster-whisper
  large-v3-turbo (env: VE_ASR_LOCAL_MODEL / _DEVICE / _COMPUTE; VE_ASR_LOCAL=0 disables).
  `pip install faster-whisper` is the only extra dependency. Verified ✔ Connected via `claude mcp list`.
  **Subprocess architecture (measured 2026-09-19, E2E PASS):** faster_whisper is NEVER imported
  in the MCP server process (in-process import deadlocks the av DLL loader) and decode NEVER runs
  in the threaded executor (observed GIL hang, zero CPU burn); `local_asr.py` probes import and
  transcribes via `local_asr_worker.py` in plain subprocesses (worker: large-v3-turbo, cpu, int8,
  hardcoded — the _MODEL/_DEVICE/_COMPUTE env vars affect status reporting only; known gap).
  Model cached under `HF_HOME=D:\basic-memory\.hf\hub` (mobiuslabsgmbh/faster-whisper-large-v3-turbo)
  → fully offline, zero downloads. CPU-int8 timing: 6 s audio ≈ 21 s wall cold (incl. model load).
  CUDA path untested in the worker (the agents.json "CUDA" description predates the rewrite).
  Receipt: `~/.agents/mcp-servers/video-agent-kit/receipts/asr-e2e_2026-09-19.md`.
- Works everywhere with NO extra config: inspect/analyze media, shot detection, timeline
  build/validate/render, subtitle scout/build/render/QC, basic ops (all local ffmpeg).
- **Cloud speech (speech_transcribe / speech_synthesize): inside ZCode the host injects
  identity (nothing to configure). On other hosts the tools need ONE of:**
  1. `VE_SPEECH_MCP_URL` (+ optional `VE_SPEECH_MCP_TOKEN`) pointing at a remote speech MCP, or
  2. direct-backend env (`VE_SPEECH_ASR_ENDPOINT` etc. — process env only, see plugin `.env.example`).
  Without them, run the ASR step inside ZCode and carry the per-chunk `t*.json` forward —
  `merge_chunks.py merge` is harness-agnostic from there.
- Local bindeps: ffmpeg/ffprobe on PATH, python with cv2+numpy (face-tracked reframe).
- Harness tool timeouts vary (ZCode MCP: 900s) — the chunk sizes here are chosen to stay far below.
