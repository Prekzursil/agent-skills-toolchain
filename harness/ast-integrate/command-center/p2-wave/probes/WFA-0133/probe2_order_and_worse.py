#!/usr/bin/env python3
"""Probe 2: independent order proof + FC-11333 recompute + mutation.

Does not trust probe1's narrative. Re-reads the persisted ledger and
recomputes worse-than-every-source from rows.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus  # noqa: E402
import ledger as L  # noqa: E402

ART = (
    REPO
    / "command-center/foundry/WFA-0133-source-baseline-before-fusion-ordering-invariant.json"
)
LEDGER = HERE / "live-ledger.json"
MARKER = HERE / "baselines-closed.marker"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0133-probe2 {msg}")
    return 1


def independent_worse(fusion: dict, sources: list[dict], registry: list[dict]) -> bool:
    if not sources:
        return False
    for spec in registry:
        mid = spec["id"]
        f = float(fusion[mid])
        vals = [float(s[mid]) for s in sources]
        if spec["higher_is_better"]:
            if not (f < min(vals)):
                return False
        else:
            if not (f > max(vals)):
                return False
    return True


def main() -> int:
    if not LEDGER.is_file() or LEDGER.stat().st_size <= 0:
        return fail("live-ledger.json missing; emit_artifact.py must run first")
    if not MARKER.is_file():
        return fail("baselines-closed.marker missing")
    if not ART.is_file():
        return fail("foundry artifact missing")
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    sources = [e for e in events if e.get("kind") == L.KIND_SOURCE]
    fusions = [e for e in events if e.get("kind") == L.KIND_FUSION]
    refusals = [e for e in events if e.get("kind") == L.KIND_REFUSAL]
    if len(fusions) != 30:
        return fail(f"fusion count {len(fusions)} != 30")
    unit_ids = sorted({e["merge_unit_id"] for e in fusions})
    if len(unit_ids) != 30:
        return fail(f"fusion unit cardinality {len(unit_ids)}")
    last_source_seq = max(e["seq"] for e in sources)
    first_fusion_seq = min(e["seq"] for e in fusions)
    last_source_ts = max(e["ts_ns"] for e in sources)
    first_fusion_ts = min(e["ts_ns"] for e in fusions)
    if last_source_seq >= first_fusion_seq:
        return fail("seq: a fusion precedes a source measure")
    if last_source_ts >= first_fusion_ts:
        return fail("ts_ns: a fusion precedes a source measure")
    for fu in fusions:
        peers = [s for s in sources if s["merge_unit_id"] == fu["merge_unit_id"]]
        if any(s["seq"] >= fu["seq"] for s in peers):
            return fail(f"source seq not < fusion seq for {fu['merge_unit_id']}")
    marker = json.loads(MARKER.read_text(encoding="utf-8"))
    live_sha = hashlib.sha256(LEDGER.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if marker.get("last_source_seq") != last_source_seq:
        return fail("marker last_source_seq != live last_source_seq")
    if marker.get("ledger_sha256") == live_sha:
        return fail("marker hash equals post-fusion ledger; fusions did not persist")
    st = MARKER.stat()
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    if mtime_ns > first_fusion_ts:
        return fail("marker mtime_ns after first fusion ts_ns")

    loaded = corpus.load_merge_units()
    worse_ids = []
    for unit in loaded["units"]:
        fu = next(e for e in fusions if e["merge_unit_id"] == unit["id"])
        src_m = [
            e["metrics"]
            for e in sources
            if e["merge_unit_id"] == unit["id"]
            and e["workflow_id"] in set(unit["sources_resolved"])
        ]
        if len(src_m) != len(unit["sources_resolved"]):
            return fail(f"baseline gap on {unit['id']}")
        indep = independent_worse(fu["metrics"], src_m, corpus.METRIC_REGISTRY)
        recorded = bool(fu.get("worse_than_every_source"))
        if indep != recorded:
            return fail(
                f"FC-11333 mismatch {unit['id']} indep={indep} recorded={recorded}"
            )
        if indep:
            worse_ids.append(unit["id"])
    planted = [u["id"] for u in loaded["units"] if u.get("planted_worse_than_every_source")]
    if worse_ids != planted:
        return fail(f"independent FC-11333 {worse_ids} != planted {planted}")

    art = json.loads(ART.read_text(encoding="utf-8"))
    if art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {art.get('state')}")
    if "SUCCESS:WFA-0133" not in json.dumps(art):
        return fail("sentinel absent from artifact")
    if len(art.get("merge_units") or []) != 30:
        return fail("artifact merge_units != 30")
    if int(art.get("answers", {}).get("merge_unit_count") or 0) != 30:
        return fail("answers.merge_unit_count != 30")

    with tempfile.TemporaryDirectory(prefix="wfa0133-p2-") as td:
        mutant = L.BaselineLedger(Path(td) / "mutant.json")
        victim = loaded["units"][1]
        mutant.measure_all_sources(victim)
        drop = victim["sources_resolved"][-1]
        mutant.events = [
            e
            for e in mutant.events
            if not (e.get("kind") == L.KIND_SOURCE and e.get("workflow_id") == drop)
        ]
        mutant.persist()
        refused = mutant.score_fusion(victim)
        if refused.get("accepted") or drop not in (refused.get("missing") or []):
            return fail(f"mutation did not refuse dropped source {drop}: {refused}")

    if refusals:
        return fail(f"main ledger has refusals after closed baselines: {len(refusals)}")

    out = {
        "fc11333_independent": worse_ids,
        "first_fusion_seq": first_fusion_seq,
        "last_source_seq": last_source_seq,
        "marker_mtime_ns": mtime_ns,
        "mutation_refused": True,
        "n_fusions": len(fusions),
        "n_sources": len(sources),
        "pass": True,
        "probe": "probe2-order-and-worse",
        "seq_ok": True,
        "ts_ok": True,
        "unit_id": "WFA-0133",
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:WFA-0133-probe2 order-proof FC-11333 mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
