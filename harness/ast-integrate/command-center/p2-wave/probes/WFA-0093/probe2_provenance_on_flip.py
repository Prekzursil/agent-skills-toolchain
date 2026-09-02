#!/usr/bin/env python3
"""Probe 2: a flip must keep licence and provenance; dropping them is rejected.

Independent of probe 1's hash/spike machinery: re-reads candidate JSON and
compares licence/provenance byte-for-byte to each decision. A planted drop
of provenance on a flipped row must fail attribution_ok.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate as G  # noqa: E402

RAW = HERE / "probe2-provenance-on-flip.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0093-probe2 {msg}")
    return 1


def main() -> int:
    cands = G.load_candidates()
    result = G.run_gate(cands, G.load_spikes())
    decisions = result["decisions"]
    by_src = {c["id"]: c for c in cands}

    flips = [d for d in decisions if d["flipped"]]
    keeps = [d for d in decisions if not d["flipped"]]
    if not flips:
        return fail("no flips; provenance-on-flip is untested")
    if not keeps:
        return fail("no KEEP-REPAIR rows; keep-path copy is untested")

    for d in decisions:
        src = by_src[d["id"]]
        if not G.attribution_ok(src, d):
            return fail(f"attribution_ok failed on live row {d['id']}")
        if d["licence"] != src["licence"] or d["provenance"] != src["provenance"]:
            return fail(f"licence/provenance copy mismatch on {d['id']}")

    planted = G.drop_provenance(flips[0])
    if G.attribution_ok(by_src[flips[0]["id"]], planted):
        return fail("planted provenance drop was accepted (gate does not constrain)")

    missing_lic = dict(flips[0])
    missing_lic["licence"] = {"spdx": "", "source": ""}
    if G.attribution_ok(by_src[flips[0]["id"]], missing_lic):
        return fail("empty licence on flip was accepted")

    hist = result["histogram"]
    if hist["CLEAN-ROOM-REIMPLEMENT"] < 1 or hist["REBUILD-FROM-SPEC"] < 1:
        return fail(f"both flip targets not exercised: {hist}")
    if hist["REPAIR"] < 1:
        return fail(f"no REPAIR kept: {hist}")
    if sum(hist.values()) != 15:
        return fail(f"histogram does not cover 15: {hist}")

    doc = {
        "flips": len(flips),
        "keeps": len(keeps),
        "histogram": hist,
        "planted_drop_rejected": True,
        "empty_licence_rejected": True,
        "live_attribution_ok": True,
        "flip_ids": [d["id"] for d in flips],
        "pass": True,
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"flips={len(flips)} keeps={len(keeps)} "
        f"planted_drop_rejected=True histogram={hist}"
    )
    print("SUCCESS:WFA-0093-probe2 provenance-on-flip planted-drop-rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
