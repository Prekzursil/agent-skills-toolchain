#!/usr/bin/env python3
"""Tests for the shared multi-account layer as wired into the social-hub.

Covers the env-mode store ops (add/list/switch/cycle/current/remove) plus the
social-specific nuance: a login is a FILE, so switching an account swaps which
session/cookie file the backend loads -- either by pointing a path env var at it
(Instagram ``INSTA_DATA_DIR``, fb-messenger ``FB_COOKIES_PATH``; copy-free) or by
COPYING the account's artifact onto a backend's fixed path (WhatsApp
``auth_info/``). Also: kill+respawn on switch, no-secret-leak, and the account
tools being listed + served WITHOUT spawning a backend.
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

import accounts  # noqa: E402
import hub  # noqa: E402
from accounts import AccountPolicy, AccountStore, FileSlot  # noqa: E402
from backends import BackendSpec, default_backends  # noqa: E402
from registry import build_plan  # noqa: E402

PY = sys.executable
FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_backend.py")


# --------------------------------------------------------------------------- #
# env-mode store basics (tiktok: keyless, env-only, no file slot)
# --------------------------------------------------------------------------- #
def _tt_store(tmp_path, environ=None):
    pol = AccountPolicy(platform="tiktok", mode="env", label="TikTok")
    return AccountStore(str(tmp_path / "acc.json"), [pol], environ=environ or {})


def test_env_add_list_switch_cycle_current_remove(tmp_path):
    store = _tt_store(tmp_path)
    add = store.handle(
        "tiktok", "add", {"name": "default", "env": {"TIKTOK_MS_TOKEN": "t0"}}
    )
    assert add["ok"] and add["active"] == "default"
    store.handle(
        "tiktok",
        "add",
        {
            "name": "proxied",
            "env": {"TIKTOK_MS_TOKEN": "t1", "TIKTOK_PROXY": "http://p"},
        },
    )
    assert store.handle("tiktok", "list", {})["accounts"] == ["default", "proxied"]

    sw = store.handle("tiktok", "switch", {"name": "proxied"})
    assert sw["ok"] and sw["respawn"] is True
    assert store.active_env("tiktok") == {
        "TIKTOK_MS_TOKEN": "t1",
        "TIKTOK_PROXY": "http://p",
    }

    cyc = store.handle("tiktok", "cycle", {})  # proxied -> default (round-robin)
    assert cyc["active"] == "default" and cyc["respawn"] is True
    assert store.active_env("tiktok") == {"TIKTOK_MS_TOKEN": "t0"}

    cur = store.handle("tiktok", "current", {})  # keys only, no file slots
    assert cur["active"] == "default"
    assert cur["env_keys"] == ["TIKTOK_MS_TOKEN"] and cur["file_keys"] == []

    rm = store.handle("tiktok", "remove", {"name": "proxied"})
    assert rm["ok"] and store.handle("tiktok", "list", {})["accounts"] == ["default"]


def test_env_only_backend_has_no_file_actions(tmp_path):
    store = _tt_store(tmp_path)
    store.handle("tiktok", "add", {"name": "x", "env": {"TIKTOK_MS_TOKEN": "t"}})
    assert store.active_files("tiktok") == []
    assert store.materialize_files("tiktok") == {
        "platform": "tiktok",
        "copied": [],
        "errors": [],
    }


def test_cycle_with_no_accounts_errors(tmp_path):
    store = _tt_store(tmp_path)
    res = store.handle("tiktok", "cycle", {})
    assert not res["ok"] and "no accounts" in res["error"]


# --------------------------------------------------------------------------- #
# file switching via an ENV-VAR pointer (Instagram INSTA_DATA_DIR, fb COOKIES)
# --------------------------------------------------------------------------- #
def _ig_store(tmp_path):
    slot = FileSlot(
        key="session",
        dest=str(tmp_path / "ig_data"),
        env_var="INSTA_DATA_DIR",
        is_dir=True,
    )
    pol = AccountPolicy(platform="insta", mode="env", label="Instagram", files=(slot,))
    return AccountStore(str(tmp_path / "acc.json"), [pol], environ={}), pol


def test_ig_switch_points_data_dir_env_no_copy(tmp_path):
    store, _ = _ig_store(tmp_path)
    alice = str(tmp_path / "ig" / "alice")  # dir holding session.json
    bob = str(tmp_path / "ig" / "bob")
    store.handle(
        "insta",
        "add",
        {
            "name": "alice",
            "env": {"IG_APP_VERSION": "431.1.0"},
            "files": {"session": alice},
        },
    )
    store.handle("insta", "add", {"name": "bob", "env": {}, "files": {"session": bob}})
    # active = alice (first add): its data dir is exported via INSTA_DATA_DIR.
    env = store.active_env("insta")
    assert env["INSTA_DATA_DIR"] == alice and env["IG_APP_VERSION"] == "431.1.0"
    # env-var slot -> NOTHING to physically copy.
    assert store.active_files("insta") == []

    sw = store.handle("insta", "switch", {"name": "bob"})
    assert sw["ok"] and sw["respawn"] is True
    # Switching swapped which session file the backend will load.
    assert store.active_env("insta")["INSTA_DATA_DIR"] == bob


def test_fb_cookies_path_env_pointer(tmp_path):
    slot = FileSlot(
        key="cookies",
        dest=str(tmp_path / "fb" / "cookies.json"),
        env_var="FB_COOKIES_PATH",
        is_dir=False,
    )
    pol = AccountPolicy(platform="fb", mode="env", label="FB", files=(slot,))
    store = AccountStore(str(tmp_path / "acc.json"), [pol], environ={})
    main = str(tmp_path / "fb" / "main-cookies.json")
    # A file-ONLY account (empty env) is valid for a file-capable backend.
    add = store.handle(
        "fb", "add", {"name": "main", "env": {}, "files": {"cookies": main}}
    )
    assert add["ok"]
    assert store.active_env("fb") == {"FB_COOKIES_PATH": main}
    assert store.active_files("fb") == []  # env pointer, no copy


def test_unknown_file_slot_rejected(tmp_path):
    store, _ = _ig_store(tmp_path)
    bad = store.handle(
        "insta", "add", {"name": "x", "env": {}, "files": {"nope": "/tmp/x"}}
    )
    assert not bad["ok"] and "unknown file slot" in bad["error"]


# --------------------------------------------------------------------------- #
# file switching via a physical COPY (WhatsApp auth_info/, no env override)
# --------------------------------------------------------------------------- #
def _wa_store(tmp_path):
    dest = tmp_path / "wa_auth_info"
    slot = FileSlot(key="auth", dest=str(dest), env_var="", is_dir=True)
    pol = AccountPolicy(platform="wa", mode="env", label="WhatsApp", files=(slot,))
    store = AccountStore(str(tmp_path / "acc.json"), [pol], environ={})
    return store, dest


def _auth_dir(tmp_path, name, marker):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "creds.json").write_text(marker, encoding="utf-8")
    return str(d)


def test_wa_switch_copies_auth_dir_onto_fixed_path(tmp_path):
    store, dest = _wa_store(tmp_path)
    a_src = _auth_dir(tmp_path, "acc_a", "AAA")
    b_src = _auth_dir(tmp_path, "acc_b", "BBB")
    store.handle("wa", "add", {"name": "a", "env": {}, "files": {"auth": a_src}})
    store.handle("wa", "add", {"name": "b", "env": {}, "files": {"auth": b_src}})

    # copy-only slot: NO env pointer, but a copy action IS planned.
    assert store.active_env("wa") == {}
    actions = store.active_files("wa")
    assert len(actions) == 1 and actions[0].dest == str(dest)

    rep = store.materialize_files("wa")  # active = a
    assert rep["copied"] == ["auth"] and not rep["errors"]
    assert (dest / "creds.json").read_text(encoding="utf-8") == "AAA"

    store.handle("wa", "switch", {"name": "b"})
    store.materialize_files("wa")  # session file swapped to b
    assert (dest / "creds.json").read_text(encoding="utf-8") == "BBB"


def test_materialize_reports_missing_source(tmp_path):
    store, _dest = _wa_store(tmp_path)
    store.handle(
        "wa",
        "add",
        {
            "name": "ghost",
            "env": {},
            "files": {"auth": str(tmp_path / "does_not_exist")},
        },
    )
    rep = store.materialize_files("wa")
    assert rep["copied"] == [] and rep["errors"][0]["key"] == "auth"


# --------------------------------------------------------------------------- #
# no-secret-leak: ${REF} bundles resolve at spawn but never hit disk literally
# --------------------------------------------------------------------------- #
def test_ref_env_resolves_but_secret_never_persisted(tmp_path):
    slot = FileSlot(
        key="cookies", dest=str(tmp_path / "c.json"), env_var="FB_COOKIES_PATH"
    )
    pol = AccountPolicy(platform="fb", mode="env", label="FB", files=(slot,))
    store = AccountStore(
        str(tmp_path / "acc.json"), [pol], environ={"FB_TOKEN": "s3cr3t-value"}
    )
    store.handle(
        "fb",
        "add",
        {
            "name": "main",
            "env": {"FB_PAGE_ACCESS_TOKEN": "${FB_TOKEN}"},
            "files": {"cookies": str(tmp_path / "main.json")},
        },
    )
    # Resolves to the real secret only in the live spawn env...
    assert store.active_env("fb")["FB_PAGE_ACCESS_TOKEN"] == "s3cr3t-value"
    # ...but the gitignored store keeps only the ${REF}, never the literal.
    on_disk = (tmp_path / "acc.json").read_text(encoding="utf-8")
    assert "s3cr3t-value" not in on_disk and "${FB_TOKEN}" in on_disk
    # `current` returns keys only (never values).
    cur = store.handle("fb", "current", {})
    assert cur["env_keys"] == ["FB_PAGE_ACCESS_TOKEN"] and cur["file_keys"] == [
        "cookies"
    ]


# --------------------------------------------------------------------------- #
# real backends wire an account policy for exactly ig/tt/fb/wa (not fbreels)
# --------------------------------------------------------------------------- #
def test_default_backends_account_policies():
    by_id = {s.id: s for s in default_backends()}
    assert by_id["insta"].account.files[0].env_var == "INSTA_DATA_DIR"
    assert by_id["fb"].account.files[0].env_var == "FB_COOKIES_PATH"
    assert by_id["wa"].account.files[0].env_var == ""  # copy-only
    assert by_id["tiktok"].account.files == ()  # keyless, no file
    assert by_id["fbreels"].account is None  # not in scope


def test_account_tool_defs_shape_for_social():
    ig = accounts.account_tool_defs(
        "ig", "insta", "env", "Instagram", file_slots=("session",)
    )
    names = [d["name"] for d in ig]
    assert names == [
        "ig_account_list",
        "ig_account_current",
        "ig_account_add",
        "ig_account_remove",
        "ig_account_switch",
        "ig_account_cycle",
    ]
    add = next(d for d in ig if d["name"] == "ig_account_add")
    assert "files" in add["inputSchema"]["properties"]
    # a file-capable account may omit env (file-only) -> name is the only required
    assert add["inputSchema"]["required"] == ["name"]
    # keyless tiktok has no file slots -> add still requires an env bundle
    tt_add = next(
        d
        for d in accounts.account_tool_defs("tt", "tiktok", "env")
        if d["name"] == "tt_account_add"
    )
    assert tt_add["inputSchema"]["required"] == ["name", "env"]


# --------------------------------------------------------------------------- #
# hub wiring: listed without spawn + switch copies session then kills backend
# --------------------------------------------------------------------------- #
class _Capture:
    def __init__(self):
        self._q: "queue.Queue[dict]" = queue.Queue()

    def __call__(self, line: str) -> None:
        self._q.put(json.loads(line))

    def wait(self, n: int, timeout: float = 30.0) -> list[dict]:
        got: list[dict] = []
        end = time.monotonic() + timeout
        while len(got) < n and (rem := end - time.monotonic()) > 0:
            try:
                got.append(self._q.get(timeout=rem))
            except queue.Empty:
                break
        return got


@pytest.fixture
def account_hub(tmp_path):
    dest = tmp_path / "wa_auth"
    slot = FileSlot(key="auth", dest=str(dest), env_var="", is_dir=True)
    spec = BackendSpec(
        id="wa",
        label="WhatsApp",
        prefix="wa",
        cmd=(PY, FAKE, "wa", "wa_only"),
        cache="wa.json",
        account=AccountPolicy(
            platform="wa", mode="env", label="WhatsApp", files=(slot,)
        ),
    )
    cache_dir = str(tmp_path)
    old = hub.CACHE_DIR
    hub.CACHE_DIR = cache_dir
    ok, _n, msg = hub.refresh_backend(spec)
    assert ok, msg
    plan = build_plan([spec], cache_dir)
    store = AccountStore(str(tmp_path / "acc.json"), [spec.account], environ={})
    cap = _Capture()
    server = hub.HubServer([spec], plan, emit=cap, account_store=store)
    try:
        yield server, store, cap, dest, tmp_path
    finally:
        hub.CACHE_DIR = old
        for backend in server.backends.values():
            backend._terminate()


def test_account_tools_listed_and_served_without_spawn(account_hub):
    server, _store, cap, _dest, _tmp = account_hub
    server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    tools = {t["name"] for t in cap.wait(1)[0]["result"]["tools"]}
    assert {
        "wa_account_list",
        "wa_account_switch",
        "wa_account_cycle",
        "wa_only",
    } <= tools
    add = [t for t in server.all_tools if t["name"] == "wa_account_add"][0]
    assert "files" in add["inputSchema"]["properties"]  # session-file slot shown

    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "wa_account_list", "arguments": {}},
        }
    )
    reply = cap.wait(1)[0]
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["accounts"] == []  # no accounts configured, no seed
    assert server.backends["wa"].proc is None  # account mgmt never spawns


def test_switch_copies_session_then_kills_and_resets_backend(account_hub):
    server, store, cap, dest, tmp = account_hub
    # Start the backend with a real tool call.
    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "wa_only", "arguments": {}},
        }
    )
    assert cap.wait(1)[0]["id"] == 10
    assert server.backends["wa"].proc is not None

    a_src = _auth_dir(tmp, "a", "AAA")
    b_src = _auth_dir(tmp, "b", "BBB")
    store.handle("wa", "add", {"name": "a", "env": {}, "files": {"auth": a_src}})
    store.handle("wa", "add", {"name": "b", "env": {}, "files": {"auth": b_src}})

    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "wa_account_switch", "arguments": {"name": "b"}},
        }
    )
    reply = cap.wait(1)[0]
    payload = json.loads(reply["result"]["content"][0]["text"])
    assert payload["ok"] and payload["active"] == "b"
    # The newly-active account's session file was copied onto the backend path...
    assert payload["files"]["copied"] == ["auth"]
    assert (dest / "creds.json").read_text(encoding="utf-8") == "BBB"
    # ...and the backend was killed + reset (next call respawns with new session).
    assert server.backends["wa"].proc is None
    assert server.backends["wa"].started is False
