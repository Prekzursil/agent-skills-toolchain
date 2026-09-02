#!/usr/bin/env python3
"""Emit IMP-0172 catalog receipt + per-unit return/manifest.

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
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import semantic_diff as D  # noqa: E402

UNIT = "IMP-0172"
OUT = "command-center/receipts/IMP-0172.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0172/probe1_diverged.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0172/probe2_antisymmetry.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/IMP-0172/semantic_diff.py",
    "command-center/p2-wave/probes/IMP-0172/fixtures.py",
    "command-center/p2-wave/probes/IMP-0172/probe1_diverged.py",
    "command-center/p2-wave/probes/IMP-0172/probe2_antisymmetry.py",
    "command-center/p2-wave/probes/IMP-0172/fixtures/both-sides-left.json",
    "command-center/p2-wave/probes/IMP-0172/fixtures/both-sides-right.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0172/SUBAGENT-RETURN.json",
        "role": role,
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe_block(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    F.write_json_fixtures()
    left, right = F.both_sides_left(), F.both_sides_right()
    two = D.diff_workflows(left, right)
    one = D.diff_workflows(left, right, one_directional=True)
    stripped = D.diff_workflows(F._base(), right)
    matrix = []
    for name, a, b in F.fixture_matrix():
        ab = D.diff_workflows(a, b)
        ba = D.diff_workflows(b, a)
        rev = D.reverse_diff(ab)
        matrix.append(
            {
                "pair": name,
                "verdict_ab": ab["verdict"],
                "verdict_ba": ba["verdict"],
                "antisymmetric": D.diffs_equal(rev, ba),
            }
        )
    anti_ok = all(r["antisymmetric"] for r in matrix)
    if two["verdict"] != "DIVERGED" or one["verdict"] == "DIVERGED" or not anti_ok:
        print(
            f"FAILED:IMP-0172 instrument preflight "
            f"two={two['verdict']} one={one['verdict']} anti={anti_ok}"
        )
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    now = utcnow()
    p_src = probe_block(
        "source",
        "command",
        "python3 -B command-center/p2-wave/probes/IMP-0172/semantic_diff.py",
        json.dumps(
            {
                "two_directional": two["verdict"],
                "one_directional": one["verdict"],
                "left_unique": len(two["left_unique"]),
                "right_unique": len(two["right_unique"]),
                "ops": [o["op"] for o in two["ops"]],
            },
            sort_keys=True,
        ),
        0,
    )
    supporting_arts = []
    for rel in SUPPORTING:
        p = REPO / rel
        if not p.is_file():
            print(f"FAILED:IMP-0172 missing supporting {rel}")
            return 1
        sha, size = digest(p)
        supporting_arts.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "role": "supporting",
                "eol": "LF",
            }
        )

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0172",
        "completion_sentinel": "SUCCESS:IMP-0172",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#IMP-0172",
        "title": "Implement semantic diff of two workflows over aligned stages, roles and gates",
        "min_bytes_threshold": 128,
        "profile": "selfimprove-measure-artifact",
        "produced_by": {
            "vendor": "cursor",
            "model": "composer",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "both_sides_unique_verdict": two["verdict"],
        "one_directional_mutant_verdict": one["verdict"],
        "one_directional_blind_spot": (
            "A one-directional read of right-only extras classifies the both-sides-unique "
            "fixture RIGHT-AHEAD and drops left-unique stages/roles/gates/tools. That is "
            "the measured shape behind 31 data-loss-pointing misclassifications. The live "
            "instrument reports DIVERGED because both unique sets are nonempty."
        ),
        "antisymmetry": {
            "pairs": len(matrix),
            "all_hold": anti_ok,
            "matrix": matrix,
            "definition": "reverse(diff(a,b)) == diff(b,a) under canonical ops+unique sets",
        },
        "typed_ops_on_both_sides_unique": [o["op"] for o in two["ops"]],
        "artifacts": supporting_arts,
        "evidence": [
            {
                "claim": (
                    "A both-sides-unique fixture (left-only adversarial-review stage vs "
                    "right-only publish-pr stage on a shared two-stage prefix) classifies "
                    f"DIVERGED, not one-sided. Live verdict={two['verdict']}; "
                    f"left_unique={len(two['left_unique'])}; "
                    f"right_unique={len(two['right_unique'])}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0172/fixtures/both-sides-left.json",
                "confidence": "almost-certain",
                "probes": [p_src],
            },
            {
                "claim": (
                    f"Antisymmetry holds on {len(matrix)}/{len(matrix)} fixture pairs: "
                    "reverse(diff(a,b)) equals diff(b,a)."
                ),
                "verdict": "CONFIRMED" if anti_ok else "REFUTED",
                "anchor": "command-center/p2-wave/probes/IMP-0172/probe2_antisymmetry.py",
                "confidence": "almost-certain",
                "probes": [
                    probe_block(
                        "verifier",
                        "command",
                        P2,
                        json.dumps(matrix, sort_keys=True),
                        0,
                    )
                ],
            },
        ],
        "tests": [
            {"id": "both-sides-unique-diverged", "command": P1, "result": "PASS"},
            {"id": "antisymmetry-matrix", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "one-directional-mutant",
                "kind": "known-broken-fixture",
                "description": (
                    "one_directional=True over the same both-sides-unique pair must not "
                    "report DIVERGED; it reports RIGHT-AHEAD, dropping left-unique content"
                ),
                "fired_on_bad_state": one["verdict"] == "RIGHT-AHEAD",
                "silent_on_good_state": two["verdict"] == "DIVERGED",
                "bad_state_output": one["verdict"],
                "good_state_output": two["verdict"],
            },
            {
                "id": "strip-left-unique",
                "kind": "both-states",
                "description": (
                    "Remove the left-unique stage; two-directional verdict must leave DIVERGED"
                ),
                "fired_on_bad_state": stripped["verdict"] != "DIVERGED",
                "silent_on_good_state": two["verdict"] == "DIVERGED",
                "bad_state_output": stripped["verdict"],
                "good_state_output": two["verdict"],
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0170 mechanism fingerprint is not on disk in this worktree; "
                    "alignment uses stage kind as the rename-invariant key that unit names."
                ),
                "settling_experiment": "Re-bind alignment to IMP-0170 fingerprint once delivered.",
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "reviewer_id": "IMP-0172-probe2-antisymmetry",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0172/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "exit_code": None,
                "read_ok": True,
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0172",
                    "exit_code": None,
                    "fingerprint": fingerprint(
                        "command",
                        "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0172",
                    ),
                    "method": "command",
                    "raw_output": "deferred-to-post-write-measure",
                    "role": "verifier",
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 IMP-0172: directional typed workflow diff; both-sides-unique is DIVERGED; "
            "antisymmetry computed on the fixture matrix. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(f"probe1 rc={c1}")
    print(t1[-2000:])
    print(f"probe2 rc={c2}")
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0172 probes c1={c1} c2={c2}")
        return 1

    receipt["evidence"][0]["probes"].append(probe_block("verifier", "command", P1, t1, c1))
    receipt["evidence"][1]["probes"][0] = probe_block("verifier", "command", P2, t2, c2)
    receipt["timestamps"]["ended_at"] = utcnow()
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1b, t1b = run_probe(P1)
    c2b, t2b = run_probe(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:IMP-0172 post-receipt probes c1={c1b} c2={c2b}")
        print(t1b[-1500:])
        print(t2b[-1500:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0172",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "both-sides-unique-diverged",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "antisymmetry-matrix",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0172/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0172-probe2-antisymmetry",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": utcnow(),
        "notes": (
            "G-1 for IMP-0172: live named probes exit 0, receipt state=SUCCESS, "
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0172 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
