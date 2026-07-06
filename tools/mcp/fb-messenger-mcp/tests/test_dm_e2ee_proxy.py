"""FB_DM_PROXY plumbing: proves the proxy is actually applied to BOTH E2EE
egress paths (the fbchat-v2 `requests` calls AND the Go-bridge subprocess env)
when set, is NOT applied when unset (direct, the pre-proxy behavior), and NEVER
leaks a global proxy into the parent process.

fbchat-v2 exposes no proxy/session parameter, so the backend scopes FB_DM_PROXY
by temporarily setting HTTP(S)_PROXY/ALL_PROXY around each call. These tests
capture os.environ at the exact moment each egress would fire (the real
`requests.get/post` reads env at request time; the real `subprocess.Popen`
inherits env at spawn time), which is a faithful stand-in for the real network.
"""

from __future__ import annotations

import json
import os
import threading
from unittest.mock import MagicMock

import pytest

import fbmcp.backends.fbchat_v2_backend as be
from fbmcp.backends.fbchat_v2_backend import FbchatV2Backend

PROXY = "http://user:pass@residential.example:8080"
KEYS = ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY")


@pytest.fixture(autouse=True)
def _clean_proxy_env():
    """Give every test a proxy-free environment and restore the real one after,
    so 'no leak' assertions are meaningful and tests never clobber the shell."""
    watched = KEYS + ("https_proxy", "http_proxy", "all_proxy")
    saved = {k: os.environ.get(k) for k in watched}
    for k in watched:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _snapshot() -> dict:
    return {k: os.environ.get(k) for k in KEYS}


def _assert_no_leak():
    """After a scoped call the parent process must carry no proxy vars."""
    for k in KEYS:
        assert k not in os.environ, f"{k} leaked into parent env"


# --------------------------------------------------------------------------- #
# _proxy_env context manager (the primitive) — set / restore / no-op
# --------------------------------------------------------------------------- #
def test_proxy_env_noop_when_unset():
    b = FbchatV2Backend(cookies_path="x", proxy=None)
    with b._proxy_env():
        assert _snapshot() == {k: None for k in KEYS}  # nothing injected
    _assert_no_leak()


def test_proxy_env_sets_all_keys_and_removes_them_after():
    b = FbchatV2Backend(cookies_path="x", proxy=PROXY)
    with b._proxy_env():
        assert _snapshot() == {k: PROXY for k in KEYS}
    _assert_no_leak()  # absent-before keys are popped, not left behind


def test_proxy_env_restores_prior_value_exactly():
    """A pre-existing parent HTTPS_PROXY must be restored, never clobbered."""
    os.environ["HTTPS_PROXY"] = "http://preexisting:1"
    b = FbchatV2Backend(cookies_path="x", proxy=PROXY)
    with b._proxy_env():
        assert os.environ["HTTPS_PROXY"] == PROXY  # overridden inside scope
    assert os.environ["HTTPS_PROXY"] == "http://preexisting:1"  # restored
    assert "HTTP_PROXY" not in os.environ and "ALL_PROXY" not in os.environ


def test_proxy_env_restores_even_when_body_raises():
    b = FbchatV2Backend(cookies_path="x", proxy=PROXY)
    with pytest.raises(RuntimeError):
        with b._proxy_env():
            assert os.environ["HTTPS_PROXY"] == PROXY
            raise RuntimeError("boom")
    _assert_no_leak()


# --------------------------------------------------------------------------- #
# requests path: dataGetHome + _all_thread_data
# --------------------------------------------------------------------------- #
async def test_data_fb_applies_proxy_to_requests(monkeypatch):
    captured: dict = {}

    def fake_dgh(header):  # stands in for requests.get in dataGetHome
        captured.update(_snapshot())
        return {"cookieFacebook": header}

    monkeypatch.setattr(be, "cookie_header", lambda _p: "c_user=1;")
    b = FbchatV2Backend(cookies_path="x", proxy=PROXY)
    b._lib = lambda: (fake_dgh, MagicMock(), MagicMock(), MagicMock())

    await b._data_fb()

    assert captured == {k: PROXY for k in KEYS}  # proxy live during the GET
    _assert_no_leak()


async def test_data_fb_direct_when_unset(monkeypatch):
    captured: dict = {}

    def fake_dgh(header):
        captured.update(_snapshot())
        return {"cookieFacebook": header}

    monkeypatch.setattr(be, "cookie_header", lambda _p: "c_user=1;")
    b = FbchatV2Backend(cookies_path="x", proxy=None)  # FB_DM_PROXY unset
    b._lib = lambda: (fake_dgh, MagicMock(), MagicMock(), MagicMock())

    await b._data_fb()

    assert captured == {k: None for k in KEYS}  # direct: no proxy injected
    _assert_no_leak()


async def test_list_threads_applies_proxy_to_requests():
    captured: dict = {}
    data_get = json.dumps(
        {
            "o0": {
                "data": {
                    "viewer": {
                        "message_threads": {
                            "nodes": [
                                {
                                    "thread_key": {
                                        "thread_fbid": None,
                                        "other_user_id": "777",
                                    },
                                    "name": "Alice",
                                },
                            ]
                        }
                    }
                }
            }
        }
    )

    def fake_list(data_fb):  # stands in for requests.post in _all_thread_data
        captured.update(_snapshot())
        return {"dataGet": data_get}

    b = FbchatV2Backend(cookies_path="x", proxy=PROXY)
    b._dataFB = {"cookieFacebook": "c_user=1;"}  # skip dataGetHome
    b._lib = lambda: (MagicMock(), fake_list, MagicMock(), MagicMock())

    out = await b.list_threads(limit=20)

    assert captured == {k: PROXY for k in KEYS}
    assert out["count"] == 1 and out["dms"][0]["other_user_id"] == "777"
    _assert_no_leak()


# --------------------------------------------------------------------------- #
# subprocess path: the Go bridge inherits os.environ at Popen (send / react)
# --------------------------------------------------------------------------- #
def _capturing_sender(captured: dict):
    """A fake fbchat-v2 sender whose connect() records os.environ — the exact
    moment the real _BridgeProcess spawns the Go bridge via subprocess.Popen."""
    sender = MagicMock()

    def _connect(enable_e2ee=True):
        captured.update(_snapshot())

    sender.connect.side_effect = _connect
    sender.send.return_value = {"success": 1, "payload": {"messageID": "m1"}}
    sender.bridge.call.return_value = {"ok": 1}
    return sender


async def test_send_applies_proxy_to_subprocess_env():
    captured: dict = {}
    sender = _capturing_sender(captured)
    b = FbchatV2Backend(cookies_path="x", proxy=PROXY)
    b._dataFB = {"cookieFacebook": "c_user=1;"}
    b._lib = lambda: (
        MagicMock(),
        MagicMock(),
        MagicMock(return_value=sender),
        MagicMock(),
    )

    res = await b.send("100012345678", "hello")

    assert captured == {k: PROXY for k in KEYS}  # bridge would inherit the proxy
    assert res["success"] == 1
    sender.close.assert_called_once()
    _assert_no_leak()


async def test_send_direct_when_unset():
    captured: dict = {}
    sender = _capturing_sender(captured)
    b = FbchatV2Backend(cookies_path="x", proxy=None)  # FB_DM_PROXY unset
    b._dataFB = {"cookieFacebook": "c_user=1;"}
    b._lib = lambda: (
        MagicMock(),
        MagicMock(),
        MagicMock(return_value=sender),
        MagicMock(),
    )

    await b.send("100012345678", "hello")

    assert captured == {k: None for k in KEYS}  # direct egress, as before
    _assert_no_leak()


async def test_react_applies_proxy_to_subprocess_env():
    captured: dict = {}
    sender = _capturing_sender(captured)
    b = FbchatV2Backend(cookies_path="x", proxy=PROXY)
    b._dataFB = {"cookieFacebook": "c_user=1;"}
    b._lib = lambda: (
        MagicMock(),
        MagicMock(),
        MagicMock(return_value=sender),
        MagicMock(),
    )

    await b.react("777", "MID", "❤")

    assert captured == {k: PROXY for k in KEYS}
    sender.bridge.call.assert_called_once()
    _assert_no_leak()


# --------------------------------------------------------------------------- #
# read path: listener __init__ (requests) + connect_mqtt (bridge Popen)
# --------------------------------------------------------------------------- #
async def test_read_thread_applies_proxy_to_requests_and_subprocess(monkeypatch):
    holder: list = []

    class _Listener:
        def __init__(self, data_fb, binary_path=None):
            # __init__ runs _all_thread_data.func(dataFB) -> requests.post
            self.env_at_init = _snapshot()
            self.env_at_connect = None
            self._stop = threading.Event()
            self.captured = threading.Event()
            holder.append(self)

        def on_message(self, fn):
            return fn

        def connect_mqtt(self):  # real one spawns the Go bridge via Popen
            self.env_at_connect = _snapshot()
            self.captured.set()
            self._stop.wait(timeout=5)  # block like the real poll loop

        def stop(self):
            self._stop.set()

    # Make the daemon-thread capture deterministic: the backend's time.sleep
    # (the listen window) waits until connect_mqtt has recorded the env.
    monkeypatch.setattr(
        be.time, "sleep", lambda _s: holder[-1].captured.wait(timeout=5)
    )

    b = FbchatV2Backend(cookies_path="x", proxy=PROXY)
    b._dataFB = {"cookieFacebook": "c_user=1;"}
    b._lib = lambda: (
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(side_effect=_Listener),
    )

    out = await b.read_thread("777", limit=5, listen_seconds=0)

    lst = holder[-1]
    assert lst.env_at_init == {k: PROXY for k in KEYS}  # requests path
    assert lst.env_at_connect == {k: PROXY for k in KEYS}  # bridge Popen path
    assert out["count"] == 0
    _assert_no_leak()


async def test_read_thread_direct_when_unset(monkeypatch):
    holder: list = []

    class _Listener:
        def __init__(self, data_fb, binary_path=None):
            self.env_at_init = _snapshot()
            self.env_at_connect = None
            self._stop = threading.Event()
            self.captured = threading.Event()
            holder.append(self)

        def on_message(self, fn):
            return fn

        def connect_mqtt(self):
            self.env_at_connect = _snapshot()
            self.captured.set()
            self._stop.wait(timeout=5)

        def stop(self):
            self._stop.set()

    monkeypatch.setattr(
        be.time, "sleep", lambda _s: holder[-1].captured.wait(timeout=5)
    )

    b = FbchatV2Backend(cookies_path="x", proxy=None)  # FB_DM_PROXY unset
    b._dataFB = {"cookieFacebook": "c_user=1;"}
    b._lib = lambda: (
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(side_effect=_Listener),
    )

    await b.read_thread("777", limit=5, listen_seconds=0)

    lst = holder[-1]
    assert lst.env_at_init == {k: None for k in KEYS}
    assert lst.env_at_connect == {k: None for k in KEYS}
    _assert_no_leak()


# --------------------------------------------------------------------------- #
# status still surfaces the proxy flag (behavior unchanged)
# --------------------------------------------------------------------------- #
async def test_status_reports_proxy_set(monkeypatch):
    b = FbchatV2Backend(cookies_path="x", proxy=PROXY)
    monkeypatch.setattr(be, "missing_e2ee_cookies", lambda _p: [])
    b._lib = lambda: (MagicMock(), MagicMock(), MagicMock(), MagicMock())
    # avoid the real bridge-binary resolver (it may hit the network to download)
    monkeypatch.setattr(
        "fbchat_v2._messaging._listening_e2ee._resolve_binary", lambda: "bin"
    )

    info = await b.status()

    assert info["proxy_set"] is True
    assert info["ready"] is True


# --------------------------------------------------------------------------- #
# module completeness: exercise the fallbacks / error branches the proxy change
# routes through, so the touched module stays fully covered.
# --------------------------------------------------------------------------- #
def test_lib_imports_the_real_symbols():
    fns = FbchatV2Backend(cookies_path="x")._lib()
    assert len(fns) == 4 and all(callable(f) for f in fns)


def test_new_sender_falls_back_on_old_kwarg_set():
    def SendApi(**kwargs):
        if "e2ee_memory_only" in kwargs or "binary_path" in kwargs:
            raise TypeError("older fbchat-v2 signature")
        return "sender-obj"

    b = FbchatV2Backend(cookies_path="x")
    assert b._new_sender(SendApi, {"cookieFacebook": "c;"}) == "sender-obj"


async def test_status_reports_lib_not_importable(monkeypatch):
    b = FbchatV2Backend(cookies_path="x")
    monkeypatch.setattr(be, "missing_e2ee_cookies", lambda _p: [])
    b._lib = MagicMock(side_effect=ImportError("no fbchat_v2"))

    info = await b.status()

    assert info["lib_installed"] is False
    assert info["ready"] is False
    assert "not importable" in info["reason"]


async def test_status_reports_bridge_binary_missing(monkeypatch):
    b = FbchatV2Backend(cookies_path="x")
    monkeypatch.setattr(be, "missing_e2ee_cookies", lambda _p: [])
    b._lib = lambda: (MagicMock(), MagicMock(), MagicMock(), MagicMock())
    monkeypatch.setattr(
        "fbchat_v2._messaging._listening_e2ee._resolve_binary",
        MagicMock(side_effect=RuntimeError("binary not found")),
    )

    info = await b.status()

    assert info["bridge_binary_found"] is False
    assert info["ready"] is False
    assert "go bridge binary not resolved" in info["reason"]


async def test_status_reports_missing_cookies(monkeypatch):
    b = FbchatV2Backend(cookies_path="x")
    monkeypatch.setattr(be, "missing_e2ee_cookies", lambda _p: ["datr", "fr"])
    b._lib = lambda: (MagicMock(), MagicMock(), MagicMock(), MagicMock())
    monkeypatch.setattr(
        "fbchat_v2._messaging._listening_e2ee._resolve_binary", lambda: "bin"
    )

    info = await b.status()

    assert info["ready"] is False
    assert "missing required cookies" in info["reason"]


async def test_list_threads_parse_error_returns_group_fallback():
    b = FbchatV2Backend(cookies_path="x", proxy=None)
    b._dataFB = {"cookieFacebook": "c_user=1;"}
    b._lib = lambda: (
        MagicMock(),
        lambda _d: {"dataGet": "not-json", "dataAllThread": {"countThread": 3}},
        MagicMock(),
        MagicMock(),
    )

    out = await b.list_threads()

    assert "could not parse DM thread list" in out["error"]
    assert out["group_threads"] == {"countThread": 3}


async def test_list_threads_respects_limit():
    nodes = [
        {"thread_key": {"thread_fbid": None, "other_user_id": "1"}, "name": "A"},
        {"thread_key": {"thread_fbid": None, "other_user_id": "2"}, "name": "B"},
    ]
    data_get = json.dumps(
        {"o0": {"data": {"viewer": {"message_threads": {"nodes": nodes}}}}}
    )
    b = FbchatV2Backend(cookies_path="x", proxy=None)
    b._dataFB = {"cookieFacebook": "c_user=1;"}
    b._lib = lambda: (
        MagicMock(),
        lambda _d: {"dataGet": data_get},
        MagicMock(),
        MagicMock(),
    )

    out = await b.list_threads(limit=1)

    assert out["count"] == 1  # hit the limit break with a second DM present


async def test_read_thread_listener_fallback_and_stop_error(monkeypatch):
    class _FakeL:
        def on_message(self, fn):
            return fn

        def connect_mqtt(self):
            pass

        def stop(self):  # teardown errors are swallowed (best-effort)
            raise RuntimeError("stop boom")

    def _Listener(data_fb, **kwargs):
        if "binary_path" in kwargs:  # emulate an older listener signature
            raise TypeError("no binary_path kwarg")
        return _FakeL()

    monkeypatch.setattr(be.time, "sleep", lambda _s: None)
    b = FbchatV2Backend(cookies_path="x", proxy=None)
    b._dataFB = {"cookieFacebook": "c_user=1;"}
    b._lib = lambda: (
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(side_effect=_Listener),
    )

    out = await b.read_thread("777", limit=5, listen_seconds=0)

    assert out["count"] == 0  # fell back to Listener(data_fb) and survived stop()
