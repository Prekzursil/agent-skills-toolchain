#!/usr/bin/env python3
"""Named probe 2: independent recount of fixtures (does not call evaluate.decide).

Re-derives FIRE/SILENT from fixture JSON on disk with a local seat loop.
A disagreement with the author's expected_decision blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0081-executable-stopping-example-quality-gate-pass-and-unresolv.schema.json"
)

ROLE_REGISTRAR = "LoadBearingRegistrar"
ROLE_CERTIFIER = "ResolutionCertifier"
ROLE_QG = "QualityGateOperator"
EXPRESSION = (
    "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0081-probe2 {msg}")
    return 1


def has_role(roster: dict, pid: str | None, role: str) -> bool:
    if not pid:
        return False
    for p in roster.get("participants") or []:
        if p.get("id") == pid and role in (p.get("roles") or []):
            return True
    return False


def recount_unresolved(records: list, roster: dict) -> tuple[int, list[dict]]:
    """Independent seat loop. Dual-role records stay unresolved."""
    n = 0
    rows = []
    for rec in records:
        declared = bool(rec.get("declared_load_bearing"))
        if not declared:
            rows.append({"id": rec.get("id"), "counted": False, "reason": "not-declared"})
            continue
        author = rec.get("author_id")
        registrar = rec.get("declared_load_bearing_by")
        resolved = bool(rec.get("resolved"))
        cert = rec.get("resolved_by")
        evidence = rec.get("evidence_producer_id")
        dual = bool(registrar) and registrar == cert
        registrar_is_author = bool(registrar) and registrar == author
        cert_is_author = bool(cert) and cert == author
        cert_is_evidence = bool(cert) and cert == evidence
        role_reg = has_role(roster, registrar, ROLE_REGISTRAR)
        role_cert = has_role(roster, cert, ROLE_CERTIFIER)
        seats_ok = (
            bool(registrar)
            and not registrar_is_author
            and role_reg
            and (
                not resolved
                or (
                    bool(cert)
                    and not dual
                    and not cert_is_author
                    and not cert_is_evidence
                    and role_cert
                )
            )
        )
        if resolved and seats_ok:
            rows.append(
                {
                    "id": rec.get("id"),
                    "counted": False,
                    "reason": "resolved-seats-ok",
                    "dual_role": dual,
                }
            )
            continue
        reason = "open"
        if dual:
            reason = "dual-role-declare-and-resolve"
        elif resolved and not seats_ok:
            reason = "resolved-but-seats-fail"
        n += 1
        rows.append(
            {
                "id": rec.get("id"),
                "counted": True,
                "reason": reason,
                "dual_role": dual,
                "registrar": registrar,
                "resolved_by": cert,
            }
        )
    return n, rows


def effective_qg(state: dict) -> str:
    if state.get("quality_gate") != "PASS":
        return "FAIL"
    op = state.get("quality_gate_operator_id")
    roster = state.get("roster") or {}
    if not has_role(roster, op, ROLE_QG):
        return "FAIL"
    for rec in state.get("counterexamples") or []:
        if rec.get("declared_load_bearing") and rec.get("declared_load_bearing_by") == op:
            return "FAIL"
    return "PASS"


def independent_decision(state: dict) -> dict:
    derived, rows = recount_unresolved(
        list(state.get("counterexamples") or []),
        state.get("roster") or {},
    )
    qg = effective_qg(state)
    fired = qg == "PASS" and derived == 0
    return {
        "decision": "FIRE" if fired else "SILENT",
        "derived_unresolved": derived,
        "effective_quality_gate": qg,
        "claimed_unresolved": state.get("unresolved_load_bearing_counterexample"),
        "rows": rows,
    }


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0081" not in text:
        return fail("sentinel absent")
    art = json.loads(text)
    if art.get("expression_verbatim") != EXPRESSION:
        return fail("artifact expression mismatch")

    needed = [
        "FIRE.json",
        "SILENT-unresolved.json",
        "SILENT-quality-fail.json",
        "NEG-dual-role.json",
        "NEG-claimed-lie.json",
    ]
    table = []
    for name in needed:
        path = FIX / name
        if not path.is_file():
            return fail(f"fixture missing {name}")
        state = json.loads(path.read_text(encoding="utf-8"))
        got = independent_decision(state)
        want = state.get("expected_decision")
        if got["decision"] != want:
            return fail(
                f"{state.get('fixture_id')} recount {got['decision']} want {want} "
                f"derived={got['derived_unresolved']}"
            )
        table.append(
            {
                "fixture_id": state.get("fixture_id"),
                "expected": want,
                "recounted": got["decision"],
                "derived_unresolved": got["derived_unresolved"],
                "effective_quality_gate": got["effective_quality_gate"],
                "claimed_unresolved": got["claimed_unresolved"],
                "rows": got["rows"],
            }
        )

    dual = next(r for r in table if r["fixture_id"] == "NEG-dual-role")
    if dual["recounted"] != "SILENT" or dual["derived_unresolved"] != 1:
        return fail("dual-role negative control did not stay unresolved")
    if not any(row.get("dual_role") for row in dual["rows"]):
        return fail("dual-role flag not observed")

    lie = next(r for r in table if r["fixture_id"] == "NEG-claimed-lie")
    if lie["claimed_unresolved"] != 0 or lie["derived_unresolved"] != 1:
        return fail("claimed-lie control did not ignore claimed 0")
    if lie["recounted"] != "SILENT":
        return fail("claimed-lie did not stay SILENT")

    fire = next(r for r in table if r["fixture_id"] == "FIRE")
    silent = next(r for r in table if r["fixture_id"] == "SILENT-unresolved")
    if fire["recounted"] != "FIRE" or silent["recounted"] != "SILENT":
        return fail("both-states recount failed")

    print(json.dumps({"independent_recount": table}, indent=2, sort_keys=True))
    print(
        "recount FIRE=FIRE SILENT=SILENT NEG-dual-role=SILENT "
        "NEG-claimed-lie=SILENT"
    )
    print("SUCCESS:CNL-0081-probe2 independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
