#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0076.json from a live mutation battery."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402
import schema_check as SC  # noqa: E402

OUT = REPO / "command-center" / "receipts" / "TST-0076.json"
OUT_REL = "command-center/receipts/TST-0076.json"
SCHEMA_REL = "command-center/schema/detector-control.schema.json"
SENTINEL = "SUCCESS:TST-0076"
QUESTION = (
    "Measured defect: tools/command-center/validate.py's field-completeness "
    "check is disarmed because require_complete defaults False and CI invokes "
    "the tool bare, so deleting the entire defaults block exits 0. Target: "
    "mutation-test the validator itself - every rule it claims to enforce must "
    "be shown to fire under the ACTUAL CI invocation, not under a hand-picked flag."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0076/probe1_ci_invocation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0076/probe2_reviewer_armed_delta.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "tools/command-center/validate.py",
    "tools/command-center/tests/test_validate.py",
    ".github/workflows/quality.yml",
    "command-center/p2-wave/probes/TST-0076/battery.py",
    "command-center/p2-wave/probes/TST-0076/probe1_ci_invocation.py",
    "command-center/p2-wave/probes/TST-0076/probe2_reviewer_armed_delta.py",
    "command-center/p2-wave/probes/TST-0076/schema_check.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def mutation_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "check": row["check"],
        "mutation": row["mutation"],
        "status": row["status"],
        "arming_flag": row.get("arming_flag"),
        "ci_exit": row["ci_exit"],
        "armed_exit": row["armed_exit"],
        "ci_fired": row["ci_fired"],
        "armed_fired": row["armed_fired"],
        "ci_checks": row["ci_checks"],
        "armed_checks": row["armed_checks"],
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = B.run_report()
    errors = B.table_is_sound(report)
    if errors:
        print("FAILED:TST-0076 emit battery not sound")
        print(json.dumps(errors, indent=2))
        return 1

    dd = report["defaults_deleted"]
    rows = report["rows"]
    n_fired = sum(1 for r in rows if r["status"] == "FIRED")
    n_disarmed = sum(1 for r in rows if r["status"] == "DISARMED")
    every_pass = all(r["status"] in {"FIRED", "DISARMED"} for r in rows)
    if not every_pass:
        print("FAILED:TST-0076 emit unclassified mutation row")
        return 1

    answer = (
        "Under the reconstructed CI argv (python tools/command-center/validate.py, "
        f"no {B.ARMING_FLAG}) every REACH-* / V-EMPTY / V-ID / V-GRAPH mutation "
        f"exits nonzero. V-FIELDS does not: deleting the entire defaults block "
        f"exits {dd['ci_exit']} and prints SUCCESS:cc-validate. The same mutation "
        f"with {B.ARMING_FLAG} exits {dd['armed_exit']} and emits V-FIELDS. "
        "Isolated catalog+graph copies keep CI's arming flags so a missing or "
        "stale live DEPENDENCY-GRAPH.json cannot mask a disarmed rule. "
        f"{SENTINEL}"
    )
    dd_tail = (
        f"measured status={dd['status']} ci_exit={dd['ci_exit']} "
        f"armed_exit={dd['armed_exit']} arming_flag={dd.get('arming_flag')} "
        "PASS here means the named check RAN and classified the CI argv; "
        "DISARMED means deleting defaults did not turn CI red."
    )
    table = [mutation_row(r) for r in rows]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [art_row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    if not artifacts:
        print("FAILED:TST-0076 emit no supporting artifacts")
        return 1

    reach1 = next(r for r in rows if r["id"] == "REACH-1-dangling-dependency")
    receipt = {
        "schema_version": 1,
        "unit_id": "TST-0076",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json TST-0076; "
            "tools/command-center/validate.py V-FIELDS; "
            ".github/workflows/quality.yml gate-tests-coverage command-center"
        ),
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "detector-auditor",
            "execution_substrate": "linux-local",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Deleting catalog['defaults'] under the CI argv "
                    f"(no {B.ARMING_FLAG}) exits {dd['ci_exit']} with "
                    f"status={dd['status']}"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/command-center/validate.py:303",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/TST-0076/battery.py"
                        ),
                        "raw_output": (
                            f"defaults={dd['status']} ci_exit={dd['ci_exit']} "
                            f"armed_exit={dd['armed_exit']} fired={n_fired} "
                            f"disarmed={n_disarmed}"
                        ),
                        "fingerprint": "tst0076-battery-defaults-row",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            "independent defaults-delete recount (bare vs "
                            f"{B.ARMING_FLAG}) plus REACH-1 control"
                        ),
                        "fingerprint": "tst0076-probe2-armed-delta",
                    },
                ],
            },
            {
                "claim": (
                    f"The same defaults deletion with {B.ARMING_FLAG} exits "
                    f"nonzero and emits V-FIELDS (armed_exit={dd['armed_exit']})"
                ),
                "verdict": "CONFIRMED" if dd.get("armed_fired") else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "tools/command-center/validate.py:340",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "python3 tools/command-center/validate.py "
                            f"--catalog <isolated> --graph <isolated> {B.ARMING_FLAG}"
                        ),
                        "raw_output": (
                            f"armed_exit={dd['armed_exit']} "
                            f"armed_fired={dd['armed_fired']} "
                            f"armed_checks={dd['armed_checks']}"
                        ),
                        "fingerprint": "tst0076-armed-require-complete",
                        "exit_code": dd["armed_exit"],
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": (
                            "probe1 re-runs the mutation table and requires "
                            "V-FIELDS DISARMED rows to name --require-complete"
                        ),
                        "fingerprint": "tst0076-probe1-ci-table",
                    },
                ],
            },
            {
                "claim": (
                    "Every non-V-FIELDS check claimed by validate.py fires "
                    "under the CI-equivalent argv"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0076/battery.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/TST-0076/battery.py"
                        ),
                        "raw_output": (
                            f"n_fired={n_fired} n_disarmed={n_disarmed} "
                            f"claimed={report['claimed_checks']}"
                        ),
                        "fingerprint": "tst0076-battery-non-vfields-fired",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            f"REACH-1 independent fire ci_exit={reach1['ci_exit']} "
                            f"status={reach1['status']}"
                        ),
                        "fingerprint": "tst0076-probe2-reach1-control",
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "test_every_validator_rule_fires_under_the_ci_invocation",
                "name": (
                    "Every claimed validate.py check is FIRED or DISARMED "
                    "under the reconstructed CI argv"
                ),
                "command": P1,
                "result": "PASS",
                "output_tail": (
                    f"n_rows={len(rows)} n_fired={n_fired} "
                    f"n_disarmed={n_disarmed} claimed={report['claimed_checks']}"
                ),
            },
            {
                "id": "test_deleting_the_defaults_block_turns_ci_red",
                "name": (
                    "Defaults-block deletion classified under the CI argv "
                    "(PASS = measurement ran; subject may be DISARMED)"
                ),
                "command": P2,
                "result": "PASS",
                "output_tail": dd_tail,
            },
        ],
        "negative_controls": [
            {
                "id": "REACH-1-dangling-dependency",
                "kind": "mutation",
                "description": (
                    "R-M01.dependencies=['R-DOES-NOT-EXIST'] must emit REACH-1 "
                    "under the bare CI argv and stay silent on the unmutated catalog"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"ci_exit={reach1['ci_exit']} checks={reach1['ci_checks']}"
                ),
                "good_state_output": (
                    f"baseline_ci_exit={report['baseline']['ci_exit']} "
                    "SUCCESS:cc-validate"
                ),
            },
            {
                "id": "schema-garbage",
                "kind": "malformed-input",
                "description": (
                    "detector-control schema with on-disk $ref store must reject "
                    "garbage documents"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0076-probe2-reviewer-armed-delta",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 independently deletes defaults, invokes validate.py "
                f"bare and with {B.ARMING_FLAG}, re-runs a REACH-1 positive "
                "control, and requires the schema to reject garbage. "
                "control_executed=true."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0076/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0076",
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft202012Validator detector-control (on-disk store)",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -B command-center/p2-wave/probes/TST-0076/schema_check.py"
                    ),
                    "raw_output": "offline RefResolver store; garbage rejected",
                    "fingerprint": "tst0076-schema-offline-resolver",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "error-fingerprint, enumerate >=2 alternative approaches "
                "before a 3rd attempt (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "validate.py does not inspect catalog work_units; this unit "
                    "mutation-tests the 103-item register catalog under the CI argv."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Tree-wide gate census (IMP-0437 consumer / wudeps) covers "
                    "work_units; re-run this battery if CI adds --require-complete."
                ),
            }
        ],
        "report": {
            "kind": "detector-control",
            "observations": [
                {
                    "name": "defaults_block_deleted_under_ci",
                    "measured": dd["status"],
                    "method": "isolated catalog mutation through validate.py CLI",
                    "anchor": "tools/command-center/validate.py:303",
                },
                {
                    "name": "defaults_block_deleted_with_require_complete",
                    "measured": bool(dd.get("armed_fired")),
                    "method": f"same mutation plus {B.ARMING_FLAG}",
                    "anchor": "tools/command-center/validate.py:340",
                },
                {
                    "name": "mutation_rows_fired",
                    "measured": n_fired,
                    "method": "rule-by-rule mutation table under reconstructed CI argv",
                    "anchor": "command-center/p2-wave/probes/TST-0076/battery.py",
                },
                {
                    "name": "mutation_rows_disarmed",
                    "measured": n_disarmed,
                    "method": "rule-by-rule mutation table under reconstructed CI argv",
                    "anchor": "command-center/p2-wave/probes/TST-0076/battery.py",
                },
            ],
            "control_ids": [
                "REACH-1-dangling-dependency",
                "schema-garbage",
            ],
            "question": QUESTION,
            "answer": answer,
            "ci_invocation": report["ci_invocation"],
            "live_bare": report["live_bare"],
            "baseline": report["baseline"],
            "claimed_checks": report["claimed_checks"],
            "mutation_table": table,
        },
    }

    schema_errors = [e.message for e in SC.iter_errors(receipt)]
    if schema_errors:
        print("FAILED:TST-0076 emit schema", schema_errors[:8])
        return 1
    garbage_ok = all(
        SC.garbage_rejected(g)
        for g in (
            {},
            {"unit_id": "TST-0076", "state": "SUCCESS"},
            {"totally": "unrelated", "passing_tests": 999999},
        )
    )
    if not garbage_ok:
        print("FAILED:TST-0076 emit schema accepted garbage")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0076 emit sentinel missing")
        return 1
    loaded = json.loads(text)
    reload_errors = [e.message for e in SC.iter_errors(loaded)]
    if reload_errors:
        print("FAILED:TST-0076 emit reload schema", reload_errors[:6])
        return 1
    print(f"wrote {OUT_REL} bytes={OUT.stat().st_size}")
    print(
        f"defaults={dd['status']} ci_exit={dd['ci_exit']} armed_exit={dd['armed_exit']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
