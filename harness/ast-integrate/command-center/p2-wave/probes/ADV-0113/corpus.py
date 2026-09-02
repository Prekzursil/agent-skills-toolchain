"""Blast-radius census of settled claim-shaped records missing source_probe.

Mechanically different from probe 1 (gate submission). Does not rewrite
the corpus (no ADV rebuild loop).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

SETTLED = frozenset({"CONFIRMED", "REFUTED"})
TEXT_KEYS = ("text", "claim", "question", "question_or_target", "statement")
ID_KEYS = ("id", "claim_id", "unit_id", "target_id")
SKIP_DIRS = {
    "__pycache__",
    "schema-deps",
    "node_modules",
    ".git",
}
CANONICAL_PATHS = (
    "command-center/CLAIM-REGISTRY.json",
    "platform/corpus/CANONICAL-CLAIMS.json",
)
WALK_GLOBS = (
    "command-center/receipts/*.json",
    "command-center/confirmation/*.json",
    "command-center/research/*.json",
)


def _has_text(obj: dict[str, Any]) -> bool:
    return any(isinstance(obj.get(k), str) and obj.get(k).strip() for k in TEXT_KEYS)


def _record_id(obj: dict[str, Any], rel: str, index: int) -> str:
    for key in ID_KEYS:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return f"{rel}#{index}"


def _walk_objects(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for val in node.values():
            yield from _walk_objects(val)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_objects(item)


def probe_present(obj: dict[str, Any], key: str) -> bool:
    probe = obj.get(key)
    if probe is None:
        return False
    if isinstance(probe, str):
        return bool(probe.strip())
    if isinstance(probe, dict):
        for field in ("tool", "engine", "shell", "field", "path", "instrument", "fingerprint", "sha256"):
            val = probe.get(field)
            if isinstance(val, str) and val.strip():
                return True
    return False


def is_settled_claim_shaped(obj: dict[str, Any]) -> bool:
    verdict = obj.get("verdict")
    if not isinstance(verdict, str) or verdict not in SETTLED:
        return False
    return _has_text(obj)


def audit_file(path: Path, repo: Path) -> list[dict[str, Any]]:
    rel = path.relative_to(repo).as_posix()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    rows: list[dict[str, Any]] = []
    for i, obj in enumerate(_walk_objects(doc)):
        if not is_settled_claim_shaped(obj):
            continue
        has_source = probe_present(obj, "source_probe")
        has_verifier = probe_present(obj, "verifier_probe")
        rows.append(
            {
                "id": _record_id(obj, rel, i),
                "path": rel,
                "verdict": obj.get("verdict"),
                "source_present": has_source,
                "verifier_present": has_verifier,
                "missing_source": not has_source,
            }
        )
    return rows


def census(repo: Path) -> dict[str, Any]:
    canonical = []
    for rel in CANONICAL_PATHS:
        path = repo / rel
        canonical.append(
            {
                "path": rel,
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for rel in CANONICAL_PATHS:
        path = repo / rel
        if path.is_file():
            for row in audit_file(path, repo):
                key = (row["path"], row["id"])
                if key not in seen:
                    seen.add(key)
                    records.append(row)
    for pattern in WALK_GLOBS:
        for path in sorted(repo.glob(pattern)):
            if not path.is_file():
                continue
            if path.name.startswith("_"):
                continue
            for row in audit_file(path, repo):
                key = (row["path"], row["id"])
                if key not in seen:
                    seen.add(key)
                    records.append(row)
    settled = len(records)
    missing_source = [r for r in records if r["missing_source"]]
    with_both = [
        r for r in records if r["source_present"] and r["verifier_present"]
    ]
    sample = missing_source[:12]
    return {
        "canonical_paths": canonical,
        "canonical_present": any(c["exists"] for c in canonical),
        "settled_claim_shaped": settled,
        "settled_missing_source": len(missing_source),
        "settled_with_both_probes": len(with_both),
        "sample_missing_source": sample,
        "every_settled_has_source": settled > 0 and len(missing_source) == 0,
        "note": (
            "Canonical CLAIM-REGISTRY.json and CANONICAL-CLAIMS.json are the "
            "named claim corpora. Receipts/confirmation records with "
            "verdict CONFIRMED|REFUTED plus a claim/text field are counted "
            "as claim-shaped. This census does not rewrite those records."
        ),
    }
