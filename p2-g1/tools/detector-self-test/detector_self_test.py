"""TG-1 - detector self-test: a both-states fixture gate for harness detectors.

A *detector* is any check that must FIRE on a broken input and stay SILENT on a
fixed one - a linter rule, a security guard, a validator, a hook predicate. A
detector that is silent-in-both measures nothing; one that fires-in-both alarms
on everything. Either is a broken instrument that a green coverage number will
happily hide (single-signal-verification section 3b, "the both-states test").
This module MECHANIZES that rule: it discovers ``<detector>/broken/`` +
``<detector>/fixed/`` fixture pairs under a root and, for each, asserts the
detector FIRES on broken and is SILENT on fixed. It is mutation-testing applied
to the harness's own instruments.

Fixture layout (a "detector case")::

    <root>/<name>/
        detector.py       # defines ``detect(target: Path) -> object`` (truthy == fired)
        broken/...        # input the detector MUST fire on
        fixed/...         # input the detector MUST stay silent on

Two entrypoints ride the same core: a pytest plugin (``pytest_generate_tests``,
re-exported by a one-line ``conftest.py``) that emits one both-states test per
detector, and a CLI (``python detector_self_test.py``) that exits non-zero on
any failure - suitable for a Stop-hook self-check or a CI job.
"""

from __future__ import annotations

import argparse
import os
import runpy
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

ENV_ROOT = "DETECTOR_SELF_TEST_ROOT"


class Outcome(Enum):
    """The verdict of a detector's both-states self-test."""

    PASS = "pass"
    SILENT_IN_BOTH = "silent-in-both"
    FIRING_IN_BOTH = "firing-in-both"
    INVERTED = "inverted"
    MISSING_FIXTURE = "missing-fixture"
    BROKEN_DETECTOR = "broken-detector"


class DetectorContractError(Exception):
    """A detector module does not satisfy the ``detect()`` contract."""


@dataclass(frozen=True)
class DetectorCase:
    """One detector under test and the location of its both-states fixtures."""

    name: str
    path: Path
    detector_file: Path
    broken_dir: Path
    fixed_dir: Path


@dataclass(frozen=True)
class Result:
    """The verdict of evaluating a single :class:`DetectorCase`."""

    case_name: str
    outcome: Outcome
    message: str

    @property
    def passed(self) -> bool:
        return self.outcome is Outcome.PASS


@dataclass
class PairResult:
    ok: bool
    silent_on_good: bool
    fires_on_bad: bool
    good_output: Any
    bad_output: Any
    notes: list[str]


def run_both_states(
    detector: Callable[..., Any],
    good: Any,
    bad: Any,
    *,
    is_silent: Callable[[Any], bool] | None = None,
    is_fire: Callable[[Any], bool] | None = None,
) -> PairResult:
    """Callable both-states helper used by IMP-0148 (good then planted-bad)."""
    good_output = detector(good)
    bad_output = detector(bad)
    silent = bool(is_silent(good_output)) if is_silent else not bool(good_output)
    fire = bool(is_fire(bad_output)) if is_fire else bool(bad_output)
    notes: list[str] = []
    if not silent:
        notes.append("good-not-silent")
    if not fire:
        notes.append("bad-did-not-fire")
    return PairResult(
        ok=silent and fire,
        silent_on_good=silent,
        fires_on_bad=fire,
        good_output=good_output,
        bad_output=bad_output,
        notes=notes,
    )


def default_root() -> Path:
    """Return the fixtures root: the ``$DETECTOR_SELF_TEST_ROOT`` override, else
    the bundled ``examples/`` directory next to this module."""
    override = os.environ.get(ENV_ROOT)
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "examples"


def discover(root: Path) -> list[DetectorCase]:
    """Find every detector case (a directory holding a ``detector.py``) under ``root``.

    A ``detector.py`` that lives *inside* a ``broken/`` or ``fixed/`` fixture is
    skipped, so fixture contents can never masquerade as a detector case.
    """
    if not root.is_dir():
        return []
    cases: list[DetectorCase] = []
    for detector_file in sorted(root.rglob("detector.py")):
        parts = detector_file.relative_to(root).parts
        if "broken" in parts or "fixed" in parts:
            continue
        case_dir = detector_file.parent
        cases.append(
            DetectorCase(
                name=case_dir.relative_to(root).as_posix(),
                path=case_dir,
                detector_file=detector_file,
                broken_dir=case_dir / "broken",
                fixed_dir=case_dir / "fixed",
            )
        )
    return cases


def _has_fixture_files(directory: Path) -> bool:
    """True iff ``directory`` exists and contains at least one file."""
    if not directory.is_dir():
        return False
    return any(child.is_file() for child in directory.rglob("*"))


def load_detector(case: DetectorCase) -> Callable[[Path], object]:
    """Load ``detect`` from the case's ``detector.py`` (run in an isolated namespace)."""
    namespace = runpy.run_path(str(case.detector_file))
    detect = namespace.get("detect")
    if not callable(detect):
        raise DetectorContractError(
            f"{case.detector_file} does not define a callable detect()"
        )
    return detect


def _classify(case_name: str, fired_on_broken: bool, fired_on_fixed: bool) -> Result:
    """Map the (broken, fixed) firing pair onto an :class:`Outcome`."""
    if fired_on_broken and not fired_on_fixed:
        return Result(case_name, Outcome.PASS, "fires on broken, silent on fixed")
    if not fired_on_broken and not fired_on_fixed:
        return Result(
            case_name,
            Outcome.SILENT_IN_BOTH,
            "silent on BOTH fixtures - the detector measures nothing",
        )
    if fired_on_broken and fired_on_fixed:
        return Result(
            case_name,
            Outcome.FIRING_IN_BOTH,
            "fires on BOTH fixtures - the detector always alarms",
        )
    return Result(
        case_name,
        Outcome.INVERTED,
        "fires on fixed but not broken - the detector is inverted",
    )


def evaluate(case: DetectorCase) -> Result:
    """Run the detector against both fixtures and classify the outcome."""
    if not _has_fixture_files(case.broken_dir):
        return Result(
            case.name,
            Outcome.MISSING_FIXTURE,
            f"no broken fixtures at {case.broken_dir}",
        )
    if not _has_fixture_files(case.fixed_dir):
        return Result(
            case.name, Outcome.MISSING_FIXTURE, f"no fixed fixtures at {case.fixed_dir}"
        )
    try:
        detect = load_detector(case)
        fired_on_broken = bool(detect(case.broken_dir))
        fired_on_fixed = bool(detect(case.fixed_dir))
    except (
        Exception
    ) as exc:  # detector code is untrusted: surface any failure as a self-test failure
        return Result(
            case.name,
            Outcome.BROKEN_DETECTOR,
            f"detector raised {type(exc).__name__}: {exc}",
        )
    return _classify(case.name, fired_on_broken, fired_on_fixed)


def run(root: Path) -> list[Result]:
    """Evaluate every detector case discovered under ``root``."""
    return [evaluate(case) for case in discover(root)]


def format_line(result: Result) -> str:
    """Render a terminal-state line: ``SUCCESS:<name>`` or ``FAILED:<name>``."""
    status = "SUCCESS" if result.passed else "FAILED"
    return f"{status}:{result.case_name} [{result.outcome.value}] {result.message}"


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: evaluate all detectors under the root and return an exit code."""
    parser = argparse.ArgumentParser(
        prog="detector-self-test",
        description="Both-states self-test for harness detectors (fires-on-broken, silent-on-fixed).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help=f"fixtures root (default: bundled examples/, overridable via ${ENV_ROOT})",
    )
    args = parser.parse_args(argv)
    root = args.root if args.root is not None else default_root()

    cases = discover(root)
    if not cases:
        print(
            f"FAILED:detector-self-test [no-cases] no detector fixtures discovered under {root}"
        )
        return 1

    results = [evaluate(case) for case in cases]
    failures = 0
    for result in results:
        print(format_line(result))
        if not result.passed:
            failures += 1
    print(
        f"detector-self-test: {len(results) - failures}/{len(results)} detectors passed the both-states self-test"
    )
    return 1 if failures else 0


def pytest_generate_tests(metafunc: Any) -> None:
    """Pytest hook: parametrize a ``detector_case`` argument with every discovered detector."""
    if "detector_case" not in metafunc.fixturenames:
        return
    cases = discover(default_root())
    metafunc.parametrize("detector_case", cases, ids=[case.name for case in cases])


if __name__ == "__main__":
    raise SystemExit(main())
