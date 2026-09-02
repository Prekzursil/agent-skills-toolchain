#!/usr/bin/env python3
"""Stdlib fake of the public OSSInsight API for search-hub adapter tests.

OSSInsight (https://api.ossinsight.io) is an external public API; this fake
stands in for it so the OSSInsightAdapter can be exercised with NO network. It
mirrors the shapes verified live on 2026-09-02 (see the decision record):

* ``GET /gh/repo/{owner}/{repo}``     -> {"data": <github repo object>}  (200)
* ``GET /v1/collections/``            -> {"type","data":{"rows":[{id,name}]}} (200)
* ``GET /v1/collections/{id}/ranking_by_{stars|prs}/`` -> 200 with an EMPTY
  result and the real ``data_quality: unavailable`` block (event-firehose
  degradation) -- so the truthful-passthrough path is testable.
* an owner ``boom`` -> HTTP 500 (backend error), to exercise degradation.

Used as an importable ``fake_caller`` (pure) and as a runnable socket server.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

_COLLECTIONS = {
    "type": "sql_endpoint",
    "data": {
        "columns": [{"col": "id"}, {"col": "name"}],
        "rows": [
            {"id": "1", "name": "Static Site Generator"},
            {"id": "2", "name": "Web Framework"},
            {"id": "3", "name": "Vector Database"},
        ],
        "result": {"row_count": 3},
    },
}

_DATA_QUALITY_UNAVAILABLE = {
    "status": "unavailable",
    "metric": "github_event_derived_ranking",
    "source": "github_public_events_firehose",
    "unavailable_since": "2026-03-01",
    "reason": (
        "This ranking is ordered by recent star/PR/issue event counts, and our "
        "capture of those events fell to roughly 0.3% of baseline, so the ordering "
        "would be noise. An empty result here means the metric cannot be computed, "
        "not that there are no matching repositories."
    ),
    "docs": "https://ossinsight.io/docs/data-quality",
}


def build_repo_stats(owner: str, repo: str) -> dict:
    return {
        "data": {
            "full_name": f"{owner}/{repo}",
            "stargazers_count": 40478,
            "forks_count": 6234,
            "open_issues_count": 6863,
            "language": "Go",
            "description": f"stub description for {owner}/{repo}",
            "html_url": f"https://github.com/{owner}/{repo}",
            "topics": ["agent", "database"],
            "watchers_count": 40478,
        }
    }


def build_ranking() -> dict:
    return {
        "type": "sql_endpoint",
        "data": {"columns": [], "rows": [], "result": {"row_count": 0}},
        "data_quality": dict(_DATA_QUALITY_UNAVAILABLE),
    }


def route(method: str, path: str) -> tuple[int, dict | None]:
    parts = [p for p in path.split("?", 1)[0].split("/") if p]
    if method == "GET" and parts[:2] == ["gh", "repo"] and len(parts) == 4:
        owner, repo = parts[2], parts[3]
        if "boom" in owner:
            return 500, {"detail": "simulated backend failure"}
        return 200, build_repo_stats(owner, repo)
    if method == "GET" and parts == ["v1", "collections"]:
        return 200, _COLLECTIONS
    if (
        method == "GET"
        and parts[:2] == ["v1", "collections"]
        and len(parts) == 4
        and parts[3].startswith("ranking_by_")
    ):
        return 200, build_ranking()
    return 404, {"detail": "not found"}


def fake_caller(
    method: str, url: str, body: bytes | None, headers: dict, timeout: float
) -> tuple[int, dict | None, str]:
    """A stdlib-only ``adapters.Caller`` that never touches the network."""
    tail = url.split("://", 1)[-1]
    path = tail[tail.find("/") :] if "/" in tail else "/"
    status, payload = route(method, path)
    raw = json.dumps(payload) if payload is not None else ""
    return status, payload, raw


class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict | None) -> None:
        raw = json.dumps(payload or {}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        status, payload = route("GET", self.path)
        self._send(status, payload)

    def log_message(self, *_args) -> None:
        return


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 0
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print(f"fake-ossinsight listening on http://127.0.0.1:{server.server_address[1]}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
