# tools/search-expansion

Two independent capabilities behind one small, dependency-free package:

| File | What it is | Gated |
|---|---|---|
| `rank_fusion.py` | Reciprocal Rank Fusion across search providers. Pure functions, stdlib only. | 100% line+branch |
| `searxng_config.py` | Pure `settings.yml` transform for enabling SearXNG's regional engines. | 100% line+branch |
| `searxng_regional.py` | Thin CLI shell: live probe, backup, container restart, health check. | lint + types only |

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
)
for r in fused:
    print(f"{r.score:.5f}  {r.sources}  {r.display_url}")
```

`fuse_provider_payloads` adapts raw provider payloads (`results` / `data` / `data.web` /
a bare list / a list of URL strings) then fuses. `reciprocal_rank_fusion` takes already-
extracted lists if you have them.

Each `FusedResult` carries `url` (normalised, the dedup key), `display_url` (the original
as first seen), `title`, `score`, `sources` (which providers returned it) and `ranks`
(each provider's best rank).

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
  order the providers were consulted.

## SearXNG regional engines

```bash
python searxng_regional.py --probe      # live per-engine reachability
python searxng_regional.py --dry-run    # print the settings.yml diff, change nothing
python searxng_regional.py --apply      # backup -> splice -> validate -> restart -> health-check
python searxng_regional.py --revert     # restore newest backup -> restart
```

Defaults target the owner's instance (`D:\searxng\settings.yml`, container `searxng`,
`http://127.0.0.1:8890`); override with `--settings` / `--container` / `--base-url`.

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
pytest --cov=rank_fusion --cov=searxng_config --cov-branch \
       --cov-report=term-missing --cov-fail-under=100
```

## Mutation check

Coverage says every line ran, not that a test would notice if the line were wrong. Use the
repo's existing `mutation-check` tool (do not hand-roll one — its mutation set is generic
and catches things a hand-picked set does not):

```bash
cd tools/search-expansion
python ../../.agents/skills/mutation-check/mutation_check.py rank_fusion.py \
  --max-mutations 0 --cwd . -- python -m pytest -q --no-header -x -p no:cacheprovider
python ../../.agents/skills/mutation-check/mutation_check.py searxng_config.py \
  --max-mutations 0 --cwd . -- python -m pytest -q --no-header -x -p no:cacheprovider
```

Current state: **21/21 killed on `rank_fusion.py`, 21/21 on `searxng_config.py`**. A
surviving mutation means the suite stopped protecting that behaviour — fix the tests, not
the tool.

Both suites were strengthened by exactly this. The generic mutation set found two gaps a
hand-written set had missed:

* `keep_blank_values=True` in `normalize_url` was unasserted — dropping it would merge
  `?q=&id=7` with `?id=7`, two different requests;
* the `inside = False` reset after `END_MARKER` was unasserted in **both**
  `remove_block` and `find_top_level_key` — every test happened to put the managed block at
  EOF. Had the block ever been followed by other content, `remove_block` would have
  **silently deleted everything after it** and the duplicate-key guard would have stopped
  looking. The code was right; the tests could not tell.
