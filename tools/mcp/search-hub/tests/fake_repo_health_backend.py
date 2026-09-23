#!/usr/bin/env python3
"""Stdlib fake of the three repo-health backends for the ``lane_repo_health`` tests.

bestofjs (``bestofjs-static-api-v2.vercel.app``), deps.dev (``api.deps.dev``) and
the OpenSSF Scorecard API (``api.securityscorecards.dev``) are external public
services; this fake stands in for all three so the lane is exercised with NO
network. One path-keyed router serves every route because the three real APIs
have disjoint path shapes. It mirrors the shapes verified live on 2026-09-02
(receipts in ``lane_repo_health.py`` and the search-hub README):

* ``GET /projects.json`` -> the bestofjs v2 document ``{date, tags[], projects[]}``
  (200). Prefixes select failure modes: ``/broken/projects.json`` -> 503 text,
  ``/badshape/projects.json`` -> 200 with a bare JSON list (wrong document),
  ``/nonjson/projects.json`` -> 200 ``text/html``.
* ``GET /v3/projects/github.com%2F{owner}%2F{repo}`` -> a deps.dev project record
  for ``pallets%2Fflask`` (with ``scorecard`` + ``ossFuzz``) and
  ``acme%2Fno-scorecard`` (without either); ``acme%2Fboom`` -> 500 JSON; the
  unencoded ``/v3/projects/github.com/o/r`` form -> 404 text ``404 page not
  found`` exactly like the real router (extra path segments); anything else ->
  404 with the real API's plain-text body ``project not found`` (not JSON).
* ``GET /v3/systems/{system}/packages/{name}`` -> ``npm/express`` (five versions,
  one deprecated, a pre-release published AFTER the default), the scoped
  ``npm/%40types%2Fnode`` (only in its encoded form), ``pypi/Flask`` (deps.dev
  normalizes the key to ``flask``), ``npm/left-pad`` (the lane's probe target),
  ``npm/boom`` -> 500; anything else -> 404 text ``package not found``.
  ``/v3/search`` -> 404 ``404 page not found`` (the real API has no search route).
* ``GET /projects/github.com/{owner}/{repo}`` -> a Scorecard document
  ``{date, repo, scorecard, score, checks[]}`` for ``pallets/flask`` (one check
  scored -1 = inconclusive, relayed verbatim); ``unscanned/repo`` -> 404 with an
  EMPTY body exactly like the live API; ``acme/boom`` -> 500 JSON.
* ``GET /`` -> 200 ``text/html`` (the Scorecard API root serves its Swagger UI).

Every received path is appended to ``RECEIVED`` (call ``reset()`` first) so tests
can count dataset fetches (the TTL cache) and assert URL encoding on the wire.
Used as an importable ``fake_caller`` (pure, returns the 3-tuple
``adapters.Caller`` shape) and as a runnable loopback socket server.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

DATASET_DATE = "2026-09-01T23:58:04.175Z"
JSON = "application/json; charset=utf-8"
TEXT = "text/plain; charset=utf-8"
HTML = "text/html; charset=utf-8"

# Every request path, pure caller and socket alike.
RECEIVED: list[str] = []
_LOCK = threading.Lock()


def reset() -> None:
    with _LOCK:
        RECEIVED.clear()


# --------------------------------------------------------------------------- #
# bestofjs v2 dataset (hand-authored, deterministic)
# --------------------------------------------------------------------------- #
def _tag(name: str, code: str, description: str = "") -> dict:
    return {
        "name": name,
        "code": code,
        "createdAt": "2015-04-25T00:00:00.000Z",
        "description": description or f"Projects tagged {name}.",
    }


TAGS = [
    _tag("Framework", "framework"),
    _tag("Vue", "vue"),
    _tag("React", "react"),
    _tag("Node.js framework", "nodejs-framework"),
    _tag("Testing", "test"),
    _tag("AI", "ai"),
]


def _project(
    name: str,
    full_name: str,
    slug: str,
    stars: int,
    trends: dict,
    tags: list[str],
    status: str = "active",
    created_at: str = "2018-06-12",
    pushed_at: str = "2026-08-27",
    added_at: str = "2021-01-22",
    contributor_count: int = 100,
    npm: str | None = None,
    downloads: int | None = None,
    url: str | None = None,
) -> dict:
    project = {
        "name": name,
        "slug": slug,
        "added_at": added_at,
        "description": f"stub description for {full_name}",
        "stars": stars,
        "full_name": full_name,
        "owner_id": abs(hash(full_name)) % 10_000_000,
        "status": status,
        "tags": tags,
        "trends": trends,
        "contributor_count": contributor_count,
        "pushed_at": pushed_at,
        "created_at": created_at,
    }
    if npm is not None:
        project["npm"] = npm
        project["downloads"] = downloads if downloads is not None else 1000
    if url is not None:
        project["url"] = url
    return project


PROJECTS = [
    _project(
        "Vue.js",
        "vuejs/core",
        "vuejs",
        54286,
        {"daily": 2, "weekly": 41, "monthly": 200, "quarterly": 522, "yearly": 2831},
        ["framework", "vue"],
        status="featured",
        npm="vue",
        downloads=59_580_275,
        url="https://vuejs.org/",
        contributor_count=643,
    ),
    _project(
        "React",
        "facebook/react",
        "react",
        240_000,
        {
            "daily": 30,
            "weekly": 210,
            "monthly": 900,
            "quarterly": 2700,
            "yearly": 11_000,
        },
        ["framework", "react"],
        status="featured",
        npm="react",
    ),
    _project(
        "Express",
        "expressjs/express",
        "express",
        67_000,
        {"daily": 5, "weekly": 60, "monthly": 250, "quarterly": 700, "yearly": 2900},
        ["nodejs-framework"],
        npm="express",
    ),
    _project(
        "Hono",
        "honojs/hono",
        "hono",
        28_000,
        {
            "daily": 40,
            "weekly": 300,
            "monthly": 1200,
            "quarterly": 3200,
            "yearly": 12_000,
        },
        ["nodejs-framework", "framework"],
        npm="hono",
    ),
    _project(
        "Vitest",
        "vitest-dev/vitest",
        "vitest",
        15_000,
        {"daily": 8, "weekly": 80, "monthly": 300, "quarterly": 900, "yearly": 3500},
        ["test"],
        npm="vitest",
    ),
    # Young project: only daily + weekly exist yet (real bestofjs omits the
    # longer windows until the project has been tracked that long).
    _project(
        "Skills",
        "mattpocock/skills",
        "skills",
        9000,
        {"daily": 900, "weekly": 7288},
        ["ai"],
        created_at="2026-08-20",
        added_at="2026-08-28",
        contributor_count=12,
    ),
    # Newest project: daily only.
    _project(
        "Sourcey",
        "sourcey/sourcey",
        "sourcey",
        1366,
        {"daily": 1},
        ["ai"],
        added_at="2026-08-29",
        url="https://sourcey.com/docs",
    ),
    _project(
        "Pinia",
        "vuejs/pinia",
        "pinia",
        14_000,
        {"daily": 3, "weekly": 35, "monthly": 150, "quarterly": 400, "yearly": 1600},
        ["vue"],
        npm="pinia",
    ),
    # Ties Vue.js on weekly (41) with MORE stars -> ranks above it (stars tie-break).
    _project(
        "React Router",
        "remix-run/react-router",
        "react-router",
        55_000,
        {"daily": 4, "weekly": 41, "monthly": 170, "quarterly": 500, "yearly": 2000},
        ["react"],
        npm="react-router",
    ),
]


def build_dataset() -> dict:
    return {"date": DATASET_DATE, "tags": TAGS, "projects": PROJECTS}


# --------------------------------------------------------------------------- #
# deps.dev v3
# --------------------------------------------------------------------------- #
SCORECARD_COMMIT = "d318b683471101618febed18996405ad26462110"
SCORECARD_VERSION = "v5.5.1-0.20260815060127-d1fab88f5463"


def _depsdev_check(name: str, score: int, reason: str) -> dict:
    return {
        "name": name,
        "documentation": {
            "shortDescription": f"Determines {name}.",
            "url": f"https://github.com/ossf/scorecard/blob/x/docs/checks.md#{name.lower()}",
        },
        "score": score,
        "reason": reason,
        "details": [],
    }


DEPSDEV_FLASK = {
    "projectKey": {"id": "github.com/pallets/flask"},
    "openIssuesCount": 4,
    "starsCount": 72_165,
    "forksCount": 16_952,
    "license": "BSD-3-Clause",
    "description": "The Python micro framework for building web applications.",
    "homepage": "https://flask.palletsprojects.com",
    "scorecard": {
        "date": "2026-08-17T00:00:00Z",
        "repository": {"name": "github.com/pallets/flask", "commit": SCORECARD_COMMIT},
        "scorecard": {"version": SCORECARD_VERSION, "commit": "d1fab88f5463"},
        "checks": [
            _depsdev_check(
                "Maintained",
                10,
                "18 commit(s) and 20 issue activity found in the last 90 days",
            ),
            _depsdev_check("Code-Review", 0, "Found 2/25 approved changesets"),
            _depsdev_check("Branch-Protection", 3, "branch protection is not maximal"),
        ],
        "overallScore": 7.1,
        "metadata": [],
    },
    "ossFuzz": {
        "lineCount": 6234,
        "lineCoverCount": 2663,
        "date": "2026-05-31T00:00:00Z",
        "configUrl": "https://github.com/google/oss-fuzz/tree/master/projects/flask",
    },
}

DEPSDEV_NO_SCORECARD = {
    "projectKey": {"id": "github.com/acme/no-scorecard"},
    "openIssuesCount": 1,
    "starsCount": 12,
    "forksCount": 3,
    "license": "MIT",
    "description": "a small repo deps.dev knows but Scorecard never scanned",
    "homepage": "",
}


def _version(
    name: str,
    version: str,
    published: str,
    default: bool = False,
    deprecated: str = "",
    system: str = "NPM",
) -> dict:
    return {
        "versionKey": {"system": system, "name": name, "version": version},
        "publishedAt": published,
        "isDefault": default,
        "isDeprecated": bool(deprecated),
        "deprecatedReason": deprecated,
    }


DEPSDEV_EXPRESS = {
    "packageKey": {"system": "NPM", "name": "express"},
    "versions": [
        _version("express", "4.17.1", "2019-05-26T04:03:02Z"),
        _version(
            "express",
            "4.18.0",
            "2022-04-25T02:05:31Z",
            deprecated="upgrade to 4.18.2",
        ),
        _version("express", "5.1.0", "2025-03-31T20:39:49Z"),
        _version("express", "5.2.1", "2025-12-01T20:49:43Z", default=True),
        # A pre-release published AFTER the default version.
        _version("express", "5.3.0-beta.1", "2026-08-15T10:00:00Z"),
    ],
}

DEPSDEV_TYPES_NODE = {
    "packageKey": {"system": "NPM", "name": "@types/node"},
    "versions": [
        _version("@types/node", "24.0.0", "2026-06-01T00:00:00Z"),
        _version("@types/node", "24.1.0", "2026-08-01T00:00:00Z", default=True),
    ],
}

DEPSDEV_FLASK_PYPI = {
    "packageKey": {"system": "PYPI", "name": "flask"},
    "versions": [
        _version("flask", "3.1.0", "2024-11-13T18:24:36Z", system="PYPI"),
        _version("flask", "3.1.2", "2025-08-19T20:09:00Z", default=True, system="PYPI"),
    ],
}

# The lane's probe target: a tiny, permanent real package (15 versions live).
DEPSDEV_LEFT_PAD = {
    "packageKey": {"system": "NPM", "name": "left-pad"},
    "versions": [
        _version("left-pad", "1.2.0", "2018-01-11T01:07:16Z"),
        _version("left-pad", "1.3.0", "2018-04-11T20:44:10Z", default=True),
    ],
}

# --------------------------------------------------------------------------- #
# OpenSSF Scorecard API
# --------------------------------------------------------------------------- #
SCORECARD_FLASK = {
    "date": "2026-08-24",
    "repo": {"name": "github.com/pallets/flask", "commit": SCORECARD_COMMIT},
    "scorecard": {"version": SCORECARD_VERSION, "commit": "d1fab88f5463"},
    "score": 7.1,
    "checks": [
        {
            "name": "Code-Review",
            "score": 0,
            "reason": "Found 2/25 approved changesets -- score normalized to 0",
            "details": None,
            "documentation": {
                "url": "https://github.com/ossf/scorecard/blob/x/docs/checks.md#code-review",
                "short": "Determines if the project requires human code review.",
            },
        },
        {
            "name": "Maintained",
            "score": 10,
            "reason": "18 commit(s) and 20 issue activity found in the last 90 days",
            "details": None,
            "documentation": {"url": "https://example.invalid", "short": "Maintained"},
        },
        {
            "name": "Vulnerabilities",
            "score": -1,
            "reason": "internal error: check could not run (inconclusive)",
            "details": ["Warn: osv.dev lookup failed"],
            "documentation": {"url": "https://example.invalid", "short": "Vulns"},
        },
    ],
}

ROOT_HTML = "<!DOCTYPE html><html><head><title>OpenSSF Scorecard</title></head></html>"


# --------------------------------------------------------------------------- #
# the router
# --------------------------------------------------------------------------- #
def _json(status: int, payload) -> tuple[int, bytes, str]:
    return status, json.dumps(payload).encode("utf-8"), JSON


def _text(status: int, body: str) -> tuple[int, bytes, str]:
    return status, body.encode("utf-8"), TEXT


def route(method: str, path: str) -> tuple[int, bytes, str]:
    """Pure router: (status, raw body bytes, content-type)."""
    with _LOCK:
        RECEIVED.append(path)
    if method != "GET":
        return _json(405, {"message": "method not allowed"})
    path = path.split("?", 1)[0]
    # ---- bestofjs v2: one static file ------------------------------------
    if path.endswith("/projects.json"):
        if path.startswith("/broken/"):
            return _text(503, "service unavailable")
        if path.startswith("/badshape/"):
            return _json(200, [])
        if path.startswith("/nonjson/"):
            return 200, b"<html>maintenance</html>", HTML
        return _json(200, build_dataset())
    # ---- deps.dev v3 ------------------------------------------------------
    if path.startswith("/v3/projects/"):
        key = path[len("/v3/projects/") :]
        if key == "github.com%2Fpallets%2Fflask":
            return _json(200, DEPSDEV_FLASK)
        if key == "github.com%2Facme%2Fno-scorecard":
            return _json(200, DEPSDEV_NO_SCORECARD)
        if key == "github.com%2Facme%2Fboom":
            return _json(500, {"code": 13, "message": "internal error"})
        if "/" in key:  # unencoded slashes: the real router sees extra segments
            return _text(404, "404 page not found\n")
        return _text(404, "project not found")
    if path.startswith("/v3/systems/"):
        parts = path.split("/")  # ['', 'v3', 'systems', system, 'packages', name]
        if len(parts) == 6 and parts[4] == "packages":
            system, name = parts[3], parts[5]
            if (system, name) == ("npm", "express"):
                return _json(200, DEPSDEV_EXPRESS)
            if (system, name) == ("npm", "%40types%2Fnode"):
                return _json(200, DEPSDEV_TYPES_NODE)
            if (system, name) == ("npm", "left-pad"):
                return _json(200, DEPSDEV_LEFT_PAD)
            if (system, name) == ("npm", "boom"):
                return _json(500, {"code": 13, "message": "internal error"})
            if (system, name.lower()) == ("pypi", "flask"):
                return _json(200, DEPSDEV_FLASK_PYPI)
        return _text(404, "package not found")
    if path.startswith("/v3/"):
        return _text(404, "404 page not found")
    # ---- OpenSSF Scorecard API --------------------------------------------
    if path.startswith("/projects/github.com/"):
        repo = path[len("/projects/github.com/") :]
        if repo == "pallets/flask":
            return _json(200, SCORECARD_FLASK)
        if repo == "acme/boom":
            return _json(500, {"code": 500, "message": "internal"})
        return 404, b"", JSON  # the live API: 404 with an empty body
    if path == "/":
        return 200, ROOT_HTML.encode("utf-8"), HTML
    return _json(404, {"code": 404, "message": f"path {path} was not found"})


def fake_caller(
    method: str, url: str, body: bytes | None, headers: dict, timeout: float
) -> tuple[int, dict | list | None, str]:
    """A stdlib-only ``adapters.Caller`` that never touches the network."""
    tail = url.split("://", 1)[-1]
    path = tail[tail.find("/") :] if "/" in tail else "/"
    status, raw_bytes, _ctype = route(method, path)
    raw = raw_bytes.decode("utf-8", "replace")
    try:
        return status, json.loads(raw), raw
    except (json.JSONDecodeError, ValueError):
        return status, None, raw


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        status, raw, ctype = route("GET", self.path)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def log_message(self, *_args) -> None:  # keep the test output quiet
        return


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 0
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print(f"fake-repo-health listening on http://127.0.0.1:{server.server_address[1]}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
