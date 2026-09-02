"""Instantiate C15/C16 against a fixture task and score board outcomes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def load_task(path: Path | None = None) -> dict[str, Any]:
    p = path or (HERE / "fixtures" / "task.json")
    return json.loads(p.read_text(encoding="utf-8"))


def instantiate(preset: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    return {
        "preset_id": preset["id"],
        "preset_name": preset["name"],
        "task_id": task["id"],
        "question": preset["question"],
        "roster": list(preset["roles"]),
        "protocol_schedule": list(preset["bound_protocols"]),
        "voting_method": preset["voting_method"],
        "stopping_expression": preset["stopping_expression"],
        "evidence_bar": preset["evidence_standard"]["bar"],
        "outcome_types": list(preset["outcome_types"]),
    }


def legal_outcome(task: dict[str, Any]) -> dict[str, Any]:
    pin = task.get("legal_pin")
    if not pin:
        return {
            "board": "ethics-legal-review",
            "outcome": "PROHIBITED",
            "may_we": False,
            "reason": "fail-closed-no-cited-instrument",
            "minority_report_filed": False,
        }
    if task.get("instrument_prohibits"):
        return {
            "board": "ethics-legal-review",
            "outcome": "PROHIBITED",
            "may_we": False,
            "reason": "cited-instrument-prohibits",
            "pin": pin,
            "minority_report_filed": bool(task.get("minority_report_filed")),
        }
    conditions = list(task.get("legal_conditions") or [])
    if conditions:
        return {
            "board": "ethics-legal-review",
            "outcome": "PERMITTED-CONDITIONAL",
            "may_we": True,
            "reason": "cited-instrument-permits-with-conditions",
            "pin": pin,
            "conditions": conditions,
            "minority_report_filed": False,
        }
    if task.get("legal_irreducible"):
        return {
            "board": "ethics-legal-review",
            "outcome": "IRREDUCIBLE-DISAGREEMENT",
            "may_we": False,
            "reason": "hung-permission-minority-report",
            "pin": pin,
            "minority_report_filed": True,
        }
    return {
        "board": "ethics-legal-review",
        "outcome": "PERMITTED",
        "may_we": True,
        "reason": "cited-instrument-permits",
        "pin": pin,
        "minority_report_filed": False,
    }


def risk_outcome(task: dict[str, Any]) -> dict[str, Any]:
    residual = task.get("residual_named")
    if not residual:
        return {
            "board": "risk-committee",
            "outcome": "PARK-UNQUANTIFIED",
            "residual_risk_named": False,
            "reason": "unnamed-residual",
        }
    disposition = str(task.get("risk_disposition") or "ACCEPT")
    row = {
        "board": "risk-committee",
        "outcome": disposition,
        "residual_risk_named": True,
        "residual": residual,
        "expected_loss_usd": task.get("expected_loss_usd"),
        "reason": "named-residual-scored",
    }
    if disposition == "MITIGATE":
        row["mitigations"] = list(task.get("mitigations") or [])
    if disposition == "TRANSFER":
        row["transfer_instrument"] = task.get("transfer_instrument")
    return row
