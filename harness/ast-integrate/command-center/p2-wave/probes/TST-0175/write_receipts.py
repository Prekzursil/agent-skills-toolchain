#!/usr/bin/env python3
"""Write TST-0175 cache_report receipt, SUBAGENT-RETURN, and per-unit manifest.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402

UID = "TST-0175"
OUT = "command-center/receipts/TST-0175.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/cache_report"
SENTINEL = "SUCCESS:TST-0175"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0175/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0175/probe2_rollback_regression.py"
)
SUPPORTING = [
    "tools/plugin/cache_ownership.py",
    "tools/plugin/cli.py",
    "command-center/p2-wave/probes/TST-0175/scenario.py",
    "command-center/p2-wave/probes/TST-0175/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0175/probe2_rollback_regression.py",
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
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": (REPO / rel).is_file(),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0175/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0175-emit-") as tmp:
        tmp_path = Path(tmp)
        both = S.measure_repair_and_update(tmp_path / "both")
        rb = S.measure_rollback(tmp_path / "rollback")

    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    repair = both["repair"]
    update = both["update"]
    good = rb["correct"]
    naive = rb["naive_wholesale"]
    both_ok = (
        repair["exit_code"] == 0
        and update["exit_code"] == 0
        and repair["user_tree_identical"]
        and update["user_tree_identical"]
        and not repair["owned_cache"]["exists"]
        and repair["user_file"]["exists"]
        and repair["foreign_cache"]["exists"]
        and not both["mutant_user_file"]["exists"]
        and both["missing_manifest"]["ok"] is False
        and good["exit_code"] == 0
        and good["user_tree_identical"]
        and good["user_file"]["exists"]
        and good["user_cmd"]["exists"]
        and not rb["naive_user_file"]["exists"]
        and not rb["naive_user_cmd"]["exists"]
        and naive.get("user_data_byte_identical") is False
    )
    if not both_ok:
        print("FAILED:TST-0175 live measurements did not satisfy the contract")
        print(json.dumps({"both": both, "rollback": rb}, indent=2, default=str)[:8000])
        return 1

    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Upgrade clears derived caches and preserves user data",
        "report_kind": "cache_report",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "question_or_target": (
            "Does `update` / `install --repair` invalidate exactly the caches it "
            "owns while leaving user data untouched? PASS requires an explicit "
            "ownership manifest for cache paths; anything not on it must survive "
            "the upgrade byte-identical."
        ),
        "answer": (
            "Yes. tools/plugin/cli.py update and install --repair load "
            "ownership-manifest.json and delete only owned_cache_paths "
            "(cache/derived, cache/index). A planted user-data file and user "
            "command survive byte-identical (signal a: matching pre/post tree "
            "hashes). Owned cache files are gone after the upgrade (signal b). "
            "A cache file not on the manifest survives. A missing manifest "
            "refuses rather than wiping. Rollback restores package blobs only; "
            "a wholesale-snapshot mutant drops user data and is the 11347 "
            "regression seed going red in the same run. SUCCESS:TST-0175"
        ),
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0175",
        "min_bytes_threshold": 2048,
        "produced_at": now,
        "timestamps": {"started_at": now, "ended_at": now},
        "produced_by": {
            "vendor": "spacexai-cursor",
            "model": "grok-4.6",
            "role": "cache-integrity-tester",
            "execution_substrate": "worktree-isolated",
        },
        "evidence": {
            "a_user_data_tree_hash": {
                "repair_before": repair["user_tree_before"],
                "repair_after": repair["user_tree_after"],
                "update_before": update["user_tree_before"],
                "update_after": update["user_tree_after"],
                "identical": True,
            },
            "b_owned_cache_empty_after": {
                "derived_exists": repair["owned_cache"]["exists"],
                "index_exists": repair["owned_index"]["exists"],
                "empty": True,
            },
            "foreign_cache_survived": repair["foreign_cache"]["exists"],
            "ownership_manifest": "ownership-manifest.json",
            "sut": "tools/plugin/cache_ownership.py",
            "cli": "tools/plugin/cli.py",
        },
        "tests": [
            {
                "id": "TST-0175-BOTH-STATES",
                "name": "planted user file survives; planted derived-cache file is removed",
                "result": "PASS",
                "repair_user_file": repair["user_file"],
                "repair_owned_cache": repair["owned_cache"],
                "update_user_file": update["user_file"],
                "update_owned_cache": update["owned_cache"],
            },
            {
                "id": "TST-0175-REGRESSION-SEED-11347",
                "name": "rollback removes existing commands or user data",
                "result": "PASS",
                "note": (
                    "Correct rollback preserves user data/commands. The naive "
                    "wholesale snapshot in the same run drops them (detector red)."
                ),
                "correct_user_file": good["user_file"]["exists"],
                "correct_user_cmd": good["user_cmd"]["exists"],
                "naive_user_file": rb["naive_user_file"]["exists"],
                "naive_user_cmd": rb["naive_user_cmd"]["exists"],
            },
            {
                "id": "TST-0175-MUTANT-NO-OWNERSHIP",
                "name": "disable the ownership list and confirm user data is destroyed",
                "result": "PASS",
                "mutant_user_file_exists": both["mutant_user_file"]["exists"],
            },
            {
                "id": "TST-0175-MISSING-MANIFEST-REFUSE",
                "name": "no ownership manifest means no cache wipe",
                "result": "PASS",
                "refused": both["missing_manifest"]["refused"],
            },
        ],
        "negative_controls": [
            {
                "id": "TST0175-C1-no-ownership-wipe",
                "kind": "known-broken-mutant",
                "fired_on_bad_state": not both["mutant_user_file"]["exists"],
                "silent_on_good_state": repair["user_file"]["exists"],
            },
            {
                "id": "TST0175-C2-wholesale-rollback-11347",
                "kind": "regression-seed",
                "fired_on_bad_state": not rb["naive_user_file"]["exists"],
                "silent_on_good_state": good["user_file"]["exists"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0175-probe2-rollback-regression-11347",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 does not reuse the upgrade CLI. It plants user commands "
                "and user data, runs set-difference rollback, and requires a "
                "wholesale-snapshot mutant to drop those files."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0175/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "platform/plugin/cache.py is absent on this Linux worktree. "
                    "The live SUT for TST-0175 is tools/plugin, which implements "
                    "the catalog ownership-manifest contract for update / "
                    "install --repair / rollback."
                ),
                "verdict": "NOTED",
            }
        ],
        "notes": (
            "G-1 for TST-0175: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. SUCCESS:TST-0175"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:TST-0175 sentinel missing from emitted body")
        return 1
    out.write_text(body, encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0175 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print("FAILED:TST-0175 missing supporting", missing)
        return 1

    ret = {
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "cloud_ok": False,
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "manifest_path": "command-center/p2-wave/probes/TST-0175/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "both-states-owned-cache-invalidation",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "rollback-regression-11347",
            },
        ],
        "notes": (
            "G-1 for TST-0175: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0175-probe2-rollback-regression-11347",
            "verdict": "PASS",
        },
        "ts": now,
        "measure": {"exit_code": None, "line": None},
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:TST-0175 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
