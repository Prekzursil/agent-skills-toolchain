#!/usr/bin/env python3
"""Probe 1: live ablate-and-remeasure vs published per-class tokens."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from measure import measure  # noqa: E402

ART = REPO / "command-center/research/RES-0017.json"
SENTINEL = (
    "SUCCESS:RES-0017 in the receipt AND a per-class byte and token "
    "attribution where at least one class is confirmed by an "
    "ablate-and-remeasure delta"
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0017-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:RES-0017-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "RES-0017":
        print("FAILED:RES-0017-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:RES-0017-probe1 self-declared", doc.get("state"))
        return 1

    live = measure()
    pub_occ = doc.get("occupancy") or {}
    live_occ = live["occupancy"]
    if live_occ["turn0_injected_tokens"] != pub_occ.get("turn0_injected_tokens"):
        print(
            "FAILED:RES-0017-probe1 occupancy tokens",
            live_occ["turn0_injected_tokens"],
            pub_occ.get("turn0_injected_tokens"),
        )
        return 1
    if live_occ["turn0_injected_bytes"] != pub_occ.get("turn0_injected_bytes"):
        print("FAILED:RES-0017-probe1 occupancy bytes")
        return 1
    if live_occ["tokens_cumulative"] == live_occ["turn0_injected_tokens"]:
        print("FAILED:RES-0017-probe1 cumulative collapsed into occupancy")
        return 1

    pub_rows = {r["class"]: r for r in doc.get("per_class") or []}
    live_rows = {r["class"]: r for r in live["per_class"]}
    if set(pub_rows) != set(live_rows) or len(pub_rows) < 4:
        print("FAILED:RES-0017-probe1 per_class set", sorted(pub_rows), sorted(live_rows))
        return 1
    for name, row in live_rows.items():
        pr = pub_rows[name]
        if row["injected_tokens"] != pr.get("injected_tokens"):
            print("FAILED:RES-0017-probe1 tokens", name, row["injected_tokens"], pr)
            return 1
        if row["injected_bytes"] != pr.get("injected_bytes"):
            print("FAILED:RES-0017-probe1 bytes", name)
            return 1

    abl = live["ablation"]
    pub_abl = doc.get("ablation") or {}
    if not abl["confirmed"] or pub_abl.get("confirmed") is not True:
        print("FAILED:RES-0017-probe1 ablation not confirmed")
        return 1
    if abl["class"] != pub_abl.get("class"):
        print("FAILED:RES-0017-probe1 ablation class", abl["class"], pub_abl.get("class"))
        return 1
    if abl["measured_occupancy_delta_tokens"] != pub_abl.get(
        "measured_occupancy_delta_tokens"
    ):
        print("FAILED:RES-0017-probe1 ablation delta tokens")
        return 1
    if abl["measured_occupancy_delta_tokens"] < 1:
        print("FAILED:RES-0017-probe1 ablation delta non-positive")
        return 1
    if not live["stability"]["stable"]:
        print("FAILED:RES-0017-probe1 stability")
        return 1
    if live["dominates_tokens"] != doc.get("dominates_tokens"):
        print("FAILED:RES-0017-probe1 dominates", live["dominates_tokens"])
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-ablate-remeasure",
                "unit_id": "RES-0017",
                "occupancy_tokens": live_occ["turn0_injected_tokens"],
                "occupancy_bytes": live_occ["turn0_injected_bytes"],
                "cumulative": live_occ["tokens_cumulative"],
                "dominates_tokens": live["dominates_tokens"],
                "ablate_class": abl["class"],
                "delta_tokens": abl["measured_occupancy_delta_tokens"],
                "delta_bytes": abl["measured_delta_bytes"],
                "confirmed": abl["confirmed"],
                "stable": live["stability"]["stable"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"ablate={abl['class']} delta_tokens={abl['measured_occupancy_delta_tokens']} "
        f"delta_bytes={abl['measured_delta_bytes']} dominates={live['dominates_tokens']}"
    )
    print("SUCCESS:RES-0017-probe1 ablate-and-remeasure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
