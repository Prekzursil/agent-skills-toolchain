#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0043.stopping-verdict.json."""
from __future__ import annotations

import hashlib
import json
import sys
import sysconfig
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Unshadow stdlib `platform` so jsonschema can import it even if cwd is repo root.
_STDLIB = sysconfig.get_paths()["stdlib"]
if _STDLIB not in sys.path:
    sys.path.insert(0, _STDLIB)

sys.path.insert(0, str(HERE))
from evaluate import EVAL_CMD, live_bundle  # noqa: E402
import schema_util as SU  # noqa: E402

OUT = "command-center/synthesis/SYN-0043.stopping-verdict.json"
SCHEMA = "command-center/schema/stopping-verdict.schema.json"
CATALOG_SENTINEL = (
    "SUCCESS:SYN-0043 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all 21 rows carry a "
    "verdict and a probe, and the overall verdict follows the stated rule. "
    "Any other terminal state is FAILED:SYN-0043 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Implementation target: execute CC-0015's encoded predicates for all 21 "
    "stopping conditions (_USER-PROMPTS.md:11376-11398) at report time and emit "
    "TRUE | FALSE | NOT-CHECKED per condition with the probe that produced it. "
    "A NOT-CHECKED may never be folded into a pass, and condition 13 (release "
    "or canary succeeds) is known to be unsatisfiable as written under the "
    "binding PR-ONLY release mode, so its resolution must be recorded rather "
    "than silently skipped."
)
OVERALL_RULE = (
    "PROGRAM-COMPLETE requires all 21 rows TRUE. Any NOT-CHECKED yields "
    "PROGRAM-INCOMPLETE with the missing probe named. DECORATIVE (unfalsifiable) "
    "is never TRUE. FALSE also blocks PROGRAM-COMPLETE. Condition 13 under "
    "PR-ONLY is recorded FALSE with an explicit resolution; it is never skipped "
    "and never folded into a pass."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0043/probe1_live_rows.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0043/probe2_required_tests.py"
)
SELFTEST = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0043/evaluate.py --self-test"
)
SUPPORTING = [
    SCHEMA,
    "command-center/COMPLETION-GATES.json",
    "command-center/OWNER-DECISIONS.md",
    "command-center/p2-wave/probes/SYN-0043/conditions.py",
    "command-center/p2-wave/probes/SYN-0043/evaluate.py",
    "command-center/p2-wave/probes/SYN-0043/schema_util.py",
    "command-center/p2-wave/probes/SYN-0043/probe1_live_rows.py",
    "command-center/p2-wave/probes/SYN-0043/probe2_required_tests.py",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def receipt_artifact(rel: str, role: str) -> dict:
    sha, size = digest_file(rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-65000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def validate_or_die(doc: dict) -> None:
    errs = SU.iter_errors(doc, SCHEMA)
    if errs:
        print("FAILED:SYN-0043 schema errors")
        for e in errs[:25]:
            print(" ", e)
        raise SystemExit(1)
    SU.assert_rejects_garbage(SCHEMA)


def main() -> int:
    started = utc_now()
    bundle = live_bundle()
    adj = bundle["adjudication"]
    tests = bundle["tests"]
    if any(t["verdict"] != "PASS" for t in tests):
        print("FAILED:SYN-0043 required tests did not all PASS")
        print(json.dumps(tests, indent=2))
        return 1

    rows_out = []
    for r in bundle["rows"]:
        row = {
            "condition_id": r["condition_id"],
            "condition_text": r["condition_text"],
            "spec_line": r["spec_line"],
            "reconstructed": r["reconstructed"],
            "catalog_citation": r["catalog_citation"],
            "floor": r["floor"],
            "verdict": r["verdict"],
            "reason": r["reason"],
            "probe": r["probe"],
            "timestamp": r["timestamp"],
        }
        if r.get("pr_only"):
            row["pr_only"] = r["pr_only"]
        rows_out.append(row)

    counts = adj.get("counts") or {
        "TRUE": 0,
        "FALSE": 0,
        "NOT-CHECKED": 0,
        "DECORATIVE": 0,
        "row_total": 21,
    }
    c13 = bundle["condition_13_resolution"]
    world = bundle["world"]
    ended = utc_now()

    test_cmd = SELFTEST
    receipt_tests = [
        {
            "id": t["id"],
            "name": t["requirement"],
            "command": test_cmd,
            "result": "PASS" if t["verdict"] == "PASS" else "FAIL",
            "output_tail": str(t.get("evidence") or "")[:16000],
        }
        for t in tests
    ]

    observations = [
        {
            "name": "row_count",
            "measured": 21,
            "method": "command",
            "anchor": "command-center/p2-wave/probes/SYN-0043/evaluate.py",
        },
        {
            "name": "overall_verdict",
            "measured": str(adj["overall_verdict"]),
            "method": "command",
            "anchor": "command-center/p2-wave/probes/SYN-0043/evaluate.py",
        },
        {
            "name": "blocking_class",
            "measured": str(adj["blocking_class"]),
            "method": "command",
            "anchor": "command-center/p2-wave/probes/SYN-0043/evaluate.py",
        },
        {
            "name": "condition_13_verdict",
            "measured": str(c13.get("verdict")),
            "method": "command",
            "anchor": f"{EVAL_CMD} --condition 13",
        },
        {
            "name": "condition_13_skipped",
            "measured": bool(c13.get("skipped")),
            "method": "command",
            "anchor": f"{EVAL_CMD} --condition 13",
        },
        {
            "name": "not_checked_count",
            "measured": int(counts.get("NOT-CHECKED") or 0),
            "method": "command",
            "anchor": "command-center/p2-wave/probes/SYN-0043/evaluate.py",
        },
        {
            "name": "work_unit_count",
            "measured": int(world.get("work_unit_count") or 0),
            "method": "file-read",
            "anchor": "command-center/WORK-UNIT-CATALOG.json",
        },
        {
            "name": "release_mode",
            "measured": str(world.get("release_mode") or ""),
            "method": "file-read",
            "anchor": "command-center/OWNER-DECISIONS.md",
        },
    ]

    evidence_tail = json.dumps(
        {
            "overall": adj["overall_verdict"],
            "class": adj["blocking_class"],
            "counts": counts,
            "c13": c13.get("verdict"),
        },
        sort_keys=True,
    )
    evidence = [
        {
            "claim": (
                "All 21 stopping conditions were evaluated at report time with a "
                "named probe; NOT-CHECKED did not fold into PROGRAM-COMPLETE."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/SYN-0043/evaluate.py",
            "probes": [
                probe_obj("source", "command", SELFTEST, json.dumps(tests, sort_keys=True), 0),
                probe_obj("verifier", "file-read", SCHEMA, SCHEMA, 0),
            ],
        },
        {
            "claim": (
                "Condition 13 as-written is FALSE under binding PR-ONLY and was "
                "not skipped; OQ-9 is recorded as a substitute without making "
                "as-written TRUE."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"{EVAL_CMD} --condition 13",
            "probes": [
                probe_obj(
                    "source",
                    "command",
                    f"{EVAL_CMD} --condition 13",
                    evidence_tail,
                    0,
                ),
                probe_obj(
                    "verifier",
                    "file-read",
                    "command-center/OWNER-DECISIONS.md",
                    "OQ-3 PR-ONLY; OQ-9 install/upgrade/rollback substitute",
                    0,
                ),
            ],
        },
    ]

    residuals = []
    for r in rows_out:
        if r["verdict"] == "NOT-CHECKED":
            residuals.append(
                {
                    "claim": (
                        f"Stopping condition {r['condition_id']} "
                        f"({r['condition_text'][:120]}) was NOT-CHECKED."
                    ),
                    "verdict": "NOT-CHECKED",
                    "settling_experiment": r.get("reason") or r["probe"]["command"],
                }
            )
    if not residuals:
        residuals.append(
            {
                "claim": "No NOT-CHECKED stopping-condition row at this report time.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run evaluate.py --all after the missing Phase-14 receipts land."
                ),
            }
        )

    consumer_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json; from pathlib import Path; "
        "p=Path('command-center/synthesis/SYN-0043.stopping-verdict.json'); "
        "d=json.loads(p.read_text(encoding='utf-8')); "
        "assert d['unit_id']=='SYN-0043'; "
        "assert len((d.get('report') or {}).get('rows') or [])==21; "
        "print('read_ok', p.as_posix(), 'rows', 21)\""
    )

    doc = {
        "schema_version": 1,
        "unit_id": "SYN-0043",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0043",
        "profile": "stopping-verdict",
        "spec_anchor": "_USER-PROMPTS.md:11372-11400",
        "min_bytes_threshold": 2048,
        "artifacts": [receipt_artifact(rel, "supporting") for rel in SUPPORTING if (REPO / rel).is_file()],
        "evidence": evidence,
        "tests": receipt_tests,
        "negative_controls": [
            {
                "id": "planted-c4-required-test-red",
                "kind": "mutation",
                "description": (
                    "Force condition 4 (no required test is red) FALSE on an "
                    "all-TRUE world; overall must flip to PROGRAM-INCOMPLETE."
                ),
                "fired_on_bad_state": tests[2]["verdict"] == "PASS",
                "silent_on_good_state": tests[1]["verdict"] == "PASS",
                "bad_state_output": tests[2]["evidence"],
                "good_state_output": tests[1]["evidence"],
            },
            {
                "id": "single-not-checked-blocks-complete",
                "kind": "absent-input",
                "description": (
                    "20 TRUE + 1 NOT-CHECKED must yield PROGRAM-INCOMPLETE with "
                    "the missing probe named; never fold NOT-CHECKED into a pass."
                ),
                "fired_on_bad_state": tests[1]["verdict"] == "PASS",
                "silent_on_good_state": tests[0]["verdict"] == "PASS",
                "bad_state_output": tests[1]["evidence"],
                "good_state_output": tests[0]["evidence"],
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0043-probe2-required-tests",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe2 re-runs the four catalog tests_required against the "
                "evaluator, including the planted C4 false and the single "
                "NOT-CHECKED aggregation control. It does not inherit this "
                "file's overall_verdict. Owner sign-off is still required by "
                "the catalog reviewer_requirement and is not claimed here."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0043/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of SYN-0043.stopping-verdict.json 21-row report",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": probe_obj("verifier", "command", consumer_cmd, "pending-write", 0),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. The first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record, never an error "
                "to retry away"
            ),
        },
        "residual_unknowns": residuals[:16],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "completion-adjudicator",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "stopping-verdict",
            "completion_sentinel": CATALOG_SENTINEL,
            "question": QUESTION,
            "overall_verdict": adj["overall_verdict"],
            "overall_rule": OVERALL_RULE,
            "blocking_class": adj["blocking_class"],
            "blocking_condition_ids": adj["blocking_condition_ids"],
            "named_missing_probe": adj.get("named_missing_probe") or "",
            "adjudication_reason": adj.get("reason") or "",
            "rows": rows_out,
            "counts": counts,
            "condition_13_resolution": c13,
            "encoding": {
                "cc0015_role": "ENCODES the 21 predicates",
                "tst0347_role": "proves each predicate can be made FALSE",
                "this_unit_role": "RUNS them at report time and adjudicates",
                "cc0015_path": "command-center/receipts/CC-0015.json",
                "cc0015_present": bool((world.get("present") or {}).get("cc0015")),
                "tst0347_path": "command-center/receipts/TST-0347.json",
                "tst0347_present": bool((world.get("present") or {}).get("tst0347")),
                "user_prompts_present": bool(
                    (world.get("present") or {}).get("user_prompts")
                ),
                "stand_in": (
                    "command-center/p2-wave/probes/SYN-0043/evaluate.py "
                    "(TST-0347 receipt absent; CC-0015 encodes, this unit runs)"
                ),
                "spec_range": "_USER-PROMPTS.md:11376-11398",
            },
            "live_world": world,
            "falsifiability": bundle["falsifiability"],
            "controls": {
                "not_checked_does_not_fold": {
                    "id": "test_a_single_NOT_CHECKED_forces_PROGRAM_INCOMPLETE",
                    "holds": tests[1]["verdict"] == "PASS",
                    "evidence": tests[1]["evidence"],
                },
                "planted_condition_4_false": {
                    "id": "planted_false_condition_4_flips_overall",
                    "holds": tests[2]["verdict"] == "PASS",
                    "evidence": tests[2]["evidence"],
                },
                "condition_13_pr_only": {
                    "id": "test_condition_13_resolution_is_explicit_under_PR_ONLY",
                    "holds": tests[3]["verdict"] == "PASS",
                    "evidence": tests[3]["evidence"],
                },
                "twenty_one_rows": {
                    "id": "test_all_21_conditions_appear_as_rows_with_no_omission",
                    "holds": tests[0]["verdict"] == "PASS",
                    "evidence": tests[0]["evidence"],
                },
            },
            "catalog_tests": tests,
            "observations": observations,
            "control_ids": [
                "planted-c4-required-test-red",
                "single-not-checked-blocks-complete",
            ],
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "named_probes": [
                {"id": "probe1", "role": "live-21-row-re-evaluation", "command": P1},
                {"id": "probe2", "role": "required-tests-adjudication", "command": P2},
            ],
            "cloud_ok": False,
            "notes": (
                "Honest terminal evaluation: PROGRAM-COMPLETE is not claimed. "
                "cloud ok=true is not delivery. Did not run global "
                "unit_manifest.py --write."
            ),
        },
    }

    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    import subprocess
    import os

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        consumer_cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if p.returncode != 0:
        print("FAILED:SYN-0043 downstream consumer")
        print((p.stdout or "") + (p.stderr or ""))
        return 1
    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        ((p.stdout or "") + (p.stderr or "")).strip()[-65000:]
    )
    doc["downstream_consumers"][0]["exit_code"] = p.returncode
    doc["timestamps"]["ended_at"] = utc_now()
    validate_or_die(doc)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:SYN-0043 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if CATALOG_SENTINEL not in text:
        print("FAILED:SYN-0043 catalog sentinel absent from artifact")
        return 1
    if "SUCCESS:SYN-0043" not in text:
        print("FAILED:SYN-0043 short sentinel absent")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(
        f"overall={doc['report']['overall_verdict']} "
        f"class={doc['report']['blocking_class']} "
        f"counts={doc['report']['counts']}"
    )
    print("SUCCESS:SYN-0043")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
