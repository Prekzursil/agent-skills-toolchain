#!/usr/bin/env python3
"""Probe 1: tor class without owner flag fails closed (owner-blocked).

Signal (1) of IMP-0137: a tor-requesting fixture without the flag returns
owner-blocked, not a partial result. Mixed-class requests must not silently
drop public-tor and keep the rest. No live onion connection is made.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.research import SourceRequest, run_research_stage  # noqa: E402
from agentspec.source_policy import (  # noqa: E402
    OWNER_FLAG_PUBLIC_TOR,
    SOURCE_CLASSES,
    TOR_CLASS,
)
from agentspec.spec import ReceiptSpec, WorkUnit  # noqa: E402


def _unit(uid: str, **kwargs: object) -> WorkUnit:
    return WorkUnit(
        id=uid,
        prompt="IMP-0137 research-stage fixture",
        timeout_s=1800,
        receipt=ReceiptSpec(fmt="json", required_fields=("status",)),
        **kwargs,  # type: ignore[arg-type]
    )


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0137-probe1 {msg}")
    return 1


def silent_subset(requests: list[SourceRequest]) -> list[str]:
    """The forbidden degradation: drop tor, keep the rest."""
    return [
        r.source_class
        for r in requests
        if r.source_class not in {"public-tor", "tor", "onion"}
    ]


def main() -> int:
    evidence: dict = {
        "probe": "probe1_tor_fail_closed",
        "source_classes": sorted(SOURCE_CLASSES),
        "cases": [],
    }

    mixed = [
        SourceRequest("code", locator="repo://example"),
        SourceRequest("public-tor", locator="onion://example.onion"),
    ]

    # Case A: tor-requesting fixture, no owner flag, public-tor not even declared.
    unit_a = _unit("IMP-0137-fix-tor-undeclared")
    out_a = run_research_stage(unit_a, [SourceRequest("public-tor")], dry_run=True)
    evidence["cases"].append(
        {
            "id": "A-tor-undeclared-no-flag",
            "status": out_a.status,
            "results": len(out_a.results),
            "violation_id": out_a.violation_id,
            "egress_attempts": out_a.egress_attempts,
            "loud": out_a.loud,
            "partial": out_a.partial,
        }
    )
    if out_a.status != "owner-blocked":
        return _fail(f"A status={out_a.status} want owner-blocked")
    if out_a.results:
        return _fail(f"A returned {len(out_a.results)} results (partial)")
    if out_a.violation_id != "source-class-owner-blocked":
        return _fail(f"A violation_id={out_a.violation_id}")
    if out_a.egress_attempts != 0:
        return _fail(f"A egress_attempts={out_a.egress_attempts} (must be zero)")
    if "SOURCE-CLASS-UNAVAILABLE" not in out_a.message:
        return _fail("A message was not loud about unavailability")
    if out_a.partial:
        return _fail("A marked partial")

    # Case B: unit lists public-tor in allowed_classes but still no owner flag.
    unit_b = _unit(
        "IMP-0137-fix-tor-listed",
        source_policy=("code", "public-tor"),
    )
    out_b = run_research_stage(unit_b, mixed, dry_run=True)
    evidence["cases"].append(
        {
            "id": "B-mixed-listed-no-flag",
            "status": out_b.status,
            "results": len(out_b.results),
            "violation_id": out_b.violation_id,
            "egress_attempts": out_b.egress_attempts,
            "would_silent_subset": silent_subset(mixed),
        }
    )
    if out_b.status != "owner-blocked":
        return _fail(f"B status={out_b.status} want owner-blocked")
    if out_b.results:
        return _fail("B mixed request returned a partial harvest")
    if [h.source_class for h in out_b.results] == silent_subset(mixed):
        return _fail("B matched the silent-subset degradation")
    if out_b.egress_attempts != 0:
        return _fail("B consulted egress on an owner-blocked request")
    if "silent subset" not in out_b.message.lower():
        return _fail("B did not say it refuses a silent subset")

    # Case C: onion alias without flag.
    out_c = run_research_stage(
        _unit("IMP-0137-fix-onion-alias"),
        [SourceRequest("onion")],
        dry_run=True,
    )
    evidence["cases"].append({"id": "C-onion-alias", "status": out_c.status})
    if out_c.status != "owner-blocked" or out_c.results:
        return _fail(f"C status={out_c.status} results={len(out_c.results)}")

    # Case D both-states: code-only request without tor must be allowed.
    out_d = run_research_stage(
        _unit("IMP-0137-fix-code-only"),
        [SourceRequest("code", locator="repo://ok")],
        dry_run=True,
    )
    evidence["cases"].append(
        {
            "id": "D-code-only-control",
            "status": out_d.status,
            "results": [h.payload for h in out_d.results],
        }
    )
    if out_d.status != "allowed" or len(out_d.results) != 1:
        return _fail(f"D control failed status={out_d.status}")
    if out_d.results[0].payload != "DRY-RUN":
        return _fail("D did not stay on dry-run")

    # Case E both-states: owner flag + public-tor in allowed → not owner-blocked.
    unit_e = _unit(
        "IMP-0137-fix-tor-enabled",
        source_policy=("code", "public-tor"),
        owner_flags=(OWNER_FLAG_PUBLIC_TOR,),
    )
    out_e = run_research_stage(
        unit_e, [SourceRequest("public-tor", locator="dry")], dry_run=True
    )
    evidence["cases"].append(
        {
            "id": "E-tor-with-flag",
            "status": out_e.status,
            "results": len(out_e.results),
            "violation_id": out_e.violation_id,
        }
    )
    if out_e.status == "owner-blocked":
        return _fail("E with owner flag still owner-blocked")
    if out_e.status != "allowed":
        return _fail(f"E status={out_e.status} want allowed (dry-run)")
    if out_e.results[0].source_class != TOR_CLASS:
        return _fail("E did not canonicalize to public-tor")

    # Case F: unknown class fails closed, empty results.
    out_f = run_research_stage(
        _unit("IMP-0137-fix-unknown"),
        [SourceRequest("darkweb-markets")],
        dry_run=True,
    )
    evidence["cases"].append({"id": "F-unknown", "status": out_f.status})
    if out_f.status != "class-unknown" or out_f.results:
        return _fail(f"F status={out_f.status}")

    print(json.dumps(evidence, sort_keys=True))
    print(
        "owner-blocked empty=True mixed_not_partial=True "
        f"control_allowed={out_d.status} flagged={out_e.status}"
    )
    print("SUCCESS:IMP-0137-probe1 tor class without owner flag FAIL closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
