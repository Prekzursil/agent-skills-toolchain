import json
import pathlib

import backends.databricks as m
from backends import base
from harness.contract import Unit


def _u(tmp):
    return Unit(
        id="x", lane="smoke", prompt="p", artifact=str(pathlib.Path(tmp) / "x.md")
    )


def test_is_a_build_backend(tmp_path):
    assert isinstance(
        m.DatabricksBuildBackend(run_cmd=lambda a: (0, "", ""), workdir=tmp_path),
        base.BuildBackend,
    )
    # workdir=None default arm -> cwd (construction only; writes nothing)
    default_wd = m.DatabricksBuildBackend(run_cmd=lambda a: (0, "", ""))
    assert default_wd.workdir == pathlib.Path.cwd()


def test_submit_writes_payload_and_returns_job(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(m.build_batch, "build_batch", lambda units, name: {"units": []})
    monkeypatch.setattr(m.build_batch, "write_batch", lambda b, p: p)
    monkeypatch.setattr(
        m.submit,
        "build_payload",
        lambda *a, **k: seen.update(bp=a, bpkw=k) or {"run_name": "x"},
    )
    monkeypatch.setattr(m.submit, "submit", lambda pf, rc: seen.update(pf=pf) or 4242)
    be = m.DatabricksBuildBackend(run_cmd=lambda a: (0, "", ""), workdir=tmp_path)
    job = be.submit(
        [_u(tmp_path)], {"name": "t", "batch_dbfs": "b", "result_dir": "/r"}
    )
    assert (
        isinstance(job, base.Job) and job.ref == "4242" and job.backend == "databricks"
    )
    assert job.meta == {"name": "t", "n": 1}
    assert (
        tmp_path / "payload.json"
    ).exists()  # self-contained: it wrote what it submitted
    assert json.loads((tmp_path / "payload.json").read_text(encoding="utf-8")) == {
        "run_name": "x"
    }
    # the invariant itself: the path handed to submit.submit IS the file it wrote
    assert seen["pf"] == tmp_path / "payload.json"
    # R1: build_payload called with 3 positional args and NO kwargs -> no extra_env,
    # so no GITHUB_TOKEN/GH_TOKEN can reach spark_env_vars
    assert len(seen["bp"]) == 3 and seen["bpkw"] == {}


def test_submit_none_run_id_gives_empty_ref(tmp_path, monkeypatch):
    monkeypatch.setattr(m.build_batch, "build_batch", lambda u, n: {})
    monkeypatch.setattr(m.build_batch, "write_batch", lambda b, p: p)
    monkeypatch.setattr(m.submit, "build_payload", lambda n, b, r, e=None: {})
    monkeypatch.setattr(m.submit, "submit", lambda pf, rc: None)
    be = m.DatabricksBuildBackend(run_cmd=lambda a: (0, "", ""), workdir=tmp_path)
    job = be.submit([_u(tmp_path)], {"batch_dbfs": "b", "result_dir": "/r"})
    assert job.ref == ""
    assert job.meta == {"name": "batch", "n": 1}  # meta without "name" -> default


def test_poll_parses_state_and_handles_bad_json(tmp_path):
    be = m.DatabricksBuildBackend(
        run_cmd=lambda a: (
            0,
            json.dumps({"state": {"life_cycle_state": "RUNNING"}}),
            "",
        ),
        workdir=tmp_path,
    )
    assert be.poll(base.Job("databricks", "1")) == "RUNNING"
    be2 = m.DatabricksBuildBackend(
        run_cmd=lambda a: (0, "not json", ""), workdir=tmp_path
    )
    assert be2.poll(base.Job("databricks", "1")) == "?"
    # valid JSON but no "state" key -> the falsy arm of `(… .get("state") or {})`
    be3 = m.DatabricksBuildBackend(
        run_cmd=lambda a: (0, json.dumps({}), ""), workdir=tmp_path
    )
    assert be3.poll(base.Job("databricks", "1")) == "?"


def test_harvest_cancel_teardown(tmp_path):
    calls = []
    be = m.DatabricksBuildBackend(
        run_cmd=lambda a: calls.append(a) or (0, "", ""), workdir=tmp_path
    )
    assert be.harvest(base.Job("databricks", "1"), tmp_path) == {}
    be.cancel(base.Job("databricks", "1"))
    be.teardown(base.Job("databricks", "1"))
    assert any("cancel-run" in c for c in calls)
    # cancel is the ONLY CLI call: harvest and teardown must stay genuine no-ops
    assert len(calls) == 1
