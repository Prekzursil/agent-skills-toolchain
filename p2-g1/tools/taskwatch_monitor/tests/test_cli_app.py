"""Tests for cli/app.py — argparse surface (register / list / status)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.history import HistoryStore  # noqa: E402
from core.models import TaskSpec  # noqa: E402
from cli import app  # noqa: E402
from cli import status as st  # noqa: E402


def _args(*argv: str):
    return app.build_parser().parse_args(list(argv))


def _write_registry(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


_GOOD_REGISTRY = """
[[task]]
id = "run-1"
adapter = "local-file-tail"
parser = "generic-logfile"

[task.config]
path = "/logs/run.log"
"""

_BAD_REGISTRY = """
[[task]]
id = "run-1"
adapter = "nonexistent-adapter"
"""


# ── _coerce_scalar ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("false", False),
        ("42", 42),
        ("1.5", 1.5),
        ("hello", "hello"),
    ],
)
def test_coerce_scalar(raw, expected):
    assert app._coerce_scalar(raw) == expected


# ── _parse_config ──────────────────────────────────────────────────────────────


def test_parse_config_ok():
    assert app._parse_config(["path=/x", "n=3"]) == {"path": "/x", "n": 3}


def test_parse_config_missing_equals():
    with pytest.raises(ValueError, match="key=value"):
        _ = app._parse_config(["noequals"])


def test_parse_config_empty_key():
    with pytest.raises(ValueError, match="key=value"):
        _ = app._parse_config(["=value"])


# ── _load_specs_or_none ────────────────────────────────────────────────────────


def test_load_specs_or_none_ok(tmp_path):
    path = tmp_path / "r.toml"
    _write_registry(path, _GOOD_REGISTRY)
    specs = app._load_specs_or_none(path)
    assert specs is not None and specs[0].id == "run-1"


def test_load_specs_or_none_error(tmp_path, capsys):
    path = tmp_path / "r.toml"
    _write_registry(path, _BAD_REGISTRY)
    assert app._load_specs_or_none(path) is None
    assert "Registry error" in capsys.readouterr().out


# ── _load_priors ───────────────────────────────────────────────────────────────


def test_load_priors_no_history_is_empty():
    spec = TaskSpec(id="a", adapter="local-file-tail", parser="generic-logfile")
    assert app._load_priors(None, [spec]) == {}


def test_load_priors_with_and_without_match(tmp_path):
    db = str(tmp_path / "h.db")
    with HistoryStore(db) as store_:
        store_.record("generic-logfile", 120.0, ts=1.0)
    specs = [
        TaskSpec(id="a", adapter="local-file-tail", task_type="generic-logfile"),
        TaskSpec(id="b", adapter="process-pid", task_type="unseen-type"),
    ]
    priors = app._load_priors(db, specs)
    assert priors == {"generic-logfile": 120.0}


# ── cmd_register ───────────────────────────────────────────────────────────────


def test_register_success(tmp_path, capsys):
    path = tmp_path / "r.toml"
    rc = app.cmd_register(
        _args(
            "register",
            "generic-logfile",
            "run-1",
            "--config",
            f"path={tmp_path}/l",
            "--registry",
            str(path),
        )
    )
    assert rc == 0
    assert "Registered 'run-1'" in capsys.readouterr().out
    assert path.exists()


def test_register_bad_config(tmp_path, capsys):
    rc = app.cmd_register(
        _args(
            "register",
            "generic-logfile",
            "x",
            "--config",
            "oops",
            "--registry",
            str(tmp_path / "r.toml"),
        )
    )
    assert rc == 2
    assert "key=value" in capsys.readouterr().out


def test_register_template_error(tmp_path, capsys):
    # generic-logfile requires config.path; omit it → TemplateError
    rc = app.cmd_register(
        _args(
            "register", "generic-logfile", "x", "--registry", str(tmp_path / "r.toml")
        )
    )
    assert rc == 2
    assert "missing config" in capsys.readouterr().out


def test_register_load_error(tmp_path, capsys):
    path = tmp_path / "r.toml"
    _write_registry(path, _BAD_REGISTRY)
    rc = app.cmd_register(
        _args(
            "register",
            "generic-logfile",
            "x",
            "--config",
            "path=/l",
            "--registry",
            str(path),
        )
    )
    assert rc == 2
    assert "Registry error" in capsys.readouterr().out


def test_register_duplicate_id(tmp_path, capsys):
    path = tmp_path / "r.toml"
    _write_registry(path, _GOOD_REGISTRY)
    rc = app.cmd_register(
        _args(
            "register",
            "generic-logfile",
            "run-1",
            "--config",
            "path=/l",
            "--registry",
            str(path),
        )
    )
    assert rc == 2
    assert "duplicate task id" in capsys.readouterr().out


# ── cmd_list ───────────────────────────────────────────────────────────────────


def test_list_load_error(tmp_path):
    path = tmp_path / "r.toml"
    _write_registry(path, _BAD_REGISTRY)
    assert app.cmd_list(_args("list", "--registry", str(path))) == 2


def test_list_table(tmp_path, capsys):
    path = tmp_path / "r.toml"
    _write_registry(path, _GOOD_REGISTRY)
    assert app.cmd_list(_args("list", "--registry", str(path))) == 0
    assert "run-1" in capsys.readouterr().out


def test_list_json(tmp_path, capsys):
    path = tmp_path / "r.toml"
    _write_registry(path, _GOOD_REGISTRY)
    assert app.cmd_list(_args("list", "--registry", str(path), "--json")) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["id"] == "run-1"


# ── cmd_status ─────────────────────────────────────────────────────────────────


def test_status_load_error(tmp_path):
    path = tmp_path / "r.toml"
    _write_registry(path, _BAD_REGISTRY)
    assert app.cmd_status(_args("status", "--registry", str(path))) == 2


def test_status_empty_registry(tmp_path, capsys):
    path = tmp_path / "r.toml"
    _write_registry(path, "")
    assert app.cmd_status(_args("status", "--registry", str(path))) == 0
    assert "No tasks registered" in capsys.readouterr().out


def test_status_watch_routes_to_tui(tmp_path, monkeypatch):
    path = tmp_path / "r.toml"
    _write_registry(path, _GOOD_REGISTRY)
    calls: list[object] = []
    monkeypatch.setattr(app.tui, "run_watch", lambda specs, **kw: calls.append(kw))
    assert app.cmd_status(_args("status", "--registry", str(path), "--watch")) == 0
    assert calls and "interval" in calls[0]


def _fake_view() -> st.TaskView:
    spec = TaskSpec(id="run-1", adapter="local-file-tail", parser="generic-logfile")
    from core.models import PollResult
    from probes.base import ProbeReading

    poll = PollResult(exists=True, mtime=1.0, lines=["2/8"], liveness=True)
    reading = ProbeReading(
        done=2.0, total=8.0, phase="", frontier=2.0, gpu="", terminal=False, detail=""
    )
    return st.assemble_view(
        spec,
        poll,
        reading,
        progressing=True,
        stalled=False,
        elapsed_s=None,
        prior_duration_s=None,
    )


def test_status_report(tmp_path, monkeypatch, capsys):
    path = tmp_path / "r.toml"
    _write_registry(path, _GOOD_REGISTRY)
    monkeypatch.setattr(app.engine, "snapshot", lambda specs, **kw: [_fake_view()])
    assert app.cmd_status(_args("status", "--registry", str(path))) == 0
    assert "run-1" in capsys.readouterr().out


def test_status_json(tmp_path, monkeypatch, capsys):
    path = tmp_path / "r.toml"
    _write_registry(path, _GOOD_REGISTRY)
    monkeypatch.setattr(app.engine, "snapshot", lambda specs, **kw: [_fake_view()])
    assert app.cmd_status(_args("status", "--registry", str(path), "--json")) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["id"] == "run-1"


# ── main dispatch ──────────────────────────────────────────────────────────────


def test_main_no_command_prints_help(capsys):
    assert app.main(["taskwatch"]) == 2
    assert "usage" in capsys.readouterr().out.lower()


def test_main_routes_register(tmp_path, capsys):
    path = tmp_path / "r.toml"
    rc = app.main(
        [
            "taskwatch",
            "register",
            "generic-logfile",
            "run-1",
            "--config",
            "path=/l",
            "--registry",
            str(path),
        ]
    )
    assert rc == 0
    assert path.exists()


def test_main_routes_list(tmp_path, capsys):
    path = tmp_path / "r.toml"
    _write_registry(path, _GOOD_REGISTRY)
    assert app.main(["taskwatch", "list", "--registry", str(path)]) == 0
    assert "run-1" in capsys.readouterr().out
