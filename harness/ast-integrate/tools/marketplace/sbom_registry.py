"""SBOM registry: indexed query equals brute-force; SBOM-ABSENT stays visible."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EMPTY_RESULT = "EMPTY"
QUERY_ERROR = "QUERY-ERROR"
SBOM_ABSENT = "SBOM-ABSENT"
SBOM_PRESENT = "SBOM-PRESENT"


class SbomRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.packages: dict[str, dict[str, Any]] = {}
        self._index: dict[tuple[str, str], list[str]] = {}

    def publish(self, name: str, version: str, sbom: dict[str, Any] | None) -> dict[str, Any]:
        pid = f"{name}@{version}"
        if sbom is None:
            rec = {"id": pid, "name": name, "version": version, "sbom_status": SBOM_ABSENT, "components": []}
            self.packages[pid] = rec
            return {"ok": True, "sbom_status": SBOM_ABSENT, "id": pid}
        comps = sbom.get("components")
        if not isinstance(comps, list):
            return {"ok": False, "error": "invalid-sbom", "id": pid}
        rec = {
            "id": pid,
            "name": name,
            "version": version,
            "sbom_status": SBOM_PRESENT,
            "components": comps,
        }
        self.packages[pid] = rec
        for c in comps:
            key = (str(c.get("name") or "").lower(), str(c.get("version") or "").lower())
            self._index.setdefault(key, []).append(pid)
        return {"ok": True, "sbom_status": SBOM_PRESENT, "id": pid}

    def query_space(self) -> list[dict[str, Any]]:
        return list(self.packages.values())

    def indexed_query(self, name: str, version: str) -> dict[str, Any]:
        if not name or not version:
            return {
                "ok": False,
                "kind": QUERY_ERROR,
                "empty": False,
                "matches": None,
                "match_ids": [],
                "unknown": [],
                "unknown_ids": [],
                "query_space_ids": [p["id"] for p in self.query_space()],
                "sbom_absent_visible": True,
            }
        key = (name.lower(), version.lower())
        ids = list(self._index.get(key, []))
        matches = [self.packages[i] for i in ids]
        unknown = [p for p in self.packages.values() if p["sbom_status"] == SBOM_ABSENT]
        return {
            "ok": True,
            "kind": EMPTY_RESULT if not matches else "MATCH",
            "empty": not matches,
            "matches": matches,
            "match_ids": ids,
            "unknown": unknown,
            "unknown_ids": [p["id"] for p in unknown],
            "query_space_ids": [p["id"] for p in self.query_space()],
            "sbom_absent_visible": True,
            "method": "inverted-index",
        }

    def brute_force_query(self, name: str, version: str) -> dict[str, Any]:
        if not name or not version:
            return {"ok": False, "kind": QUERY_ERROR, "empty": False, "matches": None}
        ids = []
        for pid, rec in self.packages.items():
            for c in rec.get("components") or []:
                if str(c.get("name") or "").lower() == name.lower() and str(c.get("version") or "").lower() == version.lower():
                    ids.append(pid)
                    break
        unknown = [p for p in self.packages.values() if p["sbom_status"] == SBOM_ABSENT]
        return {
            "ok": True,
            "kind": EMPTY_RESULT if not ids else "MATCH",
            "empty": not ids,
            "matches": [self.packages[i] for i in ids],
            "match_ids": ids,
            "unknown": unknown,
            "unknown_ids": [p["id"] for p in unknown],
            "query_space_ids": [p["id"] for p in self.query_space()],
            "method": "dfs-packages",
            "index_file_consulted": False,
        }

    def query_equals_brute(self, name: str, version: str) -> dict[str, Any]:
        indexed = self.indexed_query(name, version)
        brute = self.brute_force_query(name, version)
        return {
            "equal": set(indexed["match_ids"]) == set(brute["match_ids"]),
            "indexed_ids": indexed["match_ids"],
            "brute_ids": brute["match_ids"],
            "indexed": indexed,
            "brute": brute,
        }
