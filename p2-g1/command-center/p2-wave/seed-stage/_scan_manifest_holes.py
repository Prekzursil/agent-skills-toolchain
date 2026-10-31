#!/usr/bin/env python3
"""List receipt artifacts that would make unit_manifest --write fail closed."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CC = REPO / "command-center"
DIRS = ("receipts", "adversarial", "audit")


def is_receipt(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    uid = value.get("unit_id")
    arts = value.get("artifacts")
    return isinstance(uid, str) and bool(uid.strip()) and isinstance(arts, list) and bool(arts)


def main() -> None:
    missing = []
    n_receipts = 0
    n_arts = 0
    for dirname in DIRS:
        base = CC / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.json")):
            if any(part.startswith("_") for part in path.relative_to(CC).parts):
                continue
            if path.name in {"ARTIFACT-MANIFEST.json", "UNIT-ARTIFACT-MANIFEST.json"}:
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not is_receipt(value):
                continue
            n_receipts += 1
            for art in value["artifacts"]:
                if not isinstance(art, dict) or not isinstance(art.get("path"), str):
                    continue
                n_arts += 1
                rel = art["path"].replace("\\", "/")
                if not (REPO / rel).is_file():
                    missing.append((path.relative_to(REPO).as_posix(), rel, value.get("unit_id")))
    print(f"receipts={n_receipts} artifacts={n_arts} missing={len(missing)}")
    for rec, rel, uid in missing[:40]:
        print(f"MISSING {uid} receipt={rec} artifact={rel}")
    if len(missing) > 40:
        print(f"... {len(missing) - 40} more")


if __name__ == "__main__":
    main()
