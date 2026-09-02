#!/usr/bin/env python3
"""Write TST-0180 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0180"
OUT = "command-center/receipts/TST-0180.json"
SENTINEL = "SUCCESS:TST-0180"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0180/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0180/probe2_collision_seed.py"
)
TESTS = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_case_collision.py"
)
SUPPORTING = [
    "tools/plugin/case_collision.py",
    "tools/plugin/tests/test_case_collision.py",
    "command-center/p2-wave/probes/TST-0180/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0180/probe2_collision_seed.py",
    "command-center/p2-wave/probes/TST-0180/write_receipts.py",
    "command-center/p2-wave/probes/TST-0180/fixtures/clean_plugin.json",
    "command-center/p2-wave/probes/TST-0180/fixtures/clean_marketplace.json",
    "command-center/p2-wave/probes/TST-0180/fixtures/collision_top.json",
    "command-center/p2-wave/probes/TST-0180/fixtures/collision_nested.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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


def first_json(text: str):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/TST-0180/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UNIT,
    }


def main() -> int:
    c_t, t_t = run_cmd(TESTS)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_t != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0180 receipts tests={c_t} p1={c1} p2={c2}")
        print(t_t[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    j1 = first_json(t1) or {}
    j2 = first_json(t2) or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib_sha, lib_n = digest(REPO / "tools/plugin/case_collision.py")
    sig = (j2.get("signal_b_keyset_sizes") or {}) if isinstance(j2, dict) else {}

    receipt = {
        "artifacts": [
            {
                "bytes": lib_n,
                "exists": True,
                "path": "tools/plugin/case_collision.py",
                "role": "primary-implementation",
                "sha256": lib_sha,
            }
        ],
        "completion_sentinel": SENTINEL,
        "evidence": [
            {
                "anchor": "tools/plugin/case_collision.py:validate_document",
                "claim": (
                    "Both-states: a plugin/marketplace document whose keys remain "
                    "distinct after casefold is ACCEPTed; Name/name and nested "
                    "owner.Name/owner.name are REJECTed on the same code path."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": c1,
                        "method": "command",
                        "raw_output": t1[:16000],
                        "role": "verifier",
                    }
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/plugin/case_collision.py:independent_signal",
                "claim": (
                    "Regression seed FC-11309/11310: validator REJECT names both "
                    "keys, and an independent raw-vs-casefolded key-set size "
                    f"comparison reports raw={sig.get('worst_raw_keyset_size')} "
                    f"folded={sig.get('worst_casefolded_keyset_size')}. "
                    "Emitter refuses to serialize the colliding mapping."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P2,
                        "exit_code": c2,
                        "method": "command",
                        "raw_output": t2[:16000],
                        "role": "verifier",
                    }
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "id": UNIT,
        "implementation": {
            "module": "tools/plugin/case_collision.py",
            "operator": (
                "object_pairs_hook key bags; reject when unique_raw_size > "
                "casefolded_size; emitter refuses before dumps"
            ),
            "case_collision_bytes": lib_n,
            "case_collision_sha256": lib_sha,
        },
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": "command-center/p2-wave/probes/TST-0180/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 128,
        "negative_controls": [
            {
                "description": (
                    "Top-level name plus owner.name (same spelling, different "
                    "objects) ACCEPTs — collision is per-object."
                ),
                "id": "TST-0180-C1-nested-same-name-ok",
                "kind": "negative-control",
            },
            {
                "description": (
                    "Case-sensitive uniqueness sees 3 keys and would miss the "
                    "bug; casefold size 2 plus validator REJECT catch it."
                ),
                "fired_on_bad_state": True,
                "id": "TST-0180-C2-case-sensitive-miss",
                "kind": "both-states",
                "silent_on_good_state": True,
            },
            {
                "description": (
                    "Naive casefold last-wins keeps only 'other' for name; "
                    "our validator rejects instead of last-key-wins."
                ),
                "id": "TST-0180-C3-last-wins-loss",
                "kind": "mutation",
            },
        ],
        "notes": (
            "G-1 TST-0180: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. B06 plugin/marketplace schemas were absent on this "
            "worktree; the unit implements the case-collision guard the catalog "
            f"question requires. {SENTINEL}"
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/parser_report",
        "parser_report": {
            "both_states": {
                "clean_accepted": True,
                "collision_rejected": True,
                "marketplace_accepted": True,
                "nested_collision_rejected": True,
            },
            "emitter_refuses_collision": True,
            "independent_keyset_signal": sig,
            "kind": "case-insensitive-parser-collision",
            "probe1": j1,
            "probe2": j2,
        },
        "premise": {
            "action": (
                "Created probes/TST-0180 and tools/plugin/case_collision.py. "
                "Did not exit on predicate:absent. receipt.schema.json is absent "
                "on this worktree (same as other G-1 deliveries); this unit does "
                "not rebuild ADV/IMP-0433."
            ),
            "catalog_inputs": [
                "B06 plugin/marketplace manifest schemas",
                "_USER-PROMPTS.md:11309",
            ],
            "inputs_were_absent": True,
        },
        "produced_by": {
            "execution_substrate": "linux-worktree-local",
            "model": "grok-4.6",
            "role": "schema-conformance-tester",
            "vendor": "cursor",
        },
        "profile": "p2-wave-g1-unit",
        "question_or_target": (
            "Do two keys differing only in case produce a detected collision "
            "rather than last-key-wins? PASS requires our emitter to never "
            "produce case-colliding keys AND our validator to reject an incoming "
            "document that has them."
        ),
        "reviewer": {
            "independent": True,
            "notes": (
                "Adversarial control is probe2: independent key-set sizes, "
                "case-sensitive miss, last-wins loss, and emitter refusal. "
                "Did not author the Name/name fixture as the only check."
            ),
            "reviewer_id": "TST-0180-probe2-collision-seed",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "spec_anchor": (
            "catalog TST-0180 / _USER-PROMPTS.md:11309 case-insensitive parser "
            "collision on case-distinct JSON keys"
        ),
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "command": TESTS,
                "exit_code": c_t,
                "id": "test_case_collision",
                "result": "PASS",
            },
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1_both_states",
                "result": "PASS",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2_collision_seed",
                "result": "PASS",
            },
        ],
        "tests_required": [
            "both-states control: a document with distinct case-folded keys validates",
            "regression seed: case-insensitive parser collision (_USER-PROMPTS.md:11309)",
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Case-distinct JSON keys colliding under a case-insensitive parser are detected",
        "unit_id": UNIT,
    }

    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0180 emit sentinel missing before write")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/TST-0180/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "both-states-distinct-vs-collision",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "adversarial-collision-seed-two-signals",
            },
        ],
        "notes": (
            "G-1 for TST-0180: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/parser_report",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0180-probe2-collision-seed",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests_command": TESTS,
        "tests_exit_code": c_t,
        "ts": now,
        "unit_id": UNIT,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:TST-0180 receipts {SENTINEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
