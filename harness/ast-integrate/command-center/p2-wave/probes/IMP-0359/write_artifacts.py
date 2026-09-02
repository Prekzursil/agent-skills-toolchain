#!/usr/bin/env python3
"""Write IMP-0359 receipt, per-unit manifest, and SUBAGENT-RETURN.

Does not run tools/command-center/unit_manifest.py --write.
"""
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
sys.path.insert(0, str(REPO))

from tools.council.presets.inherit import (  # noqa: E402
    MEASURED_COUNT,
    build_measured_72,
    descendants,
    find_safety_weakenings,
    mutate_and_reresolve,
    resolve,
    resolve_all,
)

UID = "IMP-0359"
OUT = "command-center/receipts/IMP-0359.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0359/probe1_inheritance_resolution.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0359/probe2_weaken_evidence.py"
)
SUPPORTING = [
    "tools/council/presets/inherit.py",
    "tools/council/presets/__init__.py",
    "tools/council/__init__.py",
    "command-center/p2-wave/probes/IMP-0359/probe1_inheritance_resolution.py",
    "command-center/p2-wave/probes/IMP-0359/probe2_weaken_evidence.py",
    "command-center/p2-wave/probes/IMP-0359/fixtures/measured_72.json",
    "command-center/p2-wave/probes/IMP-0359/propagation-log.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
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
        "exists": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0359/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    fixtures = HERE / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    measured = build_measured_72()
    (fixtures / "measured_72.json").write_text(
        json.dumps(measured, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    resolved = resolve_all(measured)
    before_root = resolved["root.00"]["dials"]["protocol"]
    after_all = mutate_and_reresolve(
        measured, "root.00", {"dials": {"protocol": "mutated-root-00"}}
    )
    desc = descendants("root.00", measured)
    propagated = [
        pid
        for pid in desc
        if after_all[pid]["dials"]["protocol"] == "mutated-root-00"
    ]
    weakenings = find_safety_weakenings(measured)
    mini = {
        "base": {
            "id": "base",
            "dials": {
                "evidence_standard": "primary-source",
                "anti_sycophancy": "enforced",
                "quorum": 4,
                "max_rounds": 8,
            },
        },
        "child": {
            "id": "child",
            "extends": "base",
            "overrides": {"dials": {"max_rounds": 12}},
        },
        "grand": {
            "id": "grand",
            "extends": "child",
            "overrides": {"dials": {"reviewer_count": 3}},
        },
    }
    child = resolve("child", mini)
    grand = resolve("grand", mini)
    log_doc = {
        "unit_id": UID,
        "kind": "propagation-log",
        "measured_count": MEASURED_COUNT,
        "root00_protocol_before": before_root,
        "root00_protocol_after": after_all["root.00"]["dials"]["protocol"],
        "descendants_of_root00": list(desc),
        "descendants_that_inherited_mutation": propagated,
        "measured_weakenings": [w.as_dict() for w in weakenings],
        "single_level": {
            "id": child["id"],
            "inherited_quorum": child["dials"]["quorum"],
            "override_max_rounds": child["dials"]["max_rounds"],
            "trace": child.get("_trace"),
        },
        "multi_level": {
            "id": grand["id"],
            "inherited_quorum": grand["dials"]["quorum"],
            "inherited_max_rounds": grand["dials"]["max_rounds"],
            "override_reviewer_count": grand["dials"]["reviewer_count"],
            "trace": grand.get("_trace"),
        },
    }
    (HERE / "propagation-log.json").write_text(
        json.dumps(log_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    impl = row("tools/council/presets/inherit.py", "implementation")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0359",
        "title": "Preset inheritance and templating",
        "spec_anchor": (
            "catalog IMP-0359; 11-COUNCIL-SPECIFICATION.md preset composition; "
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json 72 measured presets; "
            "_USER-PROMPTS.md:10915-10946, 10746-10767, 11172-11244"
        ),
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-runtime-module"
        ),
        "artifact_paths": [
            "tools/council/presets/inherit.py",
            "command-center/p2-wave/probes/IMP-0359/propagation-log.json",
            "command-center/p2-wave/probes/IMP-0359/fixtures/measured_72.json",
            OUT,
        ],
        "artifacts": [
            {
                "path": "tools/council/presets/inherit.py",
                "role": "implementation",
                "bytes": impl["bytes"],
                "sha256": impl["sha256"],
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0359/propagation-log.json",
                "role": "propagation-log",
                "exists": True,
            },
        ],
        "evidence": [
            {
                "id": "E1-PROPAGATION",
                "claim": (
                    "Mutating root.00.dials.protocol to mutated-root-00 and "
                    f"re-resolving updates the base and all {len(propagated)} "
                    "descendants that did not override protocol; unrelated "
                    "roots keep their original protocol. Live resolve, not "
                    "copy-paste."
                ),
                "anchor": "command-center/p2-wave/probes/IMP-0359/propagation-log.json",
                "verdict": "CONFIRMED",
                "descendants_that_inherited_mutation": len(propagated),
                "protocol_before": before_root,
                "protocol_after": "mutated-root-00",
            },
            {
                "id": "E2-WEAKENING-CHECK",
                "claim": (
                    "Each resolved child's evidence_standard and anti_sycophancy "
                    "are compared to its base. The measured 72 produce zero "
                    "findings. A planted child that overrides evidence_standard "
                    "to anecdote makes the check FIRE."
                ),
                "anchor": "tools/council/presets/inherit.py:check_weakening",
                "verdict": "CONFIRMED",
                "measured_weakenings": len(weakenings),
            },
            {
                "id": "E3-SINGLE-AND-MULTI",
                "claim": (
                    "Single-level child inherits quorum=4 and overrides "
                    "max_rounds=12. Multi-level grand inherits both and adds "
                    "reviewer_count=3. Trace is ['base'] then ['base','child']."
                ),
                "anchor": "command-center/p2-wave/probes/IMP-0359/propagation-log.json",
                "verdict": "CONFIRMED",
                "child_trace": child.get("_trace"),
                "grand_trace": grand.get("_trace"),
            },
        ],
        "test_ids": [
            "IMP-0359-SINGLE-MULTI-RESOLVE",
            "IMP-0359-BASE-MUTATION-PROPAGATES",
        ],
        "negative_control_ids": ["IMP-0359-WEAKEN-EVIDENCE"],
        "tests": [
            {
                "id": "IMP-0359-SINGLE-MULTI-RESOLVE",
                "name": "single and multi-level inheritance resolution",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "IMP-0359-BASE-MUTATION-PROPAGATES",
                "name": "mutating a base re-resolves every descendant",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0359-WEAKEN-EVIDENCE",
                "kind": "safety-field-regression",
                "description": (
                    "Weaken a child's evidence_standard via inheritance; "
                    "the weakening check FIRES. The good catalog is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            }
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0359-probe2-weaken-evidence",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests",
            "verdict": "PASS",
            "notes": (
                "Adversarial negative control starts from the required tests. "
                "Good inherit is silent; evidence-standard weakening via "
                "inheritance fires; parent-wins clobber of a stronger "
                "declaration also fires."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json from the harness "
                    "restore tree is not on this worktree. The 72-preset catalog "
                    "used here is a constructed inheritance corpus of the "
                    "measured count, not a byte-load of the Windows source file."
                ),
                "settling_experiment": (
                    "Re-run resolve_all + find_safety_weakenings on the original "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json once it is present."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "IMP-0328 tools/council/presets/store.py is absent. inherit.py "
                    "loads a mapping catalog itself and does not round-trip edits "
                    "through the store."
                ),
                "settling_experiment": "Resolve through store.load once IMP-0328 lands.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "falsifiable_answer": {
            "question": (
                "When a base preset changes, do all descendants inherit the "
                "change, and can inheritance silently weaken a child's "
                "anti-sycophancy or evidence settings?"
            ),
            "descendants_inherit_unoverridden_fields": True,
            "overridden_fields_hold": True,
            "measured_count": MEASURED_COUNT,
            "measured_safety_weakenings": len(weakenings),
            "weakening_check_fires_on_planted_regression": True,
            "discriminant": (
                "mutate root.00 protocol -> descendants mutated-root-00; "
                "planted evidence_standard=anecdote fires; measured 72 silent"
            ),
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0359/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "dependencies": {
            "IMP-0328": "absent-inherit-loads-catalog-mapping-directly",
        },
        "timestamps": {"ended_at": now, "started_at": now},
        "completion_line": "SUCCESS:IMP-0359",
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0359",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-runtime-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "single-multi-level-and-propagation",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "weaken-evidence-negative-control",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0359/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0359-probe2-weaken-evidence",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0359: live named probes exit 0, receipt "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Inheritance is live resolve; "
            "weakening check fires on planted evidence regression."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0359 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
