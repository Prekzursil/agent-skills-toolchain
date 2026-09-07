"""Unit tests for the detector self-test harness (tools/detector-self-test).

These exercise discovery, the both-states classification (every outcome), the
detector-loading contract, the CLI entrypoint, and the pytest hook — and prove
the harness FAILS, with a clear message, for a silent-in-both detector, a
firing-in-both detector, an inverted detector, a missing-fixture case, and a
broken detector. This is the gem eating its own dogfood: mutation-testing
applied to the harness's own instrument.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import detector_self_test as dst
import pytest
from detector_self_test import (
    DetectorCase,
    DetectorContractError,
    Outcome,
    Result,
    default_root,
    discover,
    evaluate,
    format_line,
    load_detector,
    main,
    run,
)

EXAMPLES = Path(dst.__file__).resolve().parent / "examples"

# A detector whose firing is driven purely by fixture CONTENT (the literal
# "BAD"): pointing it at different broken/fixed contents yields every outcome.
_MARKER_DETECTOR = (
    "from pathlib import Path\n"
    "def detect(target):\n"
    "    files = (p for p in target.rglob('*') if p.is_file())\n"
    "    return [str(p) for p in files if 'BAD' in p.read_text(encoding='utf-8')]\n"
)


def _make_case(
    root: Path,
    name: str,
    *,
    detector_src: str = _MARKER_DETECTOR,
    broken: dict[str, str] | None,
    fixed: dict[str, str] | None,
) -> DetectorCase:
    """Write a synthetic detector case under ``root`` and return its DetectorCase.

    ``broken``/``fixed`` map filename -> content; ``None`` omits the directory
    entirely, an empty dict creates the directory with no files.
    """
    case_dir = root / name
    case_dir.mkdir(parents=True)
    (case_dir / "detector.py").write_text(detector_src, encoding="utf-8")
    for sub, files in (("broken", broken), ("fixed", fixed)):
        if files is None:
            continue
        directory = case_dir / sub
        directory.mkdir()
        for fname, content in files.items():
            (directory / fname).write_text(content, encoding="utf-8")
    return DetectorCase(
        name=name,
        path=case_dir,
        detector_file=case_dir / "detector.py",
        broken_dir=case_dir / "broken",
        fixed_dir=case_dir / "fixed",
    )


# --------------------------------------------------------------------------- #
# classify — the four both-states outcomes
# --------------------------------------------------------------------------- #
def test_pass_when_fires_on_broken_and_silent_on_fixed(tmp_path: Path) -> None:
    case = _make_case(
        tmp_path, "ok", broken={"f.txt": "has BAD here"}, fixed={"f.txt": "all clean"}
    )
    result = evaluate(case)
    assert result.outcome is Outcome.PASS
    assert result.passed is True


def test_silent_in_both_fails_with_clear_message(tmp_path: Path) -> None:
    case = _make_case(
        tmp_path, "silent", broken={"f.txt": "clean"}, fixed={"f.txt": "clean"}
    )
    result = evaluate(case)
    assert result.outcome is Outcome.SILENT_IN_BOTH
    assert result.passed is False
    assert "measures nothing" in result.message


def test_firing_in_both_fails_with_clear_message(tmp_path: Path) -> None:
    case = _make_case(
        tmp_path, "firing", broken={"f.txt": "BAD"}, fixed={"f.txt": "also BAD"}
    )
    result = evaluate(case)
    assert result.outcome is Outcome.FIRING_IN_BOTH
    assert "always" in result.message


def test_inverted_fails_with_clear_message(tmp_path: Path) -> None:
    case = _make_case(
        tmp_path, "inverted", broken={"f.txt": "clean"}, fixed={"f.txt": "BAD"}
    )
    result = evaluate(case)
    assert result.outcome is Outcome.INVERTED
    assert "inverted" in result.message


# --------------------------------------------------------------------------- #
# missing / empty fixtures
# --------------------------------------------------------------------------- #
def test_missing_broken_dir_fails(tmp_path: Path) -> None:
    case = _make_case(tmp_path, "nobrk", broken=None, fixed={"f.txt": "clean"})
    result = evaluate(case)
    assert result.outcome is Outcome.MISSING_FIXTURE
    assert "broken" in result.message


def test_missing_fixed_dir_fails(tmp_path: Path) -> None:
    case = _make_case(tmp_path, "nofix", broken={"f.txt": "BAD"}, fixed=None)
    result = evaluate(case)
    assert result.outcome is Outcome.MISSING_FIXTURE
    assert "fixed" in result.message


def test_empty_broken_dir_fails(tmp_path: Path) -> None:
    case = _make_case(tmp_path, "emptybrk", broken={}, fixed={"f.txt": "clean"})
    result = evaluate(case)
    assert result.outcome is Outcome.MISSING_FIXTURE


# --------------------------------------------------------------------------- #
# broken detector (untrusted code failures are surfaced, never crash the gate)
# --------------------------------------------------------------------------- #
def test_broken_detector_without_detect_callable(tmp_path: Path) -> None:
    case = _make_case(
        tmp_path,
        "nodef",
        detector_src="x = 1\n",
        broken={"f.txt": "BAD"},
        fixed={"f.txt": "clean"},
    )
    result = evaluate(case)
    assert result.outcome is Outcome.BROKEN_DETECTOR


def test_broken_detector_detect_raises(tmp_path: Path) -> None:
    src = "def detect(target):\n    raise RuntimeError('boom')\n"
    case = _make_case(
        tmp_path,
        "raiser",
        detector_src=src,
        broken={"f.txt": "BAD"},
        fixed={"f.txt": "clean"},
    )
    result = evaluate(case)
    assert result.outcome is Outcome.BROKEN_DETECTOR
    assert "RuntimeError" in result.message


def test_broken_detector_import_raises(tmp_path: Path) -> None:
    case = _make_case(
        tmp_path,
        "importboom",
        detector_src="raise RuntimeError('import boom')\n",
        broken={"f.txt": "BAD"},
        fixed={"f.txt": "clean"},
    )
    result = evaluate(case)
    assert result.outcome is Outcome.BROKEN_DETECTOR


# --------------------------------------------------------------------------- #
# load_detector contract
# --------------------------------------------------------------------------- #
def test_load_detector_returns_callable(tmp_path: Path) -> None:
    case = _make_case(tmp_path, "ld", broken={"f.txt": "BAD"}, fixed={"f.txt": "clean"})
    detect = load_detector(case)
    assert callable(detect)
    assert detect(case.broken_dir)
    assert not detect(case.fixed_dir)


def test_load_detector_raises_on_non_callable_detect(tmp_path: Path) -> None:
    case = _make_case(
        tmp_path,
        "notcallable",
        detector_src="detect = 5\n",
        broken={"f.txt": "BAD"},
        fixed={"f.txt": "x"},
    )
    with pytest.raises(DetectorContractError):
        load_detector(case)


# --------------------------------------------------------------------------- #
# _has_fixture_files
# --------------------------------------------------------------------------- #
def test_has_fixture_files_missing_dir(tmp_path: Path) -> None:
    assert dst._has_fixture_files(tmp_path / "nope") is False


def test_has_fixture_files_empty_dir(tmp_path: Path) -> None:
    directory = tmp_path / "empty"
    directory.mkdir()
    assert dst._has_fixture_files(directory) is False


def test_has_fixture_files_only_subdir_no_files(tmp_path: Path) -> None:
    (tmp_path / "sub" / "child").mkdir(parents=True)
    assert dst._has_fixture_files(tmp_path / "sub") is False


def test_has_fixture_files_with_file(tmp_path: Path) -> None:
    directory = tmp_path / "has"
    directory.mkdir()
    (directory / "f.txt").write_text("x", encoding="utf-8")
    assert dst._has_fixture_files(directory) is True


# --------------------------------------------------------------------------- #
# discover
# --------------------------------------------------------------------------- #
def test_discover_nonexistent_root_returns_empty(tmp_path: Path) -> None:
    assert discover(tmp_path / "missing") == []


def test_discover_existing_empty_root_returns_empty(tmp_path: Path) -> None:
    assert discover(tmp_path) == []


def test_discover_finds_and_sorts_cases(tmp_path: Path) -> None:
    _make_case(tmp_path, "bravo", broken={"f.txt": "BAD"}, fixed={"f.txt": "x"})
    _make_case(tmp_path, "alpha", broken={"f.txt": "BAD"}, fixed={"f.txt": "x"})
    cases = discover(tmp_path)
    assert [c.name for c in cases] == ["alpha", "bravo"]
    assert cases[0].path == tmp_path / "alpha"
    assert cases[0].detector_file == tmp_path / "alpha" / "detector.py"
    assert cases[0].broken_dir == tmp_path / "alpha" / "broken"
    assert cases[0].fixed_dir == tmp_path / "alpha" / "fixed"


def test_discover_skips_detector_inside_fixture_dir(tmp_path: Path) -> None:
    case = _make_case(
        tmp_path, "guarded", broken={"f.txt": "BAD"}, fixed={"f.txt": "x"}
    )
    # a stray detector.py sitting INSIDE the broken fixture must NOT create a case
    (case.broken_dir / "detector.py").write_text(_MARKER_DETECTOR, encoding="utf-8")
    assert [c.name for c in discover(tmp_path)] == ["guarded"]


# --------------------------------------------------------------------------- #
# default_root
# --------------------------------------------------------------------------- #
def test_default_root_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DETECTOR_SELF_TEST_ROOT", str(tmp_path))
    assert default_root() == tmp_path


def test_default_root_defaults_to_examples(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DETECTOR_SELF_TEST_ROOT", raising=False)
    root = default_root()
    assert root.name == "examples"
    assert root.parent == Path(dst.__file__).resolve().parent


# --------------------------------------------------------------------------- #
# Result / format_line
# --------------------------------------------------------------------------- #
def test_result_passed_true_only_for_pass() -> None:
    assert Result("c", Outcome.PASS, "m").passed is True
    assert Result("c", Outcome.SILENT_IN_BOTH, "m").passed is False


def test_format_line_success_for_pass() -> None:
    line = format_line(
        Result("mycase", Outcome.PASS, "fires on broken, silent on fixed")
    )
    assert line.startswith("SUCCESS:mycase")
    assert "pass" in line
    assert "fires on broken" in line


def test_format_line_failed_for_non_pass() -> None:
    line = format_line(Result("mycase", Outcome.SILENT_IN_BOTH, "nothing"))
    assert line.startswith("FAILED:mycase")
    assert "silent-in-both" in line


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #
def test_run_over_examples_all_pass() -> None:
    results = run(EXAMPLES)
    assert len(results) == 2
    assert all(r.outcome is Outcome.PASS for r in results)


def test_run_over_empty_root_returns_empty(tmp_path: Path) -> None:
    assert run(tmp_path) == []


# --------------------------------------------------------------------------- #
# main (CLI)
# --------------------------------------------------------------------------- #
def test_main_all_pass_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--root", str(EXAMPLES)])
    out = capsys.readouterr().out
    assert code == 0
    assert "SUCCESS:debug_print" in out
    assert "SUCCESS:todo_marker" in out
    assert "2/2" in out


def test_main_default_root(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DETECTOR_SELF_TEST_ROOT", raising=False)
    code = main([])
    assert code == 0
    assert "2/2" in capsys.readouterr().out


def test_main_no_cases_returns_one(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code = main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "no detector fixtures discovered" in out


def test_main_failing_detector_returns_one(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _make_case(tmp_path, "silent", broken={"f.txt": "clean"}, fixed={"f.txt": "clean"})
    code = main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "FAILED:silent" in out
    assert "0/1" in out


# --------------------------------------------------------------------------- #
# module entrypoint (__main__ guard)
# --------------------------------------------------------------------------- #
def test_module_entrypoint_invokes_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DETECTOR_SELF_TEST_ROOT", raising=False)
    monkeypatch.setattr(
        sys, "argv", ["detector-self-test"]
    )  # no --root -> default examples (all pass)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(dst.__file__, run_name="__main__")
    assert excinfo.value.code == 0


# --------------------------------------------------------------------------- #
# pytest_generate_tests hook
# --------------------------------------------------------------------------- #
class _FakeMetafunc:
    def __init__(self, fixturenames: list[str]) -> None:
        self.fixturenames = fixturenames
        self.calls: list[tuple[str, list[object], list[str]]] = []

    def parametrize(
        self, argnames: str, argvalues: list[object], *, ids: list[str]
    ) -> None:
        self.calls.append((argnames, list(argvalues), list(ids)))


def test_pytest_hook_is_noop_without_detector_case_param() -> None:
    metafunc = _FakeMetafunc(["something_else"])
    dst.pytest_generate_tests(metafunc)
    assert metafunc.calls == []


def test_pytest_hook_parametrizes_discovered_cases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _make_case(tmp_path, "only", broken={"f.txt": "BAD"}, fixed={"f.txt": "x"})
    monkeypatch.setenv("DETECTOR_SELF_TEST_ROOT", str(tmp_path))
    metafunc = _FakeMetafunc(["detector_case", "tmp_path"])
    dst.pytest_generate_tests(metafunc)
    assert len(metafunc.calls) == 1
    argnames, argvalues, ids = metafunc.calls[0]
    assert argnames == "detector_case"
    assert ids == ["only"]
    assert len(argvalues) == 1
    assert isinstance(argvalues[0], DetectorCase)


# --------------------------------------------------------------------------- #
# TST-0328 callable both-states fixture (assert_both_states / run_both_states)
# --------------------------------------------------------------------------- #
def test_assert_both_states_accepts_discriminating_detector() -> None:
    def detect(state: str) -> bool:
        return state == "broken"

    obs = dst.assert_both_states(detect, broken="broken", good="good", name="ok")
    assert obs.passed is True
    assert obs.fired_on_broken is True
    assert obs.fired_on_good is False
    assert obs.as_dict()["outcome"] == "pass"


def test_assert_both_states_rejects_silent_in_both() -> None:
    def silent(_state: str) -> bool:
        return False

    with pytest.raises(dst.BothStatesError) as excinfo:
        dst.assert_both_states(silent, broken="a", good="b", name="silent")
    assert excinfo.value.observation.outcome is Outcome.SILENT_IN_BOTH


def test_assert_both_states_rejects_firing_in_both() -> None:
    def always(_state: str) -> bool:
        return True

    with pytest.raises(dst.BothStatesError) as excinfo:
        dst.assert_both_states(always, broken="a", good="b", name="always")
    assert excinfo.value.observation.outcome is Outcome.FIRING_IN_BOTH


def test_run_both_states_records_without_raising() -> None:
    obs = dst.run_both_states(lambda s: False, broken="x", good="y", name="quiet")
    assert obs.passed is False
    assert obs.outcome is Outcome.SILENT_IN_BOTH

