#!/usr/bin/env python3
"""Unit tests for the OSSInsight repo-discovery adapter (default OFF).

Network-free: the ``adapters.Caller`` is the stdlib fake OSSInsight router. Pins
the GET path templating, argument validation, the collections name filter, the
truthful data_quality passthrough for the degraded ranking, the capability
lattice, and the ENABLE_OSSINSIGHT gate in ``default_adapters``. One test uses a
real loopback socket to prove the default urllib caller on GET.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import HTTPServer

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HUB_DIR)
sys.path.insert(0, TESTS_DIR)

import adapters  # noqa: E402
import fake_ossinsight_backend as fake  # noqa: E402

BASE = "https://api.ossinsight.io"


def _adapter(base=BASE, caller=None):
    return adapters.OSSInsightAdapter(base, caller=caller or fake.fake_caller)


def _payload(result: dict) -> dict:
    assert not result["isError"], result
    return json.loads(result["content"][0]["text"])


# --------------------------------------------------------------------------- #
# surface + gate
# --------------------------------------------------------------------------- #
def test_tool_surface():
    names = _adapter().tool_names()
    assert names == [
        "ossinsight_repo_stats",
        "ossinsight_collections",
        "ossinsight_collection_ranking",
    ]


def test_default_adapters_gate_off_by_default():
    built = adapters.default_adapters({}, caller=fake.fake_caller)
    platforms = [a.platform for a in built]
    assert platforms == ["selfhosted"]  # only TrailSearch, no ossinsight
    assert "ossinsight" not in platforms


def test_default_adapters_wires_ossinsight_when_flag_on():
    for flag in ("1", "true", "yes"):
        built = adapters.default_adapters(
            {"ENABLE_OSSINSIGHT": flag}, caller=fake.fake_caller
        )
        assert [a.platform for a in built] == ["selfhosted", "ossinsight"]


def test_default_adapters_flag_off_values():
    for flag in ("", "0", "false", "no", "off"):
        built = adapters.default_adapters(
            {"ENABLE_OSSINSIGHT": flag}, caller=fake.fake_caller
        )
        assert [a.platform for a in built] == ["selfhosted"]


# --------------------------------------------------------------------------- #
# GET path templating + validation
# --------------------------------------------------------------------------- #
def test_repo_stats_templates_get_path():
    captured = {}

    def spy(method, url, body, _h, _t):
        captured.update(method=method, url=url, body=body)
        return fake.fake_caller(method, url, body, _h, _t)

    ad = _adapter(caller=spy)
    result = ad.handle_call(
        "ossinsight_repo_stats", {"owner": "pingcap", "repo": "tidb"}
    )
    assert captured["method"] == "GET"
    assert captured["url"] == BASE + "/gh/repo/pingcap/tidb"
    assert captured["body"] is None  # GET has no body
    payload = _payload(result)
    assert payload["data"]["full_name"] == "pingcap/tidb"
    assert payload["data"]["stargazers_count"] == 40478


def test_repo_stats_requires_owner_and_repo():
    ad = _adapter()
    assert ad.handle_call("ossinsight_repo_stats", {"owner": "x"})["isError"] is True
    assert ad.handle_call("ossinsight_repo_stats", {})["isError"] is True


def test_repo_stats_rejects_unsafe_segments():
    ad = _adapter()
    r = ad.handle_call("ossinsight_repo_stats", {"owner": "a/../b", "repo": "tidb"})
    assert r["isError"] is True
    assert "must match" in r["content"][0]["text"]


def test_collections_filter_is_local_and_truthful():
    ad = _adapter()
    all_rows = _payload(ad.handle_call("ossinsight_collections", {}))["data"]["rows"]
    assert len(all_rows) == 3
    filtered = _payload(ad.handle_call("ossinsight_collections", {"query": "vector"}))
    assert [r["name"] for r in filtered["data"]["rows"]] == ["Vector Database"]
    assert filtered["filtered_by"] == "vector"
    assert filtered["data"]["result"]["row_count"] == 1


def test_ranking_passes_degraded_data_quality_through_verbatim():
    ad = _adapter()
    payload = _payload(
        ad.handle_call(
            "ossinsight_collection_ranking", {"collection_id": "1", "by": "stars"}
        )
    )
    # Truthful degradation: relay the API's own unavailable note, do not hide it.
    assert payload["data_quality"]["status"] == "unavailable"
    assert payload["data"]["rows"] == []


def test_ranking_validates_by():
    ad = _adapter()
    r = ad.handle_call(
        "ossinsight_collection_ranking", {"collection_id": "1", "by": "bogus"}
    )
    assert r["isError"] is True
    assert "'by' must be" in r["content"][0]["text"]


# --------------------------------------------------------------------------- #
# capability lattice + degradation
# --------------------------------------------------------------------------- #
def test_capabilities_native_unprobed_then_probed():
    ad = _adapter()
    assert all(t["state"] == "native" for t in ad.capabilities()["tools"])
    probed = ad.capabilities(probe=True)
    assert all(t["state"] == "probed" for t in probed["tools"])


def test_capabilities_absent_when_unreachable():
    def dead(_m, _u, _b, _h, _t):
        return 0, None, "connection refused"

    report = _adapter(caller=dead).capabilities(probe=True)
    assert all(t["state"] == "absent" for t in report["tools"])


def test_backend_down_returns_truthful_error():
    def dead(_m, _u, _b, _h, _t):
        return 0, None, "connection refused"

    r = _adapter(caller=dead).handle_call(
        "ossinsight_repo_stats", {"owner": "pingcap", "repo": "tidb"}
    )
    assert r["isError"] is True
    assert "not reachable" in r["content"][0]["text"]


def test_backend_500_surfaces_status():
    r = _adapter().handle_call("ossinsight_repo_stats", {"owner": "boom", "repo": "x"})
    assert r["isError"] is True
    assert "HTTP 500" in r["content"][0]["text"]


# --------------------------------------------------------------------------- #
# end-to-end over a real loopback socket (default urllib caller, GET)
# --------------------------------------------------------------------------- #
def test_default_urllib_caller_get_against_real_socket():
    server = HTTPServer(("127.0.0.1", 0), fake._Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        ad = adapters.OSSInsightAdapter(f"http://127.0.0.1:{port}")  # real caller
        reachable, note = ad.probe()
        assert reachable, note
        payload = _payload(
            ad.handle_call(
                "ossinsight_repo_stats", {"owner": "pingcap", "repo": "tidb"}
            )
        )
        assert payload["data"]["full_name"] == "pingcap/tidb"
    finally:
        server.shutdown()
        server.server_close()
