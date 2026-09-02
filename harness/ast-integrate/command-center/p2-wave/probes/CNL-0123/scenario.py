"""Load CNL-0123 fixtures and fill live evidence digests."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

SPLIT = "split"
ALL_PASS = "all_pass"
MISSING = "missing_receipt"
PERTURBED = "perturbed_split"


def repo_read(rel: str) -> bytes | None:
    path = REPO / str(rel).replace("\\", "/")
    if not path.is_file():
        return None
    return path.read_bytes()


def load_fixture(name: str) -> dict:
    root = FIX / name
    meta = json.loads((root / "children.json").read_text(encoding="utf-8"))
    children = []
    for raw in meta["children"]:
        child = dict(raw)
        rel = str(child["evidence_path"]).replace("\\", "/")
        planted = child.get("digest")
        if planted in (None, "", "LIVE"):
            data = repo_read(rel)
            if data is None:
                raise FileNotFoundError(rel)
            child["digest"] = __import__("hashlib").sha256(
                data.replace(b"\r\n", b"\n")
            ).hexdigest()
        children.append(child)
    return {
        "id": meta["id"],
        "title": meta.get("title") or name,
        "children": children,
    }
