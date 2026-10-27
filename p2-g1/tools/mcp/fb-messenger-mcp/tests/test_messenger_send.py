"""T3 non-E2EE send/react tools: verify each maps to the right fbchat-muqit
Client method with the right argument order (the load-bearing part)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

import fbmcp.messenger_send as ms


class _FakeCM:
    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, *a):
        return False


@pytest.fixture
def client(monkeypatch):
    c = AsyncMock()
    c.send_message = AsyncMock(return_value="MID123")
    c.create_group_thread = AsyncMock(return_value="TID9")
    monkeypatch.setattr(ms, "fb_client", lambda: _FakeCM(c))
    return c


async def test_send_message(client, get_tool):
    out = json.loads(
        await get_tool("fb_send_message")(
            thread_id="T", text="hi", reply_to_message="M"
        )
    )
    client.send_message.assert_awaited_once_with("hi", "T", reply_to_message="M")
    assert out["message_id"] == "MID123" and out["sent"] is True


async def test_send_file_requires_input(client, get_tool):
    out = json.loads(await get_tool("fb_send_file")(thread_id="T"))
    assert "error" in out
    client.send_message.assert_not_awaited()


async def test_send_file_url(client, get_tool):
    await get_tool("fb_send_file")(thread_id="T", file_url=["http://u"], text="cap")
    client.send_message.assert_awaited_once_with(
        "cap", "T", file_path=None, file_url=["http://u"]
    )


async def test_react_argument_order(client, get_tool):
    # fbchat-muqit signature is react(reaction, message_id, thread_id)
    await get_tool("fb_react_to_message")(thread_id="T", message_id="M", emoji="❤")
    client.react.assert_awaited_once_with("❤", "M", "T")


async def test_unsend_argument_order(client, get_tool):
    await get_tool("fb_unsend_message")(thread_id="T", message_id="M")
    client.unsend.assert_awaited_once_with("M", "T")


async def test_forward(client, get_tool):
    await get_tool("fb_forward_message")(message_id="M", to_thread_id="T2")
    client.forward_message.assert_awaited_once_with("M", "T2")


async def test_mark_read(client, get_tool):
    await get_tool("fb_mark_read")(thread_id="T")
    client.mark_as_read.assert_awaited_once_with("T")


async def test_typing(client, get_tool):
    await get_tool("fb_send_typing")(thread_id="T", is_typing=False)
    client.typing.assert_awaited_once_with("T", False)


async def test_create_group(client, get_tool):
    out = json.loads(await get_tool("fb_create_group")(participant_ids=["a", "b"]))
    client.create_group_thread.assert_awaited_once_with(["a", "b"])
    assert out["thread_id"] == "TID9"
