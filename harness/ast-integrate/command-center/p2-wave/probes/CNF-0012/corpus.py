#!/usr/bin/env python3
"""Locate confirmation receipts on disk and apply the freshness rule."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from freshness import CLOSED_VERDICTS, evaluate_receipt
from phase15 import load_bearing_flags, phase15_units

SKIP_NAMES = frozenset(
    {
        "SUBAGENT-RETURN.json",
        "UNIT-ARTIFACT-MANIFEST.json",
        "CNF-0012-freshness-decay.json",
    }
)
SCAN_ROOTS = (
    "command-center/confirmation",
    "command-center/receipts",
)


def is_audit_report(doc: dict) -> bool:
    if doc.get("report_kind") in {"confirmation-audit", "freshness-decay"}:
        return True
    if doc.get("unit_id") == "CNF-0012" and "stale_list" in doc:
        return True
    return False


def is_confirmation_receipt(doc: Any) -> bool:
    if not isinstance(doc, dict) or is_audit_report(doc):
        return False
    if doc.get("architecture_id") or doc.get("report_kind") == "architecture-review":
        return False
    claim_id = doc.get("claim_id")
    if not isinstance(claim_id, str) or not claim_id.strip():
        return False
    verdict = str(doc.get("verdict") or doc.get("stored_verdict") or "").upper()
    if verdict not in CLOSED_VERDICTS:
        return False
    if doc.get("confirmer") or doc.get("source_probe") or "input_hashes" in doc:
        return True
    return False


def iter_json_files(repo: Path, roots: tuple[str, ...] | None = None) -> list[Path]:
    found: list[Path] = []
    for rel in roots if roots is not None else SCAN_ROOTS:
        root = Path(rel) if Path(rel).is_absolute() else repo / rel
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            if path.name in SKIP_NAMES:
                continue
            found.append(path)
    return found


def load_receipt(path: Path) -> dict | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not is_confirmation_receipt(doc):
        return None
    doc["_corpus_path"] = path.as_posix()
    return doc


def file_reader(repo: Path):
    def read(path_str: str) -> bytes | None:
        p = Path(path_str)
        candidates = [p] if p.is_absolute() else [repo / path_str, Path(path_str)]
        for cand in candidates:
            if cand.is_file():
                return cand.read_bytes()
        return None

    return read


def scan_corpus(
    repo: Path,
    *,
    now: datetime | None = None,
    roots: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    scan_roots = tuple(roots) if roots is not None else SCAN_ROOTS
    catalog_path = repo / "command-center" / "WORK-UNIT-CATALOG.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    p15 = phase15_units(catalog)
    examined = iter_json_files(repo, scan_roots)
    receipts: list[dict] = []
    for path in examined:
        rec = load_receipt(path)
        if rec is not None:
            receipts.append(rec)

    reader = file_reader(repo)
    rows = []
    for rec in receipts:
        ev = evaluate_receipt(rec, now=now, read_bytes=reader)
        flags = load_bearing_flags(rec, p15)
        ev["load_bearing_for_phase15"] = bool(flags)
        ev["load_bearing_reasons"] = flags
        ev["path"] = rec.get("_corpus_path")
        ev["advisory_class"] = bool(rec.get("advisory_class") or rec.get("unhashable_inputs"))
        rows.append(ev)

    stale = [r for r in rows if r["live_verdict"] == "STALE"]
    confirmed = [r for r in rows if r["live_verdict"] == "CONFIRMED"]
    load_bearing_stale = [r for r in stale if r["load_bearing_for_phase15"]]
    missing_hashes = [
        r for r in stale if "missing-input-hashes" in (r.get("reasons") or [])
    ]
    present_roots = {}
    for rel in scan_roots:
        root = Path(rel) if Path(rel).is_absolute() else repo / rel
        present_roots[rel] = root.is_dir()
    return {
        "scan_roots": list(scan_roots),
        "roots_present": present_roots,
        "files_examined": [
            (
                p.relative_to(repo).as_posix()
                if repo in p.parents or p == repo
                else p.as_posix()
            )
            for p in examined
        ],
        "files_examined_count": len(examined),
        "corpus_size": len(rows),
        "stale_count": len(stale),
        "confirmed_count": len(confirmed),
        "missing_input_hashes_count": len(missing_hashes),
        "load_bearing_stale_count": len(load_bearing_stale),
        "empty_corpus": len(rows) == 0,
        "empty_set_is_not_a_pass": True,
        "stale_list": stale,
        "load_bearing_stale": load_bearing_stale,
        "phase15_gate_ids": [u["id"] for u in p15],
        "phase15_gate_count": len(p15),
        "claim_registry_present": (repo / "command-center" / "CLAIM-REGISTRY.json").is_file(),
        "artifact_manifest_present": (
            repo / "command-center" / "ARTIFACT-MANIFEST.json"
        ).is_file(),
    }
