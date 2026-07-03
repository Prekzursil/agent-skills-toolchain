"""T1 - Facebook Graph API tools (Page + professional Instagram).

ToS-clean and token-based: managing your OWN Page and linked professional
Instagram account needs NO app review. Auth via environment:

  FB_PAGE_ACCESS_TOKEN   (required)  long-lived Page access token
  FB_PAGE_ID             (Page tools) numeric Page id
  FB_IG_USER_ID          (IG tools)   IG professional account id linked to Page
  FB_APP_SECRET          (optional)   enables appsecret_proof hardening
  FB_APP_ID              (optional)   used by fb_graph_token_info (debug_token)
  FB_GRAPH_VERSION       (optional)   default v23.0 (v25.0 is current as of 2026)

Nothing here uses cookies - it is entirely the official Graph API, so it never
touches the E2EE / private-API surface.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Optional

import httpx

from mcp.server.fastmcp import FastMCP

from .common import dump

GRAPH_HOST = "https://graph.facebook.com"
GRAPH_VIDEO_HOST = "https://graph-video.facebook.com"
DEFAULT_VERSION = "v23.0"


class GraphError(RuntimeError):
    """Raised for missing config or a >=400 Graph API response."""


# --------------------------------------------------------------------------- #
# HTTP seam (single choke point - mocked in tests)
# --------------------------------------------------------------------------- #
async def _do_http(
    method: str,
    url: str,
    *,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    files: Optional[dict] = None,
    headers: Optional[dict] = None,
    content: Optional[bytes] = None,
    timeout: float = 120.0,
) -> dict:
    """Perform one HTTP request and return parsed JSON. The only network call."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(
            method,
            url,
            params=params,
            data=data,
            files=files,
            headers=headers,
            content=content,
        )
    try:
        body: Any = resp.json()
    except Exception:
        body = {"raw": resp.text}
    if resp.status_code >= 400:
        raise GraphError(f"Graph API {resp.status_code}: {body}")
    return body if isinstance(body, dict) else {"data": body}


class GraphClient:
    """Thin typed wrapper over the Graph API with auth-param injection."""

    def __init__(  # nosec B107 - token/app_secret are optional, sourced from env (not hardcoded)
        self,
        token: str,
        page_id: str = "",
        ig_user_id: str = "",
        app_secret: str = "",
        app_id: str = "",
        version: str = DEFAULT_VERSION,
        host: str = GRAPH_HOST,
        video_host: str = GRAPH_VIDEO_HOST,
    ) -> None:
        self.token = token
        self.page_id = page_id
        self.ig_user_id = ig_user_id
        self.app_secret = app_secret
        self.app_id = app_id
        self.version = version
        self.host = host
        self.video_host = video_host

    def _proof(self) -> Optional[str]:
        if not self.app_secret:
            return None
        return hmac.new(
            self.app_secret.encode(), self.token.encode(), hashlib.sha256
        ).hexdigest()

    def _auth(self, extra: Optional[dict] = None) -> dict:
        p = {k: v for k, v in (extra or {}).items() if v is not None}
        p["access_token"] = self.token
        proof = self._proof()
        if proof:
            p["appsecret_proof"] = proof
        return p

    def url(self, path: str, *, video: bool = False) -> str:
        host = self.video_host if video else self.host
        return f"{host}/{self.version}/{str(path).lstrip('/')}"

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        return await _do_http("GET", self.url(path), params=self._auth(params))

    async def post(
        self,
        path: str,
        data: Optional[dict] = None,
        files: Optional[dict] = None,
        *,
        video: bool = False,
        params: Optional[dict] = None,
    ) -> dict:
        clean = {k: v for k, v in (data or {}).items() if v is not None}
        return await _do_http(
            "POST",
            self.url(path, video=video),
            params=self._auth(params),
            data=clean or None,
            files=files,
        )

    async def delete(self, path: str, params: Optional[dict] = None) -> dict:
        return await _do_http("DELETE", self.url(path), params=self._auth(params))


# --------------------------------------------------------------------------- #
# Config factory + guards
# --------------------------------------------------------------------------- #
def graph_client() -> GraphClient:
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not token:
        raise GraphError(
            "FB_PAGE_ACCESS_TOKEN is not set. Provide a long-lived Page access "
            "token (see README 'T1 setup')."
        )
    return GraphClient(
        token=token,
        page_id=os.environ.get("FB_PAGE_ID", ""),
        ig_user_id=os.environ.get("FB_IG_USER_ID", ""),
        app_secret=os.environ.get("FB_APP_SECRET", ""),
        app_id=os.environ.get("FB_APP_ID", ""),
        version=os.environ.get("FB_GRAPH_VERSION", DEFAULT_VERSION),
    )


def _page(gc: GraphClient) -> str:
    if not gc.page_id:
        raise GraphError("FB_PAGE_ID is not set.")
    return gc.page_id


def _ig(gc: GraphClient) -> str:
    if not gc.ig_user_id:
        raise GraphError(
            "FB_IG_USER_ID is not set (the IG professional account id linked to the Page)."
        )
    return gc.ig_user_id


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
# Multi-phase upload helpers (reels / stories)
# --------------------------------------------------------------------------- #
async def _resumable_video(
    gc: GraphClient,
    page_id: str,
    edge: str,
    description: Optional[str],
    video_url: Optional[str],
    video_path: Optional[str],
) -> dict:
    """3-phase Reels/Stories video upload: start -> upload -> finish/publish."""
    if not video_url and not video_path:
        raise GraphError("provide video_url or video_path")
    start = await gc.post(f"{page_id}/{edge}", data={"upload_phase": "start"})
    video_id = start.get("video_id")
    upload_url = start.get("upload_url")
    if not upload_url:
        raise GraphError(f"start phase returned no upload_url: {start}")
    headers = {"Authorization": f"OAuth {gc.token}"}
    if video_url:
        headers["file_url"] = video_url
        await _do_http("POST", upload_url, headers=headers)
    else:
        blob = _read_bytes(video_path)  # type: ignore[arg-type]
        headers["offset"] = "0"
        headers["file_size"] = str(len(blob))
        await _do_http("POST", upload_url, headers=headers, content=blob)
    finish = await gc.post(
        f"{page_id}/{edge}",
        params={
            "video_id": video_id,
            "upload_phase": "finish",
            "video_state": "PUBLISHED",
            "description": description or "",
        },
    )
    return {"video_id": video_id, "start": start, "finish": finish}


# --------------------------------------------------------------------------- #
# Tool registration
# --------------------------------------------------------------------------- #
def register_graph_tools(mcp: FastMCP) -> None:
    """Register T1 Graph API tools (Page + professional Instagram)."""

    # -- diagnostics ------------------------------------------------------- #
    @mcp.tool()
    async def fb_graph_token_info() -> str:
        """Verify the configured Page token: returns /me plus (if FB_APP_ID and
        FB_APP_SECRET are set) a debug_token scope/expiry report. Use this to
        confirm T1 setup before posting."""
        gc = graph_client()
        out: dict = {"version": gc.version}
        out["me"] = await gc.get(
            "me", {"fields": "id,name,category,tasks"}
        )
        if gc.app_id and gc.app_secret:
            out["debug_token"] = await gc.get(
                "debug_token",
                {"input_token": gc.token, "access_token": f"{gc.app_id}|{gc.app_secret}"},
            )
        return dump(out)

    # -- Page: publishing -------------------------------------------------- #
    @mcp.tool()
    async def fb_page_post(message: str, link: Optional[str] = None) -> str:
        """Publish a text (and optional link) post to your Page feed. Returns the
        new post id. Needs pages_manage_posts."""
        gc = graph_client()
        res = await gc.post(f"{_page(gc)}/feed", data={"message": message, "link": link})
        return dump(res)

    @mcp.tool()
    async def fb_page_schedule_post(
        message: str, scheduled_publish_time: int, link: Optional[str] = None
    ) -> str:
        """Schedule a Page feed post. scheduled_publish_time is a UNIX timestamp
        between 10 minutes and 75 days out. Needs pages_manage_posts."""
        gc = graph_client()
        res = await gc.post(
            f"{_page(gc)}/feed",
            data={
                "message": message,
                "link": link,
                "published": "false",
                "scheduled_publish_time": str(scheduled_publish_time),
            },
        )
        return dump(res)

    @mcp.tool()
    async def fb_page_upload_photo(
        image_url: Optional[str] = None,
        image_path: Optional[str] = None,
        caption: Optional[str] = None,
        published: bool = True,
    ) -> str:
        """Upload a photo to the Page (image_url OR image_path). published=False
        stages it (e.g. for a story). Needs pages_manage_posts."""
        gc = graph_client()
        page = _page(gc)
        pub = "true" if published else "false"
        if image_url:
            res = await gc.post(
                f"{page}/photos",
                data={"url": image_url, "caption": caption, "published": pub},
            )
        elif image_path:
            res = await gc.post(
                f"{page}/photos",
                data={"caption": caption, "published": pub},
                files={"source": ("upload", _read_bytes(image_path))},
            )
        else:
            return dump({"error": "provide image_url or image_path"})
        return dump(res)

    @mcp.tool()
    async def fb_page_upload_video(
        video_url: Optional[str] = None,
        video_path: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Upload a standard (non-Reel) video to the Page feed (video_url OR
        video_path). Needs pages_manage_posts."""
        gc = graph_client()
        page = _page(gc)
        if video_url:
            res = await gc.post(
                f"{page}/videos",
                data={"file_url": video_url, "title": title, "description": description},
                video=True,
            )
        elif video_path:
            res = await gc.post(
                f"{page}/videos",
                data={"title": title, "description": description},
                files={"source": ("upload", _read_bytes(video_path))},
                video=True,
            )
        else:
            return dump({"error": "provide video_url or video_path"})
        return dump(res)

    @mcp.tool()
    async def fb_page_upload_reel(
        video_url: Optional[str] = None,
        video_path: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """Publish a Facebook Reel to the Page (3-phase upload). Provide video_url
        OR video_path. Needs pages_manage_posts."""
        gc = graph_client()
        res = await _resumable_video(
            gc, _page(gc), "video_reels", description, video_url, video_path
        )
        return dump(res)

    @mcp.tool()
    async def fb_page_upload_story(
        image_url: Optional[str] = None,
        image_path: Optional[str] = None,
        video_url: Optional[str] = None,
        video_path: Optional[str] = None,
    ) -> str:
        """Publish a Page Story. Photo story: staged photo -> /photo_stories.
        Video story: 3-phase -> /video_stories. Needs pages_manage_posts."""
        gc = graph_client()
        page = _page(gc)
        if video_url or video_path:
            res = await _resumable_video(
                gc, page, "video_stories", None, video_url, video_path
            )
            return dump(res)
        if image_url:
            photo = await gc.post(
                f"{page}/photos", data={"url": image_url, "published": "false"}
            )
        elif image_path:
            photo = await gc.post(
                f"{page}/photos",
                data={"published": "false"},
                files={"source": ("upload", _read_bytes(image_path))},
            )
        else:
            return dump({"error": "provide an image_* or video_* argument"})
        res = await gc.post(
            f"{page}/photo_stories", data={"photo_id": photo.get("id")}
        )
        return dump({"photo": photo, "story": res})

    # -- Page: reading + moderation --------------------------------------- #
    @mcp.tool()
    async def fb_page_read_posts(limit: int = 25) -> str:
        """Read recent posts from your Page feed. Needs pages_read_engagement."""
        gc = graph_client()
        res = await gc.get(
            f"{_page(gc)}/feed",
            {
                "limit": limit,
                "fields": "id,message,story,created_time,permalink_url,"
                "shares,likes.summary(true),comments.summary(true)",
            },
        )
        return dump(res)

    @mcp.tool()
    async def fb_page_read_comments(object_id: str, limit: int = 25) -> str:
        """Read comments on a post/photo/video by object id. Needs
        pages_read_engagement."""
        gc = graph_client()
        res = await gc.get(
            f"{object_id}/comments",
            {
                "limit": limit,
                "fields": "id,message,from,created_time,like_count,comment_count",
            },
        )
        return dump(res)

    @mcp.tool()
    async def fb_page_moderate(
        action: str, comment_id: str, message: Optional[str] = None
    ) -> str:
        """Moderate a Page comment. action = reply | hide | unhide | delete |
        like | unlike. 'reply' requires `message`. Needs
        pages_manage_engagement."""
        gc = graph_client()
        act = action.lower().strip()
        if act == "reply":
            if not message:
                return dump({"error": "reply requires message"})
            res = await gc.post(f"{comment_id}/comments", data={"message": message})
        elif act == "hide":
            res = await gc.post(comment_id, data={"is_hidden": "true"})
        elif act == "unhide":
            res = await gc.post(comment_id, data={"is_hidden": "false"})
        elif act == "delete":
            res = await gc.delete(comment_id)
        elif act == "like":
            res = await gc.post(f"{comment_id}/likes")
        elif act == "unlike":
            res = await gc.delete(f"{comment_id}/likes")
        else:
            return dump(
                {"error": f"unknown action '{action}'",
                 "valid": ["reply", "hide", "unhide", "delete", "like", "unlike"]}
            )
        return dump({"action": act, "comment_id": comment_id, "result": res})

    @mcp.tool()
    async def fb_page_insights(
        metric: str, period: str = "day", since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> str:
        """Read Page insights. metric = comma-separated metric names (e.g.
        'page_impressions,page_post_engagements'); period = day|week|days_28.
        Needs read_insights."""
        gc = graph_client()
        res = await gc.get(
            f"{_page(gc)}/insights",
            {"metric": metric, "period": period, "since": since, "until": until},
        )
        return dump(res)

    @mcp.tool()
    async def fb_page_message(recipient_id: str, text: str) -> str:
        """Send a Messenger message FROM the Page to a user (Send API). Only valid
        within 24h of a user-initiated message (messaging_type=RESPONSE). Needs
        pages_messaging."""
        gc = graph_client()
        import json as _json

        res = await gc.post(
            f"{_page(gc)}/messages",
            data={
                "recipient": _json.dumps({"id": recipient_id}),
                "message": _json.dumps({"text": text}),
                "messaging_type": "RESPONSE",
            },
        )
        return dump(res)

    # -- Instagram Graph twins -------------------------------------------- #
    @mcp.tool()
    async def ig_graph_publish(
        caption: Optional[str] = None,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        media_type: str = "IMAGE",
    ) -> str:
        """Publish to the linked professional Instagram account (2-phase: create
        container -> publish). media_type = IMAGE | REELS. image_url/video_url
        MUST be publicly reachable (IG Graph cannot take local files). Needs
        instagram_content_publish."""
        gc = graph_client()
        ig = _ig(gc)
        mt = media_type.upper().strip()
        if mt == "REELS" or video_url:
            if not video_url:
                return dump({"error": "REELS requires video_url"})
            container = await gc.post(
                f"{ig}/media",
                data={"media_type": "REELS", "video_url": video_url, "caption": caption},
            )
        else:
            if not image_url:
                return dump({"error": "IMAGE requires image_url"})
            container = await gc.post(
                f"{ig}/media", data={"image_url": image_url, "caption": caption}
            )
        creation_id = container.get("id")
        published = await gc.post(
            f"{ig}/media_publish", data={"creation_id": creation_id}
        )
        return dump({"container": container, "published": published})

    @mcp.tool()
    async def ig_graph_insights(
        metric: str, period: str = "day", ig_media_id: Optional[str] = None
    ) -> str:
        """Read Instagram insights. If ig_media_id is given, reads media-level
        insights; otherwise account-level for FB_IG_USER_ID. metric =
        comma-separated. Needs instagram_manage_insights."""
        gc = graph_client()
        target = ig_media_id or _ig(gc)
        params: dict = {"metric": metric}
        if not ig_media_id:
            params["period"] = period
        res = await gc.get(f"{target}/insights", params)
        return dump(res)

    @mcp.tool()
    async def ig_graph_moderate_comments(
        action: str, comment_id: str, message: Optional[str] = None
    ) -> str:
        """Moderate an Instagram comment. action = reply | hide | unhide | delete.
        'reply' requires `message`. Needs instagram_manage_comments."""
        gc = graph_client()
        act = action.lower().strip()
        if act == "reply":
            if not message:
                return dump({"error": "reply requires message"})
            res = await gc.post(f"{comment_id}/replies", data={"message": message})
        elif act == "hide":
            res = await gc.post(comment_id, data={"hide": "true"})
        elif act == "unhide":
            res = await gc.post(comment_id, data={"hide": "false"})
        elif act == "delete":
            res = await gc.delete(comment_id)
        else:
            return dump(
                {"error": f"unknown action '{action}'",
                 "valid": ["reply", "hide", "unhide", "delete"]}
            )
        return dump({"action": act, "comment_id": comment_id, "result": res})
