#!/usr/bin/env python3
"""Disclosed reconstructed estate for WFA-0003.

The five catalog inputs live on the Windows harness-restore tree and are
absent from this Linux worktree. Live paths are still probed. Fixtures are
labelled corpus_role=fixture and never presented as the 284-row / 108-row
registries.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ESTATE = HERE / "fixtures" / "estate"

LAST_KNOWN_08_SHA256 = (
    "4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a"
)
CATALOG_CLAIMED_CANDIDATES = 284
CATALOG_CLAIMED_BLUEPRINTS = 108
OPTION_COUNT = 33
MECH_COUNT = 38
ABSENT_CLASS = ("M-12", "M-16", "M-17", "M-19", "M-28", "M-30", "M-38")
PUBLISHED_COLLISION_COUNT = 31

INSPECT_CANDIDATES = [
    {
        "id": "wf-saved-agentic-repair-reliability",
        "name": "agentic-repair-reliability.js",
        "notes": "Inspect sample from the 284-row registry; cites MECH-7.",
    },
    {
        "id": "wf-saved-bc-stage-compendium-enrichment",
        "name": "bc-stage-compendium-enrichment.js",
        "notes": "Inspect sample from the 284-row registry; cites MECH-12.",
    },
    {
        "id": "wf-saved-codex-auth-research-fanout",
        "name": "codex-auth-research-fanout.mjs",
        "notes": "Inspect sample from the 284-row registry; cites option M-5.",
    },
]

BLUEPRINT_FIXTURE_IDS = [f"BP-{n:03d}" for n in range(1, 7)]

LIVE_CANDIDATE_PATHS = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/07-OPTION-UNIVERSE.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/13-ARCHITECTURE-CANDIDATES.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/17-DECISION-LOG.md",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/07-OPTION-UNIVERSE.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/13-ARCHITECTURE-CANDIDATES.md",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/17-DECISION-LOG.md",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "07-OPTION-UNIVERSE.json",
    "13-ARCHITECTURE-CANDIDATES.md",
    "17-DECISION-LOG.md",
    "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "command-center/07-OPTION-UNIVERSE.json",
    "command-center/13-ARCHITECTURE-CANDIDATES.md",
    "command-center/17-DECISION-LOG.md",
    "command-center/wfa/schema/wfa-schema-pack.json",
]

FIVE_REL = {
    "08-WORKFLOW-CANDIDATE-REGISTRY.json": "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json": "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json": "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "07-OPTION-UNIVERSE.json": "07-OPTION-UNIVERSE.json",
    "13-ARCHITECTURE-CANDIDATES.md": "13-ARCHITECTURE-CANDIDATES.md",
}

PINNED_LINE_175 = (
    "The 31-way option-id collision between family M and the architecture-candidate "
    "cards is still live (present tense) and is queued as P2-09."
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _foundry_candidates() -> list[dict]:
    path = REPO / "tools/workflow_foundry/candidate_registry.json"
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for row in doc.get("candidates") or []:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            out.append(
                {
                    "id": row["id"],
                    "name": row["id"],
                    "notes": f"Worktree-local foundry seed; licence={row.get('licence')}.",
                }
            )
    return out


def _cnf0064_candidates() -> list[dict]:
    path = REPO / "command-center/p2-wave/probes/CNF-0064/registry.json"
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for row in doc.get("candidates") or []:
        if not isinstance(row, dict):
            continue
        cid = row.get("id")
        if isinstance(cid, str) and cid.startswith("wf-"):
            out.append(
                {
                    "id": cid,
                    "name": row.get("name") or cid,
                    "notes": "Worktree-local CNF-0064 registry row.",
                }
            )
    return out


def _option_universe() -> dict:
    return {
        "artifact": "07-OPTION-UNIVERSE",
        "corpus_role": "fixture",
        "family": "M",
        "count": OPTION_COUNT,
        "ids": [
            {
                "id": f"M-{n}",
                "title": f"Family-M option card {n}",
            }
            for n in range(1, OPTION_COUNT + 1)
        ],
    }


def _architecture_md(*, prefix: str = "MECH") -> str:
    lines = [
        "# 13 Architecture Candidates",
        "",
        "Mechanism cards re-prefixed to MECH-NN on 2026-08-07 (107 substitutions).",
        "This file carries zero bare M-NN tokens."
        if prefix == "MECH"
        else "PRE-FIX reconstruction: architecture cards still use the bare M- prefix.",
        "",
    ]
    for n in range(1, MECH_COUNT + 1):
        token = f"{prefix}-{n}"
        lines.append(f"## {token} Architecture mechanism card {n}")
        lines.append("")
        lines.append(
            f"Architecture-candidate mechanism {token} "
            f"({'post-fix prefix; not a bare M- token' if prefix == 'MECH' else 'pre-fix shared M-NN namespace'})."
        )
        lines.append("")
    return "\n".join(lines) + "\n"


def _decision_log_md() -> str:
    lines = ["# 17 Decision Log", ""]
    while len(lines) < 174:
        lines.append(
            f"Settled entry {len(lines)}: routine note with no mechanism-prefix tokens."
        )
    lines.append(PINNED_LINE_175)
    return "\n".join(lines) + "\n"


def _candidates_doc() -> dict:
    rows = []
    seen = set()
    for src in (INSPECT_CANDIDATES, _foundry_candidates(), _cnf0064_candidates()):
        for row in src:
            cid = row["id"]
            if cid in seen:
                continue
            seen.add(cid)
            rows.append(row)
    return {
        "artifact": "08-WORKFLOW-CANDIDATE-REGISTRY",
        "corpus_role": "fixture",
        "note": (
            "NOT the 284-row harness-restore registry (absent on this worktree; "
            f"last known sha256 {LAST_KNOWN_08_SHA256})."
        ),
        "catalog_claimed_count": CATALOG_CLAIMED_CANDIDATES,
        "candidates": rows,
    }


def _blueprints_doc() -> dict:
    return {
        "artifact": "09-WORKFLOW-BLUEPRINT-LIBRARY",
        "corpus_role": "fixture",
        "discovery_only": True,
        "catalog_claimed_count": CATALOG_CLAIMED_BLUEPRINTS,
        "note": (
            "108-row blueprint library is absent; this fixture carries only the "
            "six BP-00N tokens already named on this worktree (SYN-0038)."
        ),
        "blueprints": [
            {"id": bid, "title": f"Workflow blueprint {bid}"}
            for bid in BLUEPRINT_FIXTURE_IDS
        ],
    }


def _merge_maps_doc() -> dict:
    return {
        "artifact": "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS",
        "corpus_role": "fixture",
        "no_merge_has_been_performed": True,
        "maps": [
            {
                "id": "MAP-001",
                "uses": [
                    "wf-saved-agentic-repair-reliability",
                    "BP-001",
                    "MECH-12",
                    "M-5",
                ],
            }
        ],
    }


def materialize() -> Path:
    if ESTATE.exists():
        for child in ESTATE.rglob("*"):
            if child.is_file():
                child.unlink()
    ESTATE.mkdir(parents=True, exist_ok=True)
    _write(
        ESTATE / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        json.dumps(_candidates_doc(), indent=2, sort_keys=True) + "\n",
    )
    _write(
        ESTATE / "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        json.dumps(_blueprints_doc(), indent=2, sort_keys=True) + "\n",
    )
    _write(
        ESTATE / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
        json.dumps(_merge_maps_doc(), indent=2, sort_keys=True) + "\n",
    )
    _write(
        ESTATE / "07-OPTION-UNIVERSE.json",
        json.dumps(_option_universe(), indent=2, sort_keys=True) + "\n",
    )
    _write(ESTATE / "13-ARCHITECTURE-CANDIDATES.md", _architecture_md(prefix="MECH"))
    _write(
        ESTATE / "13-ARCHITECTURE-CANDIDATES.pre-fix.md",
        _architecture_md(prefix="M"),
    )
    _write(ESTATE / "17-DECISION-LOG.md", _decision_log_md())
    return ESTATE


def live_presence(repo: Path | None = None) -> list[dict]:
    root = repo or REPO
    rows = []
    for rel in LIVE_CANDIDATE_PATHS:
        path = Path(rel)
        if not path.is_absolute():
            path = root / rel
        present = path.is_file()
        rows.append(
            {
                "path": rel.replace("\\", "/"),
                "present": present,
                "bytes": path.stat().st_size if present else 0,
            }
        )
    return rows


def five_artifact_paths(estate: Path | None = None) -> dict[str, Path]:
    root = estate or ESTATE
    return {name: root / rel for name, rel in FIVE_REL.items()}


if __name__ == "__main__":
    print(f"materialized {materialize()}")
