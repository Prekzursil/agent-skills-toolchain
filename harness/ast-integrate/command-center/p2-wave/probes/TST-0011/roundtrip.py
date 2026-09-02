"""Condition-11 round-trip: close writes a manifest row; reverse sweep is two set diffs.

Direction A (orphan rows): manifest paths minus existing files.
Direction B (unregistered files): on-disk receipts minus manifest paths.

The two counts are never folded into a single 'looks consistent' boolean.
A zero in either direction is trusted only after a planted control has fired.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

HEX64 = re.compile(r"^[0-9a-f]{64}$")
RECEIPT_DIRS = ("receipts", "adversarial", "audit")
CONTRACT = "completion-predicate-condition-11-unit-artifact-registration"
DEFAULT_MANIFEST_REL = "command-center/UNIT-ARTIFACT-MANIFEST.json"


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())


def _posix(rel: str) -> str:
    return str(rel or "").replace("\\", "/")


def _is_scratch(path: Path, corpus: Path) -> bool:
    return any(part.startswith("_") for part in path.relative_to(corpus).parts)


def _is_receipt_shape(value: dict[str, Any]) -> bool:
    unit_id = value.get("unit_id")
    artifacts = value.get("artifacts")
    return (
        isinstance(unit_id, str)
        and bool(unit_id.strip())
        and isinstance(artifacts, list)
        and bool(artifacts)
    )


def make_row(
    path: str,
    sha256: str,
    nbytes: int,
    unit_id: str,
    receipt_path: str,
    *,
    present: bool = True,
) -> dict[str, Any]:
    if not HEX64.match(sha256):
        raise ValueError(f"non-hex sha256 for {path}")
    uid = unit_id.strip()
    return {
        "path": _posix(path),
        "sha256": sha256,
        "bytes": nbytes,
        "present": present,
        "unit_id": uid,
        "producing_unit_id": uid,
        "receipt_path": _posix(receipt_path),
    }


def empty_manifest(derivation: str = "close_unit") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract": CONTRACT,
        "derivation": derivation,
        "verified_on_disk": True,
        "expected": 0,
        "present": 0,
        "artifacts": [],
    }


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_manifest()
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"manifest {path} is not an object")
    if not isinstance(doc.get("artifacts"), list):
        doc["artifacts"] = []
    return doc


def write_manifest(path: Path, doc: dict[str, Any]) -> None:
    rows = [r for r in (doc.get("artifacts") or []) if isinstance(r, dict)]
    doc["artifacts"] = rows
    doc["expected"] = len(rows)
    doc["present"] = sum(1 for r in rows if r.get("present") is True)
    doc["verified_on_disk"] = all(r.get("present") is True for r in rows) if rows else True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def append_row(manifest_path: Path, row: dict[str, Any]) -> dict[str, Any]:
    doc = load_manifest(manifest_path)
    rows = [r for r in doc.get("artifacts") or [] if isinstance(r, dict)]
    kept = [
        r
        for r in rows
        if not (
            _posix(str(r.get("path") or "")) == row["path"]
            and str(r.get("unit_id") or r.get("producing_unit_id") or "")
            == row["unit_id"]
        )
    ]
    kept.append(row)
    doc["artifacts"] = kept
    write_manifest(manifest_path, doc)
    return doc


def close_unit(
    root: Path,
    unit_id: str,
    output_rel: str,
    *,
    payload: dict[str, Any] | None = None,
    manifest_rel: str = DEFAULT_MANIFEST_REL,
) -> dict[str, Any]:
    """Close one unit: write the receipt at output_rel and a manifest row for it.

    The row always carries path, sha256 (CRLF-normalised), and producing_unit_id.
    """
    uid = str(unit_id).strip()
    if not uid:
        raise ValueError("unit_id is required")
    output_rel = _posix(output_rel)
    doc = payload if payload is not None else {}
    if not isinstance(doc, dict):
        raise ValueError("payload must be an object")
    doc = dict(doc)
    doc.setdefault("unit_id", uid)
    doc.setdefault("state", "SUCCESS")
    doc.setdefault("sentinel", f"SUCCESS:{uid}")
    arts = doc.get("artifacts")
    if not isinstance(arts, list) or not arts:
        doc["artifacts"] = [{"path": output_rel, "role": "primary"}]
    target = root / output_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha, nbytes = digest_file(target)
    if nbytes <= 0:
        raise ValueError(f"close refused empty artifact {output_rel}")
    row = make_row(output_rel, sha, nbytes, uid, output_rel, present=True)
    man_path = root / manifest_rel
    append_row(man_path, row)
    return {
        "row": row,
        "output_rel": output_rel,
        "manifest_rel": _posix(manifest_rel),
        "sha256": sha,
        "bytes": nbytes,
    }


def discover_manifest_files(root: Path) -> list[Path]:
    found: list[Path] = []
    global_man = root / DEFAULT_MANIFEST_REL
    if global_man.is_file():
        found.append(global_man)
    probes = root / "command-center" / "p2-wave" / "probes"
    if probes.is_dir():
        for path in sorted(probes.glob("*/UNIT-ARTIFACT-MANIFEST.json")):
            if path.is_file():
                found.append(path)
    return found


def discover_rows(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in discover_manifest_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"unreadable:{rel}:{type(exc).__name__}")
            continue
        if not isinstance(doc, dict):
            errors.append(f"not-object:{rel}")
            continue
        for item in doc.get("artifacts") or []:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                row = dict(item)
                row["_manifest_file"] = rel
                rows.append(row)
    return rows, errors


def discover_receipts(root: Path) -> set[str]:
    """On-disk receipts: existing catalog output_paths plus receipt-shaped JSON."""
    paths: set[str] = set()
    catalog = root / "command-center" / "WORK-UNIT-CATALOG.json"
    if catalog.is_file():
        try:
            data = json.loads(catalog.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = {}
        for unit in (data.get("work_units") or []) if isinstance(data, dict) else []:
            if not isinstance(unit, dict):
                continue
            rel = _posix(str(unit.get("output_path") or ""))
            if not rel:
                continue
            fp = root / rel
            try:
                if fp.is_file() and fp.stat().st_size > 0:
                    paths.add(rel)
            except OSError:
                continue
    corpus = root / "command-center"
    for dirname in RECEIPT_DIRS:
        base = corpus / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.json")):
            if path.name in {"ARTIFACT-MANIFEST.json", "UNIT-ARTIFACT-MANIFEST.json"}:
                continue
            if _is_scratch(path, corpus):
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and _is_receipt_shape(value):
                paths.add(path.relative_to(root).as_posix())
    return paths


def reverse_sweep(
    root: Path,
    receipt_paths: Iterable[str],
    rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Bidirectional set difference. Never returns a combined consistency flag."""
    receipts = {_posix(p) for p in receipt_paths if _posix(p)}
    row_list = [r for r in rows if isinstance(r, dict) and isinstance(r.get("path"), str)]
    row_paths = [_posix(str(r["path"])) for r in row_list]
    counts = Counter(row_paths)

    orphan_rows: list[dict[str, Any]] = []
    for row in row_list:
        rel = _posix(str(row["path"]))
        target = root / rel
        reason = None
        try:
            if not target.is_file():
                reason = "missing"
            elif target.stat().st_size <= 0:
                reason = "empty"
        except OSError:
            reason = "unreadable"
        if reason:
            orphan_rows.append(
                {
                    "path": rel,
                    "producing_unit_id": str(
                        row.get("producing_unit_id") or row.get("unit_id") or ""
                    ),
                    "reason": reason,
                    "manifest_file": row.get("_manifest_file"),
                }
            )

    unregistered: list[str] = []
    duplicates: list[dict[str, Any]] = []
    exactly_one: list[str] = []
    for rel in sorted(receipts):
        n = counts.get(rel, 0)
        if n == 0:
            unregistered.append(rel)
        elif n == 1:
            exactly_one.append(rel)
        else:
            duplicates.append({"path": rel, "row_count": n})

    orphan_set = {item["path"] for item in orphan_rows}
    manifest_set = set(row_paths)
    # Direction A / B as pure set differences on paths (file existence applied to A).
    direction_a = sorted(orphan_set)
    direction_b = sorted(set(receipts) - manifest_set)

    return {
        "orphan_row_count": len(orphan_rows),
        "unregistered_file_count": len(unregistered),
        "duplicate_path_count": len(duplicates),
        "exactly_one_count": len(exactly_one),
        "receipt_count": len(receipts),
        "manifest_row_count": len(row_list),
        "orphan_rows": orphan_rows,
        "unregistered_files": unregistered,
        "duplicate_paths": duplicates,
        "direction_a_manifest_minus_files": direction_a,
        "direction_b_receipts_minus_manifest": direction_b,
        "direction_a_count": len(direction_a),
        "direction_b_count": len(direction_b),
    }


def live_sweep(root: Path) -> dict[str, Any]:
    rows, errors = discover_rows(root)
    receipts = discover_receipts(root)
    result = reverse_sweep(root, receipts, rows)
    result["manifest_parse_errors"] = errors
    result["manifest_file_count"] = len(discover_manifest_files(root))
    return result


def independent_path_sets(
    root: Path, receipt_paths: Iterable[str], rows: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Second signal: raw set arithmetic, not the reverse_sweep return object.

    Orphan count is the number of rows whose file is missing (row count, not
    unique-path count) so it stays comparable to reverse_sweep. Unregistered
    count is receipts minus the manifest path set.
    """
    receipts = {_posix(p) for p in receipt_paths if _posix(p)}
    manifest_paths: set[str] = set()
    missing_rows = 0
    missing_paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            continue
        rel = _posix(row["path"])
        manifest_paths.add(rel)
        target = root / rel
        try:
            ok = target.is_file() and target.stat().st_size > 0
        except OSError:
            ok = False
        if not ok:
            missing_rows += 1
            missing_paths.add(rel)
    unregistered = sorted(receipts - manifest_paths)
    return {
        "orphan_row_count": missing_rows,
        "unregistered_file_count": len(unregistered),
        "orphan_paths": sorted(missing_paths),
        "unregistered_files": unregistered,
        "manifest_path_count": len(manifest_paths),
        "receipt_count": len(receipts),
    }


def print_counts(tag: str, sweep: dict[str, Any]) -> None:
    print(f"{tag} orphan_row_count={sweep['orphan_row_count']}")
    print(f"{tag} unregistered_file_count={sweep['unregistered_file_count']}")
