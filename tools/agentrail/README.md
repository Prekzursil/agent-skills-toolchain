---
title: README
type: note
permalink: dqverify-repo-20261013/tools/agentrail/readme
---

# agentrail

A **config-driven multi-rail agent dispatch shell** over [`agentspec`](../agentspec).

Adding an agent CLI is a row in [`agentrail/rails.toml`](agentrail/rails.toml) — not new Python.
agentrail is the *consumer* of agentspec and the proof that the spec is vendor-neutral: five
rails from four vendors ride the same core with zero per-vendor code.

```console
$ agentrail rails
$ agentrail resolve codex
$ agentrail plan  codex --unit-id u1 --prompt-file ./prompt.txt
$ agentrail run   codex --unit-id u1 --prompt-file ./prompt.txt --receipt-path ./r.txt
$ agentrail deploy                     # writes ~/.local/bin/agentrail.cmd, under a guard
```

Every command prints one JSON object carrying agentspec's four mandated envelope fields —
`status`, `summary`, `next_actions`, `artifacts` — plus `error{code, root_cause,
retry_instruction, stop_condition}` on a failure and a `terminal` marker always. One shape on
the success path and the failure path; **"error-only output without next steps" is a named
anti-pattern and there is no code path here that produces it.**

---

## The reuse boundary

This is the whole point of the package, so it is stated precisely and **gated mechanically**.

| Concern | Owner | agentrail's part |
|---|---|---|
| Completion AND-gate (six clauses) | `agentspec.oracle.judge` | calls it |
| Closed failure taxonomy | `agentspec.taxonomy.REASONS` | subset of it |
| Argv cap + prompt routing | `agentspec.argv.build_for_rail`, `WINDOWS_CMDLINE_CAP` | calls / imports |
| `win-arg-limit` one-shot retry | `agentspec.retry.plan_retry` | calls it, passes `attempt` through |
| Result envelope | `agentspec.envelope` | builds through it, validates with it |
| Terminal markers | `agentspec.terminal.terminal_line` | calls it |
| Progress-stream rejection | `agentspec.progress` (via the oracle) | never re-reads a progress body |
| Pre-dispatch policy | `agentspec.dispatchpolicy.check_dispatch` | calls it before any spawn |
| Rail declaration type | `agentspec.argv.RailSpec` | **imports** it; does not redeclare |
| Clock port | `agentspec.clock.Clock` | implements it in the impure shell |
| Live-marker mechanism | `agentspec.evals.pytest_live` | reuses it in `conftest.py` |

`tests/test_no_rival_core.py` walks agentrail's own AST and fails on any redeclaration of an
agentspec-owned constant, type or function; it also asserts the reason strings are a subset of
the closed taxonomy and that `WINDOWS_CMDLINE_CAP` is *imported* rather than re-typed. The
watchlist is itself checked against agentspec's real module contents, so a typo'd entry cannot
pass forever.

### What agentrail actually adds

1. **A config layer** (`rails.py`) — TOML rows → validated `RailRow` → `agentspec.RailSpec`.
2. **Dynamic executable resolution** (`resolve.py`) — ordered globs, then a shim fallback with a
   warning that reaches the result envelope.
3. **The spill** (`plan.py`) — a rail whose CLI wants the prompt on **argv** gets it routed to a
   file or stdin instead. This is why `agentspec.argv.PROMPT_TRANSPORTS` never has to widen.
4. **The impure shell** (`runner.py`) — the only module that binds a real disk, clock or process.

---

## Measured vs assumed

Everything below is stated at the confidence it was actually established at.

### MEASURED (direct observation on this machine, 2026-07-26/27)

- **`codex` prompt transport = stdin.** `codex exec` reads the prompt from stdin and announces
  `Reading prompt from stdin...`; with **empty** stdin it exits 1 with `No prompt provided via
  stdin.` The negative control matters — it rules out the reading in which a literal `-` was
  taken as a one-character prompt. There is **no** prompt-file flag on codex.
- **`codex` hardening flag exists.** `--ignore-user-config` is present in `codex exec --help`
  (verified in this lane, not inherited). `-a/--ask-for-approval` is **top-level only** and
  errors with exit 2 on `exec`.
- **The codex vendor glob resolves to exactly 1 match** here, and both wildcard segments are
  genuinely volatile (npm sub-package name; target triple).
- **`grok --prompt-file` is a real file read** — a bad path returns `os error 3`.
- **`opencode` consumes stdin as the message** — piped stdin satisfies the message-presence gate
  that empty stdin fails.
- **basedpyright cannot see an editable sibling install.** With
  `[tool.basedpyright] extraPaths = ["../agentspec"]` commented out: **17 errors**. Restored:
  **0 errors**. Same tree, basedpyright 1.39.8.
- **The gated suite**: `219 passed, 9 deselected`, **100.00% line + branch**, **0**
  `# pragma: no cover` in package source.

### ASSUMED / UNVERIFIED — named, not papered over

- **`agy`: binary settled, transport NOT.** The live probe was run (`pytest --run-live -m live`)
  and `agy --version` exits **0 within 20 s** — so the earlier 15 s timeout was indeed a
  **DETECTOR failure, not a verdict**. That settles only the binary half. The row stays
  `verified = false` because its prompt transport is still **unmeasured** and assumed `argv`;
  `verified = true` claims both halves. Remaining experiment: a headless one-shot proving where
  agy reads its prompt from.
- **`gemini`: BLOCKED, and now with a cause.** Spawning the resolved `.ps1` fails with
  **`WinError 193, "%1 is not a valid Win32 application"`** — `CreateProcess` cannot launch a
  PowerShell script. The original 15 s timeout was masking a hard incompatibility, not
  slowness. The live row fails on purpose; that red *is* the finding. Settling experiment: find
  a native `gemini.exe`/`.cmd`, or add a `powershell.exe` wrapper row.
- Both rows ship opt-in: the CLI refuses them without `--allow-unverified`, and nothing here
  describes them as working.
- **The success-path JSON schema of `grok` and `opencode` is unknown** — the probes that settled
  them reached only *error* paths. Every row therefore uses `receipt_format = "text"` with
  `forbidden_markers` rather than inventing `required_fields` that would fail the schema clause
  on every real dispatch. (`json` + `required_fields` is fully supported by the loader; it is the
  better spec the moment a success schema is measured.) `codex` is `text` for a stronger reason:
  its receipt is the `--output-last-message` **file**, which is prose, while its `--json` stdout
  is JSON**L** and would not parse as one object.
- **`codex` stdout JSONL purity — highly likely, not certain.** Measured 0 non-JSON lines on
  stdout, but on a stream that aborted before turn completion. agentrail does not depend on it:
  the receipt comes from the `--output-last-message` file.
- **No rail has been driven end-to-end through a real completed turn by this lane.** The live
  probes assert resolution and `--version`, which is what `verified = true` claims and no more.

---

## Hermeticity, and how 100% is reached without a single pragma

The gated suite performs **no network I/O and spawns no process**. That is a design property,
not a discipline:

- Every impure edge is an injected **port** (`ports.py`): filesystem, spawn, warning sink; the
  clock port is agentspec's. The pure layer only ever sees Protocols, so a fake drives every
  branch.
- `LocalFileSystem` is measured against a pytest `tmp_path` — real disk, no network, no spawn.
- `SubprocessSpawn` takes `subprocess.run` as a **constructor seam**, so every arm (success,
  `TimeoutExpired`, `E2BIG`, Windows error 206, `FileNotFoundError`, `PermissionError`) is driven
  with a fake. The real default is asserted, never called.
- The `__main__` guard's *true* arm is covered by `runpy.run_path`, which re-executes the file
  in-process with `__name__ == "__main__"`. That is the usual excuse for a pragma, removed.
- The pragma check itself **tokenises** rather than greps: three modules discuss
  `# pragma: no cover` in prose to explain why they carry none, and a substring search reports
  all three as violations. Use-vs-mention.

---

## The mutation gate

A green suite proves the code passes its tests. It does **not** prove the tests would notice if a
decision were removed. `tests/test_mutations.py` reverts each load-bearing decision one at a time
and requires the matching check to go **RED**, with a control run proving every check is **GREEN**
unmutated:

| Mutation | Decision reverted |
|---|---|
| `codex-glob-to-hardcoded-path` | the vendor-bin glob → today's resolved path |
| `spill-removed-prompt-rides-argv` | the spill → the 34,472-char prompt on argv |
| `envelope-field-deleted-success-path` | `artifacts` dropped from a success envelope |
| `envelope-field-deleted-error-path` | `next_actions` emptied on an error envelope |
| `reason-outside-the-closed-taxonomy` | a rail-flavoured reason agentspec never declared |
| `deploy-guard-to-unconditional-write` | the `Test-Path` guard → an unconditional write |
| `rival-core-argv-cap-forked` | `WINDOWS_CMDLINE_CAP` re-declared instead of imported |

A registry test refuses to let a named row be deleted, and another refuses a "mutation" that
produces the same value as its control.

---

## Deploy

`agentrail deploy` writes `~/.local/bin/agentrail.cmd` **under a guard**: if the target exists it
is left byte-identical and the command returns a `warning` envelope telling you to diff it and
pass `--overwrite`. This is the ledger-proven data-loss class — `New-Item -Force` on a **file**
truncates it, and an unconditional write is the same class. `-Force` on a **directory** is
idempotent and safe, which is why the parent-directory create is unguarded and the file write is
not. The decision is a pure function (`deploy.decide`) so it is unit-tested in both states and
carries a mutation row.

## Local development

```bash
python -m venv .venv && . .venv/Scripts/activate     # Python 3.11, matching CI
pip install -e ../agentspec && pip install -e ".[dev]"

pytest -m "not live" --cov=agentrail --cov-branch --cov-report=term-missing --cov-fail-under=100
basedpyright agentrail
ruff check . && ruff format --check .                 # ruff 0.15.17, from the repo root

pytest --run-live -m live                             # opt-in; spawns real agent CLIs
```

Use the venv's **`pytest` console script**, never `python -m pytest`: the `-m` form prepends the
CWD to `sys.path` and hides the exact import failure the CI step is guarding against.

## CI

Two steps in `.github/workflows/quality.yml`, both reusing existing charter slugs (`gate-types`,
`gate-tests-coverage`) so `.quality/charter_check.sh` still reports **6 gates consistent** — a new
`gate-<slug>` without a charter entry reds the *lint* job, which is the measured trap.