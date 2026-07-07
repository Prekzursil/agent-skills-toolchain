#!/usr/bin/env python3
"""Unit tests for the Modal MCP wrapper (CLI path + SDK path).

The ``modal`` CLI and SDK are BOTH mocked -- no network, no credentials, no live
Modal calls. The CLI tools are exercised by stubbing ``_modal_common.run_cli`` /
``subprocess``; the SDK sandbox/function tools by stubbing
``_modal_common.load_sdk`` with a fake ``modal`` module (a MagicMock surface plus
a concrete ``FakeSandbox`` for the file/exec behaviour that needs real values).
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_TESTS = os.path.dirname(os.path.abspath(__file__))
_MODAL_MCP = os.path.join(os.path.dirname(_TESTS), "modal-mcp")
if _MODAL_MCP not in sys.path:
    sys.path.insert(0, _MODAL_MCP)

import _modal_common as _c  # noqa: E402
import sandbox  # noqa: E402
import server  # noqa: E402


# --------------------------------------------------------------------------- #
# Fakes.                                                                       #
# --------------------------------------------------------------------------- #
class _FakeStream:
    """A sandbox exec stdout/stderr stream: ``.read()`` + line iteration."""

    def __init__(self, data="", lines=None):
        self._data = data
        self._lines = list(lines) if lines is not None else []

    def read(self):
        return self._data

    def __iter__(self):
        return iter(self._lines)


class _FakeProc:
    def __init__(self, stdout="", stderr="", rc=0, lines=None):
        self.stdout = _FakeStream(stdout, lines)
        self.stderr = _FakeStream(stderr, [])
        self._rc = rc

    def wait(self):
        return self._rc


class _FakeFile:
    def __init__(self, data=""):
        self._data = data
        self.written = None
        self.closed = False

    def read(self):
        return self._data

    def write(self, data):
        self.written = data

    def close(self):
        self.closed = True


class FakeSandbox:
    """Concrete sandbox with recorded calls + configurable payloads."""

    def __init__(
        self,
        object_id="sb-1",
        ls=None,
        poll=None,
        tags=None,
        read_data="hello",
        rc=0,
        lines=None,
        snapshot_id="im-snap-1",
    ):
        self.object_id = object_id
        self._ls = ls if ls is not None else ["a.txt", "b.txt"]
        self._poll = poll
        self._tags = dict(tags or {})
        self._read = read_data
        self._rc = rc
        self._lines = lines if lines is not None else ["l1", "l2"]
        self._snapshot_id = snapshot_id
        self.calls = []
        self.opened = []

    def exec(self, *args, **kwargs):
        self.calls.append(("exec", args, kwargs))
        return _FakeProc(stdout=self._read, rc=self._rc, lines=self._lines)

    def open(self, path, mode="r"):
        handle = _FakeFile(self._read)
        self.opened.append((path, mode, handle))
        return handle

    def ls(self, path):
        self.calls.append(("ls", path))
        return self._ls

    def mkdir(self, path, parents=False):
        self.calls.append(("mkdir", path, parents))

    def rm(self, path, recursive=False):
        self.calls.append(("rm", path, recursive))

    def terminate(self, wait=False):
        self.calls.append(("terminate", wait))

    def poll(self):
        return self._poll

    def wait(self, raise_on_termination=True):
        self.calls.append(("wait", raise_on_termination))

    def snapshot_filesystem(self, timeout=55):
        return SimpleNamespace(object_id=self._snapshot_id)

    def set_tags(self, tags, client=None):
        self._tags = dict(tags)
        self.calls.append(("set_tags", tags, client))

    def get_tags(self):
        return self._tags


def make_modal(sandbox_obj=None, fn_result="RESULT", got="GOT", call_id="fc-1"):
    """A MagicMock ``modal`` module wired to a concrete FakeSandbox."""
    sbx = sandbox_obj or FakeSandbox()
    modal = MagicMock(name="modal")
    modal.Sandbox.from_id.return_value = sbx
    modal.Sandbox.create.return_value = sbx
    modal.Sandbox.list.return_value = [sbx]
    modal.App.lookup.return_value = SimpleNamespace(app_id="ap-1")
    modal.Image.from_registry.return_value = "IMG"
    modal.Image.debian_slim.return_value = "IMG-SLIM"
    modal.Volume.from_name.return_value = "VOL"
    modal.Secret.from_name.return_value = "SEC"
    modal.CloudBucketMount.return_value = "CBM"
    modal.Client.from_credentials.return_value = "CLIENT"
    fn = MagicMock(name="function")
    fn.remote.return_value = fn_result
    fn.spawn.return_value = SimpleNamespace(object_id=call_id)
    modal.Function.from_name.return_value = fn
    call = MagicMock(name="functioncall")
    call.get.return_value = got
    modal.FunctionCall.from_id.return_value = call
    return modal, sbx


@pytest.fixture
def fake_sdk(monkeypatch):
    """Install a fake modal SDK; return (modal, sandbox)."""
    modal, sbx = make_modal()
    monkeypatch.setattr(_c, "load_sdk", lambda: (modal, None))
    return modal, sbx


# --------------------------------------------------------------------------- #
# _modal_common: rotation.                                                     #
# --------------------------------------------------------------------------- #
def test_resolve_profile_from_env():
    env = {
        "MODAL_TOKEN_ID_TEAM": "tid",
        "MODAL_TOKEN_SECRET_TEAM": "tsec",
        "MODAL_ENVIRONMENT_TEAM": "prod",
    }
    assert _c.resolve_profile("team", environ=env) == ("tid", "tsec", "prod")


def test_resolve_profile_slug_non_alnum():
    env = {"MODAL_TOKEN_ID_CA_OAUTH2": "i", "MODAL_TOKEN_SECRET_CA_OAUTH2": "s"}
    assert _c.resolve_profile("ca-oauth2", environ=env) == ("i", "s", "")


def test_resolve_profile_from_toml(tmp_path):
    toml = tmp_path / "modal.toml"
    toml.write_text(
        '[team]\ntoken_id = "ti"\ntoken_secret = "ts"\nenvironment = "prod"\n',
        encoding="utf-8",
    )
    assert _c.resolve_profile("team", environ={}, toml_path=str(toml)) == (
        "ti",
        "ts",
        "prod",
    )


def test_resolve_profile_missing_raises():
    with pytest.raises(KeyError) as exc:
        _c.resolve_profile("nope", environ={}, toml_path="/does/not/exist")
    assert "MODAL_TOKEN_ID_NOPE" in str(exc.value)


def test_rotation_env_sets_tokens_and_drops_profile():
    base = {
        "MODAL_PROFILE": "stale",
        "MODAL_TOKEN_ID_TEAM": "i",
        "MODAL_TOKEN_SECRET_TEAM": "s",
    }
    out = _c.rotation_env(base, profile="team")
    assert out["MODAL_TOKEN_ID"] == "i"
    assert out["MODAL_TOKEN_SECRET"] == "s"
    assert "MODAL_PROFILE" not in out
    # base is not mutated (per-invocation only).
    assert base["MODAL_PROFILE"] == "stale"


def test_rotation_env_environment_override():
    base = {
        "MODAL_TOKEN_ID_TEAM": "i",
        "MODAL_TOKEN_SECRET_TEAM": "s",
        "MODAL_ENVIRONMENT_TEAM": "prof-env",
    }
    out = _c.rotation_env(base, profile="team", environment="explicit")
    assert out["MODAL_ENVIRONMENT"] == "explicit"


def test_rotation_env_no_profile_is_noop_copy():
    base = {"A": "1"}
    out = _c.rotation_env(base)
    assert out == {"A": "1"} and out is not base


# --------------------------------------------------------------------------- #
# _modal_common: CLI runner.                                                   #
# --------------------------------------------------------------------------- #
def test_run_cli_missing_binary(monkeypatch):
    monkeypatch.setattr(_c.shutil, "which", lambda _: None)
    res = _c.run_cli("app", "list")
    assert res["ok"] is False and "modal CLI not found" in res["error"]


def test_run_cli_success(monkeypatch):
    monkeypatch.setattr(_c.shutil, "which", lambda _: "/usr/bin/modal")
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="out", stderr="")

    monkeypatch.setattr(_c.subprocess, "run", fake_run)
    res = _c.run_cli("app", "list", environment="dev")
    assert res["ok"] is True and res["stdout"] == "out"
    assert captured["argv"] == ["/usr/bin/modal", "app", "list"]
    assert captured["env"]["MODAL_ENVIRONMENT"] == "dev"


def test_run_cli_profile_resolution_error(monkeypatch):
    monkeypatch.setattr(_c.shutil, "which", lambda _: "/usr/bin/modal")
    res = _c.run_cli("app", "list", profile="ghost")
    assert res["ok"] is False and "MODAL_TOKEN_ID_GHOST" in res["error"]


def test_run_cli_stream_bounded(monkeypatch):
    monkeypatch.setattr(_c.shutil, "which", lambda _: "/usr/bin/modal")

    class FakePopen:
        def __init__(self, *a, **k):
            self.stdout = ["line-1\n", "line-2\n"]

        def terminate(self):
            pass

    monkeypatch.setattr(_c.subprocess, "Popen", FakePopen)
    res = _c.run_cli_stream("app", "logs", "x", timeout=5)
    assert res["ok"] is True
    assert res["output"] == "line-1\nline-2"
    assert res["truncated"] is False


# --------------------------------------------------------------------------- #
# _modal_common: destructive gating.                                          #
# --------------------------------------------------------------------------- #
def test_guard_destructive_dry_run():
    out = json.loads(_c.guard_destructive("delete volume", "v1", False, True))
    assert out["dry_run"] is True and out["would"] == "delete volume"


def test_guard_destructive_needs_confirm():
    out = json.loads(_c.guard_destructive("delete volume", "v1", False, False))
    assert out["ok"] is False and out["needs_confirm"] is True


def test_guard_destructive_confirmed_returns_none():
    assert _c.guard_destructive("delete volume", "v1", True, False) is None


# --------------------------------------------------------------------------- #
# _modal_common: cost estimation.                                             #
# --------------------------------------------------------------------------- #
def test_estimate_cost_gpu_and_cpu():
    out = _c.estimate_cost(
        3600, gpu="h100", cpu_cores=1.0, memory_gib=8.0, tier="standard"
    )
    assert out["ok"] is True
    assert out["breakdown"]["gpu"]["type"] == "h100"
    # H100 list price 0.001097/sec * 3600 s = 3.9492.
    assert out["breakdown"]["gpu"]["usd"] == pytest.approx(3.9492, rel=1e-6)
    assert out["total_usd"] > 3.9


def test_estimate_cost_gpu_count_from_spec():
    out = _c.estimate_cost(10, gpu="a100:2", cpu_cores=0, memory_gib=0)
    assert out["breakdown"]["gpu"]["count"] == 2
    assert out["breakdown"]["gpu"]["type"] == "a100-80gb"


def test_estimate_cost_alias_and_sandbox_tier():
    out = _c.estimate_cost(100, gpu="a10g", cpu_cores=0.5, tier="sandbox")
    assert out["breakdown"]["gpu"]["type"] == "a10"
    assert (
        out["breakdown"]["cpu"]["usd_per_core_sec"]
        == _c.CPU_USD_PER_CORE_SEC["sandbox"]
    )


def test_estimate_cost_unknown_gpu():
    out = _c.estimate_cost(10, gpu="banana")
    assert out["ok"] is False and "banana" in out["error"]


# --------------------------------------------------------------------------- #
# server.py: CLI tools build the right argv + thread rotation.                #
# --------------------------------------------------------------------------- #
@pytest.fixture
def cli_spy(monkeypatch):
    calls = []

    def fake_run_cli(*args, profile="", environment="", timeout=_c._CLI_TIMEOUT):
        calls.append({"args": args, "profile": profile, "environment": environment})
        return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

    def fake_stream(*args, profile="", environment="", timeout=30):
        calls.append({"args": args, "profile": profile, "stream": True})
        return {"ok": True, "output": "", "truncated": False}

    monkeypatch.setattr(_c, "run_cli", fake_run_cli)
    monkeypatch.setattr(_c, "run_cli_stream", fake_stream)
    return calls


def test_app_list_threads_account(cli_spy):
    server.modal_app_list(account="team", environment="prod")
    assert cli_spy[0]["args"] == ("app", "list")
    assert cli_spy[0]["profile"] == "team"
    assert cli_spy[0]["environment"] == "prod"


def test_volume_ls_with_and_without_volume(cli_spy):
    server.modal_volume_ls()
    server.modal_volume_ls(volume="v", path="/data")
    assert cli_spy[0]["args"] == ("volume", "list")
    assert cli_spy[1]["args"] == ("volume", "ls", "v", "/data")


def test_container_exec_splits_command(cli_spy):
    server.modal_container_exec("c-1", "ls -la /tmp")
    assert cli_spy[0]["args"] == ("container", "exec", "c-1", "ls", "-la", "/tmp")


def test_app_logs_uses_stream(cli_spy):
    server.modal_app_logs("my-app", timeout=7)
    assert cli_spy[0]["stream"] is True
    assert cli_spy[0]["args"] == ("app", "logs", "my-app")


def test_volume_delete_gated(cli_spy):
    out = json.loads(server.modal_volume_delete("v"))
    assert out["needs_confirm"] is True
    assert cli_spy == []  # nothing ran
    out2 = json.loads(server.modal_volume_delete("v", confirm=True))
    assert out2["ok"] is True
    assert cli_spy[0]["args"] == ("volume", "delete", "v", "--yes")


def test_volume_rm_dry_run_does_not_run(cli_spy):
    out = json.loads(server.modal_volume_rm("v", "/f", dry_run=True))
    assert out["dry_run"] is True
    assert cli_spy == []


def test_container_stop_gated(cli_spy):
    assert json.loads(server.modal_container_stop("c"))["needs_confirm"] is True
    server.modal_container_stop("c", confirm=True)
    assert cli_spy[0]["args"] == ("container", "stop", "c")


def test_secret_create_builds_pairs(cli_spy):
    server.modal_secret_create("s", {"A": "1", "B": "2"}, force=True)
    assert cli_spy[0]["args"] == ("secret", "create", "s", "A=1", "B=2", "--force")


def test_secret_create_rejects_empty(cli_spy):
    out = json.loads(server.modal_secret_create("s", {}))
    assert out["ok"] is False and cli_spy == []


def test_whoami(cli_spy):
    server.modal_whoami()
    assert cli_spy[0]["args"] == ("token", "info")


# --------------------------------------------------------------------------- #
# server.py: local tools (no API).                                            #
# --------------------------------------------------------------------------- #
def test_estimate_cost_tool():
    out = json.loads(server.modal_estimate_cost(3600, gpu="t4"))
    assert out["ok"] is True and out["breakdown"]["gpu"]["type"] == "t4"


def test_cloud_bucket_mount_config_ok():
    out = json.loads(
        server.modal_cloud_bucket_mount_config(
            "my-bucket", "/mnt/data", secret="s3creds"
        )
    )
    mount = out["cloud_bucket_mount"]
    assert mount["bucket_name"] == "my-bucket"
    assert mount["mount_path"] == "/mnt/data"
    assert mount["secret"] == "s3creds"


def test_cloud_bucket_mount_config_bad_prefix():
    out = json.loads(
        server.modal_cloud_bucket_mount_config("b", "/m", key_prefix="no-slash")
    )
    assert out["ok"] is False


# --------------------------------------------------------------------------- #
# sandbox.py: SDK tools (mocked modal).                                        #
# --------------------------------------------------------------------------- #
def test_sandbox_create_defaults(fake_sdk):
    modal, sbx = fake_sdk
    out = json.loads(sandbox.modal_sandbox_create(app_name="app", gpu="a100"))
    assert out["ok"] is True and out["sandbox_id"] == sbx.object_id
    modal.App.lookup.assert_called_once()
    assert modal.App.lookup.call_args.kwargs["create_if_missing"] is True
    # No image -> debian_slim default.
    modal.Image.debian_slim.assert_called_once()
    assert modal.Sandbox.create.call_args.kwargs["gpu"] == "a100"


def test_sandbox_create_with_image_volumes_bucket(fake_sdk):
    modal, _sbx = fake_sdk
    sandbox.modal_sandbox_create(
        image="python:3.12",
        volumes={"/data": "vol1"},
        cloud_bucket_mounts=[
            {"mount_path": "/s3", "bucket_name": "b", "secret": "sec"}
        ],
        secrets=["s1"],
    )
    modal.Image.from_registry.assert_called_once_with("python:3.12")
    modal.Volume.from_name.assert_called_once()
    modal.CloudBucketMount.assert_called_once()
    vols = modal.Sandbox.create.call_args.kwargs["volumes"]
    assert set(vols) == {"/data", "/s3"}


def test_sandbox_create_sdk_unavailable(monkeypatch):
    monkeypatch.setattr(_c, "load_sdk", lambda: (None, "no sdk"))
    out = json.loads(sandbox.modal_sandbox_create())
    assert out["ok"] is False and out["error"] == "no sdk"


def test_sandbox_exec(fake_sdk):
    modal, sbx = fake_sdk
    sbx._read = "the-output"
    out = json.loads(sandbox.modal_sandbox_exec("sb-1", "echo hi"))
    assert out["returncode"] == 0 and out["stdout"] == "the-output"
    kind, args, _kw = sbx.calls[0]
    assert kind == "exec" and args == ("sh", "-c", "echo hi")


def test_sandbox_exec_stream_truncates(fake_sdk):
    _modal, sbx = fake_sdk
    sbx._lines = ["a", "b", "c", "d"]
    out = json.loads(sandbox.modal_sandbox_exec_stream("sb-1", "run", max_lines=2))
    assert out["lines"] == ["a", "b"] and out["truncated"] is True


def test_sandbox_write_and_read_file(fake_sdk):
    _modal, sbx = fake_sdk
    sbx._read = "file-body"
    wrote = json.loads(sandbox.modal_sandbox_write_file("sb-1", "/f.txt", "hello"))
    assert wrote["ok"] is True and wrote["bytes"] == 5
    assert sbx.opened[0][0] == "/f.txt" and sbx.opened[0][1] == "w"
    read = json.loads(sandbox.modal_sandbox_read_file("sb-1", "/f.txt"))
    assert read["content"] == "file-body"


def test_sandbox_read_file_binary(fake_sdk):
    import base64

    _modal, sbx = fake_sdk
    sbx._read = b"\x00\x01\x02"
    out = json.loads(sandbox.modal_sandbox_read_file("sb-1", "/b", binary=True))
    assert base64.b64decode(out["base64"]) == b"\x00\x01\x02"


def test_sandbox_upload_missing_local(fake_sdk):
    out = json.loads(sandbox.modal_sandbox_upload("sb-1", "/no/such/file", "/r"))
    assert out["ok"] is False and "local file not found" in out["error"]


def test_sandbox_upload_download_roundtrip(fake_sdk, tmp_path):
    _modal, sbx = fake_sdk
    local = tmp_path / "up.bin"
    local.write_bytes(b"payload")
    up = json.loads(sandbox.modal_sandbox_upload("sb-1", str(local), "/remote"))
    assert up["ok"] is True and up["bytes"] == 7
    assert sbx.opened[-1][1] == "wb" and sbx.opened[-1][2].written == b"payload"

    sbx._read = b"down-bytes"
    dest = tmp_path / "down.bin"
    down = json.loads(sandbox.modal_sandbox_download("sb-1", "/remote", str(dest)))
    assert down["ok"] is True and dest.read_bytes() == b"down-bytes"


def test_sandbox_ls_mkdir_rm(fake_sdk):
    _modal, sbx = fake_sdk
    assert json.loads(sandbox.modal_sandbox_ls("sb-1", "/"))["entries"] == sbx._ls
    sandbox.modal_sandbox_mkdir("sb-1", "/d")
    sandbox.modal_sandbox_rm("sb-1", "/d", recursive=True)
    assert ("mkdir", "/d", True) in sbx.calls
    assert ("rm", "/d", True) in sbx.calls


def test_sandbox_stat(fake_sdk):
    _modal, sbx = fake_sdk
    sbx._read = "  Size: 42"
    out = json.loads(sandbox.modal_sandbox_stat("sb-1", "/f"))
    assert out["ok"] is True and "Size: 42" in out["stat"]


def test_sandbox_stat_nonzero(fake_sdk):
    _modal, sbx = fake_sdk
    sbx._rc = 1
    out = json.loads(sandbox.modal_sandbox_stat("sb-1", "/nope"))
    assert out["ok"] is False


def test_sandbox_list_by_app(fake_sdk):
    modal, sbx = fake_sdk
    out = json.loads(sandbox.modal_sandbox_list(app_name="app"))
    assert out["sandboxes"] == [sbx.object_id] and out["count"] == 1
    modal.App.lookup.assert_called_once()


def test_sandbox_from_id_reports_liveness(fake_sdk):
    _modal, sbx = fake_sdk
    sbx._poll = None
    sbx._tags = {"role": "prep"}
    out = json.loads(sandbox.modal_sandbox_from_id("sb-1"))
    assert out["running"] is True and out["tags"] == {"role": "prep"}


def test_sandbox_poll_exited(fake_sdk):
    _modal, sbx = fake_sdk
    sbx._poll = 0
    out = json.loads(sandbox.modal_sandbox_poll("sb-1"))
    assert out["running"] is False and out["returncode"] == 0


def test_sandbox_wait(fake_sdk):
    _modal, sbx = fake_sdk
    sbx._poll = 0
    out = json.loads(sandbox.modal_sandbox_wait("sb-1"))
    assert out["returncode"] == 0
    assert any(call[0] == "wait" for call in sbx.calls)


def test_sandbox_terminate_gated(fake_sdk):
    _modal, sbx = fake_sdk
    blocked = json.loads(sandbox.modal_sandbox_terminate("sb-1"))
    assert blocked["needs_confirm"] is True
    assert not any(call[0] == "terminate" for call in sbx.calls)
    ok = json.loads(sandbox.modal_sandbox_terminate("sb-1", confirm=True))
    assert ok["terminated"] is True
    assert any(call[0] == "terminate" for call in sbx.calls)


def test_sandbox_tags_get_and_set(fake_sdk):
    _modal, sbx = fake_sdk
    got = json.loads(sandbox.modal_sandbox_tags("sb-1"))
    assert got["updated"] is False
    setres = json.loads(sandbox.modal_sandbox_tags("sb-1", tags={"k": "v"}))
    assert setres["updated"] is True and setres["tags"] == {"k": "v"}


def test_sandbox_snapshot(fake_sdk):
    _modal, _sbx = fake_sdk
    out = json.loads(sandbox.modal_sandbox_snapshot("sb-1"))
    assert out["ok"] is True and out["image_id"] == "im-snap-1"


def test_function_call(fake_sdk):
    modal, _sbx = fake_sdk
    out = json.loads(
        sandbox.modal_function_call("app", "fn", args=[1, 2], kwargs={"k": "v"})
    )
    assert out["result"] == "RESULT"
    fn = modal.Function.from_name.return_value
    fn.remote.assert_called_once_with(1, 2, k="v")


def test_function_spawn_and_get(fake_sdk):
    modal, _sbx = fake_sdk
    spawned = json.loads(sandbox.modal_function_spawn("app", "fn"))
    assert spawned["function_call_id"] == "fc-1"
    got = json.loads(sandbox.modal_functioncall_get("fc-1"))
    assert got["result"] == "GOT"
    modal.FunctionCall.from_id.assert_called_once_with("fc-1", client=None)


def test_function_call_nonserializable_result(monkeypatch):
    modal, _sbx = make_modal(fn_result=object())
    monkeypatch.setattr(_c, "load_sdk", lambda: (modal, None))
    out = json.loads(sandbox.modal_function_call("app", "fn"))
    assert "result_repr" in out


# --------------------------------------------------------------------------- #
# SDK rotation: a per-call account builds a fresh Client threaded via client=. #
# --------------------------------------------------------------------------- #
def test_account_builds_per_call_client(monkeypatch):
    modal, _sbx = make_modal()
    monkeypatch.setattr(_c, "load_sdk", lambda: (modal, None))
    monkeypatch.setattr(
        _c,
        "resolve_profile",
        lambda p, environ=None, toml_path=None: ("tid", "ts", "prod"),
    )
    sandbox.modal_sandbox_from_id("sb-9", account="team")
    modal.Client.from_credentials.assert_called_once_with("tid", "ts")
    modal.Sandbox.from_id.assert_called_once_with("sb-9", client="CLIENT")


def test_no_account_uses_ambient_no_client(fake_sdk):
    modal, _sbx = fake_sdk
    sandbox.modal_sandbox_from_id("sb-1")
    modal.Client.from_credentials.assert_not_called()
    modal.Sandbox.from_id.assert_called_once_with("sb-1", client=None)


# --------------------------------------------------------------------------- #
# Registration / surface.                                                      #
# --------------------------------------------------------------------------- #
def test_all_tools_registered():
    import asyncio

    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert len(names) == 41
    # The 6 original CLI tools survive.
    for original in (
        "modal_app_list",
        "modal_app_stop",
        "modal_run",
        "modal_deploy",
        "modal_volume_ls",
        "modal_secret_list",
    ):
        assert original in names
    # A representative slice of the new surface.
    for added in (
        "modal_sandbox_create",
        "modal_sandbox_exec",
        "modal_sandbox_snapshot",
        "modal_function_call",
        "modal_volume_delete",
        "modal_estimate_cost",
        "modal_cloud_bucket_mount_config",
    ):
        assert added in names


def test_enumeration_does_not_import_modal():
    # tools/list must stay credential-free: importing server + listing tools
    # must NOT import the modal SDK (it is gated behind the first real call).
    assert "modal" not in sys.modules
