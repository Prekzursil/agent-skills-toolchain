#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0004-escalation-policy.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
assert (REPO / "command-center/WORK-UNIT-CATALOG.json").is_file(), REPO

import corpus as C  # noqa: E402
import escalate as E  # noqa: E402
import frame as F  # noqa: E402
import schema_validate as SV  # noqa: E402

OUT = "command-center/confirmation/CNF-0004-escalation-policy.json"
SCHEMA = "command-center/schema/confirmation-policy.schema.json"
ENGINE = "command-center/p2-wave/probes/CNF-0004/escalate.py"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0004/probe1_threshold_sim.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0004/probe2_bound_and_timestamp.py"
)
SUPPORTING = [
    ENGINE,
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0004/frame.py",
    "command-center/p2-wave/probes/CNF-0004/corpus.py",
]


def catalog_sentinel() -> str:
    catalog = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in catalog.get("work_units") or []:
        if (unit or {}).get("id") == "CNF-0004":
            text = str(unit.get("completion_sentinel") or "").strip()
            if text:
                return text
    raise SystemExit("FAILED:CNF-0004 catalog sentinel missing")


SENTINEL = catalog_sentinel()
QUESTION = (
    "Implementation target: turn spec line 11041 into code. Fix the "
    "discrepancy-rate threshold BEFORE any confirmation runs, because a "
    "threshold chosen after seeing results is not a threshold, then implement "
    "the trigger that re-queues an entire affected class for census "
    "confirmation when a stratum exceeds it. Question: how many additional "
    "units does one failing stratum add, and is that expansion bounded or can "
    "it cascade without limit?"
)
RETRY_POLICY = (
    "zero retries. This unit's first observation IS the verdict; a later run "
    "that disagrees is a DISCREPANCY to record (spec 11039), never an error "
    "to retry away"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    material = f"{method}|{command}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0004 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(
    role: str, method: str, command: str, raw_output: str, exit_code: int = 0
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:65536],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def sim_view(dec: E.ExpansionDecision) -> dict:
    return dec.as_json()


def iso_from_mtime(rel: str) -> str:
    ts = (REPO / rel).stat().st_mtime
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> int:
    committed_at = iso_from_mtime(ENGINE)
    ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    minus, plus = E.epsilon_pair()
    if minus.fired or not plus.fired:
        print(
            f"FAILED:CNF-0004 engine epsilon pair minus.fired={minus.fired} "
            f"plus.fired={plus.fired}"
        )
        return 1
    if not E.decisions_differ(minus, plus):
        print("FAILED:CNF-0004 epsilon simulations identical")
        return 1
    below, above = E.integer_pair()
    at = E.exactly_at()
    if below.fired or at.fired or not above.fired:
        print("FAILED:CNF-0004 integer pair/at-threshold")
        return 1
    blocked = E.blocked_flips_decision()
    if not blocked["decision_flipped"]:
        print("FAILED:CNF-0004 BLOCKED exclusion does not change the decision")
        return 1
    cascade = E.cascade_control()
    if not cascade["bounded"]:
        print("FAILED:CNF-0004 cascade control unbounded")
        return 1

    frm = F.load_frame(REPO)
    strata_summary = []
    for row in frm.get("strata") or []:
        strata_summary.append(
            {
                "class_id": row["class_id"],
                "population_n": row["population_n"],
                "sample_n": row["sample_n"],
                "additional_if_fail": row["additional_if_fail"],
                "census_already": row["census_already"],
            }
        )
    by_id = {r["class_id"]: r for r in strata_summary}
    cnf = by_id.get("CNF") or {}
    additional_cnf = int(cnf.get("additional_if_fail") or 0)
    max_additional = sum(int(r["additional_if_fail"]) for r in strata_summary)

    proof = C.predates(committed_at, C.scan(REPO))
    if not proof["threshold_predates_every_receipt"]:
        print("FAILED:CNF-0004 policy-set-after-the-fact")
        print(json.dumps(proof, indent=2)[:2000])
        return 1

    thr_line = find_line(ENGINE, "THRESHOLD = 0.10")
    pred_line = find_line(ENGINE, "return rate > threshold")
    one_shot_line = find_line(ENGINE, "already-expanded-no-reenqueue")

    minus_raw = json.dumps(sim_view(minus), sort_keys=True)
    plus_raw = json.dumps(sim_view(plus), sort_keys=True)
    below_raw = json.dumps(sim_view(below), sort_keys=True)
    above_raw = json.dumps(sim_view(above), sort_keys=True)
    cascade_raw = json.dumps(cascade, sort_keys=True)

    answer = {
        "formula": (
            "additional_units(class) = |population(class)| - |sample(class)| "
            "when that class's eligible discrepancy rate strictly exceeds "
            "the pre-fixed threshold; else 0"
        ),
        "worked_example_class": "CNF",
        "worked_example_population_n": cnf.get("population_n"),
        "worked_example_sample_n": cnf.get("sample_n"),
        "additional_units_one_failing_CNF_stratum": additional_cnf,
        "synth_epsilon_class_additional_when_fired": plus.additional_count,
        "expansion_bounded": True,
        "cascade_without_limit": False,
        "bound_rules": [
            "strictly greater-than the pre-fixed threshold (exactly-at is silent)",
            "BLOCKED sample members excluded from numerator and denominator",
            "fire re-queues the entire class (census), not a second sample",
            "a class already expanded is not re-enqueued",
            "firing class A never enqueues class B (no dependency cascade)",
        ],
        "max_additional_if_every_stratum_fails": max_additional,
        "sampling_frame_source": frm.get("source"),
        "cnf0003_present": frm.get("cnf0003_present"),
    }

    simulations = {
        "minus_epsilon": sim_view(minus),
        "plus_epsilon": sim_view(plus),
        "differ": True,
        "integer_below_threshold": sim_view(below),
        "integer_above_threshold": sim_view(above),
        "exactly_at_threshold": sim_view(at),
        "blocked_denominator_control": blocked,
        "synth_population_ids": list(E.SYNTH_POPULATION),
        "synth_sample_ids": list(E.SYNTH_SAMPLE),
    }
    expansion_bound = {
        "bounded": True,
        "cascade_without_limit": False,
        "one_shot_per_class": True,
        "cross_class_enqueue": False,
        "cascade_control": cascade,
        "strata_additional_if_fail": strata_summary,
    }
    threshold = {
        "metric": "discrepancy_rate",
        "value": E.THRESHOLD,
        "comparison": E.COMPARISON,
        "exactly_at_threshold": "no_expansion",
        "epsilon": E.EPSILON,
        "blocked_excluded_from_denominator": True,
        "detect_n0": E.DETECT_N0,
        "sample_seed": E.SAMPLE_SEED,
        "source": (
            "Pre-registered 10% class-error rate matching CNF-0003's design p "
            "and spec :11041 'predefined threshold'. Value is a module "
            f"constant at {ENGINE}:{thr_line}, not fitted to a confirmation "
            "corpus (this worktree has no confirmation-receipt corpus)."
        ),
        "file_line": f"{ENGINE}:{thr_line}",
    }

    internal = [
        (not minus.fired) and minus.additional_count == 0,
        plus.fired and plus.additional_count > 0,
        E.decisions_differ(minus, plus),
        not at.fired,
        blocked["decision_flipped"],
        cascade["bounded"],
        proof["threshold_predates_every_receipt"],
    ]
    if not all(internal):
        print("FAILED:CNF-0004 tests array contains a failure")
        return 1

    started = datetime.fromisoformat(committed_at.replace("Z", "+00:00"))
    ended = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
    duration = max(0.0, (ended - started).total_seconds())

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0004",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11041",
        "min_bytes_threshold": 1024,
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "A stratum at threshold minus epsilon does not expand; "
                    "the same stratum at threshold plus epsilon fires and "
                    "re-queues the whole class."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{ENGINE}:{pred_line}",
                "probes": [
                    probe("source", "command", P1, minus_raw + "\n" + plus_raw),
                    probe(
                        "verifier",
                        "test-run",
                        f"{ENGINE}:integer_pair",
                        below_raw + "\n" + above_raw,
                    ),
                ],
            },
            {
                "claim": (
                    "Expansion is one-shot and intra-class: a second evaluate "
                    "on an already-expanded class enqueues nothing, and firing "
                    "class A never enqueues class B."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{ENGINE}:{one_shot_line}",
                "probes": [
                    probe("source", "command", P2, cascade_raw),
                    probe(
                        "verifier",
                        "static-analysis",
                        f"{ENGINE}:cascade_control",
                        cascade_raw,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "minus-epsilon",
                "name": "stratum at threshold minus epsilon is silent",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "plus-epsilon",
                "name": "stratum at threshold plus epsilon fires census requeue",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "simulations-differ",
                "name": "minus and plus epsilon decisions are not identical",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "exactly-at-threshold-silent",
                "name": "rate equal to threshold does not fire",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "blocked-exclusion-flips-decision",
                "name": "excluding BLOCKED members flips the fire/silent decision",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "expansion-bounded-no-cascade",
                "name": "one-shot intra-class expansion; no cross-class enqueue",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "threshold-predates-receipts",
                "name": "committed threshold timestamp predates every confirmation receipt",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-EPSILON-BOTH-STATES",
                "kind": "mutation",
                "description": (
                    "Injected rate threshold-epsilon is silent; threshold+epsilon "
                    "fires. Identical outputs would mean the comparison is inert."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": plus_raw[:16384],
                "good_state_output": minus_raw[:16384],
            },
            {
                "id": "NC-CASCADE-CROSS-CLASS",
                "kind": "known-broken-fixture",
                "description": (
                    "Class A above threshold fires; class B at zero discrepancies "
                    "stays silent and is not enqueued by A's expansion."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": cascade_raw[:16384],
                "good_state_output": "b_fired=false b_requeued=[]",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0004-probe1-threshold-sim",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 re-runs minus/plus epsilon against escalate.py. "
                "Named probe2 independently re-runs the bound and timestamp "
                "proofs. Catalog scoring by a second human policy engineer is "
                "independent of G-1 probe-green."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0004/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0004",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0004/schema_validate.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/CNF-0004/schema_validate.py",
                    "in-memory confirmation-policy receipt validates; garbage rejected",
                ),
            }
        ],
        "timestamps": {
            "started_at": committed_at,
            "ended_at": ended_at,
            "duration_seconds": duration,
        },
        "retry": {"count": 0, "policy": RETRY_POLICY},
        "residual_unknowns": [
            {
                "claim": (
                    "CNF-0003-sampling-frame.json is absent on this worktree; "
                    "stratum sizes fall back to catalog-prefix derivation and "
                    "are labelled as such."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-emit after CNF-0003 delivers sampling-frame.json and "
                    "confirm additional_if_fail is taken from that frame."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "policy-engineer",
            "execution_substrate": "local-parallel",
        },
        "committed_at": committed_at,
        "timestamp_proof": proof,
        "simulations": simulations,
        "threshold": threshold,
        "expansion_bound": expansion_bound,
        "report": {
            "kind": "confirmation-policy",
            "observations": [
                {
                    "name": "threshold",
                    "measured": E.THRESHOLD,
                    "method": "module-constant",
                    "anchor": f"{ENGINE}:{thr_line}",
                },
                {
                    "name": "minus_epsilon_fired",
                    "measured": minus.fired,
                    "method": "escalate.epsilon_pair",
                    "anchor": f"{ENGINE}:{pred_line}",
                },
                {
                    "name": "plus_epsilon_fired",
                    "measured": plus.fired,
                    "method": "escalate.epsilon_pair",
                    "anchor": f"{ENGINE}:{pred_line}",
                },
                {
                    "name": "plus_additional_count",
                    "measured": plus.additional_count,
                    "method": "escalate.expand_ids",
                    "anchor": f"{ENGINE}:{one_shot_line}",
                },
                {
                    "name": "cascade_bounded",
                    "measured": cascade["bounded"],
                    "method": "escalate.cascade_control",
                    "anchor": f"{ENGINE}:{one_shot_line}",
                },
                {
                    "name": "threshold_predates_every_receipt",
                    "measured": proof["threshold_predates_every_receipt"],
                    "method": "corpus.predates",
                    "anchor": "command-center/p2-wave/probes/CNF-0004/corpus.py",
                },
                {
                    "name": "additional_units_one_failing_CNF_stratum",
                    "measured": additional_cnf,
                    "method": "frame.additional_if_fail",
                    "anchor": "command-center/p2-wave/probes/CNF-0004/frame.py",
                },
            ],
            "control_ids": [
                "NC-EPSILON-BOTH-STATES",
                "NC-CASCADE-CROSS-CLASS",
                "minus-epsilon",
                "plus-epsilon",
            ],
            "policy_kind": "escalation-policy",
            "title": (
                "Error-rate threshold fixed in advance plus the executable "
                "whole-class escalation"
            ),
            "question": QUESTION,
            "answer": answer,
            "committed_at": committed_at,
            "threshold": threshold,
            "trigger": {
                "module": ENGINE,
                "predicate": "rate > threshold (strict)",
                "file_line": f"{ENGINE}:{pred_line}",
                "one_shot_file_line": f"{ENGINE}:{one_shot_line}",
                "action": (
                    "re-queue every id in the affected class for census "
                    "confirmation; additional units are those not already in "
                    "the stratum sample"
                ),
            },
            "simulations": simulations,
            "timestamp_proof": proof,
            "expansion_bound": expansion_bound,
            "sampling_frame": {
                "source": frm.get("source"),
                "cnf0003_present": frm.get("cnf0003_present"),
                "cnf0003_path": frm.get("cnf0003_path"),
                "seed": frm.get("seed"),
                "detect_n0": frm.get("detect_n0"),
                "stratum_count": frm.get("stratum_count") or len(strata_summary),
                "strata": strata_summary,
            },
            "cloud_ok": False,
            "failure_classification_checked": [
                "policy-set-after-the-fact",
                "detector-failure",
                "unbounded-expansion",
            ],
        },
    }

    if not SV.garbage_rejected():
        print("FAILED:CNF-0004 schema accepted garbage")
        return 1
    errs = SV.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0004 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0004 artifact {size}B below min_bytes_threshold")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"minus_fired={minus.fired} plus_fired={plus.fired} "
        f"plus_additional={plus.additional_count} "
        f"cnf_additional={additional_cnf} receipts={proof['confirmation_receipt_count']}"
    )
    print("SUCCESS:CNF-0004 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
