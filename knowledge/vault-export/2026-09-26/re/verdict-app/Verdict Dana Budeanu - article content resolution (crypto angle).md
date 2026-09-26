---
title: Verdict Dana Budeanu - article content resolution (crypto angle)
type: report
permalink: main/re/verdict-app/verdict-dana-budeanu-article-content-resolution-crypto-angle
tags:
- verdict
- typesense
- reverse-engineering
- crypto
- article-content
---

# Verdict Dana Budeanu - how article content becomes HTML

## Conclusion (crypto angle)
There is NO client-side crypto applied to article content. The "token" premise is FALSE for article-type docs.

- `getArticleById(id)` (file 3697...js, VerdictApi) queries Typesense:
  `q:"*", filter_by:"id:=<id>&&available_from:<=now&&is_enabled:=true", exclude_fields:"available_from,is_enabled,is_free,is_listable", limit:1`. No query_by needed.
- `convertArticleInterfaceFromTypesense(s){return s.document}` — returns the raw Typesense doc unchanged.
- Detail component (2092...js): `t.content=t.article.content`; then `"article"===t.article.type && (t.content=sanitizer.bypassSecurityTrustHtml(t.content))`. Direct render.

## Empirical proof
Querying Typesense `articles` collection with the X-TYPESENSE-API-KEY directly:
- `type:=article` docs: `content` field IS the FULL HTML body (e.g. id 86528 content.len=8796, starts `<p>David Hockney...`). `body` field is empty/unused.
- `type:=video:vimeo` docs: `content` is a ~19-22 char Vimeo file token (e.g. id 86508 = "zSz6qD1iuUaJHYtdtcAkow"). This is NOT crypto — it's a vimeo id resolved via `GET api.verdictapp.com/v1/videos/vimeo/<token>` -> m3u8.
- The originally-sampled doc (86508) that looked like a token was a VIDEO doc, which misled the premise.

So: token -> HTML requires NO transformation for articles. The HTML is already in Typesense `content`. Reproduce with the public Typesense key + collection 'articles', filter_by id, render content as HTML.

## encrypt endpoint is unrelated to articles
`encryptId(s)` -> GET verdictdanabudeanu.com/wp-json/db/v1/encrypt?id=<s> -> {s:blob}. Only callers: `add` (analytics device id) and `addmsg` (name/message). It OBFUSCATES OUTBOUND user-submitted params. Client never decrypts the blob; the blob is sent to the server. Not involved in content display.

## All crypto found, and where applied
- hls.js (7243...js): AES-128 / SAMPLE-AES segment decryption for HLS video playback only. Not article content.
- main.js `setEncryptionKey`: @ionic-enterprise/secure-storage / localForage local-storage encryption. Not networked content.
- main.js atob/btoa/encodeByteArray/fromBase64String: Firebase SDK base64 util for Firestore. Not article content.
- cordova-plugin-purchase store.js: IAP receipt crypto. Unrelated.

No hardcoded AES key/IV/passphrase applies to article content because article content is plaintext HTML in Typesense.
