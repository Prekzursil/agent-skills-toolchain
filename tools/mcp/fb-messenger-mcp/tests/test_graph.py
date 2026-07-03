"""T1 Graph API tools: verify exact URL / method / params / body construction.

The single HTTP choke point `fbmcp.graph._do_http` is replaced with a recorder,
so no network happens and we assert the request the tool WOULD send.
"""
from __future__ import annotations

import json

import pytest

import fbmcp.graph as graph


@pytest.fixture
def rec(monkeypatch):
    """Record every _do_http call; return a canned Graph-ish response."""
    calls: list[dict] = []

    async def fake(method, url, *, params=None, data=None, files=None,
                   headers=None, content=None, timeout=120.0):
        calls.append(
            {"method": method, "url": url, "params": params, "data": data,
             "files": files, "headers": headers, "content": content}
        )
        return {"id": "c1", "post_id": "p1", "video_id": "v1",
                "upload_url": "https://rupload.facebook.com/x"}

    monkeypatch.setattr(graph, "_do_http", fake)
    return calls


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "TESTTOKEN")
    monkeypatch.setenv("FB_PAGE_ID", "PAGE1")
    monkeypatch.setenv("FB_IG_USER_ID", "IG1")
    monkeypatch.setenv("FB_GRAPH_VERSION", "v99.0")
    monkeypatch.delenv("FB_APP_SECRET", raising=False)
    monkeypatch.delenv("FB_APP_ID", raising=False)


# --------------------------------------------------------------------------- #
# GraphClient primitives
# --------------------------------------------------------------------------- #
def test_url_and_auth_params():
    gc = graph.GraphClient(token="T", page_id="P", version="v99.0")
    assert gc.url("P/feed") == "https://graph.facebook.com/v99.0/P/feed"
    assert gc.url("P/videos", video=True).startswith(
        "https://graph-video.facebook.com/v99.0/"
    )
    assert gc._auth({"a": 1})["access_token"] == "T"
    assert "appsecret_proof" not in gc._auth()


def test_appsecret_proof_is_hmac():
    import hashlib
    import hmac

    gc = graph.GraphClient(token="T", app_secret="SECRET")
    expect = hmac.new(b"SECRET", b"T", hashlib.sha256).hexdigest()
    assert gc._auth()["appsecret_proof"] == expect


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("FB_PAGE_ACCESS_TOKEN", raising=False)
    with pytest.raises(graph.GraphError):
        graph.graph_client()


# --------------------------------------------------------------------------- #
# Page publishing
# --------------------------------------------------------------------------- #
async def test_page_post(env, rec, get_tool):
    await get_tool("fb_page_post")(message="hi", link="http://x")
    c = rec[-1]
    assert c["method"] == "POST"
    assert c["url"] == "https://graph.facebook.com/v99.0/PAGE1/feed"
    assert c["data"]["message"] == "hi" and c["data"]["link"] == "http://x"
    assert c["params"]["access_token"] == "TESTTOKEN"


async def test_page_schedule_post(env, rec, get_tool):
    await get_tool("fb_page_schedule_post")(message="later", scheduled_publish_time=111)
    c = rec[-1]
    assert c["url"].endswith("/PAGE1/feed")
    assert c["data"]["published"] == "false"
    assert c["data"]["scheduled_publish_time"] == "111"


async def test_page_upload_photo_url(env, rec, get_tool):
    await get_tool("fb_page_upload_photo")(image_url="http://img", caption="cap")
    c = rec[-1]
    assert c["url"].endswith("/PAGE1/photos")
    assert c["data"]["url"] == "http://img" and c["data"]["caption"] == "cap"
    assert c["data"]["published"] == "true"


async def test_page_upload_photo_path(env, rec, get_tool, tmp_path):
    p = tmp_path / "i.jpg"
    p.write_bytes(b"JPEGDATA")
    await get_tool("fb_page_upload_photo")(image_path=str(p))
    c = rec[-1]
    assert c["files"]["source"][1] == b"JPEGDATA"


async def test_page_upload_photo_requires_arg(env, rec, get_tool):
    out = json.loads(await get_tool("fb_page_upload_photo")())
    assert "error" in out and rec == []


async def test_page_upload_video_uses_video_host(env, rec, get_tool):
    await get_tool("fb_page_upload_video")(video_url="http://v", title="t")
    c = rec[-1]
    assert c["url"].startswith("https://graph-video.facebook.com/")
    assert c["url"].endswith("/PAGE1/videos")
    assert c["data"]["file_url"] == "http://v"


async def test_page_upload_reel_three_phase(env, rec, get_tool):
    await get_tool("fb_page_upload_reel")(video_url="http://v", description="d")
    assert len(rec) == 3
    start, upload, finish = rec
    assert start["url"].endswith("/PAGE1/video_reels")
    assert start["data"]["upload_phase"] == "start"
    assert upload["url"] == "https://rupload.facebook.com/x"
    assert upload["headers"]["file_url"] == "http://v"
    assert upload["headers"]["Authorization"] == "OAuth TESTTOKEN"
    assert finish["params"]["upload_phase"] == "finish"
    assert finish["params"]["video_state"] == "PUBLISHED"
    assert finish["params"]["video_id"] == "v1"


async def test_page_upload_story_photo(env, rec, get_tool):
    await get_tool("fb_page_upload_story")(image_url="http://img")
    assert len(rec) == 2
    photo, story = rec
    assert photo["url"].endswith("/PAGE1/photos")
    assert photo["data"]["published"] == "false"
    assert story["url"].endswith("/PAGE1/photo_stories")
    assert story["data"]["photo_id"] == "c1"


# --------------------------------------------------------------------------- #
# Page reading + moderation
# --------------------------------------------------------------------------- #
async def test_page_read_posts(env, rec, get_tool):
    await get_tool("fb_page_read_posts")(limit=5)
    c = rec[-1]
    assert c["method"] == "GET" and c["url"].endswith("/PAGE1/feed")
    assert c["params"]["limit"] == 5 and "fields" in c["params"]


async def test_page_read_comments(env, rec, get_tool):
    await get_tool("fb_page_read_comments")(object_id="OBJ9")
    assert rec[-1]["url"].endswith("/OBJ9/comments")


@pytest.mark.parametrize(
    "action,expect_method,expect_suffix",
    [
        ("reply", "POST", "/C1/comments"),
        ("hide", "POST", "/C1"),
        ("delete", "DELETE", "/C1"),
        ("like", "POST", "/C1/likes"),
        ("unlike", "DELETE", "/C1/likes"),
    ],
)
async def test_page_moderate(env, rec, get_tool, action, expect_method, expect_suffix):
    await get_tool("fb_page_moderate")(action=action, comment_id="C1", message="yo")
    c = rec[-1]
    assert c["method"] == expect_method
    assert c["url"].endswith(expect_suffix)
    if action == "hide":
        assert c["data"]["is_hidden"] == "true"
    if action == "reply":
        assert c["data"]["message"] == "yo"


async def test_page_moderate_reply_needs_message(env, rec, get_tool):
    out = json.loads(await get_tool("fb_page_moderate")(action="reply", comment_id="C1"))
    assert "error" in out and rec == []


async def test_page_moderate_bad_action(env, rec, get_tool):
    out = json.loads(await get_tool("fb_page_moderate")(action="nuke", comment_id="C1"))
    assert "error" in out


async def test_page_insights(env, rec, get_tool):
    await get_tool("fb_page_insights")(metric="page_impressions", period="week")
    c = rec[-1]
    assert c["url"].endswith("/PAGE1/insights")
    assert c["params"]["metric"] == "page_impressions"
    assert c["params"]["period"] == "week"


async def test_page_message_send_api(env, rec, get_tool):
    await get_tool("fb_page_message")(recipient_id="U7", text="hello")
    c = rec[-1]
    assert c["url"].endswith("/PAGE1/messages")
    assert json.loads(c["data"]["recipient"]) == {"id": "U7"}
    assert json.loads(c["data"]["message"]) == {"text": "hello"}
    assert c["data"]["messaging_type"] == "RESPONSE"


# --------------------------------------------------------------------------- #
# Instagram Graph twins
# --------------------------------------------------------------------------- #
async def test_ig_publish_image(env, rec, get_tool):
    await get_tool("ig_graph_publish")(image_url="http://img", caption="c")
    assert len(rec) == 2
    container, publish = rec
    assert container["url"].endswith("/IG1/media")
    assert container["data"]["image_url"] == "http://img"
    assert publish["url"].endswith("/IG1/media_publish")
    assert publish["data"]["creation_id"] == "c1"


async def test_ig_publish_reels(env, rec, get_tool):
    await get_tool("ig_graph_publish")(video_url="http://v", media_type="REELS")
    container = rec[0]
    assert container["data"]["media_type"] == "REELS"
    assert container["data"]["video_url"] == "http://v"


async def test_ig_insights_account(env, rec, get_tool):
    await get_tool("ig_graph_insights")(metric="reach")
    assert rec[-1]["url"].endswith("/IG1/insights")
    assert rec[-1]["params"]["period"] == "day"


async def test_ig_insights_media(env, rec, get_tool):
    await get_tool("ig_graph_insights")(metric="reach", ig_media_id="MED5")
    assert rec[-1]["url"].endswith("/MED5/insights")
    assert "period" not in rec[-1]["params"]


async def test_ig_moderate_reply(env, rec, get_tool):
    await get_tool("ig_graph_moderate_comments")(action="reply", comment_id="X1", message="hi")
    assert rec[-1]["url"].endswith("/X1/replies")
    assert rec[-1]["data"]["message"] == "hi"


async def test_ig_moderate_hide(env, rec, get_tool):
    await get_tool("ig_graph_moderate_comments")(action="hide", comment_id="X1")
    assert rec[-1]["data"]["hide"] == "true"


async def test_token_info(env, rec, get_tool):
    await get_tool("fb_graph_token_info")()
    assert rec[-1]["url"].endswith("/me")


# --------------------------------------------------------------------------- #
# Error propagation from the HTTP layer
# --------------------------------------------------------------------------- #
async def test_graph_error_on_4xx(monkeypatch):
    class FakeResp:
        status_code = 400

        def json(self):
            return {"error": {"message": "bad"}}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr(graph.httpx, "AsyncClient", FakeClient)
    with pytest.raises(graph.GraphError):
        await graph._do_http("GET", "https://graph.facebook.com/v99.0/me")
