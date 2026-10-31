"""TikTok MCP — read-only, public-data wrapper over davidteather/TikTok-Api (v7.3.3).

PUBLIC SCRAPING ONLY. There is no login, no session.json, no QR, no password — by
design. This server can read public TikTok data (trending, a creator's public posts,
hashtags, a video's metadata/comments, user search) and **cannot** read your own feed,
your saved/favorites, your following, or any DM, and **cannot** post/like/follow.

It rides an *unofficial* API, so each call carries TikTok ToS + IP-block risk. Two env
knobs reduce bot-detection (both optional, both **never logged**):
  - TIKTOK_MS_TOKEN : an ms_token copied from a logged-in tiktok.com cookie (anti-bot help,
                      NOT authentication — it does not log you in or expose your account).
  - TIKTOK_PROXY    : a residential proxy URL (http://user:pass@host:port). REQUIRED on a
                      datacenter/cloud egress IP (TikTok returns empty/`EmptyResponseException`
                      almost immediately from datacenter IPs); not needed on a home IP.

Results are geo-localized to the egress IP (or proxy region). Each tool spins up a fresh
headless-Chromium TikTok session (robust over fast — a scraper session can go stale), then
closes it. Counts are clamped to [1, 50].
"""

from __future__ import annotations

import os
from typing import Any, Optional
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from TikTokApi import TikTokApi

try:  # exception surface differs across TikTokApi point releases — degrade gracefully
    from TikTokApi.exceptions import EmptyResponseException, InvalidResponseException
except Exception:  # pragma: no cover - defensive import

    class EmptyResponseException(Exception): ...

    class InvalidResponseException(Exception): ...


def _load_env() -> None:
    """Load KEY=VALUE pairs from a gitignored `.env` next to this file into the process
    environment (without overriding already-set vars). Lets the registered MCP pick up
    TIKTOK_MS_TOKEN / TIKTOK_PROXY / TIKTOK_BROWSER without baking the secret into the MCP
    registration in ~/.claude.json. Values are never logged."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if key and val:
                    os.environ.setdefault(key, val)
    except OSError:  # pragma: no cover - defensive
        pass


_load_env()

mcp = FastMCP("tiktok")

_MS_TOKEN = os.environ.get("TIKTOK_MS_TOKEN") or None
_PROXY = os.environ.get("TIKTOK_PROXY") or None
_BROWSER = os.environ.get("TIKTOK_BROWSER") or "chromium"  # chromium | webkit | firefox
_MAX_COUNT = 50


def _clamp(count: int) -> int:
    """Bound a requested item count to a sane, non-abusive range."""
    try:
        count = int(count)
    except (TypeError, ValueError):
        return 20
    return max(1, min(count, _MAX_COUNT))


def _proxies() -> Optional[list[dict[str, str]]]:
    """Translate TIKTOK_PROXY (a URL, possibly with embedded creds) into the Playwright
    ProxySettings shape TikTokApi expects. Credentials are split out of the server URL
    (Playwright rejects creds embedded in `server`). Returns None when no proxy is set."""
    if not _PROXY:
        return None
    u = urlparse(_PROXY)
    if not u.hostname:
        return None
    settings: dict[str, str] = {
        "server": f"{u.scheme or 'http'}://{u.hostname}:{u.port or 80}"
    }
    if u.username:
        settings["username"] = u.username
    if u.password:
        settings["password"] = u.password
    return [settings]


async def _open(api: TikTokApi) -> None:
    """Create a single headless TikTok session honoring the optional ms_token/proxy."""
    await api.create_sessions(
        num_sessions=1,
        headless=True,
        ms_tokens=[_MS_TOKEN] if _MS_TOKEN else None,
        proxies=_proxies(),
        sleep_after=3,
        browser=_BROWSER,
    )


def _g(d: Any, *keys: str, default: Any = None) -> Any:
    """Safe nested-get over dicts (the raw TikTok payloads are deeply nested and uneven)."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def _trim_video(raw: dict[str, Any]) -> dict[str, Any]:
    """Reduce a raw TikTok video object to the useful, stable fields."""
    author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    stats = raw.get("stats") or raw.get("statsV2") or {}
    music = raw.get("music") if isinstance(raw.get("music"), dict) else {}
    vid = raw.get("video") if isinstance(raw.get("video"), dict) else {}
    author_handle = author.get("uniqueId") or author.get("unique_id")
    vid_id = raw.get("id") or raw.get("aweme_id")
    out = {
        "id": vid_id,
        "desc": raw.get("desc"),
        "createTime": raw.get("createTime") or raw.get("create_time"),
        "author": {
            "uniqueId": author_handle,
            "nickname": author.get("nickname"),
            "id": author.get("id"),
            "verified": author.get("verified"),
        },
        "stats": {
            "playCount": stats.get("playCount") or stats.get("play_count"),
            "diggCount": stats.get("diggCount") or stats.get("digg_count"),
            "commentCount": stats.get("commentCount") or stats.get("comment_count"),
            "shareCount": stats.get("shareCount") or stats.get("share_count"),
            "collectCount": stats.get("collectCount") or stats.get("collect_count"),
        },
        "music": {"title": music.get("title"), "authorName": music.get("authorName")},
        "durationSec": vid.get("duration"),
    }
    if vid_id and author_handle:
        out["url"] = f"https://www.tiktok.com/@{author_handle}/video/{vid_id}"
    return out


def _trim_user(raw: dict[str, Any]) -> dict[str, Any]:
    """Reduce a raw TikTok user object to identity + counts, tolerating the several
    shapes the API returns (search item vs userInfo vs flat user)."""
    user = (
        _g(raw, "userInfo", "user")
        or _g(raw, "user_info", "user")
        or raw.get("user")
        or raw
    )
    stats = (
        _g(raw, "userInfo", "stats")
        or _g(raw, "user_info", "stats")
        or raw.get("stats")
        or {}
    )
    return {
        "uniqueId": user.get("uniqueId") or user.get("unique_id"),
        "nickname": user.get("nickname"),
        "id": user.get("id"),
        "secUid": user.get("secUid") or user.get("sec_uid"),
        "verified": user.get("verified"),
        "signature": user.get("signature"),
        "privateAccount": user.get("privateAccount"),
        "stats": {
            "followerCount": stats.get("followerCount") or stats.get("follower_count"),
            "followingCount": stats.get("followingCount")
            or stats.get("following_count"),
            "heartCount": stats.get("heartCount")
            or stats.get("heart")
            or stats.get("heart_count"),
            "videoCount": stats.get("videoCount") or stats.get("video_count"),
        },
    }


def _trim_comment(raw: dict[str, Any]) -> dict[str, Any]:
    """Reduce a raw TikTok comment object to text + author + likes."""
    user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    return {
        "text": raw.get("text"),
        "likeCount": raw.get("digg_count") or raw.get("diggCount"),
        "replyCount": raw.get("reply_comment_total") or raw.get("replyCommentTotal"),
        "createTime": raw.get("create_time") or raw.get("createTime"),
        "author": {
            "uniqueId": user.get("unique_id") or user.get("uniqueId"),
            "nickname": user.get("nickname"),
        },
    }


def _err(exc: Exception) -> dict[str, Any]:
    """Map an exception to a structured, actionable error (no secrets in the message)."""
    name = type(exc).__name__
    hint = (
        "TikTok returned empty/blocked — likely bot-detection. Set TIKTOK_MS_TOKEN "
        "(from a logged-in tiktok.com cookie) and/or TIKTOK_PROXY (a residential proxy; "
        "required on datacenter IPs), then retry. The target may also be private/removed."
    )
    return {"error": name, "detail": str(exc)[:300], "hint": hint}


@mcp.tool()
async def tiktok_trending(count: int = 20) -> dict[str, Any]:
    """Public TikTok trending feed (geo-localized to the egress IP/proxy region).
    Read-only. count is clamped to [1, 50]."""
    count = _clamp(count)
    try:
        async with TikTokApi() as api:
            await _open(api)
            videos = [
                _trim_video(v.as_dict) async for v in api.trending.videos(count=count)
            ]
        return {"count": len(videos), "videos": videos}
    except Exception as exc:  # noqa: BLE001 - surface a structured error, never crash the tool
        return _err(exc)


@mcp.tool()
async def tiktok_user_info(username: str) -> dict[str, Any]:
    """Public profile + stats for a TikTok creator by @username (without the @).
    Read-only."""
    if not username or not username.strip():
        return {"error": "ValueError", "detail": "username is required"}
    username = username.lstrip("@").strip()
    try:
        async with TikTokApi() as api:
            await _open(api)
            info = await api.user(username=username).info()
        return {"user": _trim_user(info)}
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def tiktok_user_posts(username: str, count: int = 20) -> dict[str, Any]:
    """A creator's recent PUBLIC posts by @username (without the @). Read-only.
    count is clamped to [1, 50]."""
    if not username or not username.strip():
        return {"error": "ValueError", "detail": "username is required"}
    username = username.lstrip("@").strip()
    count = _clamp(count)
    try:
        async with TikTokApi() as api:
            await _open(api)
            videos = [
                _trim_video(v.as_dict)
                async for v in api.user(username=username).videos(count=count)
            ]
        return {"username": username, "count": len(videos), "videos": videos}
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def tiktok_user_liked(username: str, count: int = 20) -> dict[str, Any]:
    """A creator's PUBLIC likes by @username — ONLY works if that user made their liked
    videos public (most accounts keep them private → expect empty). Read-only. Clamp [1,50]."""
    if not username or not username.strip():
        return {"error": "ValueError", "detail": "username is required"}
    username = username.lstrip("@").strip()
    count = _clamp(count)
    try:
        async with TikTokApi() as api:
            await _open(api)
            videos = [
                _trim_video(v.as_dict)
                async for v in api.user(username=username).liked(count=count)
            ]
        note = None if videos else "empty — the account likely keeps its likes private"
        return {
            "username": username,
            "count": len(videos),
            "videos": videos,
            "note": note,
        }
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def tiktok_hashtag(tag: str, count: int = 20) -> dict[str, Any]:
    """Recent PUBLIC videos for a hashtag (without the #). Read-only. Clamp [1, 50]."""
    if not tag or not tag.strip():
        return {"error": "ValueError", "detail": "tag is required"}
    tag = tag.lstrip("#").strip()
    count = _clamp(count)
    try:
        async with TikTokApi() as api:
            await _open(api)
            videos = [
                _trim_video(v.as_dict)
                async for v in api.hashtag(name=tag).videos(count=count)
            ]
        return {"tag": tag, "count": len(videos), "videos": videos}
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def tiktok_video_details(url_or_id: str) -> dict[str, Any]:
    """Metadata for one public TikTok video — pass a full video URL (preferred) or a
    numeric video id. Read-only."""
    if not url_or_id or not url_or_id.strip():
        return {"error": "ValueError", "detail": "url_or_id is required"}
    url_or_id = url_or_id.strip()
    is_url = url_or_id.startswith("http")
    try:
        async with TikTokApi() as api:
            await _open(api)
            video = api.video(url=url_or_id) if is_url else api.video(id=url_or_id)
            info = await video.info()
        return {"video": _trim_video(info)}
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def tiktok_comments(url_or_id: str, count: int = 20) -> dict[str, Any]:
    """Top-level comments on a public TikTok video (URL preferred, or numeric id).
    Read-only. count is clamped to [1, 50]."""
    if not url_or_id or not url_or_id.strip():
        return {"error": "ValueError", "detail": "url_or_id is required"}
    url_or_id = url_or_id.strip()
    is_url = url_or_id.startswith("http")
    count = _clamp(count)
    try:
        async with TikTokApi() as api:
            await _open(api)
            video = api.video(url=url_or_id) if is_url else api.video(id=url_or_id)
            comments = [
                _trim_comment(c.as_dict) async for c in video.comments(count=count)
            ]
        return {"count": len(comments), "comments": comments}
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def tiktok_related_videos(url_or_id: str, count: int = 20) -> dict[str, Any]:
    """Videos TikTok relates to a given public video (URL preferred, or numeric id).
    Read-only. count is clamped to [1, 50]."""
    if not url_or_id or not url_or_id.strip():
        return {"error": "ValueError", "detail": "url_or_id is required"}
    url_or_id = url_or_id.strip()
    is_url = url_or_id.startswith("http")
    count = _clamp(count)
    try:
        async with TikTokApi() as api:
            await _open(api)
            video = api.video(url=url_or_id) if is_url else api.video(id=url_or_id)
            videos = [
                _trim_video(v.as_dict) async for v in video.related_videos(count=count)
            ]
        return {"count": len(videos), "videos": videos}
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def tiktok_search_users(query: str, count: int = 10) -> dict[str, Any]:
    """Search TikTok for public user accounts by name/keyword. Read-only. Clamp [1, 50].
    NOTE: TikTok-Api 7.x exposes user search only — there is no generic video search;
    use tiktok_hashtag / tiktok_trending for video discovery."""
    if not query or not query.strip():
        return {"error": "ValueError", "detail": "query is required"}
    query = query.strip()
    count = _clamp(count)
    try:
        async with TikTokApi() as api:
            await _open(api)
            users = [
                _trim_user(u.as_dict)
                async for u in api.search.users(query, count=count)
            ]
        return {"query": query, "count": len(users), "users": users}
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


if __name__ == "__main__":
    mcp.run()
