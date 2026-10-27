#!/usr/bin/env python3
"""IMP-0074 probe1 (source): reference client over the recorded case matrix.

Every recorded success fixture must be accepted by the lenient reference
client; every recorded error case must surface as a structured ClientError
with the recorded status.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))

from marketplace.api import RegistryApi  # noqa: E402
from marketplace.clients import ClientError, RegistryClient  # noqa: E402

INDEX = json.loads((W / "tools/marketplace/fixtures/index.json").read_text(encoding="utf-8"))
RESULTS = {"probe": "probe1-reference-client", "unit_id": "IMP-0074", "rows": []}
FAILS = []


def record(cid, ok, detail=""):
    RESULTS["rows"].append({"id": cid, "ok": ok, "detail": detail[:160]})
    if not ok:
        FAILS.append(cid + ": " + detail[:120])


def run_cases():
    api = RegistryApi(INDEX)
    ref = RegistryClient(api)
    body = ref.index()
    record("index-ok", body["name"] == "conformance-fixture-registry" and bool(body["endpoints"]))

    full = ref.list_plugins()
    record("list-default", full["total"] == 4 and len(full["plugins"]) == 4)

    page1 = ref.list_plugins({"limit": "2"})
    record("list-limit-2-truncated", len(page1["plugins"]) == 2 and "next_cursor" in page1)

    cur = page1["next_cursor"]
    page2 = ref.list_plugins({"limit": "2", "cursor": cur})
    disjoint = not {p["name"] for p in page1["plugins"]} & {p["name"] for p in page2["plugins"]}
    record("list-page-2", len(page2["plugins"]) == 2 and "next_cursor" not in page2 and disjoint)

    _, _, raw = api.get_plugin("alpha")
    record("get-plugin-alpha", raw["plugin"]["name"] == "alpha")

    try:
        ref.get_plugin("nope-missing-plugin")
        record("get-plugin-missing", False, "no error raised")
    except ClientError as e:
        record("get-plugin-missing", e.status == 404 and e.code == "not_found")

    hits = ref.search({"q": "alpha"})
    record("search-hit", len(hits["results"]) == 1 and hits["results"][0]["name"] == "alpha")

    empty = ref.search({"q": "zzz-unmatched"})
    record("search-unmatched-empty", empty["results"] == [] and "next_cursor" not in empty)

    for q, cid in (({}, "search-missing-q"), ({"q": "  "}, "search-empty-q")):
        try:
            ref.search(q)
            record(cid, False, "no error raised")
        except ClientError as e:
            record(cid, e.status == 400)

    for q, cid in (({"limit": "0"}, "list-limit-0"),
                   ({"limit": "5000"}, "list-limit-too-big"),
                   ({"cursor": "!!!"}, "list-bad-cursor")):
        try:
            ref.list_plugins(q)
            record(cid, False, "no error raised")
        except ClientError as e:
            record(cid, e.status == 400)

    try:
        ref.search({"q": "alpha", "cursor": "!!!"})
        record("search-bad-cursor", False)
    except ClientError as e:
        record("search-bad-cursor", e.status == 400)

    status, schema_name, body = api.dispatch("/v9/none", {})
    record("unknown-endpoint", status == 404 and body["error"]["code"] == "unknown_endpoint")

    try:
        ref.get_plugin("INVALID NAME")
        record("get-plugin-invalid-name", False)
    except ClientError as e:
        record("get-plugin-invalid-name", e.status == 400)

    tolerated = ref.list_plugins({"spot": "1"})
    record("list-unknown-query-key", tolerated["total"] == 4)

    _, _, raw = api.get_plugin("beta")
    record("get-plugin-beta", raw["plugin"]["name"] == "beta")


run_cases()
RESULTS.update({"n": len(RESULTS["rows"]), "ok": sum(r["ok"] for r in RESULTS["rows"]),
                "pass": not FAILS, "failures": FAILS})
print("RESULT:" + json.dumps(RESULTS, sort_keys=True))
if FAILS:
    print("FAILED:IMP-0074-probe1 " + "; ".join(FAILS[:6]))
    raise SystemExit(1)
print("SUCCESS:IMP-0074-probe1 reference client accepts the full case matrix")
