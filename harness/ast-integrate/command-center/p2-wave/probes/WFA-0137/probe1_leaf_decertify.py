#!/usr/bin/env python3
"""Probe 1: decertify a leaf blueprint; every transitive pack is re-gated.

Signal A (this file): reverse-BFS over CONSUMERS embed lists, computed here,
not imported from engine.propagate_re_gate.
Signal B (engine.serve): forward embed walk + certification ledger; dependents
must refuse, unrelated packs must still serve, nobody serves the decertified
bytes.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "foundry"))

from revocation.engine import (  # noqa: E402
    RE_GATE_REQUIRED,
    apply_regression,
    fresh_world,
    serve,
    serving_decertified_version,
)
from revocation.graph import CONSUMERS, LEAF_ID  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0137-decertification-path-when-a-certified-workflow-later.json"


def local_downstream(start: str) -> set[str]:
    """Independent reverse-BFS. Does not call engine.propagate_re_gate."""
    rev: dict[str, list[str]] = defaultdict(list)
    for cid, spec in CONSUMERS.items():
        for embedded in spec["embeds"]:
            rev[embedded].append(cid)
    seen = {start}
    out: set[str] = set()
    q = deque([start])
    while q:
        cur = q.popleft()
        for cid in rev.get(cur, []):
            if cid not in seen:
                seen.add(cid)
                out.add(cid)
                q.append(cid)
    return out


def main() -> int:
    expected = local_downstream(LEAF_ID)
    world = fresh_world()
    ev = apply_regression(world, LEAF_ID, passed=False, run_id="probe1-fail")
    got = set(ev.re_gated)
    if got != expected:
        print(f"FAILED:WFA-0137-probe1 propagate {sorted(got)} != local {sorted(expected)}")
        return 1
    if not ev.applied or ev.new_status != "DECERTIFIED":
        print("FAILED:WFA-0137-probe1 leaf not DECERTIFIED")
        return 1

    packs = {cid for cid, spec in CONSUMERS.items() if spec["kind"] == "pack"}
    dep_packs = sorted(p for p in packs if p in expected)
    unrel_packs = sorted(p for p in packs if p not in expected)
    if not dep_packs:
        print("FAILED:WFA-0137-probe1 no dependent packs")
        return 1
    for p in dep_packs:
        if world.consumers[p].status != RE_GATE_REQUIRED:
            print(f"FAILED:WFA-0137-probe1 pack {p} not re-gated")
            return 1
        sr = serve(world, p)
        if sr.ok:
            print(f"FAILED:WFA-0137-probe1 pack {p} still serving")
            return 1
        if serving_decertified_version(world, p, LEAF_ID):
            print(f"FAILED:WFA-0137-probe1 pack {p} served decertified bytes")
            return 1
    for p in unrel_packs:
        if world.consumers[p].status == RE_GATE_REQUIRED:
            print(f"FAILED:WFA-0137-probe1 unrelated pack {p} re-gated")
            return 1
        sr = serve(world, p)
        if not sr.ok:
            print(f"FAILED:WFA-0137-probe1 unrelated pack {p} refused {sr.reason}")
            return 1

    any_bad = False
    for cid in CONSUMERS:
        if serving_decertified_version(world, cid, LEAF_ID):
            any_bad = True
    if any_bad:
        print("FAILED:WFA-0137-probe1 a consumer served the decertified version")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:WFA-0137" not in text:
            print("FAILED:WFA-0137-probe1 sentinel absent in artifact")
            return 1
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:WFA-0137-probe1 artifact state {doc.get('state')}")
            return 1
        art_packs = set(doc.get("re_gated", {}).get("packs") or [])
        if art_packs != set(dep_packs):
            print(f"FAILED:WFA-0137-probe1 artifact packs {sorted(art_packs)} != {dep_packs}")
            return 1

    doc = {
        "probe": "probe1-leaf-decertify",
        "unit_id": "WFA-0137",
        "leaf": LEAF_ID,
        "dependent_packs": dep_packs,
        "unrelated_packs": unrel_packs,
        "re_gated_consumers": sorted(expected),
        "any_consumer_serving_decertified": False,
        "pass": True,
    }
    print(json.dumps(doc, sort_keys=True))
    print(
        f"leaf={LEAF_ID} dep_packs={len(dep_packs)} unrel_packs={len(unrel_packs)} "
        f"re_gated={len(expected)}"
    )
    print("SUCCESS:WFA-0137-probe1 leaf decertify; dependent packs re-gated; serve closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
