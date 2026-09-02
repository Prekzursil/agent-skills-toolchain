#!/usr/bin/env python3
"""Enumerate JSON Schema keys and detect case-collisions and exact duplicates.

Keys are taken from the schema files themselves via a pairs-preserving parse
(json.loads would collapse exact duplicates before we could see them).
Detector control MUST fire on a planted Name/name pair before a live
zero-collision census is trusted.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
PLANTED_COLLISION = FIXTURES / "planted-case-collision.schema.json"
PLANTED_CLEAN = FIXTURES / "planted-clean.schema.json"
FIXTURE_MARK = "p2-wave/probes/ARC-0101/fixtures"
PROBE_TREE_MARK = "p2-wave/probes/"

NAMED_CONTRACTS = [
    f"command-center/phase4/contracts/ARC-{n:04d}.json" for n in range(78, 88)
]
OBJ = "__obj__"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def pointer_escape(part: str) -> str:
    return part.replace("~", "~0").replace("/", "~1")


def rel_of(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_pairs(text: str) -> Any:
    def hook(pairs: list[tuple[str, Any]]) -> Any:
        return (OBJ, tuple(pairs))

    return json.loads(text, object_pairs_hook=hook)


def is_obj(node: Any) -> bool:
    return isinstance(node, tuple) and len(node) == 2 and node[0] == OBJ


class Scan:
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.all_keys: list[dict[str, str]] = []
        self.instance_properties: list[dict[str, str]] = []
        self.definition_names: list[dict[str, str]] = []
        self.same_object_case_collisions: list[dict[str, Any]] = []
        self.exact_duplicates: list[dict[str, Any]] = []

    def note_object(self, pointer: str, pairs: tuple[tuple[str, Any], ...]) -> None:
        keys = [k for k, _ in pairs]
        counts = Counter(keys)
        for key, n in sorted(counts.items()):
            if n > 1:
                self.exact_duplicates.append(
                    {"pointer": pointer, "key": key, "count": n, "file": self.rel}
                )
        by_fold: dict[str, list[str]] = defaultdict(list)
        for key in keys:
            by_fold[key.casefold()].append(key)
        for fold, group in sorted(by_fold.items()):
            distinct = sorted(set(group))
            if len(distinct) > 1:
                self.same_object_case_collisions.append(
                    {
                        "pointer": pointer,
                        "casefold": fold,
                        "keys": distinct,
                        "file": self.rel,
                    }
                )
        for key, _value in pairs:
            self.all_keys.append({"pointer": pointer, "key": key, "file": self.rel})

    def walk(self, node: Any, pointer: str) -> None:
        if is_obj(node):
            pairs = node[1]
            self.note_object(pointer, pairs)
            for key, value in pairs:
                child = f"{pointer}/{pointer_escape(key)}"
                if key in {"properties", "patternProperties"} and is_obj(value):
                    for pk, _pv in value[1]:
                        self.instance_properties.append(
                            {
                                "pointer": child,
                                "key": pk,
                                "map": key,
                                "file": self.rel,
                            }
                        )
                if key in {"$defs", "definitions"} and is_obj(value):
                    for dk, _dv in value[1]:
                        self.definition_names.append(
                            {"pointer": child, "key": dk, "file": self.rel}
                        )
                self.walk(value, child)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                self.walk(item, f"{pointer}/{i}")


def file_wide_collisions(
    rows: list[dict[str, str]], kind: str
) -> list[dict[str, Any]]:
    by_file_fold: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_file_fold[(row["file"], row["key"].casefold())].append(row)
    out: list[dict[str, Any]] = []
    for (file_rel, fold), group in sorted(by_file_fold.items()):
        distinct = sorted({r["key"] for r in group})
        if len(distinct) > 1:
            out.append(
                {
                    "kind": kind,
                    "file": file_rel,
                    "casefold": fold,
                    "keys": distinct,
                    "locations": [
                        {"pointer": r["pointer"], "key": r["key"]} for r in group
                    ],
                }
            )
    return out


def scan_text(rel: str, text: str) -> dict[str, Any]:
    acc = Scan(rel)
    try:
        tree = load_pairs(text)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        return {
            "path": rel,
            "present": True,
            "parse_ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "key_count": 0,
            "instance_property_count": 0,
            "same_object_case_collisions": [],
            "exact_duplicates": [],
            "file_wide_object_key_case_collisions": [],
            "file_wide_instance_property_case_collisions": [],
        }
    acc.walk(tree, "")
    return {
        "path": rel,
        "present": True,
        "parse_ok": True,
        "error": None,
        "key_count": len(acc.all_keys),
        "instance_property_count": len(acc.instance_properties),
        "same_object_case_collisions": acc.same_object_case_collisions,
        "exact_duplicates": acc.exact_duplicates,
        "file_wide_object_key_case_collisions": file_wide_collisions(
            acc.all_keys, "object-key"
        ),
        "file_wide_instance_property_case_collisions": file_wide_collisions(
            acc.instance_properties, "instance-property"
        ),
        "all_keys": acc.all_keys,
        "instance_properties": acc.instance_properties,
    }


def scan_path(path: Path) -> dict[str, Any]:
    rel = rel_of(path)
    if not path.is_file():
        return {
            "path": rel,
            "present": False,
            "parse_ok": False,
            "error": "absent",
            "key_count": 0,
            "instance_property_count": 0,
            "same_object_case_collisions": [],
            "exact_duplicates": [],
            "file_wide_object_key_case_collisions": [],
            "file_wide_instance_property_case_collisions": [],
        }
    text = path.read_text(encoding="utf-8")
    doc = scan_text(rel, text)
    doc["sha256"] = sha256_bytes(path.read_bytes())
    doc["bytes"] = len(path.read_bytes().replace(b"\r\n", b"\n"))
    return doc


def _has_name_pair(collisions: list[dict[str, Any]]) -> bool:
    want = {"Name", "name"}
    for row in collisions:
        if set(row.get("keys") or []) == want:
            return True
    return False


def planted_name_pair_found(doc: dict[str, Any]) -> bool:
    if _has_name_pair(doc.get("same_object_case_collisions") or []):
        return True
    if _has_name_pair(doc.get("file_wide_instance_property_case_collisions") or []):
        return True
    props = {
        str(p.get("key"))
        for p in (doc.get("instance_properties") or [])
        if str(p.get("map") or "") == "properties"
    }
    return props >= {"Name", "name"}


def run_control() -> dict[str, Any]:
    """Planted collision MUST be found; planted clean MUST be silent."""
    planted = scan_path(PLANTED_COLLISION)
    clean = scan_path(PLANTED_CLEAN)
    fired = planted.get("parse_ok") is True and planted_name_pair_found(planted)
    clean_silent = (
        clean.get("parse_ok") is True
        and not (clean.get("same_object_case_collisions") or [])
        and not (clean.get("exact_duplicates") or [])
        and not (clean.get("file_wide_instance_property_case_collisions") or [])
    )
    return {
        "order": "control-before-census",
        "planted_schema": rel_of(PLANTED_COLLISION),
        "clean_schema": rel_of(PLANTED_CLEAN),
        "planted_keys": ["Name", "name"],
        "planted_sha256": planted.get("sha256"),
        "clean_sha256": clean.get("sha256"),
        "fired": fired,
        "clean_silent": clean_silent,
        "planted_collisions": planted.get("same_object_case_collisions") or [],
        "trusted": fired and clean_silent,
    }


def live_schema_paths() -> list[Path]:
    found: list[Path] = []
    root = REPO / "command-center"
    if root.is_dir():
        for path in sorted(root.rglob("*.schema.json")):
            posix = path.as_posix().replace("\\", "/")
            if PROBE_TREE_MARK in posix:
                continue
            if FIXTURE_MARK in posix:
                continue
            if "__pycache__" in posix:
                continue
            found.append(path.resolve())
    for rel in NAMED_CONTRACTS:
        path = (REPO / rel).resolve()
        if path not in found:
            found.append(path)
    return found


def named_contract_rows() -> list[dict[str, Any]]:
    rows = []
    for rel in NAMED_CONTRACTS:
        path = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": path.is_file() and path.stat().st_size > 0,
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def census_live() -> dict[str, Any]:
    files = []
    same_object: list[dict[str, Any]] = []
    exact: list[dict[str, Any]] = []
    file_wide_props: list[dict[str, Any]] = []
    file_wide_keys: list[dict[str, Any]] = []
    parsed = 0
    absent = 0
    parse_fail = 0
    keys_total = 0
    for path in live_schema_paths():
        doc = scan_path(path)
        slim = {
            k: doc[k]
            for k in (
                "path",
                "present",
                "parse_ok",
                "error",
                "key_count",
                "instance_property_count",
                "same_object_case_collisions",
                "exact_duplicates",
                "file_wide_object_key_case_collisions",
                "file_wide_instance_property_case_collisions",
            )
            if k in doc
        }
        if "sha256" in doc:
            slim["sha256"] = doc["sha256"]
            slim["bytes"] = doc["bytes"]
        files.append(slim)
        if not doc.get("present"):
            absent += 1
            continue
        if not doc.get("parse_ok"):
            parse_fail += 1
            continue
        parsed += 1
        keys_total += int(doc.get("key_count") or 0)
        same_object.extend(doc.get("same_object_case_collisions") or [])
        exact.extend(doc.get("exact_duplicates") or [])
        file_wide_props.extend(
            doc.get("file_wide_instance_property_case_collisions") or []
        )
        file_wide_keys.extend(doc.get("file_wide_object_key_case_collisions") or [])
    return {
        "generated_from_schema_files": True,
        "files_considered": len(files),
        "files_parsed": parsed,
        "files_absent": absent,
        "files_parse_failed": parse_fail,
        "keys_total": keys_total,
        "same_object_case_collision_count": len(same_object),
        "exact_duplicate_count": len(exact),
        "file_wide_instance_property_case_collision_count": len(file_wide_props),
        "file_wide_object_key_case_collision_count": len(file_wide_keys),
        "same_object_case_collisions": same_object,
        "exact_duplicates": exact,
        "file_wide_instance_property_case_collisions": file_wide_props,
        "file_wide_object_key_case_collisions": file_wide_keys,
        "files": files,
    }
