"""T4 E2EE DM: cookie loading, JID mapping, backend call shape, honest
success reporting, and graceful 'not configured' behavior (no creds needed)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import fbmcp.dm_e2ee as dm
from fbmcp.backends._cookies import (
    cookie_header,
    load_cookie_map,
    missing_e2ee_cookies,
)
from fbmcp.backends.fbchat_v2_backend import FbchatV2Backend


# --------------------------------------------------------------------------- #
# cookie loader
# --------------------------------------------------------------------------- #
def _c3c(tmp_path, **kv):
    p = tmp_path / "cookies.json"
    p.write_text(json.dumps([{"key": k, "value": v, "domain": ".facebook.com"}
                             for k, v in kv.items()]))
    return str(p)


def test_load_c3c_list(tmp_path):
    path = _c3c(tmp_path, c_user="100", xs="abc", datr="d", fr="f")
    m = load_cookie_map(path)
    assert m == {"c_user": "100", "xs": "abc", "datr": "d", "fr": "f"}
    assert cookie_header(path) == "c_user=100; xs=abc; datr=d; fr=f"
    assert missing_e2ee_cookies(path) == []


def test_missing_required_cookies(tmp_path):
    path = _c3c(tmp_path, c_user="100", xs="abc")  # no datr/fr
    assert set(missing_e2ee_cookies(path)) == {"datr", "fr"}


def test_flat_map_form(tmp_path):
    p = tmp_path / "flat.json"
    p.write_text(json.dumps({"c_user": "1", "xs": "2", "datr": "3", "fr": "4"}))
    assert load_cookie_map(str(p))["c_user"] == "1"


def test_wrapped_cookies_form(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(json.dumps({"cookies": [{"name": "c_user", "value": "9"}]}))
    assert load_cookie_map(str(p)) == {"c_user": "9"}


# --------------------------------------------------------------------------- #
# JID mapping + DM parsing
# --------------------------------------------------------------------------- #
def test_to_jid_default_suffix():
    b = FbchatV2Backend(cookies_path="x")
    assert b._to_jid("100012345678") == "100012345678@s.whatsapp.net"
    assert b._to_jid("abc@msgr") == "abc@msgr"  # full jid passes through


def test_to_jid_custom_suffix(monkeypatch):
    monkeypatch.setenv("FB_DM_JID_SUFFIX", "@msgr")
    b = FbchatV2Backend(cookies_path="x")
    assert b._to_jid("123") == "123@msgr"


def test_parse_dms_excludes_groups():
    b = FbchatV2Backend(cookies_path="x")
    data_get = json.dumps({
        "o0": {"data": {"viewer": {"message_threads": {"nodes": [
            {"thread_key": {"thread_fbid": "555", "other_user_id": None}, "name": "Group"},
            {"thread_key": {"thread_fbid": None, "other_user_id": "777"}, "name": "Alice"},
        ]}}}}
    })
    out = b._parse_dms({"dataGet": data_get}, limit=20)
    assert out["count"] == 1
    assert out["dms"][0]["other_user_id"] == "777"
    assert out["dms"][0]["thread_jid"] == "777@s.whatsapp.net"


# --------------------------------------------------------------------------- #
# Backend call shape (mock the fbchat-v2 library — no bridge/creds)
# --------------------------------------------------------------------------- #
async def test_backend_send_maps_to_real_api():
    b = FbchatV2Backend(cookies_path="x")
    b._dataFB = {"cookieFacebook": "c_user=1;"}  # skip dataGetHome
    sender = MagicMock()
    sender.send.return_value = {"success": 1, "payload": {"messageID": "m1"}}
    SendApi = MagicMock(return_value=sender)
    b._lib = lambda: (MagicMock(), MagicMock(), SendApi, MagicMock())

    res = await b.send("100012345678", "hello")

    sender.connect.assert_called_once_with(enable_e2ee=True)
    sender.send.assert_called_once_with("100012345678@s.whatsapp.net", "hello")
    sender.close.assert_called_once()
    assert res["success"] == 1


async def test_backend_react_uses_bridge_rpc():
    b = FbchatV2Backend(cookies_path="x")
    b._dataFB = {"cookieFacebook": "c_user=1;"}
    sender = MagicMock()
    sender.bridge.call.return_value = {"ok": 1}
    SendApi = MagicMock(return_value=sender)
    b._lib = lambda: (MagicMock(), MagicMock(), SendApi, MagicMock())

    await b.react("777", "MID", "❤")

    sender.bridge.call.assert_called_once_with(
        "sendE2EEReaction",
        {"chatJid": "777@s.whatsapp.net", "messageId": "MID",
         "senderJid": "777@s.whatsapp.net", "emoji": "❤"},
    )


# --------------------------------------------------------------------------- #
# Tool wiring: honest success + graceful 'not configured'
# --------------------------------------------------------------------------- #
class _FakeBackend:
    def __init__(self, send_result):
        self._send_result = send_result
        self.reacted = None

    async def status(self):
        return {"ready": True}

    async def send(self, thread_id, text):
        return self._send_result

    async def react(self, thread_id, message_id, emoji):
        self.reacted = (thread_id, message_id, emoji)
        return {"ok": 1}

    async def list_threads(self, limit=20):
        return {"dms": []}


async def test_send_reports_true_only_on_success(monkeypatch, get_tool):
    fake = _FakeBackend({"success": 1, "payload": {"messageID": "m"}})
    monkeypatch.setattr(dm, "_load_backend", lambda: fake)
    out = json.loads(await get_tool("fb_dm_send")(thread_id="777", text="hi"))
    assert out["sent"] is True


async def test_send_reports_false_on_error(monkeypatch, get_tool):
    fake = _FakeBackend({"error": 1, "payload": {"error-code": "x"}})
    monkeypatch.setattr(dm, "_load_backend", lambda: fake)
    out = json.loads(await get_tool("fb_dm_send")(thread_id="777", text="hi"))
    assert out["sent"] is False  # never fabricate a send


async def test_react_wiring(monkeypatch, get_tool):
    fake = _FakeBackend({})
    monkeypatch.setattr(dm, "_load_backend", lambda: fake)
    await get_tool("fb_dm_react")(thread_id="777", message_id="M", emoji="👍")
    assert fake.reacted == ("777", "M", "👍")


async def test_not_configured_is_graceful(monkeypatch, get_tool):
    def _raise():
        raise dm.DMNotConfigured("nope")

    monkeypatch.setattr(dm, "_load_backend", _raise)
    out = json.loads(await get_tool("fb_dm_send")(thread_id="777", text="hi"))
    assert out["sent"] is False and out["error"] == "not_configured"


async def test_status_reports_disabled(monkeypatch, get_tool):
    monkeypatch.delenv("FB_E2EE_ENABLED", raising=False)
    out = json.loads(await get_tool("fb_dm_status")())
    assert out["ready"] is False
    assert out["license"] == "AGPL-3.0"


async def test_backend_selector_unknown(monkeypatch):
    monkeypatch.setenv("FB_E2EE_ENABLED", "1")
    monkeypatch.setenv("FB_DM_BACKEND", "bogus")
    with pytest.raises(dm.DMNotConfigured):
        dm._load_backend()
