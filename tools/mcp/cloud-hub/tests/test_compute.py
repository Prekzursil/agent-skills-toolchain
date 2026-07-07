#!/usr/bin/env python3
"""Fully-mocked tests for the unified compute layer (no live calls, no network).

Every provider seam is stubbed:

* ``providers._http.request_json`` -- the single HTTP seam for RunPod/OVH (so
  the real URL/body/signing construction IS exercised, only the socket is fake).
* ``transfer.subprocess.run`` / ``transfer.shutil.which`` -- ssh/scp.
* ``providers.lightning._sdk`` -- a tiny in-memory fake ``lightning_sdk``.

Covers handle round-trips, per-verb dispatch for all three providers, the
confirm/dry_run gates, the scp-vs-rclone selector, and credential resolution
(active account, a named account, and a temp accounts.json).
"""

from __future__ import annotations

import json
import os
import sys
import types

import pytest

_TESTS = os.path.dirname(os.path.abspath(__file__))
_HUB = os.path.dirname(_TESTS)
_COMPUTE = os.path.join(_HUB, "compute-mcp")
_SHARED = os.path.join(os.path.dirname(_HUB), "_shared")
for _p in (_COMPUTE, _HUB, _SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import accounts_bridge  # noqa: E402
import dispatch  # noqa: E402
import envelope  # noqa: E402
import handles  # noqa: E402
import transfer  # noqa: E402
from providers import _http, lightning  # noqa: E402


# --------------------------------------------------------------------------- #
# Fakes                                                                        #
# --------------------------------------------------------------------------- #
class FakeHTTP:
    """A canned ``request_json`` router that records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.routes: dict[str, list[tuple]] = {}

    def add(self, method: str, url_sub: str, status: int, body) -> "FakeHTTP":
        self.routes.setdefault(method.upper(), []).append((url_sub, status, body))
        return self

    def __call__(self, method, url, headers=None, body=None, timeout=30.0):
        self.calls.append((method.upper(), url, headers or {}, body))
        if "/auth/time" in url:  # OVH time-sync always answers
            return 200, 1_600_000_000
        for url_sub, status, resp in self.routes.get(method.upper(), []):
            if url_sub in url:
                return status, resp
        return 404, {"error": f"no route for {method} {url}"}

    def last(self, method: str):
        for call in reversed(self.calls):
            if call[0] == method.upper():
                return call
        raise AssertionError(f"no {method} call recorded")


class FakeRun:
    """A stand-in for ``subprocess.run`` that records the argv it was given."""

    def __init__(self, returncode=0, stdout="", stderr="") -> None:
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr
        self.argv: list[str] | None = None

    def __call__(self, argv, **_kw):
        self.argv = argv
        return types.SimpleNamespace(
            returncode=self.returncode, stdout=self.stdout, stderr=self.stderr
        )


class _FakeMachine:
    CPU = "CPU"
    T4 = "T4"
    A10G = "A10G"


class _FakeStudio:
    log: dict = {}

    def __init__(self, name, teamspace=None) -> None:
        self.name, self.teamspace, self.status = name, teamspace, "running"
        _FakeStudio.log = {"name": name, "teamspace": teamspace}

    def start(self, machine=None):
        _FakeStudio.log["machine"] = machine

    def stop(self):
        _FakeStudio.log["stopped"] = True

    def delete(self):
        _FakeStudio.log["deleted"] = True

    def run(self, command):
        _FakeStudio.log["command"] = command
        return f"ran:{command}"

    def upload_file(self, local, remote=None, progress_bar=True):
        _FakeStudio.log["upload"] = (local, remote, progress_bar)


class _FakeTeamspace:
    def __init__(self, name=None) -> None:
        self.name = name

    @property
    def studios(self):
        return [types.SimpleNamespace(name="alpha"), types.SimpleNamespace(name="beta")]


class FakeSDK:
    Machine = _FakeMachine
    Studio = _FakeStudio
    Teamspace = _FakeTeamspace


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    """Reset process-global caches so tests never leak state into each other."""
    _http._ovh_delta.clear()
    _http._oauth_cache.clear()
    dispatch._ACCOUNTS = None
    yield


@pytest.fixture
def env(monkeypatch):
    """Pin dispatch's credential resolution to a fixed env per provider."""
    creds = {
        "runpod": {"RUNPOD_API_KEY": "rp-key"},
        "ovh": {
            "OVH_ENDPOINT": "ovh-ca",
            "OVH_APPLICATION_KEY": "AK",
            "OVH_APPLICATION_SECRET": "AS",
            "OVH_CONSUMER_KEY": "CK",
        },
        "lightning": {"LIGHTNING_USER_ID": "u", "LIGHTNING_API_KEY": "k"},
    }
    monkeypatch.setattr(
        dispatch, "_resolve_env", lambda p, account="": creds.get(p, {})
    )
    return creds


@pytest.fixture
def http(monkeypatch):
    fake = FakeHTTP()
    monkeypatch.setattr(_http, "request_json", fake)
    return fake


@pytest.fixture
def sdk(monkeypatch):
    monkeypatch.setattr(lightning, "_sdk", lambda: (FakeSDK, ""))
    return FakeSDK


# --------------------------------------------------------------------------- #
# Handles                                                                      #
# --------------------------------------------------------------------------- #
def test_handle_roundtrip_runpod():
    h = handles.parse("compute://runpod/pod/pod123")
    assert (h.provider, h.kind, h.ident) == ("runpod", "pod", "pod123")
    assert handles.parse(h.format()) == h


def test_handle_slash_ident_ovh():
    h = handles.parse("compute://ovh/instance/svc-1/inst-9")
    assert h.parts == ["svc-1", "inst-9"]
    assert h.format() == "compute://ovh/instance/svc-1/inst-9"


def test_handle_lightning_teamspace():
    h = handles.parse("compute://lightning/studio/team-a/studio-x")
    assert h.parts == ["team-a", "studio-x"]


@pytest.mark.parametrize(
    "bad",
    [
        "runpod/pod/x",  # no scheme
        "compute://runpod/pod",  # missing ident
        "compute://bogus/pod/x",  # unknown provider
        "compute://runpod//",  # empty ident
    ],
)
def test_handle_invalid(bad):
    with pytest.raises(handles.HandleError):
        handles.parse(bad)


def test_make_defaults_kind():
    assert handles.make("runpod", "p1").kind == "pod"
    assert handles.make("ovh", "s/i").kind == "instance"
    assert handles.make("lightning", "s").kind == "studio"


def test_dispatch_bad_handle_is_envelope():
    out = dispatch.status("not-a-handle")
    assert out["ok"] is False and "handle must" in out["error"]


# --------------------------------------------------------------------------- #
# Envelope gates                                                               #
# --------------------------------------------------------------------------- #
def test_needs_confirm_and_dry_run_shape():
    nc = envelope.needs_confirm("runpod", "terminate", {"method": "DELETE"})
    assert nc["ok"] is False and nc["would"] == {"method": "DELETE"}
    dr = envelope.dry_run("ovh", "provision", {"path": "/x"})
    assert dr["ok"] is True and dr["dry_run"] is True and dr["action"] == "provision"


# --------------------------------------------------------------------------- #
# RunPod                                                                       #
# --------------------------------------------------------------------------- #
def test_runpod_provision_body_and_handle(env, http):
    http.add("POST", "/pods", 201, {"id": "pod123", "desiredStatus": "RUNNING"})
    out = dispatch.provision(
        "runpod",
        gpu="NVIDIA A100",
        image="runpod/base:latest",
        region="US-CA",
        gpu_count=2,
        disk_gb=40,
        ports="8888/http,22/tcp",
        template="tmpl1",
    )
    assert out["ok"] and out["handle"] == "compute://runpod/pod/pod123"
    assert out["state"] == "RUNNING"
    body = http.last("POST")[3]
    assert body["imageName"] == "runpod/base:latest"
    assert body["gpuTypeIds"] == ["NVIDIA A100"]
    assert body["gpuCount"] == 2 and body["containerDiskInGb"] == 40
    assert body["ports"] == ["8888/http", "22/tcp"]
    assert body["dataCenterIds"] == ["US-CA"] and body["templateId"] == "tmpl1"


def test_runpod_provision_dry_run_makes_no_call(env, http):
    out = dispatch.provision("runpod", image="img", dry_run=True)
    assert out["dry_run"] is True and out["request"]["path"] == "/pods"
    assert out["request"]["body"]["imageName"] == "img"
    assert http.calls == []  # nothing was sent


def test_runpod_status(env, http):
    http.add("GET", "/pods/pod123", 200, {"id": "pod123", "desiredStatus": "RUNNING"})
    out = dispatch.status("compute://runpod/pod/pod123")
    assert out["ok"] and out["state"] == "RUNNING" and out["id"] == "pod123"


def test_runpod_ls(env, http):
    http.add("GET", "/pods", 200, [{"id": "a"}, {"id": "b"}])
    out = dispatch.ls("runpod")
    assert out["ok"] and out["count"] == 2


def test_runpod_teardown_stop(env, http):
    http.add("POST", "/pods/pod1/stop", 200, {"desiredStatus": "EXITED"})
    out = dispatch.teardown("compute://runpod/pod/pod1")
    assert out["ok"] and out["state"] == "EXITED"
    assert http.last("POST")[1].endswith("/pods/pod1/stop")


def test_runpod_terminate_needs_confirm(env, http):
    out = dispatch.teardown("compute://runpod/pod/pod1", terminate=True)
    assert out["ok"] is False and out["would"]["method"] == "DELETE"
    assert http.calls == []  # refused before any network call


def test_runpod_terminate_confirmed(env, http):
    http.add("DELETE", "/pods/pod1", 204, {})
    out = dispatch.teardown("compute://runpod/pod/pod1", terminate=True, confirm=True)
    assert out["ok"] and out["state"] == "terminated"


def test_runpod_terminate_dry_run(env, http):
    out = dispatch.teardown("compute://runpod/pod/pod1", terminate=True, dry_run=True)
    assert out["dry_run"] is True and http.calls == []


def test_runpod_cost(env, http):
    http.add(
        "POST",
        "graphql",
        200,
        {"data": {"myself": {"clientBalance": 12.5, "currentSpendPerHr": 0.4}}},
    )
    out = dispatch.cost("runpod")
    assert out["ok"] and out["balance"] == 12.5 and out["currency"] == "USD"
    assert out["spend_per_hr"] == 0.4


def test_runpod_catalog(env, http):
    http.add("GET", "/gpuTypes", 200, [{"id": "A100"}, {"id": "H100"}])
    out = dispatch.catalog("runpod")
    assert out["ok"] and out["count"] == 2 and out["kind"] == "gpuType"


def test_runpod_exec_over_ssh(env, http, monkeypatch):
    http.add(
        "GET",
        "/pods/pod1",
        200,
        {"publicIp": "1.2.3.4", "portMappings": {"22": "40022"}},
    )
    run = FakeRun(returncode=0, stdout="hello\n", stderr="")
    monkeypatch.setattr(transfer.subprocess, "run", run)
    monkeypatch.setattr(transfer.shutil, "which", lambda _n: "/usr/bin/ssh")
    out = dispatch.exec_("compute://runpod/pod/pod1", "echo hello")
    assert out["ok"] and out["stdout"] == "hello\n" and out["exit_code"] == 0
    assert "-p" in run.argv and "40022" in run.argv
    assert "root@1.2.3.4" in run.argv and run.argv[-1] == "echo hello"


def test_runpod_exec_no_ssh_endpoint(env, http):
    http.add("GET", "/pods/pod1", 200, {"publicIp": "", "portMappings": {}})
    out = dispatch.exec_("compute://runpod/pod/pod1", "ls")
    assert out["ok"] is False and "no public SSH" in out["error"]


# --------------------------------------------------------------------------- #
# OVH                                                                          #
# --------------------------------------------------------------------------- #
def test_ovh_provision_body_and_signature(env, http):
    http.add(
        "POST",
        "/cloud/project/proj1/instance",
        201,
        {"id": "inst9", "status": "BUILDING"},
    )
    out = dispatch.provision(
        "ovh", gpu="l4-90", image="img-ubuntu", region="BHS5", project="proj1"
    )
    assert out["ok"] and out["handle"] == "compute://ovh/instance/proj1/inst9"
    method, url, headers, body = http.last("POST")
    assert url.startswith("https://ca.api.ovh.com/1.0/cloud/project/proj1/instance")
    assert '"monthlyBilling":false' in body and '"flavorId":"l4-90"' in body
    assert headers["X-Ovh-Signature"].startswith("$1$")
    assert headers["X-Ovh-Application"] == "AK" and headers["X-Ovh-Consumer"] == "CK"


def test_ovh_service_autodiscover(env, http):
    http.add("GET", "/cloud/project", 200, ["only-project"])
    http.add("POST", "/cloud/project/only-project/instance", 201, {"id": "i1"})
    out = dispatch.provision("ovh", image="img", region="GRA")
    assert out["ok"] and out["handle"] == "compute://ovh/instance/only-project/i1"


def test_ovh_service_ambiguous_is_error(env, http):
    http.add("GET", "/cloud/project", 200, ["p1", "p2"])
    out = dispatch.provision("ovh", image="img")
    assert out["ok"] is False and "multiple OVH projects" in out["error"]
    assert not any(c[0] == "POST" for c in http.calls)


def test_ovh_teardown_stop_is_honest_note(env, http):
    out = dispatch.teardown("compute://ovh/instance/p1/i1")
    assert out["ok"] and out["stopped"] is False
    assert "no stop-without-billing" in out["note"]
    assert http.calls == []


def test_ovh_terminate_confirmed(env, http):
    http.add("DELETE", "/cloud/project/p1/instance/i1", 204, {})
    out = dispatch.teardown(
        "compute://ovh/instance/p1/i1", terminate=True, confirm=True
    )
    assert out["ok"] and out["state"] == "terminated"


def test_ovh_status(env, http):
    http.add("GET", "/cloud/project/p1/instance/i1", 200, {"status": "ACTIVE"})
    out = dispatch.status("compute://ovh/instance/p1/i1")
    assert out["ok"] and out["state"] == "ACTIVE"


def test_ovh_ls(env, http):
    http.add("GET", "/cloud/project/p1/instance", 200, [{"id": "i1"}])
    out = dispatch.ls("ovh", project="p1")
    assert out["ok"] and out["count"] == 1 and out["kind"] == "instance"


def test_ovh_catalog(env, http):
    http.add("GET", "/cloud/project/p1/flavor", 200, [{"id": "l4-90"}])
    http.add("GET", "/cloud/project/p1/region", 200, ["GRA", "BHS"])
    out = dispatch.catalog("ovh", region="GRA", project="p1")
    assert out["ok"] and out["items"] == [{"id": "l4-90"}]
    assert out["regions"] == ["GRA", "BHS"]


def test_ovh_cost(env, http):
    http.add("GET", "/me/credit/balance", 200, ["voucher"])
    http.add("GET", "/cloud/project/p1/usage/current", 200, {"total": 3.2})
    out = dispatch.cost("ovh", project="p1")
    assert out["ok"] and out["currency"] == "EUR"
    assert out["usage_current"] == {"total": 3.2}


def test_ovh_oauth2_uses_bearer(monkeypatch, http):
    monkeypatch.setattr(
        dispatch,
        "_resolve_env",
        lambda p, account="": {
            "OVH_ENDPOINT": "ovh-eu",
            "OVH_CLIENT_ID": "cid",
            "OVH_CLIENT_SECRET": "csecret",
        },
    )
    http.add("POST", "/oauth2/token", 200, {"access_token": "tok", "expires_in": 3600})
    http.add("GET", "/cloud/project/p1/instance/i1", 200, {"status": "ACTIVE"})
    out = dispatch.status("compute://ovh/instance/p1/i1")
    assert out["ok"]
    _m, _u, headers, _b = http.last("GET")
    assert headers["Authorization"] == "Bearer tok"
    assert "X-Ovh-Signature" not in headers


def test_ovh_ssh_target_user_from_image(env, http, monkeypatch):
    http.add(
        "GET",
        "/cloud/project/p1/instance/i1",
        200,
        {
            "ipAddresses": [
                {"ip": "10.0.0.1", "type": "private", "version": 4},
                {"ip": "51.222.1.9", "type": "public", "version": 4},
            ],
            "image": {"user": "debian"},
        },
    )
    run = FakeRun(returncode=0, stdout="ok", stderr="")
    monkeypatch.setattr(transfer.subprocess, "run", run)
    monkeypatch.setattr(transfer.shutil, "which", lambda _n: "/usr/bin/ssh")
    out = dispatch.exec_("compute://ovh/instance/p1/i1", "whoami")
    assert out["ok"] and "debian@51.222.1.9" in run.argv


# --------------------------------------------------------------------------- #
# Lightning                                                                    #
# --------------------------------------------------------------------------- #
def test_lightning_provision(env, sdk):
    out = dispatch.provision("lightning", name="s1", gpu="A10G", teamspace="ts")
    assert out["ok"] and out["handle"] == "compute://lightning/studio/ts/s1"
    assert _FakeStudio.log["machine"] == "A10G"


def test_lightning_provision_dry_run(env, sdk):
    out = dispatch.provision("lightning", name="s1", dry_run=True)
    assert out["dry_run"] is True and out["request"]["studio"] == "s1"


def test_lightning_provision_requires_name(env, sdk):
    out = dispatch.provision("lightning", gpu="A10G")
    assert out["ok"] is False and "needs name" in out["error"]


def test_lightning_exec(env, sdk):
    out = dispatch.exec_("compute://lightning/studio/ts/s1", "nvidia-smi")
    assert out["ok"] and out["stdout"] == "ran:nvidia-smi" and out["exit_code"] == 0
    assert _FakeStudio.log["command"] == "nvidia-smi"


def test_lightning_push_uses_upload_file(env, sdk):
    out = dispatch.push("compute://lightning/studio/ts/s1", "/tmp/a.txt", "/data/a.txt")
    assert out["ok"] and out["mechanism"] == "upload_file"
    assert _FakeStudio.log["upload"] == ("/tmp/a.txt", "/data/a.txt", False)


def test_lightning_pull_is_honest_note(env, sdk):
    out = dispatch.pull("compute://lightning/studio/ts/s1", "/data/a.txt", "/tmp/a.txt")
    assert (
        out["ok"] and out["downloaded"] is False and "no file download" in out["note"]
    )


def test_lightning_status(env, sdk):
    out = dispatch.status("compute://lightning/studio/ts/s1")
    assert out["ok"] and out["state"] == "running"


def test_lightning_ls_needs_teamspace(env, sdk):
    out = dispatch.ls("lightning")
    assert out["ok"] and out["items"] == [] and "teamspace" in out["note"]


def test_lightning_ls_with_teamspace(env, sdk):
    out = dispatch.ls("lightning", teamspace="ts")
    assert out["ok"] and out["items"] == ["alpha", "beta"]


def test_lightning_catalog(env, sdk):
    out = dispatch.catalog("lightning")
    assert out["ok"] and out["items"] == ["A10G", "CPU", "T4"]


def test_lightning_cost_is_dashboard_note(env, sdk):
    out = dispatch.cost("lightning")
    assert out["ok"] and out["balance"] is None and "dashboard" in out["note"]


def test_lightning_teardown_stop(env, sdk):
    out = dispatch.teardown("compute://lightning/studio/ts/s1")
    assert out["ok"] and out["state"] == "stopped"
    assert _FakeStudio.log.get("stopped") is True


def test_lightning_terminate_needs_confirm(env, sdk):
    out = dispatch.teardown("compute://lightning/studio/ts/s1", terminate=True)
    assert out["ok"] is False and "confirm" in out["error"]
    assert _FakeStudio.log.get("deleted") is None


def test_lightning_terminate_confirmed(env, sdk):
    out = dispatch.teardown(
        "compute://lightning/studio/ts/s1", terminate=True, confirm=True
    )
    assert out["ok"] and out["state"] == "terminated"
    assert _FakeStudio.log.get("deleted") is True


def test_lightning_sdk_absent(env, monkeypatch):
    monkeypatch.setattr(lightning, "_sdk", lambda: (None, "sdk missing"))
    out = dispatch.provision("lightning", name="s1")
    assert out["ok"] is False and out["error"] == "sdk missing"


# --------------------------------------------------------------------------- #
# Transfer selection + provider unknowns                                       #
# --------------------------------------------------------------------------- #
def test_is_rclone_remote_vs_windows_drive():
    assert transfer.is_rclone_remote("s3:bucket/x") is True
    assert transfer.is_rclone_remote("gdrive:") is True
    assert transfer.is_rclone_remote("C:\\Users\\x") is False
    assert transfer.is_rclone_remote("/home/x") is False


def test_select_via_rules():
    assert transfer.select_via("/tmp/a", "s3:bucket/x") == "rclone"
    assert transfer.select_via("/tmp/a", "/remote/b") == "scp"
    assert transfer.select_via("/tmp/a", "/remote/b", via="rclone") == "rclone"
    assert transfer.select_via("/tmp/a", "s3:bucket/x", via="scp") == "scp"


def test_pull_routes_to_rclone_daemon(env, http):
    http.add("POST", "5572/operations/copyfile", 200, {})
    out = dispatch.pull("compute://runpod/pod/pod1", "s3:bkt/f.bin", "/tmp/f.bin")
    assert out["ok"] and out["mechanism"] == "rclone"
    assert out["op"] == "operations/copyfile"
    assert "operations/copyfile" in http.last("POST")[1]


def test_push_routes_to_scp(env, http, monkeypatch):
    http.add(
        "GET", "/pods/pod1", 200, {"publicIp": "5.6.7.8", "portMappings": {"22": "22"}}
    )
    run = FakeRun(returncode=0)
    monkeypatch.setattr(transfer.subprocess, "run", run)
    monkeypatch.setattr(transfer.shutil, "which", lambda _n: "/usr/bin/scp")
    out = dispatch.push("compute://runpod/pod/pod1", "/tmp/a", "/root/a")
    assert out["ok"] and out["mechanism"] == "scp" and out["direction"] == "push"
    assert run.argv[0] == "scp" and "root@5.6.7.8:/root/a" in run.argv


def test_provision_unknown_provider():
    out = dispatch.provision("azure")
    assert out["ok"] is False and "unknown provider" in out["error"]


def test_ls_cost_catalog_unknown_provider():
    for fn in (dispatch.ls, dispatch.cost, dispatch.catalog):
        out = fn("nope")
        assert out["ok"] is False and out["provider"] == "compute"


# --------------------------------------------------------------------------- #
# Credential resolution (accounts_bridge)                                      #
# --------------------------------------------------------------------------- #
def _bridge(tmp_path, data: dict | None, environ: dict):
    path = os.path.join(str(tmp_path), "accounts.json")
    if data is not None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    return accounts_bridge.build(accounts_path=path, environ=environ)


def test_creds_seeded_active(tmp_path):
    bridge = _bridge(tmp_path, None, {"RUNPOD_API_KEY": "seed-key"})
    assert bridge.resolve_env("runpod") == {"RUNPOD_API_KEY": "seed-key"}


def test_creds_named_account_from_store(tmp_path):
    data = {
        "runpod": {
            "active": "personal",
            "accounts": [
                {"name": "personal", "env": {"RUNPOD_API_KEY": "${RP_PERSONAL}"}},
                {"name": "work", "env": {"RUNPOD_API_KEY": "${RP_WORK}"}},
            ],
        }
    }
    environ = {"RP_PERSONAL": "p-key", "RP_WORK": "w-key"}
    bridge = _bridge(tmp_path, data, environ)
    assert bridge.resolve_env("runpod")["RUNPOD_API_KEY"] == "p-key"
    assert bridge.resolve_env("runpod", account="work")["RUNPOD_API_KEY"] == "w-key"


def test_creds_ovh_endpoint_in_bundle(tmp_path):
    data = {
        "ovh": {
            "active": "ca",
            "accounts": [
                {
                    "name": "ca",
                    "env": {
                        "OVH_ENDPOINT": "ovh-ca",
                        "OVH_APPLICATION_KEY": "${AK}",
                        "OVH_APPLICATION_SECRET": "${AS}",
                        "OVH_CONSUMER_KEY": "${CK}",
                    },
                }
            ],
        }
    }
    bridge = _bridge(tmp_path, data, {"AK": "a", "AS": "s", "CK": "c"})
    resolved = bridge.resolve_env("ovh")
    assert (
        resolved["OVH_ENDPOINT"] == "ovh-ca" and resolved["OVH_APPLICATION_KEY"] == "a"
    )


def test_creds_unknown_provider_is_empty(tmp_path):
    bridge = _bridge(tmp_path, None, {})
    assert bridge.resolve_env("gcloud") == {}
    assert bridge.resolve_env("runpod") == {}  # no seed env present
