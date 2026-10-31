"""Charter completeness check (IMP-0356)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CHARTER_REQUIRED_OUTPUTS = (
    "positions",
    "idea_ledger",
    "argument_graph",
    "votes",
    "dissent",
    "unknowns",
    "experiments",
    "recommendation",
    "calibration",
)

_VACUOUS_MARKERS = ("TBD", "TODO", "FIXME", "placeholder", "n/a", "N/A")


def is_vacuous(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip()
        return (not s) or s in _VACUOUS_MARKERS or s.lower() in {"tbd", "todo", "none"}
    if isinstance(value, (list, dict, tuple, set)):
        if not value:
            return True
        if isinstance(value, dict):
            if set(value.keys()) <= {"ok", "present", "note", "status", "checked"}:
                return True
            if all(is_vacuous(v) for v in value.values()):
                return True
            for k, v in value.items():
                if isinstance(v, str) and v.strip() in _VACUOUS_MARKERS:
                    return True
        return False
    return False


def check_artifact(doc: dict[str, Any]) -> dict[str, Any]:
    required = list((doc.get("charter") or {}).get("required_outputs") or CHARTER_REQUIRED_OUTPUTS)
    outputs = doc.get("outputs") or {}
    present = {}
    vacuous = {}
    missing = []
    fail_reasons = []
    for key in required:
        exists = key in outputs
        present[key] = exists
        vac = exists and is_vacuous(outputs.get(key))
        vacuous[key] = vac
        if (not exists) or vac:
            missing.append(key)
            fail_reasons.append(key if not exists else f"{key}:vacuous")
    return {
        "council_id": doc.get("council_id"),
        "pass": not missing,
        "missing": missing,
        "present": present,
        "vacuous": vacuous,
        "fail_reasons": fail_reasons,
        "required": required,
    }


def load_recorded_fixtures(folder: Path) -> list[dict[str, Any]]:
    folder = Path(folder)
    rows = []
    for path in sorted(folder.glob("rec-*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def census(corpus: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [check_artifact(doc) for doc in corpus]
    n_pass = sum(1 for r in rows if r["pass"])
    n_fail = len(rows) - n_pass
    counts: dict[str, dict[str, int]] = {}
    for key in CHARTER_REQUIRED_OUTPUTS:
        counts[key] = {"incomplete": 0, "absent": 0, "vacuous": 0}
    for r in rows:
        for key in CHARTER_REQUIRED_OUTPUTS:
            if key in r["missing"]:
                counts[key]["incomplete"] += 1
                if not r["present"].get(key):
                    counts[key]["absent"] += 1
                elif r["vacuous"].get(key):
                    counts[key]["vacuous"] += 1
    ranked = [
        {"output": k, **counts[k]}
        for k in CHARTER_REQUIRED_OUTPUTS
    ]
    ranked.sort(key=lambda x: (-x["incomplete"], x["output"]))
    most = ranked[0]["output"] if ranked else ""
    return {
        "n_councils": len(corpus),
        "n_pass": n_pass,
        "n_fail": n_fail,
        "missing_most_often": most,
        "per_output": ranked,
        "rows": rows,
    }


def complete_artifact(council_id: str) -> dict[str, Any]:
    outputs = {}
    for key in CHARTER_REQUIRED_OUTPUTS:
        outputs[key] = {"items": [{"id": f"{key}-1", "text": f"live {key} content"}]}
    return {
        "council_id": council_id,
        "charter": {"required_outputs": list(CHARTER_REQUIRED_OUTPUTS)},
        "outputs": outputs,
    }


def vacuous_mutants(base: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    twin = base or complete_artifact("mutant-base")
    rows = []
    for section in CHARTER_REQUIRED_OUTPUTS:
        doc = json.loads(json.dumps(twin))
        doc["outputs"][section] = {"items": [], "note": "TBD"}
        doc["council_id"] = f"vacuous-{section}"
        rows.append({"section": section, "artifact": doc})
    return rows
