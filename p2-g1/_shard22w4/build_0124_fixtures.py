#!/usr/bin/env python3
"""Shard-22 wave-4 builder: WFA-0124 fixture library (7 blueprints).

Re-materializes the known-broken fixture library the detector controls run
against, per the recorded detector_controls numbers: 7 fixtures, exactly 3
measured executable, exactly 1 flagship identified, a NATIVE-unloadable
contradiction, a claimed-flagship-without-e2e demotion, a load-error with
concrete remaining_work, and a discovery-only row (consistent, not executable).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
LIB = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0124" / "fixtures" / "library"
LIB.mkdir(parents=True, exist_ok=True)
(LIB / "e2e").mkdir(exist_ok=True)
(LIB / "e2e" / "bp.ok.flagship.json").write_text(
    json.dumps({"blueprint": "bp.ok.flagship", "journey": "gold smoke to e2e",
                "verdict": "pass"}, indent=1) + "\n", encoding="utf-8", newline="\n")


def bp(id_, stages, *, state="", tier="", discovery=False, e2e=None):
    d = {
        "id": id_,
        "source_anchor": f"fixtures/library/{id_}.json",
        "stages": stages,
        "gates": ["g1"] if stages else [],
        "stop": {"condition": "all stages ok"} if stages else {},
        "dag": {"nodes": len(stages)},
        "topo": [s.get("id", "s") for s in stages] if stages else [],
        "roles": ["builder"],
        "discovery_only": discovery,
        "state": state,
        "quality_tier": tier,
    }
    if e2e:
        d["e2e"] = e2e
    return d


STAGES_OK = [{"id": "s1", "type": "action"}, {"id": "s2", "type": "action"},
             {"id": "s3", "type": "action"}]

fixtures = [
    bp("bp.ok.smoke", STAGES_OK),
    bp("bp.ok.flagship", STAGES_OK,
       tier="", e2e={"path": "command-center/p2-wave/probes/WFA-0124/fixtures/library/e2e/bp.ok.flagship.json",
                     "run_id": "e2e-001", "ok": True}),
    bp("bp.ok.recoverable", STAGES_OK),
    bp("bp.load-error.missing-stages", []),
    bp("bp.contradiction.native-unloadable", [], state="NATIVE"),
    bp("bp.flagship-claimed-no-e2e", STAGES_OK, tier="flagship"),
    bp("bp.discovery-only", [], discovery=True),
]

for f in fixtures:
    (LIB / f"{f['id']}.json").write_text(json.dumps(f, indent=1) + "\n",
                                         encoding="utf-8", newline="\n")

# smoke result artifacts for the three executable fixtures
for rid in ("bp.ok.smoke", "bp.ok.flagship", "bp.ok.recoverable"):
    (LIB / f"{rid}.result.json").write_text(
        json.dumps({"blueprint": rid, "smoke": "pass"}, indent=1) + "\n",
        encoding="utf-8", newline="\n")

print("fixture library written:", len(fixtures), "blueprints at", LIB)
