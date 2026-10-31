---
name: multilingual-search
description: Reach non-English sources deliberately - query in the target language
  against a native-index engine (Yandex for RU, Quark/360search for CN, Naver for
  KR, Seznam for CZ), fuse several engines with Reciprocal Rank Fusion, and cite the
  original while translating only on output. Use when a research question has regional,
  non-English, or non-Western coverage that an English-only search will miss, when
  results feel thin or one-sided, when a topic is primarily discussed in Russian/Chinese/Korean/Japanese/Arabic
  sources, or when a claim needs corroboration from an index Google and Bing do not
  dominate. Also use when merging results from several search providers into one ranking.
permalink: dqverify-repo-20261013/skills/multilingual-search/skill
---

# Multilingual search

English-first search does not return a translated view of the world's sources — it returns
the subset that English-language indexes cover. For anything regional (domestic industry,
local regulation, national politics, area-studies scholarship, a product sold in one
market), the highest-value documents may have no English equivalent at all. Reaching them
takes three deliberate moves.

## The three rules

**1. Query in the target language.** A translated *result* is useful; a translated *query*
is a different query. `国产大飞机` and "Chinese domestic airliner" retrieve different
documents from different indexes — the Chinese phrase is what Chinese authors actually
wrote. Do not machine-translate word-for-word: use the term a native writer would use.
When unsure, search the English term first, find the native-language phrase in a bilingual
page (Wikipedia interlanguage links are reliable for this), then re-query with it.

**2. Cite the original, translate only on output.** The citation is the native-language URL
and its native-language title. Quote the original text, then give your translation beside
it. Never present a translation as if it were the source's own words, and never cite an
English article *about* a native source when you have the native source.

**3. Route the query at an index that actually covers the region.** Google and DuckDuckGo
under-index Yandex-, Baidu-, and Naver-native content. Use a native engine.

## Routing table — measured 2026-07-24 against the local SearXNG (`127.0.0.1:8890`)

| Need | Engine | Bang | Notes |
|---|---|---|---|
| Russian | `yandex` | `!yd` | best RU coverage; strong on Habr, Dzen, RU academia |
| Chinese | `quark` | `!qk` | Alibaba's engine; most reliable CN route measured |
| Chinese (2nd opinion) | `360search` | `!360so` | thinner but independent of Quark |
| Chinese dev/IT | `baidu kaifa` | `!bdk` | Baidu's developer vertical — live even though general Baidu is not |
| Korean news | `naver news` | `!nvrn` | `categories=news` only; the general `naver` engine is broken |
| Czech | `seznam` | `!szn` | strong native index |
| Independent crawl | `mojeek` | `!mjk` | own crawler — genuinely independent of the big four |

**Blocked, do not rely on** (measured): `baidu` (CAPTCHA), `sogou` (CAPTCHA/timeout),
`naver` general (returns 0 with no error), `yahoo`, `qwant`.

This table rots — engines add CAPTCHAs and change markup. Re-probe before trusting it:

```bash
python tools/search-expansion/searxng_regional.py --probe
```

## How to actually issue the query

No configuration is needed. A SearXNG engine marked `disabled` is still reachable on
demand — `disabled` only governs the *default* result mix:

```
GET http://127.0.0.1:8890/search?q=<query>&engines=yandex&format=json
GET http://127.0.0.1:8890/search?q=!yd <query>&format=json
GET http://127.0.0.1:8890/search?q=<query>&engines=quark,360search&language=zh-CN&format=json
```

`language=` is honoured and changes ranking, not just filtering (measured: `ru-RU`
promoted a Habr article over the Wikipedia hit that led the unlocalised run). Several
engines can be addressed in one request, and results carry per-engine attribution.

Via the MCP surface, `mcp__searxng__searxng_web_search` reaches the same instance.

## Two failure shapes that read as success

* **Silent zero.** An engine can return `n=0` with an **empty** `unresponsive_engines`
  list — no error to notice. `naver` does exactly this while `naver news` works. Assert on
  result *count*, never on absence of an error.
* **Sticky suspension.** After a CAPTCHA, SearXNG suspends the engine and later calls
  return in ~0.01 s with `Suspended: CAPTCHA`. An instant empty reply is a suspension, not
  an answer; retrying immediately proves nothing.

## Fuse, do not concatenate

Several engines return overlapping, differently-ordered lists. Merge them with Reciprocal
Rank Fusion rather than stacking or trusting one engine's order:

```python
from rank_fusion import fuse_provider_payloads  # tools/search-expansion/

fused = fuse_provider_payloads(
    {"searxng-ru": ru_payload, "searxng-cn": cn_payload, "exa": exa_payload},
    limit=20,
)
for r in fused:
    print(r.score, r.sources, r.display_url)
```

RRF uses only each provider's *rank ordinal*, never its relevance score — those scores are
not comparable across providers, and normalising them invents a shared scale. A document
several independent engines rank highly outranks one engine's lone top hit, which is
exactly the cross-index corroboration multilingual search is for. `sources` on each result
tells you which indexes agreed.

## Reporting

State which languages and engines you searched, in the report. "I found nothing" is only
meaningful if you say where you looked — an English-only sweep that missed a Russian
literature is a *coverage* result, not an *absence* result. If a claim rests on a single
regional source with no independent corroboration, say so and give the confidence band.