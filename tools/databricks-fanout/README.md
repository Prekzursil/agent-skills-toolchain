# tools/databricks-fanout

The **executable** half of the `codex-databricks-fanout` skill. That skill documents the measured
constraints; this directory is the code that enforces them, extracted from a production run of
**604 units across 9 job submissions**, all terminal SUCCESS.

| file | role |
|---|---|
| `gate.py` | the AND-gate: is a unit's artifact actually complete? |
| `harvest.py` | download from DBFS + apply the gate + per-unit terminal states |
| `tests/test_gate.py` | both-states + mutation-checked tests for the gate |

## Why a gate exists at all

**Exit code 0 is not proof a unit produced anything.** Blocking on process exit tells you the
process ended. The artifact may be absent, truncated, or unparsable. A wave harvested on exit codes
alone reports a full set and is wrong in the direction that looks like success.

The gate requires, per unit:

1. the artifact exists and is downloadable,
2. a completion sentinel appears within the last 600 **bytes**,
3. the sentinel names **that** unit — otherwise a directory harvest happily credits a unit with a
   sibling's artifact,
4. if the lane declares a fenced block, it parses and every required field is non-empty.

## The byte-floor trap — read before adding `min_bytes`

The obvious gate is `len(artifact) >= N`. It is wrong, and it failed here in production.

A 127-unit audit ran two lanes: one contractually terse (a fenced verdict block plus a one-line
reason, median **382 B**) and one verbose (median **1690 B**). An 800-byte floor rejected **84 of 85
valid artifacts** in the terse lane and **0 of 42** in the verbose lane.

> A gate that fails one entire lane and no part of another is measuring **verbosity, not
> truncation**.

So the default is structural, not dimensional. `min_bytes` remains available for a lane whose
contract genuinely fixes a size, but it is opt-in and must be justified per lane — never global.

## Parse the FIELD, never the document

`parse_block()` extracts the fenced block and reads keys from it. Searching the whole artifact for
a token matches prose that merely *discusses* the token. This use-vs-mention error recurred **three
separate times in one program**: a stub ledger where 0 of 9 findings were real, a platform
classifier that misread 6 of 9 options, and a fold census that inflated 10 findings to 13. Every
one was a document-wide grep where a field read was meant.

## Operational constraints (measured — do not re-derive)

- **Arrival rate is the binding constraint, not compute.** 180 concurrent → 120 died, *all* 429,
  while the node still had 228.9 GB free. `concurrency=48` at `stagger_s=3.0` → 0 × 429.
- **Download with `fs cat`, never `fs cp`.** `fs cp` has been observed to return 0 having written
  nothing; a harvest built on it yields a full set of empty files.
- **Strip `DATABRICKS_TOKEN` from the environment.** A stale ambient token overrides the config
  file and produces confusing 403s.
- **Set `MSYS_NO_PATHCONV=1`, scoped.** Git-Bash rewrites `dbfs:/…` arguments into Windows paths
  before the CLI sees them. Do *not* export it globally — it then breaks legitimate `/c/Users/…`
  path arguments, which silently turned a `git clone` into a no-op.
- **Name the subject bundle explicitly.** The runner unpacks whatever archive it is handed and
  cannot tell a wrong subject from a right one. An entire 604-unit campaign judged from option
  cards against a bundle belonging to a *different program*, and nothing in the run surfaced it.
  The notebook now takes `bundle_tgz` as a widget and reports the archive path, its size and its
  top-level entries in the run summary, so a wrong subject is visible rather than silent.

## Testing

```bash
python tools/databricks-fanout/tests/test_gate.py
```

The suite is mutation-checked: reintroducing the 800-byte floor turns **5 of 8 tests red**,
including the terse-artifact regression. A suite that stays green under that mutation is not
protecting the behaviour it claims to.
