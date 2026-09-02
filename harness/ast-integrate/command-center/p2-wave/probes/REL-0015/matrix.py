"""Run every declared cell through the identical install-and-smoke journey."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from contract import enumerate_cells, load_contract
from renderer import publish
from smoke import IsolationError, OWNER_HOME, assert_isolated, both_states, run_journey

HERE = Path(__file__).resolve().parent
RECEIPT_DIR = HERE / "cell-receipts"
SKIP_DIR = HERE / "cell-skips"


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def run_matrix(work: Path | None = None) -> dict[str, Any]:
    contract = load_contract()
    specs = enumerate_cells(contract)
    root = Path(work) if work else Path(tempfile.mkdtemp(prefix="rel0015-matrix-"))
    root.mkdir(parents=True, exist_ok=True)
    executed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    receipts_by_id: dict[str, dict[str, Any]] = {}

    for spec in specs:
        cell_home = root / spec["cell_id"].replace(":", "_")
        cell_home.mkdir(parents=True, exist_ok=True)
        result = run_journey(
            spec["os"], spec["client"], spec["declared_version"], cell_home
        )
        result["cell_id"] = spec["cell_id"]
        status = result.get("status")
        if status in {"PASS", "FAIL"}:
            receipt = {
                "cell_id": spec["cell_id"],
                "os": spec["os"],
                "client": spec["client"],
                "declared_version": spec["declared_version"],
                "status": status,
                "observed_client_build_string": result.get(
                    "observed_client_build_string", ""
                ),
                "acceptance_signal": result.get("acceptance_signal"),
                "listing_disqualified": True,
                "reason": result.get("reason"),
                "host_os_observed": result.get("host_os_observed"),
                "uname": result.get("uname"),
            }
            executed.append(receipt)
            receipts_by_id[spec["cell_id"]] = receipt
            _write_json(
                RECEIPT_DIR / f"{spec['cell_id'].replace(':', '_')}.json", receipt
            )
        else:
            skip = {
                "cell_id": spec["cell_id"],
                "os": spec["os"],
                "client": spec["client"],
                "declared_version": spec["declared_version"],
                "status": "NOT-CHECKED",
                "reason": result.get("reason") or "not executed",
            }
            skipped.append(skip)
            _write_json(SKIP_DIR / f"{spec['cell_id'].replace(':', '_')}.json", skip)

    rendered = publish(specs, receipts_by_id)
    isolation_refused = False
    isolation_error = ""
    try:
        assert_isolated(OWNER_HOME)
    except IsolationError as exc:
        isolation_refused = True
        isolation_error = str(exc)

    both = both_states(root / "_both-states")
    return {
        "contract": contract,
        "specs": specs,
        "executed_receipts": executed,
        "not_checked_entries": skipped,
        "rendered": rendered,
        "isolation": {
            "owner_home": str(OWNER_HOME),
            "refused": isolation_refused,
            "error": isolation_error,
        },
        "both_states": both,
        "work_root": str(root),
    }


run_matrix = run_matrix
