"""Control producer: assemble the full document, write tmp, atomic replace."""
from __future__ import annotations

import json
import os
from pathlib import Path

SENTINEL = "SUCCESS:ADV-0004-PLANTED-ATOMIC-COMPLETE"
PAYLOAD = "x" * 4000


def write_complete_atomic(path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"payload": PAYLOAD, "sentinel": SENTINEL}
    blob = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(blob, encoding="utf-8")
    os.replace(tmp, path)
