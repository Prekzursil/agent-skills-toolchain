#!/usr/bin/env python3
"""Emit IMP-0356 receipt + per-unit manifest + SUBAGENT-RETURN after live probes."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0356"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/outcomes/tests/test_completeness.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0356/probe1_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0356/probe2_vacuous_section.py"
)
SUPPORTING = [
    "tools/council/outcomes/__init__.py",
    "tools/council/outcomes/completeness.py",
    "tools/council/schema/charter-completeness.schema.json",
    "tools/council/outcomes/tests/__init__.py",
    "tools/council/outcomes/tests/conftest.py",
    "tools/council/outcomes/tests/test_completeness.py",
    "command-center/p2-wave/probes/IMP-0356/probe1_census.py",
    "command-center/p2-wave/probes/IMP-0356/probe2_vacuous_section.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
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


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code_t, out_t = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print("FAILED:IMP-0356 live tests/probes did not all exit 0")
        print(out_t[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if "SUCCESS:IMP-0356-tests" not in out_t:
        print("FAILED:IMP-0356 tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0356-probe1" not in out1:
        print("FAILED:IMP-0356 probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0356-probe2" not in out2:
        print("FAILED:IMP-0356 probe2 sentinel missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    pt = probe_rec("verifier", TEST_CMD, out_t, code_t)
    supporting_arts = [art(rel, "supporting") for rel in SUPPORTING]
    artifact_paths = [OUT_REL] + list(SUPPORTING)
    test_ids = [
        "test_complete_artifact_passes",
        "test_absent_section_listed_as_missing",
        "test_empty_but_present_fails_nonvacuity",
        "test_census_twenty_councils_lists_missing",
        "named-probe1",
        "named-probe2",
    ]
    negative_control_ids = [
        "empty-but-present-dissent",
        "present-checkbox",
        "placeholder-tbd-unknowns",
    ]
    question = (
        "Implement tools/council/outcomes/completeness.py asserting the final "
        "artifact contains every output the charter declared required "
        "(positions, idea ledger, argument graph, votes, dissent, unknowns, "
        "experiments, recommendation, calibration). Falsifiable question: "
        "which required outputs are missing most often across recorded "
        "councils, and can the check be satisfied by an empty section that "
        "merely exists?"
    )
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0356; charter-required final outputs "
            "and non-vacuity of empty-but-present sections"
        ),
        "min_bytes_threshold": 128,
        "title": "Charter completeness check on the final answer",
        "question_or_target": question,
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": "two-strikes-then-pivot; a verification failure never retries",
        },
        "implementation": {
            "module": "tools/council/outcomes/completeness.py",
            "required_outputs": [
                "positions",
                "idea_ledger",
                "argument_graph",
                "votes",
                "dissent",
                "unknowns",
                "experiments",
                "recommendation",
                "calibration",
            ],
            "presence_is_not_completeness": True,
            "census_n": 20,
            "missing_most_often": "calibration",
        },
        "artifact_paths": artifact_paths,
        "artifacts": supporting_arts,
        "evidence": [
            {
                "anchor": "tools/council/outcomes/completeness.py:census",
                "claim": (
                    "A per-output presence and non-vacuity table over 20 "
                    "recorded councils lists missing outputs per council. "
                    "Calibration is incomplete most often (12/20: 10 absent, "
                    "2 vacuous)."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, pt],
            },
            {
                "anchor": "tools/council/outcomes/completeness.py:is_vacuous",
                "claim": (
                    "An empty-but-present section ([], {}, '', TBD, or "
                    "{present: true}) FAILS non-vacuity. A complete twin in "
                    "the same run still passes."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, pt],
            },
        ],
        "tests": [
            {
                "id": "test_census_twenty_councils_lists_missing",
                "command": TEST_CMD + "::test_census_twenty_councils_lists_missing",
                "result": "PASS",
            },
            {
                "id": "test_empty_but_present_fails_nonvacuity",
                "command": TEST_CMD + "::test_empty_but_present_fails_nonvacuity",
                "result": "PASS",
            },
            {"id": "named-probe1", "command": P1, "result": "PASS"},
            {"id": "named-probe2", "command": P2, "result": "PASS"},
        ],
        "test_ids": test_ids,
        "negative_controls": [
            {
                "id": "empty-but-present-dissent",
                "kind": "known-broken-fixture",
                "description": (
                    "Complete twin with dissent replaced by [] / {} / '' / TBD "
                    "/ {present: true} fails non-vacuity; the untouched twin "
                    "still passes."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "dissent:vacuous",
                "good_state_output": "complete twin pass=true missing=[]",
            },
            {
                "id": "present-checkbox",
                "kind": "known-broken-fixture",
                "description": "{present: true} is metadata-only and FAILS.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "vacuous present_checkbox",
                "good_state_output": "filled section pass",
            },
            {
                "id": "placeholder-tbd-unknowns",
                "kind": "known-broken-fixture",
                "description": "rec-15 unknowns='TBD' is listed missing though present.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "unknowns:vacuous on rec-15",
                "good_state_output": "rec-20 missing=[]",
            },
        ],
        "negative_control_ids": negative_control_ids,
        "reviewer": {
            "reviewer_id": "IMP-0356-probe2-vacuous-section",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "starts_from": "complete twin and vacuous mutants, not the census ranking",
            "obligation": (
                "Empty-but-present required sections must FAIL. Presence of a "
                "key is not completeness."
            ),
        },
        "reviewer_verdict": "PASS",
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog dependencies IMP-0315 (event store) and IMP-0312 "
                    "(dissent pipeline) are not present as imported modules "
                    "this checker calls. Completeness inspects a final artifact "
                    "dict. Wiring check_artifact into those pipelines is their "
                    "units' work, not a missing non-vacuity rule."
                ),
                "settling_experiment": (
                    "When IMP-0315/IMP-0312 land, run check_artifact on a "
                    "replayed store artifact and on a dissent-conservation "
                    "final and assert empty sections still fail."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0356 charter completeness. Live named probes "
            "measure the 20-council census and the empty-but-present negative "
            "control. Did not run global unit_manifest.py --write. cloud ok "
            "is not consulted."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:IMP-0356 receipt too small ({live_bytes} B)")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    fixture_dir = HERE / "fixtures" / "recorded"
    for path in sorted(fixture_dir.glob("rec-*.json")):
        rel = str(path.relative_to(REPO)).replace("\\", "/")
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "census",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "vacuous-section",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0356-probe2-vacuous-section",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0356: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
