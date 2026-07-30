"""Regression suite for the stage-0 plan linter + cross-session resume manifest.

The module under test (``agent-self/config/harness-meta/plan_lint_stage0.py``) is the
repo-side snapshot of a LIVE harness tool that, before this suite existed, lived only on
one machine's disk with no test and no CI. It is loaded by path (not by import name)
because ``agent-self`` is not an importable package name.

Emphasis, in order of the risk it retires:

1. ``ResumeManifest`` -- the crash-recovery ledger. If it mis-folds its log a resuming
   cohort silently REDOES completed work, or worse, skips a crashed work unit. Every
   state transition, the torn-last-line tolerance, and the pending classification are
   pinned here.
2. ``lint()`` -- each of the four mechanical checks must actually FIRE (a linter that
   returns ``clean`` on a broken plan is worse than no linter), and the SHADOW contract
   must hold: never raise, always exit 0.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = (
    REPO_ROOT / "agent-self" / "config" / "harness-meta" / "plan_lint_stage0.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("plan_lint_stage0", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


plan_lint = _load_module()


@pytest.fixture(autouse=True)
def _isolated_shadow_sink(tmp_path, monkeypatch):
    """Never let a test write into the real harness-meta/logs sink."""
    monkeypatch.setenv("PLAN_LINT_SHADOW_DIR", str(tmp_path / "shadow"))
    return tmp_path / "shadow"


# --------------------------------------------------------------------------- #
# The module exists in the repo at all (the whole point of this lane)
# --------------------------------------------------------------------------- #


def test_module_is_versioned_at_the_deployable_path() -> None:
    """bootstrap.ps1 copies config/* into ~/.claude, so this path round-trips."""
    assert MODULE_PATH.is_file()
    assert MODULE_PATH.parent.name == "harness-meta"
    assert MODULE_PATH.parent.parent.name == "config"


def test_sync_self_captures_this_module() -> None:
    """Without this, sync-self.ps1 would DELETE the module on its next run.

    sync-self.ps1 wipes its bundle root and re-populates only what it explicitly
    copies; anything it does not copy is dropped from the repo. harness-meta is
    captured through a FILE allowlist (not Copy-Tree) because the unlisted siblings
    would fail the repo-wide ruff gate and drag in runtime logs.
    """
    script = (REPO_ROOT / "agent-self" / "sync-self.ps1").read_text(encoding="utf-8")
    allowlist = [ln for ln in script.splitlines() if "$HarnessMetaFiles" in ln]
    assert allowlist, "the harness-meta sync allowlist vanished from sync-self.ps1"
    assert any(MODULE_PATH.name in ln for ln in allowlist), (
        f"{MODULE_PATH.name} is versioned but not on the sync allowlist: "
        "the next sync-self.ps1 run would delete it"
    )


# --------------------------------------------------------------------------- #
# ResumeManifest -- the crash-recovery contract
# --------------------------------------------------------------------------- #


def test_manifest_is_empty_before_anything_is_written(tmp_path) -> None:
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    assert mani.records() == []
    assert mani.latest_state() == {}
    state = mani.resume()
    assert state.to_dict() == {
        "done": [],
        "partial": [],
        "failed": [],
        "pending": [],
    }


def test_write_ahead_partial_survives_as_a_crash_marker(tmp_path) -> None:
    """mark_partial before the WU runs is the only reason a crash is recoverable."""
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    record = mani.mark_partial("WU3", attempt=1)
    assert record["wu_id"] == "WU3"
    assert record["state"] == "partial"
    assert record["meta"] == {"attempt": 1}
    assert mani.path.is_file()

    # A fresh reader (a resuming session) sees the crashed WU as re-drivable.
    reopened = plan_lint.ResumeManifest(tmp_path / "resume")
    assert reopened.resume(["WU1", "WU3"]).partial == ["WU3"]
    assert reopened.resume(["WU1", "WU3"]).pending == ["WU1"]


def test_partial_then_done_folds_to_done_not_both(tmp_path) -> None:
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    mani.mark_partial("WU1")
    mani.mark_done("WU1")
    state = mani.resume(["WU1"])
    assert state.done == ["WU1"]
    assert state.partial == []
    assert state.pending == []
    assert len(mani.records()) == 2, "the log stays append-only"


def test_failed_is_distinct_from_partial_and_from_done(tmp_path) -> None:
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    mani.mark_partial("WU1")
    mani.mark_failed("WU1", reason="boom")
    mani.mark_partial("WU2")
    mani.mark_done("WU3")
    state = mani.resume(["WU1", "WU2", "WU3", "WU4"])
    assert state.failed == ["WU1"]
    assert state.partial == ["WU2"]
    assert state.done == ["WU3"]
    assert state.pending == ["WU4"]


def test_a_later_partial_reopens_a_done_unit(tmp_path) -> None:
    """latest_state folds to the MOST RECENT record, not the strongest one."""
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    mani.mark_done("WU1")
    mani.mark_partial("WU1")
    assert mani.latest_state() == {"WU1": "partial"}
    assert mani.resume().done == []


def test_torn_last_line_from_a_crash_mid_write_is_tolerated(tmp_path) -> None:
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    mani.mark_done("WU1")
    with open(mani.path, "a", encoding="utf-8") as fh:
        fh.write('{"wu_id": "WU2", "sta')  # truncated by a crash
    assert [r["wu_id"] for r in mani.records()] == ["WU1"]
    assert mani.resume(["WU1", "WU2"]).pending == ["WU2"]


def test_blank_lines_and_records_without_a_wu_id_are_skipped(tmp_path) -> None:
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    mani.path.parent.mkdir(parents=True, exist_ok=True)
    mani.path.write_text(
        "\n"
        "   \n"
        '{"wu_id": "", "state": "done"}\n'
        '["not", "a", "dict"]\n'
        '{"wu_id": "WU9", "state": "done"}\n',
        encoding="utf-8",
    )
    assert [r["wu_id"] for r in mani.records()] == ["WU9"]


def test_non_string_state_or_wu_id_is_ignored_by_the_fold(tmp_path) -> None:
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    mani.path.parent.mkdir(parents=True, exist_ok=True)
    mani.path.write_text(
        '{"wu_id": 7, "state": "done"}\n'
        '{"wu_id": "WU1", "state": 5}\n'
        '{"wu_id": "WU2", "state": "done"}\n',
        encoding="utf-8",
    )
    assert mani.latest_state() == {"WU2": "done"}


def test_duplicate_ids_in_all_wu_ids_do_not_duplicate_pending(tmp_path) -> None:
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    assert mani.resume(["WU1", "WU1", "WU2"]).pending == ["WU1", "WU2"]


def test_manifest_filename_is_overridable(tmp_path) -> None:
    mani = plan_lint.ResumeManifest(tmp_path / "resume", filename="other.jsonl")
    mani.mark_done("WU1")
    assert (tmp_path / "resume" / "other.jsonl").is_file()
    assert not (tmp_path / "resume" / "done.jsonl").exists()


def test_records_are_one_json_object_per_line(tmp_path) -> None:
    mani = plan_lint.ResumeManifest(tmp_path / "resume")
    mani.mark_partial("WU1")
    mani.mark_done("WU1")
    lines = mani.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        assert set(json.loads(line)) == {"ts", "wu_id", "state", "meta"}


# --------------------------------------------------------------------------- #
# lint() -- every check must actually fire
# --------------------------------------------------------------------------- #


def test_a_well_formed_plan_is_clean() -> None:
    plan = {
        "work_units": [
            {"id": "WU1", "files": ["a.py", "b.py"]},
            {"id": "WU2", "files": ["c.py"], "deps": ["WU1"]},
        ]
    }
    result = plan_lint.lint(plan)
    assert result.verdict == "clean"
    assert result.marker == "PLAN_LINT:clean"
    assert result.violations == []
    assert result.wu_count == 2
    assert result.to_dict()["shadow"] is True


@pytest.mark.parametrize(
    ("plan", "kind"),
    [
        pytest.param(
            [{"id": "WU1", "files": ["a", "b", "c", "d", "e", "f"]}],
            "oversized_scope",
            id="fat-wu-was-never-decomposed",
        ),
        pytest.param(
            [{"id": "WU1", "files": ["a.py"]}, {"id": "WU2", "files": ["a.py"]}],
            "overlapping_scope",
            id="two-wus-fight-over-one-file",
        ),
        pytest.param(
            [{"id": "WU1", "files": ["a.py"]}, {"id": "WU1", "files": ["b.py"]}],
            "duplicate_id",
            id="duplicate-wu-id",
        ),
        pytest.param(
            [{"id": "WU1", "files": ["a.py"], "deps": ["WU1"]}],
            "self_dep",
            id="self-dependency",
        ),
        pytest.param(
            [{"id": "WU1", "files": ["a.py"], "deps": ["NOPE"]}],
            "missing_dep",
            id="dep-on-undeclared-unit",
        ),
        pytest.param(
            [
                {"id": "WU1", "files": ["a.py"], "deps": ["WU2"]},
                {"id": "WU2", "files": ["b.py"], "deps": ["WU1"]},
            ],
            "cycle",
            id="two-cycle-deadlocks-the-barrier",
        ),
        pytest.param(
            [
                {"id": "WU1", "files": ["a.py"]},
                {"id": "WU2", "files": ["b.py"], "parent": "WU1"},
                {"id": "WU3", "files": ["c.py"], "parent": "WU2"},
            ],
            "deep_nesting",
            id="two-level-nesting",
        ),
    ],
)
def test_each_mechanical_check_fires(plan, kind) -> None:
    result = plan_lint.lint(plan)
    assert result.verdict == "dirty"
    assert result.marker == "PLAN_LINT:dirty"
    assert kind in {v.kind for v in result.violations}


def test_max_files_ceiling_is_configurable() -> None:
    plan = [{"id": "WU1", "files": ["a", "b", "c"]}]
    assert plan_lint.lint(plan, max_files=5).verdict == "clean"
    dirty = plan_lint.lint(plan, max_files=2)
    assert dirty.verdict == "dirty"
    assert dirty.max_files == 2


def test_one_level_nesting_is_allowed() -> None:
    plan = [
        {"id": "WU1", "files": ["a.py"]},
        {"id": "WU2", "files": ["b.py"], "parent": "WU1"},
    ]
    assert plan_lint.lint(plan).verdict == "clean"


def test_a_parent_that_is_not_a_declared_unit_stops_the_walk() -> None:
    plan = [{"id": "WU1", "files": ["a.py"], "parent": "GHOST"}]
    assert plan_lint.lint(plan).verdict == "clean"


def test_a_longer_cycle_is_reported_once_not_once_per_entry_node() -> None:
    plan = [
        {"id": "WU1", "files": ["a"], "deps": ["WU3"]},
        {"id": "WU2", "files": ["b"], "deps": ["WU1"]},
        {"id": "WU3", "files": ["c"], "deps": ["WU2"]},
    ]
    cycles = [v for v in plan_lint.lint(plan).violations if v.kind == "cycle"]
    assert len(cycles) == 1
    assert set(cycles[0].related) == {"WU1", "WU2", "WU3"}


def test_the_same_cycle_found_twice_is_deduped_by_its_node_set() -> None:
    """A duplicated dep edge re-discovers one cycle; only one violation survives."""
    plan = [
        {"id": "WU1", "files": ["a"], "deps": ["WU2"]},
        {"id": "WU2", "files": ["b"], "deps": ["WU1", "WU1"]},
    ]
    cycles = [v for v in plan_lint.lint(plan).violations if v.kind == "cycle"]
    assert len(cycles) == 1


def test_a_dag_with_a_diamond_is_clean() -> None:
    plan = [
        {"id": "WU1", "files": ["a"]},
        {"id": "WU2", "files": ["b"], "deps": ["WU1"]},
        {"id": "WU3", "files": ["c"], "deps": ["WU1"]},
        {"id": "WU4", "files": ["d"], "deps": ["WU2", "WU3"]},
    ]
    assert plan_lint.lint(plan).verdict == "clean"


def test_na_when_there_are_no_recognisable_work_units() -> None:
    for empty in (None, [], {}, "nonsense", 17, [1, 2, 3]):
        result = plan_lint.lint(empty)
        assert result.verdict == "na"
        assert result.marker == "PLAN_LINT:na"
        assert result.wu_count == 0


def test_lint_accepts_already_normalised_work_units() -> None:
    units = [
        plan_lint.WorkUnit(id="WU1", files=["a.py"], deps=[]),
        plan_lint.WorkUnit(id="WU2", files=["b.py"], deps=["WU1"]),
    ]
    assert plan_lint.lint(units).verdict == "clean"


def test_violation_to_dict_renders_related_as_a_list() -> None:
    plan = [
        {"id": "WU1", "files": ["a.py"]},
        {"id": "WU2", "files": ["a.py"]},
    ]
    payload = plan_lint.lint(plan).to_dict()
    assert payload["violations"][0]["related"] == ["WU2"]
    assert isinstance(payload["violations"][0]["related"], list)


# --------------------------------------------------------------------------- #
# Scope-overlap semantics (globs)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("a", "b", "conflict"),
    [
        ("src/a.py", "src/a.py", True),
        ("src/*.py", "src/a.py", True),
        ("src/a.py", "src/*.py", True),
        ("src/*.py", "tests/*.py", False),
        ("src/*.py", "src/*.py", True),
        ("src/a.py", "src/b.py", False),
        ("src/?.py", "src/a.py", True),
        ("src/[ab].py", "src/a.py", True),
    ],
)
def test_scope_conflict_semantics(a, b, conflict) -> None:
    assert plan_lint._scopes_conflict(a, b) is conflict


def test_glob_vs_different_glob_is_not_reported() -> None:
    """Documented soundness limit: glob-vs-glob only collides when identical."""
    plan = [
        {"id": "WU1", "files": ["src/a*.py"]},
        {"id": "WU2", "files": ["src/*b.py"]},
    ]
    assert plan_lint.lint(plan).verdict == "clean"


def test_overlap_detail_names_both_sides() -> None:
    plan = [
        {"id": "WU1", "files": ["src/*.py"]},
        {"id": "WU2", "files": ["src/a.py"]},
    ]
    violation = plan_lint.lint(plan).violations[0]
    assert violation.wu == "WU1"
    assert violation.related == ("WU2",)
    assert "src/*.py ~ src/a.py" in violation.detail


# --------------------------------------------------------------------------- #
# Liberal plan parsing
# --------------------------------------------------------------------------- #


def test_key_aliases_are_all_accepted() -> None:
    units = plan_lint.normalise_plan(
        {
            "units": [
                {"wu": "A", "scope": "x.py", "after": "B", "parent_id": "B"},
                {"key": "B", "target_files": ["y.py"], "needs": []},
            ]
        }
    )
    assert [u.id for u in units] == ["A", "B"]
    assert units[0].files == ["x.py"]
    assert units[0].deps == ["B"]
    assert units[0].parent == "B"


def test_an_id_to_unit_mapping_is_accepted() -> None:
    units = plan_lint.normalise_plan(
        {"WU1": {"files": ["a.py"]}, "WU2": {"id": "OTHER", "files": ["b.py"]}}
    )
    assert sorted(u.id for u in units) == ["OTHER", "WU1"]


def test_a_mapping_whose_values_are_not_units_is_rejected() -> None:
    assert plan_lint.normalise_plan({"title": "my plan", "owner": "me"}) == []


def test_units_without_an_id_get_a_positional_fallback() -> None:
    units = plan_lint.normalise_plan([{"files": ["a"]}, {"id": "   ", "files": ["b"]}])
    assert [u.id for u in units] == ["WU1", "WU2"]


def test_non_dict_entries_are_skipped() -> None:
    units = plan_lint.normalise_plan([{"id": "WU1", "files": ["a"]}, "junk", 42, None])
    assert [u.id for u in units] == ["WU1"]


def test_deps_and_files_accept_nested_dicts_and_drop_junk() -> None:
    units = plan_lint.normalise_plan(
        [
            {
                "id": "WU1",
                "files": [{"path": "a.py"}, {"nope": 1}, 7, "b.py"],
                "deps": [{"id": "WU2"}, 9],
            }
        ]
    )
    assert units[0].files == ["a.py", "b.py"]
    assert units[0].deps == ["WU2"]


def test_scope_paths_are_normalised() -> None:
    units = plan_lint.normalise_plan(
        [{"id": "WU1", "files": ["./src\\a.py", "  src/dir/  ", ""]}]
    )
    assert units[0].files == ["src/a.py", "src/dir"]


def test_a_repeated_leading_dot_slash_is_stripped() -> None:
    assert plan_lint._norm_path("././a.py") == "a.py"


def test_norm_path_only_strips_a_leading_dot_slash_run() -> None:
    """Documented limit: `.//./x` keeps the interior `/./` (not a path canonicaliser)."""
    assert plan_lint._norm_path(".//./a.py") == "/./a.py"


def test_as_list_edge_cases() -> None:
    assert plan_lint._as_list(None) == []
    assert plan_lint._as_list("solo") == ["solo"]
    assert plan_lint._as_list(("a", "b")) == ["a", "b"]
    assert plan_lint._as_list(42) == []


def test_first_returns_the_default_when_no_key_matches() -> None:
    assert plan_lint._first({"a": None}, ("a", "b"), default="fallback") == "fallback"


def test_a_non_list_units_value_is_rejected() -> None:
    assert plan_lint.normalise_plan({"work_units": "not a list"}) == []


# --------------------------------------------------------------------------- #
# load_plan
# --------------------------------------------------------------------------- #


def test_load_plan_reads_straight_json(tmp_path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps([{"id": "WU1", "files": ["a"]}]), encoding="utf-8")
    assert plan_lint.load_plan(path) == [{"id": "WU1", "files": ["a"]}]


def test_load_plan_extracts_a_fenced_block_from_markdown(tmp_path) -> None:
    path = tmp_path / "active-plan.md"
    path.write_text(
        "# Plan\n\nprose\n\n"
        "```json\n"
        '{"not": "a plan"}\n'
        "```\n\n"
        "```json\n"
        '{"work_units": [{"id": "WU1", "files": ["a.py"]}]}\n'
        "```\n",
        encoding="utf-8",
    )
    plan = plan_lint.load_plan(path)
    assert plan_lint.lint(plan).verdict == "clean"


def test_load_plan_skips_unparseable_fences(tmp_path) -> None:
    path = tmp_path / "plan.md"
    path.write_text(
        "```json\n{ this is not json\n```\n"
        '```plan\n[{"id": "WU1", "files": ["a"]}]\n```\n',
        encoding="utf-8",
    )
    assert plan_lint.normalise_plan(plan_lint.load_plan(path))[0].id == "WU1"


def test_load_plan_returns_none_for_markdown_without_a_plan(tmp_path) -> None:
    path = tmp_path / "plan.md"
    path.write_text("# no plan here\n", encoding="utf-8")
    assert plan_lint.load_plan(path) is None


def test_load_plan_returns_none_for_a_missing_file(tmp_path) -> None:
    assert plan_lint.load_plan(tmp_path / "absent.json") is None


# --------------------------------------------------------------------------- #
# Shadow sink + emit (SHADOW contract: log only, never block)
# --------------------------------------------------------------------------- #


def test_shadow_log_writes_to_the_env_overridden_sink(tmp_path) -> None:
    assert plan_lint.shadow_log({"event": "probe"}) is True
    sink = tmp_path / "shadow" / "plan_lint_shadow.jsonl"
    assert json.loads(sink.read_text(encoding="utf-8").splitlines()[0])["event"] == (
        "probe"
    )


def test_shadow_sink_defaults_next_to_the_module(monkeypatch) -> None:
    monkeypatch.delenv("PLAN_LINT_SHADOW_DIR", raising=False)
    path = plan_lint._shadow_sink_path()
    assert path.parent.name == "logs"
    assert path.parent.parent == MODULE_PATH.parent


def test_shadow_sink_rotates_when_it_exceeds_its_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(plan_lint, "_SHADOW_MAX_BYTES", 1)
    sink = tmp_path / "shadow" / "plan_lint_shadow.jsonl"
    for _ in range(4):
        assert plan_lint.shadow_log({"event": "probe"}) is True
    assert sink.exists()
    rotated = sorted(p.name for p in sink.parent.iterdir())
    assert "plan_lint_shadow.jsonl.1" in rotated
    assert "plan_lint_shadow.jsonl.3" not in rotated, "keep is bounded at 3"


def test_shadow_log_returns_false_when_the_sink_is_unwritable(
    tmp_path, monkeypatch
) -> None:
    blocker = tmp_path / "afile"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("PLAN_LINT_SHADOW_DIR", str(blocker / "nested"))
    assert plan_lint.shadow_log({"event": "probe"}) is False


def test_emit_records_the_verdict_without_touching_the_ledger(tmp_path) -> None:
    result = plan_lint.lint([{"id": "WU1", "files": ["a.py"]}])
    sinks = plan_lint.emit(result, cwd="/some/where", to_ledger=False)
    assert sinks == {"shadow_sink": True, "ledger": False}
    sink = tmp_path / "shadow" / "plan_lint_shadow.jsonl"
    record = json.loads(sink.read_text(encoding="utf-8").splitlines()[0])
    assert record["event"] == "plan_lint"
    assert record["cwd"] == "/some/where"
    assert record["marker"] == "PLAN_LINT:clean"
    assert record["shadow"] is True


def test_emit_defaults_cwd_to_the_process_cwd(tmp_path) -> None:
    result = plan_lint.lint(None)
    plan_lint.emit(result, to_ledger=False)
    sink = tmp_path / "shadow" / "plan_lint_shadow.jsonl"
    record = json.loads(sink.read_text(encoding="utf-8").splitlines()[0])
    assert record["cwd"]


def test_emit_never_raises_when_the_ledger_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(plan_lint, "_load_ledger", lambda: None)
    sinks = plan_lint.emit(plan_lint.lint(None), to_ledger=True)
    assert sinks["ledger"] is False


# --------------------------------------------------------------------------- #
# CLI -- SHADOW means exit 0, always
# --------------------------------------------------------------------------- #


def test_cli_prints_the_marker_and_exits_zero(tmp_path, capsys) -> None:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            [{"id": "WU1", "files": ["a.py"]}, {"id": "WU2", "files": ["a.py"]}]
        ),
        encoding="utf-8",
    )
    assert plan_lint.main(["--plan", str(path), "--no-ledger"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("PLAN_LINT:dirty")
    assert "[overlapping_scope] WU1" in out
    assert "SHADOW - non-blocking" in out
    assert "shadow-sink: written" in out


def test_cli_json_mode_carries_the_sinks(tmp_path, capsys) -> None:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps([{"id": "WU1", "files": ["a.py"]}]), encoding="utf-8")
    assert plan_lint.main(["--plan", str(path), "--json", "--no-ledger"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "clean"
    assert payload["sinks"]["shadow_sink"] is True


def test_cli_on_a_missing_plan_is_na_and_still_exits_zero(tmp_path, capsys) -> None:
    missing = tmp_path / "absent.json"
    assert plan_lint.main(["--plan", str(missing), "--no-ledger"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("PLAN_LINT:na")
    assert "no plan at" in out


def test_cli_max_files_flag_is_honoured(tmp_path, capsys) -> None:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps([{"id": "WU1", "files": ["a", "b", "c"]}]), encoding="utf-8"
    )
    plan_lint.main(["--plan", str(path), "--max-files", "2", "--no-ledger"])
    assert "oversized_scope" in capsys.readouterr().out


def test_cli_writes_to_the_ledger_by_default(tmp_path, monkeypatch, capsys) -> None:
    """--no-ledger absent means the ledger is ATTEMPTED (best-effort)."""
    calls: list[bool] = []

    def _fake_ledger():
        calls.append(True)
        return None

    monkeypatch.setattr(plan_lint, "_load_ledger", _fake_ledger)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps([{"id": "WU1", "files": ["a"]}]), encoding="utf-8")
    assert plan_lint.main(["--plan", str(path)]) == 0
    capsys.readouterr()
    assert calls == [True]


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        ("--mark-partial", "PLAN_RESUME:partial WU3"),
        ("--mark-done", "PLAN_RESUME:done WU3"),
        ("--mark-failed", "PLAN_RESUME:failed WU3"),
    ],
)
def test_cli_manifest_marks(tmp_path, capsys, flag, expected) -> None:
    base = tmp_path / "resume"
    assert plan_lint.main(["--manifest", str(base), flag, "WU3"]) == 0
    assert capsys.readouterr().out.strip() == expected
    assert (
        plan_lint.ResumeManifest(base).latest_state()["WU3"]
        == expected.split(":")[1].split(" ")[0]
    )


def test_cli_resume_prints_every_bucket(tmp_path, capsys) -> None:
    base = tmp_path / "resume"
    plan_lint.main(["--manifest", str(base), "--mark-done", "WU1"])
    plan_lint.main(["--manifest", str(base), "--mark-partial", "WU2"])
    plan_lint.main(["--manifest", str(base), "--mark-failed", "WU3"])
    capsys.readouterr()
    assert plan_lint.main(["--manifest", str(base), "--resume"]) == 0
    out = capsys.readouterr().out
    assert "PLAN_RESUME:state" in out
    assert "done:    WU1" in out
    assert "partial: WU2" in out
    assert "failed:  WU3" in out
    assert "pending: -" in out


def test_cli_resume_json_mode(tmp_path, capsys) -> None:
    base = tmp_path / "resume"
    plan_lint.main(["--manifest", str(base), "--mark-done", "WU1"])
    capsys.readouterr()
    plan_lint.main(["--manifest", str(base), "--resume", "--json"])
    assert json.loads(capsys.readouterr().out)["done"] == ["WU1"]


def test_cli_resume_derives_pending_from_the_plan(tmp_path, capsys) -> None:
    base = tmp_path / "resume"
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps([{"id": "WU1", "files": ["a"]}, {"id": "WU2", "files": ["b"]}]),
        encoding="utf-8",
    )
    plan_lint.main(["--manifest", str(base), "--mark-done", "WU1"])
    capsys.readouterr()
    plan_lint.main(["--manifest", str(base), "--resume", "--plan", str(path), "--json"])
    state = json.loads(capsys.readouterr().out)
    assert state["done"] == ["WU1"]
    assert state["pending"] == ["WU2"]


def test_cli_resume_with_an_unreadable_plan_falls_back_to_no_ids(
    tmp_path, capsys
) -> None:
    base = tmp_path / "resume"
    plan_lint.main(["--manifest", str(base), "--mark-done", "WU1"])
    capsys.readouterr()
    plan_lint.main(
        [
            "--manifest",
            str(base),
            "--resume",
            "--plan",
            str(tmp_path / "absent.json"),
            "--json",
        ]
    )
    assert json.loads(capsys.readouterr().out)["pending"] == []


def test_cli_resume_with_a_plan_that_has_no_units_falls_back(tmp_path, capsys) -> None:
    base = tmp_path / "resume"
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"title": "empty"}), encoding="utf-8")
    plan_lint.main(["--manifest", str(base), "--mark-done", "WU1"])
    capsys.readouterr()
    plan_lint.main(["--manifest", str(base), "--resume", "--plan", str(path), "--json"])
    assert json.loads(capsys.readouterr().out)["pending"] == []


# --- the --ids / --next work-list surface (a saved Workflow's unit list is a JS
# --- array, not a plan file, so --plan cannot name its units) ------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        (",  ,", None),
        ("WU1", ["WU1"]),
        ("WU1,WU2", ["WU1", "WU2"]),
        ("WU1 WU2", ["WU1", "WU2"]),
        (" WU1 , WU2,WU3 ", ["WU1", "WU2", "WU3"]),
    ],
)
def test_split_ids_accepts_commas_and_whitespace(raw, expected) -> None:
    """A blank --ids must stay None, not become [] (which reads as zero units)."""
    assert plan_lint._split_ids(raw) == expected


def test_ids_beats_plan_as_the_work_list(tmp_path, capsys) -> None:
    base = tmp_path / "resume"
    path = tmp_path / "plan.json"
    path.write_text(json.dumps([{"id": "FROM_PLAN", "files": ["a"]}]), encoding="utf-8")
    plan_lint.main(
        [
            "--manifest",
            str(base),
            "--resume",
            "--json",
            "--plan",
            str(path),
            "--ids",
            "FROM_IDS",
        ]
    )
    assert json.loads(capsys.readouterr().out)["pending"] == ["FROM_IDS"]


def test_next_prints_only_the_ids_still_to_run(tmp_path, capsys) -> None:
    base = tmp_path / "resume"
    plan_lint.main(["--manifest", str(base), "--mark-done", "WU1"])
    plan_lint.main(["--manifest", str(base), "--mark-partial", "WU2"])
    plan_lint.main(["--manifest", str(base), "--mark-failed", "WU3"])
    capsys.readouterr()
    assert (
        plan_lint.main(["--manifest", str(base), "--next", "--ids", "WU1,WU2,WU3,WU4"])
        == 0
    )
    # partial + failed + pending, one per line, nothing else. WU1 (done) is absent.
    assert capsys.readouterr().out.splitlines() == ["WU2", "WU3", "WU4"]


def test_next_prints_nothing_when_no_work_list_is_declared(tmp_path, capsys) -> None:
    base = tmp_path / "resume"
    plan_lint.main(["--manifest", str(base), "--mark-done", "WU1"])
    capsys.readouterr()
    assert plan_lint.main(["--manifest", str(base), "--next"]) == 0
    assert capsys.readouterr().out == ""


def test_next_derives_the_work_list_from_a_plan_when_ids_is_absent(
    tmp_path, capsys
) -> None:
    base = tmp_path / "resume"
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps([{"id": "WU1", "files": ["a"]}, {"id": "WU2", "files": ["b"]}]),
        encoding="utf-8",
    )
    plan_lint.main(["--manifest", str(base), "--mark-done", "WU1"])
    capsys.readouterr()
    plan_lint.main(["--manifest", str(base), "--next", "--plan", str(path)])
    assert capsys.readouterr().out.splitlines() == ["WU2"]


def test_wu_ids_returns_none_when_neither_ids_nor_plan_is_given() -> None:
    args = plan_lint.argparse.Namespace(ids=None, plan=None)
    assert plan_lint._wu_ids(args) is None


def test_wu_ids_tolerates_an_args_namespace_without_an_ids_attribute() -> None:
    args = plan_lint.argparse.Namespace(plan=None)
    assert plan_lint._wu_ids(args) is None


def test_cli_manifest_without_an_action_is_a_noop(tmp_path, capsys) -> None:
    assert plan_lint.main(["--manifest", str(tmp_path / "resume")]) == 0
    assert "PLAN_RESUME:noop" in capsys.readouterr().out


def test_cli_with_no_arguments_prints_help_and_exits_zero(capsys) -> None:
    assert plan_lint.main([]) == 0
    assert "plan_lint_stage0" in capsys.readouterr().out
