"""Fan-in barrier cited by BLD-0055 (`tools/fan_in/barrier.py:admit`)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable


def admit(root: Path | str, rels: Iterable[str], digest_text: str) -> dict[str, Any]:
    base = Path(root)
    text = str(digest_text or "")
    for rel in rels:
        path = base / rel
        if not path.is_file():
            return {"admitted": False, "reason": "absent", "path": str(rel)}
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in text:
            return {"admitted": False, "reason": "digest-mismatch", "path": str(rel)}
    return {"admitted": True}
