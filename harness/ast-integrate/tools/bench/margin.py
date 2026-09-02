"""Pre-registered margin table. Post-hoc override is refused."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TABLE = HERE / "margins.json"


class PostHocMarginOverrideError(Exception):
    pass


def load_margin_table(override: float | None = None) -> dict[str, Any]:
    if override is not None:
        raise PostHocMarginOverrideError("post-hoc margin override refused")
    if TABLE.is_file():
        raw = TABLE.read_bytes().replace(b"\r\n", b"\n")
        doc = json.loads(raw.decode("utf-8"))
        doc["spec_sha256"] = hashlib.sha256(raw).hexdigest()
        return doc
    return {
        "id": "pre-registered-margins-v1",
        "spec_sha256": "inline",
        "primary": {"pre_registered_n": 24, "min_effect": 0.05},
        "secondary": {"min_effect": -0.05},
    }
