"""Two-directional registry vs disk reconciliation.

Signal A: existence probe on every candidate provenance path.
Signal B: enumerate workflow-bearing files by extension AND frontmatter,
then subtract the registry id set.

HIT requires a non-empty file. Empty existing files are PRESENT-EMPTY.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402

FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
ID_LINE = re.compile(r"(?m)^id:\s*[\"']?([^\"'\s#]+)")
SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules"}


def provenance_path(row: dict, disk_root: Path) -> Path | None:
    raw = row.get("provenance")
    if isinstance(raw, dict):
        raw = raw.get("path") or raw.get("file") or raw.get("source_path")
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("\\", "/")
    p = Path(text)
    if p.is_absolute():
        return p
    return disk_root / text


def classify_path(path: Path | None) -> dict:
    if path is None:
        return {
            "verdict": "PROVENANCE-UNAVAILABLE",
            "bytes": None,
            "exists": False,
            "path": None,
        }
    try:
        exists = path.exists()
    except OSError:
        exists = False
    if not exists:
        return {
            "verdict": "MISS",
            "bytes": None,
            "exists": False,
            "path": str(path),
        }
    if path.is_dir():
        return {
            "verdict": "PRESENT-DIR",
            "bytes": None,
            "exists": True,
            "path": str(path),
        }
    try:
        n = path.stat().st_size
    except OSError:
        return {
            "verdict": "MISS",
            "bytes": None,
            "exists": False,
            "path": str(path),
        }
    if n == 0:
        return {
            "verdict": "PRESENT-EMPTY",
            "bytes": 0,
            "exists": True,
            "path": str(path),
        }
    return {
        "verdict": "HIT",
        "bytes": n,
        "exists": True,
        "path": str(path),
    }


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def parse_frontmatter(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = FRONTMATTER.match(text)
    if not m:
        return None
    return m.group(1)


def extract_id(path: Path, root: Path, fm: str | None) -> str:
    if fm:
        m = ID_LINE.search(fm)
        if m:
            return m.group(1).strip()
    if path.name.lower() == "skill.md":
        return path.parent.name
    stem = path.stem
    if stem:
        return stem
    return _rel(path, root)


def is_workflow_bearing(path: Path, root: Path) -> tuple[bool, str, str | None]:
    if not path.is_file():
        return False, "not-a-file", None
    try:
        size = path.stat().st_size
    except OSError:
        return False, "stat-error", None
    if size == 0:
        return False, "empty", None
    rel = _rel(path, root)
    suffix = path.suffix.lower()
    name = path.name.lower()
    fm = None
    if suffix in {".md", ".yml", ".yaml"}:
        fm = parse_frontmatter(path)

    if name == "skill.md":
        return True, "skill-md", extract_id(path, root, fm)
    if "/.github/workflows/" in f"/{rel}" and suffix in {".yml", ".yaml"}:
        return True, "github-workflow-extension", extract_id(path, root, fm)
    if rel.startswith("workflows/") and suffix in {".md", ".yml", ".yaml", ".json"}:
        return True, "workflows-dir-extension", extract_id(path, root, fm)
    if rel.startswith("commands/") and suffix == ".md":
        return True, "commands-dir-extension", extract_id(path, root, fm)
    if fm:
        keys = ("name:", "description:", "argument-hint:", "allowed-tools:", "id:")
        if any(k in fm for k in keys):
            return True, "yaml-frontmatter", extract_id(path, root, fm)
    if suffix == ".json":
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict):
            if doc.get("kind") in {"workflow", "command", "skill"}:
                wid = str(doc.get("id") or path.stem)
                return True, "json-kind", wid
            if "jobs" in doc and "on" in doc:
                return True, "json-github-shape", str(doc.get("id") or path.stem)
    return False, "not-bearing", None


def iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


def sweep_disk(root: Path) -> list[dict]:
    rows = []
    for path in iter_files(root):
        bearing, reason, wid = is_workflow_bearing(path, root)
        rec = {
            "path": _rel(path, root),
            "abs_path": str(path),
            "bytes": path.stat().st_size,
            "bearing": bearing,
            "reason": reason,
            "id": wid,
        }
        rows.append(rec)
    return rows


def existence_probe(candidates: list[dict], disk_root: Path) -> list[dict]:
    rows = []
    for cand in candidates:
        cid = str(cand.get("id") or "")
        p = provenance_path(cand, disk_root)
        cls = classify_path(p)
        cls["id"] = cid
        cls["provenance_declared"] = cand.get("provenance")
        rows.append(cls)
    return rows


def both_directions(candidates: list[dict], disk_root: Path) -> dict:
    existence = existence_probe(candidates, disk_root)
    disk_rows = sweep_disk(disk_root)
    bearing = [r for r in disk_rows if r["bearing"] and r["id"]]
    registry_ids = {str(c["id"]) for c in candidates if c.get("id")}
    disk_ids = {str(r["id"]) for r in bearing}
    path_stale = [
        r for r in existence if r["verdict"] == "MISS"
    ]
    present_empty = [
        r for r in existence if r["verdict"] == "PRESENT-EMPTY"
    ]
    hits = [r for r in existence if r["verdict"] == "HIT"]
    registry_minus_disk = sorted(registry_ids - disk_ids)
    disk_minus_registry = sorted(disk_ids - registry_ids)
    reasons = {}
    for r in bearing:
        reasons.setdefault(r["reason"], 0)
        reasons[r["reason"]] += 1
    return {
        "n_candidates": len(candidates),
        "n_disk_files_walked": len(disk_rows),
        "n_workflow_bearing": len(bearing),
        "existence": existence,
        "disk_rows": disk_rows,
        "bearing": bearing,
        "verdict_counts": {
            "HIT": len(hits),
            "MISS": len(path_stale),
            "PRESENT-EMPTY": len(present_empty),
            "PROVENANCE-UNAVAILABLE": sum(
                1 for r in existence if r["verdict"] == "PROVENANCE-UNAVAILABLE"
            ),
            "PRESENT-DIR": sum(1 for r in existence if r["verdict"] == "PRESENT-DIR"),
        },
        "path_stale": path_stale,
        "present_empty": present_empty,
        "hits": hits,
        "discovery_reasons": reasons,
        "registry_minus_disk": {
            "count": len(registry_minus_disk),
            "ids": registry_minus_disk,
            "meaning": "registry ids with no workflow-bearing disk file of that id",
        },
        "disk_minus_registry": {
            "count": len(disk_minus_registry),
            "ids": disk_minus_registry,
            "meaning": "live workflow-bearing ids Prompt One / registry missed",
        },
        "path_stale_count": len(path_stale),
        "one_direction_only": not (
            len(registry_minus_disk) > 0 and len(disk_minus_registry) > 0
        ),
    }


def directions_admissible(report: dict) -> tuple[bool, str]:
    a = report.get("registry_minus_disk")
    b = report.get("disk_minus_registry")
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False, "missing-direction-object"
    if not isinstance(a.get("count"), int) or not isinstance(b.get("count"), int):
        return False, "count-absent-or-not-int"
    if a["count"] < 0 or b["count"] < 0:
        return False, "negative-count"
    if "ids" not in a or "ids" not in b:
        return False, "ids-absent"
    if a["count"] != len(a["ids"]) or b["count"] != len(b["ids"]):
        return False, "count-ids-mismatch"
    return True, "both-directions-present"


def fixture_reconcile() -> dict:
    meta = E.build_estate()
    candidates = E.load_fixture_candidates()
    report = both_directions(candidates, E.DISK)
    report["estate"] = meta
    report["disk_root"] = str(E.DISK)
    return report


def host_census() -> dict[str, Any]:
    regs = E.hunt_host_registry()
    trees = E.hunt_host_trees()
    present_reg = [r for r in regs if r["exists"] and r["bytes"] > 0]
    live_files: list[dict] = []
    for t in trees:
        root = Path(t["path"])
        if not t["is_dir"]:
            continue
        for row in sweep_disk(root):
            if row["bearing"]:
                live_files.append(row)
    return {
        "registry_hunt": regs,
        "host_registry_present": bool(present_reg),
        "host_registry_n": None,
        "trees": trees,
        "host_trees_with_files": [
            t for t in trees if t["is_dir"] and t["file_count"] > 0
        ],
        "host_workflow_bearing": live_files,
        "host_workflow_bearing_count": len(live_files),
        "catalog_pinned_n": E.CATALOG_PINNED_N,
        "inspect_sha256": E.HOST_REGISTRY_SHA256,
        "note": (
            "284-row Prompt One registry is not on this Linux worktree; "
            "host both-direction counts against that file are NOT-COMPUTABLE."
        ),
    }
