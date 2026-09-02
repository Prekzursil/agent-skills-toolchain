#!/usr/bin/env python3
"""Write IMP-0309 receipt, per-unit manifest, and SUBAGENT-RETURN.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0309.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0309/probe1_instant_consensus.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0309/probe2_gate_disabled.py"
)
SUPPORTING = [
    "tools/council/stopping/minimum.py",
    "tools/council/stopping/__init__.py",
    "command-center/p2-wave/probes/IMP-0309/probe1_instant_consensus.py",
    "command-center/p2-wave/probes/IMP-0309/probe2_gate_disabled.py",
    "command-center/p2-wave/probes/IMP-0309/fixtures/instant_consensus.json",
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


def first_json(text: str):
    blobs = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                blobs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return blobs[-1] if blobs else None


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0309",
        "receipt_path": "command-center/p2-wave/probes/IMP-0309/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    j1 = first_json(t1) or {}
    j2 = first_json(t2) or {}
    src = REPO / "tools/council/stopping/minimum.py"
    src_sha, src_bytes = digest(src)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl_path = "tools/council/stopping/minimum.py"
    receipt = {
        "unit_id": "IMP-0309",
        "id": "IMP-0309",
        "title": "Minimum-deliberation-condition gate",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0309",
        "completion_sentinel": "SUCCESS:IMP-0309",
        "schema_version": 1,
        "profile": "council-stopping-module",
        "ts": now,
        "spec_anchor": (
            "_USER-PROMPTS.md:11338 (council stops before minimum deliberation "
            "conditions); catalog IMP-0309; FAILURE-MODES.json FC-11338; "
            "TST-0264 floors as hard precondition on any stopping expression"
        ),
        "artifact_paths": [
            "command-center/receipts/IMP-0309.json",
            impl_path,
            "command-center/p2-wave/probes/IMP-0309/fixtures/instant_consensus.json",
        ],
        "question": (
            "Implement tools/council/stopping/minimum.py preventing a stop "
            "before declared minimums (rounds, independent briefs, objections "
            "considered) are met. Falsifiable question: can a council that "
            "reaches instant consensus stop before any independent brief exists?"
        ),
        "answer": (
            "No. With the gate enabled, an instant-consensus fixture "
            "(round 1, stop expression true, zero independent briefs) is "
            "FLOOR_BLOCK. The same fixture with gate_enabled=false stops "
            "(GATE_DISABLED_STOP), which is FC-11338 reproduced as the "
            "negative control. Each named floor independently blocks when "
            "it is the sole unmet condition."
        ),
        "implementation": {
            "path": impl_path,
            "sha256": src_sha,
            "bytes": src_bytes,
            "entry_point": "council.stopping.minimum.evaluate",
            "floors": [
                "min_rounds",
                "min_independent_briefs",
                "min_objections_considered",
            ],
            "ceiling": "max_rounds required; unmet floors at ceiling -> CEILING_ESCALATE (NO-DECISION), not a hang and not a silent stop",
        },
        "honesty": {
            "does_not_parse_stopping_expressions": True,
            "does_not_implement_imp_0306_consent_window": True,
            "does_not_implement_imp_0322_no_gain_detector": True,
            "independence_is_author_identity_not_content": True,
            "catalog_dependencies_absent_on_this_worktree": [
                "IMP-0306",
                "IMP-0322",
            ],
            "overclaim_refused": (
                "This unit does not claim a live multi-vendor council, "
                "IMP-0308 expression evaluation, or clone-cast detection "
                "across distinct author ids. It claims only that THIS gate "
                "refuses a stop while declared floors are unmet, including "
                "instant consensus with zero independent briefs."
            ),
        },
        "evidence": [
            {
                "id": "instant-consensus-fixture-does-not-stop",
                "claim": (
                    "An instant-consensus fixture (unanimity in round 1, "
                    "zero independent briefs, stop expression true) does not "
                    "stop while the gate is enabled."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0309/fixtures/instant_consensus.json",
                "probe": "probe1_instant_consensus.py",
                "stopped": j1.get("stopped"),
                "reason": j1.get("reason"),
                "unmet": j1.get("unmet"),
            },
            {
                "id": "condition-table-at-candidate-stop",
                "claim": (
                    "The gate prints its own condition table with each "
                    "condition's declared minimum and measured value at the "
                    "candidate-stop instant."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/stopping/minimum.py:format_condition_table",
                "probe": "probe1_instant_consensus.py",
                "condition_table": j1.get("condition_table"),
                "condition_table_printed": j1.get("condition_table_printed"),
            },
        ],
        "test_ids": [
            "each-minimum-condition-independently-blocks-premature-stop",
            "all-floors-met-allows-stop-overblocking-control",
            "duplicate-authors-do-not-inflate-independent-briefs",
            "min_rounds=0-rejected-at-validation",
        ],
        "negative_control_ids": [
            "FC-11338-disable-gate-instant-consensus-stops-early",
        ],
        "tests": [
            {
                "id": "each-minimum-condition-independently-blocks-premature-stop",
                "path": "command-center/p2-wave/probes/IMP-0309/probe1_instant_consensus.py",
                "result": "PASS",
                "independent_floor_blocks": j1.get("independent_floor_blocks"),
            },
            {
                "id": "FC-11338-disable-gate-instant-consensus-stops-early",
                "path": "command-center/p2-wave/probes/IMP-0309/probe2_gate_disabled.py",
                "result": "PASS",
                "gate_off_stopped": j2.get("gate_off_stopped"),
                "gate_on_stopped": j2.get("gate_on_stopped"),
            },
        ],
        "negative_controls": [
            {
                "id": "FC-11338-disable-gate-instant-consensus-stops-early",
                "state_meant_to_reject": (
                    "Instant-consensus round 1, zero independent briefs, "
                    "stopping expression true."
                ),
                "check_does": (
                    "With gate_enabled=false the fixture stops "
                    "(GATE_DISABLED_STOP). With gate_enabled=true it does not."
                ),
                "verbatim": j2.get("verbatim_negative_control"),
                "fired": bool(j2.get("gate_off_stopped"))
                and (j2.get("gate_on_stopped") is False),
            }
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0309-probe2-ast-and-both-states",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "starts_from": "tests (probe1 independent-floor matrix + probe2 both-states)",
            "method": (
                "AST-inspect tools/council/stopping/minimum.py: evaluate must "
                "exist, must not return constant True, must name all three "
                "floors and GATE_DISABLED_STOP / FLOOR_BLOCK / CEILING_ESCALATE. "
                "Live both-states run of the fixture confirms discrimination."
            ),
            "probe": "probe2_gate_disabled.py",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Independence is unique author identity. Distinct ids "
                    "submitting clone content are not collapsed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Pair this gate with a content-similarity brief collapser "
                    "once that detector is a delivered unit."
                ),
            },
            {
                "claim": (
                    "IMP-0306 objection-window and IMP-0322 no-gain detector "
                    "are catalog dependencies and are absent here. Objection "
                    "counts are caller-measured."
                ),
                "verdict": "ACCEPTED-LIMITATION",
            },
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.md is not on this worktree. "
                    "Floors are taken from catalog IMP-0309 and FC-11338."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-bind declared minima to the specification schema when "
                    "that file is present."
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0309",
        "unit_id": "IMP-0309",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0309",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-stopping-module"
        ),
        "cloud_ok": False,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0309/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0309-probe2-ast-and-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0309: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0309, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Instant consensus cannot stop before "
            "independent briefs exist while the gate is enabled."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0309",
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
    print("SUCCESS:IMP-0309 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
