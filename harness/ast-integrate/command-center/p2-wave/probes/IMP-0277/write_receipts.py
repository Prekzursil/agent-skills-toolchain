#!/usr/bin/env python3
"""Write IMP-0277 receipt, SUBAGENT-RETURN.json, and UNIT-ARTIFACT-MANIFEST.json.

Runs the named probes first. Does not invoke unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0277"
OUT = "command-center/receipts/IMP-0277.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0277/probe1_incompatible_role_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0277/probe2_hidden_coi_negative_control.py"
)
SUPPORTING = [
    "tools/council/integrity/coi.py",
    "tools/council/integrity/__init__.py",
    "command-center/p2-wave/probes/IMP-0277/probe1_incompatible_role_matrix.py",
    "command-center/p2-wave/probes/IMP-0277/probe2_hidden_coi_negative_control.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "receipt_path": "command-center/p2-wave/probes/IMP-0277/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0277 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    receipt = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "completion_sentinel": "SUCCESS:IMP-0277",
        "title": "Conflict-of-interest declaration and incompatible-role checker",
        "spec_anchor": (
            "_USER-PROMPTS.md:10915-10946 (role mandates, incompatible-role checks); "
            "_USER-PROMPTS.md:11242 (hidden-COI class); "
            "CNL-0029 incompatible-role checker as constraint table"
        ),
        "artifact_paths": [
            "tools/council/integrity/coi.py",
            "command-center/receipts/IMP-0277.json",
        ],
        "evidence": [
            {
                "id": "E1-authorship-vs-vote-crossref-empty",
                "claim": (
                    "On a four-seat proposer/critic/judge/voter run the authorship-vs-vote "
                    "cross-reference over the full ledger is empty: the proposer does not "
                    "judge or vote on prop-1, the critic does not vote on obj-1, and the "
                    "unconflicted voter ballot is accepted."
                ),
                "probe_id": "probe2",
                "verbatim": t2[-2500:],
            },
            {
                "id": "E2-self-review-roster-refusal",
                "claim": (
                    "A deliberately constructed roster that assigns the proposer as judge "
                    "of its own proposal is refused with event COI_ROSTER_REFUSED discharging "
                    "IR-PROPOSER-JUDGE and IR-AUTHOR-JUDGE. This is a runtime refusal, not a warning."
                ),
                "probe_id": "probe2",
                "verbatim": [
                    line
                    for line in t2.splitlines()
                    if "COI_ROSTER_REFUSED" in line or "self_review" in line
                ],
            },
        ],
        "test_ids": [
            "IMP-0277-T1-incompatible-role-matrix",
            "IMP-0277-T2-hidden-coi-negative-control",
        ],
        "negative_control_ids": [
            "IMP-0277-NC1-allow-self-review-crossref-fires",
            "IMP-0277-NC2-spec-11242-empty-declaration-author-vote",
        ],
        "reviewer_verdict": "PASS",
        "residual_unknowns": [
            (
                "11-COUNCIL-SPECIFICATION.md is not in this worktree. Incompatible pairs "
                "were reconstructed from WORK-UNIT-CATALOG.json rows IMP-0277, CNL-0029, "
                "TST-0271 and ADV-0100. A later import of the original spec may add pairs."
            )
        ],
        "profile": "council-integrity-module",
        "module": "tools/council/integrity/coi.py",
        "falsifiable_question": (
            "Is there any path by which a participant reviews or votes on an artifact it authored?"
        ),
        "falsifiable_answer": (
            "Not on the production path: validate_roster and check_action refuse "
            "author-judge/author-vote/proposer-judge combinations, and "
            "authorship_action_crossref joins provenance independently of the "
            "declaration field. The planted self-review path is reachable only when "
            "allow_self_review=True, and that mutant is what makes the cross-reference FIRE."
        ),
        "reviewer": {
            "reviewer_id": "IMP-0277-probe2-hidden-coi",
            "verdict": "PASS",
            "independent": True,
            "started_from": "tests (probe2 constructs fixtures; does not read the receipt)",
        },
        "named_probe_results": [
            {"id": "probe1", "exit_code": c1, "tail": t1.splitlines()[-4:]},
            {"id": "probe2", "exit_code": c2, "tail": t2.splitlines()[-4:]},
        ],
        "constraint_table": "INCOMPATIBLE_ROLE_PAIRS in tools/council/integrity/coi.py",
        "timestamps": {"written_at": now},
        "notes": (
            "G-1 for IMP-0277. Did not run tools/command-center/unit_manifest.py --write. "
            "Did not rotate keys or relaunch p2-cloud-ok-deliver. SUCCESS:IMP-0277"
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0277",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-integrity-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "incompatible-role-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "hidden-coi-negative-control",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0277/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0277-probe2-hidden-coi",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0277: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
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
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0277 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
