---
title: README
type: note
permalink: dqverify-repo-20261013/tools/detector-self-test/readme
---

# TG-1 · detector self-test

A **both-states fixture gate** for the estate's harness detectors, hooks, and
gates. It mechanizes the single-signal-verification §3b rule ("the both-states
test") and is mutation-testing applied to the harness's own instruments.

## The problem it closes

A *detector* is any check that is supposed to **FIRE** on a broken input and stay
**SILENT** on a fixed one — a linter rule, a security guard, a validator, a hook
predicate, a CI grep. Two silent failure modes routinely ship green:

- **silent-in-both** — the detector never fires, so it catches nothing. Its
  silence on real input reads as "clean". (Ledger: a `codex exec` probe that
  printed no error in the broken state *or* the fixed state — it measured nothing.)
- **firing-in-both** — the detector always fires, so its signal is noise.

100% line coverage does **not** catch either: coverage proves a line *ran*, never
that the detector would *fire when it should and stay quiet when it shouldn't*.
This gate does, by running each detector against a known-broken **and** a
known-fixed fixture and asserting the two disagree in the right direction.

## Fixture layout

Each detector under test is a directory holding a `detector.py` plus a
`broken/` + `fixed/` fixture pair:

```
<root>/<name>/
    detector.py       # def detect(target: Path) -> object   (truthy == fired)
    broken/…          # input the detector MUST fire on
    fixed/…           # input the detector MUST stay silent on
```

`detect(target)` returns a **truthy** value (typically a non-empty list of
findings) when it detects the problem, and a **falsy** value (empty list / False
/ None) when the input is clean. See the worked examples in [`examples/`](examples):

- **`debug_print`** — flags a leftover `print()` in a Python source.
- **`todo_marker`** — blocks on a leftover `XXX-DO-NOT-SHIP` marker.

## Outcomes

| outcome | broken | fixed | verdict |
|---|---|---|---|
| `pass` | fires | silent | ✅ correctly wired |
| `silent-in-both` | silent | silent | ❌ measures nothing |
| `firing-in-both` | fires | fires | ❌ always alarms |
| `inverted` | silent | fires | ❌ backwards |
| `missing-fixture` | — | — | ❌ a `broken/` or `fixed/` fixture is absent/empty |
| `broken-detector` | — | — | ❌ `detector.py` has no `detect()` or it raised |

A root with **zero** discovered detectors also fails — a self-check that finds
nothing to check is itself silent-in-both.

## Two entrypoints (same core)

**CLI** — for a Stop-hook self-check or a shell/CI step. Exits non-zero on any
failure:

```bash
python tools/detector-self-test/detector_self_test.py            # bundled examples/
python tools/detector-self-test/detector_self_test.py --root PATH # your own root
# or point the default root at your fixtures:
DETECTOR_SELF_TEST_ROOT=/path/to/fixtures python tools/detector-self-test/detector_self_test.py
```

**pytest plugin** — emits one both-states test per discovered detector. A
one-line `conftest.py` re-exports the hook (see this directory's `conftest.py`):

```python
# conftest.py
from detector_self_test import pytest_generate_tests  # noqa: F401

# test_detectors.py
def test_both_states(detector_case):
    from detector_self_test import Outcome, evaluate
    result = evaluate(detector_case)
    assert result.outcome is Outcome.PASS, result.message
```

## Opt-in, not wired into the blocking gate

This is a **new gate detectors can opt into** — it does not modify any existing
hook, workflow, or the repo's `quality` charter. Wire it where you want it:

- **CI (toolchain convention):** this repo runs one lean `quality` workflow whose
  `test-python` job names each stdlib-only, 100%-coverage tool as its own step
  (see `.github/workflows/quality.yml`, e.g. the `stdin-server` step). To opt this
  gate in, add a step to that job — reuse the existing `gate-tests-coverage`
  charter slug so `.quality/charter_check.sh` stays consistent with **no**
  `charter.yml` edit:

  ```yaml
      # tools/detector-self-test — the both-states self-test for harness detectors.
      # Stdlib-only, so only pytest+pytest-cov are installed; the harness holds ITSELF
      # to 100% line+branch, and the both-states CLI runs over the committed examples.
      # Reuses the gate-tests-coverage charter slug on purpose (not a new gate).
      - name: gate-tests-coverage detector-self-test (self-coverage + both-states CLI)
        working-directory: tools/detector-self-test
        run: |
          pip install pytest pytest-cov
          pytest --cov=detector_self_test --cov-branch --cov-report=term-missing --cov-fail-under=100
          python detector_self_test.py
  ```

- **Stop-hook:** call the CLI; a non-zero exit blocks completion.

## Self-verification (this harness eats its own dogfood)

```bash
cd tools/detector-self-test
python -m pytest --cov=detector_self_test --cov-branch --cov-fail-under=100
```

100% line **and** branch coverage, and the suite is mutation-checked: reverting
the core discrimination (`and` → `or` in `_classify`) flips the silent-in-both,
firing-in-both, and CLI-failure tests RED — proof the tests assert behavior, not
just execute lines.