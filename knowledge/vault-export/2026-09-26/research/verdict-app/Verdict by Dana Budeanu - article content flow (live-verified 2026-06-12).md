---
title: Verdict by Dana Budeanu - article content flow (live-verified 2026-06-12)
type: report
permalink: main/research/verdict-app/verdict-by-dana-budeanu-article-content-flow-live-verified-2026-06-12
tags:
- verdict
- typesense
- reverse-engineering
- content-flow
---

# Verdict (Dana Budeanu) Ionic/Angular app — article body resolution

Live adversarial verification, 2026-06-12.

## Confirmed
- Typesense host `1spr94q6vkeyhabjp-1.a1.typesense.net` (443), key `n81mQFYG9wUPwGqpdT7SJC3LWQ8Gmee1` (header `X-TYPESENSE-API-KEY`), collection `articles` (24362 docs). No login.
- For `type:"article"` docs the displayed HTML body IS the Typesense `content` field, verbatim plaintext HTML. NO token->HTML transform, no decrypt, no CDN-by-token. IDENTITY.
- The `body` field also carries the SAME full HTML for article docs (premise that body is always empty is WRONG; body==content modulo trivial whitespace/entity diffs). Either field works.
- The ~22-char token only appears on non-article docs (video:vimeo/video:youtube/link) where `content` = media id / URL. e.g. id 86508 type video:vimeo content="zSz6qD1iuUaJHYtdtcAkow"==meta.video_id.

## Premium
- `is_premium` is present in docs but is NOT a filterable Typesense field (filter_by errors). Filter by `type` instead.
- Premium does NOT gate/strip text content server-side: the 3 premium article-type docs returned full HTML.
- BUT premium content is almost entirely VIDEO. In first 10000 docs: premium = 567 video:vimeo + 2 video:youtube + 1 article. ZERO premium articles have >800 chars of real text. Real paywalled value = the video, resolved via `GET https://api.verdictapp.com/v1/videos/vimeo/<content>` with UA `getDanaForApp` -> {url: dyntube .m3u8}. That API DOES require the UA.

## Embargo guard is real
- `available_from:<=NOW && is_enabled:=true` is a genuine server-side filter. Articles scheduled for later (status "future", available_from in future) are excluded WITH the guard but content still returns WITHOUT it. 9785 articles currently available.

## encrypt endpoint = unrelated
- `GET verdictdanabudeanu.com/wp-json/db/v1/encrypt?id=X` returns randomized-IV blobs (non-deterministic across calls). Write-only obfuscator for /add /addmsg device-id params, NOT a content-decrypt path.

## Working recipe (free + premium identical)
curl -s -G '.../collections/articles/documents/search' -H 'X-TYPESENSE-API-KEY: ...' \
  --data-urlencode 'q=*' --data-urlencode 'filter_by=id:=<ID>&&available_from:<=<NOW_MS>&&is_enabled:=true' \
  --data-urlencode 'exclude_fields=available_from,is_enabled,is_free,is_listable' --data-urlencode 'limit=1'
-> .hits[0].document.content == article HTML (for type=article). NEVER exclude `content`.
- Verified free 86516 (7614 chars readable RO HTML "Unde au dispărut adolescenții?...") and premium 47570 (390 chars full).
