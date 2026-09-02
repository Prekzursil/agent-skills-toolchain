import json
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {"ok": True, "items": []}
    return {"ok": True, "items": json.loads(p.read_text(encoding="utf-8"))}
