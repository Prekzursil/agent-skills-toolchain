# codex-databricks-fanout — scripts

The **executable** implementation of the `codex-databricks-fanout` skill. `SKILL.md` documents the
measured constraints; this directory is the code that enforces them. Consolidated from a standalone
harness repo (the driver) plus the toolchain's `tools/databricks-fanout/` (the structural gate +
worker notebook), extracted from a production run of **604 units across 9 job submissions**.

## Layout

| path | role |
|---|---|
| `harness/contract.py` | **authoritative executable RAIL** — the frozen config every module reads (policy_id, node type, concurrency=48, stagger=3.0, profile, notebook path) plus `Unit`, lane schemas, and the byte-floor `and_gate_artifact` / `schema_valid` used by the driver's 5-clause poll gate |
| `harness/build_batch.py` · `submit.py` · `poll.py` · `preflight.py` | the **driver**: build a batch, submit the job, poll to a terminal life-cycle state, apply the gate |
| `harness/harvest.py` | driver harvest — a per-unit, `run_cmd`-injectable library fn the lanes call (`harvest(dbfs_dir, dest, units, run_cmd)`) |
| `harness/harvest_cli.py` | standalone whole-directory harvest **CLI** — lists a results dir, downloads via `fs cat`, applies the structural gate, reports explicit per-unit terminal states (SUCCESS / SEVERED / MALFORMED / ABSENT), wired onto `contract.RAIL` |
| `harness/gate.py` | the **structural** completeness gate (sentinel + fenced-field contract, no byte floor by default) — mutation-tested; delegates the size/sentinel rule to the shared `hooks/_shared/completion.py` predicate with a local fallback |
| `harness/lanes/{coverage,preflight_units,run_E}.py` | Program E orchestration (one Unit per uncovered-file gap; node/runnability preflight) |
| `batch_runner.py` | the **worker** — the on-Databricks notebook the driver invokes via `RAIL["notebook"]`. A notebook export, NOT a standalone module (`dbutils` is runtime-injected), so it is excluded from lint/format |
| `tests/` | unit tests for every driver module **plus** the mutation-tested `test_gate.py` (both-states proof) |
| `e2e/` | live round-trips (`smoke_2unit`, `run_fanout`, `run_runnability`, `watch`) — **require a live Databricks workspace**; see Testing |

## The completeness gate is STRUCTURAL, not a byte floor

A unit's exit code is not proof it produced anything: the artifact may be absent, truncated, or
unparsable. The obvious gate — `len(artifact) >= N` — is wrong and failed in production. A 127-unit
audit ran a terse lane (fenced verdict + one reason line, median **382 B**) and a verbose lane
(median 1690 B); an 800-byte floor rejected **84 of 85 valid** terse artifacts and **0 of 42**
verbose ones. A gate that fails one entire lane and no part of another measures verbosity, not
truncation. So the default (`harness/gate.py`) is structural — sentinel present in the last 600
bytes, the sentinel names **that** unit, and every field the lane's contract requires is present and
non-empty. `min_bytes` remains available per lane but is opt-in and justified per lane, never global.
`tests/test_gate.py` is mutation-checked: reintroducing the 800-byte floor turns several tests red,
including the terse-artifact regression — a suite that stays green under that mutation is not
protecting the behaviour it claims to.

Completeness is a property of the ARTIFACT; doneness is a property of the RUN. A harvest is final only
once the run reaches a terminal life-cycle state — before that, an artifact can only report what was
true when it was last written (the write-as-you-go skeleton it may still hold).

## Operational constraints (measured — do not re-derive)

- **Arrival rate is the binding constraint, not compute.** 180 concurrent → 120 died, all 429, while
  the node still had 228.9 GB free. `concurrency=48` at `stagger_s=3.0` → 0 × 429.
- **Download with `fs cat`, never `fs cp`.** `fs cp` has returned 0 having written nothing; a harvest
  built on it yields a full set of empty files.
- **Strip `DATABRICKS_TOKEN` from the environment.** A stale ambient token overrides the config file
  and produces confusing 403s.
- **Set `MSYS_NO_PATHCONV=1`, scoped.** Git-Bash rewrites `dbfs:/…` args into Windows paths before the
  CLI sees them. Never export it globally — it then breaks legitimate `/c/Users/…` path arguments.
- **Name the subject bundle explicitly.** The runner unpacks whatever archive it is handed; a wrong
  subject is otherwise silent. `batch_runner` takes `bundle_tgz` as a widget and reports the archive
  path, size, and top-level entries in the run summary.

## Testing

Unit + mutation tests (stdlib-only, no Databricks, run in CI):

```
python -m pytest tests -q
```

The `e2e/` scripts (`smoke_2unit`, `run_fanout`, `run_runnability`, `watch`) drive a **live Databricks
workspace** (real, billable job submissions) and are therefore **NOT run in CI** — invoke them
manually against a configured `RAIL["profile"]` when validating an end-to-end round trip.
