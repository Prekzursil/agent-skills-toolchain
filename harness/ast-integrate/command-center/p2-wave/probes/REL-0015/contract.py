"""Load the REL-0015 support contract and enumerate OS x client x version cells."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "support_contract.json"


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def cell_id(os_name: str, client_id: str, declared_version: str) -> str:
    return f"{os_name}::{client_id}::{declared_version}"


def enumerate_cells(contract: dict[str, Any] | None = None) -> list[dict[str, str]]:
    doc = contract or load_contract()
    cells: list[dict[str, str]] = []
    for os_name in doc["operating_systems"]:
        for client in doc["clients"]:
            cid = client["id"]
            ver = client["declared_version"]
            cells.append(
                {
                    "cell_id": cell_id(os_name, cid, ver),
                    "os": os_name,
                    "client": cid,
                    "client_display": client.get("display", cid),
                    "declared_version": ver,
                }
            )
    return cells
