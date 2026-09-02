"""On-disk fixture paths for IMP-0455 three-fixture + adversarial battery."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

READABLE = FIX / "01-readable.json"
UNPARSEABLE = FIX / "02-exists-unparseable.json"
MISSING_FIELD = FIX / "03-parseable-missing-field.json"
ADVERSARIAL = FIX / "04-adversarial-unusable-field.json"

REQUIRED_FIELD = "sentinel"

EXPECTED = {
    "readable": {"path": READABLE, "ok": True, "code": "READABLE"},
    "exists-but-unparseable": {"path": UNPARSEABLE, "ok": False, "code": "UNPARSEABLE"},
    "parseable-but-missing-required-field": {
        "path": MISSING_FIELD,
        "ok": False,
        "code": "MISSING_REQUIRED_FIELD",
    },
}
