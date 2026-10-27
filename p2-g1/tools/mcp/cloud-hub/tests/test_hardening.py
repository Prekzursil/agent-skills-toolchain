#!/usr/bin/env python3
"""Tests for the D4/D6 owned-hub hardening layer (_shared/hardening.py).

Unit-tests the lexical classifier, the confirm-gate membership, the pure
enrichment, and the shadow/enforce ConfirmGate; then integration-tests the REAL
HubServer so the enriched tools/list and the gate's block/forward behaviour are
proven end-to-end against a fake backend (no cloud creds, nothing real spawned
until a call is actually forwarded).
"""

from __future__ import annotations

import json
import os
import queue
import sys
import time

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

import hardening  # noqa: E402
import hub  # noqa: E402
from backends import BackendSpec  # noqa: E402
from registry import build_plan  # noqa: E402

PY = sys.executable
FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_backend.py")


# --------------------------------------------------------------------------- #
# classify (lexical, token-boundary)                                           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name,expected",
    [
        ("modal_sandbox_terminate", "DESTRUCTIVE"),
        ("delete-pod", "DESTRUCTIVE"),
        ("dbx_cluster_permanent_delete", "DESTRUCTIVE"),
        ("operations_purge", "DESTRUCTIVE"),
        ("dbx_cluster_restart", "DISRUPTIVE"),
        ("bm_cancel", "DISRUPTIVE"),
        ("ovh_vps_stop", "DISRUPTIVE"),
        # the substring trap: "skills"/"skill" must NOT read as "kill"
        ("bm_list_skills", "READONLY"),
        ("bm_set_skill_status", "READONLY"),
        ("modal_secret_list", "READONLY"),
        ("dataset_download", "READONLY"),
        ("dbx_cluster_create", "WRITE"),
        ("modal_secret_create", "WRITE"),
    ],
)
def test_classify_token_boundary(name, expected):
    assert hardening.classify(name) == expected


def test_classify_unknown_is_conservative():
    # exec/command tools we deliberately do not label (they are ambiguous)
    assert hardening.classify("modal_sandbox_exec") == "UNKNOWN"
    assert hardening.classify("") == "UNKNOWN"
    assert hardening.classify(None) == "UNKNOWN"  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# confirm_required (D4 membership)                                              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name",
    [
        "modal_sandbox_terminate",
        "modal_volume_delete",
        "delete-pod",
        "delete-network-volume",
        "purge-endpoint-queue",
        "dbx_cluster_permanent_delete",
        "dbx_job_delete",
        "dataset_delete",
        "model_delete",
        "compute_teardown",
        "operations_delete",
        "operations_purge",
        "config_delete",
        "ovh_domain_dns_delete",
        "ovh_vps_stop",  # explicit extra (halts a paid resource)
        "ovh_vps_reboot",  # explicit extra
        "stop-pod",  # explicit extra
    ],
)
def test_confirm_required_true_for_irreversible(name):
    assert hardening.confirm_required(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "modal_sandbox_exec",
        "dbx_sql_exec",
        "modal_secret_list",
        "dataset_download",
        "core_stats_delete",  # excluded: resets a counter, not a resource
        "core_stats_reset",
        "dbx_cluster_restart",  # reversible restart, not gated
        "bm_cancel",  # reversible cancel
        "az_account_list",
    ],
)
def test_confirm_required_false_for_safe(name):
    assert hardening.confirm_required(name) is False


# --------------------------------------------------------------------------- #
# annotations_for                                                              #
# --------------------------------------------------------------------------- #
def test_annotations_destructive():
    a = hardening.annotations_for("delete-pod")
    assert a["destructiveHint"] is True and a["readOnlyHint"] is False


def test_annotations_readonly():
    a = hardening.annotations_for("modal_secret_list")
    assert a["readOnlyHint"] is True and a["destructiveHint"] is False
    assert a["idempotentHint"] is True


def test_annotations_write():
    a = hardening.annotations_for("modal_secret_create")
    assert a["readOnlyHint"] is False and a["destructiveHint"] is False


def test_annotations_unknown_empty():
    assert hardening.annotations_for("modal_sandbox_exec") == {}


# --------------------------------------------------------------------------- #
# enrich_tools (pure, additive)                                                #
# --------------------------------------------------------------------------- #
def _tool(name, **kw):
    t = {
        "name": name,
        "description": f"desc {name}",
        "inputSchema": {"type": "object", "properties": {}},
    }
    t.update(kw)
    return t


def test_enrich_adds_annotations_and_is_pure():
    src = [
        _tool(
            "thing_delete",
            inputSchema={
                "type": "object",
                "properties": {"target": {"type": "string"}},
                "required": ["target"],
            },
        )
    ]
    out = hardening.enrich_tools(src)
    assert out[0]["annotations"]["destructiveHint"] is True
    # purity: the input tool was not mutated
    assert "annotations" not in src[0]
    assert "Examples:" not in src[0]["description"]


def test_enrich_additive_never_clobbers_backend_hint():
    src = [
        _tool("thing_delete", annotations={"destructiveHint": False, "title": "Custom"})
    ]
    out = hardening.enrich_tools(src)
    # backend explicitly said NOT destructive -> preserved (additive setdefault)
    assert out[0]["annotations"]["destructiveHint"] is False
    assert out[0]["annotations"]["title"] == "Custom"
    # readOnlyHint was absent -> filled in
    assert out[0]["annotations"]["readOnlyHint"] is False


def test_enrich_preserves_existing_output_schema():
    src = [_tool("md_account_list", outputSchema={"type": "string"})]
    out = hardening.enrich_tools(src)
    assert out[0]["outputSchema"] == {"type": "string"}  # not clobbered


def test_enrich_account_tool_tightened():
    src = [
        _tool(
            "md_account_add",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string"}, "env": {"type": "object"}},
                "required": ["name", "env"],
            },
        )
    ]
    out = hardening.enrich_tools(src)
    assert out[0]["inputSchema"]["additionalProperties"] is False
    assert out[0]["outputSchema"]["type"] == "object"


def test_enrich_example_on_confirm_gated_tool():
    src = [
        _tool(
            "modal_sandbox_terminate",
            inputSchema={
                "type": "object",
                "properties": {
                    "sandbox_id": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
                "required": ["sandbox_id"],
            },
        )
    ]
    out = hardening.enrich_tools(src)
    desc = out[0]["description"]
    assert "Examples:" in desc
    assert '"confirm": true' in desc and "DESTRUCTIVE" in desc


def test_enrich_no_example_on_simple_readonly():
    src = [
        _tool(
            "modal_secret_list",
            inputSchema={
                "type": "object",
                "properties": {"account": {"type": "string"}},
            },
        )
    ]
    out = hardening.enrich_tools(src)
    assert "Examples:" not in out[0]["description"]


# --------------------------------------------------------------------------- #
# ConfirmGate                                                                   #
# --------------------------------------------------------------------------- #
def _call(name, args=None):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": args or {}},
    }


def test_gate_off_is_noop(tmp_path):
    gate = hardening.ConfirmGate(mode="off", sink_path=str(tmp_path / "s.jsonl"))
    d = gate.check("delete-pod", _call("delete-pod"))
    assert d.blocked is False and d.shadow_logged is False
    assert not os.path.exists(str(tmp_path / "s.jsonl"))


def test_gate_shadow_never_blocks_but_logs(tmp_path):
    sink = str(tmp_path / "s.jsonl")
    gate = hardening.ConfirmGate(mode="shadow", sink_path=sink)
    d = gate.check("delete-pod", _call("delete-pod", {"podId": "p1"}))
    assert d.blocked is False and d.shadow_logged is True
    rec = json.loads(open(sink, encoding="utf-8").read().strip())
    assert rec["tool"] == "delete-pod" and rec["would_block"] is True
    assert rec["arg_keys"] == ["podId"]


def test_gate_shadow_ignores_non_destructive(tmp_path):
    sink = str(tmp_path / "s.jsonl")
    gate = hardening.ConfirmGate(mode="shadow", sink_path=sink)
    d = gate.check("modal_secret_list", _call("modal_secret_list"))
    assert d.blocked is False and d.shadow_logged is False
    assert not os.path.exists(sink)


def test_gate_shadow_logs_keys_not_values(tmp_path):
    sink = str(tmp_path / "s.jsonl")
    gate = hardening.ConfirmGate(mode="shadow", sink_path=sink)
    gate.check("delete-pod", _call("delete-pod", {"podId": "SECRET-VALUE-XYZ"}))
    body = open(sink, encoding="utf-8").read()
    assert "podId" in body
    assert "SECRET-VALUE-XYZ" not in body  # values are never logged


def test_gate_enforce_blocks_without_confirm(tmp_path):
    gate = hardening.ConfirmGate(mode="enforce", sink_path=str(tmp_path / "s.jsonl"))
    d = gate.check("delete-pod", _call("delete-pod", {"podId": "p1"}))
    assert d.blocked is True and "confirm" in d.message.lower()


def test_gate_enforce_allows_with_hub_confirm_and_strips_it(tmp_path):
    gate = hardening.ConfirmGate(mode="enforce", sink_path=str(tmp_path / "s.jsonl"))
    req = _call("delete-pod", {"podId": "p1", "_confirm": True})
    d = gate.check("delete-pod", req)
    assert d.blocked is False
    fwd_args = d.request["params"]["arguments"]
    assert fwd_args == {"podId": "p1"}  # _confirm stripped before forward


def test_gate_enforce_allows_native_confirm_and_keeps_it(tmp_path):
    gate = hardening.ConfirmGate(mode="enforce", sink_path=str(tmp_path / "s.jsonl"))
    req = _call("modal_sandbox_terminate", {"sandbox_id": "s", "confirm": True})
    d = gate.check("modal_sandbox_terminate", req)
    assert d.blocked is False
    assert d.request["params"]["arguments"]["confirm"] is True  # backend keeps it


def test_gate_enforce_allows_dry_run(tmp_path):
    gate = hardening.ConfirmGate(mode="enforce", sink_path=str(tmp_path / "s.jsonl"))
    d = gate.check("delete-pod", _call("delete-pod", {"podId": "p1", "dry_run": True}))
    assert d.blocked is False


def test_gate_enforce_ignores_non_destructive(tmp_path):
    gate = hardening.ConfirmGate(mode="enforce", sink_path=str(tmp_path / "s.jsonl"))
    d = gate.check("modal_secret_list", _call("modal_secret_list"))
    assert d.blocked is False


def test_gate_fail_open_on_internal_error(tmp_path, monkeypatch):
    # If any internal step raises, the gate must fail OPEN (never break the hub).
    def boom(_name):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(hardening, "confirm_required", boom)
    gate = hardening.ConfirmGate(mode="enforce", sink_path=str(tmp_path / "s.jsonl"))
    d = gate.check("delete-pod", _call("delete-pod"))
    assert d.blocked is False  # exception -> forward, do not block


def test_gate_enforce_blocks_unparseable_destructive_request(tmp_path):
    # A destructive call whose args cannot be read (None request) has no
    # confirmation token -> the safe default in enforce mode is to block.
    gate = hardening.ConfirmGate(mode="enforce", sink_path=str(tmp_path / "s.jsonl"))
    d = gate.check("delete-pod", None)  # type: ignore[arg-type]
    assert d.blocked is True


def test_gate_invalid_mode_defaults_to_shadow(tmp_path):
    gate = hardening.ConfirmGate(mode="bananas", sink_path=str(tmp_path / "s.jsonl"))
    assert gate.mode == "shadow"


def test_sink_rotates_when_bounded(tmp_path, monkeypatch):
    sink = str(tmp_path / "s.jsonl")
    monkeypatch.setattr(hardening, "_SINK_MAX_BYTES", 1)  # force rotation
    gate = hardening.ConfirmGate(mode="shadow", sink_path=sink)
    gate.check("delete-pod", _call("delete-pod", {"podId": "a"}))
    gate.check("delete-pod", _call("delete-pod", {"podId": "b"}))
    assert os.path.exists(sink + ".1")  # rolled the first record out


# --------------------------------------------------------------------------- #
# Integration: the REAL HubServer                                              #
# --------------------------------------------------------------------------- #
class _Capture:
    def __init__(self):
        self._q: "queue.Queue[dict]" = queue.Queue()

    def __call__(self, line):
        self._q.put(json.loads(line))

    def wait(self, n, timeout=30.0):
        got = []
        end = time.monotonic() + timeout
        while len(got) < n:
            rem = end - time.monotonic()
            if rem <= 0:
                break
            try:
                got.append(self._q.get(timeout=rem))
            except queue.Empty:
                break
        return got


@pytest.fixture
def infra_hub(tmp_path):
    spec = BackendSpec(
        id="infra",
        label="fake-infra",
        prefix="in",
        cmd=(PY, FAKE, "infra", "widget_delete,widget_list"),
        cache="infra.json",
    )
    old = hub.CACHE_DIR
    hub.CACHE_DIR = str(tmp_path)
    # HubServer builds its AccountStore from hub.ACCOUNTS_PATH, which points at the REAL
    # tools/mcp/cloud-hub/accounts.json -- git-crypt encrypted on any keyless checkout,
    # including every CI runner, so the store raises AccountStoreLoadError and these tests
    # ERROR at setup. The `infra` spec declares no account policy, so an empty store is
    # faithful: same code path, no real credentials anywhere near CI.
    old_accounts = hub.ACCOUNTS_PATH
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text("{}", encoding="utf-8")
    hub.ACCOUNTS_PATH = str(accounts_path)
    ok, _n, msg = hub.refresh_backend(spec)
    assert ok, msg
    plan = build_plan([spec], str(tmp_path))
    cap = _Capture()
    server = hub.HubServer([spec], plan, emit=cap)
    try:
        yield server, cap, tmp_path
    finally:
        hub.CACHE_DIR = old
        hub.ACCOUNTS_PATH = old_accounts
        for b in server.backends.values():
            b._terminate()


def test_tools_list_is_enriched(infra_hub):
    server, cap, _ = infra_hub
    server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = {t["name"]: t for t in cap.wait(1)[0]["result"]["tools"]}
    assert tools["widget_delete"]["annotations"]["destructiveHint"] is True
    assert "Examples:" in tools["widget_delete"]["description"]
    assert tools["widget_list"]["annotations"]["readOnlyHint"] is True
    # served without spawning anything
    assert server.backends["infra"].proc is None


def test_enforce_blocks_destructive_call_without_spawning(infra_hub):
    server, cap, tmp_path = infra_hub
    server._confirm_gate = hardening.ConfirmGate(
        mode="enforce", sink_path=str(tmp_path / "s.jsonl")
    )
    server.dispatch(_call_named("widget_delete", {"target": "x"}))
    reply = cap.wait(1)[0]
    assert reply["result"]["isError"] is True
    assert "confirm" in reply["result"]["content"][0]["text"].lower()
    assert server.backends["infra"].proc is None  # nothing spawned


def test_enforce_forwards_with_confirm_and_strips_hub_key(infra_hub):
    server, cap, tmp_path = infra_hub
    server._confirm_gate = hardening.ConfirmGate(
        mode="enforce", sink_path=str(tmp_path / "s.jsonl")
    )
    server.dispatch(_call_named("widget_delete", {"target": "x", "_confirm": True}))
    reply = cap.wait(1)[0]
    echoed = json.loads(reply["result"]["content"][0]["text"])
    assert echoed["backend"] == "infra"
    assert echoed["received_name"] == "widget_delete"
    assert echoed["arguments"] == {"target": "x"}  # _confirm stripped on forward
    assert server.backends["infra"].proc is not None


def test_shadow_forwards_destructive_unchanged(infra_hub):
    server, cap, tmp_path = infra_hub
    server._confirm_gate = hardening.ConfirmGate(
        mode="shadow", sink_path=str(tmp_path / "s.jsonl")
    )
    server.dispatch(_call_named("widget_delete", {"target": "x"}))
    reply = cap.wait(1)[0]
    echoed = json.loads(reply["result"]["content"][0]["text"])
    assert echoed["arguments"] == {"target": "x"}  # forwarded unchanged
    assert server.backends["infra"].proc is not None
    # and it observed the call in the shadow sink
    assert os.path.exists(str(tmp_path / "s.jsonl"))


def _call_named(name, args):
    return {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }
