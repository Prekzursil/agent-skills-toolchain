# EVAL DEFINITION: process-hygiene-supervisor

Eval-driven development for the supervisor: each eval is a replayed process table
graded by **code** (deterministic assertions on the plan), not by opinion. The
runner prints `pass@1` (first-trial success) and `pass^3` (three consecutive
trials all pass); the engine is deterministic, so `pass^3` is the stability bar.

```
python evals/run_evals.py            # EVAL REPORT + exit 1 on any failure
pytest tests/test_evals.py           # the same evals as a CI gate (+ both-states proofs)
```

## Capability evals (must pass@3 >= 0.90; currently 6/6, pass^3 = 100%)

| eval | asserts |
|---|---|
| `measurement-2026-09-02` | replay of the owner's 02.09.2026 measurement (31.6 GB / 3.5 GB free / 67.7 GB committed, 70 chrome, 42 msedge, 28 node, 14 pwsh, 3 Grok + bridge-servers, auth2api, 4 orphans, daemons, idle vmmem): tier `elevated` **because 12.3 GB of commit headroom remains** under an 80 GB commit limit and 2.14x is below the 2.5x critical leg; stop **exactly** the 3 retired bridge-servers, 4 leaked orphans, 2 detached leaf shells and the younger duplicate playwright tree; delegate the 28-31 h cursor orphans to the reaper; report chrome; never touch auth2api, Basic Memory, agent-mail, the watchdog, the IDE, its active agent, browsers, Memory Compression, vmmem |
| `measurement-2026-09-02-low-headroom` | the identical box with a 70 GB commit limit (2.3 GB headroom) reads `critical` with an **unchanged kill set** - proof the headroom leg changes what may *execute*, not what is *decided* |
| `stale-cli-sessions-under-terminal` | 30 h idle cursor-agent and 50 h idle Claude sessions under a terminal are stopped by `session-age`; an IDE-owned session of the same age is only reported |
| `oversized-active-session-default` | an ACTIVE 4 GiB cursor session at critical is reported (`rss-hard`), not stopped |
| `oversized-active-session-opt-in` | the same with `escalation.stopActiveAtCritical=true` is stopped |
| `singleton-duplicate-past-grace` | a 3 h-old second Basic Memory daemon that does not own `:8765` is stopped at elevated; the port owner never is |

## Regression evals (must pass^3 = 1.00 - release-critical safety)

| eval | protects |
|---|---|
| `quiet-box` | a healthy box produces no stop and no rule at all (no false positives) |
| `protected-daemons-under-pressure` | at critical, parentless idle auth2api / Basic Memory / agent-mail / bm-watchdog / resource-guard / mcp_http_host are all untouched |
| `singleton-relaunch-grace` | a 200 s-old relaunch beside the live daemon is inside the grace window - nothing stopped |
| `pid-reuse-stale-ppid` | a ppid recycled to a newer process counts as orphaned; a child older than its "parent" is excluded from the kill tree |
| `detached-shell-hosting-session` | a parentless shell hosting a live session is never swallowed by the orphan rule |

## Graders

* **Code grader** (`run_evals._grade`): tier, exact `stop_pids`, `never_touched`,
  `rules_present`, `rules_absent`, `delegate_reaper`, `wsl_shutdown`.
* **Both-states proof** (`tests/test_evals.py`): the grader is itself tested to go
  RED when an expectation is wrong (a protected daemon "expected" in the kill set,
  a wrong tier, a missing rule), so a green report is evidence, not silence.
* **Human grader**: any change to `protected` lists, tier thresholds, or the kill
  path in `hygiene_actuate.py` gets manual review - security-relevant.

## Adding an eval

Drop a JSON under `evals/scenarios/` (rows use `age_seconds`, `private_mib`,
`active`, `count`; see `run_evals.py` docstring), state the expectation before
running it, then run the runner. Keep evals fast (whole set < 10 s).
