#!/usr/bin/env python3
"""Probe 2: adversarial refuter — Asch rate is not-portable; fabricated fields rejected.

Independent of probe 1's artifact walk: re-inventories fields from live schemas
and refuses a detector that names private_judgment. The healthy fixture is the
same-run negative control (must stay silent).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detectors as D  # noqa: E402
import fixtures as F  # noqa: E402
from fields import inventory  # noqa: E402

OUT = REPO / "command-center/research/RES-0080.json"
UNIT = "RES-0080"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0080-probe2 {msg}")
    return 1


def main() -> int:
    inv = inventory()
    names = set(inv["names"])
    for banned in ("private_judgment", "trial_type", "ground_truth"):
        if banned in names or f"votes.{banned}" in names or f"events.{banned}" in names:
            return fail(f"{banned} unexpectedly present in inventory")

    asch = D.propose("asch_critical_trial_conformity_rate", D.ASCH_FIELDS, inv)
    if asch["portable"] or set(asch["missing_fields"]) != set(D.ASCH_FIELDS):
        return fail(f"Asch propose() {asch}")

    janis = D.propose(
        "janis_eight_symptom_checklist",
        ["morale", "illusion_of_invulnerability"],
        inv,
    )
    if janis["portable"]:
        return fail("Janis checklist must not be portable")

    np_catalog = D.not_portable_catalog(inv)
    asch_row = next(
        (r for r in np_catalog if r["id"] == "asch_critical_trial_conformity_rate"),
        None,
    )
    if asch_row is None or asch_row["portable"] or not asch_row.get("reason"):
        return fail("Asch not-portable row missing reason")

    healthy = D.run_all(F.healthy())
    if healthy["pathological"] or healthy["fired"]:
        return fail("healthy negative control fired")
    planted = D.run_all(F.instant_unanimity())
    if not planted["pathological"]:
        return fail("instant-unanimity planted state silent (vacuous detector)")

    if not OUT.is_file():
        return fail("research artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    listed = doc.get("not_portable_measures") or doc.get("not_portable") or []
    if not listed:
        return fail("artifact has no not-portable measure")
    reasons = []
    asch_named = False
    for row in listed:
        if not isinstance(row, dict):
            return fail("not-portable row is not an object")
        reason = str(row.get("reason") or "")
        if len(reason) < 24:
            return fail(f"{row.get('id')} not-portable reason too short")
        reasons.append(reason)
        ident = str(row.get("id") or "") + str(row.get("classical_measure") or "")
        if "asch" in ident.lower() or "asch" in reason.lower():
            asch_named = True
        if row.get("portable") is True:
            return fail(f"{row.get('id')} marked portable")
    if not asch_named:
        return fail("Asch-style conformity is not the named not-portable measure")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") not in {"PASS", "REFUTED", "PARTIAL"}:
        return fail("reviewer verdict missing")
    refuted = doc.get("refuted_claims") or reviewer.get("refuted_claims") or []
    if len(refuted) < 1:
        return fail("adversarial refuter recorded no REFUTED claims")

    report = {
        "probe": "probe2-not-portable-control",
        "unit_id": UNIT,
        "private_judgment_absent": True,
        "asch_portable": False,
        "asch_missing_fields": asch["missing_fields"],
        "janis_portable": False,
        "healthy_silent": True,
        "planted_instant_fires": True,
        "not_portable_count": len(listed),
        "asch_named_not_portable": True,
        "refuted_claim_count": len(refuted),
        "pass": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "asch_not_portable missing="
        f"{asch['missing_fields']} healthy_silent=True planted_fires=True"
    )
    print("SUCCESS:RES-0080-probe2 Asch rate marked not-portable; fabricated fields rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
