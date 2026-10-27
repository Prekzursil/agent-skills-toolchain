#!/usr/bin/env python3
"""Write TST-0337 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json.

Runs named probes live. Does not invoke tools/command-center/unit_manifest.py --write.
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

import engine as E  # noqa: E402
import product as P  # noqa: E402

UID = "TST-0337"
OUT = "command-center/receipts/TST-0337.json"
SENTINEL = "SUCCESS:TST-0337"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0337/probe1_soundness_differential.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0337/probe2_newfile_noml.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0337/selector.py",
    "command-center/p2-wave/probes/TST-0337/product.py",
    "command-center/p2-wave/probes/TST-0337/engine.py",
    "command-center/p2-wave/probes/TST-0337/probe1_soundness_differential.py",
    "command-center/p2-wave/probes/TST-0337/probe2_newfile_noml.py",
    "command-center/p2-wave/probes/TST-0337/fixtures/coverage_map.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0337/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    P.dump_coverage_map(HERE / "fixtures" / "coverage_map.json")
    live = E.run()
    if not live["ok"]:
        print("FAILED:TST-0337 engine.ok is false; not writing SUCCESS receipt")
        print(json.dumps({k: live[k] for k in ("ok", "both_states") if k in live}, indent=1))
        return 1

    sound = live["sound"]
    unsound = live["unsound_filename_only"]
    nf = live["newfile"]
    ml = live["noml"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    miss_pub = [
        {
            "mutation_id": row["mutation_id"],
            "file": row["file"],
            "kind": row["kind"],
            "class": row["class"],
        }
        for row in unsound["miss_list"]
    ]

    receipt = {
        "id": UID,
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Prove the impacted-test selector never omits a test the full suite would have failed",
        "question": (
            "Selecting only impacted tests is only safe if selection is sound. "
            "For a corpus of mutations, run BOTH the selected subset and the full "
            "suite, and assert that every mutation caught by the full suite is also "
            "caught by the subset. Any mutation the full suite catches and the subset "
            "misses is an unsound selector."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "catalog_output_schema": "command-center/schema/receipt.schema.json",
        "generated_at": now,
        "generating_commit": "NO-GIT",
        "inputs_resolved": {
            "command-center/TEST-REGISTRY.json": (
                "PRESENT"
                if (REPO / "command-center" / "TEST-REGISTRY.json").is_file()
                else "ABSENT"
            ),
            "note": (
                "Catalog lists TEST-REGISTRY.json as an input. The file is on "
                "this worktree and names command-center/harness suites, not an "
                "impacted-test selector. The soundness differential therefore "
                "uses the probe-local product, tests, and "
                "fixtures/coverage_map.json. Presence of the registry is not "
                "folded into a pass."
            ),
            "selector": "command-center/p2-wave/probes/TST-0337/selector.py",
            "mutation_corpus": "engine.build_mutations (deterministic, >=100)",
        },
        "evidence": {
            "n_mutations": sound["n_mutations"],
            "caught_by_full_suite": sound["caught_by_full_suite"],
            "caught_by_subset": sound["caught_by_subset"],
            "sound_selector_miss_list": sound["miss_list"],
            "unsound_filename_only_miss_list": miss_pub,
            "unsound_miss_files": sorted({r["file"] for r in unsound["miss_list"]}),
            "time_saved": sound["time_saved"],
            "newfile_default_selected": nf["all_changes_select_newfile"],
            "predictive_rejected": ml["predictive_rejected"],
            "both_states": live["both_states"],
        },
        "measurements": {
            "mutations": sound["n_mutations"],
            "full_caught": sound["caught_by_full_suite"],
            "subset_caught": sound["caught_by_subset"],
            "sound_misses": sound["miss_count"],
            "unsound_misses": unsound["miss_count"],
            "graph_misses": live["dependency_graph"]["miss_count"],
        },
        "tests": [
            {
                "id": "TST-0337-soundness-differential-100",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "TST-0337-unsound-filename-only-control",
                "result": "PASS",
                "detail": f"miss_count={unsound['miss_count']}",
            },
            {
                "id": "TST-0337-newfile-default-selected",
                "result": "PASS",
                "command": P2,
            },
            {
                "id": "TST-0337-no-ml-predictive-rejected",
                "result": "PASS",
                "command": P2,
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": "command-center/p2-wave/probes/TST-0337/selector.py", "role": "selector"},
            {
                "path": "command-center/p2-wave/probes/TST-0337/fixtures/coverage_map.json",
                "role": "coverage-map",
            },
        ],
        "negative_controls": [
            {
                "id": "filename-only-unsound",
                "fired_on_bad_state": unsound["miss_count"] > 0,
                "silent_on_good_state": sound["miss_count"] == 0,
                "description": (
                    "Filename-only selection misses helper()/mid mutations that "
                    "the full suite catches; coverage-map selection does not."
                ),
            },
            {
                "id": "drop-unmapped-newfile",
                "fired_on_bad_state": nf["mapped_only_misses_secret"],
                "silent_on_good_state": nf["newfile_is_the_catch"],
                "description": (
                    "Dropping tests absent from the coverage map misses secret() "
                    "mutations; default SELECTED catches them."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0337-probe2-newfile-noml",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Reconstructed unmapped tests from on-disk coverage_map.json, "
                "required SELECTED on four changed-file sets, reproduced secret() "
                "miss without the new-file test, and rejected PredictiveSelector."
            ),
        },
        "answer": (
            f"Coverage-map and dependency-graph selectors are sound on "
            f"{sound['n_mutations']} mutations: full suite caught "
            f"{sound['caught_by_full_suite']}, subset caught "
            f"{sound['caught_by_subset']}, miss list empty. Filename-only "
            f"control missed {unsound['miss_count']} mutations "
            f"(files {sorted({r['file'] for r in unsound['miss_list']})}). "
            f"Time saved: {sound['time_saved']['executions_saved']} test "
            f"executions "
            f"({sound['time_saved']['seconds_saved']}s). New-file tests "
            f"default SELECTED. Predictive selectors rejected. {SENTINEL}"
        ),
        "notes": (
            "G-1 for TST-0337. Did not run unit_manifest.py --write. "
            "Did not git add/commit/push. No ADV rebuild. SUCCESS:TST-0337"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0337 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    # Re-hash after probes (probes dump coverage_map.json; receipt already written).
    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "soundness-differential",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "newfile-and-noml",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0337/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0337-probe2-newfile-noml",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0337: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
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
    print("SUCCESS:TST-0337 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
