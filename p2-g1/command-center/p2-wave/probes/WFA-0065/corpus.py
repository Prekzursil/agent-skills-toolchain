"""Reachable-corpus incidence for WFA-0065.

The 284-row workflow-candidate registry is not on this Linux worktree.
Novelty is therefore scored against WORK-UNIT-CATALOG.json plus on-tree
tools/, never claimed against the missing 284 candidates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SELF_ID = "WFA-0065"

SIGNATURES: dict[str, tuple[str, ...]] = {
    "delphi": (r"\bdelphi\b",),
    "jury-deciders": (
        r"jury topology",
        r"deciders who did not argue",
        r"who did not argue",
        r"pcj\.py",
    ),
    "quorum": (r"\bquorum\b",),
    "typed-handoff": (r"typed handoff", r"handoff record replacing raw-output"),
    "instruction-readback": (
        r"timeout readback",
        r"instruction readback",
        r"clearance readback",
        r"\bhearback\b",
        r"ATC readback",
        r"pilot readback",
    ),
    "receiver-synthesis": (
        r"synthesis by receiver",
        r"\bi-pass\b",
        r"\bsbar\b",
        r"receiver synthesis",
    ),
    "unity-of-command": (r"unity of command", r"reports to only one"),
    "span-of-control": (r"span of control",),
    "sterile-cockpit": (r"sterile cockpit", r"critical phase of flight"),
    "isolated-peer-review": (
        r"double-?blind",
        r"isolated parallel review",
        r"reviewers do not see each other",
    ),
    "paxos-byzantine": (r"\bpaxos\b", r"\byzantine\b"),
}

TIMEOUT_READBACK = re.compile(r"timeout", re.I)


def _hay(unit: dict[str, Any]) -> str:
    parts = [
        str(unit.get("id") or ""),
        str(unit.get("title") or ""),
        str(unit.get("question_or_target") or ""),
        str(unit.get("output_path") or ""),
    ]
    return "\n".join(parts)


def _match_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text, flags=re.I) for p in patterns)


def scan_catalog() -> dict[str, list[dict[str, str]]]:
    hits: dict[str, list[dict[str, str]]] = {k: [] for k in SIGNATURES}
    if not CATALOG.is_file():
        return hits
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if uid == SELF_ID:
            continue
        text = _hay(unit)
        for sig, pats in SIGNATURES.items():
            if not _match_any(text, pats):
                continue
            if sig == "instruction-readback" and TIMEOUT_READBACK.search(text):
                kind = "near-miss-timeout-readback"
            else:
                kind = "catalog-unit"
            hits[sig].append(
                {
                    "id": uid,
                    "title": str(unit.get("title") or "")[:180],
                    "kind": kind,
                }
            )
    for sig in hits:
        hits[sig] = sorted(hits[sig], key=lambda r: r["id"])
    return hits


def registry_status() -> dict[str, Any]:
    candidates = [
        REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        REPO / "command-center" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    ]
    present = [str(p) for p in candidates if p.is_file()]
    return {
        "present": bool(present),
        "paths_checked": [str(p) for p in candidates],
        "found": present,
        "novelty_scope": (
            "284-candidate-registry"
            if present
            else "reachable-catalog-and-repo-only; 284-row registry absent"
        ),
    }


def scan() -> dict[str, Any]:
    catalog_hits = scan_catalog()
    n_units = 0
    if CATALOG.is_file():
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
        n_units = len(data.get("work_units") or [])
    return {
        "catalog_units_scanned": n_units,
        "registry": registry_status(),
        "hits": catalog_hits,
    }
