"""Locate confirmation receipts and score CONFIRMED rows for same-probe re-runs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from fingerprint import independence_check, REJECTED, VIOLATION, UNDECLARED_SOURCE, SAME_PROBE_RERUN

SKIP_NAMES = {
    "CNF-0006-probe-independence.json",
    "UNIT-ARTIFACT-MANIFEST.json",
    "SUBAGENT-RETURN.json",
}

CONFIRMED_VALUES = {"CONFIRMED", "confirmed"}

SEARCH_ROOTS = (
    "command-center/confirmation",
    "command-center/receipts",
    "command-center/events",
)


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _looks_like_receipt(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    if "verdict" not in obj:
        return False
    keys = set(obj)
    probe_keys = {
        "source_probe",
        "verifier_probe",
        "source_probe_fingerprint",
        "verifier_probe_fingerprint",
        "confirmer",
        "confirmer_id",
        "claim_id",
    }
    return bool(keys & probe_keys)


def _iter_receipts(node: Any) -> Iterator[dict]:
    if isinstance(node, dict):
        if _looks_like_receipt(node):
            yield node
        for key in ("receipts", "confirmations", "records", "items", "claims"):
            child = node.get(key)
            if isinstance(child, list):
                for item in child:
                    yield from _iter_receipts(item)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_receipts(item)


def _receipt_id(receipt: dict, path: Path, index: int) -> str:
    for key in ("id", "claim_id", "receipt_id", "confirmation_id"):
        value = receipt.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{path.as_posix()}#{index}"


def _source_of(receipt: dict) -> Any:
    if "source_probe" in receipt:
        return receipt.get("source_probe")
    return receipt.get("source_probe_fingerprint")


def _verifier_of(receipt: dict) -> Any:
    if "verifier_probe" in receipt:
        return receipt.get("verifier_probe")
    return receipt.get("verifier_probe_fingerprint")


def scan_corpus(repo: Path) -> dict:
    files_examined: list[str] = []
    confirmed: list[dict] = []
    missing_roots: list[str] = []
    for rel in SEARCH_ROOTS:
        root = repo / rel
        if not root.exists():
            missing_roots.append(rel)
            continue
        paths = [root] if root.is_file() else sorted(root.rglob("*.json"))
        for path in paths:
            if path.name in SKIP_NAMES:
                continue
            files_examined.append(path.relative_to(repo).as_posix())
            data = _load(path)
            if data is None:
                continue
            for i, receipt in enumerate(_iter_receipts(data)):
                verdict = str(receipt.get("verdict") or "")
                if verdict not in CONFIRMED_VALUES:
                    continue
                check = independence_check(_source_of(receipt), _verifier_of(receipt))
                rid = _receipt_id(receipt, path.relative_to(repo), i)
                confirmed.append(
                    {
                        "id": rid,
                        "path": path.relative_to(repo).as_posix(),
                        "verdict": verdict,
                        "check": check,
                    }
                )

    same = [row for row in confirmed if row["check"]["classification"] == SAME_PROBE_RERUN]
    undeclared = [row for row in confirmed if row["check"]["classification"] == UNDECLARED_SOURCE]
    n = len(confirmed)
    percentage = (100.0 * len(same) / n) if n else None
    offenders = [
        {
            "id": row["id"],
            "path": row["path"],
            "classification": row["check"]["classification"],
            "source_fingerprint": row["check"]["source_fingerprint"],
            "verifier_fingerprint": row["check"]["verifier_fingerprint"],
        }
        for row in confirmed
        if row["check"]["verdict"] in {REJECTED, VIOLATION}
    ]
    return {
        "roots": list(SEARCH_ROOTS),
        "missing_roots": missing_roots,
        "files_examined": files_examined,
        "files_examined_count": len(files_examined),
        "confirmed_count": n,
        "same_probe_rerun_count": len(same),
        "undeclared_source_count": len(undeclared),
        "percentage": percentage,
        "percentage_note": (
            f"{len(same)} of {n} CONFIRMED receipts are same-probe re-runs"
            if n
            else "0 of 0 CONFIRMED receipts in the live confirmation corpus; empty set is not a pass"
        ),
        "empty_corpus_is_not_a_pass": True,
        "offender_ids": [row["id"] for row in same] + [row["id"] for row in undeclared],
        "offenders": offenders,
        "same_probe_ids": [row["id"] for row in same],
        "undeclared_source_ids": [row["id"] for row in undeclared],
    }
