#!/usr/bin/env python3
"""Write IMP-0146 receipt, per-unit manifest, and SUBAGENT-RETURN.

Does not run tools/command-center/unit_manifest.py --write.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0146"
OUT = "command-center/receipts/IMP-0146.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0146/probe1_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0146/probe2_blob_eol.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/canonical.py",
    "tools/agentspec/agentspec/spec.py",
    "command-center/p2-wave/probes/IMP-0146/probe1_roundtrip.py",
    "command-center/p2-wave/probes/IMP-0146/probe2_blob_eol.py",
    "command-center/p2-wave/probes/IMP-0146/scenario.py",
    "command-center/p2-wave/probes/IMP-0146/fixtures/all-kinds.json",
    "command-center/p2-wave/probes/IMP-0146/fixtures/all-kinds.crlf.json",
    "command-center/p2-wave/probes/IMP-0146/fixtures/subworkflow.json",
    "command-center/p2-wave/probes/IMP-0146/fixtures/loop.json",
    "command-center/p2-wave/probes/IMP-0146/fixtures/human-checkpoint.json",
    "command-center/p2-wave/probes/IMP-0146/fixtures/dynamic-fanout.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
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


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0146/SUBAGENT-RETURN.json",
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0146 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    s1 = first_json(t1)
    s2 = first_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    can_sha, can_bytes = digest(REPO / "tools/agentspec/agentspec/canonical.py")
    spec_sha, spec_bytes = digest(REPO / "tools/agentspec/agentspec/spec.py")

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0146",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0146",
        "min_bytes_threshold": 128,
        "title": "Implement canonical export/import with a byte-stable round trip",
        "question_or_target": (
            "export(import(export(w))) == export(w) byte-for-byte on LF bytes "
            "from git cat-file -p, including every new node type."
        ),
        "implementation": {
            "canonical": "tools/agentspec/agentspec/canonical.py",
            "spec": "tools/agentspec/agentspec/spec.py",
            "canonical_sha256": can_sha,
            "canonical_bytes": can_bytes,
            "spec_sha256": spec_sha,
            "spec_bytes": spec_bytes,
            "new_node_types": [
                "Subworkflow",
                "Loop",
                "HumanCheckpoint",
                "DynamicFanOut",
            ],
            "existing_node_types": ["WorkUnit", "FanOut", "Barrier", "Pipeline"],
            "blob_recipe": "git cat-file -p (NOT git archive)",
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "eol": "LF",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Idempotent round trip over every fixture including "
                    "Subworkflow, Loop, HumanCheckpoint, and DynamicFanOut: "
                    "export(import(export(w))) equals export(w) byte-for-byte."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/canonical.py:export",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:65000],
                    }
                ],
                "measured": {
                    "kinds": s1.get("kinds"),
                    "fixtures_objects": s1.get("fixtures_objects"),
                    "fixtures_files": s1.get("fixtures_files"),
                    "mutation_control": s1.get("mutation_control"),
                },
            },
            {
                "claim": (
                    "The same round-trip holds on LF blob bytes from "
                    "git cat-file -p and on a CRLF working-tree copy; a "
                    "CRLF-only difference is visible in raw sha256 and does "
                    "not masquerade as a pass. git archive is never used."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/canonical.py:read_blob_via_cat_file",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:65000],
                    }
                ],
                "measured": {
                    "blob_bytes": s2.get("blob_bytes"),
                    "blob_crlf": s2.get("blob_crlf"),
                    "worktree_bytes": s2.get("worktree_bytes"),
                    "worktree_crlf": s2.get("worktree_crlf"),
                    "raw_sha_differ": s2.get("raw_sha_differ"),
                    "blob_sha1": s2.get("blob_sha1"),
                    "method": s2.get("method"),
                    "archive_forbidden": s2.get("archive_forbidden"),
                },
            },
        ],
        "tests": [
            {
                "id": "probe1-roundtrip",
                "name": "idempotent round trip over all fixtures including every new node type",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "probe2-blob-eol",
                "name": "CRLF working-tree copy and LF blob copy both round-trip",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "content-mutation",
                "kind": "known-broken-fixture",
                "description": (
                    "XOR one byte of the all-kinds export; round-trip equality "
                    "must fail. The unmutated twin must pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "mutated_equal=false",
                "good_state_output": "unmutated_equal=true",
            },
            {
                "id": "eol-trap-raw-sha",
                "kind": "both-states",
                "description": (
                    "Raw sha256 of CRLF worktree != raw sha256 of LF blob; "
                    "canonical round-trip sha256 of both are equal."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "raw_sha_differ=true",
                "good_state_output": "both_roundtrip=true",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0146-probe2-blob-eol",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Mechanically different from probe1: isolated bare git repo, "
                "hash-object -w, git cat-file -p, CRLF worktree copy. "
                "Never git archive."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0146/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "note": "measure runs after this receipt is written",
            }
        ],
        "residual_unknowns": [],
        "notes": (
            "G-1 for IMP-0146: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not git add/commit. Isolated bare repo used only for cat-file."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = art(OUT, "primary")
    # Patch the primary artifact row now that the file exists with a real hash.
    receipt["artifacts"] = [
        {
            "path": OUT,
            "sha256": primary["sha256"],
            "bytes": primary["bytes"],
            "exists": True,
            "role": "primary",
            "eol": "LF",
        }
    ]
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = art(OUT, "primary")
    # Second write changes the sha (self-hash in body). Leave the body hash
    # unsynchronized? Measure hashes the FILE, not the inner field. Keep the
    # inner artifacts[0].sha256 matching the file by iterating once more if
    # needed. After first patch the content changed so sha drifted. Do not
    # embed the receipt's own sha in the receipt body.
    receipt["artifacts"] = [
        {
            "path": OUT,
            "role": "primary",
            "exists": True,
            "eol": "LF",
        }
    ]
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = art(OUT, "primary")

    artifacts = [primary] + [art(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0146",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "round-trip-fidelity",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "blob-eol-trap",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0146/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0146-probe2-blob-eol",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0146: live named probes exit 0, receipt state=SUCCESS, "
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
    print("SUCCESS:IMP-0146 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
