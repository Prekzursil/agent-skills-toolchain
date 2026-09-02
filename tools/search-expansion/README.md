# tools/search-expansion

Three pure modules and one I/O shell behind one small, dependency-free package:

| File | What it is | Gated |
|---|---|---|
| `rank_fusion.py` | Reciprocal Rank Fusion across search providers, snippet carry, opt-in post-fusion diversity (host cap + near-dup demotion). Pure functions, stdlib only. | 100% line+branch |
| `searxng_config.py` | Pure `settings.yml` transform: the managed block that enables SearXNG's regional engines and carries the default-mix flips (google off, mwmbl + marginalia on). | 100% line+branch |
| `query_plan.py` | Decompose -> translate -> re-dedup planning sibling; reuses `reciprocal_rank_fusion` for the dedup. | 100% line+branch |
| `searxng_regional.py` | Thin CLI shell: live probe, backup, container restart, health check. | lint only |

`searxng_regional.py` is deliberately outside the coverage gate: it is I/O against a live
Docker container, and a mocked-to-100% shell would assert against the mocks rather than
the behaviour. Its decision logic was pushed down into `searxng_config.py`, which *is*
gated. The CLI paths were exercised live instead — see `docs/search-expansion/README.md`
for the measured runs, including a real defect the exercise caught.

## Rank fusion

```python
from rank_fusion import fuse_provider_payloads, reciprocal_rank_fusion

fused = fuse_provider_payloads(
    {"searxng": searxng_json, "exa": exa_json, "tavily": tavily_json},
    k=60,        # the RRF paper's damping constant
    limit=20,
    max_per_host=2,          # opt-in diversity (both knobs default to None = off)
    near_dup_threshold=0.8,
)
for r in fused:
    print(f"{r.score:.5f}  {r.sources}  {r.display_url}  {r.snippet[:60]!r}")
```

`fuse_provider_payloads` adapts raw provider payloads (`results` / `data` / `data.web` /
a bare list / a list of URL strings) then fuses. `reciprocal_rank_fusion` takes already-
extracted lists if you have them.

Each `FusedResult` carries `url` (normalised, the dedup key), `display_url` (the original
as first seen), `title`, `score`, `sources` (which providers returned it), `ranks`
(each provider's best rank) and `snippet` (defaulted to `""`, so every pre-existing
constructor call still works).

**Snippet carry (2026-09-02).** `extract_results` now returns `{"url", "title", "snippet"}`.
The snippet is the first non-blank of the vendor keys `snippet`, `description`, `content`
(SearXNG, Tavily), `text`, `summary` (Exa), `markdown` (Firecrawl — last, because it is a
page body), whitespace-collapsed and hard-capped at `MAX_SNIPPET_CHARS = 500` so a fused
list of 50 results never drags 50 pages along. `FusedResult.snippet` is the snippet from
the provider that ranked the URL **best** (lowest rank) among those that sent one; ties go
to the provider consulted first, and a provider that sent none does not compete. Best-rank
rather than first-seen because snippets are query-dependent: the engine that ranked the
page highest is the one whose passage matched the query best — the most useful input to a
downstream reranker. `query_plan.fuse_decomposed` threads snippets through its second
fusion stage, so a decomposed query keeps them too.

### Post-fusion diversity (opt-in)

`diversify(fused, *, max_per_host=2, near_dup_threshold=0.8, window=10)` is an MMR-style
single greedy pass over a fused ranking, stdlib only, 0 MB. Both fusers accept the same
three keywords; `max_per_host` and `near_dup_threshold` default to `None` there, which is
exactly the pre-existing behaviour, so `query_plan.py` and the search-hub are unaffected
until they name a knob. When one is named, `diversify` runs after fusion and **before**
`limit`, so a diverse result just past the cut can be promoted into it.

* **Host cap.** At most `max_per_host` kept results per `host_key(url)` within the top
  `window`. `host_key` is `urlsplit(url).hostname`, lower-cased, `www.` stripped, then the
  last two labels — or the last **three** when the TLD is a two-letter country code and the
  second-level label is generic (`ac co com edu go gov ne net or org`): `news.bbc.co.uk` ->
  `bbc.co.uk`, `finance.sina.com.cn` -> `sina.com.cn`. IP literals, single-label and empty
  hosts are used whole. Subdomains are folded on purpose: multilingual queries routinely
  return `ru.` / `zh.` / `en.wikipedia.org`, and an exact-host cap would let one site take
  six of the top ten. This is **not** the public-suffix list (200 KB, changes monthly); the
  documented miss is shared-hosting parents (`alice.github.io` and `bob.github.io` count as
  one host) — an error in the safe direction, since it can only demote a distinct site
  below the window, never let one site dominate it.
* **Near-dup demotion.** Token-Jaccard of `title + " " + snippet` (lower-cased `[a-z0-9]+`
  runs) against **every** already-kept result in the window; strictly greater than
  `near_dup_threshold` demotes. Pinned at the boundary: exactly `0.8` is **not** a
  duplicate. A result with no title and no snippet has no tokens and is never a duplicate.
  The tokenizer is ASCII by design, so pure CJK/Cyrillic text is never demoted as a
  duplicate (it is still host-capped); widening it is a deliberate follow-up.
* **Re-ordering only.** Nothing is dropped and no object is copied or altered: demoted
  results (either reason, or arriving after the window is full) follow the window in their
  original order and keep their RRF `score` — a non-monotonic score column is the visible
  trace of a demotion. Only *kept* results spend host quota or become comparison targets.
* `None` disables either check independently; `window=0` is the identity;
  `max_per_host < 1`, a threshold outside `[0, 1]` or a negative window raise `ValueError`.

**Why rank-only.** Exa, Tavily and SearXNG each emit a relevance score from a different
model over a different corpus. Those numbers are not comparable, and min-max normalising
them manufactures a shared scale that never existed — the fused order would then track
whichever provider had the widest spread. Rank ordinals *are* comparable: "this engine's
best hit" means the same thing everywhere. RRF (Cormack et al., SIGIR 2009) needs no
training and no tuning per corpus.

**Properties the tests pin** (all mutation-verified — see below):

* consensus beats a single loud vote: a document three engines rank #2 outranks one
  engine's #1;
* deduplication by normalised URL (scheme/host case, `www.`, default port, tracking
  params incl. `utm_*`/`yclid`/`spm`, trailing slash, fragment);
* a provider repeating a URL cannot inflate it — best rank, counted once;
* blank entries do not shift the ranks of real ones;
* ties break lexicographically, so the ordering is deterministic and independent of the
  order the providers were consulted;
* the snippet comes from the best-ranking provider, is decided at the occurrence that
  earned that rank (a later repeat cannot rewrite it), and is capped at 500 chars;
* `diversify` never drops, never changes a `score`, is the identity at `window=0`, and
  the fusers' defaults reproduce the pre-diversify ordering exactly.

## SearXNG engines: regional + default-mix flips

```bash
python searxng_regional.py --probe      # live per-engine reachability (all MANAGED_ENGINES)
python searxng_regional.py --dry-run    # print the settings.yml diff, change nothing
python searxng_regional.py --apply      # backup -> splice -> validate -> restart -> health-check
python searxng_regional.py --revert     # restore newest backup -> restart
```

Defaults target the owner's instance (`D:\searxng\settings.yml`, container `searxng`,
`http://127.0.0.1:8890`); override with `--settings` / `--container` / `--base-url`.

The managed block covers two tables, rendered in order as `MANAGED_ENGINES`:

* `REGIONAL_ENGINES` — measured 2026-07-24 against the owner's instance; unchanged.
  `enabled_specs()` / `query_plan` routing still fan out over this table only.
* `INDEPENDENT_ENGINES` — the default-mix flips of plan G-3 / Wave 1 item 1a, evidenced
  2026-09-02 from a cloud VM (**not** the owner's instance): `google` -> `disabled: true`
  (keyless scraping is dead — Whoogle archived with an EOL notice 2026-07-24, searxng#6359
  closed 2026-08-22; upstream now ships it disabled, and this entry cancels any force-enable
  in the file it is applied to); `mwmbl` -> `disabled: false` (keyless; the upstream module's
  URL `api.mwmbl.org/api/v1/search/?s=` answered HTTP 200, 44 results, 0.41 s);
  `marginalia` -> `disabled: false`, `inactive: false`, `api_key: public` (upstream ships it
  disabled **and** inactive — the module is not even loaded — with no key). Marginalia's
  status is `rate-limited`, not `works`: with the shared `public` key the endpoint answered
  **HTTP 429 on the first request**. It is switched on because the plan says so and because
  SearXNG fails it truthfully (`unresponsive_engines`, then a ~0-latency suspension), but it
  is kept out of `enabled_specs()` so routing never spends a call on it. A personal key in
  the entry's `extra` tuple replaces `public`; do not self-host Marginalia to dodge the limit.

`EngineSpec` gained `extra: tuple[tuple[str, str], ...]` (rendered verbatim as `key: value`
lines) and two properties: `switched_on` (`works` / `rate-limited` -> `disabled: false` +
`timeout`) and `switched_off` (`dead` -> `disabled: true`, no timeout). Any other status
stays an inert comment, as before. The three flips render as:

```yaml
  # global: keyless scraping dead (Whoogle EOL 2026-07-24, searxng#6359 closed 2026-08-22); upstream ships it disabled, checked 2026-09-02 (bang !go)
  - name: google
    disabled: true
  # independent: api.mwmbl.org/api/v1/search probed 2026-09-02: HTTP 200, 44 results, 0.41 s; keyless; upstream ships it disabled (bang !mwm)
  - name: mwmbl
    disabled: false
    timeout: 6.0
  # independent: api2.marginalia-search.com with the shared `public` key: HTTP 429 QPM Limit Exceeded at FIRST touch, 2026-09-02; on by plan G-3, fails truthfully - put a personal key in `extra` to make it useful (bang !mar)
  - name: marginalia
    disabled: false
    timeout: 6.0
    inactive: false
    api_key: public
```

Under `use_default_settings: true` SearXNG merges this partial list into its built-in
engine definitions **by `name`**, so only the overridden keys appear; the tests parse the
spliced file with pyyaml and replay that merge. The block markers still say "regional" on
purpose — renaming them would orphan any block already applied (`remove_block` finds the
block by its markers).

**Status 2026-09-02: rendered and parsed, NOT applied live.** This VM cannot reach the
owner's instance; the owner applies the flips on the box with `--dry-run`, then `--apply`
(which backs up, validates, restarts and health-checks as before), then `--probe`.

`--probe` walks all of `MANAGED_ENGINES` and prints a `block` column (`on` / `off` / `-`)
beside the measured verdict, so an `off` engine that measures `BLOCKED` is the expected
reading. It now counts only results SearXNG *attributes* to the probed engine: SearXNG
silently drops an `engines=<name>` it has not loaded and answers with the default mix, so a
plain result count would have read marginalia (upstream `inactive: true`) as `WORKS n=10`
before `--apply`. That shape is reported as `NOT-LOADED` instead. The extension was
exercised against a loopback stub of the JSON API, not the live instance.

**You probably do not need `--apply`.** A SearXNG engine marked `disabled` is still
reachable via `engines=<name>` or its `!<shortcut>` bang — `disabled` only controls the
*default* result mix. `--apply` buys default-mix membership at a measured latency cost
(~1 s to ~3-5 s per query). The trade-off numbers are in `docs/search-expansion/`.

Safety properties: the block is delimited by markers and re-applying is a true no-op;
`--apply` refuses outright if `settings.yml` already defines its own top-level `engines:`
key (a duplicate YAML key would break the instance); the spliced YAML is re-parsed before
it is written; and if the instance does not return healthy after the restart, the backup
is restored and the container restarted again automatically.

## Running the tests

```bash
cd tools/search-expansion
pip install pytest pytest-cov pyyaml
pytest --cov=rank_fusion --cov=searxng_config --cov=query_plan --cov-branch \
       --cov-report=term-missing --cov-fail-under=100
```

191 tests as of 2026-09-02 (119 `test_rank_fusion.py`, 50 `test_searxng_config.py`,
22 `test_query_plan.py`); 100% line + branch on the three pure modules is the CI gate.

## Mutation check

Coverage says every line ran, not that a test would notice if the line were wrong. Use the
repo's existing `mutation-check` tool (do not hand-roll one — its mutation set is generic
and catches things a hand-picked set does not):

```bash
cd tools/search-expansion
for m in rank_fusion.py searxng_config.py query_plan.py; do
  python ../../.agents/skills/mutation-check/mutation_check.py "$m" \
    --max-mutations 0 --cwd . -- python -m pytest -q --no-header -x -p no:cacheprovider
done
```

Current state (2026-09-02): **53/53 killed on `rank_fusion.py`, 24/24 on
`searxng_config.py`, 8/8 on `query_plan.py`** (was 21/21, 21/21 and 7/8 before the
snippet/diversity/flip work grew the mutation surface). A surviving mutation means the
suite stopped protecting that behaviour — fix the tests, not the tool.

The 2026-09-02 run found two more, handled differently on purpose:

* `rank_fusion.py` — the best-rank snippet rule was first written as
  `position < snippet_rank.get(key, position + 1)`; the `+ 1` was an *equivalent mutant*
  (any default greater than `position` behaves identically), so no test could kill it.
  Fixed by removing the arbitrary constant (`best is None or position < best`) rather than
  writing a test that pretends to pin it.
* `query_plan.py` — `_regional_specs` returning `()` vs `None` survived at HEAD because
  both are falsy at its only call site. Its docstring promises an empty **tuple**, so that
  promise is now pinned directly.

Both original suites were strengthened by exactly this. The generic mutation set found two
gaps a hand-written set had missed:

* `keep_blank_values=True` in `normalize_url` was unasserted — dropping it would merge
  `?q=&id=7` with `?id=7`, two different requests;
* the `inside = False` reset after `END_MARKER` was unasserted in **both**
  `remove_block` and `find_top_level_key` — every test happened to put the managed block at
  EOF. Had the block ever been followed by other content, `remove_block` would have
  **silently deleted everything after it** and the duplicate-key guard would have stopped
  looking. The code was right; the tests could not tell.
