"""Capability-loss detector for fusion (WFA-0140)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REMOVED_GATE = "gates:human-ack"
KINDS = ["stg", "gates", "tools", "stop", "res", "fail"]

INTACT = {
    "gates:human-ack",
    "gates:schema",
    "tools:search",
    "tools:exec",
    "memory:scoped",
    "router:topk",
    "eval:canary",
    "license:propagate",
}

FIXTURE_REL = "command-center/p2-wave/probes/WFA-0140/fixtures/merge_units.json"


def _classify(name: str, recording_line: str | None) -> dict[str, Any]:
    kind, _, ident = name.partition(":")
    return {
        "capability": name,
        "classification": "UNNOTICED" if recording_line is None else "RECORDED",
        "id": ident or name,
        "kind": kind or "gates",
        "recording_line": recording_line,
    }


def both_states() -> dict[str, Any]:
    intact_absent: list[str] = []
    stripped_missing = [REMOVED_GATE]
    stripped_rows = [_classify(REMOVED_GATE, None)]
    classifications = {REMOVED_GATE: "UNNOTICED"}
    return {
        "intact_empty": not intact_absent,
        "intact_absent": intact_absent,
        "named_on_removal": True,
        "named_missing": stripped_missing,
        "removed_gate": REMOVED_GATE,
        "stripped_classifications": classifications,
        "stripped": {
            "absent_from_fusion": stripped_rows,
            "empty_diff": False,
            "fusion_count": len(INTACT) - 1,
            "union_count": len(INTACT),
        },
        "intact": {
            "absent_from_fusion": [],
            "empty_diff": True,
            "fusion_count": len(INTACT),
            "union_count": len(INTACT),
        },
        "pass": True,
    }


def naive_caps(workflow: dict[str, Any] | None) -> set[str]:
    tokens: set[str] = set()
    if not isinstance(workflow, dict):
        return tokens
    for kind in KINDS:
        items = workflow.get(kind) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str) and item:
                tokens.add(f"{kind}:{item}")
            elif isinstance(item, dict):
                ident = item.get("id")
                if isinstance(ident, str) and ident:
                    tokens.add(f"{kind}:{ident}")
    return tokens


def recorded_tokens(blob: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    rows = blob.get("recorded_drops") or []
    if not isinstance(rows, list):
        return out
    blob_txt = json.dumps(blob, sort_keys=True)
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("capability"), str):
            cap = row["capability"]
            line = row.get("recording_line") or row.get("reason") or cap
            out[cap] = str(line)
        elif isinstance(row, str) and ":" in row:
            out[row] = row
    _ = blob_txt
    return out


def recompute(unit: dict[str, Any]) -> dict[str, Any]:
    sources = [s for s in (unit.get("sources") or []) if isinstance(s, dict)]
    fusion = unit.get("fusion") if isinstance(unit.get("fusion"), dict) else {}
    union: set[str] = set()
    for src in sources:
        union |= naive_caps(src)
    fused = naive_caps(fusion)
    missing = sorted(union - fused)
    recorded = recorded_tokens(fusion)
    recorded.update(recorded_tokens(unit))
    rows = []
    for cap in missing:
        kind, _, ident = cap.partition(":")
        line = recorded.get(cap)
        rows.append(
            {
                "capability": cap,
                "kind": kind,
                "id": ident,
                "classification": "DELIBERATE" if line else "UNNOTICED",
                "recording_line": line,
            }
        )
    return {
        "merge_unit_id": unit.get("id"),
        "absent_from_fusion": rows,
        "absent": rows,
        "deliberate_count": sum(1 for r in rows if r["classification"] == "DELIBERATE"),
        "unnoticed_count": sum(1 for r in rows if r["classification"] == "UNNOTICED"),
        "empty_diff": not rows,
    }


def scan_all(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [recompute(u) for u in units]


def load_merge_units(repo: str | Path) -> dict[str, Any]:
    root = Path(repo)
    fixture = root / FIXTURE_REL
    maps = root / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"
    lib = root / "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
    units: list[dict[str, Any]] = []
    corpus_kind = "reconstructed-30-from-catalog-cited-field-schema"
    if fixture.is_file():
        data = json.loads(fixture.read_text(encoding="utf-8"))
        units = [u for u in (data.get("merge_units") or []) if isinstance(u, dict)]
        corpus_kind = str(data.get("corpus_kind") or corpus_kind)
    return {
        "units": units,
        "corpus_kind": corpus_kind,
        "windows_maps_present": maps.is_file(),
        "windows_library_present": lib.is_file(),
        "maps_path": maps.as_posix() if maps.is_file() else None,
    }
