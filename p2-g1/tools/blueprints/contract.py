"""Required blueprint elements."""
from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_ELEMENTS = (
    ("charter", "charter.py", "missing-charter"),
    ("stopping", "stopping.py", "missing-stopping"),
    ("outcomes", "outcomes.py", "missing-outcomes"),
)


def inspect_blueprint(root: Path) -> dict[str, Any]:
    root = Path(root)
    present = []
    missing = []
    for element, filename, reject_id in REQUIRED_ELEMENTS:
        path = root / filename
        if path.is_file():
            present.append(element)
        else:
            missing.append({"element": element, "reject_id": reject_id})
    return {"present": present, "missing": missing, "ok": not missing}
