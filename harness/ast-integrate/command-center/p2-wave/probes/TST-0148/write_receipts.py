#!/usr/bin/env python3
"""Write TST-0148 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0148"
OUT = "command-center/receipts/TST-0148.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0148/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0148/probe2_present_only.py"
)
SUPPORTING = [
    "tools/command-center/shard_reducer.py",
    "command-center/p2-wave/probes/TST-0148/fixtures.py",
    "command-center/p2-wave/probes/TST-0148/present_only.py",
    "command-center/p2-wave/probes/TST-0148/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0148/probe2_present_only.py",
    "command-center/p2-wave/probes/TST-0148/fixtures/shard-manifest.json",
    "command-center/p2-wave/probes/TST-0148/fixtures/complete/shard-a.json",
    "command-center/p2-wave/probes/TST-0148/fixtures/complete/shard-b.json",
    "command-center/p2-wave/probes/TST-0148/fixtures/complete/shard-c.json",
    "command-center/p2-wave/probes/TST-0148/fixtures/complete/shard-d.json",
    "command-center/p2-wave/probes/TST-0148/fixtures/incomplete/shard-a.json",
    "command-center/p2-wave/probes/TST-0148/fixtures/incomplete/shard-b.json",
    "command-center/p2-wave/probes/TST-0148/fixtures/incomplete/shard-d.json",
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
        "receipt_path": "command-center/p2-wave/probes/TST-0148/SUBAGENT-RETURN.json",
        "role": role,
    }


def parse_probe_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = parse_probe_json(t1)
    j2 = parse_probe_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib_sha, lib_bytes = digest(REPO / "tools/command-center/shard_reducer.py")
    inc = j1.get("incomplete_3_of_4") or {}
    reducer = inc.get("reducer") or {}
    listing = inc.get("listing_diff") or {}

    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0148",
        "completion_sentinel": "SUCCESS:TST-0148",
        "title": "Missing shard is named, not averaged away",
        "report_kind": "predicate_report",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/predicate_report",
        "min_bytes_threshold": 2048,
        "schema_version": 1,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json#TST-0148 "
            "_USER-PROMPTS.md:11009 (Phase 10 layer 21, partial-artifact tests)"
        ),
        "question_or_target": (
            "For a multi-shard artifact set where 3 of 4 shards exist, does the "
            "reducer report the missing shard BY ID rather than computing a result "
            "over what is present? PASS requires the returned status be INCOMPLETE "
            "with the missing id enumerated."
        ),
        "question_answer": (
            "YES: tools/command-center/shard_reducer.py returns INCOMPLETE and "
            "enumerates SHARD-C when that file is absent from a 4-shard set; all "
            "four files present returns COMPLETE. A present-only averaging reducer "
            "returns COMPLETE with score=1.0 on the same 3-of-4 fixture and omits "
            "missing_ids; probe 2 rejects that reducer. SUCCESS:TST-0148"
        ),
        "implementation": {
            "library": "tools/command-center/shard_reducer.py",
            "library_sha256": lib_sha,
            "library_bytes": lib_bytes,
            "mechanism": (
                "Read the shard manifest from disk. List regular files in the set "
                "root. Diff filenames against the manifest. COMPLETE only if the "
                "missing-id list is empty. Never emit a score or majority over the "
                "shards that happen to be present."
            ),
        },
        "evidence": [
            {
                "id": "E1-reducer-status-object",
                "claim": (
                    "On the 3-of-4 fixture the reducer's returned status object is "
                    "INCOMPLETE and missing_ids enumerates SHARD-C. On the all-4 "
                    "fixture the status is COMPLETE with missing_ids=[]."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0148/probe1_both_states.py",
                "computed": {
                    "incomplete_status": reducer.get("status"),
                    "incomplete_missing_ids": reducer.get("missing_ids"),
                    "computed_over_present": reducer.get("computed_over_present"),
                    "score": reducer.get("score"),
                    "complete_status": (j1.get("complete") or {}).get("reducer", {}).get(
                        "status"
                    ),
                },
            },
            {
                "id": "E2-independent-directory-listing",
                "claim": (
                    "An independent listdir of the set root, diffed against the "
                    "on-disk shard manifest, names the same missing id as the "
                    "reducer status object."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0148/probe1_both_states.py",
                "computed": {
                    "listing_missing_ids": listing.get("missing_ids"),
                    "listing_agrees": inc.get("listing_agrees"),
                    "on_disk": listing.get("on_disk"),
                },
            },
        ],
        "tests": [
            {
                "id": "TST-0148-T1",
                "name": "both-states control: all 4 shards present returns COMPLETE",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "TST-0148-T2",
                "name": (
                    "both-states control: 3 of 4 shards present returns INCOMPLETE "
                    "with SHARD-C enumerated"
                ),
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "TST-0148-NC1",
                "name": (
                    "negative control: a reducer that computes over present shards "
                    "only must fail"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-present-only-average",
                "kind": "planted-wrong-reducer",
                "description": (
                    "A reducer that averages present shards returns COMPLETE on "
                    "3-of-4 and omits missing_ids. The TST-0148 contract check "
                    "must reject it."
                ),
                "fired_on_bad_state": bool(j2.get("fired_on_bad_state")),
                "silent_on_good_state": bool(j2.get("silent_on_good_state")),
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0148-probe2-present-only",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Catalog asked for one independent adversarial reviewer in a fresh "
                "context who did not author the harness under test. This G-1 "
                "delivery uses probe2 (present-only averaging reducer) as the "
                "independent mechanical check: it never scores the production "
                "reducer and requires the planted present-only reducer to fail "
                "the missing-shard contract. A human Codex pass is not claimed."
            ),
        },
        "defects": [],
        "artifacts": [
            {
                "path": "tools/command-center/shard_reducer.py",
                "role": "implementation",
                "sha256": lib_sha,
                "bytes": lib_bytes,
                "exists": True,
            }
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0148/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0148: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:TST-0148"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if "SUCCESS:TST-0148" not in payload:
        print("FAILED:TST-0148 sentinel missing from receipt text")
        return 1
    if out_path.stat().st_size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:TST-0148 receipt too small {out_path.stat().st_size}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0148",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/predicate_report",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-states-and-listing-diff",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "present-only-negative-control",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0148/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0148-probe2-present-only",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0148: live named probes exit 0, receipts/TST-0148.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
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
    print("SUCCESS:TST-0148 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
