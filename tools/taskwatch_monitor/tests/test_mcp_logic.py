"""Unit tests for mcp_server.logic — the orchestration behind the MCP tools.

Exercised against real temp registry files (the filesystem seam) and, where the
poll result must be deterministic, an injected ``snapshot_fn``. Covers every
branch: template/registry errors, unknown-id paths, the history-prior present /
absent split, and the remediate opt-in on/off.
"""

from __future__ import annotations

from pathlib import Path

from core.history import HistoryStore
from core.models import (
    EtaEstimate,
    Provenance,
    TaskSpec,
    TaskStatus,
)
from cli.status import TaskView
from mcp_server import logic


# --------------------------------------------------------------------------- helpers
def _reg(tmp_path: Path) -> str:
    return str(tmp_path / "taskwatch.toml")


def _log(tmp_path: Path) -> str:
    return str(tmp_path / "run.log")


def _register(tmp_path: Path, task_id: str = "t1") -> dict[str, object]:
    return logic.register_task(
        "generic-logfile",
        task_id,
        {"path": _log(tmp_path)},
        registry=_reg(tmp_path),
    )


def _fake_view(task_id: str) -> TaskView:
    return TaskView(
        id=task_id,
        adapter="local-file-tail",
        parser="generic-logfile",
        status=TaskStatus.RUNNING,
        exists=True,
        done=3.0,
        total=10.0,
        fraction=0.3,
        phase="",
        gpu="",
        terminal=False,
        eta=EtaEstimate(p50=None, p90=None, provenance=Provenance.NONE),
        progressing=True,
        stalled=False,
        blind=False,
        blind_age=None,
        elapsed_s=None,
        error=None,
        detail="",
    )


# --------------------------------------------------------------------------- register_task
def test_register_task_ok(tmp_path: Path):
    out = _register(tmp_path)
    assert out["ok"] is True
    task = out["task"]
    assert isinstance(task, dict) and task["id"] == "t1"
    assert Path(_reg(tmp_path)).exists()


def test_register_task_unknown_template(tmp_path: Path):
    out = logic.register_task("no-such-template", "t1", registry=_reg(tmp_path))
    assert out["ok"] is False
    assert "unknown template" in str(out["error"])


def test_register_task_duplicate_id(tmp_path: Path):
    _ = _register(tmp_path)
    out = _register(tmp_path)  # same id → append_spec raises RegistryError
    assert out["ok"] is False
    assert "duplicate task id" in str(out["error"])


# --------------------------------------------------------------------------- list_tasks
def test_list_tasks_empty(tmp_path: Path):
    out = logic.list_tasks(_reg(tmp_path))  # missing file → empty registry
    assert out == {"ok": True, "tasks": []}


def test_list_tasks_populated(tmp_path: Path):
    _ = _register(tmp_path)
    out = logic.list_tasks(_reg(tmp_path))
    tasks = out["tasks"]
    assert isinstance(tasks, list) and len(tasks) == 1


def test_list_tasks_malformed(tmp_path: Path):
    Path(_reg(tmp_path)).write_text('task = "not-an-array"\n', encoding="utf-8")
    out = logic.list_tasks(_reg(tmp_path))
    assert out["ok"] is False


# --------------------------------------------------------------------------- status
def test_status_all_tasks(tmp_path: Path):
    _ = _register(tmp_path)
    out = logic.status(_reg(tmp_path), snapshot_fn=lambda s, **k: [_fake_view(s[0].id)])
    tasks = out["tasks"]
    assert isinstance(tasks, list) and len(tasks) == 1


def test_status_filtered_found(tmp_path: Path):
    _ = _register(tmp_path, "t1")
    _ = _register(tmp_path, "t2")
    seen: list[str] = []

    def snap(specs: list[TaskSpec], **_kw: object) -> list[TaskView]:
        seen.extend(spec.id for spec in specs)
        return [_fake_view(spec.id) for spec in specs]

    out = logic.status(_reg(tmp_path), task_id="t2", snapshot_fn=snap)
    assert out["ok"] is True and seen == ["t2"]


def test_status_filtered_unknown(tmp_path: Path):
    _ = _register(tmp_path)
    out = logic.status(_reg(tmp_path), task_id="nope")
    assert out["ok"] is False
    assert "unknown task id" in str(out["error"])


def test_status_malformed(tmp_path: Path):
    Path(_reg(tmp_path)).write_text('task = "x"\n', encoding="utf-8")
    out = logic.status(_reg(tmp_path))
    assert out["ok"] is False


def test_status_with_prior_present(tmp_path: Path):
    _ = _register(tmp_path)
    db = str(tmp_path / "hist.sqlite")
    with HistoryStore(db) as hist:
        hist.record("generic-logfile", 120.0, ts=1.0)
    captured: dict[str, object] = {}

    def snap(specs: list[TaskSpec], **kw: object) -> list[TaskView]:
        captured.update(kw)
        return [_fake_view(spec.id) for spec in specs]

    out = logic.status(_reg(tmp_path), history=db, snapshot_fn=snap)
    assert out["ok"] is True
    assert captured["priors"] == {"generic-logfile": 120.0}


def test_status_with_history_no_prior(tmp_path: Path):
    _ = _register(tmp_path)
    db = str(tmp_path / "empty.sqlite")
    with HistoryStore(db):  # creates the schema, records nothing
        pass
    captured: dict[str, object] = {}

    def snap(specs: list[TaskSpec], **kw: object) -> list[TaskView]:
        captured.update(kw)
        return [_fake_view(spec.id) for spec in specs]

    out = logic.status(_reg(tmp_path), history=db, snapshot_fn=snap)
    assert out["ok"] is True and captured["priors"] == {}


def test_status_default_snapshot_real_poll(tmp_path: Path):
    # Exercise the default snapshot_fn (cli.engine.snapshot) end-to-end: the log
    # path does not exist, so the task polls to a deterministic PENDING view.
    _ = _register(tmp_path)
    out = logic.status(_reg(tmp_path))
    tasks = out["tasks"]
    assert isinstance(tasks, list) and len(tasks) == 1
    view = tasks[0]
    assert isinstance(view, dict) and view["status"] == "pending"


# --------------------------------------------------------------------------- attach_watch
def test_attach_watch_ok_no_remediate(tmp_path: Path):
    _ = _register(tmp_path)
    out = logic.attach_watch(
        "t1", registry=_reg(tmp_path), snapshot_fn=lambda s, **k: [_fake_view("t1")]
    )
    assert out["ok"] is True and out["watching"] is True
    assert out["remediate"] is False  # unchanged
    assert isinstance(out["status"], dict)


def test_attach_watch_sets_remediate(tmp_path: Path):
    _ = _register(tmp_path)
    out = logic.attach_watch(
        "t1",
        remediate=True,
        registry=_reg(tmp_path),
        snapshot_fn=lambda s, **k: [_fake_view("t1")],
    )
    assert out["remediate"] is True
    # persisted: reloading the registry shows the flipped opt-in
    reloaded = logic.list_tasks(_reg(tmp_path))
    tasks = reloaded["tasks"]
    assert isinstance(tasks, list)
    first = tasks[0]
    assert isinstance(first, dict) and first["remediate"] is True


def test_attach_watch_unknown(tmp_path: Path):
    _ = _register(tmp_path)
    out = logic.attach_watch("ghost", registry=_reg(tmp_path))
    assert out["ok"] is False and "unknown task id" in str(out["error"])


def test_attach_watch_malformed(tmp_path: Path):
    Path(_reg(tmp_path)).write_text('task = "x"\n', encoding="utf-8")
    out = logic.attach_watch("t1", registry=_reg(tmp_path))
    assert out["ok"] is False


# --------------------------------------------------------------------------- set_notify
def test_set_notify_ok(tmp_path: Path):
    _ = _register(tmp_path)
    out = logic.set_notify("t1", ["terminal", "stall"], registry=_reg(tmp_path))
    assert out["ok"] is True
    task = out["task"]
    assert isinstance(task, dict) and task["notify"] == ["terminal", "stall"]
    # persisted
    reloaded = logic.list_tasks(_reg(tmp_path))
    tasks = reloaded["tasks"]
    assert isinstance(tasks, list)
    first = tasks[0]
    assert isinstance(first, dict) and first["notify"] == ["terminal", "stall"]


def test_set_notify_unknown(tmp_path: Path):
    _ = _register(tmp_path)
    out = logic.set_notify("ghost", ["terminal"], registry=_reg(tmp_path))
    assert out["ok"] is False and "unknown task id" in str(out["error"])


def test_set_notify_malformed(tmp_path: Path):
    Path(_reg(tmp_path)).write_text('task = "x"\n', encoding="utf-8")
    out = logic.set_notify("t1", ["terminal"], registry=_reg(tmp_path))
    assert out["ok"] is False
