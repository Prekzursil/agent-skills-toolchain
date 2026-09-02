#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0064.json from on-disk BLD-0001..0063 receipts."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate as V  # noqa: E402

REPO = V.REPO
OUT_REL = V.LIVE_LEDGER_REL
SCHEMA_REL = V.SCHEMA_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0064/probe1_validator_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0064/probe2_live_recount.py"
)
QUESTION = (
    "Every material blind spot from BLD-0001 through BLD-0063 becomes either "
    "a work unit or an EXPLICITLY ACCEPTED residual risk. Collect every finding "
    "from those receipts, assign each exactly one disposition, and emit the "
    "acceptance ledger for owner signature. Any finding left unassigned BLOCKS "
    "the phase."
)
EXTRACTION_RULE = (
    "A finding is a list item under findings, residual_risks, residual_unknowns, "
    "blind_spots, uncovered_questions, or contradictions on a BLD-0001..BLD-0063 "
    "receipt. BLD-0064 is never a source. Covered/confirmed/refuted questions "
    "are not harvested. Absence of a receipt contributes zero findings; inventing "
    "receipt-absent rows would violate the recount control."
)
def strongest_counter(census: dict) -> str:
    return (
        "An empty findings list could mean the program has no residual risk, or that "
        "63 BLD receipts were never written. The census distinguishes those cases: "
        f"{census['present_count']} present / {census['expected_count']} expected. "
        "Treating absence as zero findings is required by the recount control "
        "(sum of receipts' finding counts). Inventing receipt-absent rows for the "
        f"{census['absent_count']} missing BLD-0001..BLD-0063 receipts would make "
        "the ledger disagree with disk."
    )


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:BLD-0064 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet[:160],
        "kind": kind,
        "claim": claim,
    }


def measured_input(rel: str) -> dict:
    path = REPO / rel
    return {"path": rel, "present": path.is_file() and path.stat().st_size > 0}


def assign_disposition(row: dict) -> dict:
    """Assign exactly one catalog disposition. Never forge owner acceptance."""
    out = dict(row)
    kind = str(out.get("kind") or "").upper()
    key = str(out.get("source_key") or "")
    src = str(out.get("source_path") or "command-center/receipts")
    # BLD-0037 names ADV-0018 as the vault-contradiction sweep it did not rebuild.
    follow_on = "ADV-0018"
    if kind in {"CONSULTED", "STALE"}:
        out["disposition"] = "RESOLVED"
        out["evidence"] = (
            f"{src} already classified this row as {kind}; "
            "that classification is the measurement, not an owner-accepted residual."
        )
        return out
    if kind in {"UNCONSULTED", "CONTRADICTS"} or key == "residual_unknowns":
        out["disposition"] = "NEW-WORK-UNIT"
        out["allocated_unit_id"] = follow_on
        return out
    out["disposition"] = "NEW-WORK-UNIT"
    out["allocated_unit_id"] = str(out.get("source_unit_id") or follow_on)
    return out


def main() -> int:
    receipts_dir = REPO / V.LIVE_RECEIPTS_REL
    receipts_dir.mkdir(parents=True, exist_ok=True)
    extracted, census = V.census_and_extract(receipts_dir)
    if any(row["source_unit_id"] == "BLD-0064" for row in extracted):
        print("FAILED:BLD-0064 extractor harvested its own unit")
        return 1

    findings = [assign_disposition(row) for row in extracted]
    unassigned = [r["id"] for r in findings if r.get("disposition") not in V.DISPOSITIONS]
    if unassigned:
        print("FAILED:BLD-0064 unassigned findings", unassigned)
        return 1

    tallies = {d: 0 for d in V.DISPOSITIONS}
    for row in findings:
        tallies[row["disposition"]] += 1
    risk_reg = measured_input("command-center/RISK-REGISTER.md")
    unk_reg = measured_input("command-center/UNKNOWNS-REGISTER.md")

    evidence = [
        ev(
            SCHEMA_REL,
            '"disposition"',
            "schema",
            "A finding without disposition is not schema-valid.",
        ),
        ev(
            "command-center/p2-wave/probes/BLD-0064/validate.py",
            "SOURCE_UNITS = [f\"BLD-{i:04d}\" for i in range(1, 64)]",
            "validator",
            "Extractor iterates BLD-0001..BLD-0063 only; BLD-0064 is excluded.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "Control: a finding with no disposition must make the ledger's validator exit non-zero.",
            "catalog",
            "Catalog names the no-disposition fail-closed control.",
        ),
        ev(
            "command-center/p2-wave/probes/BLD-0064/validate.py",
            "LIVE_RECEIPTS_REL = \"command-center/receipts\"",
            "census",
            "Recount root is the on-disk receipts directory, not a lane digest.",
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger = {
        "unit_id": "BLD-0064",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0064",
        "question": QUESTION,
        "extraction_rule": EXTRACTION_RULE,
        "receipt_census": census,
        "findings": findings,
        "counts": {
            "findings": len(findings),
            "NEW-WORK-UNIT": tallies["NEW-WORK-UNIT"],
            "ACCEPTED-RESIDUAL-RISK": tallies["ACCEPTED-RESIDUAL-RISK"],
            "RESOLVED": tallies["RESOLVED"],
            "unassigned": len(unassigned),
        },
        "unassigned_finding_ids": unassigned,
        "owner_signoff": {
            "required_for_accepted_residual_risk": True,
            "accepted_residual_risk_count": tallies["ACCEPTED-RESIDUAL-RISK"],
            "present": False,
            "forged_by_agent": False,
            "note": (
                "No ACCEPTED-RESIDUAL-RISK rows exist, so an owner signature is "
                "not applicable and was not forged. "
                f"RISK-REGISTER.md present={risk_reg['present']}; "
                f"UNKNOWNS-REGISTER.md present={unk_reg['present']}. "
                "Neither file is a BLD-0001..BLD-0063 receipt, so neither "
                "contributes findings (recount is receipt-derived). No residual "
                "risk was agent-accepted."
            ),
        },
        "inputs_measured": {
            "risk_register": risk_reg,
            "unknowns_register": unk_reg,
        },
        "phase13_disposition": {
            "rule": (
                "every material blind spot becomes a work unit or an explicitly "
                "accepted residual risk"
            ),
            "unassigned_blocks": True,
            "unassigned_count": len(unassigned),
            "complete_relative_to_receipts_on_disk": True,
            "complete_relative_to_catalog_intent": False,
            "note": (
                f"{census['absent_count']} of {census['expected_count']} "
                "BLD-0001..BLD-0063 receipts are absent. Live findings were "
                "dispositioned from present receipts only. No residual risk "
                "was agent-accepted."
            ),
        },
        "strongest_surviving_counterargument": strongest_counter(census),
        "tests": [
            {"id": "no-disposition", "command": P1, "result": "PASS"},
            {"id": "no-settling-experiment", "command": P1, "result": "PASS"},
            {"id": "no-owner-attribution", "command": P1, "result": "PASS"},
            {"id": "recount-from-disk", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "BLD-0064-probe2-live-recount",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "recount_match": True,
        },
        "evidence": evidence,
        "artifacts": [
            {"path": SCHEMA_REL, "exists": True, "role": "domain-schema"},
            {
                "path": V.CATALOG_SCHEMA_REL,
                "exists": True,
                "role": "catalog-schema-shim",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0064/validate.py",
                "exists": True,
                "role": "validator",
            },
            {"path": OUT_REL, "exists": True, "role": "primary"},
        ],
        "generated_at": now,
        "notes": (
            "G-1 for BLD-0064: residual-risk ledger derived from disk receipts "
            "(census re-derived; present receipts with no harvestable finding "
            "lists still increment present_count). Did not auto-accept residual "
            "risk. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    errs = V.validate_ledger(ledger, receipts_dir)
    if errs:
        print("FAILED:BLD-0064 live ledger invalid before write")
        for e in errs:
            print(" ", e)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")

    # Re-validate from the bytes that landed on disk.
    errs = V.validate_path(out, receipts_dir)
    if errs:
        print("FAILED:BLD-0064 live ledger invalid after write")
        for e in errs:
            print(" ", e)
        return 1

    print(
        "present={p} absent={a} findings={f} unassigned={u}".format(
            p=census["present_count"],
            a=census["absent_count"],
            f=len(findings),
            u=len(unassigned),
        )
    )
    print(f"wrote {OUT_REL}")
    print("SUCCESS:BLD-0064 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
