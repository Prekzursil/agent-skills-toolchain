"""Unit tests for the TG-2 diff-scoped mutation gate.

These are FAST and hermetic: every subprocess seam (git, cosmic-ray) is faked, so
the suite runs with no git repo and without invoking cosmic-ray. They drive the
gate module to 100% line+branch coverage. The REAL cosmic-ray RED/GREEN proof
lives in ``test_mutation_gate_demo.py`` (marked ``demo``).
"""

import json
import tomllib
from types import SimpleNamespace

import mutation_gate as mg
import pytest


def _proc(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# A representative cosmic-ray ``dump`` line for one SURVIVED mutant.
SURVIVOR_DUMP = json.dumps(
    [
        {
            "mutations": [
                {
                    "module_path": "src/a.py",
                    "operator_name": "core/ReplaceComparisonOperator_GtE_Gt",
                    "start_pos": [8, 16],
                    "definition_name": "is_large_enough",
                }
            ]
        },
        {
            "test_outcome": "survived",
            "diff": "--- d ---\n-    return size >= x\n+    return size > x",
        },
    ]
)


# --------------------------------------------------------------------------- #
# is_test_path
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/pkg/mod.py", False),
        ("src/tests/thing.py", True),
        ("a/test/thing.py", True),
        ("pkg/test_thing.py", True),
        ("pkg/thing_test.py", True),
        ("pkg/latest_thing.py", False),
    ],
)
def test_is_test_path(path, expected):
    assert mg.is_test_path(path) is expected


# --------------------------------------------------------------------------- #
# scope_changed_files
# --------------------------------------------------------------------------- #
def test_scope_changed_files_filters_all_dimensions():
    diff = "\n".join(
        [
            "",  # blank -> skipped
            "src\\a.py",  # backslash normalized, kept
            "notes.txt",  # non-.py -> skipped
            "vendor/lib.py",  # excluded substring -> skipped
            "src/tests/test_b.py",  # test file -> skipped (include_tests False)
            "src/a.py",  # duplicate -> deduped
        ]
    )
    assert mg.scope_changed_files(diff) == ["src/a.py"]


def test_scope_changed_files_include_prefix_filter():
    diff = "src/a.py\nother/b.py"
    assert mg.scope_changed_files(diff, includes=("src/",)) == ["src/a.py"]


def test_scope_changed_files_include_exact_file():
    diff = "src/a.py\nsrc/b.py"
    assert mg.scope_changed_files(diff, includes=("src/a.py",)) == ["src/a.py"]


def test_scope_changed_files_can_keep_tests():
    diff = "src/tests/test_b.py"
    assert mg.scope_changed_files(diff, include_tests=True) == ["src/tests/test_b.py"]


# --------------------------------------------------------------------------- #
# render_cosmic_ray_config
# --------------------------------------------------------------------------- #
def test_render_config_roundtrips_and_escapes():
    cfg = mg.render_cosmic_ray_config(
        "C:/x/mod.py", '"C:/py" -m pytest', 12.5, excluded_modules=["a", "b"]
    )
    data = tomllib.loads(cfg)
    assert data["cosmic-ray"]["module-path"] == "C:/x/mod.py"
    assert data["cosmic-ray"]["timeout"] == 12.5
    assert data["cosmic-ray"]["test-command"] == '"C:/py" -m pytest'
    assert data["cosmic-ray"]["excluded-modules"] == ["a", "b"]
    assert data["cosmic-ray"]["distributor"]["name"] == "local"


def test_render_config_empty_excludes():
    data = tomllib.loads(mg.render_cosmic_ray_config("m.py", "py -m pytest", 30.0))
    assert data["cosmic-ray"]["excluded-modules"] == []


# --------------------------------------------------------------------------- #
# _format_test_command
# --------------------------------------------------------------------------- #
def test_format_test_command_quotes_and_normalizes_python():
    out = mg._format_test_command("{python} -m pytest -x", "C:\\a b\\python.exe")
    assert out == '"C:/a b/python.exe" -m pytest -x'


# --------------------------------------------------------------------------- #
# parse_dump / extract_survivors
# --------------------------------------------------------------------------- #
def test_parse_dump_skips_junk_and_defaults_missing_fields():
    text = "\n".join(
        [
            "",  # blank
            "not-json",  # JSONDecodeError
            '{"a": 1}',  # not a list
            '[{"mutations": []}]',  # len < 2
            '[{"mutations": []}, {"test_outcome": "killed"}]',  # no mutations
            '[{"mutations": [{"module_path": "m.py", "operator_name": "o"}]}, {"test_outcome": "killed"}]',
        ]
    )
    recs = mg.parse_dump(text)
    assert len(recs) == 1
    assert recs[0]["line"] == 0 and recs[0]["column"] == 0 and recs[0]["function"] == ""
    assert recs[0]["outcome"] == "killed"


def test_extract_survivors_only_survived():
    killed = {
        "file": "b.py",
        "line": 1,
        "column": 0,
        "operator": "op",
        "function": "g",
        "outcome": "killed",
        "diff": "d",
    }
    recs = [*mg.parse_dump(SURVIVOR_DUMP), killed]
    survivors = mg.extract_survivors(recs)
    assert len(survivors) == 1  # the killed record is filtered out
    s = survivors[0]
    assert s.file == "src/a.py" and s.line == 8 and s.column == 16
    assert s.function == "is_large_enough" and s.operator.endswith("GtE_Gt")


# --------------------------------------------------------------------------- #
# format_report / summary_dict
# --------------------------------------------------------------------------- #
def test_format_report_success():
    result = mg.GateResult(0, ("src/a.py",), ())
    assert "SUCCESS" in mg.format_report(result, "py -m pytest")


def test_format_report_failure_lists_survivors_and_names_weak_suite():
    survivor = mg.Survivor(
        "src/a.py", 8, 16, "core/X_GtE_Gt", "is_large_enough", "-x\n+y"
    )
    survivor_nofunc = mg.Survivor(
        "src/b.py", 3, 0, "core/NumberReplacer", "", ""
    )  # empty diff branch
    result = mg.GateResult(1, ("src/a.py", "src/b.py"), (survivor, survivor_nofunc))
    report = mg.format_report(result, "PYTEST-CMD")
    assert "FAILED" in report
    assert "src/a.py:8" in report and "is_large_enough" in report
    assert "src/b.py:3" in report
    assert "PYTEST-CMD" in report  # names the weak test suite


def test_summary_dict_shape():
    survivor = mg.Survivor("src/a.py", 8, 16, "op", "fn", "diff")
    summary = mg.summary_dict(mg.GateResult(1, ("src/a.py",), (survivor,)))
    assert summary["exit_code"] == 1
    assert summary["scoped_files"] == ["src/a.py"]
    assert summary["survivors"][0]["file"] == "src/a.py"
    assert summary["survivors"][0]["function"] == "fn"
    empty = mg.summary_dict(mg.GateResult(0, (), ()))
    assert empty["survivors"] == [] and empty["scoped_files"] == []


# --------------------------------------------------------------------------- #
# default_git_diff
# --------------------------------------------------------------------------- #
def test_default_git_diff_builds_triple_dot_range_and_returns_stdout():
    calls = []

    def fake_run(argv, **kw):
        calls.append((argv, kw))
        return _proc(stdout="a.py\nb.py\n")

    out = mg.default_git_diff("origin/main", "/repo", run=fake_run)
    assert out == "a.py\nb.py\n"
    argv = calls[0][0]
    assert argv[:2] == ["git", "-C"] and argv[2] == "/repo"
    assert argv[3:5] == ["diff", "--name-only"]
    assert argv[-1] == "origin/main...HEAD"


def test_default_git_diff_raises_on_error():
    with pytest.raises(mg.GateError, match="git diff failed"):
        mg.default_git_diff(
            "x", ".", run=lambda *a, **k: _proc(returncode=128, stderr="fatal: bad rev")
        )


# --------------------------------------------------------------------------- #
# default_mutation_run
# --------------------------------------------------------------------------- #
def test_default_mutation_run_invokes_init_exec_dump(tmp_path):
    seen = []

    def fake_run(argv, **kw):
        seen.append(argv)
        if "dump" in argv:
            return _proc(stdout=SURVIVOR_DUMP + "\n")
        return _proc()

    out = mg.default_mutation_run(
        "x.py", str(tmp_path), "{python} -m pytest", 30.0, "python", run=fake_run
    )
    assert "survived" in out
    subcommands = [
        a[a.index("cosmic_ray.cli") + 1] for a in seen if "cosmic_ray.cli" in a
    ]
    assert subcommands == ["init", "exec", "dump"]


def test_default_mutation_run_raises_when_a_step_fails(tmp_path):
    def fake_run(argv, **kw):
        return _proc(returncode=3, stderr="explode") if "exec" in argv else _proc()

    with pytest.raises(mg.GateError, match="cosmic-ray exec failed"):
        mg.default_mutation_run(
            "x.py", str(tmp_path), "{python} -m pytest", 30.0, "python", run=fake_run
        )


# --------------------------------------------------------------------------- #
# run_gate
# --------------------------------------------------------------------------- #
def test_run_gate_is_diff_scoped_and_mutates_only_inscope_files():
    mutated = []

    def fake_mut(file, repo_root, test_command, timeout, python_exe):
        mutated.append(file)
        return ""  # no records -> no survivors

    diff = "src/a.py\nsrc/tests/test_b.py\nnotes.txt\nvendor/lib.py\nsrc/a.py\n"
    result = mg.run_gate(
        base="origin/main",
        repo_root=".",
        diff_runner=lambda base, root: diff,
        mutation_runner=fake_mut,
        log=lambda *_: None,
    )
    assert mutated == ["src/a.py"]  # the ONLY in-scope changed file
    assert result.exit_code == 0
    assert result.survivors == ()


def test_run_gate_flags_survivor_and_exits_nonzero():
    logs = []
    result = mg.run_gate(
        files=["src/a.py"],
        repo_root=".",
        python_exe="python",
        mutation_runner=lambda *a: SURVIVOR_DUMP,
        diff_runner=lambda *a: "",
        log=logs.append,
    )
    assert result.exit_code == 1
    assert len(result.survivors) == 1
    assert result.survivors[0].function == "is_large_enough"
    assert "FAILED" in logs[-1]


def test_run_gate_no_scoped_files_is_success():
    logs = []
    result = mg.run_gate(
        files=[],
        repo_root=".",
        mutation_runner=lambda *a: SURVIVOR_DUMP,
        diff_runner=lambda *a: "",
        log=logs.append,
    )
    assert result.exit_code == 0
    assert result.scoped_files == ()
    assert "SUCCESS" in logs[-1]


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def test_main_success_returns_zero(monkeypatch):
    monkeypatch.setattr(mg, "default_mutation_run", lambda *a: "")
    # --include exercises the include-filter CLI branch.
    assert (
        mg.main(["--files", "src/a.py", "--repo-root", ".", "--include", "src/"]) == 0
    )


def test_main_failure_writes_json(monkeypatch, tmp_path):
    monkeypatch.setattr(mg, "default_mutation_run", lambda *a: SURVIVOR_DUMP)
    out = tmp_path / "gate.json"
    # --exclude exercises the explicit-exclude CLI branch.
    rc = mg.main(["--files", "src/a.py", "--exclude", "somedir/", "--json", str(out)])
    assert rc == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["exit_code"] == 1
    assert data["survivors"][0]["file"] == "src/a.py"


def test_main_reports_gate_error(monkeypatch):
    def boom(base, repo_root):
        raise mg.GateError("no such base")

    monkeypatch.setattr(mg, "default_git_diff", boom)
    assert mg.main(["--base", "nope"]) == 2
