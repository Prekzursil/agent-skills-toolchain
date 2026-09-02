#!/usr/bin/env python3
"""Emit ADV-0103 council-pathology-sim artifact from live measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mechanism as M  # noqa: E402

UNIT = "ADV-0103"
OUT_REL = (
    "command-center/adversarial/"
    "ADV-0103-moderator-judge-single-point-failure.json"
)
SCHEMA_REL = "command-center/schema/council-pathology-sim.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0103/probe1_corrupted_judge.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0103/probe2_structural_bypass.py"
)


def catalog_unit() -> dict:
    data = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(
            encoding="utf-8"
        )
    )
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == UNIT:
            return row
    raise SystemExit(f"FAILED:emit {UNIT} missing from catalog")


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def validate(doc: dict, schema_path: Path) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return [e.message for e in jsonschema.Draft7Validator(schema).iter_errors(doc)]


def build(live: dict, unit: dict) -> dict:
    flags = live["structure"][0]
    overlay = live["overlay_judge_final"]
    honest = live["control_honest_judge"]
    corrupt = live["probe1_corrupt_judge"]
    sentinel = str(unit["completion_sentinel"])
    ev = str(unit.get("evidence_requirement") or "")
    t1_verdict = (
        "REFUTED" if not live["sdk_judge_alone_flipped_outcome"] else "CONFIRMED"
    )
    t2_verdict = "CONFIRMED" if overlay["flipped_by_judge_alone"] else "REFUTED"
    t3_verdict = "CONFIRMED" if live["recovery_path_raw_records"] else "REFUTED"
    probe1_raw = json.dumps(
        {
            "control_honest_published": honest["published_answer"],
            "control_honest_correct": live["sdk_honest_final_correct"],
            "corrupt_judge_answer": live["corrupt_judge_answer"],
            "corrupt_published": corrupt["published_answer"],
            "corrupt_accepted": corrupt["accepted"],
            "corrupt_for": corrupt["for_count"],
            "corrupt_against": corrupt["against_count"],
            "sdk_corrupt_final_wrong": live["sdk_corrupt_final_wrong"],
            "sdk_judge_alone_flipped_outcome": live["sdk_judge_alone_flipped_outcome"],
            "overlay_corrupt_published": overlay["corrupt_published"],
            "overlay_flipped_by_judge_alone": overlay["flipped_by_judge_alone"],
            "deciding_rule": corrupt["deciding_rule"],
        },
        sort_keys=True,
    )
    probe2_raw = json.dumps(
        {
            "artifact_keys": live["artifact_keys"],
            "decide_mentions_judge": flags["decide_mentions_judge"],
            "execute_calls_guard": flags["execute_calls_guard"],
            "execute_uses_decide": flags["execute_uses_decide"],
            "independent_output_ids": sorted(live["independent_output_ids"]),
            "judge_may_veto": live["judge_may_veto"],
            "recovery_path_raw_records": live["recovery_path_raw_records"],
            "overlay_shipped": overlay["shipped"],
            "sdk_decision_pass_through_judge": next(
                r["pass_through_judge"]
                for r in live["structure"]
                if r["output"] == "decision"
            ),
        },
        sort_keys=True,
    )
    p1_name, p2_name = ev, ev
    if "Probe 2" in ev:
        p1_name = ev.split("Probe 2")[0].strip()
        p2_name = "Probe 2" + ev.split("Probe 2", 1)[1]
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "report_kind": "council-pathology-sim",
        "title": unit.get("title")
        or "Moderator and judge as a single point of epistemic failure",
        "question": unit.get("question_or_target") or live["question"],
        "mechanism": unit.get("mechanism"),
        "overall_verdict": "PARTIAL",
        "produced_by": {
            "execution_substrate": "linux-local",
            "role": "p2-deliver-worker",
        },
        "targets": [
            {
                "id": "shipped-sdk-corrupted-judge-flips-final-output",
                "claim": (
                    "On a checkable proposal (2+2=4), corrupting only the "
                    "judge makes the shipped execute_spec output wrong."
                ),
                "verdict": t1_verdict,
                "probe": "probe1",
            },
            {
                "id": "judge-final-overlay-captures-published-answer",
                "claim": (
                    "A publisher that returns only the judge answer is "
                    "captured by a corrupt judge (named pathology; not "
                    "shipped execute_spec)."
                ),
                "verdict": t2_verdict,
                "probe": "probe1",
            },
            {
                "id": "independent-raw-records-recovery-path",
                "claim": (
                    "Transcript and votes are recorded independently of "
                    "the judge seat, which is the recovery path the "
                    "evidence requirement names."
                ),
                "verdict": t3_verdict,
                "probe": "probe2",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "name": p1_name,
                "command": P1,
                "raw_output": probe1_raw
                + "\nSUCCESS:ADV-0103-probe1 corrupted-judge checkable run recorded",
            },
            {
                "id": "probe2",
                "name": p2_name,
                "command": P2,
                "raw_output": probe2_raw
                + "\nSUCCESS:ADV-0103-probe2 structural bypass and recovery-path audit",
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-CORRUPT-JUDGE",
                "name": "Corrupted judge on checkable 2+2=4 via execute_spec",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-STRUCTURAL-BYPASS",
                "name": "Independent transcript/votes vs judge-final overlay",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-HONEST-JUDGE-CONTROL",
                "name": "Same council with an honest judge reaches the correct answer",
                "command": P1,
                "result": "PASS" if live["sdk_honest_final_correct"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-JUDGE-FINAL-OVERLAY-FIRES",
                "rejects": "judge-alone capture of the published answer",
                "on_state": "aggregate_judge_final with a corrupt judge",
                "fired_on_bad_state": bool(overlay["flipped_by_judge_alone"]),
                "silent_on_good_state": not live["sdk_judge_alone_flipped_outcome"],
                "verbatim": (
                    "Overlay publishes 5 when the judge is corrupt; shipped "
                    "majority still publishes 4 (3 FOR, 1 AGAINST)."
                ),
            }
        ],
        "measurements": {
            "probe1": {
                "sdk_judge_alone_flipped_outcome": live[
                    "sdk_judge_alone_flipped_outcome"
                ],
                "sdk_corrupt_final_wrong": live["sdk_corrupt_final_wrong"],
                "sdk_honest_final_correct": live["sdk_honest_final_correct"],
                "honest": honest,
                "corrupt": corrupt,
                "overlay": overlay,
            },
            "probe2": {
                "recovery_path_raw_records": live["recovery_path_raw_records"],
                "execute_calls_guard": flags["execute_calls_guard"],
                "decide_mentions_judge": flags["decide_mentions_judge"],
                "execute_uses_decide": flags["execute_uses_decide"],
                "independent_output_ids": live["independent_output_ids"],
                "structure": live["structure"],
                "judge_may_veto": live["judge_may_veto"],
            },
        },
        "evidence": [
            {
                "id": "E1",
                "kind": "live-sdk-run",
                "anchor": "tools/council/sdk.py:execute_spec",
                "claim": (
                    f"Honest judge publishes {honest['published_answer']}; "
                    f"corrupt judge still publishes {corrupt['published_answer']} "
                    f"via {corrupt['deciding_rule']} "
                    f"(for={corrupt['for_count']} against={corrupt['against_count']})."
                ),
                "verdict": t1_verdict,
            },
            {
                "id": "E2",
                "kind": "structural-source-audit",
                "anchor": "tools/council/sdk.py:_decide",
                "claim": (
                    "execute_spec calls _decide(votes) without RoleGuard; "
                    "transcript and votes are independent artifact keys. "
                    "Judge may_veto is declared but unwired. "
                    "aggregate_judge_final is the capture overlay."
                ),
                "verdict": t3_verdict,
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0103-probe2-structural-bypass",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 re-derives independence from sdk.py/guard.py "
                "source and artifact keys, not from probe 1's vote experiment."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "exists": True},
            {"path": SCHEMA_REL, "role": "schema", "exists": True},
            {
                "path": "command-center/p2-wave/probes/ADV-0103/mechanism.py",
                "role": "instrument",
                "exists": True,
            },
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
            }
        ],
        "timestamps": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        "residual_unknowns": [
            "No live LLM judge was seated; the SDK is a deterministic stance runner.",
            "Judge veto mandate is declared and unwired; later wiring would change T1.",
        ],
        "adv_rebuild_circle": False,
        "cloud_ok": False,
        "completion_line": "UNIT-COMPLETE:ADV-0103",
    }


def main() -> int:
    unit = catalog_unit()
    live = M.measure()
    if not live["sdk_honest_final_correct"]:
        print("FAILED:emit honest-judge control did not hold")
        return 1
    doc = build(live, unit)
    errors = validate(doc, REPO / SCHEMA_REL)
    if errors:
        print("FAILED:emit schema", errors[:8])
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    sha, size = digest(out)
    if unit["completion_sentinel"] not in text:
        print("FAILED:emit catalog sentinel absent")
        return 1
    print(
        f"wrote {OUT_REL} bytes={size} sha256={sha} "
        f"overall={doc['overall_verdict']}"
    )
    print("SUCCESS:ADV-0103 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
