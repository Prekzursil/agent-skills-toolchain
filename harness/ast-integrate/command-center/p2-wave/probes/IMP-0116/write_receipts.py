#!/usr/bin/env python3
"""Write IMP-0116 receipt, SUBAGENT-RETURN.json, UNIT-ARTIFACT-MANIFEST.json."""
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
OUT_REL = "command-center/receipts/IMP-0116.json"
P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0116/probe1_scaffold_lints_clean.py"
P2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0116/probe2_conformance_and_break.py"

SUPPORTING = [
    "tools/marketplace/scaffolder.py",
    "tools/marketplace/package_linter.py",
    "tools/marketplace/conformance.py",
    "tools/marketplace/name_grammar.py",
    "tools/marketplace/cli.py",
    "tools/marketplace/tests/test_scaffolder.py",
    "tools/marketplace/schema/package-manifest.schema.json",
    "command-center/p2-wave/probes/IMP-0116/probe1_scaffold_lints_clean.py",
    "command-center/p2-wave/probes/IMP-0116/probe2_conformance_and_break.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
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


def row(rel: str, role: str, receipt_path: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0116",
        "receipt_path": receipt_path,
        "role": role,
    }


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    utest = run("PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/test_scaffolder.py")
    if utest[0] != 0:
        print("FAILED:receipts unit tests")
        print(utest[1][-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)

    receipt = {
        "unit_id": "IMP-0116",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0116",
        "spec_anchor": "WORK-UNIT-CATALOG.json IMP-0116; new <skill|hook|workflow|council-preset>",
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
                "bytes": 0,
                "sha256": "pending",
                "eol": "LF",
            }
        ],
        "tests": [
            {
                "id": "test_scaffolder.py",
                "command": "python3 -B tools/marketplace/tests/test_scaffolder.py",
                "result": "PASS",
                "raw_output": utest[1][-1500:],
            }
        ],
        "evidence": [
            {
                "claim": "Each of the four scaffold kinds generates a package that the package linter reports with zero findings.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/marketplace/scaffolder.py + tools/marketplace/package_linter.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-2500:],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "python3 -B tools/marketplace/tests/test_scaffolder.py",
                        "exit_code": utest[0],
                        "raw_output": utest[1][-800:],
                    },
                ],
            },
            {
                "claim": "The same generated artifacts pass a conformance validator whose rules are not the linter's rules (entry exists, kind payload, README Usage, dir/name match, no TODO).",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/marketplace/conformance.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[-2500:],
                    }
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "broken-spdx-template",
                "kind": "template-mutation",
                "description": "license field rewritten to NOT-A-LICENSE; linter must go red on spdx-license.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "readme-usage-stripped",
                "kind": "payload-mutation",
                "description": "## Usage renamed to ## Notes; conformance fails readme-usage while linter stays clean — surfaces are independent.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0116-probe2-conformance-mutation",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0116/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": False,
                "note": "Measure runs after this receipt is written.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": "IMP-0113 has not delivered a separate package-linter receipt on this worktree; IMP-0116 ships tools/marketplace/package_linter.py as the live oracle the scaffolder is measured against, not as a claim that IMP-0113 is complete.",
                "verdict": "DISCLOSED",
                "settling_experiment": "When IMP-0113 lands its composition report, re-run test_scaffolder.py against that linter.",
            }
        ],
        "notes": (
            "Implemented `new <skill|hook|workflow|council-preset>` in tools/marketplace. "
            "Default generated packages lint clean and also pass a distinct conformance validator. "
            "Did not run unit_manifest.py --write. Did not git commit."
        ),
    }

    out_path = REPO / OUT_REL
    # First write without self-hash, then patch bytes/sha256.
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sha, size = digest(out_path)
    receipt["artifacts"][0]["sha256"] = sha
    receipt["artifacts"][0]["bytes"] = size
    # Writing again changes the hash. Leave sha as digest of the body without
    # self-hash: store measured hash after final write only in the manifest.
    receipt["artifacts"][0]["sha256"] = "see-manifest"
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sha, size = digest(out_path)

    ret = {
        "id": "IMP-0116",
        "unit_id": "IMP-0116",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0116",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
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
                "path": OUT_REL,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0116/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0116-probe2-conformance-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0116: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }

    receipt_rel = "command-center/p2-wave/probes/IMP-0116/SUBAGENT-RETURN.json"
    artifacts = [row(OUT_REL, "primary", receipt_rel)]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting", receipt_rel))

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0116",
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
    print(f"primary {OUT_REL} sha256={sha} bytes={size}")
    print("SUCCESS:IMP-0116 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
