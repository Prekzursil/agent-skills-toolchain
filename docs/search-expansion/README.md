---
title: README
type: note
permalink: dqverify-repo-20261013/docs/search-expansion/readme
---

# Search expansion — multilingual / multi-engine reach + rank fusion

A general harness capability: make research **reach further** — into RU / CN / KR / regional
sources — and then **fuse** what several engines return into one defensible ranking.

> **Measurement discipline.** §1–§4 were measured against the owner's LIVE SearXNG on
> 2026-07-24 and the numbers below are real tool output, not estimates. Engine
> reachability is drift-prone (scrapers break, sites add CAPTCHAs), so §2 ships the
> re-probe command: a stale table should be *detectable*, not believed. Anything not
> measured is tagged `UNVERIFIED` inline with the experiment that would settle it.

COVERAGE — measured vs. asserted:

| Section | State |
|---|---|
| 1. Live instance detection | MEASURED |
| 2. Regional engine reachability | MEASURED — per engine, both states, two independent probes |
| 3. Enablement: apply / verify / revert | MEASURED — full cycle exercised on the live instance |
| 4. Reach-vs-latency trade-off | MEASURED |
| 5. RRF rank fusion | MEASURED — 88 tests; 100% line+branch on the two pure modules `rank_fusion.py` + `searxng_config.py` (`searxng_regional.py` I/O shell excluded — lint+types only); 21/21 mutations killed on each |
| 6. Multilingual query strategy | Doctrine — `multilingual-search` skill |

**Final state of the owner's instance: UNCHANGED.** The config change was applied, measured,
and reverted. `D:\searxng\settings.yml` is byte-identical to as-found
(SHA-256 `52D77372…651A8`, 826 bytes), verified after the revert. One backup file
(`settings.yml.bak-20260723T222730Z`) was left behind by the tool; it is safe to delete.

---

## 1. The live instance (measured)

| Fact | Value | How measured |
|---|---|---|
| Runtime | Docker container `searxng` | `docker ps` |
| Version | `2026.6.29+e535e4c61` | `GET /config` → `.version` |
| Bind address | `127.0.0.1:8890` → container `8080` | `docker ps` port map |
| Config source | **`D:\searxng`** bind-mounted at `/etc/searxng` | `docker inspect searxng` `.Mounts` |
| Settings file | `D:\searxng\settings.yml` (26 lines, `use_default_settings: true`) | direct read |
| Engines compiled in | **276** | `GET /config` → `len(.engines)` |
| JSON API | enabled (`formats: [html, json]`), limiter off | settings + live `format=json` calls |

## 2. Regional reachability — measured, both states

**Both-states design.** A probe that cannot distinguish "engine off" from "engine broken"
measures nothing, so each engine was queried twice: **State A** (plain query, no routing —
the regional engine should contribute nothing) and **State B** (same query routed at that
engine). State A behaved as predicted (`{'duckduckgo': 10}` for a Russian query — zero
regional engines) and a `duckduckgo` control returned 10 in state B, so the detector fires.

The table was then reproduced by a **second, mechanically independent probe** — the shipped
`--probe` CLI, written separately from the ad-hoc script. Both agree: 7/12 working, same
classification for all 12.

### 2a. Headline finding — no config change is needed for ad-hoc regional search

> **A `disabled` SearXNG engine is still reachable on demand.** `disabled` governs whether an
> engine joins the *default* mix — it does **not** gate explicit selection. Measured:
> `yandex` ships `enabled: False`, yet both `engines=yandex` and the `!yd` bang returned
> **10 results each**, identical top hit, `unresponsive_engines: []`.

```
GET /search?q=<query>&engines=yandex&format=json     # explicit engine list
GET /search?q=!yd <query>&format=json                # bang shortcut
```

So the §3 config change is **not** what unlocks regional search. It buys only default-mix
membership — at a latency cost (§4).

### 2b. Per-engine verdict

| Engine | Bang | Region | Result | Detail |
|---|---|---|---|---|
| `yandex` | `!yd` | RU | **WORKS** — 10 | best RU coverage |
| `quark` | `!qk` | CN | **WORKS** — 9–12 | Alibaba's engine; most reliable CN route |
| `360search` | `!360so` | CN | **WORKS** — 5–7 | thinner, but independent of Quark |
| `baidu kaifa` | `!bdk` | CN | **WORKS** — 10 | Baidu's *dev* vertical — live though general Baidu is not |
| `naver news` | `!nvrn` | KR | **WORKS** — 10 | same-day Korean news |
| `seznam` | `!szn` | CZ | **WORKS** — 10 | strong Czech index |
| `mojeek` | `!mjk` | independent | **WORKS** — 10 | own crawler — genuinely independent signal |
| `baidu` | `!bd` | CN | **BLOCKED** | `CAPTCHA` → sticky `Suspended: CAPTCHA` |
| `sogou` | — | CN | **BLOCKED** | `timeout`, then `CAPTCHA` |
| `naver` (general) | `!nvr` | KR | **SILENT-FAIL** | `n=0`, `unresponsive_engines: []` |
| `yahoo` | `!yh` | — | **BROKEN** | `HTTP protocol error` |
| `qwant` | — | FR | **BROKEN** | `access denied` |

**Two failure shapes that mislead differently.**

*Sticky suspension.* After Baidu returned `CAPTCHA`, the next call came back in **0.01 s**
with `Suspended: CAPTCHA` — SearXNG short-circuits a failing engine instead of re-hitting
it. An instantly-empty reply is a suspension, not an answer; retrying proves nothing.

*Silent zero.* `naver` returned `n=0` with an **empty** `unresponsive_engines` list — no
error to notice. Its `naver news` sibling returned 10 on the same instance seconds later,
which rules out "Naver is down" and points at parser drift. **Consequence:
`unresponsive_engines: []` is not proof an engine worked. Assert on result count.**

### 2c. Multi-engine fan-out and locale

One request can address several engines, with per-engine attribution:

```
engines=quark,360search,duckduckgo  ->  n=25  {'duckduckgo': 10, 'quark': 11, '360search': 4}
engines=yandex,duckduckgo,google    ->  n=19  {'duckduckgo': 10, 'yandex': 10}
```

The second row matters: 10 + 10 attributions across **19** results — SearXNG merged one URL
both engines returned. SearXNG already fuses *within* one instance; the RRF module (§5)
fuses one level up, **across providers** (SearXNG vs Exa vs Tavily vs Firecrawl), which
SearXNG cannot see.

`language=` is honoured and changes *ranking*, not just filtering: `квантовые вычисления`
at `language=ru-RU` promoted a Habr article over the Wikipedia hit that led the unlocalised
run. `zh-CN` and `all` also behaved.

## 3. Enabling by default — reversible, and actually exercised

Ad-hoc use needs nothing (§2a). Use this only for default-mix membership.

```bash
python tools/search-expansion/searxng_regional.py --probe     # live reachability
python tools/search-expansion/searxng_regional.py --dry-run   # print the diff, change nothing
python tools/search-expansion/searxng_regional.py --apply     # backup->splice->validate->restart->verify
python tools/search-expansion/searxng_regional.py --revert    # restore newest backup->restart
```

The full cycle was run against the live instance, not just described:

| Step | Measured outcome |
|---|---|
| `--dry-run` | printed the 43-line diff; file hash + size unchanged (826 B) |
| `--apply` | backup written; block spliced; container restarted; **instance came back healthy (HTTP 200)** |
| verify | default RU query went from **10 results to 64** (§4) |
| `--revert` | restored from backup; `health OK`; hash back to `52D77372…651A8`, 826 B |
| verify | default RU query back to `{'duckduckgo': 10, 'startpage': 10}` |

That the instance **started** with the block is itself the evidence that
`use_default_settings: true` merges a partial engine list by name — a malformed or
misunderstood override would have failed startup.

**A real defect this exercise caught.** The first `--apply` crashed with
`http.client.RemoteDisconnected`: a container mid-restart *accepts* the TCP connection then
closes it without replying, and `RemoteDisconnected` is **not** a `urllib.error.URLError`.
The too-narrow `except` let it escape and killed the caller **before its rollback could
run** — precisely the failure the rollback exists to prevent. Fixed by widening to
`(OSError, http.client.HTTPException, TimeoutError)`, and verified both-states: the same
restart window that produced the traceback now prints `health OK` and exits 0. Had this
been asserted rather than executed, a broken safety net would have shipped looking correct.

Safety properties: markers make re-apply a true no-op; `--apply` **refuses** if
`settings.yml` already has its own top-level `engines:` key (a duplicate YAML key would
break the instance); the spliced YAML is re-parsed before writing; and a failed health
check auto-restores the backup.

## 4. What enabling actually buys — and costs

| Query | Default mix, block OFF | Default mix, block ON |
|---|---|---|
| `реактивный двигатель` (RU) | **10** — `{duckduckgo}` | **64** — `+yandex, seznam, quark, 360search, brave, startpage` |
| `国产大飞机 C919` (CN) | **16** — `{duckduckgo, startpage}` | **83** — `+mojeek, yandex, seznam, quark, 360search` |
| `반도체 수출` (KR) | — | **69** — `+yandex, quark, 360search` |

Latency, same instance, block ON:

| Query | Wall clock |
|---|---|
| plain English, 3 runs | 4.65 s / 3.24 s / 2.94 s |
| Russian, 2 runs | 7.10 s / 3.41 s |

Baseline before the change was ~1 s. **So the trade is roughly 3–6× reach for roughly 3×
latency on every default query.** That is a good trade for research and a poor one for
casual lookups — which is why the instance was left OFF: the `!bang` route already delivers
the reach on demand at no standing cost.

**Category caveat (measured, easy to get wrong):** enabling an engine adds it to *its own
categories*, not to every search. `yandex`, `quark`, `360search`, `seznam`, `mojeek` are
`general` engines and appear in a default search. `naver news` is a **news** engine and
`baidu kaifa` an **it** engine — they were absent from the general queries above and only
appeared under `categories=news` (10 results) and `categories=it` (10 results).

## 5. RRF — fusing several engines into one ranking

`tools/search-expansion/rank_fusion.py`. Pure functions, **stdlib only**, no ML, rank-only.

RRF (Cormack et al., SIGIR 2009) scores a document as `sum over lists of 1 / (k + rank)`,
`k = 60`. It uses only *rank position*, never a provider's own relevance score — Exa's
score, Tavily's and SearXNG's come from different models over different corpora and are not
comparable; normalising them manufactures a shared scale that never existed, and the fused
order would then track whichever provider had the widest spread. Rank ordinals *are*
comparable.

Handles the provider shapes (`results` / `data` / `data.web` / bare list / list of URL
strings), dedups by normalised URL (scheme/host case, `www.`, default port, tracking params
including `utm_*`, `yclid`, `spm`, trailing slash, fragment), and returns a fused ranking
with per-result provenance (`sources`, `ranks`).

**Verification.** 88 tests, **100% line + branch** on both pure modules, run on Python
3.11.9 (the CI interpreter) against the committed LF blob.

Coverage only proves lines ran, so the suites were also mutation-checked with the repo's
existing `mutation-check` tool (`.agents/skills/mutation-check/`) rather than a hand-rolled
one — **21/21 killed on `rank_fusion.py`, 21/21 on `searxng_config.py`**. That choice
mattered: a hand-written mutation set of 8 targeted anchors reported a clean 8/8, and the
generic set then found **three** behaviours it had missed.

Three genuine defects/gaps were caught by actually running things rather than asserting
they worked:

1. **`apply_block` was not idempotent** — it grew the settings file by one blank line on
   every re-apply, because `remove_block` leaves the separator newline behind. Caught by
   the idempotency test; fixed by collapsing trailing newlines before appending.
2. **The `inside = False` reset after `END_MARKER` was unasserted** in both `remove_block`
   and `find_top_level_key`. Every test happened to put the managed block at EOF. Had the
   block ever been followed by other content, `remove_block` would have **silently deleted
   everything after it** — data loss in the owner's `settings.yml` — and the duplicate-key
   guard would have stopped looking. The code was correct; the tests could not tell.
3. **`keep_blank_values=True` was unasserted** in `normalize_url` — dropping it would merge
   `?q=&id=7` with `?id=7`, two different requests and potentially two different pages.

## 6. Multilingual strategy

See the `multilingual-search` skill: query in the target language, cite the original,
translate only on output. A translated *query* is a different query — `国产大飞机` and
"Chinese domestic airliner" retrieve different documents from different indexes. The skill
carries the routing table, the two failure shapes, and the citation contract.