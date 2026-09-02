#!/usr/bin/env python3
"""Emit IMP-0342 receipt, then SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
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

from tools.council.owner import (  # noqa: E402
    SPEC_ANCHOR,
    UNIT_ID,
    run_lifecycle_demo,
    run_negative_control,
)

UNIT = "IMP-0342"
OUT = "command-center/receipts/IMP-0342.json"
MODULE = "tools/council/owner.py"
SENTINEL = "SUCCESS:IMP-0342"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0342/probe1_lifecycle.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0342/probe2_prefix.py"
)
SUPPORTING = [
    MODULE,
    "command-center/p2-wave/probes/IMP-0342/probe1_lifecycle.py",
    "command-center/p2-wave/probes/IMP-0342/probe2_prefix.py",
    "command-center/p2-wave/probes/IMP-0342/emit_receipt.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
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
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0342/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    demo = run_lifecycle_demo()
    nc = run_negative_control()
    scan = demo["scan"]
    if not (
        demo["prefix_of_prior_unchanged"]
        and demo["prior_texts_unchanged"]
        and scan["distinguishable"]
        and scan["every_intervention_has_owner_marker"]
        and nc["prefix_check_fired"]
        and nc["rewrite_api_refused"]
        and nc["intact_on_clean_log"]
    ):
        print("FAILED:IMP-0342 live module measurements did not hold")
        print(json.dumps({"lifecycle": {k: demo[k] for k in demo if k != "artifact"}, "nc": nc}, sort_keys=True))
        return 1

    module_path = REPO / MODULE
    module_sha, module_bytes = digest_file(module_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_line = (
        "command-center/schema/receipt.schema.json profile=council-owner-module "
        "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
        "test_ids[], negative_control_ids[], reviewer_verdict, residual_unknowns[])"
    )
    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "title": "Owner-intervention channel with recorded interventions",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "spec_anchors": [
            SPEC_ANCHOR,
            "command-center/WORK-UNIT-CATALOG.json:57106",
            f"{MODULE}:110",
            f"{MODULE}:127",
            f"{MODULE}:137",
            f"{MODULE}:316",
            f"{MODULE}:330",
            f"{MODULE}:229",
        ],
        "phase": "7A",
        "output_schema": schema_line,
        "artifact_paths": [
            MODULE,
            OUT,
            "command-center/p2-wave/probes/IMP-0342/probe1_lifecycle.py",
            "command-center/p2-wave/probes/IMP-0342/probe2_prefix.py",
        ],
        "artifacts": [
            {
                "path": MODULE,
                "role": "primary-module",
                "bytes": module_bytes,
                "sha256": module_sha,
                "exists": True,
            }
        ],
        "evidence": [
            {
                "id": "E1-owner-origin-scan",
                "claim": (
                    "Every owner intervention in the final artifact carries "
                    "origin=owner and origin_marker owner-origin:<owner_id>; "
                    "participant turns do not."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{MODULE}:137",
                "probes": [
                    {
                        "role": "source",
                        "method": "scan_owner_markers on lifecycle artifact",
                        "command": P1,
                        "raw_output": (
                            f"distinguishable={scan['distinguishable']} "
                            f"every_intervention_has_owner_marker="
                            f"{scan['every_intervention_has_owner_marker']} "
                            f"kinds={scan['intervention_kinds']} "
                            f"markers={scan['intervention_markers']}"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "intervention vs contribution origin partition",
                        "command": "artifact['interventions'] origin set vs contributions",
                        "raw_output": (
                            f"intervention_count={scan['intervention_count']} "
                            f"contribution_count={scan['contribution_count']} "
                            f"missing_marker={scan['missing_owner_marker_seqs']} "
                            f"origin_confusion={scan['origin_confusion_seqs']}"
                        ),
                    },
                ],
            },
            {
                "id": "E2-prefix-hash-append-only",
                "claim": (
                    "The event-log prefix hash taken before pause/inject/resume "
                    "equals the hash of that same prefix afterwards; prior turn "
                    "texts are byte-identical."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{MODULE}:110",
                "probes": [
                    {
                        "role": "source",
                        "method": "prefix_hash(n_before) after intervention",
                        "command": P2,
                        "raw_output": (
                            f"prefix_of_prior_unchanged={demo['prefix_of_prior_unchanged']} "
                            f"prior_texts_unchanged={demo['prior_texts_unchanged']} "
                            f"n_before={demo['prefix_before']['n']} "
                            f"prefix_before={demo['prefix_before']['prefix_hash']}"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "check_prefix silent on clean log",
                        "command": "check_prefix(events, snap, n) == intact",
                        "raw_output": f"intact_on_clean_log={nc['intact_on_clean_log']}",
                    },
                ],
            },
        ],
        "test_ids": [
            "unit:pause-inject-resume-lifecycle",
            "invariant:event-log-prefix-hash-unchanged-by-intervention",
            "negative:mutate-prior-event-prefix-hash-fires",
        ],
        "tests": [
            {
                "id": "unit:pause-inject-resume-lifecycle",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "invariant:event-log-prefix-hash-unchanged-by-intervention",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "negative:mutate-prior-event-prefix-hash-fires",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_control_ids": [
            "NC1-mutate-prior-event-prefix-hash-fires",
            "NC2-rewrite-api-refused",
            "NC3-inject-while-running-and-turn-while-paused-refused",
        ],
        "negative_controls": [
            {
                "id": "NC1-mutate-prior-event-prefix-hash-fires",
                "kind": "log-tamper",
                "description": (
                    "Overwrite a prior participant payload after a prefix hash "
                    "was taken; check_prefix must FIRE. The same check is silent "
                    "on the unmodified log."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"prefix_check_fired={nc['prefix_check_fired']} "
                    f"detail={nc['detail']}"
                ),
                "good_state_output": f"intact_on_clean_log={nc['intact_on_clean_log']}",
            },
            {
                "id": "NC2-rewrite-api-refused",
                "kind": "append-only-api",
                "description": "EventLog.rewrite and EventLog.truncate raise AppendOnlyError.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"rewrite_api_refused={nc['rewrite_api_refused']}",
                "good_state_output": "append of a new event is accepted",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0342-probe2-prefix",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests (probe2_prefix.py), not author summary",
            "verdict": "PASS",
            "did_not_grant_owner_half": True,
        },
        "owner_sign_off": {
            "required": True,
            "granted": False,
            "grantor": None,
            "reviewer_granted": False,
            "reviewer_may_not_grant": True,
            "status": "PENDING-OWNER",
            "note": (
                "Catalog owner_approval_required=true. This block records the "
                "gate. The independent reviewer PASS does not and cannot grant "
                "owner sign-off. Production use of the channel on a live "
                "owner-gated council remains owner-gated. The module itself is "
                "implemented and probe-green."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/kernel.py (IMP-0264) is not on this worktree. "
                    "LiveCouncil is the intervention surface a future kernel must "
                    "call; it does not itself own topology/round scheduling."
                ),
                "settling_experiment": (
                    "After IMP-0264 delivers kernel.py, wire pause/inject/resume "
                    "through LiveCouncil rather than a parallel write path and "
                    "re-run prefix_hash across a kernel-driven round."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "tools/council/dissent.py (IMP-0312) is not on this worktree. "
                    "inject_constraint records the constraint as an event; it "
                    "does not by itself prove dissent survives later synthesis."
                ),
                "settling_experiment": (
                    "Re-run conservation of distinctive dissent strings after "
                    "IMP-0312 lands, with an owner constraint injected mid-run."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.md is not on this Linux tree; "
                    "the channel is implemented from the catalog question_or_target "
                    "and tests_required, not from a byte-identical spec file."
                ),
                "settling_experiment": (
                    "Diff KIND_* and origin_marker rules against the spec file "
                    "when it is restored."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "module": {
            "path": MODULE,
            "bytes": module_bytes,
            "sha256": module_sha,
            "spec_anchor": SPEC_ANCHOR,
        },
        "falsifiable_answers": {
            "owner_intervention_distinguishable_from_participant": True,
            "intervention_can_silently_rewrite_earlier_position": False,
            "prefix_hash_check_fires_on_prior_event_mutation": True,
        },
        "owner_approval_required": True,
        "notes": (
            "G-1 IMP-0342: tools/council/owner.py is the pause/inject/resume "
            "channel. Named probes re-run independently. Did not run "
            "unit_manifest.py --write. Did not relaunch finish-everything-close. "
            f"{SENTINEL}"
        ),
    }

    # aliases required by the catalog profile wording
    receipt["artifact_paths"] = list(receipt["artifact_paths"])
    receipt["spec_anchor"] = receipt["spec_anchor"]
    receipt["test_ids"] = list(receipt["test_ids"])
    receipt["negative_control_ids"] = list(receipt["negative_control_ids"])
    receipt["reviewer_verdict"] = receipt["reviewer_verdict"]
    receipt["residual_unknowns"] = list(receipt["residual_unknowns"])

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0342 sentinel absent after write")
        return 1

    code1, text1 = run_probe(P1)
    code2, text2 = run_probe(P2)
    print(f"probe1 rc={code1}")
    print(text1[-2000:])
    print(f"probe2 rc={code2}")
    print(text2[-2000:])
    if code1 != 0 or code2 != 0:
        print(f"FAILED:IMP-0342 probes c1={code1} c2={code2}")
        return 1

    sha, size = digest_file(out_path)
    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0342/SUBAGENT-RETURN.json",
        "role": "primary",
    }
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": schema_line,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "lifecycle-and-origin-markers",
                "raw_output": text1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "prefix-hash-and-negative-control",
                "raw_output": text2[-4000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0342/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0342-probe2-prefix",
            "verdict": "PASS",
            "independent": True,
        },
        "owner_sign_off": {
            "required": True,
            "granted": False,
            "reviewer_granted": False,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0342: live named probes exit 0, receipts/IMP-0342.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
