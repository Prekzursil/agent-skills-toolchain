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
import subprocess
import sys
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
    """`open` is pinned deliberately: it catches an accidental mass re-disposition.

    69 -> 59 on 2026-08-11, when ten items were closed on re-measured evidence (see
    command-center/CLOSE-VERIFY.json and the `disposition_evidence` on each). Update this number
    when items are closed ON PURPOSE; a change you cannot explain is the regression it exists to
    catch.

    59 -> 58 at commit 3a19b9a3 ("record the four delegated owner rulings"), which closed exactly
    one item, R-A03, to DONE-VERIFIED. Its `disposition_evidence` names all three required entry
    inputs as filled, the first being OQ-1 answered 2026-08-11 (the 70 `owner_decisions` in
    07-OPTION-UNIVERSE.json, accepted verbatim, after a reported 70-vs-123 conflict was
    investigated and dissolved -- 123 counts BUCKETS). So this is the pin's documented
    close-on-purpose case, not the mass re-disposition it guards against.

    WHY IT SURFACED ONLY NOW, and why that is the more useful finding: 3a19b9a3 closed R-A03
    without updating this pin, so the assertion below has been stale since. It never reported,
    because `assert violations == []` sits ABOVE it and was failing first on a separate defect
    (REACH-6, a stale register digest introduced by 1ff5bbf8). One red assertion hid the next --
    the CI log for run 31617966828 shows ONLY the REACH-6 AssertionError, so the pin drift was
    invisible on the instrument. Verified by walking every revision of WORK-UNIT-CATALOG.json and
    recomputing the open set with catalog.is_open (not a re-implementation): 69 -> 62 at 2dd3623b,
    62 -> 59 at 318c1555, 59 -> 58 at 3a19b9a3, and no other transition.

    HOW THIS PIN WAS SHOWN LIVE -- and the control that did NOT show it, recorded because it
    was believed and reported. The original claim was: "closes one item in the real catalog
    and requires the test to go red: CLEAN exit=0 PASS, MUTATED exit=1 FAIL, so changing
    59->58 corrected the tripwire rather than disabling it." REFUTED by a verifier and
    reproduced here: closing an item DOES turn this test red, but at `assert violations == []`
    two lines below (REACH-1/REACH-5, or V-GRAPH for a clean close) -- never at the pin. That
    control passes identically whether the pin is live or dead, so it only proves the probe ran.

    The discriminating control mutates THE PIN ITSELF on an otherwise clean tree. Measured
    2026-08-13 in a throwaway clone (scratch/cigreen_r2_pin_control.py, which fails closed if
    the clone is dirty and asserts this file is restored byte-identical afterwards):

        pin=58  exit=0 PASS
        pin=59  exit=1 FAIL  "assert 58 == 59"   <- lands on the pin line
        pin=57  exit=1 FAIL  "assert 58 == 57"

    So 59 -> 58 corrected a live tripwire. Anyone updating this number should re-run that
    control rather than infer liveness from a red test.
    """
    violations, stats = val.validate(real, graph=real_graph)
    assert violations == [], [str(entry) for entry in violations]
    assert stats["items"] == 103
    assert stats["open"] == 58
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
    """Both endpoints are pinned HERE, so no live disposition can silently disarm this test.

    It previously planted only the edge (closed `T-01` -> `R-M01`) and relied on R-M01 being OPEN in
    the live catalog. When R-M01 was closed on evidence, both ends became closed, the violation
    stopped firing, and the test went red -- a detector disarmed by an unrelated, correct change to
    the data it borrowed. A bad-state test must construct its whole bad state.
    """
    bad = copy.deepcopy(real)
    target = _find(bad, "R-M01")
    target["status"] = "OPEN"
    target["disposition"] = None
    _find(bad, "T-01")["dependencies"] = ["R-M01"]
    violations, _ = val.validate(bad)
    assert any(
        entry["check"] == "REACH-1" and "closed but depends" in entry["detail"]
        for entry in violations
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
    assert any(
        entry["check"] == "REACH-3" and entry["id"] == "R-M08" for entry in violations
    )


def test_an_open_dependency_is_a_legal_reason_to_have_no_action(real):
    """REACH-3 must not fire on a legitimately waiting item, or the whole check
    becomes noise and gets ignored."""
    bad = copy.deepcopy(real)
    _find(bad, "R-A32")["next_smallest_action"] = (
        cat.UNKNOWN
    )  # still depends on open R-A01
    violations, _ = val.validate(bad)
    assert not any(
        entry["check"] == "REACH-3" and entry["id"] == "R-A32" for entry in violations
    )


def test_detects_owner_gate_pointing_at_nothing(real):
    bad = copy.deepcopy(real)
    _find(bad, "R-B08")["owner_gate"] = ["OQ-999"]
    violations, _ = val.validate(bad)
    assert any(
        entry["check"] == "REACH-4" and entry["id"] == "R-B08" for entry in violations
    )


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
    assert any(
        entry["check"] == "REACH-5" and entry["id"] == "T-05" for entry in violations
    )


def test_detects_non_terminal_disposition(real):
    bad = copy.deepcopy(real)
    _find(bad, "T-05")["disposition"] = "PROBABLY-FINE"
    violations, _ = val.validate(bad)
    assert any(
        entry["check"] == "REACH-5" and "not terminal" in entry["detail"]
        for entry in violations
    )


def test_detects_a_silently_dropped_item(real):
    """The anti-forgetting invariant: deleting a row from the catalog must fail,
    because that is precisely how 69 items got lost the first time."""
    bad = copy.deepcopy(real)
    bad["items"] = [item for item in bad["items"] if item["id"] != "R-B06"]
    violations, _ = val.validate(bad)
    assert any(
        entry["check"] == "REACH-6" and entry["id"] == "R-B06" for entry in violations
    )


def test_detects_a_tampered_register_snapshot(real, tmp_path: Path):
    bad_snapshot = tmp_path / "REGISTER.md"
    bad_snapshot.write_text("# not the register\n", encoding="utf-8")
    violations, _ = val.validate(real, register_path=bad_snapshot)
    assert any(
        entry["check"] == "REACH-6" and "sha256" in entry["detail"]
        for entry in violations
    )


def test_detects_a_missing_register_snapshot(real, tmp_path: Path):
    violations, _ = val.validate(real, register_path=tmp_path / "nope.md")
    assert any(
        entry["check"] == "REACH-6" and "missing" in entry["detail"]
        for entry in violations
    )


def test_detects_a_blank_register_digest(real):
    """The fail-OPEN this module's own docstring said could not exist.

    Until 2026-08-13 validate.py read `if recorded and digest != recorded`, so a falsy
    `provenance.register_sha256` short-circuited the comparison: REACH-6 stopped checking
    and the gate reported success. Measured before the fix on two mechanically independent
    instruments -- in-process `validate()` returned 0 violations, and the CLI exited 0 --
    while the control (one hex character flipped,
    `test_detects_a_tampered_register_snapshot`) fired on both, so the silence was a
    property of the code and not a broken probe.

    What made it survive is the asymmetry: blanking the WHOLE `provenance` block was
    already caught (the snapshot path stops resolving), so a coarse mutation test would
    have passed and recorded the branch as covered. Only the surgical edit is fail-open --
    and the surgical edit is the one a hurried fix reaches for when REACH-6 goes red, which
    is the gate that held `gate-tests-coverage (python packages)` red for 98 commits.
    """
    bad = copy.deepcopy(real)
    bad["provenance"]["register_sha256"] = ""
    violations, _ = val.validate(bad)
    assert any(
        entry["check"] == "REACH-6" and "missing or empty" in entry["detail"]
        for entry in violations
    )


def test_detects_a_deleted_register_digest(real):
    """The same fail-open reached by deleting the key instead of blanking it."""
    bad = copy.deepcopy(real)
    del bad["provenance"]["register_sha256"]
    violations, _ = val.validate(bad)
    assert any(
        entry["check"] == "REACH-6" and "missing or empty" in entry["detail"]
        for entry in violations
    )


def test_cli_fails_closed_on_a_blank_register_digest(real, tmp_path: Path):
    """End to end on the surface CI actually grades: the process exit code and marker.

    The two tests above prove `validate()` returns a violation. This one proves the thing
    that was actually lying. Before the fix this exact invocation exited 0 and printed
    `SUCCESS:cc-validate items=103 open=58 reachable=all` -- a green terminal marker
    claiming `reachable=all` from a run in which the digest comparison never executed.

    Deliberately a subprocess against a tmp_path catalog: it is the only assertion here
    that would still catch a regression introduced in `main()` rather than in `validate()`,
    and it never writes to the committed catalog.
    """
    bad = copy.deepcopy(real)
    bad["provenance"]["register_sha256"] = ""
    catalog_file = tmp_path / "WORK-UNIT-CATALOG.json"
    catalog_file.write_text(
        json.dumps(bad, indent=1, ensure_ascii=False), encoding="utf-8", newline=""
    )
    proc = subprocess.run(
        [sys.executable, val.__file__, "--catalog", str(catalog_file)],
        cwd=str(cat.repo_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 1, out
    assert "SUCCESS:cc-validate" not in out, out
    assert "REACH-6" in out, out


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


def test_require_complete_default_is_armed(real):
    """IMP-0437: library default require_complete=True catches blank fields."""
    bad = copy.deepcopy(real)
    _find(bad, "R-M01")["completion_sentinel"] = ""
    violations, _ = val.validate(bad)  # default must be armed
    assert "V-FIELDS" in _checks(violations)


def test_cli_defaults_deletion_exits_nonzero(tmp_path: Path, real, capsys):
    """Defaults-block deletion must turn the CI command red (IMP-0437 / IMP-0436)."""
    bad = copy.deepcopy(real)
    del bad["defaults"]
    catalog_file = tmp_path / "cat.json"
    graph_file = tmp_path / "graph.json"
    cat.save(bad, catalog_file)
    cat.save(cat.build_graph(bad), graph_file)
    code = val.main(
        [
            "--catalog",
            str(catalog_file),
            "--graph",
            str(graph_file),
            "--require-complete",
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "FAILED:cc-validate" in out
    assert "V-DEFAULTS" in out


def test_cli_single_default_field_deletion_exits_nonzero(tmp_path: Path, real, capsys):
    """Control: deleting one relied-upon default field also fails the gate."""
    bad = copy.deepcopy(real)
    del bad["defaults"]["timeout_seconds"]
    catalog_file = tmp_path / "cat.json"
    graph_file = tmp_path / "graph.json"
    cat.save(bad, catalog_file)
    cat.save(cat.build_graph(bad), graph_file)
    code = val.main(
        [
            "--catalog",
            str(catalog_file),
            "--graph",
            str(graph_file),
            "--require-complete",
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "V-DEFAULTS" in out
    assert "timeout_seconds" in out


def test_cli_bare_matches_require_complete_arm(tmp_path: Path, real, capsys):
    """Bare CLI (no flag) is armed after IMP-0437; soft mode needs --no-require-complete."""
    bad = copy.deepcopy(real)
    _find(bad, "R-M01")["completion_sentinel"] = ""
    catalog_file = tmp_path / "cat.json"
    graph_file = tmp_path / "graph.json"
    cat.save(bad, catalog_file)
    cat.save(cat.build_graph(bad), graph_file)
    bare = val.main(["--catalog", str(catalog_file), "--graph", str(graph_file)])
    out_bare = capsys.readouterr().out
    soft = val.main(
        [
            "--catalog",
            str(catalog_file),
            "--graph",
            str(graph_file),
            "--no-require-complete",
        ]
    )
    out_soft = capsys.readouterr().out
    assert bare == 1 and "V-FIELDS" in out_bare
    assert soft == 0 and "SUCCESS:cc-validate" in out_soft


def test_ci_workflow_passes_require_complete():
    """quality.yml must invoke validate.py with --require-complete (IMP-0437)."""
    wf = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "quality.yml"
    text = wf.read_text(encoding="utf-8")
    assert "tools/command-center/validate.py --require-complete" in text


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
    code = val.main(
        ["--catalog", str(catalog_file), "--graph", str(graph_file), "--json"]
    )
    assert code == 1
    assert "FAILED:cc-validate" in capsys.readouterr().out


def test_cli_fails_closed_on_unreadable_inputs(tmp_path: Path, capsys):
    assert val.main(["--catalog", str(tmp_path / "missing.json")]) == 1
    catalog_file = tmp_path / "cat.json"
    cat.save({"items": []}, catalog_file)
    assert (
        val.main(
            ["--catalog", str(catalog_file), "--graph", str(tmp_path / "missing.json")]
        )
        == 1
    )
    broken = tmp_path / "graph.json"
    broken.write_text("{not json", encoding="utf-8")
    assert val.main(["--catalog", str(catalog_file), "--graph", str(broken)]) == 1
    assert "FAILED:cc-validate" in capsys.readouterr().out
