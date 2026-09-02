#!/usr/bin/env python3
"""Probe 1: warm-cache resume issues zero network calls; query keys collide not.

Evidence A. Independent of emit: cold then warm sweep on a fresh temp store.
Identity reports must match; warm transport.calls must be empty. Two URLs
that share a path and differ only in query must not share a cache key.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cache as C  # noqa: E402
import emit as E  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0030-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if doc.get("unit_id") != E.UNIT or doc.get("record_type") != "ProbeReport":
        return fail("not-a-probe-report")

    pages = C.load_pages()
    urls = C.sweep_urls(pages)
    clock = C.Clock()
    transport = C.CountingTransport(pages)
    with tempfile.TemporaryDirectory(prefix="wfa-0030-p1-") as tmp:
        cache = C.AcquisitionCache(Path(tmp), transport, now=clock)
        ident_cold = C.sweep_identity(cache, urls)
        cold_n = len(transport.calls)
        ident_warm = C.sweep_identity(cache, urls)
        warm_n = len(transport.calls) - cold_n
        collision = C.query_collision_control(pages)
        keys_in_store = cache._iter_keys()

    if cold_n != len(urls):
        return fail(f"cold calls {cold_n} != {len(urls)}")
    if warm_n != 0:
        return fail(f"warm issued {warm_n} network calls")
    if ident_cold["report_sha256"] != ident_warm["report_sha256"]:
        return fail("warm report not byte-identical")
    if not collision["ok"]:
        return fail("query keys collided")
    if len(keys_in_store) != len(urls):
        return fail(f"store keys {len(keys_in_store)} != urls {len(urls)}")

    ev_a = (doc.get("evidence") or {}).get("A") or {}
    measured = doc.get("measured") or {}
    if ev_a.get("warm_network_calls") != 0 or measured.get("warm_network_calls") != 0:
        return fail("artifact claims warm network calls")
    if ev_a.get("reports_byte_identical") is not True:
        return fail("artifact reports_byte_identical")
    if ident_warm["report_sha256"] != measured.get("report_sha256"):
        return fail("artifact report_sha256 drift")
    if measured.get("query_keys_distinct") is not True:
        return fail("artifact query_keys_distinct")
    if measured.get("cold_network_calls") != cold_n:
        return fail("artifact cold_network_calls drift")

    art_rows = measured.get("identity_rows") or []
    live_by_url = {r["url"]: r for r in ident_warm["rows"]}
    if len(art_rows) != len(live_by_url):
        return fail("identity row count drift")
    for row in art_rows:
        live = live_by_url.get(row.get("url"))
        if live is None:
            return fail(f"missing live row {row.get('url')}")
        if live["payload_sha256"] != row.get("payload_sha256"):
            return fail(f"payload drift {row.get('url')}")
        if live["etag"] != row.get("etag"):
            return fail(f"etag drift {row.get('url')}")

    schema = json.loads((REPO / E.SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        errs = list(jsonschema.Draft202012Validator(schema).iter_errors(doc))
        if errs:
            return fail(f"schema {errs[0].message}")

    print(
        json.dumps(
            {
                "probe": "probe1-warm-resume",
                "cold_network_calls": cold_n,
                "warm_network_calls": warm_n,
                "report_sha256": ident_warm["report_sha256"],
                "query_keys_distinct": True,
                "n_urls": len(urls),
                "pass": True,
                "unit_id": E.UNIT,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0030-probe1 warm zero-network byte-identical query-keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
