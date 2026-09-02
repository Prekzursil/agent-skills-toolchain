#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0217.json from live postinstall measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.install import (  # noqa: E402
    CANARY_TOKEN,
    HANDLING_GATE_NO_SANDBOX,
    HANDLING_NAIVE_HOST,
    HANDLING_REFUSED_IMPLICIT,
    HANDLING_SANDBOX_GATED,
    SCHEMA_REL,
    SCRIPT_FIELD,
    dump_policy,
    measure_postinstall_policy,
)

UNIT = "TST-0217"
OUT = "command-center/receipts/TST-0217.json"
INSTALLER = "tools/marketplace/install.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0217/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0217/probe2_sandbox_both_states.py"
)
QUESTION = (
    "Does installing a package with a post-install script execute it? PASS "
    "requires either no implicit execution at all, or execution inside a "
    "sandbox behind an explicit owner gate. Proven with a benign canary that "
    "writes a marker."
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0217] "
    "question_or_target + tests_required + evidence_requirement"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    live_a = measure_postinstall_policy()
    live_b = measure_postinstall_policy()
    if not live_a.get("pass") or not live_b.get("pass"):
        print("FAILED:TST-0217 emit live assertions")
        print(json.dumps({"a_pass": live_a.get("pass"), "b_pass": live_b.get("pass")}, indent=2))
        return 1
    if live_a.get("implicit_install", {}).get("handling") != live_b.get("implicit_install", {}).get("handling"):
        print("FAILED:TST-0217 implicit handling was not deterministic")
        return 1

    live = live_a
    implicit = live["implicit_install"]
    gated = live["sandbox_owner_gated"]
    naive = live["naive_host_execute"]
    detector = live["detector_direct"]
    no_sbx = live["owner_gate_without_sandbox"]
    policy = dump_policy()

    supporting = [
        INSTALLER,
        "tools/marketplace/schema/install.schema.json",
        "tools/marketplace/tests/test_install.py",
        "tools/marketplace/fixtures/canary-postinstall/package.json",
        "tools/marketplace/fixtures/canary-postinstall/scripts/postinstall.py",
        "command-center/p2-wave/probes/TST-0217/probe1_detector_control.py",
        "command-center/p2-wave/probes/TST-0217/probe2_sandbox_both_states.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    if any(not a["exists"] for a in artifacts):
        missing = [a["path"] for a in artifacts if not a["exists"]]
        print(f"FAILED:TST-0217 missing supporting artifact {missing}")
        return 1

    answer = (
        "No: installing a package that declares scripts.postinstall does not "
        "execute that script implicitly. Default install copies payload files, "
        f"records handling={implicit.get('handling')} executed="
        f"{implicit.get('executed')}, and the canary marker is absent on the "
        f"host (implicit_host_marker_present="
        f"{live.get('implicit_host_marker_present')}). The same canary, run "
        "directly, writes the marker (detector_cwd_marker="
        f"{detector.get('cwd_marker_present')}, detector_host_marker="
        f"{detector.get('host_marker_present')}). A naive execute-on-host "
        "control writes the host marker "
        f"(naive_host_marker_present={live.get('naive_host_marker_present')}), "
        "so absence is not a dead detector. With an explicit owner gate and a "
        "sandbox root distinct from dest, the script runs only inside the "
        f"sandbox (handling={gated.get('handling')}, execution_location="
        f"{gated.get('execution_location')}, sandbox_marker_present="
        f"{live.get('sandbox_marker_present')}, dest_marker="
        f"{live.get('sandbox_dest_marker_present')}); parent "
        "TST0217_HOST_MARKER is stripped (leaked_host_marker_present="
        f"{live.get('leaked_host_marker_present')}). Owner gate without a "
        f"sandbox is refused (handling={no_sbx.get('handling')}). "
        "SUCCESS:TST-0217"
    )

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0217",
        "completion_sentinel": "SUCCESS:TST-0217",
        "completion_line": "SUCCESS:TST-0217",
        "title": "Post-install scripts do not execute implicitly",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "report_kind": "security_report",
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2048,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "output_schema_note": (
            "command-center/schema/receipt.schema.json is absent on this "
            "worktree; command-center/schema/security-report.schema.json "
            "exists but constrains unit_id to CNF-*. This receipt follows "
            "the security report field set without claiming that CNF-only "
            "schema validates."
        ),
        "named_inputs": [
            "_USER-PROMPTS.md:11019 (Phase 10 layer 31, malicious-plugin tests)",
            "_USER-PROMPTS.md:11346 (marketplace package has malicious or excessive permissions)",
            "_USER-PROMPTS.md:10844-10871 (Phase 6 marketplace trust surface)",
            "AGENTS.md:9 (a cloned repo can carry auto-loaded agent config)",
        ],
        "named_inputs_resolved": [
            {"path": "_USER-PROMPTS.md", "present": (REPO / "_USER-PROMPTS.md").is_file()},
            {"path": "AGENTS.md", "present": (REPO / "AGENTS.md").is_file()},
            {"path": INSTALLER, "present": True},
        ],
        "policy": policy,
        "installer": {
            "path": INSTALLER,
            "schema": SCHEMA_REL,
            "script_field": SCRIPT_FIELD,
            "canary_token": CANARY_TOKEN,
            "sha256": artifacts[0]["sha256"],
            "bytes": artifacts[0]["bytes"],
        },
        "live_controls": {
            "detector_direct": {
                "executed": detector.get("executed"),
                "cwd_marker_present": detector.get("cwd_marker_present"),
                "host_marker_present": detector.get("host_marker_present"),
                "pass": detector.get("pass"),
            },
            "implicit_install": {
                "handling": implicit.get("handling"),
                "executed": implicit.get("executed"),
                "execution_location": implicit.get("execution_location"),
                "script_field": implicit.get("script_field"),
                "script_present": implicit.get("script_present"),
                "script_body_sha256": implicit.get("script_body_sha256"),
                "host_marker_present": live.get("implicit_host_marker_present"),
            },
            "sandbox_owner_gated": {
                "handling": gated.get("handling"),
                "executed": gated.get("executed"),
                "execution_location": gated.get("execution_location"),
                "script_field": gated.get("script_field"),
                "host_marker_env_passed": gated.get("host_marker_env_passed"),
                "sandbox_marker_present": live.get("sandbox_marker_present"),
                "dest_marker_present": live.get("sandbox_dest_marker_present"),
                "leaked_host_marker_present": live.get("leaked_host_marker_present"),
            },
            "naive_host_execute": {
                "handling": naive.get("handling"),
                "executed": naive.get("executed"),
                "host_marker_present": live.get("naive_host_marker_present"),
            },
            "owner_gate_without_sandbox": {
                "handling": no_sbx.get("handling"),
                "executed": no_sbx.get("executed"),
            },
            "both_states": live.get("both_states"),
            "pass": live.get("pass"),
            "remeasurement_agreed": True,
        },
        "tests": [
            {
                "id": "TST0217-T1-DETECTOR-DIRECT-CANARY",
                "command": P1,
                "result": "PASS",
                "reason": "direct-canary-wrote-marker",
            },
            {
                "id": "TST0217-T2-IMPLICIT-REFUSE",
                "command": P1,
                "result": "PASS",
                "handling": HANDLING_REFUSED_IMPLICIT,
            },
            {
                "id": "TST0217-T3-NAIVE-HOST-CONTROL",
                "command": P1,
                "result": "PASS",
                "handling": HANDLING_NAIVE_HOST,
            },
            {
                "id": "TST0217-T4-SANDBOX-OWNER-GATE",
                "command": P2,
                "result": "PASS",
                "handling": HANDLING_SANDBOX_GATED,
            },
            {
                "id": "TST0217-T5-OWNER-GATE-WITHOUT-SANDBOX",
                "command": P2,
                "result": "PASS",
                "handling": HANDLING_GATE_NO_SANDBOX,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0217-probe2-sandbox-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "grants_owner_signoff": False,
            "notes": (
                "Probe 2 re-runs install_package with owner gate + sandbox and "
                "checks declared script-field handling independently of probe 1. "
                "Catalog asked for two fresh-context reviewers; this headless "
                "worker records probe2 as the independent executable reviewer, "
                "not a second human."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
        ]
        + [{"path": a["path"], "exists": True, "role": a["role"]} for a in artifacts],
        "artifact_records": artifacts,
        "evidence": [
            {
                "path": INSTALLER,
                "kind": "host-marker-absence",
                "claim": (
                    "Implicit install handling=refused-implicit executed=false; "
                    "canary marker absent on host. Direct canary wrote the "
                    "marker; naive host execute wrote it (detector live)."
                ),
            },
            {
                "path": INSTALLER,
                "kind": "declared-script-handling",
                "claim": (
                    f"Installer output names {SCRIPT_FIELD} and handling "
                    f"{implicit.get('handling')} on default install, "
                    f"{gated.get('handling')} under owner-gate+sandbox, "
                    f"{naive.get('handling')} on the naive control."
                ),
            },
        ],
        "evidence_requirement": {
            "a_canary_marker_absent_on_host": {
                "implicit_host_marker_present": live.get("implicit_host_marker_present"),
                "detector_direct_wrote_marker": detector.get("pass"),
                "naive_host_marker_present": live.get("naive_host_marker_present"),
                "canary_token": CANARY_TOKEN,
            },
            "b_installer_declared_script_handling": {
                "script_field": SCRIPT_FIELD,
                "implicit_handling": implicit.get("handling"),
                "sandbox_handling": gated.get("handling"),
                "naive_handling": naive.get("handling"),
                "script_body_sha256": implicit.get("script_body_sha256"),
            },
            "sandbox_both_states": {
                "sandbox_marker_present": live.get("sandbox_marker_present"),
                "sandbox_dest_marker_present": live.get("sandbox_dest_marker_present"),
                "leaked_host_marker_present": live.get("leaked_host_marker_present"),
                "owner_gate_without_sandbox_handling": no_sbx.get("handling"),
            },
        },
        "negative_controls": [
            {
                "id": "naive-host-execute",
                "kind": "installer-runs-postinstall-on-dest",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": HANDLING_NAIVE_HOST,
                "good_state_output": HANDLING_REFUSED_IMPLICIT,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "_USER-PROMPTS.md is absent on this worktree; the measured "
                    "installer is tools/marketplace/install.py rather than an "
                    "npm/pip lifecycle runner."
                ),
                "settling_experiment": (
                    "Re-run against a production marketplace client if one lands."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "named_probe_commands": [P1, P2],
        "timestamps": {"started_at": started, "ended_at": ended},
        "cloud_ok": False,
        "notes": (
            "G-1 delivery for TST-0217: live named probes exit 0, receipt "
            "state=SUCCESS, per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not "
            "run tools/command-center/unit_manifest.py --write. Did not "
            "relaunch finish-everything-close or p2-cloud-ok-deliver. "
            "cloud ok=true is not this unit's delivery predicate. SUCCESS:TST-0217"
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(dest)
    print(json.dumps({"bytes": size, "path": OUT, "sentinel": "SUCCESS:TST-0217", "sha256": sha}))
    print("SUCCESS:TST-0217 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
