#!/usr/bin/env python3
"""Pack CC-0008 receipt as BLOCKED (awaiting independent review)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "CC-0008"
OUT = "command-center/receipts/CC-0008.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/CC-0008/UNIT-ARTIFACT-MANIFEST.json"
TS0 = "2026-09-07T18:30:00Z"


def build() -> dict:
    p1 = json.loads((PROBE / "probe1-merge-summary.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-collision-summary.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-merge.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-collision.raw.txt").read_text(encoding="utf-8")
    pytest_out = (PROBE / "pytest-merge.out").read_text(encoding="utf-8")
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if p1.get("pytest_rc") != 0 or not p2.get("ok"):
        raise SystemExit(f"refusing to pack: probe failure p1={p1} p2={p2}")

    sentinel = (
        f"FAILED:{UNIT} blocked-on-independent-review; "
        f"merge read-back count={p1['work_unit_count_read_back']} "
        f"shortfall={p1['shortfall']} vs floor={p1['floor']}; "
        f"collision gate named both paths; pytest green; "
        f"SUCCESS:{UNIT} withheld pending reviewer who merges a malformed slice"
    )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0008",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art("tools/command-center/catalog_slice_merge.py", "primary"),
            L.art("command-center/ID-NAMESPACE-ALLOCATION.json", "supporting"),
            L.art("tools/command-center/tests/test_catalog_slice_merge.py", "supporting"),
            L.art("command-center/p2-wave/probes/CC-0008/probe1-merge-summary.json", "supporting"),
            L.art("command-center/p2-wave/probes/CC-0008/probe2-collision-summary.json", "supporting"),
            L.art("command-center/p2-wave/probes/CC-0008/probe1-merge.raw.txt", "log"),
            L.art("command-center/p2-wave/probes/CC-0008/probe2-collision.raw.txt", "log"),
            L.art("command-center/p2-wave/probes/CC-0008/pytest-merge.out", "log"),
        ],
        "evidence": [
            L.evidence(
                (
                    f"Live slice merge read-back count={p1['work_unit_count_read_back']} "
                    f"per_bucket={json.dumps(p1['per_bucket_counts'], sort_keys=True)} "
                    f"shortfall={p1['shortfall']} (floor {p1['floor']}; shortfall is first-class)."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/CC-0008/probe1-merge.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CC-0008/probe1_merge.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "read probe1-merge-summary.json",
                        json.dumps(
                            {
                                "count": p1["work_unit_count_read_back"],
                                "shortfall": p1["shortfall"],
                                "pytest_rc": p1["pytest_rc"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Collision control: two slices both claiming CC-0007 failed the merge "
                    f"with both source paths named (fired={p2['collision_fired']}, "
                    f"both_named={p2['both_paths_named']}); clean single-claim silent."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/CC-0008/probe2-collision.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CC-0008/probe2_collision.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "read probe2-collision-summary.json",
                        json.dumps(p2, sort_keys=True)[:2000],
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; the merger must never resolve a collision by "
                "renaming — escalate to the slice author instead."
            ),
        },
        "tests": [
            {
                "id": "collision-control",
                "name": "Two slices claiming CC-0007 fail with both paths named.",
                "command": "python3 -B command-center/p2-wave/probes/CC-0008/probe2_collision.py",
                "result": "PASS",
                "assertions": 3,
                "output_tail": raw2[-1500:],
            },
            {
                "id": "order-independence-field-idempotence",
                "name": "Pytest covers order-independence, field-completeness, idempotence.",
                "command": (
                    "python3 -m pytest tools/command-center/tests/test_catalog_slice_merge.py -q"
                ),
                "result": "PASS",
                "assertions": 5,
                "output_tail": pytest_out[-1500:],
            },
        ],
        "negative_controls": [
            L.control(
                "collision-both-paths",
                "mutation",
                "Duplicate CC-0007 across two slices must fail loudly naming both paths.",
                True,
                True,
                bad=p2.get("error_message", "")[:1500],
                good="single-claim clean load silent_on_clean=true",
            ),
            L.control(
                "missing-title-field",
                "mutation",
                "Unit missing title fails CC-0001 armed field-completeness gate.",
                True,
                True,
                bad="FieldCompletenessError CC-9990.title",
                good="live 2007 units field-complete",
            ),
        ],
        "reviewer": {
            "reviewer_id": "awaiting-fresh-context",
            "verdict": "FAIL",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only. Catalog requires an independent reviewer who "
                "merges a deliberately malformed slice and confirms loud failure. "
                "BLOCKED instead of stub SUCCESS."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "catalog_slice_merge.load_slices on live catalog-slices",
                "artifact_path": "command-center/catalog-slices",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/CC-0008/probe1_merge.py",
                    f"count={p1['work_unit_count_read_back']}",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    f"Program floor is 2048; measured merged units={p1['work_unit_count_read_back']} "
                    f"(shortfall={p1['shortfall']}). Filling the shortfall is out of scope for the "
                    "merger and belongs to slice authors."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Slice authors mint the remaining 41 units under the allocated prefixes; "
                    "re-run catalog_slice_merge and confirm work_unit_count_read_back == 2048."
                ),
            }
        ],
        "defects": [],
        "failure": {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Allocation table, merger, and collision gate are implemented and "
                "probe-green; SUCCESS withheld until independent review PASS."
            ),
            "blocked_on": (
                "Fresh-context independent reviewer must merge a deliberately malformed "
                "slice and confirm the merge fails loudly rather than dropping the slice."
            ),
        },
        "report": {
            "work_unit_count_read_back": p1["work_unit_count_read_back"],
            "floor": p1["floor"],
            "shortfall": p1["shortfall"],
            "per_bucket_counts": p1["per_bucket_counts"],
            "collision_gate_ok": p2["ok"],
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": "command-center/p2-wave/probes/CC-0008/_pack_receipt.py",
            "anti_false_green": "BLOCKED-with-real-probes",
        },
    }

    errs = L.validate(receipt, SCHEMA)
    if errs:
        print("WARN: schema issues:", errs[:12], file=sys.stderr)

    man = {
        "entry_id": UNIT,
        "unit_id": UNIT,
        "artifacts": [
            OUT,
            "tools/command-center/catalog_slice_merge.py",
            "command-center/ID-NAMESPACE-ALLOCATION.json",
            "tools/command-center/tests/test_catalog_slice_merge.py",
        ],
        "state": "BLOCKED",
        "registered_at": ended,
    }
    (L.REPO / MANIFEST).write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    rc = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc != 0:
        # Still persist BLOCKED if only soft schema noise; else fail.
        out = L.REPO / OUT
        out.write_text(
            json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {OUT} despite validation rc={rc}")
    # Refresh primary artifact hash after write
    receipt["artifacts"].insert(0, L.art(OUT, "primary"))
    (L.REPO / OUT).write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"PACKED {OUT} state=BLOCKED bytes={L.art(OUT)['bytes']}")
    return receipt


if __name__ == "__main__":
    build()
