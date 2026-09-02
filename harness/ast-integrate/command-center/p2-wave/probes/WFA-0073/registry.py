"""Load the 284-row candidate registry, or a catalog-histogram stand-in.

The live Prompt One file (08-WORKFLOW-CANDIDATE-REGISTRY.json, 284 records)
is the Windows harness-restore blob. When that file is absent on this Linux
worktree, the census uses a stand-in whose classification histogram is taken
from WORK-UNIT-CATALOG.json WFA-0005 evidence_requirement, with empty typed
evidence. Empty evidence is fail-closed for gated classes; it is not invented
passing smoke / preservation / probe / adapter payload.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
STANDIN_NOTE = (
    "catalog-histogram-stand-in: live 08-WORKFLOW-CANDIDATE-REGISTRY.json "
    "absent; 284 rows reconstructed from WFA-0005 histogram; typed evidence "
    "left empty (fail-closed)."
)

# WFA-0005 evidence_requirement A, recounted: 122+44+43+24+20+15+6+6+4 = 284.
CATALOG_HISTOGRAM: list[tuple[str, int]] = [
    ("ADOPT-AS-IS", 122),
    ("UNKNOWN-NEEDS-PROBE", 44),
    ("DISTILL", 43),
    ("RETIRE", 24),
    ("ADOPT-WITH-WRAPPER", 20),
    ("REPAIR", 15),
    ("EXTEND", 6),
    ("MERGE", 6),
    ("SPECIALIZE", 4),
]

LIVE_CANDIDATES = [
    Path.home() / ".claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/opt/p2/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/sources/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/sources/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center/wfa/WFA-0078-candidate-registry-v2.json",
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
]


def catalog_histogram() -> dict[str, int]:
    return {name: n for name, n in CATALOG_HISTOGRAM}


def catalog_n() -> int:
    return sum(n for _, n in CATALOG_HISTOGRAM)


def _candidates_of(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, dict):
        raw = doc.get("candidates")
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)]
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    return []


def find_live_registry() -> Path | None:
    for path in LIVE_CANDIDATES:
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path
        except OSError:
            continue
    return None


def standin_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cls, n in CATALOG_HISTOGRAM:
        slug = cls.lower().replace("_", "-")
        for i in range(1, n + 1):
            rows.append(
                {
                    "id": f"hist-{slug}-{i:03d}",
                    "name": f"stand-in {cls} {i}",
                    "classification": cls,
                    "evidence": {},
                    "notes": STANDIN_NOTE,
                    "origin": "WFA-0005-catalog-histogram",
                }
            )
    return rows


def load_registry(path: Path | None = None) -> dict[str, Any]:
    """Return {path, live, records, n, source}."""
    if path is not None:
        doc = json.loads(path.read_text(encoding="utf-8"))
        recs = _candidates_of(doc)
        return {
            "path": str(path),
            "rel": _rel(path),
            "live": True,
            "source": "explicit",
            "records": recs,
            "n": len(recs),
        }
    live = find_live_registry()
    if live is not None:
        doc = json.loads(live.read_text(encoding="utf-8"))
        recs = _candidates_of(doc)
        return {
            "path": str(live),
            "rel": _rel(live),
            "live": True,
            "source": "live-registry",
            "records": recs,
            "n": len(recs),
        }
    recs = standin_records()
    return {
        "path": None,
        "rel": None,
        "live": False,
        "source": "catalog-histogram-stand-in",
        "note": STANDIN_NOTE,
        "records": recs,
        "n": len(recs),
        "histogram": catalog_histogram(),
        "catalog_n": catalog_n(),
    }


def _rel(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def catalog_unit(uid: str = "WFA-0073") -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for item in data.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == uid:
            return item
    raise RuntimeError(f"catalog-missing-{uid}")
