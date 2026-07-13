#!/usr/bin/env python3
"""social-hub view of the shared D4/D6 hardening layer (_shared/hardening.py).

social-hub fronts read scrapers + normal app writes (post/send/upload) but NO
irreversible resource-destruction tools, so the D4 confirm gate is correctly a
no-op here; the value is the D6 enrichment (readOnly hints on scrapers, no-op
hints on writes, account-tool tightening, usage examples). The full gate
mechanics are exercised in cloud-hub/tests/test_hardening.py.
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


@pytest.mark.parametrize(
    "name,expected",
    [
        ("get_saved_posts", "READONLY"),
        ("get_recent_posts", "READONLY"),
        ("fb_page_read_posts", "READONLY"),
        ("search_messages", "READONLY"),
        ("tiktok_comments", "UNKNOWN"),
        ("fb_page_post", "WRITE"),
        ("upload_reel", "WRITE"),
        ("ig_graph_publish", "WRITE"),
        ("fb_send_message", "WRITE"),
        ("fb_unsend_message", "DISRUPTIVE"),
    ],
)
def test_social_classification(name, expected):
    assert hardening.classify(name) == expected


def test_no_social_tool_is_confirm_gated():
    # social-hub has no irreversible-resource-destruction tools
    for name in (
        "fb_page_post",
        "upload_reel",
        "ig_graph_publish",
        "fb_send_message",
        "fb_unsend_message",
        "block_user",
        "get_saved_posts",
        "search_messages",
    ):
        assert hardening.confirm_required(name) is False


def test_social_write_annotations():
    a = hardening.annotations_for("fb_page_post")
    assert a["readOnlyHint"] is False and a["destructiveHint"] is False


def test_social_read_annotations():
    a = hardening.annotations_for("get_saved_posts")
    assert a["readOnlyHint"] is True


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
def social_hub(tmp_path):
    spec = BackendSpec(
        id="ig",
        label="fake-ig",
        prefix="ig",
        cmd=(PY, FAKE, "ig", "get_saved_posts,fb_page_post"),
        cache="ig.json",
    )
    old = hub.CACHE_DIR
    hub.CACHE_DIR = str(tmp_path)
    ok, _n, msg = hub.refresh_backend(spec)
    assert ok, msg
    plan = build_plan([spec], str(tmp_path))
    cap = _Capture()
    server = hub.HubServer([spec], plan, emit=cap)
    try:
        yield server, cap
    finally:
        hub.CACHE_DIR = old
        for b in server.backends.values():
            b._terminate()


def test_social_tools_list_enriched(social_hub):
    server, cap = social_hub
    server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = {t["name"]: t for t in cap.wait(1)[0]["result"]["tools"]}
    assert tools["get_saved_posts"]["annotations"]["readOnlyHint"] is True
    assert tools["fb_page_post"]["annotations"]["readOnlyHint"] is False
    assert server.backends["ig"].proc is None  # served without spawning


def test_social_write_forwards_normally(social_hub):
    server, cap = social_hub
    server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "fb_page_post", "arguments": {"message": "hi"}},
        }
    )
    echoed = json.loads(cap.wait(1)[0]["result"]["content"][0]["text"])
    assert echoed["arguments"] == {"message": "hi"}  # gate never touches a write
    assert server.backends["ig"].proc is not None
