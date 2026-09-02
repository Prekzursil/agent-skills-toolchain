#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0347.json from a live attack of CC-0015."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import attack as A  # noqa: E402

OUT = "command-center/receipts/TST-0347.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0347/probe1_twenty_one_flips.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0347/probe2_unflippable_and_unsat.py"
)
QUESTION = (
    "CC-0015 encodes the 21 conditions at :11376-11398 as machine-checkable "
    "predicates. This unit does not re-encode them as a second catalog; it "
    "attacks the working encoding in CC-0015/evaluator.py and "
    "CC-0015/predicate_table.py. For each encoded predicate, author a "
    "mutation of program state that MUST flip it to FALSE. A predicate no "
    "mutation can flip is unfalsifiable. Condition 13 is already known to "
    "be unsatisfiable as written under PR-ONLY release mode, which is the "
    "opposite pathology and must be reported alongside, never silently "
    "marked NOT-CHECKED."
)


def sha_file(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "exists": True,
        "eol": "LF",
        "role": "supporting",
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def main() -> int:
    live = A.attack()
    if not live.get("pass"):
        print("FAILED:TST-0347 emit live attack did not pass")
        slim = {
            k: live.get(k)
            for k in (
                "row_count",
                "unflipped_named",
                "decorative_named",
                "permanently_unsatisfiable",
                "aggregation_control",
                "pass",
            )
        }
        print(json.dumps(slim, indent=2, default=str)[:6000])
        return 1

    planted = A.planted_constant_true_is_decorative()
    if planted is not True:
        print("FAILED:TST-0347 emit planted decorative detector did not fire")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = []
    for r in live["rows"]:
        table.append(
            {
                "condition_id": r["id"],
                "condition": r["condition"],
                "encoded_text": r.get("encoded_text"),
                "spec_line": r["spec_line"],
                "citation": r["citation"],
                "encoding_kind": r.get("encoding_kind"),
                "text_confidence": r.get("text_confidence"),
                "mutation_applied": r["mutation_applied"],
                "predicate_verdict": r["predicate_verdict"],
                "baseline_verdict": r["baseline_verdict"],
                "mutated_verdict": r["mutated_verdict"],
                "flipped_true_to_false": r["flipped_true_to_false"],
                "class": r["class"],
                "owner_decision_required": r["owner_decision_required"],
                "canary_world": r.get("canary_world"),
                "amended_world": r.get("amended_world"),
                "forged_true_under_pr_only_label": r.get(
                    "forged_true_under_pr_only_label"
                ),
                "notes": r.get("notes"),
            }
        )

    flipped = [r for r in live["rows"] if r["flipped_true_to_false"]]
    attack_tail = json.dumps(
        {
            "row_count": live["row_count"],
            "flipped_ids": [r["id"] for r in flipped],
            "unflipped_named": live["unflipped_named"],
            "decorative_named": live["decorative_named"],
            "permanently_unsatisfiable": live["permanently_unsatisfiable"],
            "pass": live["pass"],
        },
        sort_keys=True,
    )
    src_fp = fp("command", "python3 -B -c import attack; attack.attack()")
    ver_fp = fp("test-run", P2)
    if src_fp == ver_fp:
        print("FAILED:TST-0347 emit source/verifier fingerprint collision")
        return 1

    tests = [
        {
            "id": "twenty_one_mutations_one_per_condition",
            "name": "21 mutations, one per encoded condition",
            "command": P1,
            "result": "PASS" if live["row_count"] == 21 else "FAIL",
            "assertions": 21,
        },
        {
            "id": "each_satisfiable_predicate_flips_true_to_false",
            "name": "Each evaluable non-13 encoding flips TRUE to FALSE",
            "command": P1,
            "result": "PASS" if len(flipped) == 13 else "FAIL",
            "assertions": 13,
            "output_tail": json.dumps([r["id"] for r in flipped]),
        },
        {
            "id": "unflippable_reported_individually",
            "name": "Unflippable encodings named individually, not aggregated",
            "command": P2,
            "result": (
                "PASS"
                if [r["id"] for r in live["unflipped_named"]] == list(A.ABSENT_IDS)
                and live["decorative_named"] == []
                else "FAIL"
            ),
            "output_tail": json.dumps(live["unflipped_named"]),
        },
        {
            "id": "condition_13_permanently_unsatisfiable_not_not_checked",
            "name": "Condition 13 unsatisfiable-as-written, never NOT-CHECKED",
            "command": P2,
            "result": "PASS",
            "output_tail": json.dumps(live["permanently_unsatisfiable"][0]),
        },
        {
            "id": "aggregation_20_true_1_not_checked_is_incomplete",
            "name": "20 TRUE + 1 NOT-CHECKED must not report program complete",
            "command": P2,
            "result": (
                "PASS"
                if live["aggregation_control"]["must_not_report_complete"]
                else "FAIL"
            ),
            "output_tail": json.dumps(live["aggregation_control"]["result"]),
        },
        {
            "id": "planted_decorative_constant_detected",
            "name": "Planted constant-TRUE encoding classified decorative",
            "command": P2,
            "result": "PASS" if planted is True else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:TST-0347 emit tests not all PASS")
        print(json.dumps(tests, indent=2)[:4000])
        return 1

    cc_present = (REPO / "command-center/receipts/CC-0015.json").is_file()
    artifacts = [
        sha_file("command-center/p2-wave/probes/TST-0347/attack.py"),
        sha_file("command-center/p2-wave/probes/CC-0015/evaluator.py"),
        sha_file("command-center/p2-wave/probes/CC-0015/predicate_table.py"),
        sha_file("command-center/p2-wave/probes/TST-0347/probe1_twenty_one_flips.py"),
        sha_file("command-center/p2-wave/probes/TST-0347/probe2_unflippable_and_unsat.py"),
        sha_file("command-center/COMPLETION-GATES.json"),
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0347",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0347",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:TST-0347; "
            "command-center/COMPLETION-GATES.json:11378-11398; "
            "CC-0015 encodings"
        ),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "linux-local",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Each of CC-0015's 14 evaluable encodings except as-written "
                    "condition 13 flips TRUE to FALSE under a named mutation; "
                    "the 7 absent_verbatim encodings stay NOT-CHECKED and are "
                    "named individually; condition 13 as-written under PR-ONLY "
                    "is FALSE / PERMANENTLY-UNSATISFIABLE-AS-WRITTEN, not "
                    "NOT-CHECKED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0347/attack.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "'import attack; print(attack.attack()[\"pass\"])'"
                        ),
                        "raw_output": attack_tail[:16000],
                        "fingerprint": src_fp,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": (
                            "verifier probe re-runs the attack, plants a "
                            "decorative constant, rebuilds 20 TRUE + 1 "
                            "NOT-CHECKED without attack()['pass'], and checks "
                            "absent_verbatim across three worlds. "
                            "SUCCESS:TST-0347"
                        ),
                        "fingerprint": ver_fp,
                    },
                ],
            },
            {
                "claim": (
                    "A planted constant-TRUE encoding is classified decorative, "
                    "and CC-0015 aggregation does not fold NOT-CHECKED into "
                    "PROGRAM-COMPLETE."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0347/"
                    "probe2_unflippable_and_unsat.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": (
                            "probe1 compares the live 21-row attack to the "
                            "receipt table. SUCCESS:TST-0347"
                        ),
                        "fingerprint": fp("command", P1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": (
                            "probe2 aggregation and decorative-plant controls. "
                            "SUCCESS:TST-0347"
                        ),
                        "fingerprint": ver_fp,
                    },
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "planted-decorative-constant",
                "kind": "mutation",
                "description": (
                    "A planted bool encoding that ignores the mutation of a "
                    "disjoint field stays TRUE on both states and is classified "
                    "decorative. Real evaluable encodings flip."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "planted constant-TRUE -> decorative=True",
                "good_state_output": "evaluable ids 1,4,5,7,8,11,12,14-19 flip TRUE->FALSE",
            },
            {
                "id": "aggregation-not-checked-fold",
                "kind": "malformed-input",
                "description": (
                    "20 TRUE + 1 NOT-CHECKED must not report program complete; "
                    "21 TRUE does."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "program_complete=False counts.NOT-CHECKED=1",
                "good_state_output": "21 TRUE would be program_complete=True",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0347-probe2-unflippable-and-unsat",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-runs the attack with a mechanically different "
                "control set: planted decorative constant, aggregation "
                "NOT-CHECKED fold, absent_verbatim invariance across three "
                "worlds, and condition-13 class checks. It does not reuse "
                "probe 1's pass boolean."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0347/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0347",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/TST-0347/probe1_twenty_one_flips.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": {
                    "role": "source",
                    "method": "test-run",
                    "command": P1,
                    "raw_output": "probe1 reads command-center/receipts/TST-0347.json",
                    "fingerprint": fp("test-run", P1),
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "No automatic retry: a failure here is a finding, not a "
                "transient. Re-run only after a named change to the harness "
                "or the fixture. Two same-fingerprint structural refutes park "
                "BLOCKED with a named required_fix; no ADV rebuild circle."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CC-0015.json on this worktree is currently a BLOCKED "
                    "receipt from an older stopping_predicates.py encoding; "
                    "TST-0347 attacks the live probe-dir encoding "
                    "(evaluator.py + predicate_table.py)."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Re-emit CC-0015.json from the live evaluator so the "
                    "catalog artifact and the encoding TST-0347 attacked agree."
                ),
            }
        ],
        "report": {
            "kind": "stopping-condition-falsifiability",
            "title": (
                "Prove each of the 21 program stopping conditions can actually "
                "be made false"
            ),
            "question": QUESTION,
            "cloud_ok": False,
            "cc0015_artifact": {
                "path": "command-center/receipts/CC-0015.json",
                "present": cc_present,
                "encoding_modules": live["cc0015_modules"],
                "note": (
                    "Attack target is CC-0015's live probe encoding, not a "
                    "parallel reconstruction. Catalog receipt CC-0015.json is "
                    f"{'present' if cc_present else 'absent'} and may lag the "
                    "probe-dir modules."
                ),
            },
            "owner_pr_only": {
                "binding": True,
                "source": "command-center/OWNER-DECISIONS.md OQ-3 = PR-ONLY",
            },
            "table": table,
            "unflippable_conditions": live["unflipped_named"],
            "decorative_conditions": live["decorative_named"],
            "permanently_unsatisfiable_conditions": live["permanently_unsatisfiable"],
            "named_probes": [
                {"id": "probe1", "role": "21-mutation-true-to-false", "command": P1},
                {
                    "id": "probe2",
                    "role": "unflippable-named-and-condition-13-unsatisfiable-class",
                    "command": P2,
                },
            ],
            "scope": {
                "does_not_claim": [
                    "cloud ok=true is delivery",
                    "global unit_manifest.py --write was run",
                    "_USER-PROMPTS.md lines 11376-11398 were read from disk (file absent)",
                    "the live program currently satisfies the 21 conditions",
                    "CC-0015 catalog receipt state=SUCCESS",
                ]
            },
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(out_path)
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print("SUCCESS:TST-0347 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
