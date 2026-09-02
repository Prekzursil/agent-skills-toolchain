#!/usr/bin/env python3
"""Probe 1: packer exit+message AND independent casefold set-size.

Does not import tools.plugin.pack.collision_groups. The packer is invoked as
a subprocess (signal a). Manifest paths are counted here (signal b).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0194.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0194-probe1 {msg}")
    return 1


def main() -> int:
    live = S.evaluate()
    sig_a = live["signal_a"]
    sig_b = live["signal_b"]

    if not live["pack_exists"]:
        return fail("tools/plugin/pack.py missing")

    for name in ("colliding", "declared_only", "eszett"):
        row = sig_a[name]
        if row["rc"] != 2:
            return fail(f"{name} packer rc={row['rc']} expected 2")
        if row["both_paths_named"] is not True:
            return fail(f"{name} packer message did not name both paths: {row['text_tail'][-300:]}")
        if row["output_exists"] is True:
            return fail(f"{name} wrote an archive after a collision")

    for name in ("colliding", "declared_only", "eszett"):
        row = sig_b[name]
        if row["raw_count"] <= row["folded_count"]:
            return fail(
                f"{name} independent set-size did not detect collision "
                f"raw={row['raw_count']} folded={row['folded_count']}"
            )
        if row["collision"] is not True:
            return fail(f"{name} independent collision flag false")

    if sig_b["eszett"]["lower_misses_casefold"] is not True:
        return fail("Straße/STRASSE collides under casefold but lower() would miss it; detector used lower()?")

    if not live["gates"]["signals_agree"]:
        return fail(f"signals disagree gates={live['gates']}")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        errs = S.artifact_ok(doc)
        if errs:
            return fail(",".join(errs))
        ev = {e.get("id"): e for e in (doc.get("evidence") or []) if isinstance(e, dict)}
        ev_a = ev.get("a") or {}
        ev_b = ev.get("b") or {}
        if ev_a.get("colliding_rc") != 2:
            return fail(f"artifact signal a colliding_rc={ev_a.get('colliding_rc')}")
        if ev_b.get("colliding_raw_count") != sig_b["colliding"]["raw_count"]:
            return fail("artifact signal b raw_count drift")
        if ev_b.get("colliding_folded_count") != sig_b["colliding"]["folded_count"]:
            return fail("artifact signal b folded_count drift")

    summary = {
        "probe": "probe1-packer-exit-and-setsize",
        "unit_id": "TST-0194",
        "colliding_rc": sig_a["colliding"]["rc"],
        "declared_only_rc": sig_a["declared_only"]["rc"],
        "eszett_rc": sig_a["eszett"]["rc"],
        "colliding_raw": sig_b["colliding"]["raw_count"],
        "colliding_folded": sig_b["colliding"]["folded_count"],
        "both_named": sig_a["colliding"]["both_paths_named"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"signal_a rc={sig_a['colliding']['rc']} named={sig_a['colliding']['both_paths_named']} "
        f"signal_b raw={sig_b['colliding']['raw_count']} folded={sig_b['colliding']['folded_count']}"
    )
    print("SUCCESS:TST-0194-probe1 packer exit+message and independent set-size")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
