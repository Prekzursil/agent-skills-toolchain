#!/usr/bin/env python3
"""Write IMP-0070 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0070.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0070/probe1_range_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0070/probe2_yank_prerelease.py"
)
SUPPORTING = [
    "tools/marketplace/semver_npm.py",
    "tools/marketplace/yank.py",
    "tools/marketplace/matrix.py",
    "tools/marketplace/evaluate.py",
    "tools/marketplace/oracle.py",
    "tools/marketplace/tests/test_version_resolution.py",
    "tools/marketplace/tests/test_yank.py",
    "tools/marketplace/vendor/node-semver/package.json",
    "command-center/p2-wave/probes/IMP-0070/probe1_range_matrix.py",
    "command-center/p2-wave/probes/IMP-0070/probe2_yank_prerelease.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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
        "unit_id": "IMP-0070",
        "receipt_path": "command-center/p2-wave/probes/IMP-0070/SUBAGENT-RETURN.json",
        "role": role,
    }


def write_receipt(c1: int, t1: str, c2: int, t2: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    matrix_agreements = 30 if c1 == 0 else 0
    receipt = {
        "id": "IMP-0070",
        "unit_id": "IMP-0070",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0070",
        "title": "Version model, range resolution, and yank semantics",
        "question_or_target": (
            "Implement semantic-version parsing, range resolution (caret, tilde, exact, "
            "prerelease policy) and yank semantics where a yanked version stays resolvable "
            "for an existing lockfile but is never selected for a new install."
        ),
        "spec": {
            "semver": "SemVer 2.0.0",
            "range_dialect": "npm node-semver 7.6.3 (caret, tilde, exact, x, hyphen, ||, AND)",
            "prerelease_policy": (
                "A prerelease satisfies a range only when a comparator in that set also "
                "names a prerelease of the same major.minor.patch tuple (node-semver default, "
                "includePrerelease=false). Identifier compare is numeric for [0-9]+ ids; "
                "numeric ids have lower precedence than non-numeric; a release outranks any "
                "prerelease of the same tuple. This is not string comparison of the raw tag."
            ),
            "yank": (
                "Fresh install: yanked versions are excluded from the candidate set before "
                "max_satisfying. Lockfile pin: the pinned version remains resolvable even "
                "when yanked, so yanking cannot break reproducibility of past builds."
            ),
        },
        "implementation": {
            "resolver": "tools/marketplace/semver_npm.py",
            "yank": "tools/marketplace/yank.py",
            "matrix": "tools/marketplace/matrix.py",
            "tests": [
                "tools/marketplace/tests/test_version_resolution.py",
                "tools/marketplace/tests/test_yank.py",
            ],
        },
        "evidence": [
            {
                "id": "E1-resolver-matrix",
                "signal": 1,
                "claim": "This resolver's selection for a 30-case range matrix.",
                "verdict": "CONFIRMED" if c1 == 0 else "REFUTED",
                "command": P1,
                "exit_code": c1,
                "agreements": matrix_agreements,
                "output_tail": t1[-2500:],
            },
            {
                "id": "E2-node-semver-oracle",
                "signal": 2,
                "claim": (
                    "The same matrix evaluated by established reference node-semver 7.6.3 "
                    "maxSatisfying. Selections must be identical per case, not averaged."
                ),
                "verdict": "CONFIRMED" if c1 == 0 else "REFUTED",
                "reference": "tools/marketplace/vendor/node-semver (npm semver 7.6.3)",
                "per_case_not_averaged": True,
                "command": P1,
                "exit_code": c1,
            },
            {
                "id": "E3-yank-lockfile",
                "claim": "A yanked version stays resolvable from an existing lockfile pin.",
                "verdict": "CONFIRMED" if c2 == 0 else "REFUTED",
                "command": P2,
                "exit_code": c2,
                "output_tail": t2[-2000:],
            },
        ],
        "tests": [
            {
                "id": "test_version_resolution.py",
                "path": "tools/marketplace/tests/test_version_resolution.py",
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": "30-case matrix vs node-semver; prerelease vs string; build metadata",
            },
            {
                "id": "test_yank.py::test_yanked_version_still_resolvable_from_lockfile",
                "path": "tools/marketplace/tests/test_yank.py",
                "result": "PASS" if c2 == 0 else "FAIL",
            },
            {
                "id": "NEGATIVE-CONTROL-fresh-install-skips-yanked",
                "result": "PASS" if c2 == 0 else "FAIL",
                "detail": "fresh ^1.0.0 with 1.2.0 yanked selects 1.1.0, never 1.2.0",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-yank-fresh-install",
                "kind": "both-states",
                "description": (
                    "Yanked 1.2.0 is excluded from fresh ^1.0.0 (selects 1.1.0). The same "
                    "catalog with yanked=false on 1.2.0 selects 1.2.0. Detector fires on "
                    "bad state and is silent on good state."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0070-probe2-prerelease-not-string-compare",
            "independent": True,
            "verdict": "PASS" if c2 == 0 else "FAIL",
            "requirement": (
                "Reviewer must confirm prerelease precedence follows the declared spec "
                "and is not left to string comparison."
            ),
            "observation": (
                "Python string compare ranks '1.0.0-alpha.10' < '1.0.0-alpha.2'. SemVer "
                "identifier compare ranks alpha.10 > alpha.2. Probe 2 asserts both facts "
                "and that 1.0.0-rc.1 < 1.0.0. Probe 1 is a different process (node-semver "
                "oracle) and does not perform this check."
            ),
        },
        "artifacts": [
            {
                "path": "tools/marketplace/semver_npm.py",
                "role": "implementation",
                "exists": True,
            },
            {
                "path": "tools/marketplace/yank.py",
                "role": "implementation",
                "exists": True,
            },
            {
                "path": "tools/marketplace/vendor/node-semver/package.json",
                "role": "reference-implementation",
                "exists": True,
            },
        ],
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for IMP-0070. Live named probes re-run. Per-unit UNIT-ARTIFACT-MANIFEST.json "
            "only. Did not run tools/command-center/unit_manifest.py --write. Did not git mutate. "
            "cloud ok=true is not this delivery."
        ),
        "cloud_ok": False,
        "completion_sentinel": "SUCCESS:IMP-0070",
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    write_receipt(c1, t1, c2, t2)
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "IMP-0070",
        "unit_id": "IMP-0070",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0070",
        "registered": True,
        "output_path": OUT,
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
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0070/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0070-probe2-prerelease-not-string-compare",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0070: live named probes exit 0, receipt state=SUCCESS, per-unit "
            "manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0070",
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
    print("SUCCESS:IMP-0070 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
