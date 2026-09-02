"""Classify recovered public surface against a retained tree.

PRESERVED: symbol/token exists in a retained artifact (path cited).
LOST: executable/export/CLI/hook/command exists nowhere retained.
LOST-COVERAGE: a deleted TEST assertion has no equivalent in the retained suite
(reported as lost coverage, not only as a lost file).
RETIRED: recovered file has no extractable behaviour (narrative / empty stub).
UNPROVEN: recovery did not yield bytes.
"""
from __future__ import annotations

from pathlib import Path

PRESERVED = "PRESERVED"
LOST = "LOST"
LOST_COVERAGE = "LOST-COVERAGE"
RETIRED = "RETIRED"
UNPROVEN = "UNPROVEN"


def index_retained(root: Path) -> list[dict]:
    rows: list[dict] = []
    if not root.is_dir():
        return rows
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        text = raw.decode("utf-8", "replace")
        is_test = (
            "/tests/" in rel
            or path.name.startswith("test")
            or ".test." in path.name
        )
        rows.append(
            {
                "path": rel,
                "text": text,
                "raw": raw,
                "is_test": is_test,
            }
        )
    return rows


def _hits(token: str, retained: list[dict], *, tests_only: bool = False) -> list[str]:
    if not token:
        return []
    out: list[str] = []
    for r in retained:
        if tests_only and not r["is_test"]:
            continue
        if token in r["text"]:
            out.append(r["path"])
    return out


def classify_element(element: dict, retained: list[dict]) -> dict:
    kind = element.get("kind") or "none"
    token = str(element.get("token") or "")
    symbol = str(element.get("symbol") or "")
    path = str(element.get("path") or "")
    needle = token or symbol

    if kind == "none" or not needle:
        return {
            "path": path,
            "kind": "none",
            "symbol": symbol,
            "token": token,
            "classification": RETIRED,
            "retained_path": None,
            "reason": "no extractable public behaviour in recovered bytes",
        }

    if kind in {"test", "test-assertion"}:
        hits = _hits(needle, retained, tests_only=True)
        if not hits and symbol and symbol != needle:
            hits = _hits(symbol, retained, tests_only=True)
        if hits:
            return {
                "path": path,
                "kind": kind,
                "symbol": symbol,
                "token": token,
                "classification": PRESERVED,
                "retained_path": hits[0],
                "reason": "equivalent assertion/test present in retained suite",
            }
        return {
            "path": path,
            "kind": kind,
            "symbol": symbol,
            "token": token,
            "classification": LOST_COVERAGE,
            "retained_path": None,
            "reason": "deleted test assertion has no equivalent in retained suite",
        }

    hits = _hits(needle, retained, tests_only=False)
    if not hits and symbol and symbol != needle:
        hits = _hits(symbol, retained, tests_only=False)
    if hits:
        return {
            "path": path,
            "kind": kind,
            "symbol": symbol,
            "token": token,
            "classification": PRESERVED,
            "retained_path": hits[0],
            "reason": "symbol present in retained artifact",
        }
    return {
        "path": path,
        "kind": kind,
        "symbol": symbol,
        "token": token,
        "classification": LOST,
        "retained_path": None,
        "reason": "behaviour exists nowhere in the retained tree",
    }


def classify_all(elements: list[dict], retained: list[dict]) -> list[dict]:
    return [classify_element(e, retained) for e in elements]
