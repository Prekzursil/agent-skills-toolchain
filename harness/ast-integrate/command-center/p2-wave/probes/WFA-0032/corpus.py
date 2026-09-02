"""284-candidate reconstruction for WFA-0032.

The Windows registry (08-WORKFLOW-CANDIDATE-REGISTRY.json, 284 rows) is not
on this Linux worktree. Family quotas and live ids are taken from
WFA-0042/_inspect_source_out.json (histogram) and WFA-0007/_inspect_source_out.json
(sample ids). Generated stand-ins fill remaining slots. That is reconstruction,
not a claim that the original registry file was read here.
"""
from __future__ import annotations

from typing import Any

FAMILY_QUOTAS: dict[str, int] = {
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

KNOWN_IDS: dict[str, list[str]] = {
    "A-saved-workflow": [
        "wf-saved-agentic-repair-reliability",
        "wf-saved-bc-stage-compendium-enrichment",
        "wf-saved-codex-auth-research-fanout",
        "wf-saved-design-gate",
        "wf-saved-harness-self-improve-sweep",
        "wf-saved-plant-fs-only",
        "wf-saved-plant-git-only",
    ],
    "I-command": [
        "cmd-start-task",
        "cmd-orchestrate",
        "cmd-multi-workflow",
        "cmd-multi-plan",
        "cmd-multi-execute",
        "cmd-multi-frontend",
        "cmd-multi-backend",
        "cmd-review-design",
    ],
}

PREFIX: dict[str, str] = {
    "A-saved-workflow": "wf-saved-recon",
    "B-repo-workflow": "wf-repo-recon",
    "C-repo-tool": "tool-repo-recon",
    "D-harness-runtime": "harness-recon",
    "E-agent": "agent-recon",
    "F-plugin": "plugin-recon",
    "G-skill": "skill-recon",
    "H-executed-corpus": "corpus-recon",
    "I-command": "cmd-recon",
}

PLANT_FS_ONLY = "wf-saved-plant-fs-only"
PLANT_GIT_ONLY = "wf-saved-plant-git-only"
ANCHOR_LINE = 3
WRONG_LINE = 5
N_EXPECTED = 284


def _body(cid: str, family: str) -> str:
    return (
        f"id: {cid}\n"
        f"family: {family}\n"
        f"ANCHOR-LINE {cid} provenance-payload\n"
        f"pad-a {cid}\n"
        f"pad-b {cid} distinct-from-anchor\n"
    )


def candidates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for family, quota in FAMILY_QUOTAS.items():
        known = list(KNOWN_IDS.get(family, []))
        ids: list[str] = []
        for cid in known:
            if cid in seen:
                raise RuntimeError(f"duplicate known id {cid}")
            ids.append(cid)
            seen.add(cid)
        n = 1
        while len(ids) < quota:
            cid = f"{PREFIX[family]}-{n:03d}"
            n += 1
            if cid in seen:
                continue
            ids.append(cid)
            seen.add(cid)
        if len(ids) != quota:
            raise RuntimeError(f"{family} quota {quota} got {len(ids)}")
        for cid in ids:
            plant = None
            if cid == PLANT_FS_ONLY:
                plant = "fs-only"
            elif cid == PLANT_GIT_ONLY:
                plant = "git-only"
            rows.append(
                {
                    "id": cid,
                    "family": family,
                    "plant": plant,
                    "anchor_line": ANCHOR_LINE,
                    "body": _body(cid, family),
                    "origin": (
                        "inspect-sample"
                        if cid in set(sum(KNOWN_IDS.values(), []))
                        and plant is None
                        else ("detector-plant" if plant else "reconstructed-stand-in")
                    ),
                }
            )
    if len(rows) != N_EXPECTED:
        raise RuntimeError(f"expected {N_EXPECTED} candidates, got {len(rows)}")
    fam = {}
    for r in rows:
        fam[r["family"]] = fam.get(r["family"], 0) + 1
    if fam != FAMILY_QUOTAS:
        raise RuntimeError(f"family histogram {fam} != {FAMILY_QUOTAS}")
    return rows
