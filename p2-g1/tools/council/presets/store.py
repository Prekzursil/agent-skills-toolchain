"""Load/edit/save council presets with order-preserving fidelity."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.council.presets.catalog import CATALOG_PATH, ensure_catalog

PRESET_KEY_ORDER = (
    "id",
    "family",
    "title",
    "stopping",
    "dials",
    "default_binding",
)
EDIT_DIAL = ("stopping", "max_rounds")


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(_canonical_bytes(obj)).hexdigest()


def reorder_keys(obj: dict[str, Any], order: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in order:
        if k in obj:
            out[k] = obj[k]
    for k, v in obj.items():
        if k not in out:
            out[k] = v
    return out


def _walk_diffs(a: Any, b: Any, prefix: str = "") -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    if type(a) is not type(b):
        diffs.append({"path": prefix, "kind": "type", "left": a, "right": b})
        return diffs
    if isinstance(a, dict):
        if list(a.keys()) != list(b.keys()):
            diffs.append(
                {
                    "path": prefix,
                    "kind": "keys_reordered" if set(a) == set(b) else "keys",
                    "left": list(a.keys()),
                    "right": list(b.keys()),
                }
            )
        for k in a:
            if k in b:
                child = f"{prefix}.{k}" if prefix else k
                diffs.extend(_walk_diffs(a[k], b[k], child))
        return diffs
    if a != b:
        diffs.append({"path": prefix, "kind": "value", "left": a, "right": b})
    return diffs


def fidelity_ok(
    original: dict[str, Any],
    mutated: dict[str, Any],
    allowed_paths: set[str] | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    diffs = _walk_diffs(original, mutated)
    allowed = allowed_paths or set()
    unexpected = [d for d in diffs if d.get("path") not in allowed]
    return (not unexpected), diffs


class PresetStore:
    def __init__(self, path: Path | None = None) -> None:
        ensure_catalog()
        self.path = path or CATALOG_PATH
        self._doc = json.loads(self.path.read_text(encoding="utf-8"))

    def presets(self) -> list[dict[str, Any]]:
        return list(self._doc.get("presets") or [])

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def round_trip_one(self, preset_id: str) -> dict[str, Any]:
        before = copy.deepcopy(self.presets())
        hashes = {p["id"]: canonical_hash(p) for p in before}
        target = next(p for p in self._doc["presets"] if p["id"] == preset_id)
        original = copy.deepcopy(target)
        dial = "stopping.max_rounds"
        old = int(target["stopping"]["max_rounds"])
        target["stopping"]["max_rounds"] = old + 1
        self._save()
        reloaded = json.loads(self.path.read_text(encoding="utf-8"))
        after = reloaded["presets"]
        edited = next(p for p in after if p["id"] == preset_id)
        ok, diffs = fidelity_ok(original, edited, allowed_paths={dial})
        unexpected = [d for d in diffs if d.get("path") not in {dial}]
        untouched_ok = True
        for p in after:
            if p["id"] == preset_id:
                continue
            orig = next(x for x in before if x["id"] == p["id"])
            if canonical_hash(p) != hashes[p["id"]] or p != orig:
                untouched_ok = False
        edited_changed = canonical_hash(edited) != hashes[preset_id]
        # restore catalog so later rounds start clean
        self._doc = {"presets": before}
        self._save()
        self._doc = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            "preset_id": preset_id,
            "fidelity_ok": ok and not unexpected,
            "unexpected": unexpected,
            "untouched_all_match": untouched_ok,
            "edited_hash_changed": edited_changed,
            "diffs": diffs,
            "dial": dial,
        }
