---
title: verdict article content = plaintext HTML in Typesense (CORRECTION) 2026-06-12
type: note
permalink: main/projects/verdict-article-content-plaintext-html-in-typesense-correction-2026-06-12
---

# Verdict article body resolution — CORRECTED + live-verified (2026-06-12)

**Earlier notes were WRONG** about a "content token / encrypted content / Firestore-gated bodies." A multi-agent spike (wf_e203a546) + adversarial live verification corrected it:

## Truth: there is NO token, NO decryption, NO secondary fetch for article bodies
- For Typesense docs with **`type:"article"`**, the **`content` field IS the full ready-to-render HTML** (verbatim; `body===content`). The app does `bypassSecurityTrustHtml(content)` — a trust marker, NOT decryption.
- The "~22-char token" (e.g. `zSz6qD1iuUaJHYtdtcAkow`) was a misread: it only appears on **`type:"video:vimeo"/"video:youtube"/"link"`** docs, where `content` = a media id / URL (e.g. dyntube video id), not ciphertext.
- `getArticleById` does NOT exclude `content` → returns full body. The LIST/search methods use `exclude_fields:"...,content"` → that's why earlier ad-hoc queries saw content stripped or hit a video doc.

## Recipe to get any article's plaintext HTML (client-side only, NO login)
- Typesense: host `1spr94q6vkeyhabjp-1.a1.typesense.net`, key `n81mQFYG9wUPwGqpdT7SJC3LWQ8Gmee1` (header `X-TYPESENSE-API-KEY`), collection `articles`.
- Detail query (app's exact): `q=*`, `filter_by=id:=<ID> && available_from:<=<now_ms> && is_enabled:=true`, `limit=1`, exclude_fields=`available_from,is_enabled,is_free,is_listable` (content NOT excluded) → `hits[0].document.content` = HTML.
- UA `getDanaForApp` only matters for verdictdanabudeanu.com/wp-json + app.verdictapp.com (NOT needed for Typesense; NOT used for bodies). The wp-json `db/v1/encrypt` blob is only id/message obfuscation for addmsg/add telemetry.

## Premium = fully open (UNLOCK IS REAL server-side)
Live-confirmed: free article id 86516 (7614 chars HTML) AND **premium** id 47570 (full HTML, NOT gated). `is_premium` does NOT strip/gate text server-side; client `if(!1&&...)` paywall is dead code. So a new frontend renders premium bodies with the same single unauthenticated Typesense query.

## Impact
The one flagged blocker for the new React frontend is NOT a blocker — article rendering is trivial (Typesense search → render content as HTML). Video docs: `content`=media id → dyntube `api.verdictapp.com/v1/videos/vimeo/<id>` → m3u8. Whole verdict-app-v2 plan de-risked.