# TG-2 — diff-scoped mutation gate

**Coverage says a line *ran*. Mutation says a test would *notice* if that line broke.**

A line at 100% coverage can still be unasserted: the motivating scar is a
`DEFAULT_MIN_BYTES` default that every test passed *explicitly*, so mutating the
constant changed nothing any test observed — 100% coverage, zero protection.

This gate perturbs the source of the files a diff touched and fails when any
**mutant survives** (i.e. the whole test suite still passes with the code
subtly broken), naming the surviving mutant and the weak suite that let it live.

- **Diff-scoped** (the cost control): it mutates only the files in
  `git diff --name-only <base>...HEAD` — never the whole tree.
- **Self-contained**: stdlib + one pinned mutation tool. Nothing here touches the
  repo's existing quality gates; wire-in is opt-in (below).

> Ported into agent-skills-toolchain from a harness build. `mutation_gate.py` and its
> tests are repo-agnostic — every repo-specific value (`--base`, `--repo-root`,
> `--include`, `--test-command`, …) is a CLI flag — so only this README and the
> default exclude markers were reconciled to the toolchain; the logic is byte-for-byte
> the verified original, re-verified against this repo's gates (ruff 0.15.17 at
> line-length 88, 100% line+branch, mutation self-check).

## Why cosmic-ray

The gate is meant to be **runnable locally on any developer box** as well as in CI,
and **mutmut 3.x refuses to run on native Windows**
(`To run mutmut on Windows, please use the WSL` — boxed/mutmut#397).
[cosmic-ray](https://github.com/sixty-north/cosmic-ray) installs cleanly via
`uvx`/`pip` and runs natively on Windows, macOS, and Linux, so it is the tool that
backs a gate a developer can run on this box. Pinned: **`cosmic-ray==8.4.6`**
(see `COSMIC_RAY_VERSION` in `mutation_gate.py`).

### How it relates to the toolchain's existing gates (additive, opt-in)

The repo's quality contract is the lean, closed **6-gate charter** in
`.github/workflows/quality.yml` / `.quality/charter.yml` (lint-format, types,
tests-coverage, sast, secrets, deps). TG-2 does **not** modify any of those gates or
the charter's closed gate set. The `lint-format` gate (`ruff check .` +
`ruff format --check .`) already covers this tool's source, because it runs repo-wide;
wiring the *mutation* check itself into CI is a separate, opt-in step (below).

## Usage

The gate runs cosmic-ray via `sys.executable`, so run it inside an environment
that has **cosmic-ray + pytest** available:

```bash
# From the repo root — mutate the changed files of a package vs origin/main,
# running THAT package's own suite as the kill oracle:
uv run --python 3.11 --with cosmic-ray==8.4.6 --with pytest \
  python tools/mutation-gate/mutation_gate.py \
    --base origin/main \
    --include tools/mutation-gate/ \
    --test-command "{python} -m pytest -x -q -m 'not demo' tools/mutation-gate/tests/test_mutation_gate.py"
```

Key flags (`--help` for all):

| flag | meaning |
|---|---|
| `--base` | diff base ref (default `origin/main`); scope is `<base>...HEAD` |
| `--repo-root` | dir to run git + cosmic-ray in (default `.`) |
| `--test-command` | cosmic-ray test command; `{python}` is substituted with the (quoted) interpreter |
| `--include` | only mutate paths under this prefix/file (repeatable) |
| `--exclude` | skip paths containing this marker (repeatable; replaces the vendored-tree defaults) |
| `--files` | explicit file(s), bypassing git (repeatable) — used by the self-demo |
| `--python` | interpreter for the test command (default: the one running the gate) |
| `--include-tests` | also mutate test files (off by default) |
| `--json <path>` | write a machine-readable summary |

Exit code: `0` = no survivors; `1` = at least one survivor (report on stdout);
`2` = a tool (git/cosmic-ray) failed to run.

> Note: `{python}` **must** stay in the test command. cosmic-ray runs it in a fresh
> subprocess; a bare `python` can resolve to an interpreter without pytest, which
> makes every mutant read as falsely *killed* (a silent detector failure the gate's
> own design avoids by injecting `sys.executable`).

## Self-demo — see it go RED then GREEN

`sample/` holds a tiny module and two suites at **100% line coverage**:

```bash
cd tools/mutation-gate/sample
# WEAK suite -> a mutant SURVIVES -> gate exits non-zero:
uv run --python 3.11 --with cosmic-ray==8.4.6 --with pytest \
  python ../mutation_gate.py --files threshold.py \
    --test-command "{python} -m pytest -x -q test_threshold_weak.py"

# STRONG suite -> the mutant is killed -> gate exits zero:
uv run --python 3.11 --with cosmic-ray==8.4.6 --with pytest \
  python ../mutation_gate.py --files threshold.py \
    --test-command "{python} -m pytest -x -q test_threshold_strong.py"
```

The weak suite leaves `>=  ->  >` (the off-by-one boundary) **and**
`DEFAULT_MIN_BYTES -> 1025/1023` alive; the strong suite pins the default with
*literal* values (a symbolic reference would move with the mutation) and checks the
`==` boundary, killing all of them. Both states are asserted by the `demo` tests
in `tests/test_mutation_gate_demo.py`.

## Where it fits: the smallest-check-ladder, tier L2.5

The `smallest-check-ladder` runs the smallest test that could still catch a change:

| tier | check |
|---|---|
| L0 | lint the edited file |
| L1 | impacted tests (deterministic selection) |
| L2 | full suite |
| **L2.5** | **TG-2 — diff-scoped mutation gate on the changed files** |
| L3 | e2e |

**L2.5 runs *after* L2 is green** (the suite must pass before it is meaningful to ask
whether it would *notice* a break) and *before* the heavier L3 e2e. It is proportionate
because it is diff-scoped — it mutates only what the change touched, not the tree.
Trigger it when a change adds/edits pure logic and you want proof the new tests
actually assert behaviour (not just execute it).

## Opt-in CI wire-in (NOT installed)

TG-2 adds no CI gate on its own (additive + opt-in; the toolchain's gate set is a
closed charter). Two independent things can be wired in, each opt-in:

**(a) The gate's OWN fast unit suite** — to enforce its 100% line+branch coverage in
CI, add a step to the `test-python` job in `.github/workflows/quality.yml`, reusing the
existing `gate-tests-coverage` charter slug (so `.quality/charter_check.sh` stays
consistent with no `charter.yml` edit — the same pattern the repomap / search-expansion
/ closed-batch suites already use):

```yaml
      - name: gate-tests-coverage mutation-gate (diff-scoped mutation gate, unit suite)
        working-directory: tools/mutation-gate
        run: |
          pip install pytest pytest-cov
          pytest -m "not demo" --cov=mutation_gate --cov-branch \
            --cov-report=term-missing --cov-fail-under=100
```

**(b) The mutation check ITSELF** on changed files — heavier (installs cosmic-ray and
needs full git history + the target package's deps). Keep it a *separate, non-required*
workflow; never fold it into the required `quality` gate:

```yaml
# .github/workflows/mutation-gate-tg2.yml  (opt-in; keep it non-required)
name: mutation-gate-tg2
on: { workflow_dispatch: {}, pull_request: { paths: ["tools/mutation-gate/**"] } }
permissions: { contents: read }
jobs:
  tg2:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }            # full history for the diff base
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install cosmic-ray==8.4.6 pytest pytest-cov
      - run: |
          # Dogfood: mutate the changed gate module, kill-oracle = its own unit suite.
          python tools/mutation-gate/mutation_gate.py \
            --base "origin/${{ github.base_ref || 'main' }}" \
            --include tools/mutation-gate/ \
            --test-command "{python} -m pytest -x -q -m 'not demo' tools/mutation-gate/tests/test_mutation_gate.py"
```

For any other package, point `--include` at its changed tree and `--test-command` at
the suite that covers it (the toolchain runs each suite explicitly; there is no
repo-wide pytest autodiscovery).

## Developing this gate

```bash
cd tools/mutation-gate
# Fast unit suite (no git, no cosmic-ray) — 100% line+branch on the gate module:
uv run --python 3.11 --with pytest --with pytest-cov \
  python -m pytest -m "not demo" --cov=mutation_gate --cov-branch --cov-report=term-missing
# Real RED/GREEN + real-git scoping proof (needs cosmic-ray):
uv run --python 3.11 --with cosmic-ray==8.4.6 --with pytest \
  python -m pytest -m demo
# Lint + format (pinned ruff, matches the repo's quality gate; line-length 88):
uvx ruff@0.15.17 check tools/mutation-gate/ && uvx ruff@0.15.17 format --check tools/mutation-gate/
```
