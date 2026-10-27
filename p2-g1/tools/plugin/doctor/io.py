"""Load doctor taxonomy and remediation mapping."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data"


def load_taxonomy() -> dict[str, Any]:
    return json.loads((DATA / "error-taxonomy.json").read_text(encoding="utf-8"))


def load_mapping() -> dict[str, Any]:
    return json.loads((DATA / "doctor-mapping.json").read_text(encoding="utf-8"))


def taxonomy_codes(taxonomy: dict[str, Any] | None = None) -> list[str]:
    tax = taxonomy if taxonomy is not None else load_taxonomy()
    return [row["code"] for row in tax.get("codes") or [] if isinstance(row, dict) and row.get("code")]
