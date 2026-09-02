#!/usr/bin/env python3
"""Probe 1: live snapshot is captured before the router is armed; metrics recompute."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import bench as B  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0400.json"
SENTINEL = "SENTINEL:IMP-0400:ROUTER-BENCHMARK-PAIRED"
SCHEMA = REPO / "command-center/schema/benchmark-result.schema.json"


def live_imports_router() -> bool:
    src = (HERE / "live_baseline.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "router" or alias.name.startswith("router."):
                    return True
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "router" or mod.startswith("router."):
                return True
    return False


def ci_covers(block: dict, point: float) -> bool:
    return float(block["lo"]) <= float(point) <= float(block["hi"])


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:IMP-0400-probe1 receipt missing or tiny")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0400":
        print("FAILED:IMP-0400-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0400-probe1 self-declared", doc.get("state"))
        return 1
    if SENTINEL not in json.dumps(doc):
        print("FAILED:IMP-0400-probe1 sentinel absent")
        return 1
    if not SCHEMA.is_file():
        print("FAILED:IMP-0400-probe1 schema missing")
        return 1
    errs = S.error_messages(doc)
    if errs:
        print("FAILED:IMP-0400-probe1 schema", errs[0])
        return 1
    payload = S.domain(doc)
    if live_imports_router():
        print("FAILED:IMP-0400-probe1 live_baseline imports router")
        return 1

    live = B.run_protocol()
    if not live["baseline_capture"]["captured_before_router_armed"]:
        print("FAILED:IMP-0400-probe1 baseline not marked pre-arm")
        return 1
    seq = [e["sequence"] for e in live["events"]]
    if seq != [1, 2, 3, 4]:
        print("FAILED:IMP-0400-probe1 sequence", seq)
        return 1
    if live["events"][1]["step"] != "baseline_capture_end":
        print("FAILED:IMP-0400-probe1 step 2 is not capture end")
        return 1
    if live["events"][2]["step"] != "router_arm":
        print("FAILED:IMP-0400-probe1 step 3 is not router arm")
        return 1
    if live["anti_reconstruct"]["matches_captured_live"]:
        print("FAILED:IMP-0400-probe1 reconstruction equals live snapshot")
        return 1
    if (
        payload["baseline_capture"]["snapshot_sha256"]
        != live["baseline_capture"]["snapshot_sha256"]
    ):
        print("FAILED:IMP-0400-probe1 snapshot sha drifted from receipt")
        return 1
    if abs(B.max_metric_diff({"metrics": payload["metrics"]}, live)) > B.DETERMINISM_TOLERANCE:
        print("FAILED:IMP-0400-probe1 metrics drifted from receipt")
        return 1
    if live["corpus_meta"]["negative_fraction"] < 0.25:
        print("FAILED:IMP-0400-probe1 negative fraction")
        return 1

    top3 = B.always_top3_preds(B.CORPUS, B.CAPABILITIES, B.K)
    top3_m = B.metrics_for(top3, live["golds"], len(B.CAPABILITIES))
    if top3_m["precision_at_k"] >= 0.20:
        print("FAILED:IMP-0400-probe1 always-top-3 still scores well")
        return 1

    ci = payload["confidence_intervals"]
    for arm in ("live", "router"):
        point = payload["metrics"][arm]["precision_at_k"]
        if not ci_covers(ci[arm]["precision_at_k"], point):
            print("FAILED:IMP-0400-probe1 CI misses precision", arm, point)
            return 1

    ans = payload["exact_answer"]
    d = payload["metrics"]["delta"]
    beats = d["breadth"] > 0 and d["precision_at_k"] >= 0
    if bool(ans["beats_live_breadth_without_losing_precision"]) != beats:
        print("FAILED:IMP-0400-probe1 exact_answer disagrees with delta")
        return 1
    if abs(ans["breadth_delta"] - d["breadth"]) > 1e-12:
        print("FAILED:IMP-0400-probe1 breadth_delta mismatch")
        return 1
    if abs(ans["precision_at_k_delta"] - d["precision_at_k"]) > 1e-12:
        print("FAILED:IMP-0400-probe1 precision delta mismatch")
        return 1
    if payload["router_arm"]["sequence"] <= payload["baseline_capture"]["sequence"]:
        print("FAILED:IMP-0400-probe1 router armed at or before baseline")
        return 1
    if payload.get("kind") != "benchmark-result":
        print("FAILED:IMP-0400-probe1 report.kind", payload.get("kind"))
        return 1

    print(
        "paired_ok=True "
        f"neg={live['corpus_meta']['negative_fraction']:.4f} "
        f"live_p={payload['metrics']['live']['precision_at_k']:.4f} "
        f"router_p={payload['metrics']['router']['precision_at_k']:.4f} "
        f"breadth_d={d['breadth']:.4f} "
        f"beats={beats} "
        f"anti_reconstruct={live['anti_reconstruct']['matches_captured_live']}"
    )
    print("SUCCESS:IMP-0400-probe1 paired capture before arm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
