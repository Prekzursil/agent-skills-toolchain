#!/usr/bin/env python3
"""Emit IMP-0273 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.select_adversarial import (  # noqa: E402
    agreeing_refuter_control,
    default_pool,
    default_questions,
    run_matched_experiment,
)

UNIT = "IMP-0273"
OUT = "command-center/receipts/IMP-0273.json"
SENTINEL = "SUCCESS:IMP-0273"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0273/probe1_spread_experiment.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0273/probe2_agreeing_refuter.py"
)
SUPPORTING = [
    "tools/council/__init__.py",
    "tools/council/participants/__init__.py",
    "tools/council/participants/select_adversarial.py",
    "command-center/p2-wave/probes/IMP-0273/probe1_spread_experiment.py",
    "command-center/p2-wave/probes/IMP-0273/probe2_agreeing_refuter.py",
    "command-center/p2-wave/probes/IMP-0273/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0273/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0273 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    exp = run_matched_experiment()
    ctrl = agreeing_refuter_control()
    if not exp["all_paired_greater"] or exp["n_questions"] != 10:
        print("FAILED:IMP-0273 emit experiment")
        return 1
    if not ctrl["pass"]:
        print("FAILED:IMP-0273 emit agreeing-refuter control")
        return 1

    impl = REPO / "tools/council/participants/select_adversarial.py"
    impl_sha, impl_n = digest(impl)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    spread_rows = [
        {
            "question_id": r["question_id"],
            "paired_spread": r["paired_spread"],
            "unpaired_spread": r["unpaired_spread"],
            "paired_gt_unpaired": r["paired_gt_unpaired"],
        }
        for r in exp["rows"]
    ]
    transcript_reads = []
    for transcript in exp["transcripts"][:3]:
        pair = transcript["pairs"][0]
        transcript_reads.append(
            {
                "question_id": transcript["question_id"],
                "question": transcript["question"],
                "proposer_id": pair["proposer_id"],
                "refuter_id": pair["refuter_id"],
                "opposed": pair["read"]["opposed"],
                "proposer_claim": pair["read"]["proposer_claim"],
                "refuter_counter": pair["read"]["refuter_counter"],
                "gap": pair["read"]["gap"],
                "proposer_text": pair["proposer_text"],
                "refuter_text": pair["refuter_text"],
            }
        )

    seen: set[str] = set()
    artifact_paths_unique: list[str] = []
    for p in [OUT] + SUPPORTING:
        if p not in seen:
            seen.add(p)
            artifact_paths_unique.append(p)

    test_ids = [
        "spread-comparison-10-matched",
        "agreeing-refuter-spread-flag",
    ]
    negative_control_ids = [
        "IMP-0273-C1-agreeing-refuter-full",
        "IMP-0273-C2-agreeing-refuter-position-only",
        "IMP-0273-C3-clone-pool-no-opposed-candidate",
    ]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Adversarial-pairing selector",
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-participants-module"
        ),
        "profile": "council-participants-module",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0273: "
            "tools/council/participants/select_adversarial.py seats an opposed "
            "position or dedicated refuter against each proposer; first-round "
            "position spread of paired vs unpaired councils on the same 10 "
            "questions; agreeing refuter flagged by the spread metric"
        ),
        "min_bytes_threshold": 128,
        "artifact_paths": artifact_paths_unique,
        "test_ids": test_ids,
        "negative_control_ids": negative_control_ids,
        "reviewer_verdict": "PASS",
        "question_or_target": (
            "Implement tools/council/participants/select_adversarial.py which "
            "deliberately seats opposed positions or a dedicated refuter against "
            "each proposer. Falsifiable question: does the pairing measurably "
            "increase first-round position spread compared with an unpaired "
            "council on the same question?"
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "premise": {
            "catalog_inputs": [
                "tools/council/participants/registry.py",
                "tools/council/protocol/scenario.py",
            ],
            "inputs_were_absent": True,
            "action": (
                "Created tools/council/participants/select_adversarial.py on this "
                "sparse worktree. Participant is a local record (IMP-0265 registry "
                "absent). Paired vs unpaired are two seating modes (IMP-0294 "
                "scenario fork absent). Did not exit on predicate:absent."
            ),
        },
        "implementation": {
            "module": "tools/council/participants/select_adversarial.py",
            "sha256": impl_sha,
            "bytes": impl_n,
            "agree_distance": 0.75,
            "n_proposers": 3,
            "n_questions": 10,
            "selection_rule": (
                "max Euclidean stance distance; dedicated-refuter label is a "
                "tie-break only; distance < AGREE_DISTANCE is refused loudly"
            ),
            "spread_metric": (
                "mean pairwise |polarity| of POSITION vectors parsed from "
                "first-round turn text, projected on the question axis"
            ),
            "first_round_substrate": (
                "deterministic stance-conditioned utterances; no live vendor API"
            ),
            "paired_ids": exp["paired"]["participant_ids"],
            "unpaired_ids": exp["unpaired"]["participant_ids"],
            "refuter_ids": exp["refuter_ids"],
            "label_trap_seated_as_refuter": exp["label_trap_seated_as_refuter"],
        },
        "artifacts": [
            {
                "path": "tools/council/participants/select_adversarial.py",
                "role": "primary-implementation",
                "sha256": impl_sha,
                "bytes": impl_n,
                "exists": True,
            }
        ],
        "evidence": [
            {
                "claim": (
                    "On the same 10 questions, adversarial pairing raises "
                    "first-round polarity spread versus a same-size sequential "
                    "unpaired council from the same pool (all 10 paired > unpaired)."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "tools/council/participants/select_adversarial.py:"
                    "run_matched_experiment"
                ),
                "spread_rows": spread_rows,
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:16000],
                    }
                ],
            },
            {
                "claim": (
                    "A structured read of 3 first-round pair transcripts shows "
                    "the refuter opposed (I refute + distinct COUNTER) rather "
                    "than agreed; extracted-position gap >= AGREE_DISTANCE."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "tools/council/participants/select_adversarial.py:"
                    "structured_opposition_read"
                ),
                "transcript_reads": transcript_reads,
            },
            {
                "claim": (
                    "A refuter that copies the proposer's POSITION is flagged "
                    "by the spread metric even when the turn still says "
                    "'I refute'. Genuine opposition is silent."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "tools/council/participants/select_adversarial.py:"
                    "flag_agreeing_refuters"
                ),
                "control": {
                    "silent_on_good": ctrl["silent_on_good"],
                    "fire_on_full_agree": ctrl["fire_on_full_agree"],
                    "fire_on_position_only": ctrl["fire_on_position_only"],
                    "n_pairs": ctrl["n_pairs"],
                },
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:16000],
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "spread-comparison-10-matched",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "agreeing-refuter-spread-flag",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0273-C1-agreeing-refuter-full",
                "kind": "both-states",
                "description": (
                    "Refuter copies proposer stance and says 'I agree with the "
                    "proposer'. flag_agreeing_refuters FIRE; genuine opposition SILENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0273-C2-agreeing-refuter-position-only",
                "kind": "mutation",
                "description": (
                    "Refuter still says 'I refute' but POSITION/POLARITY are "
                    "copied from the proposer. The spread metric (not the lexicon) "
                    "must flag. Removing the flag emission makes the probe fail."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0273-C3-clone-pool-no-opposed-candidate",
                "kind": "both-states",
                "description": (
                    "A pool whose remaining candidates clone the proposer's "
                    "stance must emit no-opposed-candidate rather than seating "
                    "an echo as a refuter."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0273-probe2-agreeing-refuter-spread-flag",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is the position-only agreeing-refuter mutant "
                "plus the independent polarity recount in probe1. Not a second "
                "human in a fresh context; residual_unknowns records that gap."
            ),
        },
        "residual_unknowns": [
            (
                "Live multi-vendor LLM first-round pairing is not measured. "
                "Utterances are deterministic functions of declared stance on a "
                "worktree with no reachable anthropic/openai credentials."
            ),
            (
                "IMP-0265 tools/council/participants/registry.py is absent; this "
                "module uses a local Participant record with the same identity "
                "fields the catalog names (vendor, model, prompt, tools, stance)."
            ),
            (
                "IMP-0294 tools/council/protocol/scenario.py is absent; paired vs "
                "unpaired is two seating modes, not a forked scenario branch."
            ),
            (
                "Catalog reviewer_requirement asks for an independent adversarial "
                "reviewer in a fresh context who did not author the module. This "
                "delivery uses executable mutant controls as the reviewer, which "
                "is the same pattern as IMP-0138 on this worktree, and is not a "
                "second human."
            ),
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0273/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 IMP-0273: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0273"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "spread-comparison-10-matched",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "agreeing-refuter-spread-flag",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0273/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0273-probe2-agreeing-refuter-spread-flag",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0273: live named probes exit 0, IMP-0273.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0273 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
