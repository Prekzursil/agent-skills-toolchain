#!/usr/bin/env python3
"""Probe 2: provenance of every borrowed A1-A8 mechanism.

Each mechanism must cite a source that exists on this tree and a section
that resolves. Citing a missing A3-A8 DESIGN.json is an overclaim and fails.
A planted cite of phase3/A3/DESIGN.json MUST fail (both-states).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hybrid as H  # noqa: E402

DESIGN = H.REPO / "command-center/phase3/A9/DESIGN.json"


def cite_tuple(mech: dict) -> tuple[str, str, str]:
    return (
        str(mech.get("architecture_id")),
        str(mech.get("source_path")),
        str(mech.get("source_section")),
    )


def main() -> int:
    if not DESIGN.is_file():
        print("FAILED:ARC-0059-probe2 DESIGN.json absent")
        return 1
    doc = json.loads(DESIGN.read_text(encoding="utf-8"))
    borrowed = H.design_get(doc, "borrowed_mechanisms")
    if not isinstance(borrowed, list) or len(borrowed) != 8:
        print(f"FAILED:ARC-0059-probe2 borrowed_mechanisms n={borrowed and len(borrowed)}")
        return 1

    ok_live, defects_live = H.check_provenance(borrowed)
    print(f"live_borrowed n={len(borrowed)} ok={ok_live}")
    for d in defects_live:
        print(f"  live_defect {d}")

    ok_kernel, defects_kernel = H.check_provenance(H.BORROWED)
    print(f"kernel_borrowed ok={ok_kernel}")
    for d in defects_kernel:
        print(f"  kernel_defect {d}")

    live_cites = {cite_tuple(m) for m in borrowed}
    kernel_cites = {cite_tuple(m) for m in H.BORROWED}
    match = live_cites == kernel_cites
    print(f"cites_match_kernel={match}")
    if not match:
        print(f"  only_live={sorted(live_cites - kernel_cites)}")
        print(f"  only_kernel={sorted(kernel_cites - live_cites)}")

    missing_design_cites = []
    for m in borrowed:
        path = str(m.get("source_path") or "")
        if path.startswith("command-center/phase3/A") and path.endswith("/DESIGN.json"):
            if not (H.REPO / path).is_file():
                missing_design_cites.append(path)
    print(f"cites_of_absent_design_json={missing_design_cites}")

    planted = copy.deepcopy(borrowed)
    for m in planted:
        if m.get("architecture_id") == "A3":
            # A3/DESIGN.json is now on this tree (ARC-0017 delivered). Plant a
            # dossier path that is actually absent so both-states still fires.
            m["source_path"] = "command-center/phase3/A3/MISSING-DOSSIER.json"
            m["source_section"] = "precedence.rule"
            m["dossier_on_this_tree"] = True
            m["absent_dossier"] = "command-center/phase3/A3/MISSING-DOSSIER.json"
            break
    ok_planted, defects_planted = H.check_provenance(planted)
    fired = (not ok_planted) and any(
        "absent" in d.lower() or "overclaim" in d.lower() or "missing" in d.lower()
        for d in defects_planted
    )
    print(f"planted_missing_dossier ok={ok_planted} fired_on_bad={fired}")
    for d in defects_planted[:8]:
        print(f"  planted {d}")

    if not (
        ok_live
        and ok_kernel
        and match
        and fired
        and not missing_design_cites
    ):
        print("FAILED:ARC-0059-probe2 provenance assertion")
        return 1
    print("SUCCESS:ARC-0059-probe2 provenance assertion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
