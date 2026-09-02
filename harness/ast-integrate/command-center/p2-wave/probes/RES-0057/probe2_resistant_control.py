#!/usr/bin/env python3
"""Probe 2: at least one GAMING-RESISTANT check, with OSV as the control.

Uses the live Scorecard API capture: same repo, License/Security-Policy high,
Vulnerabilities=0 with osv.dev IDs. Mutants that regrade Vulnerabilities as
gameable, or drop resistant rows, must go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    ART_REL,
    REPO,
    api_differential,
    evaluate_all,
    load_json,
    mutant_drop_resistant,
    mutant_vuln_gameable,
    verify_artifact,
    verify_captures,
)
from taxonomy import SENTINEL  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0057-probe2 {msg}")
    return 1


def main() -> int:
    cap_fail = verify_captures()
    if cap_fail:
        print(json.dumps(cap_fail[:12], indent=2))
        return fail("captures")

    diff, diff_fail = api_differential()
    if diff_fail:
        print(json.dumps(diff_fail, indent=2))
        return fail("api-differential")
    if diff.get("vulnerabilities_score") != 0:
        return fail("Vulnerabilities score is not 0")
    if int(diff.get("license_score") or 0) < 8:
        return fail("License score is not high — both-states control missing")

    art = REPO / ART_REL
    if not art.is_file():
        return fail("artifact missing")
    doc = load_json(art)
    if SENTINEL not in art.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    grades = [g for g in doc.get("gameability_grades") or [] if isinstance(g, dict)]
    resistant = [g for g in grades if g.get("grade") in {"RESISTANT", "MIXED"}]
    if not resistant:
        return fail("no resistant row")
    vul = next((g for g in grades if g.get("id") == "scorecard.Vulnerabilities"), None)
    if not vul or vul.get("grade") != "RESISTANT":
        return fail("Vulnerabilities not RESISTANT")
    reason = str(vul.get("resistant_reason") or "")
    if "OSV" not in reason and "ListUnfixedVulnerabilities" not in reason:
        return fail("resistant reason does not cite OSV")

    if not verify_artifact(mutant_vuln_gameable(doc)):
        return fail("vuln-gameable mutant stayed green")
    if not verify_artifact(mutant_drop_resistant(doc)):
        return fail("drop-resistant mutant stayed green")

    report = evaluate_all(doc)
    print(
        json.dumps(
            {
                "probe": "probe2-resistant-control",
                "unit_id": "RES-0057",
                "resistant_n": len(resistant),
                "api_differential": diff,
                "vuln_gameable_mutant_red": True,
                "drop_resistant_mutant_red": True,
                "ok": report["ok"],
            },
            sort_keys=True,
        )
    )
    if not report["ok"]:
        print(json.dumps(report["failures"][:12], indent=2))
        return fail("evaluate_all")
    print(
        f"resistant_rows={len(resistant)} "
        f"License={diff.get('license_score')} "
        f"Vulnerabilities={diff.get('vulnerabilities_score')} "
        f"osv_ids={diff.get('vulnerabilities_n')}"
    )
    print("SUCCESS:RES-0057-probe2 gaming-resistant control (OSV) holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
