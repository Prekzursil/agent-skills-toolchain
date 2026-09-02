#!/usr/bin/env python3
"""Probe 1: stage-padded REJECT, genuine improvement ACCEPT, complement ACCEPT."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import schema_local as SL  # noqa: E402
from predicate import PREDICATE, digest_predicate, metric_values  # noqa: E402
from runner import pin_registry, score_registry  # noqa: E402

OUT = REPO / "command-center" / "foundry" / (
    "WFA-0130-pre-registered-fusion-acceptance-metric-set.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0130-probe1 {msg}")
    return 1


def main() -> int:
    registry = pin_registry(PREDICATE)
    pin_sha = registry["pin"]["sha256"]
    if registry["pin"]["seq"] != 0 or registry["runs"]:
        return fail("pin was not recorded before any score")
    if digest_predicate(PREDICATE) != pin_sha:
        return fail("live digest does not match pin")

    sources = F.all_sources()
    padded = score_registry(registry, F.stage_padded(), sources)
    improved = score_registry(registry, F.genuine_improvement(), sources)
    complement = score_registry(registry, F.complement_only(), sources)
    worse = score_registry(registry, F.worse(), sources)

    if padded.get("status") != "SCORED" or padded.get("decision") != "REJECT":
        return fail(f"stage-padded not REJECT: {padded.get('decision')}")
    if padded.get("seq") != 1 or padded.get("cited_pin_sha256") != pin_sha:
        return fail("first score did not cite pin at seq=1")
    if any(row["label"] != "FAIL" for row in padded["per_source"]):
        return fail(f"stage-padded labels {[r['label'] for r in padded['per_source']]}")
    if padded.get("fusion_stage_count") != 30:
        return fail("padded stage_count missing")
    if padded.get("stage_count_excluded") is not True:
        return fail("stage_count was admitted into the predicate")

    if improved.get("decision") != "ACCEPT":
        return fail(f"genuine improvement not ACCEPT: {improved}")
    if any(row["label"] != "OUTPERFORM" for row in improved["per_source"]):
        return fail(f"improvement labels {[r['label'] for r in improved['per_source']]}")
    if improved.get("fusion_stage_count") != 99:
        return fail("improvement with 99 stages should still ACCEPT")

    if complement.get("decision") != "ACCEPT":
        return fail(f"complement not ACCEPT: {complement}")
    if any(row["label"] != "COMPLEMENT" for row in complement["per_source"]):
        return fail(f"complement labels {[r['label'] for r in complement['per_source']]}")
    crecall = complement["per_source"][0]["complement_recall"]
    if crecall < 0.05:
        return fail(f"complement_recall {crecall} below MES")
    dc = complement["per_source"][0]["deltas"]["correctness"]
    if dc >= 0.05:
        return fail(f"complement correctness delta {dc} reached MES; not a complement path")

    if worse.get("decision") != "REJECT":
        return fail(f"worse not REJECT: {worse}")
    if any(row["label"] != "REGRESS" for row in worse["per_source"]):
        return fail(f"worse labels {[r['label'] for r in worse['per_source']]}")

    src = metric_values(F.source_a())
    pad_m = metric_values(F.stage_padded())
    for mid in ("correctness", "coverage", "recovery", "usability"):
        if abs(src[mid] - pad_m[mid]) > 1e-12:
            return fail(f"padded {mid} changed vs source")

    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    body = SL.registry_payload(doc)
    if "SUCCESS:WFA-0130" not in json.dumps(doc):
        return fail("catalog sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    pin = body.get("pin") or {}
    if pin.get("sha256") != pin_sha:
        return fail("artifact pin does not match live digest")
    if pin.get("seq") != 0 or pin.get("recorded_before_first_measurement") is not True:
        return fail("artifact pin was not recorded before first measurement")
    first = body.get("first_measurement") or {}
    if first.get("seq") != 1 or first.get("cited_pin_sha256") != pin_sha:
        return fail("artifact first measurement does not cite pin")
    if first.get("decision") != "REJECT":
        return fail("artifact first measurement was not the stage-padded REJECT")
    if body.get("kind") != "metric-registry":
        return fail("artifact kind is not metric-registry")

    print(
        f"pin={pin_sha} padded=REJECT improved=ACCEPT complement=ACCEPT worse=REJECT"
    )
    print(
        "SUCCESS:WFA-0130-probe1 both-states predicate; "
        "stage-padded rejected; pin cited before first score"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
