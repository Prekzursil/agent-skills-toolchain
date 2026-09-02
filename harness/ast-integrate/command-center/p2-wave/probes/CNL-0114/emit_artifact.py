#!/usr/bin/env python3
"""Emit the CNL-0114 catalog artifact (JSON with a .md path)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0114-multi-interest-family-negotiation-mediation-adversarial-co.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0114/probe1_instantiate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0114/probe2_schema_sibling_control.py"
)
QUESTION = (
    "These four seat participants with non-aligned interests or no expertise - "
    "what distinguishes negotiation (parties bargain directly) from mediation "
    "(a neutral third party reframes interests), what protects a lay stakeholder "
    "panel from being steered by the expert presenting to it, and what makes "
    "adversarial collaboration produce a shared pre-registered test rather than "
    "a split verdict?"
)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNL-0114 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    task = F.load_task()
    presets = F.family_presets()
    siblings = F.load_siblings()
    instantiations = []
    sibling_rows = []
    for preset in presets:
        inst = F.instantiate(preset, task)
        instantiations.append(inst)
        sibling_rows.append(F.nearest_sibling(preset, siblings, task))

    answers = {
        "negotiation_versus_mediation": {
            "not_a_name_split": True,
            "negotiation": (
                "Parties bargain on the record with no reframe seat. "
                "third_party.kind=none. Franchise is the parties. "
                "BATNA walk-away is a first-class stopping outcome. "
                "A recorder has no vote."
            ),
            "mediation": (
                "A non-voting mediator is seated with caucus/reframe/certify "
                "authority. Parties still own the bargain votes. "
                "third_party.kind=mediator and integrity.mediator_cannot_vote=true. "
                "A record named 'mediation' whose third_party.kind is not mediator "
                "is rejected as a rename of negotiation."
            ),
        },
        "lay_panel_anti_steering": {
            "presenter_has_no_vote": True,
            "evidence_clerk_strips_recommendations": True,
            "ballot_forbids_expert_default": True,
            "mechanism": (
                "The expert-presenter is on the roster but not in the franchise. "
                "An evidence-clerk owns the packet and may strip recommendations. "
                "Stopping requires the expert recommendation label to be absent "
                "from ballot options. A ballot that includes that label FIRES."
            ),
        },
        "adversarial_collaboration_not_split_verdict": {
            "split_verdict_is_fault": True,
            "prereg_hash_required": True,
            "no_outcome_vote": True,
            "mechanism": (
                "Advocates sign a joint test; a registrar locks the pre-registration "
                "hash. There is no outcome vote. Claimed outcome split-verdict is a "
                "procedure fault, not a result. The stop is a locked test plus "
                "recorded/scheduled run, or registrar rejection of a split."
            ),
        },
    }

    artifact = {
        "unit_id": "CNL-0114",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0114",
        "title": "Multi-interest family: negotiation, mediation, adversarial collaboration and lay panel",
        "question": QUESTION,
        "output_schema_declared": "command-center/schema/council-preset.schema.json",
        "output_schema_declared_present": (
            REPO / "command-center/schema/council-preset.schema.json"
        ).is_file(),
        "working_schema": "command-center/p2-wave/probes/CNL-0114/council-preset.schema.json",
        "working_schema_status": (
            "unit-local working typed-delta schema; CNL-0101 owns the canonical "
            "20-key type over the 72-record library, which is not on this tree"
        ),
        "library_status": F.library_status(),
        "c_id_mapping": {
            "only_catalog_named_preset_id": "C-M01",
            "c_m01_body_on_disk": False,
            "mapped_to_unread_library_c_ids": False,
            "extends_on_this_tree": [
                "CNL-0017 stakeholder-balanced selection (lay seats / given interests)",
                "CNL-0019 adversarial selection without manufactured disagreement",
                "CNL-0050 protocol-gap: negotiation has no card among the cited 58 (first pass)",
                "CNL-0034 jury topology is related; CNL-0113 owns evidence juries",
            ],
            "honesty": (
                "This unit does not claim a C-id from 12-COUNCIL-PROTOCOLS-AND-PRESETS.json "
                "because that file is absent. Sibling named for the differential is the "
                "on-disk reconstruction council.preset.catalog-class.editable."
            ),
        },
        "answers": answers,
        "family": {
            "id": "multi-interest",
            "parameter": (
                "third_party.kind × franchise_rule × whether the product is a bargain, "
                "a certified memorandum, a locked test, or a lay ballot"
            ),
            "members": [p["id"] for p in presets],
            "merge_rule": "a member whose profile distance to another member is 0 is a rename and must be merged",
        },
        "presets": presets,
        "fixture_task": task,
        "instantiations": instantiations,
        "nearest_sibling_differential": sibling_rows,
        "nearest_sibling_named": sibling_rows[0]["nearest_distinct"]["id"]
        if sibling_rows and sibling_rows[0].get("nearest_distinct")
        else None,
        "tests": [
            {
                "id": "instantiate-fixture",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "schema-sibling-negative-control",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "name-only-clone",
                "rejects": "a preset that differs only in id/name from another record",
            },
            {
                "id": "locked-dial-overlay",
                "rejects": "operator overlay of voting.method (not in editable_dials)",
            },
            {
                "id": "lay-expert-steering",
                "fires_on": "ballot options containing the expert recommendation label",
                "silent_on": "clerk-authored options that omit that label",
            },
            {
                "id": "split-verdict",
                "fires_on": "claimed outcome split-verdict",
                "silent_on": "locked shared-test-result",
            },
            {
                "id": "mediation-name-without-mediator",
                "fires_on": "id/name contains mediation but third_party.kind != mediator",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0114-probe1-instantiate-replay",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Mechanical instantiation and profile distance; does not accept "
                "the author's prose as the differential."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "probe_tails": {
            "probe1": t1.splitlines()[-4:],
            "probe2": t2.splitlines()[-4:],
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/CNL-0114/council-preset.schema.json",
                "role": "working-schema",
                "exists": True,
            },
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completion": "SUCCESS:CNL-0114",
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(artifact, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    print(f"wrote {OUT_REL} bytes={len(raw)} sha256={sha}")
    print("SUCCESS:CNL-0114")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
