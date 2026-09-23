#!/usr/bin/env python3
"""Docker-free smoke test for the self-hosted search lane.

Docker is not always present (e.g. CI, or a first look on a fresh box). This
script proves the *adapter + hub wiring* end to end WITHOUT Docker by standing up
the stdlib fake TrailSearch backend on a real loopback socket, pointing a
``TrailSearchAdapter`` at it, and exercising probe + search + extract + the
truthful-degradation path. It is the always-runnable companion to
``run-selfhosted-search.sh smoke`` (which needs the real daemon).

Run: ``python deploy/smoke_selfhosted_no_docker.py`` (from the search-hub dir).
Exit 0 = the keyless lane works; nonzero = it does not.
"""

from __future__ import annotations

import os
import sys
import threading
from http.server import HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(HERE)
sys.path.insert(0, HUB)
sys.path.insert(0, os.path.join(HUB, "tests"))

import adapters  # noqa: E402
import fake_trailsearch_backend as fake  # noqa: E402


def main() -> int:
    server = HTTPServer(("127.0.0.1", 0), fake._Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        ad = adapters.TrailSearchAdapter(base)  # real stdlib urllib caller

        reachable, note = ad.probe()
        assert reachable, f"probe failed: {note}"
        print(f"[smoke] probe ok ({note}) -> capability=probed")

        caps = ad.capabilities(probe=True)
        states = {t["state"] for t in caps["tools"]}
        assert states == {"probed"}, states
        print(f"[smoke] capability lattice: {sorted(states)}")

        res = ad.handle_call("selfhosted_search", {"query": "keyless smoke"})
        assert not res["isError"], res
        print("[smoke] selfhosted_search returned real (fake-backed) results")

        res = ad.handle_call("selfhosted_extract", {"urls": ["https://a.test"]})
        assert not res["isError"], res
        print("[smoke] selfhosted_extract returned content")
    finally:
        server.shutdown()
        server.server_close()

    # Truthful degradation: a down backend never fabricates hits.
    down = adapters.TrailSearchAdapter("http://127.0.0.1:1")
    res = down.handle_call("selfhosted_search", {"query": "x"})
    assert res["isError"] and "fabricated" in res["content"][0]["text"], res
    print("[smoke] backend-down path returns a truthful isError (no fake hits)")

    print("[smoke] OK: keyless self-hosted lane verified without Docker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
