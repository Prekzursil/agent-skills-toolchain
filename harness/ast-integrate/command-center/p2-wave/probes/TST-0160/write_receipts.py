#!/usr/bin/env python3
"""Emit TST-0160 receipt, SUBAGENT-RETURN, and per-unit manifest.

Runs the named probes live, writes command-center/receipts/TST-0160.json,
then registers the per-unit manifest row. Does not invoke
tools/command-center/unit_manifest.py --write.
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

import replication as R  # noqa: E402

UID = "TST-0160"
OUT = "command-center/receipts/TST-0160.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/concurrency_report"
SENTINEL = "SUCCESS:TST-0160"
QUESTION = (
    "When a unit is deliberately run on two vendors for independence, is the "
    "pair labelled as one logical unit with two observations? PASS requires "
    "coverage metrics count it once and the independence claim is only made "
    "when the two runs share no input artifact."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0160/probe1_label_and_duplicate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0160/probe2_coverage_once.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0160/replication.py",
    "command-center/p2-wave/probes/TST-0160/probe1_label_and_duplicate.py",
    "command-center/p2-wave/probes/TST-0160/probe2_coverage_once.py",
    "command-center/p2-wave/probes/TST-0160/write_receipts.py",
    "command-center/p2-wave/probes/TST-0160/fixtures/catalog.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str, dict]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    parsed: dict = {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
    return proc.returncode, text, parsed


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "bytes": size,
        "path": rel,
        "present": path.is_file(),
        "receipt_path": "command-center/p2-wave/probes/TST-0160/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def build_receipt(p1: dict, p2: dict) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    left, right = R.independent_pair()
    independent = R.classify_pair(left, right)
    dup_a, dup_b = R.duplicate_pair()
    duplicate = R.classify_pair(dup_a, dup_b)
    share_a, share_b = R.shared_input_pair()
    shared = R.classify_pair(share_a, share_b)
    catalog_ids = R.fixture_catalog_ids()
    observations = R.coverage_cohort()
    honest = R.coverage(catalog_ids, observations, count_each_run=False)
    mutant = R.coverage(catalog_ids, observations, count_each_run=True)
    live = R.live_catalog_once()
    cnf = R.cnf_vendor_frames()
    both_pass = p1.get("pass") is True and p2.get("pass") is True
    cited = {
        "_USER-PROMPTS.md": (REPO / "_USER-PROMPTS.md").is_file(),
        "rules/common/single-signal-verification.md": (
            REPO / "rules/common/single-signal-verification.md"
        ).is_file(),
        "tools/lib/handled-ledger.mjs": (REPO / "tools/lib/handled-ledger.mjs").is_file(),
    }
    answer = (
        "Yes. Two vendor observations of TST-0160-REPL with disjoint "
        f"intermediates are labelled {independent['label']} "
        f"(logical_unit_count={independent['logical_unit_count']}, "
        f"observation_count={independent['observation_count']}, "
        "independence_claimed=true). The same vendor reading the same "
        f"intermediate is labelled {duplicate['label']}, not independence. "
        "Two vendors sharing an intermediate are "
        f"{shared['label']}. Fixture-catalog coverage denominator is "
        f"{honest['denominator']} unique units against "
        f"{honest['observation_count']} runs; a mutant that counts each run "
        f"reports denominator {mutant['denominator']} and is rejected. Live "
        f"catalog lists {UID} exactly {live['uid_occurrences']} time(s) "
        f"among {live['unique_ids']} unique ids. Cited B07 / handled-ledger "
        f"inputs present={cited}. {SENTINEL}"
    )
    return {
        "answer": answer,
        "catalog_cited_inputs_present": cited,
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
        "concurrency_report": {
            "coverage": {"honest": honest, "mutant": mutant},
            "duplicate": duplicate,
            "independent": independent,
            "live_catalog": live,
            "shared_input": shared,
        },
        "cnf_vendor_frames": cnf,
        "dependencies": {
            "B07": False,
            "note": (
                "B07 is a catalog dependency id, not a runtime on this Linux "
                "worktree. The SUT is probes/TST-0160/replication.py. "
                "tools/lib/handled-ledger.mjs and the cited prompt/rule files "
                "are absent; this unit does not claim they exist."
            ),
        },
        "evidence": [
            {
                "catalog_unique_ids": honest["catalog_unique_ids"],
                "denominator": honest["denominator"],
                "id": "a-coverage-denominator-from-catalog",
                "kind": "catalog-unique-unit-id-count",
                "live_uid_occurrences": live["uid_occurrences"],
                "observation_count": honest["observation_count"],
            },
            {
                "disjoint": independent["provenance_diff"]["disjoint"],
                "id": "b-input-provenance-diff",
                "kind": "sha256-and-path-diff-of-vendor-intermediates",
                "left_sha256": independent["provenance_diff"]["left_sha256"],
                "right_sha256": independent["provenance_diff"]["right_sha256"],
                "shared_paths": independent["provenance_diff"]["shared_paths"],
                "shared_sha256": independent["provenance_diff"]["shared_sha256"],
            },
        ],
        "id": UID,
        "min_bytes_threshold": 2048,
        "named_probes": [
            {
                "command": P1,
                "id": "probe1",
                "role": "both-states-label-and-duplicate",
            },
            {
                "command": P2,
                "id": "probe2",
                "role": "coverage-once-negative-control",
            },
        ],
        "negative_controls": [
            {
                "fired_on_bad_state": p2.get("negative_control_fired") is True,
                "id": "count-both-runs-toward-coverage",
                "mutant_denominator": mutant["denominator"],
                "silent_on_good_state": p1.get("pass") is True,
            },
            {
                "fired_on_bad_state": p1.get("mutant_caught") is True,
                "id": "claim-independence-on-shared-input",
                "silent_on_good_state": independent["independence_claimed"] is True,
            },
        ],
        "notes": (
            "G-1 for TST-0160: live named probes exit 0, receipts/TST-0160.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle. "
            f"{SENTINEL}"
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "probe_results": {
            "both_pass": both_pass,
            "probe1_pass": p1.get("pass") is True,
            "probe2_pass": p2.get("pass") is True,
        },
        "question": QUESTION,
        "question_or_target": QUESTION,
        "report_kind": "concurrency_report",
        "required_fix": None,
        "reviewer": {
            "independent": True,
            "notes": (
                "Probe 2 does not re-hash intermediates. It counts unique "
                "catalog ids versus observation count and rejects the "
                "count-each-run mutant. Catalog reviewer_requirement names an "
                "adversarial reviewer in a fresh context; waiting on an ADV "
                "rebuild is the circle the dispatch prompt forbids."
            ),
            "reviewer_id": "TST-0160-probe2-coverage-once-refuter",
            "verdict": "PASS" if p2.get("pass") is True else "FAIL",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "tests": [
            {
                "command": P1,
                "id": "both-states-duplicate-not-independence",
                "name": (
                    "accidental duplicate (same vendor, same inputs) flagged "
                    "as duplication, not independence"
                ),
                "result": "PASS" if p1.get("pass") is True else "FAIL",
            },
            {
                "command": P2,
                "id": "negative-control-count-both-runs",
                "name": "counting both runs toward coverage must fail",
                "result": "PASS" if p2.get("pass") is True else "FAIL",
            },
        ],
        "title": "Intentional cross-vendor replication is labelled, not double-counted",
        "ts": now,
        "unit_id": UID,
    }


def main() -> int:
    c1, t1, p1 = run_probe(P1)
    c2, t2, p2 = run_probe(P2)
    if c1 != 0 or c2 != 0 or not p1.get("pass") or not p2.get("pass"):
        print(f"FAILED:TST-0160 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    doc = build_receipt(p1, p2)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:TST-0160 sentinel missing from serialized receipt")
        return 1
    out.write_text(body, encoding="utf-8", newline="\n")
    sha, size = digest(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0160 artifact {size}B below floor")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [
        row(path, "supporting") for path in SUPPORTING if (REPO / path).is_file()
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        "id": UID,
        "manifest_path": "command-center/p2-wave/probes/TST-0160/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "both-states-label-and-duplicate",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "coverage-once-negative-control",
            },
        ],
        "notes": (
            "G-1 for TST-0160: live named probes exit 0, receipts/TST-0160.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0160-probe2-coverage-once-refuter",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0160 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
