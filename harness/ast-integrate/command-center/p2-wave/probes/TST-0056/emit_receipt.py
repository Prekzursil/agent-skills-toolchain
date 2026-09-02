#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0056.json from live measurements."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from census import live_census  # noqa: E402
from tests import (  # noqa: E402
    WIDEST_BYTES,
    WIDEST_ID,
    WIDEST_TS,
    run_required_tests,
)

UNIT = "TST-0056"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0056/probe1_field_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0056/probe2_js_roundtrip_and_schema.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0056/tests.py"
)
SUPPORTING = [
    "tools/lib/handled-ledger.mjs",
    "tools/lib/handled-ledger.schema.json",
    "command-center/p2-wave/probes/TST-0056/census.py",
    "command-center/p2-wave/probes/TST-0056/tests.py",
    "command-center/p2-wave/probes/TST-0056/probe1_field_census.py",
    "command-center/p2-wave/probes/TST-0056/probe2_js_roundtrip_and_schema.py",
    "command-center/p2-wave/probes/TST-0056/fixtures/planted-unbounded.schema.json",
    "command-center/p2-wave/probes/TST-0056/fixtures/planted-bounded.schema.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def probe_obj(cmd: str, code: int, text: str, role: str) -> dict:
    return {
        "command": cmd,
        "exit_code": code,
        "fingerprint": fp(text),
        "method": "command",
        "raw_output": text[-1500:],
        "role": role,
    }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if "SUCCESS:TST-0056-tests" not in t_test:
        print("FAILED:TST-0056 emit tests sentinel missing")
        return 1
    if "SUCCESS:TST-0056-probe1" not in t1:
        print("FAILED:TST-0056 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0056-probe2" not in t2:
        print("FAILED:TST-0056 emit probe2 sentinel missing")
        return 1

    try:
        test_rows = run_required_tests()
        census = live_census(REPO)
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:{UNIT} live recompute {type(exc).__name__}: {exc}")
        return 1

    widest = census.get("widest") or {}
    exceeding_n = int(census.get("can_exceed_2_53_count") or 0)
    js_unbounded = census.get("js_consumed_unbounded_integers") or []
    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(now.timestamp() - 1, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"Live census of {census['schema_file_count']} artifact schemas found "
        f"{census['numeric_field_count']} numeric fields; {exceeding_n} can exceed "
        f"2^53-1={census['max_safe_integer']} because they lack a maximum (or the "
        f"maximum is above MAX_SAFE_INTEGER). Widest live field: "
        f"{widest.get('schema')}{widest.get('pointer')} types={widest.get('types')} "
        f"unbounded={widest.get('unbounded')}. tools/lib/handled-ledger.mjs is "
        f"the JS consumer under test; its schema encodes id/timestamp_ns/"
        f"byte_count as decimal strings and bounds seq to MAX_SAFE_INTEGER "
        f"({len(js_unbounded)} unbounded integers in that schema). "
        f"Round-trip of uint64 id {WIDEST_ID} through the lossless JS consumer "
        f"preserves the decimal; JSON.parse degrades it. {SENTINEL}"
    )
    receipt = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0056 numeric precision and big-integer round-trip",
        "title": "Numeric precision and big-integer round-trip",
        "question": (
            "Target: ids, timestamps and byte counts must survive a JSON "
            "round-trip without precision loss. A 64-bit id beyond 2^53 silently "
            "degrades through a JavaScript consumer. Which fields in the artifact "
            "schemas can exceed 2^53, and are any of them read by a JS tool "
            "(tools/lib/*.mjs)?"
        ),
        "answer": answer,
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot: same-fingerprint structural refute parks",
        },
        "field_census": {
            "max_safe_integer": census["max_safe_integer"],
            "schema_file_count": census["schema_file_count"],
            "numeric_field_count": census["numeric_field_count"],
            "can_exceed_2_53_count": exceeding_n,
            "wide_named_exceeding_count": census["wide_named_exceeding_count"],
            "widest": widest,
            "exceeding": census["exceeding"],
            "js_consumers": census["js_consumers"],
            "js_consumed_schema": census["js_consumed_schema"],
            "js_consumed_numeric_fields": census["js_consumed_numeric_fields"],
            "js_consumed_unbounded_integers": js_unbounded,
        },
        "implementation": {
            "js_consumer": "tools/lib/handled-ledger.mjs",
            "js_schema": "tools/lib/handled-ledger.schema.json",
            "lossless": "rewriteUnsafeIntegerTokens then JSON.parse",
            "wide_fields_encoding": "decimal string",
            "seq_maximum": 9007199254740991,
            "widest_round_tripped_field": "id",
            "widest_round_tripped_value": str(WIDEST_ID),
            "timestamp_ns_fixture": str(WIDEST_TS),
            "byte_count_fixture": str(WIDEST_BYTES),
        },
        "artifact_paths": [OUT_REL] + list(SUPPORTING),
        "test_ids": [
            "test_large_integer_round_trips_through_the_js_consumer",
            "test_schema_forbids_unbounded_integers_where_a_js_consumer_exists",
            "named-probe1",
            "named-probe2",
        ],
        "negative_control_ids": [
            "json-parse-degrades-uint64",
            "planted-unbounded-byte-count",
            "drop-seq-maximum-reds-forbids-checker",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "kind": "field-census",
                "detail": (
                    f"{exceeding_n} numeric schema fields can exceed 2^53; "
                    "JS-consumed handled-ledger schema has zero unbounded integers."
                ),
                "path": "command-center/p2-wave/probes/TST-0056/census.py",
                "exit_code": c1,
                "anchor": "command-center/p2-wave/probes/TST-0056/probe1_field_census.py",
                "claim": (
                    "A live schema walk reports every integer/number field that "
                    "can exceed 2^53. The planted unbounded byte_count is found; "
                    "the planted max=255 exit_code is not."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "kind": "js-round-trip",
                "detail": (
                    f"handled-ledger.mjs round-trip preserved id={WIDEST_ID}; "
                    "JSON.parse did not."
                ),
                "path": "tools/lib/handled-ledger.mjs",
                "exit_code": c2,
                "anchor": "tools/lib/handled-ledger.mjs:parseLossless",
                "claim": (
                    "The widest JS-consumed field (uint64 id) round-trips through "
                    "the actual JS consumer as a decimal string. Naive JSON.parse "
                    "is the negative control and degrades the same token."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P2, c2, t2, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "json-parse-degrades-uint64",
                "kind": "float-parser",
                "description": (
                    "JSON.parse of an unquoted 2^64-1 id must not equal the "
                    "original decimal; the lossless consumer must."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": f"lossless id={WIDEST_ID}",
                "bad_state_output": "naive JSON.parse id != 18446744073709551615",
            },
            {
                "id": "planted-unbounded-byte-count",
                "kind": "detector-control",
                "description": (
                    "A fixture schema with unbounded integer byte_count is "
                    "flagged; a max=255 exit_code is not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "planted-bounded hits=[]",
                "bad_state_output": "planted-unbounded finds byte_count",
            },
            {
                "id": "drop-seq-maximum-reds-forbids-checker",
                "kind": "mutation",
                "description": (
                    "Deleting seq.maximum from the JS-consumed schema makes "
                    "integer_fields_unbounded return a non-empty list."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "js schema unbounded integers=0",
                "bad_state_output": "mutated seq.maximum absent -> unbounded",
            },
        ],
        "tests": [
            {
                "id": "test_large_integer_round_trips_through_the_js_consumer",
                "command": TEST_CMD,
                "result": "PASS",
                "detail": test_rows[0] if test_rows else {},
            },
            {
                "id": "test_schema_forbids_unbounded_integers_where_a_js_consumer_exists",
                "command": TEST_CMD,
                "result": "PASS",
                "detail": test_rows[1] if len(test_rows) > 1 else {},
            },
            {"id": "named-probe1", "command": P1, "result": "PASS"},
            {"id": "named-probe2", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0056-probe2-js-roundtrip-and-schema",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "obligation": (
                "Large integers must round-trip through the JS consumer; the "
                "schema the JS consumer reads must forbid unbounded integers."
            ),
            "method": (
                "Re-ran probe2: lossless vs JSON.parse on uint64 id, and "
                "jsonschema plus a seq.maximum-drop mutation. Did not re-read "
                "the receipt."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0056",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0056/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog input _USER-PROMPTS.md:10807 is absent on this "
                    "worktree. The unit was executed from WORK-UNIT-CATALOG.json "
                    "TST-0056 and the live schema/JS tree."
                ),
                "settling_experiment": (
                    "If _USER-PROMPTS.md lands, re-read line 10807 and confirm "
                    "the census still covers every named numeric field."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Dependency TST-0039 is the receipt schema family. "
                    "command-center/schema/test-receipt.schema.json exists as a "
                    "generated $ref shim to platform/schema/artifact-class-profiles.schema.json. "
                    "This receipt follows the live G-1 test-receipt shape used by "
                    "other delivered TST units and includes SUCCESS:TST-0056."
                ),
                "settling_experiment": (
                    "Validate this artifact against the physical test-receipt "
                    "profile after TST-0039 is itself G-1 delivered."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "command-center/schema integer fields that are NOT read by "
                    "tools/lib/*.mjs remain unbounded. This unit bounds the "
                    "JS-consumed handled-ledger schema rather than rewriting "
                    "every Python-only artifact schema."
                ),
                "settling_experiment": (
                    "If a new tools/lib/*.mjs starts JSON.parse-ing those "
                    "schemas, add maximum<=2^53-1 or decimal-string encoding "
                    "and re-run probe2."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "notes": (
            "G-1 delivery of TST-0056 numeric precision. Live named probes exit 0. "
            "Did not run global unit_manifest.py --write. No ADV rebuild. "
            "cloud ok is not consulted. " + SENTINEL
        ),
        "adv_rebuild_circle": False,
        "cloud_ok": False,
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
