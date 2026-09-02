"""Id-normalisation census over command-center declaration sites.

Live scan covers catalog namespaces (backlog items, work_units) plus
declaration-shaped string fields (id / unit_id / claim_id / architecture_id /
item_id) under confirmation/, phase3/, receipts/, and top-level
command-center JSON. p2-wave probe trees are excluded so a planted NFD
control cannot inflate the live non-ASCII count.

OPTION-ID-RESOLUTION.json is an input of this unit; if it is absent that
absence is recorded rather than invented.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import catalog as cat  # noqa: E402
import id_normalize as inn  # noqa: E402

ID_FIELDS = ("id", "unit_id", "claim_id", "architecture_id", "item_id")
MAX_ID_CHARS = 200
SKIP_DIR_NAMES = {
    "node_modules",
    "__pycache__",
    "runtime",
    ".egg-info",
    "p2-wave",
}
OPTION_RESOLUTION = "command-center/OPTION-ID-RESOLUTION.json"


def _namespace_of(raw: str) -> str:
    text = str(raw)
    if "-" not in text:
        return "unprefixed"
    head = text.split("-", 1)[0]
    if not head:
        return "unprefixed"
    return head


def _iter_id_fields(obj: Any, path: str) -> Iterator[tuple[str, str, str]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ID_FIELDS and isinstance(value, str):
                if 0 < len(value) <= MAX_ID_CHARS:
                    yield path, key, value
            else:
                yield from _iter_id_fields(value, path)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_id_fields(item, path)


def _skip_dir(path: Path) -> bool:
    return path.name in SKIP_DIR_NAMES


def _walk_json(root: Path) -> Iterator[Path]:
    if not root.is_dir():
        return
    for child in sorted(root.iterdir()):
        if child.is_dir():
            if _skip_dir(child):
                continue
            yield from _walk_json(child)
            continue
        if child.suffix.lower() == ".json" and child.is_file():
            yield child


def _record(namespace: str, field: str, raw: str, path: str) -> dict[str, Any]:
    text = str(raw)
    return {
        "namespace": namespace,
        "field": field,
        "id": text,
        "path": path,
        "ascii": inn.is_ascii(text),
        "nfc": inn.is_nfc(text),
        "nfd": inn.is_nfd(text),
        "canonical_nfc": inn.canonical_id(text),
        "utf8_hex": inn.byte_key(text).hex(),
        "utf8_bytes": len(inn.byte_key(text)),
    }


def collect_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    catalog = cat.load()
    catalog_rel = "command-center/WORK-UNIT-CATALOG.json"
    for item in cat.items(catalog):
        raw = str(item.get("id") or "")
        if raw:
            rows.append(_record("backlog-item", "id", raw, catalog_rel))
    # The shared catalog module exposes backlog items only; work_units is a
    # plain catalog namespace, so read it directly from the loaded document.
    work_units = catalog.get("work_units") if isinstance(catalog, dict) else None
    for unit in work_units or []:
        if not isinstance(unit, dict):
            continue
        raw = str(unit.get("id") or "")
        if raw:
            rows.append(_record("work-unit", "id", raw, catalog_rel))

    cc = REPO / "command-center"
    catalog_file = cc / "WORK-UNIT-CATALOG.json"
    extra_roots = [
        cc,
        cc / "confirmation",
        cc / "phase3",
        cc / "receipts",
        cc / "foundry",
    ]
    seen: set[Path] = set()
    files: list[Path] = []
    for root in extra_roots:
        if root == cc:
            for child in sorted(cc.glob("*.json")):
                files.append(child)
            continue
        files.extend(_walk_json(root))
    for path in files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved == catalog_file.resolve():
            continue
        try:
            if path.stat().st_size > 8_000_000:
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        rel = path.relative_to(REPO).as_posix()
        for _, field, raw in _iter_id_fields(doc, rel):
            rows.append(_record(_namespace_of(raw), field, raw, rel))
    return rows


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    non_ascii = [r for r in records if not r["ascii"]]
    collisions = inn.collision_groups(r["id"] for r in records)
    by_ns: dict[str, Counter[str]] = {}
    for row in records:
        ns = row["namespace"]
        by_ns.setdefault(ns, Counter())["ids"] += 1
        if not row["ascii"]:
            by_ns[ns]["non_ascii"] += 1
    namespaces = []
    for name in sorted(by_ns):
        namespaces.append(
            {
                "id": name,
                "id_count": int(by_ns[name]["ids"]),
                "non_ascii_count": int(by_ns[name]["non_ascii"]),
            }
        )
    option_path = REPO / OPTION_RESOLUTION
    return {
        "form": inn.CANONICAL_FORM,
        "id_fields": list(ID_FIELDS),
        "record_count": len(records),
        "unique_ids": len({r["id"] for r in records}),
        "non_ascii_count": len(non_ascii),
        "non_ascii_ids": [
            {"id": r["id"], "namespace": r["namespace"], "path": r["path"]}
            for r in non_ascii
        ],
        "live_nfc_collision_groups": collisions,
        "live_nfc_collision_count": len(collisions),
        "namespaces": namespaces,
        "option_id_resolution": {
            "path": OPTION_RESOLUTION,
            "present": option_path.is_file() and option_path.stat().st_size > 0,
        },
        "excluded": [
            "command-center/p2-wave/** (probe fixtures; planted NFD lives here)",
            "node_modules, runtime, package lockfiles",
        ],
    }


def run_census() -> dict[str, Any]:
    records = collect_records()
    summary = summarise(records)
    summary["records_omitted_from_artifact"] = True
    return summary
