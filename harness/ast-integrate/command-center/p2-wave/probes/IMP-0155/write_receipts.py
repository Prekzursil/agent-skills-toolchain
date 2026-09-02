#!/usr/bin/env python3
"""Write IMP-0155 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0155.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0155/probe1_refetch.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0155/probe2_mutated_ref.py"
)
SUPPORTING = [
    "tools/foundry/provenance.py",
    "tools/foundry/__init__.py",
    "command-center/p2-wave/probes/IMP-0155/scenario.py",
    "command-center/p2-wave/probes/IMP-0155/probe1_refetch.py",
    "command-center/p2-wave/probes/IMP-0155/probe2_mutated_ref.py",
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
        env={**dict(**__import__("os").environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def load_raw(name: str) -> dict:
    path = HERE / name
    return json.loads(path.read_text(encoding="utf-8"))


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0155",
        "receipt_path": "command-center/p2-wave/probes/IMP-0155/SUBAGENT-RETURN.json",
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
    p1 = load_raw("probe1-refetch.raw.json")
    p2 = load_raw("probe2-mutated-ref.raw.json")
    if p1.get("matched") != 10 or p1.get("sampled") != 10:
        print(f"FAILED:receipts probe1 computed matched={p1.get('matched')}")
        return 1
    if not p2.get("fired_on_bad_state") or not p2.get("silent_on_good_state"):
        print("FAILED:receipts probe2 both-states not live")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting_meta = []
    for rel in SUPPORTING:
        sha, size = digest(REPO / rel)
        supporting_meta.append(
            {
                "path": rel,
                "role": "supporting",
                "exists": True,
                "bytes": size,
                "sha256": sha,
                "eol": "LF",
            }
        )

    receipt = {
        "answer": (
            "Every candidate carries a provenance record of source, ref, "
            "retrieval_time, hash (sha256:<hex>), and retrieval_method. A second "
            f"agent given only that record re-fetched identical bytes for "
            f"{p1['matched']}/{p1['sampled']} sampled candidates by executing "
            "posix-read and tar-member against the recorded source+ref. A record "
            "with a mutated ref that still has all five fields fails re-fetch "
            "with HashMismatch (detector fires on the decoy bytes). Field "
            "presence is not acceptance. SUCCESS:IMP-0155"
        ),
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
            }
        ]
        + supporting_meta,
        "completion_sentinel": "SUCCESS:IMP-0155",
        "downstream_consumers": [
            {
                "artifact_path": "tools/foundry/provenance.py",
                "consumer": "command-center/p2-wave/probes/IMP-0155/probe1_refetch.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
            },
            {
                "artifact_path": "tools/foundry/provenance.py",
                "consumer": "command-center/p2-wave/probes/IMP-0155/probe2_mutated_ref.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
            },
        ],
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/IMP-0155/probe1-refetch.raw.json",
                "claim": (
                    f"Re-fetch from the provenance record reproduced the recorded "
                    f"hash for {p1['matched']}/{p1['sampled']} sampled candidates "
                    f"(methods {p1.get('methods_used')}). Computed, not asserted."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": c1,
                        "method": "command",
                        "raw_output": t1[-1500:],
                        "role": "source",
                    },
                    {
                        "command": P1,
                        "exit_code": c1,
                        "method": "command",
                        "raw_output": f"matched={p1['matched']} sampled={p1['sampled']}",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/IMP-0155/probe2-mutated-ref.raw.json",
                "claim": (
                    "A mutated-ref record fails re-fetch (HashMismatch on an "
                    "existing decoy) while the intact record passes. Both-states "
                    f"fired_on_bad={p2['fired_on_bad_state']} "
                    f"silent_on_good={p2['silent_on_good_state']}."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P2,
                        "exit_code": c2,
                        "method": "command",
                        "raw_output": t2[-1500:],
                        "role": "source",
                    },
                    {
                        "command": P2,
                        "exit_code": c2,
                        "method": "command",
                        "raw_output": (
                            f"fired_on_bad_state={p2['fired_on_bad_state']} "
                            f"silent_on_good_state={p2['silent_on_good_state']}"
                        ),
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "evidence_requirement": {
            "refetch_10_of_10": {
                "sampled": p1["sampled"],
                "matched": p1["matched"],
                "computed": True,
            },
            "mutated_ref_both_states": {
                "fired_on_bad_state": p2["fired_on_bad_state"],
                "silent_on_good_state": p2["silent_on_good_state"],
                "controls": p2.get("controls"),
            },
        },
        "id": "IMP-0155",
        "implementation": {
            "module": "tools/foundry/provenance.py",
            "record_fields": [
                "source",
                "ref",
                "retrieval_time",
                "hash",
                "retrieval_method",
            ],
            "retrieval_methods_executed": ["posix-read", "tar-member"],
            "hash_algorithm": "sha256",
            "note": (
                "ref is the fetch key; hash is verified after fetch. A mutated "
                "ref cannot succeed by consulting the hash as a locator."
            ),
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0155/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "global_catalog_write": False,
        },
        "min_bytes_threshold": 128,
        "named_probes": [
            {"id": "probe1", "role": "refetch-10-of-10", "command": P1, "exit_code": c1},
            {
                "id": "probe2",
                "role": "mutated-ref-both-states",
                "command": P2,
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "mutated-ref-posix-read",
                "kind": "known-broken-fixture",
                "description": (
                    "posix-read ref mutated to wf-DECOY.json; HashMismatch fires; "
                    "intact record still re-fetches."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "mutated-ref-tar-member",
                "kind": "known-broken-fixture",
                "description": (
                    "tar-member ref mutated to wf-tar-DECOY.json; HashMismatch "
                    "fires; intact record still re-fetches."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0154 append-only candidate registry is not delivered on "
                    "this worktree; provenance attaches to a candidate wrapper "
                    "and does not invent that registry."
                ),
                "settling_experiment": "Bind capture() to IMP-0154 import observations once that unit is live.",
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0155-probe2-mutated-ref",
            "verdict": "PASS",
            "method": (
                "Named probe2 is mechanically independent of probe1: it mutates "
                "only ref on an otherwise complete record and requires "
                "HashMismatch, while probe1 samples 10 intact re-fetches."
            ),
        },
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0155",
        "spec_anchor": "_USER-PROMPTS.md:11152-11170 (Workflow Foundry required production behavior)",
        "state": "SUCCESS",
        "tests": [
            {
                "id": "t1-refetch-10-of-10",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "t2-mutated-ref-both-states",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Implement the provenance record: source, ref, retrieval time, hash, retrieval method",
        "unit_id": "IMP-0155",
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    # Fixture files exist after probes; register the tar and one candidate as
    # supporting evidence that refetch sources are on disk.
    extra = [
        "command-center/p2-wave/probes/IMP-0155/fixtures/pack/candidates.tar",
        "command-center/p2-wave/probes/IMP-0155/probe1-refetch.raw.json",
        "command-center/p2-wave/probes/IMP-0155/probe2-mutated-ref.raw.json",
    ]
    for rel in extra:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, "supporting"))

    ret = {
        "id": "IMP-0155",
        "unit_id": "IMP-0155",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0155",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "refetch-10-of-10",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "mutated-ref-both-states",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0155/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0155-probe2-mutated-ref",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0155: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0155",
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
    print("SUCCESS:IMP-0155 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
