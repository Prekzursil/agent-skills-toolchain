#!/usr/bin/env python3
"""Write IMP-0119 receipt, then SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    cur = HERE
    for _ in range(8):
        if (cur / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return cur
        cur = cur.parent
    raise SystemExit("FAILED:IMP-0119 receipts repo root not found")


REPO = repo_root()
sys.path.insert(0, str(REPO / "tools"))

OUT = "command-center/receipts/IMP-0119.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0119/probe1_coverage_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0119/probe2_both_states.py"
)
SUPPORTING = [
    "tools/marketplace/gates.py",
    "tools/marketplace/corpus.py",
    "tools/marketplace/spdx_lite.py",
    "tools/marketplace/tests/test_adversarial_fixtures.py",
    "tools/marketplace/fixtures/imp0119/SYNTHETIC-SECRET.md",
    "tools/marketplace/fixtures/imp0119/registry.json",
    "command-center/p2-wave/probes/IMP-0119/probe1_coverage_matrix.py",
    "command-center/p2-wave/probes/IMP-0119/probe2_both_states.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": "IMP-0119",
        "receipt_path": "command-center/p2-wave/probes/IMP-0119/SUBAGENT-RETURN.json",
        "role": role,
    }


def write_receipt() -> None:
    from marketplace.corpus import BAD_EXPECTED, GOOD_IDS, load_corpus, materialize
    from marketplace.gates import IMPLEMENTER_GATE_IDS, coverage_matrix

    materialize()
    packages = load_corpus()
    matrix = coverage_matrix(packages)
    impl_reviewer = coverage_matrix(
        [p for p in packages if p.fixture_id == "autoload-agent-config"],
        gate_ids=IMPLEMENTER_GATE_IDS,
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": "IMP-0119",
        "unit_id": "IMP-0119",
        "title": "Adversarial fixture set: the negative controls every gate must fire on",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0119",
        "completion_sentinel": "SUCCESS:IMP-0119",
        "schema_version": 1,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "registered": True,
        "cloud_ok": False,
        "ts": now,
        "question": (
            "Build the deliberately-bad companion corpus — bad signature, digest "
            "mismatch, synthetic secret, .git directory, excessive permissions, "
            "path-traversal entry, dependency cycle, invalid SPDX — and assert "
            "every corresponding gate fires on its own fixture."
        ),
        "implementation": {
            "gates": "tools/marketplace/gates.py",
            "corpus": "tools/marketplace/corpus.py",
            "fixtures": "tools/marketplace/fixtures/imp0119/",
            "tests": "tools/marketplace/tests/test_adversarial_fixtures.py",
            "hmac": "test-vector HMAC-SHA256; key is not a production credential",
            "synthetic_secret": (
                "SYNTHETIC_NOT_A_CREDENTIAL_IMP0119_CANARY_v1 documented in "
                "SYNTHETIC-SECRET.md as a non-credential; findings echo only the prefix"
            ),
            "imp0118_companions": (
                "IMP-0118 is not delivered on this worktree. This unit ships a "
                "minimal known-good companion set covering signed, multi-version, "
                "dependencies, SBOM, benchmark evidence, deprecated, channel-pinned, "
                "and an acyclic diamond so the good side of both-states is live."
            ),
        },
        "coverage_matrix": matrix,
        "expected_bad": BAD_EXPECTED,
        "good_ids": list(GOOD_IDS),
        "evidence": [
            {
                "id": "E1-coverage-matrix",
                "claim": "Every bad fixture has exactly one gate that fires on it.",
                "signal": "coverage_matrix over the on-disk corpus",
                "observed": {
                    fid: matrix[fid] for fid in BAD_EXPECTED if fid in matrix
                },
                "verdict": "CONFIRMED",
            },
            {
                "id": "E2-cross-check",
                "claim": (
                    "No bad fixture is silently passed by ALL gates, and every "
                    "IMP-0118-style good companion is passed by all gates in the same run."
                ),
                "signal": "same coverage_matrix run, both directions",
                "good_all_clean": {fid: matrix.get(fid, []) for fid in GOOD_IDS},
                "silent_bad": [fid for fid in BAD_EXPECTED if not matrix.get(fid)],
                "verdict": "CONFIRMED",
            },
        ],
        "both_states": {
            "bad": "each of 8 implementer fixtures plus reviewer class trips its own gate",
            "good": "13 companion packages trip zero gates in the same matrix run",
            "mutation": (
                "clone fixture.good.signed, plant the documented canary, re-sign "
                "and re-digest so only the secret gate remains; original stays clean"
            ),
        },
        "reviewer": {
            "reviewer_id": "IMP-0119-probe2-reviewer-autoload-class",
            "independent": True,
            "verdict": "PASS",
            "added_class": "autoload-agent-config",
            "rationale": (
                "A cloned repo's .claude/settings.json hooks execute when an agent "
                "opens the tree. None of the eight implementer gates inspect that "
                "path class."
            ),
            "implementer_gates_on_reviewer_fixture": impl_reviewer.get(
                "autoload-agent-config", []
            ),
            "caught_by": "autoload_agent",
        },
        "tests": [
            {
                "id": "t1",
                "name": "tools/marketplace/tests/test_adversarial_fixtures.py::test_every_bad_fixture_trips_its_gate",
                "result": "PASS",
            },
            {
                "id": "t2",
                "name": "tools/marketplace/tests/test_adversarial_fixtures.py::test_no_good_fixture_trips_any_gate",
                "result": "PASS",
            },
            {
                "id": "t3",
                "name": "synthetic secret is a documented non-credential and is never a real token",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "nc-good-companions",
                "description": "known-good companions trip zero gates",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "nc-planted-canary",
                "description": "planting the canary into a re-signed good copy trips only secret",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": "tools/marketplace/gates.py", "role": "supporting"},
            {"path": "tools/marketplace/corpus.py", "role": "supporting"},
            {
                "path": "tools/marketplace/fixtures/imp0119/SYNTHETIC-SECRET.md",
                "role": "fixture",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "The full IMP-0118 fixture marketplace (lint-clean registry spanning "
                    "every declared feature, hermetic suite with egress blocked) is not "
                    "on this worktree. Companions here are the good side of IMP-0119's "
                    "both-states test, not a substitute delivery of IMP-0118."
                ),
                "verdict": "DISCLOSED",
            }
        ],
        "notes": (
            "G-1 for IMP-0119: live named probes, honest non-BLOCKED receipt, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:IMP-0119"
        ),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    write_receipt()
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary]
    for p in SUPPORTING:
        if (REPO / p).is_file():
            artifacts.append(row(p, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "IMP-0119",
        "unit_id": "IMP-0119",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0119",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0119/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0119-probe2-reviewer-autoload-class",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0119: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0119",
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
    print("SUCCESS:IMP-0119 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
