"""Node-by-node provenance resolution that fails closed.

Resolution reads the *cited source* and never infers an origin from the
node name. A name that happens to match a live file is not evidence.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

WIN_ABS = re.compile(r"^[A-Za-z]:/")
HARNESS_MARK = ".claude/harness-restore-20260806/"
FABRICATION_MARKERS = (b"WFA-0153-FABRICATED-SOURCE",)

BLOCKERS = (
    "cited-source-missing-field",
    "cited-source-absent",
    "cited-source-not-a-file",
    "cited-source-empty",
    "cited-source-unreadable",
    "cited-source-fabricated",
)

STATUS_RESOLVED = "RESOLVED"
STATUS_UNRESOLVED = "UNRESOLVED"


def cited_to_candidates(repo: Path, cited: str) -> list[Path]:
    """Map a citation string to candidate paths. Never uses a node name."""
    cited = cited.replace("\\", "/")
    out: list[Path] = []
    if WIN_ABS.match(cited):
        out.append(Path(cited))
        if HARNESS_MARK in cited:
            tail = cited.split(HARNESS_MARK, 1)[1]
            out.append(Path.home() / ".claude/harness-restore-20260806" / tail)
            out.append(repo / "harness-restore-20260806" / tail)
        return out
    p = Path(cited)
    if p.is_absolute():
        out.append(p)
        return out
    out.append(repo / cited)
    return out


def _read_pathlib(path: Path) -> bytes:
    return path.read_bytes()


def _read_stat_open(path: Path) -> bytes:
    os.stat(path)
    with open(path, "rb") as fh:
        return fh.read()


def resolve_cited_source(
    repo: Path,
    cited_source: Any,
    *,
    method: str = "pathlib",
) -> dict[str, Any]:
    """Resolve by fetching or reading cited_source only.

    Node name is intentionally not a parameter. Callers that pass a
    plausible name cannot influence the verdict through this function.
    """
    if method not in {"pathlib", "stat-open"}:
        raise ValueError(f"unknown resolve method {method!r}")
    reader = _read_pathlib if method == "pathlib" else _read_stat_open

    if not isinstance(cited_source, str) or not cited_source.strip():
        return {
            "status": STATUS_UNRESOLVED,
            "blocker": "cited-source-missing-field",
            "read_path": None,
            "sha256": None,
            "bytes": 0,
            "method": method,
        }

    last_reason = "cited-source-absent"
    last_path: str | None = None
    for cand in cited_to_candidates(repo, cited_source.strip()):
        last_path = str(cand)
        try:
            if not cand.exists():
                last_reason = "cited-source-absent"
                continue
            if not cand.is_file():
                last_reason = "cited-source-not-a-file"
                continue
            data = reader(cand)
        except OSError:
            last_reason = "cited-source-unreadable"
            continue
        if len(data) == 0:
            return {
                "status": STATUS_UNRESOLVED,
                "blocker": "cited-source-empty",
                "read_path": cand.as_posix() if cand.is_absolute() else str(cand),
                "sha256": None,
                "bytes": 0,
                "method": method,
            }
        if any(m in data for m in FABRICATION_MARKERS):
            return {
                "status": STATUS_UNRESOLVED,
                "blocker": "cited-source-fabricated",
                "read_path": str(cand),
                "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
                "bytes": len(data),
                "method": method,
            }
        digest = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        return {
            "status": STATUS_RESOLVED,
            "blocker": None,
            "read_path": str(cand),
            "sha256": digest,
            "bytes": len(data),
            "method": method,
        }

    return {
        "status": STATUS_UNRESOLVED,
        "blocker": last_reason,
        "read_path": last_path,
        "sha256": None,
        "bytes": 0,
        "method": method,
    }


def resolve_node(repo: Path, node: dict[str, Any], *, method: str = "pathlib") -> dict[str, Any]:
    core = resolve_cited_source(repo, node.get("cited_source"), method=method)
    return {
        "node_id": node.get("id"),
        "name": node.get("name"),
        "cited_source": node.get("cited_source"),
        "kind": node.get("kind"),
        **core,
    }


def settle_graph(repo: Path, graph: dict[str, Any], *, method: str = "pathlib") -> dict[str, Any]:
    verdicts = [resolve_node(repo, n, method=method) for n in graph.get("nodes") or []]
    unresolved = [v for v in verdicts if v["status"] != STATUS_RESOLVED]
    resolved = [v for v in verdicts if v["status"] == STATUS_RESOLVED]
    for v in unresolved:
        if not v.get("blocker"):
            raise RuntimeError(f"unresolved node {v.get('node_id')} lacks a named blocker")
        if v["blocker"] not in BLOCKERS:
            raise RuntimeError(f"unknown blocker {v['blocker']!r} on {v.get('node_id')}")
    resolved_ids = sorted(str(v["node_id"]) for v in resolved)
    id_blob = "\n".join(resolved_ids).encode("utf-8")
    return {
        "method": method,
        "node_count": len(verdicts),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "resolution_rate": (len(resolved) / len(verdicts)) if verdicts else 0.0,
        "resolved_ids_sha256": hashlib.sha256(id_blob).hexdigest(),
        "verdicts": verdicts,
        "survivors": [
            {
                "node_id": v["node_id"],
                "name": v.get("name"),
                "cited_source": v.get("cited_source"),
                "blocker": v["blocker"],
                "status": STATUS_UNRESOLVED,
                "method": method,
            }
            for v in unresolved
        ],
    }
