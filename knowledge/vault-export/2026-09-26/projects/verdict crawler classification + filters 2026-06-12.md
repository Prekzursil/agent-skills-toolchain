---
title: verdict crawler classification + filters 2026-06-12
type: note
permalink: main/projects/verdict-crawler-classification-filters-2026-06-12
---

# verdict crawler — classification & filters (2026-06-12)

`crawler/crawl_verdict_content.py` enhanced + live-verified. Commit 15f8730.

## Classification (the key insight)
Category alone is INSUFFICIENT: VERDICT AMETITE / VERDICT MAFIOTI contain BOTH long-format episodes AND shorts. Split is by **VIDEO DURATION** (ffprobe on the resolved HLS playlist, ~1s, cached in state.json["durations"][video_id]).
- `series` = video:vimeo in a series category (default AMETITE/MAFIOTI, `--series-categories`) with duration >= `--series-min-seconds` (default 300s).
- `short` = any other video:vimeo.
- `external` = link / video:youtube. `article` = article/message. `other` = image/audio/unknown.
- Verified live: "AMETITELE DOMNISOARE DE ONOARE"=12.6min/"AMETITELE BFF"=7.0min/"MAFIOTII PĂ DONAT SANGE"=6.1min → series; "AMETITELE CA N FILME"=47s / "TALENTU PĂ AMETITE"=54s → short.
- Probing scoped to series categories (~1341 videos) by default; `--probe-all` probes everything, `--no-probe` skips.

## Other features
- Series numbered 1..N per category by created:asc → `media/series/<Cat>/<NNN> - <title>.mp4`. catalog.json groups series(ordered)/shorts/articles/external/duplicates.
- Dedup: video_id (videos) + content sha1 (articles) → `duplicate_of`, skip re-download. Persisted in state.
- Rich record: title (in-app name), created/available_from/updated (ms+ISO), author, category, duration_seconds, video_id.
- Filters compose: `--classes --types --categories --author --exclude-shorts --exclude-external --favorites-file --limit`. `--list` = corpus breakdown.
- `--favorites-file` = JSON array of ids (favorites are device-local; export from device IndexedDB).

## Corpus facts (live)
24,324 items. Types: article 9786, video:vimeo 8142, message 3776, link 1862, image 688, video:youtube 69. Categories (8 on-screen): VERDICT MEDIA 7411, VERDICT SMART RAU 5396, VA RUPEM PE GENUNCHI 3776, VERDICT LIFESTYLE 2071, VERDICT POLITIC 1951, VA FI BINE 1299, VERDICT AMETITE 861, VERDICT MAFIOTI 841, VERDICT STIL 422, FATALAUL ZILEI 296. Authors: Dana Budeanu 19230, Paul Hitter 2298, Vlad Mitric Ciupe 1222.

## Typesense gotchas
export endpoint blocked for search key; cluster rejects parenthesised filter groups (`(type:=a||...)`) → filter type/category client-side; sort_by=created works; deep pagination past 10k works.