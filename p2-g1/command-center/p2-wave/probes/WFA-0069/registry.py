"""Locate the 122 ADOPT-AS-IS discovery candidates without inventing IDs.

When 08-WORKFLOW-CANDIDATE-REGISTRY.json is absent, return 122 slots whose
smoke case cannot be constructed. Slot IDs are not discovery IDs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

EXPECTED_N = 122
CLASS_ADOPT = "ADOPT-AS-IS"

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def search_paths(repo: Path | None = None) -> list[Path]:
    root = repo or REPO
    env = os.environ.get("WFA_REGISTRY_PATH", "").strip()
    extra = [Path(env)] if env else []
    return extra + [
        Path("/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
        Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
        root / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        root / "command-center" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        root / "command-center" / "_wfa2_entries.json",
        root / "command-center" / "catalog-slices" / "WFA-1.json",
        root / "command-center" / "wfa" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    ]


def _candidates_from_doc(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        rows = doc.get("candidates")
        if not isinstance(rows, list):
            rows = doc.get("entries")
        if not isinstance(rows, list):
            rows = []
    else:
        rows = []
    adopt = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        klass = str(row.get("classification") or row.get("disposition") or "")
        if klass == CLASS_ADOPT:
            adopt.append(row)
    return adopt


def load_registry(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    searched = [str(p) for p in search_paths(root)]
    found_path: Path | None = None
    rows: list[dict[str, Any]] = []
    digest = None
    for path in search_paths(root):
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        adopt = _candidates_from_doc(doc)
        if not adopt and path.name == "_wfa2_entries.json":
            continue
        found_path = path
        rows = adopt
        import hashlib

        digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        break

    if found_path is not None and rows:
        records = []
        for row in rows[:EXPECTED_N]:
            cid = str(row.get("id") or row.get("name") or "").strip()
            if not cid:
                continue
            records.append(
                {
                    "candidate_id": cid,
                    "discovery_id_known": True,
                    "name": row.get("name"),
                    "provenance": row.get("provenance"),
                    "source_path": _resolve_source(root, row),
                    "prior_classification": CLASS_ADOPT,
                }
            )
        while len(records) < EXPECTED_N:
            n = len(records) + 1
            records.append(_slot(n))
        records = records[:EXPECTED_N]
        return {
            "found": True,
            "path": str(found_path),
            "sha256": digest,
            "searched_paths": searched,
            "adopt_as_is_count": len(rows),
            "records": records,
        }

    return {
        "found": False,
        "path": None,
        "sha256": None,
        "searched_paths": searched,
        "adopt_as_is_count": 0,
        "records": [_slot(i) for i in range(1, EXPECTED_N + 1)],
    }


def _slot(n: int) -> dict[str, Any]:
    return {
        "candidate_id": f"wfa-0069-unresolved-adopt-as-is-{n:03d}",
        "discovery_id_known": False,
        "name": None,
        "provenance": None,
        "source_path": None,
        "prior_classification": CLASS_ADOPT,
    }


def _resolve_source(root: Path, row: dict[str, Any]) -> str | None:
    name = str(row.get("name") or "").strip()
    prov = row.get("provenance")
    guesses: list[Path] = []
    if isinstance(prov, str) and prov.strip():
        guesses.append(Path(prov))
        guesses.append(root / prov)
    if isinstance(prov, dict):
        for key in ("path", "file", "source"):
            val = prov.get(key)
            if isinstance(val, str) and val.strip():
                guesses.append(Path(val))
                guesses.append(root / val)
    if name:
        guesses.extend(
            [
                root / name,
                root / "workflows" / name,
                Path.home() / ".claude" / "workflows" / name,
            ]
        )
    for path in guesses:
        if path.is_file() and path.stat().st_size > 0:
            return str(path)
    return None
