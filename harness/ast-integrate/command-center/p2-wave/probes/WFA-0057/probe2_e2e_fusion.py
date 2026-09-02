#!/usr/bin/env python3
"""Probe 2: end-to-end native → IR → fusion → render; independent of schema-only checks.

Walks rendered nodes and checks every native construct's anchor and licence_class
survived the fusion boundary. Both-states: drop/empty at fusion FIRES; good path SILENT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ir import ir_nodes  # noqa: E402
from pipeline import (  # noqa: E402
    both_states,
    collect_anchors,
    collect_licence_by_anchor,
    end_to_end,
    expected_native_anchors,
    expected_native_licence,
    fuse,
    load_native,
    render,
    translate,
)

ART = REPO / "command-center/wfa/WFA-0057-ir-provenance-carry.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0057-probe2 {msg}")
    return 1


def main() -> int:
    native_a = load_native("native_a.json")
    native_b = load_native("native_b.json")
    expected = expected_native_anchors(native_a) | expected_native_anchors(native_b)
    expected_lic = {}
    expected_lic.update(expected_native_licence(native_a))
    expected_lic.update(expected_native_licence(native_b))

    # Independent reconstruction: translate/fuse/render, then walk objects (not a survived:true flag).
    ir_a = translate(native_a)
    ir_b = translate(native_b)
    fused = fuse(ir_a, ir_b)
    rendered = render(fused)
    present = collect_anchors(rendered)
    missing = sorted(expected - present)
    if missing:
        return fail(f"rendered lost native anchors {missing}")
    lic_map = collect_licence_by_anchor(rendered)
    mismatched = sorted(a for a in expected if lic_map.get(a) != expected_lic[a])
    if mismatched:
        return fail(f"licence did not travel with anchor {mismatched}")

    fusion_nodes = [n for n in ir_nodes(fused) if n.get("kind") == "Fusion"]
    if len(fusion_nodes) != 1:
        return fail(f"fusion hop missing Fusion node count={len(fusion_nodes)}")
    rendered_fusion = [n for n in ir_nodes(rendered) if n.get("source_kind") == "Fusion"]
    if len(rendered_fusion) != 1:
        return fail("rendered output dropped the Fusion node")
    if fusion_nodes[0]["licence_class"] != "gpl-3.0":
        return fail(f"fused licence {fusion_nodes[0]['licence_class']} != gpl-3.0 (most-restrictive)")
    if native_a["licence_class"] == native_b["licence_class"]:
        return fail("fixtures do not span two licence classes; fusion would not stress carry")

    live_e2e = end_to_end()
    if not live_e2e["survived_every_hop"] or not live_e2e["crossed_fusion_boundary"]:
        return fail(f"e2e failed {live_e2e}")
    if not live_e2e["licence_travelled_with_anchor"]:
        return fail("licence did not travel")
    if "fuse" not in live_e2e["hops"] or "render" not in live_e2e["hops"]:
        return fail(f"hops {live_e2e['hops']}")

    states = both_states(fused)
    if not states["good_silent"]:
        return fail("good fused IR was not silent")
    if not states["planted_missing_fires"] or not states["planted_empty_fires"]:
        return fail("planted missing/empty anchor at fusion did not fire")
    if not states["planted_missing_licence_fires"] or not states["planted_empty_licence_fires"]:
        return fail("planted missing/empty licence at fusion did not fire")
    if not states["empty_as_firm_as_missing"]:
        return fail("empty-string mutant not as firm as missing mutant")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0057" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    e2e = doc.get("end_to_end") or {}
    if e2e.get("crossed_fusion_boundary") is not True:
        return fail("artifact does not record fusion boundary")
    if e2e.get("survived_every_hop") is not True:
        return fail("artifact survived_every_hop is not true")
    if int(e2e.get("native_anchor_count") or 0) != len(expected):
        return fail("artifact native_anchor_count != live expected set")
    bs = doc.get("both_states") or {}
    if bs.get("good_silent") is not True or bs.get("planted_missing_fires") is not True:
        return fail("artifact both_states does not match live")
    if bs.get("planted_empty_fires") is not True:
        return fail("artifact planted_empty_fires is not true")

    reviewer = {
        "reviewer_id": "WFA-0057-probe2-e2e-fusion-reviewer",
        "independent": True,
        "method": (
            "Re-derived expected native anchors from fixture JSON keys, "
            "then walked rendered nodes (not the schema validator, not a survived flag)."
        ),
        "verdict": "PASS",
        "expected_anchor_count": len(expected),
        "rendered_anchor_count": len(present),
        "fusion_nodes": 1,
        "fused_licence_class": fusion_nodes[0]["licence_class"],
    }
    payload = {
        "probe": "probe2-e2e-fusion",
        "unit_id": "WFA-0057",
        "computed_not_asserted": True,
        "crossed_fusion_boundary": True,
        "survived_every_hop": True,
        "licence_travelled_with_anchor": True,
        "native_anchor_count": len(expected),
        "both_states": {
            "good_silent": True,
            "planted_missing_fires": True,
            "planted_empty_fires": True,
        },
        "reviewer": reviewer,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"e2e_ok=True fusion=True anchors={len(expected)} "
        f"licence={fusion_nodes[0]['licence_class']} "
        "good_silent=True planted_missing_fires=True planted_empty_fires=True"
    )
    print("SUCCESS:WFA-0057-probe2 e2e-fusion licence-carry both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
