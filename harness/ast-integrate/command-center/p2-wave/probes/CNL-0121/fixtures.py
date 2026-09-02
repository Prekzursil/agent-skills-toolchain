#!/usr/bin/env python3
"""Load CNL-0121 fixtures and bind proof_of_impossibility from disk."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
CATALOG_PATH = FIX / "catalog.json"


class BindError(ValueError):
    pass


def proof_holds(path: Path) -> bool:
    if not path.is_file():
        return False
    doc = json.loads(path.read_text(encoding="utf-8"))
    contradiction = doc.get("contradiction")
    return (
        doc.get("kind") == "proof_of_impossibility"
        and doc.get("impossible") is True
        and doc.get("unsuccessful_search") is not True
        and isinstance(contradiction, str)
        and len(contradiction.strip()) >= 24
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog() -> dict[str, Any]:
    return load_json(CATALOG_PATH)


def bind_metrics(doc: dict[str, Any], base: Path) -> dict[str, Any]:
    metrics = dict(doc.get("metrics") or {})
    rel = doc.get("proof_receipt")
    if rel:
        proof = (base / rel) if not Path(rel).is_absolute() else Path(rel)
        if not proof.is_file():
            proof = FIX / rel
        if not proof_holds(proof):
            raise BindError(f"proof receipt does not hold: {proof}")
        metrics["proof_of_impossibility"] = True
        metrics["_proof_receipt"] = str(proof.relative_to(HERE)).replace("\\", "/")
    elif metrics.get("proof_of_impossibility") is True:
        raise BindError(
            "proof_of_impossibility true is unbacked; a receipt file is required"
        )
    else:
        metrics.setdefault("proof_of_impossibility", False)
    return metrics


def load_fixture(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    path = FIX / name
    doc = load_json(path)
    return doc, bind_metrics(doc, FIX)


def expressions() -> list[dict[str, Any]]:
    return list(catalog()["expressions"])
