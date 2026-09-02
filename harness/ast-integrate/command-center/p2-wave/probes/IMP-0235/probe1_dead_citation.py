#!/usr/bin/env python3
"""Probe 1: planted dead citation is UNRESOLVED, not silently accepted (both-states).

Live fetchable citation is not UNRESOLVED. The naive mutant that assumes
unfetchable citations are valid disagrees with the honest auditor on the
planted dead row. Every citation is given a status (coverage == 1.0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402

REPO = F.REPO
sys.path.insert(0, str(REPO / "command-center"))

from research.blueprints.citation import UNRESOLVED  # noqa: E402
from research.blueprints.contract import omission_failures  # noqa: E402
from research.blueprints.registry import (  # noqa: E402
    fact_citation_audit_blueprint,
    registered,
)

UNIT = "IMP-0235"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    states = F.both_states_audit()
    print(json.dumps({"probe": "probe1-dead-citation", **states}, sort_keys=True, default=str))

    if states["coverage"] != 1.0:
        return fail(f"coverage={states['coverage']} want=1.0")
    if not states["dead_is_unresolved"]:
        return fail(f"planted dead status={states['dead_status']} want={UNRESOLVED}")
    if not states["live_not_unresolved"]:
        return fail(f"live citation status={states['live_status']} was UNRESOLVED")
    if states["assumed_valid_count"] != 0:
        return fail("honest auditor assumed a citation valid")
    if not states["naive_accepts_dead"]:
        return fail("naive mutant did not accept the dead citation (control silent)")
    if states["naive_dead_status"] == UNRESOLVED:
        return fail("naive mutant also marked UNRESOLVED; both-states do not diverge")
    if states["dead_status"] == states["naive_dead_status"]:
        return fail("honest and naive agree on the dead citation")

    bps = registered()
    if "fact-citation-audit" not in bps:
        return fail("fact-citation-audit failed to register")
    if set(bps) != {
        "evidence-map",
        "fact-citation-audit",
        "official-doc-audit",
        "source-code-archaeology",
    }:
        return fail(f"registered ids={sorted(bps)}")

    tokens = omission_failures(fact_citation_audit_blueprint())
    if any(v == "SILENT" for v in tokens.values()):
        return fail(f"omission silent {tokens}")
    if len(set(tokens.values())) < 6:
        return fail(f"omission tokens not distinct {tokens}")

    art = F.load_receipt()
    if art is None:
        return fail("receipt missing")
    text = F.ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0235" not in text:
        return fail("sentinel absent")
    if str(art.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {art.get('state')}")
    recorded = (art.get("citation_audit") or {}).get("dead_status")
    if recorded != UNRESOLVED:
        return fail(f"receipt dead_status={recorded} want={UNRESOLVED}")
    if (art.get("citation_audit") or {}).get("naive_accepts_dead") is not True:
        return fail("receipt did not record naive-mutant both-states divergence")

    print(
        f"dead_unresolved=True live_status={states['live_status']} "
        f"naive_dead={states['naive_dead_status']} coverage=1.0"
    )
    print("SUCCESS:IMP-0235-probe1 planted dead citation UNRESOLVED; live resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
