---
title: verdict video audit + duration-based classification fix 2026-06-12
type: note
permalink: main/projects/verdict-video-audit-duration-based-classification-fix-2026-06-12
---

# verdict video audit — classification corrected (2026-06-12)

Deep-audited ALL 8142 videos (`crawler/audit_videos.py` resolve+ffprobe each, ~10min, 627s). Commit f6072b4.

## Finding: category-scoped series rule was WRONG (mislabeled 591 videos)
Long-format episodes live across MANY categories, not just AMETITE/MAFIOTI:
- VERDICT POLITIC: ~113-min interviews named per guest ("VERDICT POLITIC - MARCEL CIOLACU"), 180 long.
- VERDICT SMART RAU: median 691s (11.5min), 78% long (interviews, "VREMURILE TERORII APUSE III/IV").
- VERDICT LIFESTYLE 143 long (30%), VERDICT STIL 36 ("STILUL TAU - EPISODUL 2"), VERDICT MEDIA 146.
- Total LONG (>=300s) OUTSIDE AMETITE/MAFIOTI = 591, were wrongly 'short'.
- Same recurring short-format title can have a long outlier ("TALENTU PĂ AMETITE" median 24s but one =17.6min) → title alone mislabels; DURATION is the reliable signal.

## Duration distribution (8120 with duration)
Bimodal: <90s ~5815 (shorts), tail 90-300s, long tail 300+ ~795. p50=60s, p90=293s, p95=1021s, max=9674s (2.7h). Valley ~180-300s.

## Fix (committed)
classify: series = ANY video:vimeo with duration >= `--series-min-seconds` (default 300s/5min), grouped+numbered per category; short = shorter. Dropped --series-categories/--probe-all; probe covers all videos (cached). Bundled `crawler/video-durations.json` (8087, 233KB) seeds classification on fresh clone (no re-probe) via seed_bundled_durations(). 
RESULT (24325 items): **795 series / 7347 short / 1931 external / 13563 article / 689 other**.

## Edge cases
- 20 dead videos (empty resolver url) → recorded w/ error, not downloaded.
- 69 video:youtube → external (some real interviews; not duration-probed).
- 2-5min gray zone (~815) = short at default threshold; tunable via --series-min-seconds.
- `video-audit.json` (2.6MB raw rows) gitignored; regenerate via audit_videos.py.

## Corpus (live)
24325 items. video:vimeo 8142, article 9787, message 3776, link 1862, image 688, video:youtube 69, audio 1.