#!/usr/bin/env python3
"""linkedin-mcp core -- pure LinkedIn REST logic (no MCP dep, stdlib-only HTTP).

Scoped DELIBERATELY to LinkedIn's **Open Permissions (Consumer)** surface -- the
only products a self-serve personal developer app can enable without LinkedIn
review (https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access):

    Sign In with LinkedIn using OpenID Connect -> openid, profile, email
    Share on LinkedIn                          -> w_member_social

Everything gated behind Marketing / Community Management / Sales Navigator /
Talent / Compliance is intentionally NOT implemented -- a tool that always 403s
is worse than no tool. See README.md "Deliberately NOT built".

Credentials come from the environment ONLY (never a committed file, never argv,
never a log line):

    LINKEDIN_ACCESS_TOKEN   3-legged member token (the one thing most tools need)
    LINKEDIN_CLIENT_ID      app Client ID    (OAuth URL / code exchange / introspect)
    LINKEDIN_CLIENT_SECRET  app Client Secret(code exchange / introspect only)
    LINKEDIN_REDIRECT_URI   default redirect URL for the 3-legged flow

Every network call goes through the single ``request_json`` seam so the whole
surface is unit-testable without a token and without the network. Missing
credentials raise ``LinkedInError`` with an actionable message (pointing at
SETUP.md), never a stack trace and never a partial-credential leak.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# --- endpoints (all public, documented) ------------------------------------- #
API_BASE = "https://api.linkedin.com"
OAUTH_BASE = "https://www.linkedin.com/oauth/v2"

AUTHORIZATION_URL = f"{OAUTH_BASE}/authorization"
ACCESS_TOKEN_URL = f"{OAUTH_BASE}/accessToken"
INTROSPECT_URL = f"{OAUTH_BASE}/introspectToken"
USERINFO_URL = f"{API_BASE}/v2/userinfo"
UGC_POSTS_URL = f"{API_BASE}/v2/ugcPosts"
REGISTER_UPLOAD_URL = f"{API_BASE}/v2/assets?action=registerUpload"
SOCIAL_ACTIONS_URL = f"{API_BASE}/v2/socialActions"

# Rest.li 2.0 is required on every /v2 call (Share on LinkedIn docs).
RESTLI_HEADER = {"X-Restli-Protocol-Version": "2.0.0"}

TIMEOUT = 30.0
UPLOAD_TIMEOUT = 300.0  # binary media upload; deliberately generous

# The four scopes a self-serve app can actually be granted.
OPEN_SCOPES = ("openid", "profile", "email", "w_member_social")
DEFAULT_SCOPES = "openid profile email w_member_social"

VISIBILITIES = ("PUBLIC", "CONNECTIONS")
MEDIA_CATEGORIES = ("NONE", "ARTICLE", "IMAGE")

# Client-side guard only -- LinkedIn does not publish a commentary limit in the
# Share on LinkedIn reference, so this is a sanity bound, not an API contract.
MAX_COMMENTARY_LEN = 3000
MAX_COMMENT_LEN = 1250

_ENV_TOKEN = "LINKEDIN_ACCESS_TOKEN"
_ENV_CLIENT_ID = "LINKEDIN_CLIENT_ID"
_ENV_CLIENT_SECRET = "LINKEDIN_CLIENT_SECRET"
_ENV_REDIRECT = "LINKEDIN_REDIRECT_URI"

_SETUP_HINT = "see tools/mcp/linkedin-mcp/SETUP.md for the developer-portal click-path"


class LinkedInError(ValueError):
    """Invalid input, missing credential, or an unrecoverable API failure."""


# --- credentials (env-only, dependency-injectable) -------------------------- #
def _env(environ: dict[str, str] | None) -> dict[str, str]:
    return dict(os.environ) if environ is None else environ


def _need(environ: dict[str, str] | None, name: str, why: str) -> str:
    """Read one required credential or raise an actionable LinkedInError.

    The VALUE is never echoed -- only the variable name and what it unlocks.
    """
    value = (_env(environ).get(name) or "").strip()
    if not value:
        raise LinkedInError(
            f"{name} is not set -- required to {why}. Export it in the MCP "
            f"server's environment ({_SETUP_HINT})."
        )
    return value


def access_token(environ: dict[str, str] | None = None) -> str:
    """The 3-legged member access token (LINKEDIN_ACCESS_TOKEN)."""
    return _need(environ, _ENV_TOKEN, "call the LinkedIn API on your behalf")


def client_id(environ: dict[str, str] | None = None) -> str:
    return _need(environ, _ENV_CLIENT_ID, "identify your LinkedIn app")


def client_secret(environ: dict[str, str] | None = None) -> str:
    return _need(environ, _ENV_CLIENT_SECRET, "authenticate your LinkedIn app")


def credential_presence(environ: dict[str, str] | None = None) -> dict[str, bool]:
    """Which credentials are PRESENT. Booleans only -- never the values."""
    env = _env(environ)
    return {
        name: bool((env.get(name) or "").strip())
        for name in (_ENV_TOKEN, _ENV_CLIENT_ID, _ENV_CLIENT_SECRET, _ENV_REDIRECT)
    }


# --- validation at the boundary --------------------------------------------- #
def _text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LinkedInError(f"{field} must be a non-empty string")
    if "\x00" in value:
        raise LinkedInError(f"{field} contains a NUL byte")
    if len(value) > limit:
        raise LinkedInError(f"{field} too long ({len(value)} > {limit} chars)")
    return value


def _visibility(value: str) -> str:
    if value not in VISIBILITIES:
        raise LinkedInError(
            f"visibility must be one of {'/'.join(VISIBILITIES)}, got {value!r}"
        )
    return value


def _https_url(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LinkedInError(f"{field} must be a non-empty string")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise LinkedInError(f"{field} must be an absolute http(s) URL, got {value!r}")
    return value


def _urn(value: Any, field: str, expect: tuple[str, ...] = ()) -> str:
    """Validate a LinkedIn URN and (optionally) constrain its entity type."""
    if not isinstance(value, str) or not value.startswith("urn:li:"):
        raise LinkedInError(
            f"{field} must be a LinkedIn URN ('urn:li:...'), got {value!r}"
        )
    parts = value.split(":")
    if len(parts) < 4 or not parts[3]:
        raise LinkedInError(f"{field} is not a well-formed URN: {value!r}")
    if expect and parts[2] not in expect:
        raise LinkedInError(
            f"{field} must be one of {'/'.join(expect)} URNs, got 'urn:li:{parts[2]}:...'"
        )
    return value


def person_urn(sub: str) -> str:
    """Build the Person URN the UGC API needs from an OIDC ``sub`` claim."""
    if not isinstance(sub, str) or not sub.strip():
        raise LinkedInError(
            "userinfo response has no 'sub' claim to build a Person URN"
        )
    return f"urn:li:person:{sub.strip()}"


def encode_urn(urn: str) -> str:
    """Percent-encode a URN for use as a REST path segment."""
    return urllib.parse.quote(urn, safe="")


# --- the single network seam (tests monkeypatch THIS) ----------------------- #
def _decode(raw: bytes) -> Any:
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def request_json(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: Any = None,
    timeout: float = TIMEOUT,
) -> tuple[int, Any, dict[str, str]]:
    """Issue one HTTP request -> ``(status, parsed_body, response_headers)``.

    Network failures return status ``0`` with an ``{"error": ...}`` body so every
    caller branches on status instead of catching exceptions. HTTP 4xx/5xx come
    back with their real status and LinkedIn's parsed error body.
    """
    data: bytes | None
    if body is None:
        data = None
    elif isinstance(body, (bytes, bytearray)):
        data = bytes(body)
    elif isinstance(body, str):
        data = body.encode("utf-8")
    else:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        url, data=data, headers=headers or {}, method=method.upper()
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, _decode(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, _decode(exc.read()), dict(exc.headers or {})
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, {"error": f"{method.upper()} {url} failed: {exc}"}, {}


def _auth_headers(token: str, json_body: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}", **RESTLI_HEADER}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _fail(status: int, payload: Any, action: str, gated_scope: str = "") -> dict:
    """Turn a non-2xx LinkedIn response into a structured, actionable failure.

    LinkedIn's error body is ``{"message", "serviceErrorCode", "status"}``
    (https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/error-handling).
    401/403 get a hint naming the product the caller is probably missing;
    ``gated_scope`` names a PARTNER-ONLY scope for surfaces known to be gated.
    """
    message = ""
    service_code = None
    if isinstance(payload, dict):
        message = str(payload.get("message") or payload.get("error") or "")
        service_code = payload.get("serviceErrorCode")
    elif payload:
        message = str(payload)[:400]

    hint = ""
    if status == 0:
        hint = "network error -- LinkedIn was not reached; check connectivity."
    elif status == 401:
        hint = (
            "the access token is missing, invalid, expired or revoked. LinkedIn "
            f"member tokens last 60 days -- regenerate one ({_SETUP_HINT})."
        )
    elif status == 403 and gated_scope:
        hint = (
            f"this surface requires the '{gated_scope}' scope, which is "
            "PARTNER-GATED -- a self-serve personal app cannot be granted it. "
            "This 403 is expected; see the README tool matrix."
        )
    elif status == 403:
        hint = (
            "the token lacks the required permission. Add the product that grants "
            "it on the Products tab of your app, then regenerate the token "
            f"(scopes are fixed at token-issue time; {_SETUP_HINT})."
        )
    elif status == 429:
        hint = (
            "rate limited. Share on LinkedIn allows 150 member requests per day "
            "(UTC) per app; wait for the daily reset."
        )
    return {
        "ok": False,
        "action": action,
        "status": status,
        "error": message or f"{action} failed with HTTP {status}",
        "serviceErrorCode": service_code,
        "hint": hint,
    }


# --- OAuth: local URL build + code exchange + introspection ------------------ #
def build_authorization_url(
    scopes: str = DEFAULT_SCOPES,
    redirect_uri: str = "",
    state: str = "",
    environ: dict[str, str] | None = None,
) -> dict:
    """Build the 3-legged authorization URL to open in a browser. NO network.

    Only ``openid``/``profile``/``email``/``w_member_social`` are self-serve; any
    other scope is rejected here rather than failing later at LinkedIn with an
    opaque "invalid scope".
    """
    requested = [s for s in scopes.replace(",", " ").split() if s]
    if not requested:
        raise LinkedInError("scopes must name at least one permission")
    unknown = [s for s in requested if s not in OPEN_SCOPES]
    if unknown:
        raise LinkedInError(
            f"scope(s) {', '.join(unknown)} are not self-serve. A personal app can "
            f"only be granted: {', '.join(OPEN_SCOPES)}. Everything else "
            f"(r_/w_organization_*, *_social_feed, r_ads, r_compliance, ...) needs "
            f"LinkedIn partner approval."
        )
    env = _env(environ)
    redirect = redirect_uri or (env.get(_ENV_REDIRECT) or "").strip()
    if not redirect:
        raise LinkedInError(
            f"redirect_uri is required -- pass it or set {_ENV_REDIRECT}. It must "
            f"exactly match a URL listed under 'Authorized redirect URLs for your "
            f"app' on the app's Auth tab."
        )
    params = {
        "response_type": "code",
        "client_id": client_id(environ),
        "redirect_uri": _https_url(redirect, "redirect_uri"),
        "scope": " ".join(requested),
    }
    if state:
        params["state"] = _text(state, "state", 200)
    return {
        "ok": True,
        "authorization_url": f"{AUTHORIZATION_URL}?{urllib.parse.urlencode(params)}",
        "scopes": requested,
        "redirect_uri": redirect,
        "next": (
            "Open this URL in a browser, approve, then copy the 'code' query "
            "parameter off the redirect and pass it to linkedin_exchange_code "
            "within 30 minutes (auth codes expire). Simpler alternative: the "
            "portal token generator at "
            "https://www.linkedin.com/developers/tools/oauth/token-generator"
        ),
    }


def exchange_code(
    code: str,
    redirect_uri: str = "",
    environ: dict[str, str] | None = None,
    requester=request_json,
) -> dict:
    """Exchange a 3-legged authorization code for an access token."""
    _text(code, "code", 4000)
    env = _env(environ)
    redirect = redirect_uri or (env.get(_ENV_REDIRECT) or "").strip()
    if not redirect:
        raise LinkedInError(
            "redirect_uri is required -- pass the SAME value used to obtain the "
            f"code, or set {_ENV_REDIRECT}."
        )
    form = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id(environ),
            "client_secret": client_secret(environ),
            "redirect_uri": redirect,
        }
    )
    status, payload, _ = requester(
        "POST",
        ACCESS_TOKEN_URL,
        {"Content-Type": "application/x-www-form-urlencoded"},
        form,
    )
    if status != 200 or not isinstance(payload, dict):
        return _fail(status, payload, "exchange authorization code")
    expires_in = payload.get("expires_in")
    return {
        "ok": True,
        # The token itself is returned ONCE, to the caller who asked for it, so it
        # can be stored in the environment. It is never logged or persisted here.
        "access_token": payload.get("access_token"),
        "expires_in": expires_in,
        "expires_in_days": (
            round(expires_in / 86400, 1) if isinstance(expires_in, int) else None
        ),
        "scope": payload.get("scope"),
        "refresh_token": payload.get("refresh_token"),
        "next": f"Set {_ENV_TOKEN} to this value in the MCP server environment.",
    }


def token_status(
    token: str = "",
    environ: dict[str, str] | None = None,
    requester=request_json,
) -> dict:
    """Introspect a token: active/expired/revoked, its scopes and expiry."""
    value = token.strip() or access_token(environ)
    form = urllib.parse.urlencode(
        {
            "client_id": client_id(environ),
            "client_secret": client_secret(environ),
            "token": value,
        }
    )
    status, payload, _ = requester(
        "POST",
        INTROSPECT_URL,
        {"Content-Type": "application/x-www-form-urlencoded"},
        form,
    )
    if status != 200 or not isinstance(payload, dict):
        return _fail(status, payload, "introspect token")
    scopes = [s for s in str(payload.get("scope") or "").replace(",", " ").split() if s]
    return {
        "ok": True,
        "active": payload.get("active"),
        "status": payload.get("status"),
        "scopes": scopes,
        "can_post": "w_member_social" in scopes,
        "can_identify": bool({"openid", "profile"} & set(scopes)),
        "expires_at": payload.get("expires_at"),
        "auth_type": payload.get("auth_type"),
    }


def auth_status(environ: dict[str, str] | None = None, requester=request_json) -> dict:
    """Local credential presence + a live token probe when a token is present.

    Safe to call with NOTHING configured -- that is its whole point: it reports
    exactly which variable is missing and what to do, instead of failing inside
    some other tool with an opaque 401.
    """
    present = credential_presence(environ)
    report: dict[str, Any] = {
        "ok": True,
        "credentials_present": present,
        "products_required": {
            "Sign In with LinkedIn using OpenID Connect": [
                "openid",
                "profile",
                "email",
            ],
            "Share on LinkedIn": ["w_member_social"],
        },
    }
    missing = [name for name, ok in present.items() if not ok]
    if not present[_ENV_TOKEN]:
        report["ok"] = False
        report["error"] = f"{_ENV_TOKEN} is not set -- no LinkedIn call can succeed."
        report["next"] = (
            "Generate a member token at "
            "https://www.linkedin.com/developers/tools/oauth/token-generator "
            f"and export it as {_ENV_TOKEN}. Full click-path: SETUP.md."
        )
        return report
    if present[_ENV_CLIENT_ID] and present[_ENV_CLIENT_SECRET]:
        report["token"] = token_status(environ=environ, requester=requester)
    else:
        report["token"] = {
            "ok": False,
            "error": (
                f"cannot introspect: {_ENV_CLIENT_ID}/{_ENV_CLIENT_SECRET} not set "
                "(the token itself may still work)."
            ),
        }
    if missing:
        report["missing"] = missing
    return report


# --- identity ---------------------------------------------------------------- #
def whoami(environ: dict[str, str] | None = None, requester=request_json) -> dict:
    """OIDC userinfo -> the member's identity and their Person URN.

    The Person URN (``urn:li:person:{sub}``) is what every posting tool needs as
    its ``author``; this is the only self-serve way to obtain it.
    """
    token = access_token(environ)
    status, payload, _ = requester("GET", USERINFO_URL, _auth_headers(token))
    if status != 200 or not isinstance(payload, dict):
        return _fail(status, payload, "retrieve member profile (/v2/userinfo)")
    return {
        "ok": True,
        "person_urn": person_urn(str(payload.get("sub") or "")),
        "sub": payload.get("sub"),
        "name": payload.get("name"),
        "given_name": payload.get("given_name"),
        "family_name": payload.get("family_name"),
        "picture": payload.get("picture"),
        "locale": payload.get("locale"),
        # email/email_verified are documented as OPTIONAL and may be absent.
        "email": payload.get("email"),
        "email_verified": payload.get("email_verified"),
    }


def _resolve_author(
    author: str, environ: dict[str, str] | None, requester
) -> tuple[str, dict | None]:
    """Use an explicit Person URN, else look it up once via /v2/userinfo."""
    if author:
        return _urn(author, "author", ("person",)), None
    me = whoami(environ, requester)
    if not me.get("ok"):
        return "", me
    return str(me["person_urn"]), None


# --- posting (Share on LinkedIn / w_member_social) --------------------------- #
def _ugc_payload(
    author: str,
    text: str,
    visibility: str,
    category: str,
    media: list | None = None,
) -> dict:
    content: dict[str, Any] = {
        "shareCommentary": {"text": text},
        "shareMediaCategory": category,
    }
    if media:
        content["media"] = media
    return {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": content},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }


def _created_post(headers: dict[str, str], action: str) -> dict:
    """A 201 carries the new post's URN in the X-RestLi-Id response header."""
    urn = ""
    for key, value in headers.items():
        if key.lower() == "x-restli-id":
            urn = value
            break
    result: dict[str, Any] = {"ok": True, "action": action, "post_urn": urn or None}
    if urn:
        result["url"] = f"https://www.linkedin.com/feed/update/{urn}/"
        result["delete_with"] = f"linkedin_delete_post(post_urn='{urn}')"
        result["activity_id"] = urn.rsplit(":", 1)[-1]
    return result


def _create_ugc(payload: dict, action: str, environ, requester) -> dict:
    token = access_token(environ)
    status, body, headers = requester(
        "POST", UGC_POSTS_URL, _auth_headers(token, json_body=True), payload
    )
    if status != 201:
        return _fail(status, body, action)
    return _created_post(headers, action)


def post_text(
    text: str,
    visibility: str = "PUBLIC",
    author: str = "",
    environ: dict[str, str] | None = None,
    requester=request_json,
) -> dict:
    """Publish a text-only share."""
    text = _text(text, "text", MAX_COMMENTARY_LEN)
    visibility = _visibility(visibility)
    resolved, failure = _resolve_author(author, environ, requester)
    if failure:
        return failure
    payload = _ugc_payload(resolved, text, visibility, "NONE")
    return _create_ugc(payload, "create text post", environ, requester)


def post_article(
    text: str,
    url: str,
    title: str = "",
    description: str = "",
    visibility: str = "PUBLIC",
    author: str = "",
    environ: dict[str, str] | None = None,
    requester=request_json,
) -> dict:
    """Publish a share that links out to an article/URL."""
    text = _text(text, "text", MAX_COMMENTARY_LEN)
    url = _https_url(url, "url")
    visibility = _visibility(visibility)
    resolved, failure = _resolve_author(author, environ, requester)
    if failure:
        return failure
    media: dict[str, Any] = {"status": "READY", "originalUrl": url}
    if title:
        media["title"] = {"text": _text(title, "title", 400)}
    if description:
        media["description"] = {"text": _text(description, "description", 400)}
    payload = _ugc_payload(resolved, text, visibility, "ARTICLE", [media])
    return _create_ugc(payload, "create article post", environ, requester)


def register_upload(
    owner: str,
    recipe: str = "feedshare-image",
    environ=None,
    requester=request_json,
) -> tuple[dict, dict | None]:
    """Step 1 of a media share: reserve an upload slot -> (uploadUrl, asset)."""
    token = access_token(environ)
    payload = {
        "registerUploadRequest": {
            "recipes": [f"urn:li:digitalmediaRecipe:{recipe}"],
            "owner": owner,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }
    status, body, _ = requester(
        "POST", REGISTER_UPLOAD_URL, _auth_headers(token, json_body=True), payload
    )
    if status != 200 or not isinstance(body, dict):
        return {}, _fail(status, body, "register media upload")
    value = body.get("value") or {}
    mechanism = (value.get("uploadMechanism") or {}).get(
        "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
    ) or {}
    upload_url = mechanism.get("uploadUrl")
    asset = value.get("asset")
    if not upload_url or not asset:
        return {}, _fail(
            status, body, "register media upload (response missing uploadUrl/asset)"
        )
    return {"upload_url": upload_url, "asset": asset}, None


def post_image(
    text: str,
    image_path: str,
    title: str = "",
    description: str = "",
    visibility: str = "PUBLIC",
    author: str = "",
    environ: dict[str, str] | None = None,
    requester=request_json,
    opener=None,
) -> dict:
    """Publish a share with an image: registerUpload -> binary upload -> post."""
    text = _text(text, "text", MAX_COMMENTARY_LEN)
    visibility = _visibility(visibility)
    read = opener or _read_binary
    try:
        blob = read(image_path)
    except OSError as exc:
        raise LinkedInError(f"cannot read image_path {image_path!r}: {exc}") from exc
    if not blob:
        raise LinkedInError(f"image_path {image_path!r} is empty")

    resolved, failure = _resolve_author(author, environ, requester)
    if failure:
        return failure
    slot, failure = register_upload(resolved, "feedshare-image", environ, requester)
    if failure:
        return failure

    token = access_token(environ)
    status, body, _ = requester(
        "PUT",
        slot["upload_url"],
        {"Authorization": f"Bearer {token}"},
        blob,
        UPLOAD_TIMEOUT,
    )
    if status in (400, 405):
        # The reference shows `curl --upload-file` (PUT) while the prose says
        # POST; retry the other verb once rather than fail on that ambiguity.
        status, body, _ = requester(
            "POST",
            slot["upload_url"],
            {"Authorization": f"Bearer {token}"},
            blob,
            UPLOAD_TIMEOUT,
        )
    if status not in (200, 201):
        return _fail(status, body, "upload image binary")

    media: dict[str, Any] = {"status": "READY", "media": slot["asset"]}
    if title:
        media["title"] = {"text": _text(title, "title", 400)}
    if description:
        media["description"] = {"text": _text(description, "description", 400)}
    payload = _ugc_payload(resolved, text, visibility, "IMAGE", [media])
    result = _create_ugc(payload, "create image post", environ, requester)
    if result.get("ok"):
        result["asset"] = slot["asset"]
    return result


def _read_binary(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def delete_post(
    post_urn: str,
    environ: dict[str, str] | None = None,
    requester=request_json,
) -> dict:
    """Delete a UGC post you authored."""
    post_urn = _urn(post_urn, "post_urn", ("ugcPost", "share"))
    token = access_token(environ)
    url = f"{UGC_POSTS_URL}/{encode_urn(post_urn)}"
    status, body, _ = requester("DELETE", url, _auth_headers(token))
    if status not in (200, 204):
        return _fail(status, body, "delete post")
    return {"ok": True, "action": "delete post", "post_urn": post_urn}


# --- comment / react (GATED on a self-serve app) ----------------------------- #
# GATED / expected-403 (unlikely to work, 20-45%): although the Open Permissions
# table's w_member_social row reads "Post, comment and like", the socialActions
# surface in practice requires the PARTNER-GATED w_member_social_feed scope on a
# personal app -- independently reproduced in two live reports (soleur #799,
# claude-code #60046, both 403 without w_member_social_feed). These tools call
# the UNVERSIONED /v2/socialActions twin, but the member surface is gated
# regardless of version. They are shipped for completeness + honest matrix
# coverage: they return LinkedIn's real 403 with the exact missing scope named,
# never a crash. See README.md "Deliberately NOT built / gated".
_SOCIAL_GATE = "w_member_social_feed"


def comment(
    post_urn: str,
    text: str,
    author: str = "",
    environ: dict[str, str] | None = None,
    requester=request_json,
) -> dict:
    """Comment on a post."""
    post_urn = _urn(post_urn, "post_urn", ("ugcPost", "share", "activity"))
    text = _text(text, "text", MAX_COMMENT_LEN)
    resolved, failure = _resolve_author(author, environ, requester)
    if failure:
        return failure
    token = access_token(environ)
    url = f"{SOCIAL_ACTIONS_URL}/{encode_urn(post_urn)}/comments"
    payload = {"actor": resolved, "object": post_urn, "message": {"text": text}}
    status, body, headers = requester(
        "POST", url, _auth_headers(token, json_body=True), payload
    )
    if status not in (200, 201):
        return _fail(status, body, "create comment", gated_scope=_SOCIAL_GATE)
    comment_urn = body.get("commentUrn") if isinstance(body, dict) else None
    header_id = None
    for key, value in headers.items():
        if key.lower() == "x-restli-id":
            header_id = value
            break
    return {
        "ok": True,
        "action": "create comment",
        "post_urn": post_urn,
        "comment_urn": comment_urn,
        "comment_id": header_id,
    }


def react(
    post_urn: str,
    author: str = "",
    environ: dict[str, str] | None = None,
    requester=request_json,
) -> dict:
    """Like a post."""
    post_urn = _urn(post_urn, "post_urn", ("ugcPost", "share", "activity"))
    resolved, failure = _resolve_author(author, environ, requester)
    if failure:
        return failure
    token = access_token(environ)
    url = f"{SOCIAL_ACTIONS_URL}/{encode_urn(post_urn)}/likes"
    payload = {"actor": resolved, "object": post_urn}
    status, body, _ = requester(
        "POST", url, _auth_headers(token, json_body=True), payload
    )
    if status not in (200, 201):
        return _fail(status, body, "create like", gated_scope=_SOCIAL_GATE)
    return {
        "ok": True,
        "action": "create like",
        "post_urn": post_urn,
        "like_id": body.get("id") if isinstance(body, dict) else None,
    }
