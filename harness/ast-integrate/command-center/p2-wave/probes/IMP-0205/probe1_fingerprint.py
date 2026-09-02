#!/usr/bin/env python3
"""Named probe 1: rehearsed rollback restores sources by structural fingerprint.

Mechanically: put a fused workflow IN SERVICE, roll it back, and require
fingerprint(restored) == fingerprint(original) for every source that entered
fuse() — not merely that lineage is internally consistent. Also: in-flight
payload fingerprints survive, deletion is refused, a tampered snapshot is
refused, and a lineage-stripped fusion is refused.

Runs across all eight fusion strategies so a single-strategy green cannot hide
a broken inverse.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.workflow.fusion_rollback import (  # noqa: E402
    RollbackRefused,
    STRATEGIES,
    decompose,
    fingerprint,
    rollback,
    refuse_deletion_as_rollback,
)
import scenario as S  # noqa: E402


def _refuse_ok(fn, code: str) -> bool:
    try:
        fn()
    except RollbackRefused as exc:
        return exc.code == code
    return False


def main() -> int:
    orig_fp = S.original_fingerprints()
    per_strategy = []
    for strategy in STRATEGIES:
        fusion_id = f"wf.fusion.{strategy}"
        svc, fusion = S.armed_service(strategy, fusion_id, lossy=False, enqueue=True)
        pre_payloads = {i["item_id"]: i["payload_fingerprint"] for i in svc.in_flight}
        if len(pre_payloads) != 2:
            print(f"FAILED:IMP-0205-probe1 expected 2 in-flight, got {len(pre_payloads)}")
            return 1
        serving_before = svc.serving[0]["id"]
        if serving_before != fusion_id:
            print("FAILED:IMP-0205-probe1 fusion was not in service")
            return 1
        result = rollback(svc, fusion_id)
        restored_fp = {w["id"]: fingerprint(w) for w in svc.serving}
        if set(restored_fp) != set(orig_fp):
            print(f"FAILED:IMP-0205-probe1 restored id set {sorted(restored_fp)} != {sorted(orig_fp)}")
            return 1
        mismatches = {
            sid: {"original": orig_fp[sid], "restored": restored_fp[sid]}
            for sid in orig_fp
            if orig_fp[sid] != restored_fp[sid]
        }
        if mismatches:
            print(f"FAILED:IMP-0205-probe1 fingerprint mismatch {json.dumps(mismatches)}")
            return 1
        post_payloads = {i["item_id"]: i["payload_fingerprint"] for i in svc.in_flight}
        if pre_payloads != post_payloads:
            print("FAILED:IMP-0205-probe1 in-flight payload fingerprints changed")
            return 1
        if {i["serving_id"] for i in svc.in_flight} != set(orig_fp):
            print("FAILED:IMP-0205-probe1 in-flight not remapped onto restored sources")
            return 1
        if fusion["id"] in {w["id"] for w in svc.serving}:
            print("FAILED:IMP-0205-probe1 fusion still serving after rollback")
            return 1
        per_strategy.append(
            {
                "strategy": strategy,
                "fingerprint_all_equal": True,
                "inflight_preserved": result["inflight_preserved"],
                "pairs": result["fingerprint_pairs"],
            }
        )

    # Negative: deletion is not rollback.
    if not _refuse_ok(
        lambda: refuse_deletion_as_rollback("wf.fusion.union_collapse"),
        "deletion-is-not-rollback",
    ):
        print("FAILED:IMP-0205-probe1 deletion-as-rollback was not refused")
        return 1

    # Negative: lineage-stripped fusion cannot decompose or roll back.
    svc, fusion = S.armed_service("union_collapse", "wf.fusion.stripped", enqueue=False)
    fusion_stripped = dict(fusion)
    fusion_stripped["lineage"] = {}
    svc.put_in_service(fusion_stripped)
    if not _refuse_ok(lambda: rollback(svc, "wf.fusion.stripped"), "lineage-absent"):
        print("FAILED:IMP-0205-probe1 lineage-stripped fusion was not refused")
        return 1
    if not _refuse_ok(lambda: decompose(fusion_stripped), "lineage-absent"):
        print("FAILED:IMP-0205-probe1 decompose(lineage-stripped) was not refused")
        return 1

    # Negative: tampered snapshot fails lineage fingerprint check.
    svc, fusion = S.armed_service("best_of_breed", "wf.fusion.tamper", enqueue=False)
    tampered = S.fusion_in_service("best_of_breed", "wf.fusion.tamper")
    tampered["lineage"]["sources"][0]["snapshot"]["stages"][0]["body"] = {"tampered": True}
    if not _refuse_ok(lambda: decompose(tampered), "lineage-fingerprint-mismatch"):
        print("FAILED:IMP-0205-probe1 tampered snapshot was not refused")
        return 1

    report = {
        "probe": "probe1-fingerprint-restore",
        "unit_id": "IMP-0205",
        "pass": True,
        "strategies_rehearsed": len(per_strategy),
        "strategies": [row["strategy"] for row in per_strategy],
        "original_fingerprints": orig_fp,
        "deletion_refused": True,
        "lineage_stripped_refused": True,
        "tampered_snapshot_refused": True,
        "inflight_payload_fingerprints_unchanged": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"strategies={len(per_strategy)}/8 fingerprint_equal=True "
        "deletion_refused=True tamper_refused=True inflight_ok=True"
    )
    print("SUCCESS:IMP-0205-probe1 rehearsed rollback restores sources by fingerprint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
