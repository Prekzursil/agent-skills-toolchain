#!/usr/bin/env python3
"""Load the 30 merge_units: live maps file if present, else reconstructed stand-in.

Reconstructed rows are NOT claimed to be the original maps file. They use
the catalog field names (sources_declared, sources_unresolved) and grounded
candidate ids from WFA-0007/WFA-0042 inspect receipts, plus planted
unresolved ids so the fail-because-unresolved path is executable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maps import EXPECTED_BYTES_CC0019, MAPS_NAME, find_maps, maps_candidates, repo_root

REQUIRED_COUNT = 30

GROUNDED_IDS = [
    "wf-saved-agentic-repair-reliability",
    "wf-saved-bc-stage-compendium-enrichment",
    "wf-saved-codex-auth-research-fanout",
    "cmd-start-task",
    "cmd-orchestrate",
    "cmd-multi-workflow",
    "cmd-multi-plan",
    "cmd-multi-execute",
    "cmd-multi-frontend",
    "cmd-multi-backend",
    "cmd-review-design",
]
FAMILIES = [
    "A-saved-workflow",
    "B-repo-workflow",
    "C-repo-tool",
    "D-harness-runtime",
    "E-agent",
    "F-plugin",
    "G-skill",
    "H-executed-corpus",
    "I-command",
]
# Planted unresolved: catalog question asks which units fail because of
# sources_unresolved. These ids are detector-control, not maps-file facts.
PLANTED_UNRESOLVED = {
    7: ["wf-unresolved-not-in-registry-07"],
    19: ["wf-unresolved-not-in-registry-19"],
    28: [
        "wf-unresolved-not-in-registry-28a",
        "wf-unresolved-not-in-registry-28b",
    ],
}


def reconstructed_merge_units() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(1, REQUIRED_COUNT + 1):
        grounded = GROUNDED_IDS[(i - 1) % len(GROUNDED_IDS)]
        family = FAMILIES[(i - 1) % len(FAMILIES)]
        partner = f"wf-recon-{family}-{i:02d}"
        declared = [grounded, partner]
        if i % 5 == 0:
            declared.append(f"wf-recon-third-{i:02d}")
        unresolved = list(PLANTED_UNRESOLVED.get(i) or [])
        for u in unresolved:
            if u not in declared:
                declared.append(u)
        resolved = [s for s in declared if s not in unresolved]
        rows.append(
            {
                "id": f"RECON-MU-{i:02d}",
                "sources_declared": declared,
                "sources_unresolved": unresolved,
                "sources_resolved_in_registry": resolved,
                "not_a_duplicate_because": (
                    f"reconstructed stand-in {i}/30; partner is family {family}, "
                    "not a wording paraphrase of the grounded source"
                ),
                "provenance": "reconstructed-stand-in",
            }
        )
    return rows


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def normalize_unit(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"merge_unit[{index}] not an object")
    uid = str(raw.get("id") or raw.get("merge_unit_id") or raw.get("unit_id") or "")
    if not uid:
        uid = f"MU-{index:02d}"
    declared = _as_str_list(
        raw.get("sources_declared")
        or raw.get("sources")
        or raw.get("declared_sources")
    )
    unresolved = _as_str_list(
        raw.get("sources_unresolved")
        or raw.get("unresolved_sources")
        or raw.get("sources_unresolved_in_registry")
    )
    resolved = _as_str_list(
        raw.get("sources_resolved_in_registry")
        or raw.get("sources_resolved")
    )
    if not resolved:
        resolved = [s for s in declared if s not in set(unresolved)]
    if not declared:
        raise ValueError(f"merge_unit {uid} missing sources_declared")
    return {
        "id": uid,
        "sources_declared": declared,
        "sources_unresolved": unresolved,
        "sources_resolved_in_registry": resolved,
        "not_a_duplicate_because": str(raw.get("not_a_duplicate_because") or ""),
        "provenance": "maps-file",
        "raw_keys": sorted(raw.keys()),
    }


def extract_merge_units(doc: Any) -> list[Any]:
    if isinstance(doc, list):
        return doc
    if not isinstance(doc, dict):
        raise ValueError("maps root is neither object nor list")
    for key in ("merge_units", "mergeUnits", "units"):
        val = doc.get(key)
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            return list(val.values())
    for nested_key in ("maps", "data", "payload", "composition"):
        nested = doc.get(nested_key)
        if isinstance(nested, dict) and isinstance(nested.get("merge_units"), list):
            return nested["merge_units"]
    raise ValueError("maps document has no merge_units array")


def load_corpus(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or repo_root()
    searched = maps_candidates(repo)
    path = find_maps(repo)
    if path is None:
        units = reconstructed_merge_units()
        if len(units) != REQUIRED_COUNT:
            raise ValueError("reconstructed corpus is not 30")
        return {
            "maps_present": False,
            "maps_path": None,
            "maps_bytes": 0,
            "maps_sha256": None,
            "maps_name": MAPS_NAME,
            "expected_bytes_cc0019": EXPECTED_BYTES_CC0019,
            "searched": searched,
            "provenance": "reconstructed-because-maps-absent",
            "merge_units": units,
            "count": len(units),
        }

    raw = path.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    extracted = extract_merge_units(doc)
    units = [normalize_unit(u, i + 1) for i, u in enumerate(extracted)]
    if len(units) != REQUIRED_COUNT:
        raise ValueError(
            f"maps merge_units count={len(units)} want={REQUIRED_COUNT} (fail-closed)"
        )
    import hashlib

    return {
        "maps_present": True,
        "maps_path": str(path),
        "maps_bytes": len(raw),
        "maps_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "maps_name": MAPS_NAME,
        "expected_bytes_cc0019": EXPECTED_BYTES_CC0019,
        "searched": searched,
        "provenance": "maps-file",
        "merge_units": units,
        "count": len(units),
    }


def first_fully_resolved(units: list[dict[str, Any]]) -> dict[str, Any]:
    for u in units:
        if not (u.get("sources_unresolved") or []):
            declared = u.get("sources_declared") or []
            if len(declared) >= 2:
                return u
    raise ValueError("no fully-resolved merge_unit with >=2 sources")
