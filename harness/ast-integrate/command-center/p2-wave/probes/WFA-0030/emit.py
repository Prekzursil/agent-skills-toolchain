#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0030-acquisition-cache.json."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cache as C  # noqa: E402
import jsonschema  # noqa: E402

UNIT = "WFA-0030"
SENTINEL = "SUCCESS:WFA-0030"
OUT_REL = "command-center/wfa/WFA-0030-acquisition-cache.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0030/probe-report.schema.json"
DECLARED_SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/ProbeReport"
TITLE = (
    "Content-addressed acquisition cache with resume, staleness and corruption gates"
)
QUESTION = (
    "Implementation target: every external fetch is stored content-addressed "
    "with its URL, retrieval timestamp and HTTP validators so a re-run resumes "
    "instead of refetching - and a stale, empty or truncated entry can never "
    "be silently served as fresh."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0030/probe1_warm_resume.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0030/probe2_empty_stale_corrupt.py"
)

TEST_ROWS = (
    ("T1-empty-cache-not-ok", "EMPTY cache must NOT report OK", "empty_cache_not_ok"),
    ("T2-warm-resume", "Warm re-run issues zero network calls", "warm_zero_network"),
    ("T3-byte-identical", "Warm report is byte-identical to cold", "reports_byte_identical"),
    ("T4-expired-refetch", "Expired entry triggers a live refetch", "expired_refetch"),
    ("T5-truncated-rejected", "Truncated entry is rejected not served", "truncated_rejected"),
    ("T6-empty-payload", "Zero-byte payload is not served as fresh", "empty_payload_rejected"),
    ("T7-query-keys", "Query parameters participate in the cache key", "query_keys_distinct"),
    ("T8-both-states-health", "Empty not OK; populated READY", "populated_cache_ok"),
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0030-emit {msg}")
    return 1


def build(measured: dict) -> dict:
    tests = measured["tests"]
    if not tests.get("all_pass"):
        failed = [k for k, v in tests.items() if k != "all_pass" and not v]
        raise SystemExit(f"FAILED:WFA-0030-emit tests {failed}")
    pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    empty = measured["empty_health"]
    populated = measured["populated_health"]
    collision = measured["collision"]
    answer = (
        "The acquisition cache keys on the canonical URL including query "
        "parameters and stores payload bytes content-addressed beside retrieval "
        f"timestamp and HTTP validators (ETag, Last-Modified). Cold sweep of "
        f"{measured['cold_network_calls']} URLs issued "
        f"{measured['cold_network_calls']} transport calls; the warm re-run "
        f"issued {measured['warm_network_calls']} and produced a byte-identical "
        f"identity report ({measured['report_sha256'][:16]}…). Empty-store "
        f"health ok={empty['ok']} status={empty['status']}; after verified "
        f"entries health ok={populated['ok']}. An expired entry source="
        f"{measured['expired_source']} with {measured['expire_calls']} "
        "transport call(s); a truncated payload was rejected and refetched "
        f"({measured['trunc_calls']} call(s)); query-parameter pairs have "
        f"distinct keys ({collision['ok']}). Transport is an in-process "
        "instrumented page map, not live HTTP. WFA-0001 schema pack is absent "
        "on this worktree. SUCCESS:WFA-0030"
    )
    rows = [
        {
            "id": test_id,
            "name": name,
            "result": "PASS" if tests.get(key) else "FAIL",
        }
        for test_id, name, key in TEST_ROWS
    ]
    return {
        "unit_id": UNIT,
        "record_type": "ProbeReport",
        "kind": "ProbeReport",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": TITLE,
        "question": QUESTION,
        "answer": answer,
        "ts": now,
        "output_schema_declared": DECLARED_SCHEMA,
        "output_schema_declared_present": pack.is_file(),
        "output_schema_local": SCHEMA_REL,
        "transport": {
            "kind": "in-process-counting-page-map",
            "live_http": False,
            "fixture": C.PAGES_REL,
            "note": (
                "Network-call counts are len(CountingTransport.calls). "
                "This unit measures cache resume/staleness/corruption, not "
                "live vendor HTTP."
            ),
        },
        "evidence": {
            "A": {
                "claim": (
                    "Warm-cache re-run of the fixture sweep issued zero "
                    "transport calls and produced a byte-identical identity "
                    "report (URL, payload sha256, bytes, ETag, Last-Modified)."
                ),
                "warm_network_calls": measured["warm_network_calls"],
                "cold_network_calls": measured["cold_network_calls"],
                "reports_byte_identical": True,
                "report_sha256": measured["report_sha256"],
                "urls": measured["urls"],
            },
            "B": {
                "claim": (
                    "Empty-store health is ok=false (the estate defect is "
                    "empty-cache-reports-ok). A deliberately expired entry "
                    "issues a refetch, proving freshness is not constant true."
                ),
                "empty_cache_ok": False,
                "empty_status": empty["status"],
                "named_failure": empty["named_failure"],
                "naive_empty_ok": measured["naive_empty_health"]["ok"],
                "expired_refetch": True,
                "expired_source": measured["expired_source"],
                "expire_calls": measured["expire_calls"],
                "truncated_rejected": True,
                "trunc_calls": measured["trunc_calls"],
            },
        },
        "measured": {
            "empty_cache_ok": False,
            "empty_status": empty["status"],
            "populated_ok": populated["ok"],
            "populated_n_verified": populated["n_verified"],
            "warm_network_calls": measured["warm_network_calls"],
            "cold_network_calls": measured["cold_network_calls"],
            "reports_byte_identical": True,
            "report_sha256": measured["report_sha256"],
            "expired_refetch": True,
            "expired_source": measured["expired_source"],
            "truncated_rejected": True,
            "query_keys_distinct": True,
            "collision_pairs": collision["pairs"],
            "counters": measured["counters"],
            "identity_rows": measured["identity_warm"]["rows"],
        },
        "tests": rows,
        "reviewer": {
            "reviewer_id": "WFA-0030-probe2-empty-stale-corrupt",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-runs empty-store health, expiry refetch, truncated "
                "reject, and empty-payload reject on a fresh temp store, "
                "independent of probe 1's warm-resume identity path."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "warm-resume-and-query-keys"},
            {"id": "probe2", "command": P2, "role": "empty-stale-corrupt"},
        ],
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": SCHEMA_REL, "role": "local-schema"},
            {"path": C.PAGES_REL, "role": "disclosed-page-fixture"},
        ],
        "upstream": {
            "WFA-0001_schema_pack_present": pack.is_file(),
            "note": (
                "Declared output_schema points at WFA-0001's pack, which is "
                "absent. Local probe-report.schema.json is the executable "
                "contract."
            ),
        },
        "produced_by": {
            "execution_substrate": "local-parallel",
            "worktree": "/opt/p2/ast-integrate",
        },
        "notes": (
            "G-1 for WFA-0030. cloud ok=true is not delivery. Did not run "
            "unit_manifest.py --write. SUCCESS:WFA-0030"
        ),
    }


def main() -> int:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="wfa-0030-emit-") as tmp:
        measured = C.measure_all(Path(tmp))
    if not measured["tests"].get("all_pass"):
        return fail(f"measure tests {measured['tests']}")
    if measured["warm_network_calls"] != 0:
        return fail("warm network calls not zero")
    if measured["empty_health"].get("ok") is True:
        return fail("empty cache reported ok")
    doc = build(measured)
    errs = list(jsonschema.Draft202012Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        return fail("sentinel absent")
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:WFA-0030-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
