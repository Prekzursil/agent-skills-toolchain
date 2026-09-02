#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0178.json (cache_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import run_mutation_suite, run_property_suite  # noqa: E402

OUT = "command-center/receipts/TST-0178.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0178/probe1_property_pressure.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0178/probe2_mutation_control.py"
)
QUESTION = (
    "Under cache-size pressure, can eviction remove an entry that a running "
    "unit is actively reading? PASS requires reference counting or pinning; "
    "zero evictions of pinned entries across a randomized pressure run."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(label: str, command: str, path: Path) -> dict:
    sha, size = sha256_file(path)
    blob = f"{label}\n{command}\n{sha}\n{size}\n".encode("utf-8")
    return {
        "id": label,
        "command": command,
        "path": path.relative_to(REPO).as_posix(),
        "bytes": size,
        "sha256": sha,
        "fingerprint": hashlib.sha256(blob).hexdigest(),
    }


def main() -> int:
    prop = run_property_suite()
    mut = run_mutation_suite()
    if not prop.get("ok"):
        print("FAILED:TST-0178 emit property suite")
        print(json.dumps(prop.get("fails"), indent=2)[:2000])
        return 1
    if not mut.get("ok") or not mut.get("detector_fired"):
        print("FAILED:TST-0178 emit mutation suite")
        print(json.dumps(mut.get("harsh"), indent=2)[:2000])
        return 1

    src = fingerprint("source_probe", P1, HERE / "probe1_property_pressure.py")
    ver = fingerprint("verifier_probe", P2, HERE / "probe2_mutation_control.py")
    if src["fingerprint"] == ver["fingerprint"]:
        print("FAILED:TST-0178 source_probe == verifier_probe")
        return 1

    cache_py = REPO / "tools/plugin/cache.py"
    cache_sha, cache_bytes = sha256_file(cache_py)

    body_for_blind = {
        "unit_id": "TST-0178",
        "question": QUESTION,
        "verdict": "CONFIRMED",
        "property_ok": prop["ok"],
        "mutation_fired": mut["detector_fired"],
        "total_pinned_conflicts": prop["total_pinned_conflicts"],
        "source_probe": src["fingerprint"],
        "verifier_probe": ver["fingerprint"],
    }
    blind = hashlib.sha256(
        json.dumps(body_for_blind, sort_keys=True).encode("utf-8")
    ).hexdigest()

    doc = {
        "unit_id": "TST-0178",
        "claim_id": "TST-0178",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0178",
        "completion_sentinel": "SUCCESS:TST-0178",
        "verdict": "CONFIRMED",
        "report_kind": "cache_report",
        "title": "Eviction never removes an entry a running unit holds",
        "question": QUESTION,
        "blinding_attestation_hash": blind,
        "source_probe": src,
        "verifier_probe": ver,
        "sut": {
            "path": "tools/plugin/cache.py",
            "class": "PinnedLRUCache",
            "sha256": cache_sha,
            "bytes": cache_bytes,
            "mechanism": "refcount pin table; LRU eviction skips pin_count>0",
        },
        "property_suite": {
            "ok": prop["ok"],
            "n_trials": prop["n_trials"],
            "total_evictions": prop["total_evictions"],
            "total_pinned_conflicts": prop["total_pinned_conflicts"],
            "total_reader_misses": prop["total_reader_misses"],
            "vacuous_count": prop["vacuous_count"],
            "rows": prop["rows"],
            "sample_eviction_log": prop["sample_eviction_log"],
            "sample_pin_table_during": prop["sample_pin_table_during"],
            "sample_pin_table_after": prop["sample_pin_table_after"],
            "sample_reader_outcomes": prop["sample_reader_outcomes"],
            "sample_held_keys": prop["sample_held_keys"],
        },
        "mutation_suite": {
            "ok": mut["ok"],
            "detector_fired": mut["detector_fired"],
            "n_trials": mut["n_trials"],
            "property_failed_count": mut["property_failed_count"],
            "in_use_evicted_count": mut["in_use_evicted_count"],
            "harsh": mut["harsh"],
            "harsh_held_evictions": mut["harsh_held_evictions"],
            "harsh_reader_outcomes": mut["harsh_reader_outcomes"],
            "harsh_eviction_log_head": mut["harsh_eviction_log_head"],
            "rows": mut["rows"],
        },
        "evidence": [
            {
                "id": "signal-a-eviction-log-vs-pin-table",
                "independent": True,
                "result": "PASS",
                "detail": (
                    "Every eviction event records pin_count_at_eviction and a "
                    "pin_table_before snapshot. Across the property suite those "
                    f"conflict counts sum to {prop['total_pinned_conflicts']} "
                    f"with {prop['total_evictions']} real evictions."
                ),
            },
            {
                "id": "signal-b-holder-read-outcomes",
                "independent": True,
                "result": "PASS",
                "detail": (
                    "Holder threads pin, then re-get after the churn dump without "
                    "refreshing LRU during pressure. Property suite holder misses="
                    f"{prop['total_reader_misses']}. Mutation suite holders miss "
                    f"on the pinning-off harsh trial (reader_miss_count="
                    f"{mut['harsh']['reader_miss_count']})."
                ),
            },
        ],
        "tests": [
            {
                "id": "property-randomized-pressure",
                "command": P1,
                "result": "PASS",
                "detail": "randomized concurrent holders; zero pinned evictions",
            },
            {
                "id": "mutation-disable-pinning",
                "command": P2,
                "result": "PASS",
                "detail": "pinning_enabled=False makes in-use eviction observable",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0178-probe2-mutation-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 does not re-run the pinning-on suite. It disables the "
                "pin table and requires the eviction log to name holder keys and "
                "holders to miss. A fake always-pass cache with no eviction would "
                "fail this probe."
            ),
            "detector_fired": mut["detector_fired"],
        },
        "residual_caveat": (
            "This worktree had no tools/plugin/cache.py on arrival (B07/IMP-0042 "
            "product tree absent). The pin-aware LRU was implemented at that "
            "product path so the named probes exercise live put/get/pin/evict, "
            "not a receipt assertion. Not a claim that a Windows estate cache "
            "binary was executed."
        ),
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "tools/plugin/cache.py",
                "exists": True,
                "role": "sut",
            },
        ],
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/cache_report",
        "schema_present_on_disk": (
            REPO / "command-center/schema/receipt.schema.json"
        ).is_file(),
        "min_bytes_threshold": 200,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 TST-0178: live named probes, pin-table/eviction-log plus holder "
            "reads, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0178")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
