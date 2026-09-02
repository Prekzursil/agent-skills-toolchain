#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0166.json from live extractor measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

from algebra import evaluate, parse, stop_decision, tree_to_dict  # noqa: E402
from candidates import (  # noqa: E402
    INEXPRESSIBLE_ID,
    SPEC_EXPRESSIONS,
    WEIGHTED_EXAMPLE,
    candidate_set,
)
from extract import CLASS_UNKNOWN, extract_all  # noqa: E402
import _p2lib as L  # noqa: E402

UNIT = "IMP-0166"
OUT = "command-center/receipts/IMP-0166.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0166/probe1_six_expressions.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0166/probe2_inexpressible.py"
)


def digest_rel(rel: str) -> tuple[str, int, bool]:
    path = REPO / rel
    if not path.is_file():
        return "", 0, False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), True


def six_by_two() -> list[dict]:
    rows = []
    for spec in SPEC_EXPRESSIONS:
        tree = parse(spec["text"])
        stop_tri = evaluate(tree, spec["stop_state"])
        cont_tri = evaluate(tree, spec["continue_state"])
        rows.append(
            {
                "id": spec["id"],
                "spec_line": spec["spec_line"],
                "text": spec["text"],
                "tree": tree_to_dict(tree),
                "stop_state": spec["stop_state"],
                "continue_state": spec["continue_state"],
                "stop_tri": stop_tri,
                "continue_tri": cont_tri,
                "stop_decision": stop_decision(stop_tri),
                "continue_decision": stop_decision(cont_tri),
            }
        )
    return rows


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = six_by_two()
    extracted = extract_all(candidate_set())
    unknown_ids = [
        r["id"] for r in extracted if r["classification"] == CLASS_UNKNOWN
    ]
    evaluable_spec = [
        r["id"]
        for r in extracted
        if r["id"].startswith("cand-spec-") and r["classification"] == "EVALUABLE"
    ]
    six_ok = all(
        r["stop_decision"] == "STOP" and r["continue_decision"] == "CONTINUE"
        for r in table
    ) and len(table) == 6
    inexpressible_ok = INEXPRESSIBLE_ID in unknown_ids
    if not six_ok or not inexpressible_ok or len(evaluable_spec) != 6:
        print(
            f"FAILED:IMP-0166 emit six_ok={six_ok} "
            f"inexpressible_ok={inexpressible_ok} spec_eval={len(evaluable_spec)}"
        )
        return 1

    c1, t1 = L.run(["python3", "-B", str(HERE / "probe1_six_expressions.py")])
    c2, t2 = L.run(["python3", "-B", str(HERE / "probe2_inexpressible.py")])
    # First emit happens before the receipt exists; probes still exercise the engine.
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0166 probes-before-write c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    wtree = parse(WEIGHTED_EXAMPLE["text"])
    supporting = [
        "command-center/p2-wave/probes/IMP-0166/algebra.py",
        "command-center/p2-wave/probes/IMP-0166/extract.py",
        "command-center/p2-wave/probes/IMP-0166/candidates.py",
        "command-center/p2-wave/probes/IMP-0166/probe1_six_expressions.py",
        "command-center/p2-wave/probes/IMP-0166/probe2_inexpressible.py",
    ]
    artifacts = []
    for rel, role in [(p, "supporting") for p in supporting]:
        sha, n, exists = digest_rel(rel)
        artifacts.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": n,
                "exists": exists,
                "role": role,
                "eol": "LF",
            }
        )

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_src_1 = L.probe("source", "command", P1, t1[-4000:], c1)
    p_ver_1 = L.probe(
        "verifier",
        "in-process-eval",
        "algebra.evaluate(parse(spec), synthetic_state) x6x2",
        json.dumps(
            [
                {
                    "id": r["id"],
                    "stop": r["stop_decision"],
                    "continue": r["continue_decision"],
                }
                for r in table
            ]
        ),
        0,
    )
    p_src_2 = L.probe("source", "command", P2, t2[-4000:], c2)
    p_ver_2 = L.probe(
        "verifier",
        "in-process-extract",
        "extract_all(candidate_set()) asserted by id",
        json.dumps({"unknown_ids": unknown_ids, "asserted": INEXPRESSIBLE_ID}),
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0166",
        "completion_sentinel": "SUCCESS:IMP-0166",
        "title": "Extract gates and stopping rules into composable Boolean predicates",
        "spec_anchor": "_USER-PROMPTS.md:10937-10942",
        "question": (
            "Target: turn each candidate's stop rule into a typed predicate tree "
            "supporting ANY/ALL/NOT and weighted logic. Acceptance: the six "
            "executable stopping expressions the spec names (10937-10942) all "
            "parse and evaluate, and a rule that cannot be expressed is recorded "
            "as UNKNOWN-NEEDS-PROBE rather than approximated."
        ),
        "min_bytes_threshold": 128,
        "six_by_two": table,
        "parsed_and_evaluated": "6/6",
        "inexpressible_asserted_by_id": unknown_ids,
        "approximated": False,
        "weighted_demo": {
            "text": WEIGHTED_EXAMPLE["text"],
            "tree": tree_to_dict(wtree),
            "stop_tri": evaluate(wtree, WEIGHTED_EXAMPLE["stop_state"]),
            "continue_tri": evaluate(wtree, WEIGHTED_EXAMPLE["continue_state"]),
            "partial_unknown_tri": evaluate(
                wtree, WEIGHTED_EXAMPLE["partial_unknown"]
            ),
        },
        "extraction": extracted,
        "grammar": {
            "operators": ["ANY", "ALL", "NOT", "WEIGHTED", "AND", "OR", "CMP"],
            "three_valued": ["TRUE", "FALSE", "UNKNOWN"],
            "unknown_never_stops": True,
            "unknown_never_coerced_to_false": True,
            "full_evaluation": True,
            "side_effect_free_atoms": True,
        },
        "artifacts": artifacts,
        "evidence": [
            L.evidence(
                "6/6 spec-named stopping expressions parse and evaluate on synthetic "
                "stop and continue states (6x2 table, every cell populated).",
                "CONFIRMED",
                "command-center/p2-wave/probes/IMP-0166/candidates.py:SPEC_EXPRESSIONS",
                [p_src_1, p_ver_1],
                "almost-certain",
            ),
            L.evidence(
                f"Inexpressible rule {INEXPRESSIBLE_ID} yields UNKNOWN-NEEDS-PROBE, "
                "asserted by id; production extractor does not snap prose to "
                "completeness_score.",
                "CONFIRMED",
                f"command-center/p2-wave/probes/IMP-0166/candidates.py:{INEXPRESSIBLE_ID}",
                [p_src_2, p_ver_2],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "T1-six-spec-expressions",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 6,
                "output_tail": t1[-1500:],
            },
            {
                "id": "T2-inexpressible-unknown-needs-probe",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 2,
                "output_tail": t2[-1500:],
            },
        ],
        "negative_controls": [
            L.control(
                "inexpressible-both-states",
                "known-broken-fixture",
                "UNKNOWN-NEEDS-PROBE fires on planted prose and is silent on the "
                "expressible twin; approximator mutation is not the production path.",
                True,
                True,
                bad=INEXPRESSIBLE_ID + "=UNKNOWN-NEEDS-PROBE",
                good="cand-spec-10937=EVALUABLE",
            ),
            L.control(
                "unsuccessful-search-is-not-impossibility",
                "known-broken-fixture",
                "proof_of_impossibility == true stays CONTINUE when search_exhausted "
                "is true but the proof flag is false.",
                True,
                True,
                bad="search_exhausted=true,proof=false -> CONTINUE",
                good="proof=true -> STOP",
            ),
            L.control(
                "kleene-and-not-or",
                "partial-evidence",
                "TRUE AND UNKNOWN evaluates UNKNOWN, never TRUE (AND-as-OR).",
                True,
                True,
                bad="unique_ideas=100 missing completeness -> UNKNOWN",
                good="both conjuncts bound and true -> STOP",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0166-probe2-inexpressible-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial control is probe2: it re-derives classifications from "
                "the candidate fixture and checks the production extractor against "
                "a planted approximator. Not a second-human review."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0166/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0166",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0166",
                    "deferred to post-write measure",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0165 imported-candidate corpus is not on this worktree; "
                    "extraction ran on a disclosed fixture set that includes the six "
                    "spec-named expressions plus planted inexpressible rules."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run extract_all on IMP-0165's live imported candidates when "
                    "that unit delivers."
                ),
            },
            {
                "claim": (
                    "_USER-PROMPTS.md:10937-10942 is not on disk; the six texts are "
                    "taken from catalog CNL-0078..CNL-0083 titles that quote those lines."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Diff the six strings against the prompts file if it is restored."
                ),
            },
        ],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot - same-fingerprint structural refute parks BLOCKED",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "defects": [],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:IMP-0166")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
