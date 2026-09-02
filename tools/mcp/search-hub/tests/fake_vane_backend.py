#!/usr/bin/env python3
"""A tiny stdlib fake of the Vane (ex-Perplexica) HTTP API for the answer lane.

Vane (github ``ItzCrazyKns/Vane``) is an external service that needs an LLM; this
fake stands in for it so ``lane_answer.VaneAdapter`` can be exercised over a REAL
loopback socket with NO Docker, NO SearXNG, NO LLM and NO network. It answers the
two routes the adapter uses, in the shapes read from the ``v1.12.2`` tag on
2026-09-02 (``src/app/api/providers/route.ts``, ``src/app/api/search/route.ts``,
``docs/API/SEARCH.md``):

* ``GET  /api/providers`` -> ``{providers: [{id, name, chatModels[{name, key}],
  embeddingModels[{name, key}]}]}`` (provider ids are UUIDs that DRIFT between
  installs -- the reason the adapter resolves them on every call).
* ``POST /api/search``    -> ``{message, sources[{content, metadata{title, url}}]}``
  for ``{chatModel{providerId, key}, embeddingModel{providerId, key},
  optimizationMode, sources[web|academic|discussions], query, history, stream}``;
  HTTP 400 ``{message: 'Missing sources or query'}`` exactly like Vane when
  ``sources``/``query`` are missing.

Failure modes the adapter must degrade on, all driven by the query text or the
fake's state so a test never needs a real outage:

* query containing ``"boom"``   -> HTTP 500 ``{message: 'Search error', error}``.
* query containing ``"sleep"``  -> the SOCKET server sleeps ``SLEEP_S`` before
  answering (a real client-side timeout for the default urllib caller).
* query containing ``"onion"``  -> one source whose URL is a ``.onion`` host, to
  prove the adapter passes it through as a string and never fetches it.
* ``FakeVane(providers=[])``    -> a Vane with NO provider configured.
* ``FakeVane(providers_status=500)`` -> ``/api/providers`` itself fails.

Used two ways: (1) ``FakeVane().caller`` / the module-level ``fake_caller`` as an
injected ``adapters.Caller`` in pure unit tests (``FakeVane.calls`` records every
request so the 60 s provider cache can be pinned), and (2) as a runnable server
(``python fake_vane_backend.py [port]``) for the loopback integration tests.
"""

from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

SLEEP_S = 0.6

# Two providers, so "first available" is distinguishable from "any": the first
# carries two chat models and one embedder, the second one of each.
DEFAULT_PROVIDERS: list[dict] = [
    {
        "id": "11111111-1111-4111-8111-111111111111",
        "name": "Ollama",
        "chatModels": [
            {"name": "Llama 3.2 3B", "key": "llama3.2:3b"},
            {"name": "Qwen 2.5 7B", "key": "qwen2.5:7b"},
        ],
        "embeddingModels": [{"name": "Nomic Embed Text", "key": "nomic-embed-text"}],
    },
    {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "OpenAI compatible",
        "chatModels": [{"name": "GPT 4o mini", "key": "gpt-4o-mini"}],
        "embeddingModels": [
            {"name": "Text Embedding 3 Small", "key": "text-embedding-3-small"}
        ],
    },
]


def build_search_response(body: dict) -> dict:
    """The non-streaming ``/api/search`` payload Vane returns (``{message, sources}``)."""
    query = str(body.get("query", ""))
    chat = body.get("chatModel") or {}
    sources = [
        {
            "content": f"snippet about {query}",
            "metadata": {
                "title": f"result for {query}",
                "url": "https://example.test/answer/1",
            },
        },
        {
            "content": f"second snippet about {query}",
            "metadata": {"title": "second result", "url": "https://example.test/2"},
        },
    ]
    if "onion" in query.lower():
        sources.append(
            {
                "content": "an index entry; never fetched by the hub",
                "metadata": {
                    "title": "onion index hit",
                    "url": "http://exampleonionexampleonionexampleonionexampleonionexamp.onion/",
                },
            }
        )
    return {
        "message": (
            f"Answer about {query} [1][2] (chat {chat.get('key')} via "
            f"{chat.get('providerId')}; mode {body.get('optimizationMode')}; "
            f"sources {','.join(body.get('sources') or [])}; "
            f"history {len(body.get('history') or [])})"
        ),
        "sources": sources,
    }


class FakeVane:
    """Stateful fake: providers list, optional forced failures, a request log."""

    def __init__(
        self,
        providers: list[dict] | None = None,
        providers_status: int = 200,
        search_status: int | None = None,
    ) -> None:
        self.providers = (
            [dict(p) for p in providers]
            if providers is not None
            else [dict(p) for p in DEFAULT_PROVIDERS]
        )
        self.providers_status = providers_status
        self.search_status = search_status  # force a status on /api/search
        self.calls: list[tuple[str, str, dict | None]] = []  # (method, path, body)

    # -- pure router shared by the socket server and the injected caller -------
    def route(self, method: str, path: str, body: dict) -> tuple[int, dict | None]:
        self.calls.append((method, path, body if body else None))
        if method == "GET" and path == "/api/providers":
            if self.providers_status != 200:
                return self.providers_status, {"message": "An error has occurred."}
            return 200, {"providers": [dict(p) for p in self.providers]}
        if method == "POST" and path == "/api/search":
            if not body.get("sources") or not body.get("query"):
                return 400, {"message": "Missing sources or query"}
            if self.search_status is not None:
                return self.search_status, {"message": f"forced {self.search_status}"}
            if "boom" in str(body.get("query", "")).lower():
                return 500, {
                    "message": "Search error",
                    "error": {"detail": "simulated LLM failure"},
                }
            return 200, build_search_response(body)
        return 404, {"message": "not found"}

    def caller(
        self, method: str, url: str, body: bytes | None, headers: dict, timeout: float
    ) -> tuple[int, dict | None, str]:
        """A stdlib-only ``adapters.Caller`` that never touches the network."""
        path = url.split("://", 1)[-1]
        path = path[path.find("/") :] if "/" in path else "/"
        parsed = json.loads(body.decode("utf-8")) if body else {}
        status, payload = self.route(method, path, parsed)
        raw = json.dumps(payload) if payload is not None else ""
        return status, payload, raw

    def handler(self):
        """A ``BaseHTTPRequestHandler`` class bound to THIS fake's state."""
        state = self

        class _Handler(BaseHTTPRequestHandler):
            def _send(self, status: int, payload: dict | None) -> None:
                raw = json.dumps(payload or {}).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
                status, payload = state.route("GET", self.path, {})
                self._send(status, payload)

            def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
                length = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(length) if length else b""
                try:
                    parsed = json.loads(raw.decode("utf-8")) if raw else {}
                except (json.JSONDecodeError, ValueError):
                    parsed = {}
                if "sleep" in str(parsed.get("query", "")).lower():
                    time.sleep(SLEEP_S)  # long enough for a sub-second client timeout
                status, payload = state.route("POST", self.path, parsed)
                self._send(status, payload)

            def log_message(self, *_args) -> None:  # keep the test output quiet
                return

        return _Handler


_DEFAULT = FakeVane()


def fake_caller(
    method: str, url: str, body: bytes | None, headers: dict, timeout: float
) -> tuple[int, dict | None, str]:
    """Module-level convenience: the default two-provider fake, stateless for tests
    that do not need the request log."""
    return _DEFAULT.caller(method, url, body, headers, timeout)


def main(argv: list[str]) -> int:
    port = int(argv[0]) if argv else 0
    server = HTTPServer(("127.0.0.1", port), FakeVane().handler())
    print(f"fake-vane listening on http://127.0.0.1:{server.server_address[1]}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
