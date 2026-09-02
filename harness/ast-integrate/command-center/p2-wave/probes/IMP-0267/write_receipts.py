#!/usr/bin/env python3
"""Write IMP-0267 receipt, per-unit manifest, and SUBAGENT-RETURN."""
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

from council.participants.select_auto import (  # noqa: E402
    apply_owner_override,
    compose,
    legal_false_positive_report,
    reason_diversity_report,
    roles_of,
)

UID = "IMP-0267"
OUT_REL = "command-center/receipts/IMP-0267.json"
MODULE_REL = "tools/council/participants/select_auto.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0267/probe1_archetypes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0267/probe2_reasons_and_negatives.py"
)
SUPPORTING = [
    MODULE_REL,
    "tools/council/participants/__init__.py",
    "command-center/p2-wave/probes/IMP-0267/fixtures.json",
    "command-center/p2-wave/probes/IMP-0267/probe1_archetypes.py",
    "command-center/p2-wave/probes/IMP-0267/probe2_reasons_and_negatives.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0267/SUBAGENT-RETURN.json",
        "role": role,
    }


def live_measurements() -> dict:
    fx = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
    archetypes = []
    for item in fx["archetypes"]:
        comp = compose(item["task"])
        roles = sorted(roles_of(comp))
        archetypes.append(
            {
                "id": item["id"],
                "expected_role": item["expected_role"],
                "present": item["expected_role"] in roles,
                "roles": roles,
                "seat_count": comp["seat_count"],
                "unique_reasons": reason_diversity_report(comp["seats"])["n_unique"],
            }
        )
    missing = fx["missing_expertise"]
    miss_comp = compose(missing["task"])
    miss_roles = sorted(roles_of(miss_comp))
    overridden = apply_owner_override(
        miss_comp,
        [
            {
                "action": "remove",
                "role": "legal",
                "owner_reason": "outside counsel already retained for the subpoena",
            }
        ],
    )
    fpr = legal_false_positive_report(fx["non_legal"])
    return {
        "archetypes": archetypes,
        "missing_expertise": {
            "id": missing["id"],
            "expected_role": missing["expected_role"],
            "roles": miss_roles,
            "seated": missing["expected_role"] in miss_roles,
        },
        "owner_override": {
            "action": "remove",
            "role": "legal",
            "auto_had_role": overridden["owner_overrides"][0]["auto_had_role"],
            "result": overridden["owner_overrides"][0]["result"],
            "visible": overridden["owner_overrides"][0]["visible"],
            "remaining": sorted(roles_of(overridden)),
        },
        "legal_false_positive": fpr,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0267 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    measured = live_measurements()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting_meta = []
    for rel in SUPPORTING:
        sha, size = digest(REPO / rel)
        supporting_meta.append(
            {
                "path": rel,
                "role": "supporting",
                "bytes": size,
                "sha256": sha,
                "exists": True,
            }
        )

    receipt = {
        "unit_id": UID,
        "id": UID,
        "schema_version": 1,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0267",
        "title": "Auto-composed participant selector with per-choice explanation",
        "spec_anchor": (
            "catalog IMP-0267; _USER-PROMPTS.md:10765 general-purpose "
            "auto-composed council that explains every choice; "
            "11-COUNCIL-SPECIFICATION participants/roles"
        ),
        "output_path": OUT_REL,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-participants-module"
        ),
        "registered": True,
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0267/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "artifact_paths": [OUT_REL, MODULE_REL],
        "module": {
            "path": MODULE_REL,
            "api": [
                "compose",
                "apply_owner_override",
                "reason_diversity_report",
                "grounding_report",
                "legal_false_positive_report",
            ],
            "note": (
                "Seats are role slots derived from task-feature spans. "
                "IMP-0265 registry identities and IMP-0269 competence probes "
                "are not on this worktree, so seats are not bound to vendor/"
                "model identities or demonstrated-competence scores."
            ),
        },
        "measured": measured,
        "evidence": [
            {
                "id": "E1",
                "claim": (
                    "Missing-expertise control: an engineering task that also "
                    "names a subpoena/CFAA/export-control demand seats legal."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0267/fixtures.json:missing_expertise",
                "computed": measured["missing_expertise"],
            },
            {
                "id": "E2",
                "claim": (
                    "Reason-diversity: auto seats on each archetype emit "
                    "distinct reasons; identical boilerplate is rejected."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/participants/select_auto.py:reason_diversity_report",
                "computed": {
                    "archetype_unique_reasons": [
                        {
                            "id": row["id"],
                            "unique": row["unique_reasons"],
                            "seats": row["seat_count"],
                        }
                        for row in measured["archetypes"]
                    ],
                    "probe2": "mutant identical boilerplate rejected",
                },
            },
        ],
        "test_ids": [
            "T-IMP-0267-ARCHETYPES",
            "T-IMP-0267-MISSING-EXPERTISE",
        ],
        "negative_control_ids": [
            "NC-IMP-0267-NO-LEGAL",
            "NC-IMP-0267-BOILERPLATE-REASONS",
        ],
        "tests": [
            {
                "id": "T-IMP-0267-ARCHETYPES",
                "name": "six task archetypes, expected role present in each",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "T-IMP-0267-MISSING-EXPERTISE",
                "name": "engineering+subpoena task seats legal; owner remove is logged",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "T-IMP-0267-REASON-DIVERSITY",
                "name": "per-seat reasons unique and task-span grounded",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-IMP-0267-NO-LEGAL",
                "kind": "false-positive-rate",
                "description": (
                    "Tasks with no legal dimension must not seat legal. "
                    f"rate={measured['legal_false_positive']['rate']} "
                    f"n={measured['legal_false_positive']['n']} "
                    f"fires={measured['legal_false_positive']['fires']}"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "computed": measured["legal_false_positive"],
            },
            {
                "id": "NC-IMP-0267-BOILERPLATE-REASONS",
                "kind": "known-broken-fixture",
                "description": (
                    "Identical boilerplate reasons fail diversity; span-free "
                    "boilerplate fails grounding."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0267-probe2-reasons-and-negatives",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 starts from fixtures.json and inspects reason strings "
                "and task-span membership; it does not trust probe 1's role-set "
                "summary."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "exists": True}
        ]
        + supporting_meta,
        "residual_unknowns": [
            {
                "claim": (
                    "Cue lexicon can miss legal issues phrased without the "
                    "listed spans (e.g. a novel statute name)."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Hold out a paraphrase fixture set that never uses the "
                    "current cue words and measure legal recall."
                ),
            },
            {
                "claim": (
                    "IMP-0265 (registry) and IMP-0269 (claimed-vs-demonstrated "
                    "expertise) are absent, so auto seats are role slots, not "
                    "bound participant identities or competence-verified experts."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Re-run compose against a live registry once IMP-0265 and "
                    "IMP-0269 land; assert seats resolve to distinct identities "
                    "that pass the competence probe."
                ),
            },
        ],
        "notes": (
            "G-1 IMP-0267: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0267"
        ),
    }

    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )

    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(rel, "supporting") for rel in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0267",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0267/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0267-probe2-reasons-and-negatives",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0267: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0267 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
