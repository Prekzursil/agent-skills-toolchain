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
| 5. RRF rank fusion | MEASURED — 88 tests; 100% line+branch on the two pure modules `rank_fusion.py` + `searxng_config.py` (`searxng_regional.py` I/O shell excluded — lint+types only); 21/21 mutations killed on each (2026-07-24 figures; current figures in §7) |
| 6. Multilingual query strategy | Doctrine — `multilingual-search` skill |
| 7. Wave 1 (2026-09-02): snippet carry, diversity, default-mix flips | MEASURED for the pure modules (191 tests, 100% line+branch, 53/53 + 24/24 + 8/8 mutations killed) and for the upstream evidence behind the flips; **NOT applied live** — the flip block is rendered and parsed only, see §7 |
| 8. Wave 2 (2026-09-02): cross-encoder rerank stage, gated behind an eval | MEASURED — 124 tests, 100% line+branch on `rerank.py` + `eval_rerank.py`, 55/55 + 148/148 mutations killed; lift measured on BEIR SciFact with a real ONNX run: **-0.074 nDCG@10 on SERP-length snippets, +0.026 on full abstracts** — the stage ships DEFAULT OFF and the numbers say keep it off, see §8 |

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

## 7. Wave 1 additions — 2026-09-02 (rendered and tested; NOT applied live)

Plan items 1a, 2 and 3 of `docs/plans/2026-09-02-search-research-tools-gemhunt.md`, landed
in `tools/search-expansion/` from a cloud VM that **cannot reach the owner's instance**. The
measurement discipline above still applies, so here is what was and was not measured.

| What | State |
|---|---|
| Snippet carry into RRF (`extract_results` -> `FusedResult.snippet`, best-rank rule, 500-char cap; threaded through `query_plan.fuse_decomposed`) | MEASURED — pure; pinned by tests, incl. the best-rank tie and the "decided at the counted rank" cases |
| Post-fusion diversity `diversify()` (host cap 2 / window 10, token-Jaccard near-dup > 0.8; re-ordering only, opt-in from both fusers) | MEASURED — pure; boundary pinned (0.8 exactly is kept), score untouched, `window=0` identity, fuser defaults reproduce the old ordering (HEAD's 105 tests re-run against the new modules: 102 pass unchanged; the 3 that fail are the one `extract_results` expected dict that now also carries `snippet: ""`, and two `searxng_config` tests that asserted the block enables only the regional set — the intended Item 1a change) |
| Default-mix flips rendered in the managed block (`INDEPENDENT_ENGINES`: google off; mwmbl on; marginalia on + `inactive: false` + `api_key: public`) | MEASURED as YAML — the spliced `use_default_settings: true` file parses and the by-`name` merge replays in tests; `--dry-run` against a temp file prints the 56-line block (+1 separator line in the diff); re-run is a no-op |
| Evidence behind the flips | MEASURED from this VM — upstream `searx/settings.yml` ships `google: disabled: true` and `marginalia: disabled: true, inactive: true, api_key: None`; `api.mwmbl.org/api/v1/search/?s=` -> HTTP 200, 44 results, 0.41 s; `api2.marginalia-search.com/search` with `API-Key: public` -> **HTTP 429 "QPM Limit Exceeded" on the first request** (0.45 s); Whoogle README EOL notice dated 2026-07-24; searxng/searxng#6359 closed 2026-08-22 |
| The flips on the owner's instance | **NOT DONE.** No live `--apply`, no live `--probe`, no latency or reach numbers for mwmbl/marginalia in the default mix. The owner runs `--dry-run`, then `--apply`, then `--probe` on the box |
| `--probe` extension (walks `MANAGED_ENGINES`, `block` column, attribution-only counting, `NOT-LOADED` verdict) | Exercised against a **loopback stub** of the JSON API only. The attribution change exists because SearXNG drops an unknown `engines=` name and answers with the default mix — the old count would have reported marginalia as `WORKS n=10` before `--apply` |
| Verification | 191 tests (was 105), **100% line + branch** on `rank_fusion.py`, `searxng_config.py`, `query_plan.py`; mutation-check **53/53, 24/24, 8/8** (was 21/21, 21/21, 7/8) |

Two things worth keeping from the run. First, the mutation tool surfaced an *equivalent
mutant* in the new snippet rule (`snippet_rank.get(key, position + 1)` — any default above
`position` behaves the same), which was removed by restructuring the code rather than by a
test that would only have pinned an arbitrary constant. Second, `marginalia` is switched on
with status `rate-limited`, not `works`: the shared `public` key is spent before any
instance touches it, so expect `unresponsive_engines: [marginalia, too many requests]` and
then a suspension; the entry exists because the approved plan calls for it and because
SearXNG fails it truthfully at ~0 latency. A personal key in the spec's `extra` tuple is the
only thing that makes it contribute results. `enabled_specs()` and therefore `query_plan`
routing exclude it.

## 8. Rerank stage — 2026-09-02 (measured; ships DEFAULT OFF, and the numbers say keep it off)

Plan inventory item C / Wave 2 ("ONNX MiniLM rerank stage, gated behind a 30-50 query eval;
ships only if it lifts"), landed in `tools/search-expansion/` as `rerank.py`,
`eval_rerank.py`, `test_rerank.py` and `eval/`. Same discipline as §7: this was built on a
cloud VM that **cannot reach the owner's SearXNG**, so the eval's first stage is a stand-in,
and everything below says which side of the measured/asserted line it sits on. The package
README's "Rerank stage (optional, default OFF)" section carries the API and the full table;
`tools/search-expansion/eval/README.md` carries provenance, license and reproduction.

| What | State |
|---|---|
| The stage: cross-encoder over `title + " " + snippet` for the top 30 fused results, tail untouched; backends `onnx` / `fastembed` / `flashrank` imported lazily and probed in that order; gates `RERANK_ENABLED` (default OFF), `RERANK_MODEL_DIR`, `RERANK_ALLOW_DOWNLOAD` (default never); every failure path is identity with the reason in the result | MEASURED as code — stdlib at import; 124 tests with every backend faked via `sys.modules`; **100% line + branch** on `rerank.py` and `eval_rerank.py`; mutation-check **55/55 and 148/148** killed |
| Lift on SERP-length input: BEIR SciFact, all 300 test claims, stdlib BM25 top-30 as first stage, passages clipped to 300 chars, `Xenova/ms-marco-MiniLM-L-6-v2` int8 on onnxruntime 1.29.0 CPU | MEASURED — nDCG@10 **0.6588 -> 0.5846 (-0.0742)**, recall@5 0.7126 -> 0.6522; 59 queries improved / 84 worsened / 157 unchanged; 74 ms per query (p50 67) on 8 vCPU |
| Lift on whole documents: same 300 claims, full abstracts (mean 1,590 chars) | MEASURED — nDCG@10 **0.6588 -> 0.6845 (+0.0256)**, recall@5 0.7126 -> 0.7337; 66 / 46 / 188; 398 ms per query. Reproduces the published BEIR pair for SciFact (BM25 0.665 -> BM25+CE 0.688), which is the check that the pipeline is right and the snippet result is real |
| Break-even passage length (300 / 600 / 1000 / full chars) | MEASURED — lift -0.074 / -0.023 / +0.008 / +0.026: roughly 800-900 characters, well above `rank_fusion`'s 500-char snippet cap |
| Committed fixture `eval/scifact-50q-top30-300c.jsonl.gz` (first 50 claims by sorted qid, top-30, 300 chars, 217 KB gzipped; claims CC BY 4.0, abstracts ODC-By 1.0) + three result files | MEASURED on it: 0.6334 -> 0.5306 (-0.1028); 5 / 15 / 30. Rebuildable byte-for-byte (`build-beir`, zero gzip MTIME, ASCII rows); `eval/` totals 292 KB |
| Decision under the plan's rule (`RERANK_ENABLED=1` only if nDCG@10 lift >= +0.02) | **Leave `RERANK_ENABLED` unset.** The plan's own "medium confidence on lift for SERP snippets" resolves to *negative* lift. Worth revisiting only for a path that feeds page text (e.g. after a `read_url` extraction), re-measured on that input — the +0.026 there costs ~0.4 s per 30 candidates on CPU |
| Against the estate's real fused output (SearXNG + Exa + Tavily snippets) | **NOT MEASURED** — unreachable from here. `eval_rerank.py run <set.jsonl>` takes any set in the documented JSONL shape, so a labelled sample of real SERPs is a one-command re-measure |
| `fastembed` and `flashrank` backends against real packages | **NOT MEASURED** — faked in tests only; `auto` falls through to them when `onnxruntime`/`tokenizers` are absent |

Two things worth keeping. First, the result is a property of the *input*, not the model:
the same weights that beat BM25 on abstracts lose to it on snippets, because a 300-char
snippet gives the cross-encoder less evidence than the first stage used to rank the whole
document. Any future "add a reranker" proposal should say what text it will read. Second,
the mutation run turned up an equivalent mutant of the kind §7 recorded: flashrank's scorer
defaulted a passage the ranker dropped to `0.0`, and no default value could be told from
another by a test, so the code was restructured (map scores back by id; a dropped passage
raises, and the stage reports identity with the reason) rather than pinned.
