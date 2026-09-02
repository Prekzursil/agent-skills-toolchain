#!/usr/bin/env python3
"""Probe 1: score each degenerate strategy and rank it against reference outputs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402

ART = C.ART


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0085-probe1 {msg}")
    return 1


def main() -> int:
    live = C.ranking_bundle()
    summary = {
        "probe": live["probe"],
        "unit_id": live["unit_id"],
        "production_module_present": live["production_module_present"],
        "ranked": [
            {
                "label": r["label"],
                "kind": r["kind"],
                "rank": r["rank"],
                "total": r["total"],
                "substance": r["substance"],
            }
            for r in live["ranked"]
        ],
        "control_reference_order": live["control_reference_order"],
        "inversion_pairs": live["inversion_pairs"],
        "exploiting_strategies": live["exploiting_strategies"],
        "any_exploit": live["any_exploit"],
        "rederivable": live["rederivable"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.CATALOG_SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "ADV-0085":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    rec = doc.get("probe1_ranking") or {}
    rec_by = {r["label"]: r for r in rec.get("ranked") or [] if isinstance(r, dict)}
    if len(rec_by) != len(live["by_label"]):
        return fail(f"artifact ranking rows n={len(rec_by)}")
    for label, row in live["by_label"].items():
        got = rec_by.get(label) or {}
        if abs(float(got.get("total", -1)) - row["total"]) > 1e-6:
            return fail(f"total drifted for {label}")
        if int(got.get("rank", -1)) != int(row["rank"]):
            return fail(f"rank drifted for {label}")
    if rec.get("exploiting_strategies") != live["exploiting_strategies"]:
        return fail("exploiting_strategies drifted")
    if rec.get("any_exploit") != live["any_exploit"]:
        return fail("any_exploit drifted")
    order = live["control_reference_order"]
    if not order["pass"] and not order["already_inverted"]:
        return fail("reference-order control neither pass nor inverted")
    if not live["rederivable"]:
        return fail("score not rederivable from components")

    high = live["by_label"]["ref-high"]["total"]
    pad = live["by_label"]["deg-pad-anchors"]["total"]
    absn = live["by_label"]["deg-always-abstain"]["total"]
    print(
        f"ref_high={high} pad_anchors={pad} always_abstain={absn} "
        f"exploits={live['exploiting_strategies']} order_ok={order['pass']}"
    )
    print("SUCCESS:ADV-0085-probe1 degenerate versus reference rank")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
