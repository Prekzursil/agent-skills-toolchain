"""Candidate corpus for WFA-0040 failure-behaviour extraction.

Live 284-row registry is loaded when present. This Linux worktree does not
vend the Windows harness-restore path; absence is recorded, not invented.
In-tree workflow definitions are extracted as a second, cited population.
Planted controls always participate so the three catalog tests are live.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EXPECTED_LIVE_N = 284

REGISTRY_BASENAME = "08-WORKFLOW-CANDIDATE-REGISTRY.json"

# Catalog-cited families (WFA-0042 inspect of the live registry).
LIVE_FAMILY_COUNTS = {
    "A-saved-workflow": 10,
    "B-repo-workflow": 4,
    "C-repo-tool": 25,
    "D-harness-runtime": 6,
    "E-agent": 19,
    "F-plugin": 21,
    "G-skill": 96,
    "H-executed-corpus": 72,
    "I-command": 31,
}

FOUR_MODES = ("partial_result", "hung_unit", "timeout", "dead_monitor")

# Spec line map from ARC-0005 / catalog anchors for the four WFA-0040 modes.
MODE_SPEC = {
    "partial_result": {
        "spec_lines": [11313],
        "class_id": "FC-11313",
        "name": "partial artifact without sentinel / partial result",
    },
    "hung_unit": {
        "spec_lines": [11317],
        "class_id": "FC-11317",
        "name": "one hung unit blocks a large batch",
    },
    "timeout": {
        "spec_lines": [11315, 11316],
        "class_id": "FC-timeout",
        "name": "timeout / stall-from-mtime coupling",
    },
    "dead_monitor": {
        "spec_lines": [11315],
        "class_id": "FC-11315",
        "name": "dead monitor with live work / orchestrator death",
    },
}


def _rec(
    cid: str,
    *,
    family: str,
    name: str,
    does: str,
    mechanisms: str = "",
    notes: str = "",
    runtime: str = "",
    origin: str = "planted-control",
    provenance: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": cid,
        "family": family,
        "name": name,
        "does": does,
        "mechanisms": mechanisms,
        "notes": notes,
        "runtime": runtime,
        "origin": origin,
        "provenance": provenance,
        "corpus_tag": "planted",
    }
    if extra:
        row.update(extra)
    return row


def planted_candidates() -> list[dict[str, Any]]:
    """Catalog tests require these both-states plants, not a live 284-row file."""
    return [
        _rec(
            "plant-none",
            family="CONTROL",
            name="no-declared-failure-behaviour",
            does=(
                "Runs a sequence of stages named load, transform, and emit, then "
                "writes one final receipt. Stage tools are Read and Write."
            ),
            notes="No recovery, liveness, or deadline handling is declared.",
            provenance="command-center/p2-wave/probes/WFA-0040/corpus.py:plant-none",
        ),
        _rec(
            "plant-inferred-graceful",
            family="CONTROL",
            name="prose-assumes-graceful-defaults",
            does=(
                "When a recovery path is unspecified the workflow is assumed graceful "
                "and uses a safe-default. Operators may treat silence as healthy."
            ),
            notes="Inference is forbidden. Unnamed modes stay UNDEFINED.",
            provenance="command-center/p2-wave/probes/WFA-0040/corpus.py:plant-inferred-graceful",
        ),
        _rec(
            "plant-memory-until-end",
            family="CONTROL",
            name="holds-results-in-memory-until-the-end",
            does=(
                "Accumulates every stage result in memory until the end, then writes "
                "one blob. A 70-minute run can complete its work and write nothing "
                "if the process dies before the final flush."
            ),
            mechanisms="in-memory buffer; single write at completion",
            notes="Must be flagged against the write-as-you-go mandate (fan-out C1).",
            provenance="command-center/p2-wave/probes/WFA-0040/corpus.py:plant-memory-until-end",
        ),
        _rec(
            "plant-four-modes",
            family="CONTROL",
            name="all-four-failure-modes-named-separately",
            does=(
                "On a partial result, flush the bytes already written to disk with "
                "no completion sentinel. On a hung unit, classify STALLED and release "
                "the slot so siblings continue. On a timeout, emit FAILED:timeout and "
                "close the barrier on survivors. On a dead monitor, treat the worker "
                "as live until a heartbeat gap exceeds T rather than reading mtimes."
            ),
            mechanisms="per-unit pipeline; write-as-you-go durable on disk; heartbeat",
            notes="Four modes reported separately; a single aggregate would hide gaps.",
            provenance="command-center/p2-wave/probes/WFA-0040/corpus.py:plant-four-modes",
        ),
        _rec(
            "plant-aggregate-only",
            family="CONTROL",
            name="single-aggregate-on-any-error",
            does=(
                "On any error the workflow continues. Failures are handled in one "
                "aggregate catch-all so operators see a single failure column."
            ),
            notes="Aggregate must not fill all four modes.",
            provenance="command-center/p2-wave/probes/WFA-0040/corpus.py:plant-aggregate-only",
        ),
        _rec(
            "plant-write-as-you-go",
            family="CONTROL",
            name="write-as-you-go-compliant",
            does=(
                "Each stage flushes a durable on disk receipt before the next stage "
                "starts (write-as-you-go). Bytes already produced remain readable if "
                "a later stage dies. No other recovery path is written down."
            ),
            provenance="command-center/p2-wave/probes/WFA-0040/corpus.py:plant-write-as-you-go",
        ),
        _rec(
            "plant-timeout-only",
            family="CONTROL",
            name="timeout-behaviour-only",
            does=(
                "On a timeout the runner classifies the unit FAILED:timeout. "
                "No other recovery path is written down."
            ),
            provenance="command-center/p2-wave/probes/WFA-0040/corpus.py:plant-timeout-only",
        ),
    ]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def registry_search_paths() -> list[Path]:
    env = os.environ.get("WFA_CANDIDATE_REGISTRY", "").strip()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    out.extend(
        [
            Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806")
            / REGISTRY_BASENAME,
            Path("/c/Users/Prekzursil/.claude/harness-restore-20260806")
            / REGISTRY_BASENAME,
            Path("C:/Users/Prekzursil/.claude/harness-restore-20260806")
            / REGISTRY_BASENAME,
            REPO / REGISTRY_BASENAME,
            REPO / "command-center" / REGISTRY_BASENAME,
            REPO / "command-center" / "p2-wave" / REGISTRY_BASENAME,
            REPO / "command-center" / "wfa" / REGISTRY_BASENAME,
            HERE / "fixtures" / "live-registry-snapshot.json",
            Path.home() / ".claude" / "harness-restore-20260806" / REGISTRY_BASENAME,
        ]
    )
    # Dedup while preserving order.
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _candidates_from_doc(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        rows = [x for x in doc if isinstance(x, dict) and x.get("id")]
        return rows
    if isinstance(doc, dict):
        for key in ("candidates", "records", "items", "workflows"):
            val = doc.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict) and x.get("id")]
        if doc.get("id"):
            return [doc]
    return []


def load_live_registry() -> dict[str, Any]:
    attempts = []
    for path in registry_search_paths():
        exists = path.is_file()
        rec = {
            "path": str(path),
            "exists": exists,
            "bytes": path.stat().st_size if exists else 0,
        }
        attempts.append(rec)
        if not exists:
            continue
        doc = _read_json(path)
        rows = _candidates_from_doc(doc)
        if not rows:
            rec["parse"] = "no-candidate-array"
            continue
        for row in rows:
            row.setdefault("corpus_tag", "live-registry")
            row.setdefault("origin", str(path))
        return {
            "present": True,
            "path": str(path.as_posix()) if path.is_absolute() else str(path),
            "bytes": rec["bytes"],
            "n": len(rows),
            "candidates": rows,
            "attempts": attempts,
        }
    return {
        "present": False,
        "path": None,
        "bytes": 0,
        "n": 0,
        "candidates": [],
        "attempts": attempts,
        "honest_null": True,
        "note": (
            "08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this Linux worktree. "
            "Rows are not invented. Expected live n=284 remains an honest null."
        ),
    }


def _flatten_prose(obj: Any, skip_keys: set[str] | None = None) -> str:
    skip = skip_keys or {"timeout_seconds", "$schema", "sha256", "bytes"}
    parts: list[str] = []

    def walk(x: Any, key: str = "") -> None:
        if key in skip:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, str(k))
        elif isinstance(x, list):
            for item in x:
                walk(item, key)
        elif isinstance(x, str) and x.strip():
            parts.append(x.strip())

    walk(obj)
    return "\n".join(parts)


def in_tree_candidates() -> list[dict[str, Any]]:
    """Workflow definitions that actually exist on this worktree."""
    specs = [
        (
            "tools/blueprints/library/code-review/workflow.json",
            "B-repo-workflow",
        ),
        (
            "tools/blueprints/library/tdd-implementation/workflow.json",
            "B-repo-workflow",
        ),
        (
            "tools/blueprints/library/planning/workflow.json",
            "B-repo-workflow",
        ),
        (
            "tools/blueprints/library/architecture-tournament/workflow.json",
            "B-repo-workflow",
        ),
        (
            "command-center/p2-wave/probes/ARC-0048/fixtures/workflow.json",
            "CONTROL-IN-TREE",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for rel, family in specs:
        path = REPO / rel
        if not path.is_file():
            continue
        doc = _read_json(path)
        if not isinstance(doc, dict):
            continue
        cid = str(doc.get("id") or path.stem)
        prose = _flatten_prose(doc)
        stop = doc.get("stop_rule") if isinstance(doc.get("stop_rule"), dict) else {}
        on_error = stop.get("on_error") if isinstance(stop, dict) else None
        rows.append(
            {
                "id": cid,
                "family": family,
                "name": str(doc.get("name") or doc.get("id") or path.name),
                "does": str(doc.get("description") or prose[:2000]),
                "mechanisms": json.dumps(doc.get("stages") or [], sort_keys=True)[:4000],
                "notes": (
                    f"on_error={on_error}; stop={stop.get('expression') if isinstance(stop, dict) else None}"
                ),
                "runtime": "",
                "origin": rel,
                "provenance": rel,
                "corpus_tag": "in-tree",
                "defining_document": rel,
            }
        )
    hatch = (
        REPO
        / "command-center"
        / "p2-wave"
        / "probes"
        / "ARC-0016"
        / "fixtures"
        / "hatch-run"
        / "typed"
        / "catalogs"
        / "workflows.json"
    )
    if hatch.is_file():
        doc = _read_json(hatch)
        members = []
        if isinstance(doc, dict):
            members = doc.get("members") or []
        if isinstance(members, list):
            for mem in members:
                if not isinstance(mem, dict) or not mem.get("id"):
                    continue
                rel = hatch.relative_to(REPO).as_posix()
                rows.append(
                    {
                        "id": str(mem["id"]),
                        "family": "B-repo-workflow",
                        "name": str(mem.get("id")),
                        "does": _flatten_prose(mem)[:2000],
                        "mechanisms": json.dumps(mem.get("stages") or [], sort_keys=True)[
                            :4000
                        ],
                        "notes": json.dumps(mem.get("stopping") or {}, sort_keys=True),
                        "runtime": "",
                        "origin": rel,
                        "provenance": rel,
                        "corpus_tag": "in-tree",
                        "defining_document": rel,
                    }
                )
    return rows


def load_corpus() -> dict[str, Any]:
    live = load_live_registry()
    planted = planted_candidates()
    in_tree = in_tree_candidates()
    # Planted first so probes can address them even when live n=284 arrives.
    by_id: dict[str, dict[str, Any]] = {}
    for row in planted + in_tree + live["candidates"]:
        cid = str(row.get("id") or "")
        if not cid or cid in by_id:
            continue
        by_id[cid] = row
    return {
        "expected_live_n": EXPECTED_LIVE_N,
        "live_family_counts_cited": LIVE_FAMILY_COUNTS,
        "live": {k: v for k, v in live.items() if k != "candidates"},
        "planted_n": len(planted),
        "in_tree_n": len(in_tree),
        "live_n": live["n"],
        "candidates": list(by_id.values()),
        "ids": list(by_id.keys()),
    }
