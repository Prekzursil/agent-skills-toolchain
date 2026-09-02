#!/usr/bin/env python3
"""Both-states tests for the TST-0038 work-unit conformance contract.

Runs under pytest (quality.yml collects tools/command-center/tests) and under
``command-center/p2-wave/probes/TST-0038/run_suite.py``, which calls every
``test_*`` function directly and hands a fresh directory to the ones that
take ``tmp_path``.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CC = HERE.parent
if str(CC) not in sys.path:
    sys.path.insert(0, str(CC))

import work_unit_conformance as wuc  # noqa: E402


def _rules(violations: list[dict]) -> set[str]:
    return {row["rule"] for row in violations}


def test_conforming_catalog_is_silent() -> None:
    green = wuc.conforming_catalog()
    assert wuc.check_catalog(green) == []
    assert wuc.check_catalog(green, require_complete=True, enforce_enums=True) == []
    matrix = wuc.presence_matrix(green)
    assert matrix["n_fields"] == 19
    for name in ("items", "work_units"):
        col = matrix["collections"][name]
        assert col["n"] == 1
        assert all(row["on_unit"] == 1 for row in col["per_field"].values())


def test_defaults_only_catalog_is_red() -> None:
    red = wuc.defaults_only_catalog()
    violations = wuc.check_catalog(red)
    assert _rules(violations) == {"R-DEFAULTS-NOT-COMPLETE"}
    assert {row["field"] for row in violations} == set(wuc.DEFAULT_ONLY_EXPECTED)
    assert len(violations) == 11
    # The historical reading (defaults count as resolution) is silent.
    assert wuc.check_catalog(red, require_complete=False) == []
    assert wuc.defaults_only_fields(red) == [
        f for f in wuc.WORK_UNIT_FIELDS if f in wuc.DEFAULT_ONLY_EXPECTED
    ]


def test_missing_key_is_red() -> None:
    missing = wuc.conforming_catalog()
    missing["items"][0].pop("title")
    violations = wuc.check_catalog(missing)
    assert _rules(violations) == {"R-PER-UNIT-KEY"}
    assert violations[0]["field"] == "title"
    # A missing key is a hole even under the historical reading.
    assert _rules(wuc.check_catalog(missing, require_complete=False)) == {"R-PER-UNIT-KEY"}


def test_empty_string_is_red() -> None:
    green = wuc.conforming_catalog()
    for empty in ("", "   ", None):
        bad = copy.deepcopy(green)
        bad["items"][0]["title"] = empty
        assert _rules(wuc.check_catalog(bad)) == {"R-EMPTY-REJECTED"}, repr(empty)
    # Empty containers and falsy scalars are values, not emptiness.
    ok = copy.deepcopy(green)
    ok["items"][0]["dependencies"] = []
    ok["items"][0]["owner_approval_required"] = False
    ok["items"][0]["timeout_seconds"] = 0
    assert wuc.check_catalog(ok) == []


def test_unknown_substrate_is_red() -> None:
    bad = wuc.conforming_catalog()
    bad["items"][0]["execution_substrate"] = "quantum-substrate"
    assert _rules(wuc.check_catalog(bad)) == {"R-SUBSTRATE-ENUM"}
    assert wuc.check_catalog(bad, enforce_enums=False) == []
    for substrate in sorted(wuc.EXECUTION_SUBSTRATES):
        good = wuc.conforming_catalog()
        good["items"][0]["execution_substrate"] = substrate
        assert wuc.check_catalog(good) == [], substrate


def test_unknown_failure_class_is_red() -> None:
    bad = wuc.conforming_catalog()
    bad["items"][0]["failure_classification"] = ["overclaim", "not-a-real-class-xyzzy"]
    violations = wuc.check_catalog(bad)
    assert _rules(violations) == {"R-FAILURE-ENUM"}
    assert "not-a-real-class-xyzzy" in violations[0]["message"]
    assert "overclaim" not in violations[0]["message"].split("not in")[0]
    assert wuc.check_catalog(bad, enforce_enums=False) == []


def test_alias_keys_count_as_present() -> None:
    aliased = wuc.conforming_catalog()
    unit = aliased["work_units"][0]
    unit["assigned_model_vendor_role"] = unit.pop("assignment")
    unit["question_or_target"] = unit.pop("target")
    assert wuc.check_catalog(aliased) == []
    matrix = wuc.presence_matrix(aliased)
    wu = matrix["collections"]["work_units"]["per_field"]
    assert wu["assignment"] == {
        "n": 1, "item": 0, "alias": 1, "on_unit": 1, "absent": 0, "empty": 0, "defaults": 0
    }
    assert wu["target"]["alias"] == 1 and wu["target"]["on_unit"] == 1
    red = wuc.presence_matrix(wuc.defaults_only_catalog())["collections"]["items"]
    assert red["per_field"]["assignment"] == {
        "n": 1, "item": 0, "alias": 0, "on_unit": 0, "absent": 0, "empty": 0, "defaults": 1
    }
    hole = wuc.conforming_catalog()
    hole["items"][0].pop("phase")
    assert wuc.presence_matrix(hole)["collections"]["items"]["per_field"]["phase"]["absent"] == 1


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_bare_cli_rejects_defaults_only(tmp_path: Path) -> None:
    red = _write(tmp_path, "red.json", wuc.defaults_only_catalog())
    assert wuc.main(["--catalog", str(red), "--items-only"]) == 1
    assert wuc.main(["--catalog", str(red)]) == 1
    # Only the explicit disarm flag silences the defaults-only state.
    assert wuc.main(["--catalog", str(red), "--items-only", "--allow-defaults"]) == 0


def test_bare_cli_accepts_conforming(tmp_path: Path) -> None:
    green = _write(tmp_path, "green.json", wuc.conforming_catalog())
    assert wuc.main(["--catalog", str(green), "--items-only"]) == 0
    assert wuc.main(["--catalog", str(green)]) == 0
    substrate = wuc.conforming_catalog()
    substrate["work_units"][0]["execution_substrate"] = "quantum-substrate"
    bad = _write(tmp_path, "substrate.json", substrate)
    assert wuc.main(["--catalog", str(bad), "--items-only"]) == 0
    assert wuc.main(["--catalog", str(bad), "--work-units-only"]) == 1
    assert wuc.main(["--catalog", str(bad), "--no-enums"]) == 0
