#!/usr/bin/env python3
"""Existing-artifact corpus for the RES-0154 refutation pass.

Gold labels are assigned by this module for scoring and the negative
control. The honest refuter does not receive them.
"""
from __future__ import annotations

from pathlib import Path

from util import REPO

# Known-correct: JSON Schema documents whose required[] is a subset of
# properties, verified independently of the refuter. Negative control.
# Defective: harvest/validate sidecars on this worktree that claim
# exists:true for catalog output_paths that are absent here, and/or
# record named-probe PASS while the named scripts are absent.
CORPUS = (
    {
        "id": "SOUND-work-unit-schema",
        "rel": "command-center/schema/work-unit.schema.json",
        "gold": "known_correct",
        "why_gold": (
            "JSON Schema draft-07; every required key is in properties; "
            "type=object; no exists:true claims."
        ),
    },
    {
        "id": "SOUND-research-registry-schema",
        "rel": "command-center/schema/research-registry.schema.json",
        "gold": "known_correct",
        "why_gold": (
            "JSON Schema draft-07; every required key is in properties; "
            "type=object; no exists:true claims."
        ),
    },
    {
        "id": "DEFECT-RES-0147-validate-sidecar",
        "rel": "command-center/p2-wave/probes/RES-0147/_validate_out.json",
        "gold": "known_defective",
        "why_gold": (
            "Sidecar claims exists:true for the catalog primary under "
            "command-center/research/evidence-quality/, which is absent "
            "on this worktree; artifacts_claimed > artifacts_present; "
            "named-probe tests result PASS while named scripts are absent."
        ),
    },
    {
        "id": "DEFECT-RES-0158-measure-sidecar",
        "rel": "command-center/p2-wave/probes/RES-0158/_measure_out.json",
        "gold": "known_defective",
        "why_gold": (
            "Sidecar claims exists:true for "
            "command-center/research/gem-hunt/RES-0158-transfer-"
            "structured-analytic-techniques.json, which is absent here."
        ),
    },
    {
        "id": "DEFECT-RES-0159-strike-sidecar",
        "rel": "command-center/p2-wave/probes/RES-0159/_strike_out.json",
        "gold": "known_defective",
        "why_gold": (
            "Sidecar records named-probe tests PASS while probe1_on_disk "
            "and probe2_on_disk are false; ok_relpaths names a research "
            "primary that is absent on this worktree."
        ),
    },
)


def rows() -> list[dict]:
    out = []
    for item in CORPUS:
        path = REPO / item["rel"]
        if not path.is_file():
            raise FileNotFoundError(item["rel"])
        rec = dict(item)
        rec["path"] = path
        out.append(rec)
    return out


def known_correct_ids() -> set[str]:
    return {r["id"] for r in CORPUS if r["gold"] == "known_correct"}
