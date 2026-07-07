#!/usr/bin/env python3
"""Stdlib-only JSON HTTP for the compute providers -- ZERO new dependencies.

Everything the RunPod and OVH adapters need is built here on ``urllib`` +
``hashlib``/``hmac``:

* ``request_json`` -- the single network seam (GET/POST/DELETE -> ``(status,
  parsed)``). Tests monkeypatch THIS one function to stub every provider call.
* ``ovh_sign`` + ``ovh_request`` -- OVH's ``$1$`` SHA-1 request signature
  (``AS+CK+METHOD+URL+BODY+TS``) and the signed/​OAuth2 request wrapper. The body
  is serialized ONCE (compact, no spaces) and that exact string is BOTH signed
  and sent, so the signature always matches the bytes on the wire.
* ``runpod_rest`` / ``runpod_graphql`` -- bearer-auth helpers for RunPod's REST
  v1 surface and its GraphQL balance query.

Lightning uses its in-process SDK, not HTTP, so it has no helper here.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

TIMEOUT = 30.0

# OVH is region-partitioned into separate legal entities; the API + OAuth2 auth
# bases differ per endpoint id (the value carried in each ovh account bundle).
OVH_API_BASES = {
    "ovh-eu": "https://eu.api.ovh.com/1.0",
    "ovh-us": "https://api.us.ovhcloud.com/1.0",
    "ovh-ca": "https://ca.api.ovh.com/1.0",
}
OVH_AUTH_BASES = {
    "ovh-eu": "https://www.ovh.com/auth/oauth2/token",
    "ovh-us": "https://us.ovhcloud.com/auth/oauth2/token",
    "ovh-ca": "https://ca.ovh.com/auth/oauth2/token",
}
RUNPOD_REST = "https://rest.runpod.io/v1"
RUNPOD_GRAPHQL = "https://api.runpod.io/graphql"

# Cached client-clock delta vs OVH server time, and OAuth2 tokens, per process.
_ovh_delta: dict[str, int] = {}
_oauth_cache: dict[str, tuple[str, float]] = {}


def _encode_body(body: Any) -> bytes | None:
    """Serialize a request body to bytes (str/bytes passed through verbatim)."""
    if body is None:
        return None
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    if isinstance(body, str):
        return body.encode("utf-8")
    return json.dumps(body).encode("utf-8")


def _parse(text: str) -> Any:
    """Best-effort JSON parse; fall back to the raw text for non-JSON bodies."""
    stripped = text.strip()
    if not stripped:
        return {}
    if stripped[0] in "{[":
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return text
    try:
        return json.loads(stripped)  # bare numbers/strings (e.g. /auth/time)
    except json.JSONDecodeError:
        return text


def request_json(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: Any = None,
    timeout: float = TIMEOUT,
) -> tuple[int, Any]:
    """Issue one HTTP request, returning ``(status, parsed_body)``.

    Network failures return ``(0, {"error": ...})`` so callers branch on a
    non-2xx status rather than catching exceptions. HTTP error responses
    (4xx/5xx) are returned with their real status and parsed body.
    """
    req = urllib.request.Request(
        url, data=_encode_body(body), headers=headers or {}, method=method.upper()
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, _parse(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, {"error": f"{method.upper()} {url} failed: {exc}"}


# ---- RunPod -------------------------------------------------------------------
def runpod_rest(
    env: dict[str, str],
    method: str,
    path: str,
    body: Any = None,
    query: dict[str, str] | None = None,
) -> tuple[int, Any]:
    """Call the RunPod REST v1 API with bearer auth (``RUNPOD_API_KEY``)."""
    url = RUNPOD_REST + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {"Authorization": f"Bearer {env.get('RUNPOD_API_KEY', '')}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    return request_json(method, url, headers, body)


def runpod_graphql(env: dict[str, str], query: str) -> tuple[int, Any]:
    """POST a GraphQL query to RunPod (used for the account balance/spend)."""
    headers = {
        "Authorization": f"Bearer {env.get('RUNPOD_API_KEY', '')}",
        "Content-Type": "application/json",
    }
    return request_json("POST", RUNPOD_GRAPHQL, headers, {"query": query})


# ---- OVH ----------------------------------------------------------------------
def ovh_sign(
    app_secret: str,
    consumer_key: str,
    method: str,
    url: str,
    body: str,
    timestamp: int,
) -> str:
    """OVH request signature: ``$1$`` + SHA-1 of the ``+``-joined tuple."""
    payload = "+".join(
        [app_secret, consumer_key, method.upper(), url, body, str(timestamp)]
    )
    return "$1$" + hashlib.sha1(payload.encode("utf-8")).hexdigest()  # noqa: S324


def _ovh_timestamp(base: str) -> int:
    """Server-synced unix time (cached delta); local clock on any failure."""
    if base not in _ovh_delta:
        status, val = request_json("GET", f"{base}/auth/time")
        if status == 200 and isinstance(val, (int, float)):
            _ovh_delta[base] = int(val) - int(time.time())
        else:
            _ovh_delta[base] = 0
    return int(time.time()) + _ovh_delta[base]


def _ovh_oauth_token(env: dict[str, str], base_id: str) -> str | None:
    """Fetch/cache an OVH OAuth2 client-credentials bearer token, or None."""
    client_id = env.get("OVH_CLIENT_ID", "")
    client_secret = env.get("OVH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return None
    cached = _oauth_cache.get(client_id)
    if cached and cached[1] > time.time():
        return cached[0]
    token_url = OVH_AUTH_BASES.get(base_id, OVH_AUTH_BASES["ovh-eu"])
    creds = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "all",
        }
    )
    status, val = request_json(
        "POST",
        token_url,
        {"Content-Type": "application/x-www-form-urlencoded"},
        creds,
    )
    if status == 200 and isinstance(val, dict) and val.get("access_token"):
        token = str(val["access_token"])
        _oauth_cache[client_id] = (
            token,
            time.time() + int(val.get("expires_in", 3600)) - 30,
        )
        return token
    return None


def ovh_request(
    env: dict[str, str],
    method: str,
    path: str,
    body: Any = None,
    query: dict[str, str] | None = None,
) -> tuple[int, Any]:
    """Call the OVH API with per-account region + auth (API-key trio or OAuth2).

    The body is serialized to a compact string ONCE; that exact string is both
    signed and sent so the ``$1$`` signature always matches the wire bytes.
    """
    base_id = env.get("OVH_ENDPOINT") or "ovh-eu"
    base = OVH_API_BASES.get(base_id, base_id)
    url = base + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    body_str = "" if body is None else json.dumps(body, separators=(",", ":"))
    headers: dict[str, str] = {}
    token = _ovh_oauth_token(env, base_id)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    else:
        app_key = env.get("OVH_APPLICATION_KEY", "")
        app_secret = env.get("OVH_APPLICATION_SECRET", "")
        consumer = env.get("OVH_CONSUMER_KEY", "")
        timestamp = _ovh_timestamp(base)
        headers["X-Ovh-Application"] = app_key
        headers["X-Ovh-Consumer"] = consumer
        headers["X-Ovh-Timestamp"] = str(timestamp)
        headers["X-Ovh-Signature"] = ovh_sign(
            app_secret, consumer, method, url, body_str, timestamp
        )
    if body is not None:
        headers["Content-Type"] = "application/json"
    return request_json(method, url, headers, body_str if body is not None else None)
