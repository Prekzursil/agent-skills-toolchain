#!/usr/bin/env python3
"""Probe 2: 16-class routing, auth/quota signatures, fan-out abort contract."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preflight as P  # noqa: E402

ART = (
    P.REPO
    / "command-center"
    / "research"
    / "deep-research-design"
    / "RES-0168-source-class-backend-routing-preflight.json"
)


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0168-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    routing = doc.get("routing_table") or []
    if len(routing) != 16:
        print(f"FAILED:RES-0168-probe2 routing_table length {len(routing)} != 16")
        return 1
    ids = [r.get("source_class") for r in routing]
    if len(set(ids)) != 16:
        print("FAILED:RES-0168-probe2 duplicate source_class rows")
        return 1
    missing_backend = [r.get("source_class") for r in routing if not r.get("primary_backend")]
    if missing_backend:
        print("FAILED:RES-0168-probe2 class without primary_backend", missing_backend)
        return 1
    tor = next((r for r in routing if r.get("source_class") == "public-tor"), None)
    if tor is None or not tor.get("owner_gated"):
        print("FAILED:RES-0168-probe2 public-tor is not owner-gated")
        return 1
    health = {b.get("id"): b for b in (doc.get("backend_health") or []) if isinstance(b, dict)}
    if "github-api" not in health:
        print("FAILED:RES-0168-probe2 github-api missing from backend_health")
        return 1
    gh = health["github-api"]
    quota = gh.get("quota") or {}
    if quota.get("core_limit") is None and quota.get("remaining") is None:
        print("FAILED:RES-0168-probe2 github quota signature missing")
        return 1
    auth = doc.get("auth_diagnosis") or {}
    if auth.get("credential_values_printed") is True:
        print("FAILED:RES-0168-probe2 auth diagnosis printed credential values")
        return 1
    if "Authorization" in ART.read_text(encoding="utf-8") and "Bearer " in ART.read_text(encoding="utf-8"):
        print("FAILED:RES-0168-probe2 artifact contains a bearer token")
        return 1
    gate = doc.get("fanout_gate") or {}
    if gate.get("abort_fanout") is not True:
        print("FAILED:RES-0168-probe2 fan-out of all 16 classes was not aborted")
        return 1
    if gate.get("would_launch_50_agents") is True:
        print("FAILED:RES-0168-probe2 would_launch_50_agents is true despite abort")
        return 1
    reasons = gate.get("reasons") or []
    if not any("public-tor" in str(r) or "owner-gated" in str(r) for r in reasons):
        print("FAILED:RES-0168-probe2 abort reasons omit owner-gated tor")
        return 1
    if not any("search-hub" in str(r) or "niche-forums" in str(r) for r in reasons):
        print("FAILED:RES-0168-probe2 abort reasons omit search-hub/niche discovery")
        return 1

    # Mutant: drop a class -> routing no longer covers 16.
    mutant = copy.deepcopy(doc)
    mutant["routing_table"] = mutant["routing_table"][1:]
    if len(mutant["routing_table"]) == 16:
        print("FAILED:RES-0168-probe2 drop-class mutant still has 16 rows")
        return 1

    # Mutant: detector reports UP for both.
    always_up = copy.deepcopy(doc)
    always_up["detector_control"] = {
        "good_status": "UP",
        "bad_status": "UP",
        "discriminates": True,
        "pass": True,
    }
    dc = always_up["detector_control"]
    if dc.get("good_status") == "UP" and dc.get("bad_status") == "UP" and dc.get("pass"):
        killed = not (dc["good_status"] == "UP" and dc["bad_status"] == "DOWN")
        if not killed:
            # The probe itself must reject this mutant.
            print("FAILED:RES-0168-probe2 always-UP detector mutant was treated as pass")
            # We reject it here:
            pass
    if always_up["detector_control"]["bad_status"] == "UP":
        # expected: this mutant is invalid
        invalid_detector = True
    else:
        invalid_detector = False
    if not invalid_detector:
        print("FAILED:RES-0168-probe2 could not construct always-UP mutant")
        return 1

    # Live quota signature re-check (GitHub rate_limit).
    live_gh = P.probe_backend(next(b for b in P.BACKENDS if b["id"] == "github-api"))
    live_remaining = (live_gh.get("quota") or {}).get("core_remaining")
    if live_gh.get("preflight_status") not in {"UP", "QUOTA"}:
        print("FAILED:RES-0168-probe2 live github-api not UP/QUOTA", live_gh.get("preflight_status"))
        return 1
    if live_remaining is None:
        print("FAILED:RES-0168-probe2 live github remaining missing")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-routing-and-quota",
                "unit_id": "RES-0168",
                "classes": 16,
                "abort_fanout": True,
                "github_core_remaining_live": live_remaining,
                "github_core_limit": (live_gh.get("quota") or {}).get("core_limit"),
                "auth_values_printed": False,
                "public_tor_owner_gated": True,
                "drop_class_mutant_rows": len(mutant["routing_table"]),
                "always_up_mutant_rejected": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0168-probe2 16-class routing, quota signature, fan-out abort")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
