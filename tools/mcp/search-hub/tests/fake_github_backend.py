#!/usr/bin/env python3
"""Stdlib fake of the GitHub REST API for the search-hub GitHubSearchAdapter tests.

GitHub (https://api.github.com) is an external public API; this fake stands in
for it so the adapter is exercised with NO network. It mirrors the shapes the
adapter relies on (verified keyless on 2026-09-02, see the gemhunt plan doc):

* ``GET /rate_limit``                          -> {"resources": {core, search}} (200)
* ``GET /search/repositories?q=..``            -> {total_count, incomplete_results,
  items[<repo objects>]} (200). A ``q`` containing ``ratelimited`` -> 403 with the
  real rate-limit message + ``x-ratelimit-remaining: 0`` + ``retry-after``;
  ``toolong`` -> 422 Validation Failed; ``forbidden`` -> 403 with headroom left
  (a non-rate-limit 403, e.g. a resource the token cannot see).
* ``GET /search/topics?q=..``                  -> {total_count, items[<topic objects>]}
* ``GET /repos/{o}/{r}/stats/commit_activity`` -> 52-week list (200); owner
  ``computing`` -> 202 {} on EVERY call (GitHub still computing); owner ``slow``
  -> 202 on the FIRST call for that path, 200 afterwards (the one-retry path);
  owner ``missing`` -> 404 Not Found; owner ``empty`` -> 204 no content.
* ``GET /repos/{o}/{r}/stats/participation``   -> {"all": [52], "owner": [52]}
  with the same owner-keyed behaviours.

Every response carries ``x-ratelimit-*`` headers: keyless search limit 10/min
and core 60/h, or 30/min and 5000/h when an ``Authorization`` header arrived --
so tests can prove the token reached the wire without ever printing it. Every
received request's headers are appended to ``RECEIVED`` (call ``reset()`` first).

Used as an importable ``fake_caller`` (pure, returns the 4-tuple
``adapters.HeaderCaller`` shape) and as a runnable loopback socket server.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote

RESET_EPOCH = 1_788_000_000  # a fixed, obviously-synthetic reset timestamp

# Every request's headers (lower-cased keys), pure caller and socket alike.
RECEIVED: list[dict[str, str]] = []
# Per-path call counters so the ``slow`` owner can answer 202 then 200.
_CALLS: dict[str, int] = {}
_LOCK = threading.Lock()


def reset() -> None:
    with _LOCK:
        RECEIVED.clear()
        _CALLS.clear()


def _repo(full_name: str, stars: int, created: str, pushed: str) -> dict:
    owner, name = full_name.split("/", 1)
    return {
        "id": abs(hash(full_name)) % 10_000_000,
        "node_id": "MDEwOlJlcG9zaXRvcnkx",
        "name": name,
        "full_name": full_name,
        "private": False,
        "owner": {"login": owner, "id": 1, "type": "Organization"},
        "html_url": f"https://github.com/{full_name}",
        "description": f"stub description for {full_name}",
        "fork": False,
        "url": f"https://api.github.com/repos/{full_name}",
        "created_at": created,
        "updated_at": pushed,
        "pushed_at": pushed,
        "homepage": "",
        "size": 1234,
        "stargazers_count": stars,
        "watchers_count": stars,
        "language": "Python",
        "forks_count": stars // 10,
        "open_issues_count": 7,
        "license": {
            "key": "mit",
            "name": "MIT License",
            "spdx_id": "MIT",
            "url": "https://api.github.com/licenses/mit",
        },
        "topics": ["mcp", "search"],
        "visibility": "public",
        "default_branch": "main",
        "score": 1.0,
        "archived": False,
    }


def build_repo_search(q: str) -> dict:
    return {
        "total_count": 2,
        "incomplete_results": False,
        "items": [
            _repo(
                "acme/hot-new-thing",
                1500,
                "2026-08-10T00:00:00Z",
                "2026-09-01T12:00:00Z",
            ),
            _repo(
                "acme/steady-tool", 900, "2026-08-20T00:00:00Z", "2026-08-30T09:00:00Z"
            ),
        ],
        "_q": q,  # echoed so tests can see what the fake received
    }


def build_topic_search(q: str) -> dict:
    return {
        "total_count": 1,
        "incomplete_results": False,
        "items": [
            {
                "name": q.split()[0] if q.strip() else "topic",
                "display_name": "Model Context Protocol",
                "short_description": "An open protocol for tool use.",
                "description": "Longer description of the topic.",
                "created_by": "Anthropic",
                "released": "2024",
                "created_at": "2024-11-25T00:00:00Z",
                "updated_at": "2026-08-01T00:00:00Z",
                "featured": False,
                "curated": True,
                "score": 1.0,
                "aliases": [],
            }
        ],
    }


def build_commit_activity() -> list[dict]:
    weeks = []
    week0 = 1_756_000_000 - 51 * 604_800
    for i in range(52):
        total = (i % 5) + 1  # 1..5 commits per week; 10 cycles of 15 + 1 + 2 = 153
        weeks.append(
            {
                "days": [total, 0, 0, 0, 0, 0, 0],
                "total": total,
                "week": week0 + i * 604_800,
            }
        )
    return weeks


def build_participation() -> dict:
    return {"all": [(i % 5) + 1 for i in range(52)], "owner": [1] * 52}


def _rate_headers(
    authenticated: bool, resource: str, remaining: int | None = None
) -> dict:
    if resource == "search":
        limit = 30 if authenticated else 10
    else:
        limit = 5000 if authenticated else 60
    rem = limit - 1 if remaining is None else remaining
    return {
        "x-ratelimit-limit": str(limit),
        "x-ratelimit-remaining": str(rem),
        "x-ratelimit-reset": str(RESET_EPOCH),
        "x-ratelimit-used": str(limit - rem),
        "x-ratelimit-resource": resource,
    }


def _rate_limit_body(authenticated: bool) -> dict:
    search = 30 if authenticated else 10
    core = 5000 if authenticated else 60
    return {
        "resources": {
            "core": {
                "limit": core,
                "used": 1,
                "remaining": core - 1,
                "reset": RESET_EPOCH,
            },
            "search": {
                "limit": search,
                "used": 0,
                "remaining": search,
                "reset": RESET_EPOCH,
            },
        },
        "rate": {"limit": core, "used": 1, "remaining": core - 1, "reset": RESET_EPOCH},
    }


def route(method: str, path: str, headers: dict[str, str]) -> tuple[int, object, dict]:
    """Pure router: (status, json-payload-or-None, response headers)."""
    lowered = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    with _LOCK:
        RECEIVED.append(lowered)
    authenticated = lowered.get("authorization", "").startswith("Bearer ")
    query = ""
    if "?" in path:
        path, query = path.split("?", 1)
    params = {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()}
    q = unquote(params.get("q", ""))
    parts = [p for p in path.split("/") if p]
    if method != "GET":
        return 405, {"message": "method not allowed"}, {}
    if parts == ["rate_limit"]:
        return (
            200,
            _rate_limit_body(authenticated),
            _rate_headers(authenticated, "core"),
        )
    if parts == ["search", "repositories"]:
        if "ratelimited" in q:
            body = {
                "message": (
                    "API rate limit exceeded for 203.0.113.9. (But here's the good "
                    "news: Authenticated requests get a higher rate limit.)"
                ),
                "documentation_url": "https://docs.github.com/rest/overview/rate-limits-for-the-rest-api",
            }
            hdrs = _rate_headers(authenticated, "search", remaining=0)
            hdrs["retry-after"] = "60"
            return 403, body, hdrs
        if "toolong" in q:
            body = {
                "message": "Validation Failed",
                "errors": [
                    {
                        "message": "The search is longer than 256 characters.",
                        "resource": "Search",
                        "field": "q",
                        "code": "invalid",
                    }
                ],
                "documentation_url": "https://docs.github.com/v3/search/",
            }
            return 422, body, _rate_headers(authenticated, "search")
        if "forbidden" in q:
            body = {"message": "Resource not accessible by integration"}
            return 403, body, _rate_headers(authenticated, "search")
        return 200, build_repo_search(q), _rate_headers(authenticated, "search")
    if parts == ["search", "topics"]:
        return 200, build_topic_search(q), _rate_headers(authenticated, "search")
    if len(parts) == 5 and parts[0] == "repos" and parts[3] == "stats":
        owner, kind = parts[1], parts[4]
        hdrs = _rate_headers(authenticated, "core")
        if kind not in ("commit_activity", "participation"):
            return 404, {"message": "Not Found"}, hdrs
        if owner == "missing":
            return 404, {"message": "Not Found"}, hdrs
        if owner == "computing":
            return 202, {}, hdrs
        if owner == "empty":
            return 204, None, hdrs
        if owner == "slow":
            with _LOCK:
                n = _CALLS.get(path, 0)
                _CALLS[path] = n + 1
            if n == 0:
                return 202, {}, hdrs
        if owner == "boom":
            return 500, {"message": "simulated backend failure"}, hdrs
        payload = (
            build_commit_activity()
            if kind == "commit_activity"
            else build_participation()
        )
        return 200, payload, hdrs
    return 404, {"message": "Not Found"}, _rate_headers(authenticated, "core")


def fake_caller(
    method: str, url: str, body: bytes | None, headers: dict, timeout: float
) -> tuple[int, dict | list | None, str, dict[str, str]]:
    """A stdlib-only ``adapters.HeaderCaller`` that never touches the network."""
    tail = url.split("://", 1)[-1]
    path = tail[tail.find("/") :] if "/" in tail else "/"
    status, payload, resp_headers = route(method, path, headers)
    raw = json.dumps(payload) if payload is not None else ""
    return status, payload, raw, resp_headers


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        status, payload, resp_headers = route("GET", self.path, dict(self.headers))
        raw = json.dumps(payload).encode("utf-8") if payload is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for key, value in resp_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def log_message(self, *_args) -> None:  # keep the test output quiet
        return


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 0
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print(f"fake-github listening on http://127.0.0.1:{server.server_address[1]}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
