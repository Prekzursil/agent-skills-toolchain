"""Planted defect: flush sentinel bytes to the destination, then the payload."""
from __future__ import annotations

import json
from pathlib import Path

SENTINEL = "SUCCESS:ADV-0004-PLANTED-SENTINEL-FIRST"
PAYLOAD = "x" * 4000


def write_sentinel_before_payload(path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write('{"sentinel": "' + SENTINEL + '"')
        fh.flush()
        fh.write(', "payload": ' + json.dumps(PAYLOAD) + "}")
        fh.flush()
