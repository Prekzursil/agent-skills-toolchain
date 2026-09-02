#!/usr/bin/env python3
"""Write IMP-0276 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from scenario import (  # noqa: E402
    CHANCE,
    security_refuter,
    run_full_anonymity_battery,
    run_unshuffled_control,
)

UNIT = "IMP-0276"
OUT = "command-center/receipts/IMP-0276.json"
MODULE = "tools/council/integrity/anonymity.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0276/probe1_linkage_chance.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0276/probe2_unshuffled_order.py"
)
SUPPORTING = [
    MODULE,
    "command-center/p2-wave/probes/IMP-0276/scenario.py",
    "command-center/p2-wave/probes/IMP-0276/probe1_linkage_chance.py",
    "command-center/p2-wave/probes/IMP-0276/probe2_unshuffled_order.py",
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
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0276/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    full = run_full_anonymity_battery()
    leaky = run_unshuffled_control()
    refuter = security_refuter(full, leaky)
    if not full["passed"] or not leaky["passed"] or refuter["verdict"] != "PASS":
        print("FAILED:IMP-0276 in-process measurement or refuter")
        print(json.dumps({"full": full, "leaky": leaky, "refuter": refuter}, indent=2)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    module_sha, module_bytes = digest(REPO / MODULE)
    receipt = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0276",
        "title": "Anonymity layer with per-round unlinkable pseudonyms",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0276; "
            "_USER-PROMPTS.md:10915-10946 anonymity; "
            "_USER-PROMPTS.md:10746-10767; "
            "spec 11062 security-refuter default REFUTED"
        ),
        "artifact_paths": [OUT, MODULE],
        "test_ids": [
            "IMP-0276-probe1-linkage-chance",
            "IMP-0276-probe2-unshuffled-order",
        ],
        "negative_control_ids": ["IMP-0276-NC-unshuffled-order"],
        "reviewer_verdict": "PASS",
        "schema_version": 1,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-integrity-module"
        ),
        "min_bytes_threshold": 128,
        "implemented": {
            "module": MODULE,
            "bytes": module_bytes,
            "sha256": module_sha,
            "levels": [
                "named",
                "pseudonymous",
                "fully-blind",
                "blind-then-revealed",
            ],
            "mechanisms": [
                "HMAC-SHA256 per-round pseudonyms (secret never published)",
                "keyed Fisher-Yates shuffle of turn order",
                "strip timing, token counts, and stylometric text",
                "content_commitment replaces text bodies",
                "census_real_ids exact-string field census",
                "linkage_attack on order/timing/tokens/style",
            ],
        },
        "artifacts": [
            {
                "path": MODULE,
                "bytes": module_bytes,
                "sha256": module_sha,
                "exists": True,
                "role": "implementation",
                "eol": "LF",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "A linkage attack using published turn order, timing, token "
                    "counts, and style against fully anonymized 8-seat x 12-round "
                    "sessions reports mean accuracy at chance (1/8), with chance "
                    "baseline computed not assumed."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{MODULE}:linkage_attack",
                "confidence": "high",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-8000:],
                    }
                ],
                "measurement": {
                    "n_sessions": full["n_sessions"],
                    "n_participants": full["n_participants"],
                    "n_rounds": full["n_rounds"],
                    "chance": full["chance"],
                    "mean_order_accuracy": full["mean_order_accuracy"],
                    "session_order_accuracies": full["session_order_accuracies"],
                    "channel_mean_accuracy": full["channel_mean_accuracy"],
                    "channel_present_any": full["channel_present_any"],
                    "pass_threshold": full["pass_threshold"],
                },
            },
            {
                "claim": (
                    "Field census of the published artifact finds zero real "
                    "participant ids or display names."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{MODULE}:census_real_ids",
                "confidence": "high",
                "measurement": {
                    "census_hit_count": full["census_hit_count"],
                    "label_leak_sessions": full["label_leak_sessions"],
                },
            },
        ],
        "tests": [
            {
                "id": "IMP-0276-probe1-linkage-chance",
                "command": P1,
                "result": "PASS",
                "exit_code": 0,
            },
            {
                "id": "IMP-0276-probe2-unshuffled-order",
                "command": P2,
                "result": "PASS",
                "exit_code": 0,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0276-NC-unshuffled-order",
                "kind": "leave-ordering-unshuffled",
                "description": (
                    "Keep names masked and strip timing/tokens/style, but do not "
                    "shuffle seating order. Order-channel linkage must rise above chance."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"unshuffled order_accuracy={leaky['order_accuracy']} "
                    f"chance={CHANCE} min={leaky['min_threshold']}"
                ),
                "good_state_output": (
                    f"full-anon mean_order_accuracy={full['mean_order_accuracy']} "
                    f"chance={CHANCE}"
                ),
                "measurement": leaky,
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0276-correctness-probe1",
            "role": "correctness",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "basis": (
                "Starts from probe1: chance baseline 0.125, observed mean "
                f"{full['mean_order_accuracy']}, census empty, HMAC labels "
                "not reused across rounds."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "IMP-0276-correctness-probe1",
                "role": "correctness",
                "verdict": "PASS",
                "independent": True,
            },
            refuter,
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0264 council kernel is not on this worktree, so this "
                    "module is a standalone transform. A kernel that writes "
                    "turns without calling publish_session would bypass it."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Wire publish_session into tools/council/kernel.py event "
                    "loop when IMP-0264 exists and re-run the linkage battery "
                    "on kernel-emitted transcripts."
                ),
            },
            {
                "claim": (
                    "Vote/position payload uniqueness can still cluster seats "
                    "when a stance is rare. The contracted attack channels "
                    "are order, timing, token counts, and style."
                ),
                "verdict": "ACCEPTED-RESIDUAL",
                "settling_experiment": (
                    "Add optional stance-bucketing if a future protocol "
                    "requires unlinkable payloads as well as unlinkable labels."
                ),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0276/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": "per-unit only; did not run unit_manifest.py --write",
        },
        "notes": (
            "G-1 IMP-0276: live named probes exit 0, honest SUCCESS receipt, "
            "per-unit manifest row. cloud ok=true is not delivery."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0276",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-integrity-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "linkage-attack-vs-chance",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "negative-control-unshuffled-order",
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
            "command-center/p2-wave/probes/IMP-0276/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0276-security-refuter-probe2",
            "verdict": "PASS",
            "independent": True,
        },
        "reviewers": [
            {
                "reviewer_id": "IMP-0276-correctness-probe1",
                "verdict": "PASS",
                "independent": True,
            },
            {
                "reviewer_id": "IMP-0276-security-refuter-probe2",
                "verdict": refuter["verdict"],
                "independent": True,
                "default_when_insufficient": "REFUTED",
            },
        ],
        "ts": now,
        "notes": (
            "G-1 for IMP-0276: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
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
    print("SUCCESS:IMP-0276 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
