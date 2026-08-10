"""Both-states controls for the collection floor. TST-0350's four required tests.

A floor that has never been shown to FAIL is indistinguishable from no floor, so every assertion
here comes in a pair: the guard must fire on the bad state AND stay silent on the good one.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import suitefloor as sf  # noqa: E402


def test_zero_collected_fails_pointed_at_an_empty_directory(tmp_path: Path) -> None:
    """TST-0350 test 1. The whole defect: pytest exits 0 over nothing and reads as green."""
    empty = tmp_path / "nothing"
    empty.mkdir()
    count, _ = sf.collect_count(str(empty), cwd=tmp_path)
    assert count == 0

    suite = sf.Suite(
        "phantom", str(empty), minimum=10, observed_when_set=0, note="fixture"
    )
    ok, observed, reason = sf.check_suite(suite, cwd=tmp_path)
    assert ok is False
    assert observed == 0
    assert "NOTHING" in reason


def test_below_minimum_fails_on_a_real_but_shrunken_suite(tmp_path: Path) -> None:
    """TST-0350 test 2: a PARTIAL collapse, which a `> 0` check would wave through."""
    pkg = tmp_path / "mini"
    pkg.mkdir()
    (pkg / "test_two.py").write_text(
        "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n", encoding="utf-8"
    )
    count, _ = sf.collect_count(str(pkg), cwd=tmp_path)
    assert count == 2, f"fixture should collect 2, collected {count}"

    # A floor of 100 against 2 collected is the shrunken-suite case.
    strict = sf.Suite(
        "mini", str(pkg), minimum=100, observed_when_set=100, note="fixture"
    )
    ok, observed, reason = sf.check_suite(strict, cwd=tmp_path)
    assert ok is False
    assert observed == 2
    assert "below the declared floor" in reason


def test_a_normal_run_passes_so_the_floor_is_not_a_nuisance_gate(
    tmp_path: Path,
) -> None:
    """TST-0350 test 3. A gate that fails on legitimate growth gets disabled, so this matters."""
    pkg = tmp_path / "mini"
    pkg.mkdir()
    (pkg / "test_two.py").write_text(
        "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n", encoding="utf-8"
    )
    lenient = sf.Suite("mini", str(pkg), minimum=2, observed_when_set=2, note="fixture")
    ok, observed, reason = sf.check_suite(lenient, cwd=tmp_path)
    assert ok is True
    assert observed == 2
    assert "floor" in reason


def test_a_collection_error_is_treated_as_zero_not_as_a_pass(tmp_path: Path) -> None:
    """The clone defect in miniature: an import error must not read as a healthy small suite."""
    pkg = tmp_path / "broken"
    pkg.mkdir()
    (pkg / "test_importerror.py").write_text(
        "import a_module_that_does_not_exist_anywhere\n\n\ndef test_x():\n    pass\n",
        encoding="utf-8",
    )
    count, _ = sf.collect_count(str(pkg), cwd=tmp_path)
    assert count == 0, "a collection error must yield 0, so the floor rejects it"
    suite = sf.Suite("broken", str(pkg), minimum=1, observed_when_set=1, note="fixture")
    ok, _, _ = sf.check_suite(suite, cwd=tmp_path)
    assert ok is False


# --------------------------------------------------------------------------- non-pytest half


def test_require_nonempty_rejects_an_empty_measurement() -> None:
    """TST-0350 test 4: the rule is not pytest-specific.

    Two benchmarks on this estate returned a clean green over EMPTY inputs. That is the same defect
    wearing different clothes.
    """
    with pytest.raises(ValueError, match="below the required minimum"):
        sf.require_nonempty(0, "census over tracked files")


def test_require_nonempty_accepts_a_real_measurement() -> None:
    sf.require_nonempty(1, "census over tracked files")
    sf.require_nonempty(4187, "semgrep file walk")


def test_require_nonempty_enforces_a_floor_above_one() -> None:
    with pytest.raises(ValueError):
        sf.require_nonempty(3, "blueprint corpus", minimum=96)


# --------------------------------------------------------------------------- registry integrity


def test_every_registered_suite_declares_a_floor_below_its_observed_count() -> None:
    """A floor at or above the observed count is a nuisance gate; at zero it is not a gate."""
    assert sf.SUITES, "the registry must not be empty - an empty registry gates nothing"
    for suite in sf.SUITES:
        assert suite.minimum > 0, f"{suite.name} has a zero floor, which cannot fail"
        assert suite.minimum <= suite.observed_when_set, (
            f"{suite.name} floor {suite.minimum} exceeds the count observed when it was set "
            f"({suite.observed_when_set}) - it would fail on the very run that justified it"
        )
        assert suite.note.strip(), (
            f"{suite.name} must state why its margin is what it is"
        )


def test_unregistered_paths_are_reported_as_a_finding() -> None:
    """TST-0350: 'a suite with no declared minimum is itself a finding'."""
    assert sf.unregistered(["platform"]) == []
    assert sf.unregistered(["tools/nowhere"]) == ["tools/nowhere"]


def test_unknown_suite_name_fails_closed() -> None:
    assert sf.suite_by_name("platform") is not None
    assert sf.suite_by_name("no-such-suite") is None
    assert sf.main(["--suite", "no-such-suite"]) == 1


def test_cli_refuses_with_no_selection() -> None:
    assert sf.main([]) == 1


def test_cli_list_exits_zero() -> None:
    assert sf.main(["--list"]) == 0


def test_the_module_is_runnable_as_a_script() -> None:
    """The CI gate calls it as a script, so `python suitefloor.py --list` must work."""
    proc = subprocess.run(
        [sys.executable, str(Path(sf.__file__)), "--list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "platform" in proc.stdout
