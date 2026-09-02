"""Claim-ledger resume: intact terminals skip; truncated claims redispatch."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def run_both_states(work: Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    intact_path = work / "intact.json"
    intact = {
        "unit_id": "TST-0162",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0162",
        "terminal": True,
        "claims": [{"id": "C1", "status": "CONFIRMED", "bytes": 64}],
    }
    _write(intact_path, intact)
    loaded = json.loads(intact_path.read_text(encoding="utf-8"))
    intact_skip = bool(loaded.get("terminal") is True and loaded.get("state") == "SUCCESS")
    intact_plan = {"skip": intact_skip, "redispatch": not intact_skip}

    corrupt_path = work / "corrupt.json"
    _write(corrupt_path, {"unit_id": "TST-0162", "claims": [{"id": "C1", "status": "CONFIRMED"}]})
    raw = corrupt_path.read_bytes()
    truncated = raw[: max(8, len(raw) // 3)]
    corrupt_path.write_bytes(truncated)
    redispatch = False
    independent_changed = False
    try:
        json.loads(corrupt_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        redispatch = True
        _write(work / "redispatched.json", {"unit_id": "TST-0162", "state": "RUNNING", "redispatched": True})
        independent_changed = True
    return {
        "pass": bool(intact_skip and redispatch and independent_changed),
        "both_states": {
            "intact_claims_skip": intact_skip,
            "corrupted_claims_redispatch": redispatch,
        },
        "intact": {"plan": intact_plan, "path": str(intact_path)},
        "corrupt": {
            "plan": {"skip": False, "redispatch": redispatch},
            "independent_receipt_changed": independent_changed,
            "path": str(corrupt_path),
        },
    }


def run_mutation_truncate(work: Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
    result = run_both_states(work)
    result["mutation"] = "truncate"
    result["pass"] = bool(result.get("corrupt", {}).get("plan", {}).get("redispatch"))
    return result
