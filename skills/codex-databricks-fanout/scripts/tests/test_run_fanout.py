"""Unit tests for the e2e/run_fanout.py driver (no Databricks, no network).

`run_coverage_fanout` is monkeypatched, so nothing here submits a job. The driver lives
in e2e/ which is not a package, so it is loaded by file path.

Coverage of the reconciled behaviours specifically:
  * both gaps-file shapes  — {"gaps": [...]} and a bare list
  * all three gaps-file basenames run_runnability.py has used
  * both artifact branch fields — `branch_ready` (current) and `branch_pushed` (pre-rename)
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "e2e" / "run_fanout.py"


def load_driver():
    spec = importlib.util.spec_from_file_location("e2e_run_fanout", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rf():
    return load_driver()


def write_gaps(tmp_path, payload):
    p = tmp_path / "gaps.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


GAP = {"file": "src/a.py", "uncovered": [1, 2]}


# --- gaps payload shapes -----------------------------------------------------


def test_load_gaps_accepts_wrapped_dict(rf):
    """The run_runnability.py shape: {"repo", "ok", "gaps"}."""
    assert rf.load_gaps({"repo": "r", "ok": True, "gaps": [GAP]}) == [GAP]


def test_load_gaps_dict_without_gaps_key_is_empty(rf):
    assert rf.load_gaps({"repo": "r", "ok": False}) == []


def test_load_gaps_accepts_bare_list(rf):
    """The older shape: the gaps list dumped straight to disk."""
    assert rf.load_gaps([GAP]) == [GAP]


# --- gaps file location ------------------------------------------------------


def test_gaps_candidates_covers_every_name_ever_written(rf):
    assert rf.gaps_candidates("env-inspector") == [
        "_E_env-inspector_gaps.json",
        "_env-inspector_gaps.json",
        "_runnability_gaps.json",
    ]


def test_resolve_gaps_path_prefers_first_existing(rf, tmp_path):
    (tmp_path / "_runnability_gaps.json").write_text("[]", encoding="utf-8")
    (tmp_path / "_r_gaps.json").write_text("[]", encoding="utf-8")
    assert rf.resolve_gaps_path("r", tmp_path).name == "_r_gaps.json"


def test_resolve_gaps_path_falls_back_to_preferred_name(rf, tmp_path):
    assert rf.resolve_gaps_path("r", tmp_path).name == "_E_r_gaps.json"


# --- branch field extraction -------------------------------------------------


def test_branch_of_reads_current_branch_ready_field(rf, tmp_path):
    a = tmp_path / "u.md"
    a.write_text("suite_status: green\nbranch_ready: agent/E-r-a@abc123\n", "utf-8")
    assert rf.branch_of(a) == "agent/E-r-a@abc123"


def test_branch_of_reads_pre_rename_field_and_flags_it(rf, tmp_path):
    a = tmp_path / "u.md"
    a.write_text("branch_pushed: agent/E-r-a\n", "utf-8")
    out = rf.branch_of(a)
    assert out.startswith("agent/E-r-a")
    assert "branch_pushed" in out and "pre-rename" in out


def test_branch_of_prefers_branch_ready_when_both_present(rf, tmp_path):
    a = tmp_path / "u.md"
    a.write_text("branch_pushed: old\nbranch_ready: new\n", "utf-8")
    assert rf.branch_of(a) == "new"


def test_branch_of_unknown_when_no_branch_field(rf, tmp_path):
    a = tmp_path / "u.md"
    a.write_text("suite_status: green\n", "utf-8")
    assert rf.branch_of(a) == "?"


# --- main() ------------------------------------------------------------------


def test_main_without_repo_is_usage_error(rf, capsys):
    assert rf.main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_missing_gaps_file_fails_before_any_spend(rf, tmp_path, capsys):
    assert rf.main(["r", str(tmp_path / "nope.json")]) == 2
    assert "FAILED: gaps file not found" in capsys.readouterr().err


def test_main_default_path_missing_gaps_file_fails(rf, capsys):
    """No explicit path -> resolve_gaps_path, still a clean exit-2 when absent."""
    assert rf.main(["repo-that-has-no-gaps-file"]) == 2
    assert "FAILED: gaps file not found" in capsys.readouterr().err


def test_main_no_gaps_is_success_and_does_not_fan_out(
    rf, tmp_path, monkeypatch, capsys
):
    def boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("fanned out with zero gaps")

    monkeypatch.setattr(rf.run_E, "run_coverage_fanout", boom)
    p = write_gaps(tmp_path, {"repo": "r", "ok": True, "gaps": []})
    assert rf.main(["r", str(p)]) == 0
    assert "SUCCESS: no gaps for r" in capsys.readouterr().out


def test_main_all_done_reports_success_and_each_branch(
    rf, tmp_path, monkeypatch, capsys
):
    art = tmp_path / "u1.md"
    art.write_text("branch_ready: agent/E-r-src-a-py@deadbee\n", encoding="utf-8")
    monkeypatch.setattr(
        rf.run_E,
        "run_coverage_fanout",
        lambda repo, gaps: {"E-r-src-a-py": ("DONE", str(art))},
    )
    p = write_gaps(tmp_path, [GAP])
    assert rf.main(["r", str(p)]) == 0
    out = capsys.readouterr().out
    assert "FANOUT r: 1 gap(s) from gaps.json" in out
    assert "DONE" in out
    assert "branch[E-r-src-a-py]: agent/E-r-src-a-py@deadbee" in out
    assert "SUCCESS: 1/1 units DONE for r" in out


def test_main_partial_returns_1_and_skips_branch_line_for_failures(
    rf, tmp_path, monkeypatch, capsys
):
    art = tmp_path / "u1.md"
    art.write_text("branch_ready: agent/E-r-a\n", encoding="utf-8")
    monkeypatch.setattr(
        rf.run_E,
        "run_coverage_fanout",
        lambda repo, gaps: {
            "E-r-a": ("DONE", str(art)),
            "E-r-b": ("FAILED", None),
            "E-r-c": ("DONE", str(tmp_path / "gone.md")),
        },
    )
    p = write_gaps(tmp_path, [GAP, GAP, GAP])
    assert rf.main(["r", str(p)]) == 1
    out = capsys.readouterr().out
    assert "PARTIAL: 2/3 units DONE for r" in out
    assert "branch[E-r-a]:" in out
    assert "branch[E-r-b]" not in out  # not DONE -> no artifact to read
    assert "branch[E-r-c]" not in out  # DONE but artifact path absent
