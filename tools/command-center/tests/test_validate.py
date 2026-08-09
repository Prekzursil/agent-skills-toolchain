"""Both-states control for the reachability validator.

A probe that is silent in both states measures nothing
(`rules/common/single-signal-verification.md` 3b). Every check below is proved
able to go RED against a deliberately mutated catalog BEFORE its silence on the
real catalog is treated as evidence. `test_real_catalog_is_clean` is the good
state; every `test_detects_*` is the matching bad state.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import catalog as cat
import pytest
import seed
import validate as val


@pytest.fixture(scope="module")
def real() -> dict:
    return cat.load()


@pytest.fixture(scope="module")
def real_graph() -> dict:
    return json.loads(cat.graph_path().read_text(encoding="utf-8"))


def _checks(violations) -> set[str]:
    return {entry["check"] for entry in violations}


def _find(catalog: dict, item_id: str) -> dict:
    for item in catalog["items"]:
        if item["id"] == item_id:
            return item
    raise AssertionError(f"{item_id} not in catalog")


# --------------------------------------------------------------------------
# GOOD STATE
# --------------------------------------------------------------------------


def test_real_catalog_is_clean(real, real_graph):
    violations, stats = val.validate(real, graph=real_graph)
    assert violations == [], [str(entry) for entry in violations]
    assert stats["items"] == 103
    assert stats["open"] == 69
    assert stats["acyclic"] is True


def test_parser_reproduces_the_registers_own_header_counts():
    """Independent reproduction, not a re-read: the register's header asserts
    'OUTSTANDING 69 / DELIBERATELY-SKIPPED 3 / SUPERSEDED 5 / SETTLED 26' in
    prose, and the parser arrives at the same four numbers from the table rows
    without reading that sentence."""
    parsed = seed.rp.parse_file(cat.command_center_dir() / "sources" / "REGISTER.md")
    assert parsed.counts_by_prefix() == {"R-*": 69, "D-*": 3, "S-*": 5, "T-*": 26}


def test_committed_graph_equals_the_derived_graph(real, real_graph):
    assert real_graph == cat.build_graph(real)


# --------------------------------------------------------------------------
# BAD STATES - one per check
# --------------------------------------------------------------------------


def test_detects_dangling_dependency(real):
    bad = copy.deepcopy(real)
    _find(bad, "R-M01")["dependencies"] = ["R-DOES-NOT-EXIST"]
    violations, _ = val.validate(bad)
    assert "REACH-1" in _checks(violations)


def test_detects_closed_item_depending_on_open_item(real):
    bad = copy.deepcopy(real)
    _find(bad, "T-01")["dependencies"] = ["R-M01"]
    violations, _ = val.validate(bad)
    assert any(
        entry["check"] == "REACH-1" and "closed but depends" in entry["detail"] for entry in violations
    )


def test_detects_cycle(real):
    bad = copy.deepcopy(real)
    _find(bad, "R-M01")["dependencies"] = ["R-M04"]  # R-M04 already depends on R-M01
    violations, _ = val.validate(bad)
    assert "REACH-2" in _checks(violations)
    assert set(cat.find_cycle_nodes(bad)) == {"R-M01", "R-M04"}


def test_cycle_report_excludes_innocent_downstream_nodes(real):
    """R-M06 is blocked by R-M18 and is NOT in a cycle; a cycle elsewhere must
    not name it. Kahn's residual alone would over-report exactly this way."""
    bad = copy.deepcopy(real)
    _find(bad, "R-M18")["dependencies"] = ["R-M06"]
    assert set(cat.find_cycle_nodes(bad)) == {"R-M06", "R-M18"}
    _find(bad, "R-M17")["dependencies"] = ["R-M18"]
    assert "R-M17" not in cat.find_cycle_nodes(bad)


def test_detects_dead_end_open_item(real):
    bad = copy.deepcopy(real)
    item = _find(bad, "R-M08")  # no deps, no gate in the real catalog
    item["next_smallest_action"] = cat.UNKNOWN
    violations, _ = val.validate(bad)
    assert any(entry["check"] == "REACH-3" and entry["id"] == "R-M08" for entry in violations)


def test_an_open_dependency_is_a_legal_reason_to_have_no_action(real):
    """REACH-3 must not fire on a legitimately waiting item, or the whole check
    becomes noise and gets ignored."""
    bad = copy.deepcopy(real)
    _find(bad, "R-A32")["next_smallest_action"] = cat.UNKNOWN  # still depends on open R-A01
    violations, _ = val.validate(bad)
    assert not any(entry["check"] == "REACH-3" and entry["id"] == "R-A32" for entry in violations)


def test_detects_owner_gate_pointing_at_nothing(real):
    bad = copy.deepcopy(real)
    _find(bad, "R-B08")["owner_gate"] = ["OQ-999"]
    violations, _ = val.validate(bad)
    assert any(entry["check"] == "REACH-4" and entry["id"] == "R-B08" for entry in violations)


def test_a_gate_that_is_already_answered_stops_counting_as_a_blocker(real):
    bad = copy.deepcopy(real)
    for question in bad["owner_questions"]:
        if question["id"] == "OQ-6":
            question["state"] = "ANSWERED"
    _find(bad, "R-B08")["next_smallest_action"] = cat.UNKNOWN
    violations, _ = val.validate(bad)
    checks = {(entry["check"], entry["id"]) for entry in violations}
    assert ("REACH-4", "R-B08") in checks
    assert ("REACH-3", "R-B08") in checks


def test_detects_disposition_without_evidence(real):
    bad = copy.deepcopy(real)
    _find(bad, "T-05")["disposition_evidence"] = "   "
    violations, _ = val.validate(bad)
    assert any(entry["check"] == "REACH-5" and entry["id"] == "T-05" for entry in violations)


def test_detects_non_terminal_disposition(real):
    bad = copy.deepcopy(real)
    _find(bad, "T-05")["disposition"] = "PROBABLY-FINE"
    violations, _ = val.validate(bad)
    assert any(entry["check"] == "REACH-5" and "not terminal" in entry["detail"] for entry in violations)


def test_detects_a_silently_dropped_item(real):
    """The anti-forgetting invariant: deleting a row from the catalog must fail,
    because that is precisely how 69 items got lost the first time."""
    bad = copy.deepcopy(real)
    bad["items"] = [item for item in bad["items"] if item["id"] != "R-B06"]
    violations, _ = val.validate(bad)
    assert any(entry["check"] == "REACH-6" and entry["id"] == "R-B06" for entry in violations)


def test_detects_a_tampered_register_snapshot(real, tmp_path: Path):
    bad_snapshot = tmp_path / "REGISTER.md"
    bad_snapshot.write_text("# not the register\n", encoding="utf-8")
    violations, _ = val.validate(real, register_path=bad_snapshot)
    assert any(entry["check"] == "REACH-6" and "sha256" in entry["detail"] for entry in violations)


def test_detects_a_missing_register_snapshot(real, tmp_path: Path):
    violations, _ = val.validate(real, register_path=tmp_path / "nope.md")
    assert any(entry["check"] == "REACH-6" and "missing" in entry["detail"] for entry in violations)


def test_detects_a_stale_dependency_graph(real, real_graph):
    stale = copy.deepcopy(real_graph)
    stale["edge_count"] = 999
    violations, _ = val.validate(real, graph=stale)
    assert "V-GRAPH" in _checks(violations)


def test_detects_duplicate_and_malformed_ids(real):
    bad = copy.deepcopy(real)
    bad["items"].append(copy.deepcopy(_find(bad, "R-M01")))
    bad["items"].append({"id": "R-", "title": "garbage"})
    violations, _ = val.validate(bad)
    details = {entry["detail"] for entry in violations if entry["check"] == "V-ID"}
    assert "duplicate id" in details
    assert any("does not match" in detail for detail in details)


def test_empty_catalog_fails_closed():
    violations, stats = val.validate({"items": []})
    assert "V-EMPTY" in _checks(violations)
    assert stats == {"items": 0}


def test_require_complete_flags_unresolved_work_unit_fields(real):
    bad = copy.deepcopy(real)
    _find(bad, "R-M01")["completion_sentinel"] = ""
    ok, _ = val.validate(bad, require_complete=False)
    strict, _ = val.validate(bad, require_complete=True)
    assert "V-FIELDS" not in _checks(ok)
    assert "V-FIELDS" in _checks(strict)


# --------------------------------------------------------------------------
# CLI - the exit code is what CI reads, so it gets its own both-states pair
# --------------------------------------------------------------------------


def test_cli_exit_zero_on_the_real_tree(capsys):
    assert val.main([]) == 0
    assert "SUCCESS:cc-validate" in capsys.readouterr().out


def test_cli_exit_one_on_a_mutated_catalog(tmp_path: Path, real, real_graph, capsys):
    bad = copy.deepcopy(real)
    _find(bad, "R-M01")["dependencies"] = ["R-NOPE"]
    catalog_file = tmp_path / "cat.json"
    graph_file = tmp_path / "graph.json"
    cat.save(bad, catalog_file)
    cat.save(cat.build_graph(bad), graph_file)
    code = val.main(["--catalog", str(catalog_file), "--graph", str(graph_file), "--json"])
    assert code == 1
    assert "FAILED:cc-validate" in capsys.readouterr().out


def test_cli_fails_closed_on_unreadable_inputs(tmp_path: Path, capsys):
    assert val.main(["--catalog", str(tmp_path / "missing.json")]) == 1
    catalog_file = tmp_path / "cat.json"
    cat.save({"items": []}, catalog_file)
    assert val.main(["--catalog", str(catalog_file), "--graph", str(tmp_path / "missing.json")]) == 1
    broken = tmp_path / "graph.json"
    broken.write_text("{not json", encoding="utf-8")
    assert val.main(["--catalog", str(catalog_file), "--graph", str(broken)]) == 1
    assert "FAILED:cc-validate" in capsys.readouterr().out
