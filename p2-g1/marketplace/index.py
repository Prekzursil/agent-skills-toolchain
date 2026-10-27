"""On-disk package index mutated by record_blob."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PackageIndex:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"packages": {}}, indent=2) + "\n", encoding="utf-8")

    def record_blob(self, name: str, version: str, digest: str, projection: Any = None) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        packages = data.setdefault("packages", {})
        if not isinstance(packages, dict):
            packages = {}
            data["packages"] = packages
        packages[str(name)] = {
            "name": str(name),
            "version": str(version),
            "digest": str(digest),
            "projection": projection,
        }
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
