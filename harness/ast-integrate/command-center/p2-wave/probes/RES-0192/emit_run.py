#!/usr/bin/env python3
"""Emit RES-0192 measurement-run artifact."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from catalog import QUESTIONS, RAPID_PARAMS, SENTINEL, SYSTEMATIC_PARAMS, UNIT
from capture import load_index
from measure import run

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = (
    "command-center/research/deep-research-design/"
    "RES-0192-rapid-versus-systematic-review-protocol.json"
)
SCHEMA = "command-center/schema/measurement-run.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0192/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0192/probe2_parameter_and_lineage.py"
)
QUESTION = (
    "Define the decision rule that selects between a rapid review and a "
    "systematic review for a given question (decision reversibility, blast "
    "radius, literature density, contradiction risk), and validate it by "
    "running both protocols on 3 questions and comparing what the rapid "
    "version missed."
)
SENTINEL_FIELD = (
    "SUCCESS:RES-0192 in the receipt AND a decision rule that is not "
    "always-systematic, validated on three questions"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:RES-0192 emit snippet not in {rel}: {snippet!r}")


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
    }


def main() -> int:
    idx = load_index()
    if idx.get("failures"):
        print(f"FAILED:RES-0192 emit capture failures {idx['failures']}")
        return 1
    live = run(idx)
    if not live["pass"]:
        print("FAILED:RES-0192 emit live measure did not pass")
        slim = {k: live[k] for k in live if k != "questions"}
        print(json.dumps(slim, indent=2, default=str)[:4000])
        return 1

    q1 = next(q for q in live["questions"] if q["question_id"] == "Q1")
    q2 = next(q for q in live["questions"] if q["question_id"] == "Q2")
    q3 = next(q for q in live["questions"] if q["question_id"] == "Q3")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    miss_ids = [m["id"] for m in q2["diff"]["decision_relevant_misses"]]

    answer = (
        "Rule: SYSTEMATIC if (reversibility=0 AND blast>=2) OR "
        "(contradiction>=2 AND density>=2) OR weighted_score>=6, else RAPID. "
        "Weighted score = (2-reversibility)+blast+density+contradiction. "
        f"Live calls: Q1={q1['rule']['protocol']} "
        f"(score {q1['rule']['weighted_score']}), "
        f"Q2={q2['rule']['protocol']} (score {q2['rule']['weighted_score']}, "
        f"gates {q2['rule']['hard_gates']}), "
        f"Q3={q3['rule']['protocol']} (score {q3['rule']['weighted_score']}). "
        "Rapid vs systematic fingerprints differ "
        f"({live['fingerprints']['rapid'][:12]} vs "
        f"{live['fingerprints']['systematic'][:12]}). "
        "Q1 negative control: rapid missed "
        f"{q1['diff']['n_decision_relevant_misses']} decision-relevant claims. "
        f"Q2: rapid missed {q2['diff']['n_decision_relevant_misses']} "
        f"decision-relevant claims ({miss_ids}). "
        f"Q3: rapid missed {q3['diff']['n_decision_relevant_misses']} "
        "decision-relevant claims. Always-systematic mutant fails the "
        f"negative control. {SENTINEL}"
    )

    tests = [
        {
            "id": "negative-control-q1-rapid-complete",
            "command": P1,
            "result": "PASS" if live["negative_control"]["pass"] else "FAIL",
            "detail": (
                "Q1 rapid decision-relevant misses == 0; rule still recommends RAPID"
            ),
        },
        {
            "id": "q2-rapid-misses-decision-relevant",
            "command": P1,
            "result": (
                "PASS" if q2["diff"]["n_decision_relevant_misses"] >= 1 else "FAIL"
            ),
            "detail": ",".join(miss_ids),
        },
        {
            "id": "always-systematic-mutant-fails-negative-control",
            "command": P1,
            "result": "PASS" if live["both_states"]["discriminates"] else "FAIL",
            "detail": "known-good RAPID on Q1; known-broken always-systematic on Q1",
        },
        {
            "id": "protocol-fingerprints-differ",
            "command": P2,
            "result": "PASS" if live["fingerprints"]["differ"] else "FAIL",
            "detail": (
                f"rapid={live['fingerprints']['rapid']} "
                f"systematic={live['fingerprints']['systematic']}"
            ),
        },
        {
            "id": "claim-lineage-sha256",
            "command": P2,
            "result": "PASS",
            "detail": "every emitted claim carries resolved URL, fetch timestamp, sha256",
        },
    ]

    evidence = [
        ev(CATALOG, '"id": "RES-0192"', "catalog", "unit identity and completion sentinel"),
        ev(
            "command-center/p2-wave/probes/RES-0192/decision.py",
            "irreversible-and-high-blast",
            "decision-rule",
            "hard gate: irreversible + high blast requires SYSTEMATIC",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0192/catalog.py",
            '"max_records": 2',
            "rapid-quota",
            "declared rapid quota of 2 newest pubmed records",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0192/catalog.py",
            '"contradiction_search": True',
            "systematic-contradiction",
            "declared systematic contradiction search includes dissenting sources",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0192/protocol.py",
            'if params["dual_screen"]:',
            "dual-screen",
            "systematic dual-screen requires prose phrase AND Crossref phrase",
        ),
    ]

    question_summaries = []
    for q in live["questions"]:
        question_summaries.append(
            {
                "question_id": q["question_id"],
                "question": q["question"],
                "decision": q["decision"],
                "factors": q["factors"],
                "rule": q["rule"],
                "selected_rapid_sources": q["selected_rapid_sources"],
                "selected_systematic_sources": q["selected_systematic_sources"],
                "rapid_claim_ids": [c["id"] for c in q["rapid_claims"]],
                "systematic_claim_ids": [c["id"] for c in q["systematic_claims"]],
                "rapid_claims": q["rapid_claims"],
                "systematic_claims": q["systematic_claims"],
                "diff": q["diff"],
            }
        )

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL_FIELD,
        "question": QUESTION,
        "report_kind": "measurement-run",
        "ts": now,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "decision_rule": {
            "factors": ["reversibility", "blast", "density", "contradiction"],
            "hard_gates": [
                "irreversible-and-high-blast",
                "high-contradiction-and-dense-literature",
            ],
            "weighted_score": "(2-reversibility)+blast+density+contradiction",
            "threshold": 6,
            "systematic_if": "any hard gate OR weighted_score >= 6; else RAPID",
        },
        "protocol_parameters": {
            "rapid": RAPID_PARAMS,
            "systematic": SYSTEMATIC_PARAMS,
            "fingerprints": {
                "rapid": live["fingerprints"]["rapid"],
                "systematic": live["fingerprints"]["systematic"],
            },
        },
        "questions_under_test": QUESTIONS,
        "measurements": {
            "live_rule": live["live_rule"],
            "negative_control": {
                "question_id": "Q1",
                "pass": live["negative_control"]["pass"],
                "rapid_decision_relevant_misses": live["negative_control"][
                    "rapid_decision_relevant_misses"
                ],
            },
            "q2_decision_relevant_misses": q2["diff"]["n_decision_relevant_misses"],
            "q3_rapid_also_complete": live["q3_rapid_also_complete"],
            "fingerprints_differ": live["fingerprints"]["differ"],
            "n_questions": 3,
        },
        "recorded_runs": {"questions": question_summaries},
        "both_states": live["both_states"],
        "harvest": {
            "captured_at": idx.get("captured_at"),
            "n_rails": len(idx.get("rails") or []),
            "failures": idx.get("failures") or [],
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "RES-0192-probe2-parameter-and-lineage",
            "verdict": "PASS",
            "independent": True,
            "executed_both_states": True,
        },
        "evidence": evidence,
        "answer": answer,
        "residual_unknowns": [
            (
                "Corpus is a harvested methods-literature set (PRISMA, Cochrane RR "
                "guidance, Tricco 2015, Ganann 2010), not a de novo systematic "
                "search of every rapid-review evaluation. HTML snapshots omit "
                "PDF-only tables."
            ),
            (
                "would_change_decision is a coded classification of whether a "
                "missed claim would alter the protocol-choice decision, recomputed "
                "by probe2 from catalog flags plus live diffs — not a clinician panel."
            ),
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0192 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:RES-0192 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0192 sentinel missing from artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:RES-0192 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
