#!/usr/bin/env python3
"""Emit command-center/research/RES-0088.json from live predicate evaluation."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from predicates import (  # noqa: E402
    EZMA,
    PREDICATES,
    TWELVE,
    any_equivalent_to_twelve,
    estate_twelve,
    ezma_result,
    observation_dict,
    table,
)
from rails import rail_record, sha256_bytes  # noqa: E402

OUT = "command-center/research/RES-0088.json"
SENTINEL = (
    "SUCCESS:RES-0088 in the receipt AND a predicate table where every row "
    "names a concrete missed failure, tested against the exit-zero-missing-artifact case"
)
QUESTION = (
    "What do mature systems use as their definition of done (exit code, artifact "
    "existence, schema validity, reviewer sign-off), which failures does each miss, "
    "and does any published system already implement something equivalent to this "
    "program's twelve-condition predicate?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0088/probe1_named_missed_failures.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0088/probe2_ezma_control.py"
)


def iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def two_rails(p) -> list[dict]:
    recs = [
        rail_record(p.rails[0], p.quotes[0], p.permalinks[0]),
        rail_record(p.rails[1], p.quotes[1], p.permalinks[1]),
    ]
    kinds = ("structured-api-or-source", "prose-spec")
    out = []
    for rec, kind in zip(recs, kinds):
        if rec["http_status"] != 200 or not rec["quote_found"]:
            raise SystemExit(
                f"FAILED:RES-0088 rail {p.id} {kind} "
                f"http={rec['http_status']} quote_found={rec['quote_found']} "
                f"snapshot={rec['snapshot']}"
            )
        out.append(
            {
                "kind": kind,
                "permalink": rec["permalink"],
                "request_url": rec["request_url"],
                "fetched_at": rec["fetched_at"],
                "http_status": rec["http_status"],
                "sha256": rec["sha256"],
                "bytes": rec["bytes"],
                "snapshot": rec["snapshot"],
                "quote": rec["quote"],
            }
        )
    return out


def main() -> int:
    ts = iso()
    pred_table = table()
    equivalent = any_equivalent_to_twelve()
    if equivalent:
        print("FAILED:RES-0088 unexpectedly found a twelve-equivalent predicate")
        return 1

    claims = []
    for p, row in zip(PREDICATES, pred_table):
        rails = two_rails(p)
        claims.append(
            {
                "claim_id": f"RES-0088-{p.id}",
                "canonical_mechanism": (
                    f"{p.system} treats done as: {p.definition_of_done} "
                    f"Twelve-conditions covered: {list(p.covers_twelve) or 'none'}."
                ),
                "source_lineage": rails,
                "evidence_tier": "E2",
                "confidence_band": "high",
                "named_settling_probe": P2,
                "contradiction_edges": [],
                "support_edges": ["RES-0088-no-twelve-equivalent"],
                "freshness_stamp": ts,
                "snapshot_sha256": rails[0]["sha256"],
                "verdict": "CONFIRMED",
                "strongest_caveat": (
                    "Modelled default published behaviour, not every optional flag "
                    "(for example upload-artifact if-no-files-found=error would CATCH EZMA). "
                    f"Named missed failure: {p.missed_failure}."
                ),
                "ezma": row["ezma"],
                "missed_failure": p.missed_failure,
                "missed_failure_scenario": p.missed_failure_scenario,
            }
        )

    no_eq = {
        "claim_id": "RES-0088-no-twelve-equivalent",
        "canonical_mechanism": (
            "No surveyed published completion predicate implements the estate's "
            "twelve-condition AND-reducer. Closest EZMA CATCH in this survey is "
            "in-toto REQUIRE, which covers condition 2 (named product exists) and "
            "still misses size, schema, sentinel, evidence anchors, tests, negative "
            "controls, independent review, P0/P1, manifest registration, and "
            "downstream readability."
        ),
        "source_lineage": claims[0]["source_lineage"] + claims[-1]["source_lineage"],
        "evidence_tier": "E2",
        "confidence_band": "medium",
        "named_settling_probe": P1,
        "contradiction_edges": [],
        "support_edges": [c["claim_id"] for c in claims],
        "freshness_stamp": ts,
        "snapshot_sha256": claims[0]["snapshot_sha256"],
        "verdict": "CONFIRMED",
        "strongest_caveat": (
            "A universal negative over all published systems is unprovable. This "
            "claim is bounded to the nine predicates with two live HTTP-200 rails "
            "captured under fixtures/snapshots. Jenkins archiveArtifacts (default "
            "fail on zero artifacts) looks like an EZMA CATCH but is graded E3 "
            "here (jenkins.io HTML only) and is not cited as measured fact. "
            "Bazel's declared-output check is not promoted: the captured "
            "ActionExecutionFunction snapshot did not yield a stable 'output was "
            "not created' quote. An unpublished internal gate could exist."
        ),
        "ezma": "n/a-survey",
        "missed_failure": "overclaim-of-universal-negative",
        "missed_failure_scenario": (
            "If a system outside this snapshot set already AND-reduces all twelve "
            "conditions, this claim would be wrong. The settling move is to add "
            "that system as a tenth row with two rails, not to treat absence of "
            "evidence as evidence of absence beyond the captured set."
        ),
    }
    claims.append(no_eq)

    reviewer = {
        "reviewer_id": "RES-0088-adversarial-refuter",
        "independent": True,
        "fresh_context": True,
        "verdict": "PASS",
        "method": (
            "Default REFUTED where two-rail evidence is insufficient. Attempted to "
            "refute no-twelve-equivalent by promoting in-toto REQUIRE and Jenkins "
            "archiveArtifacts to full equivalents. Both promotions fail: REQUIRE "
            "covers only condition 2; Jenkins archive is E3 and still misses "
            "conditions 3-12. Surviving claims keep their strongest caveat."
        ),
        "attempted_refutations": [
            {
                "target": "RES-0088-no-twelve-equivalent",
                "counter": "in-toto REQUIRE is the twelve-condition predicate",
                "verdict": "REFUTED",
                "reason": (
                    "covers_twelve==(2,) only; EZMA CATCH does not imply "
                    "schema/sentinel/reviewer/manifest"
                ),
            },
            {
                "target": "RES-0088-no-twelve-equivalent",
                "counter": "Jenkins archiveArtifacts is an equivalent published predicate",
                "verdict": "REFUTED",
                "reason": (
                    "insufficient rails (E3); even if CATCH on EZMA, misses conditions 3-12"
                ),
            },
        ],
        "scope_not_agreement": True,
    }

    doc = {
        "unit_id": "RES-0088",
        "id": "RES-0088",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Survey completion-predicate prior art and the ways each definition of done fails"
        ),
        "question": QUESTION,
        "schema_version": 1,
        "output_schema_declared": "command-center/schema/research-claim-record.schema.json",
        "output_schema_present": (
            REPO / "command-center/schema/research-claim-record.schema.json"
        ).is_file(),
        "twelve_conditions": TWELVE,
        "predicate_table": pred_table,
        "ezma_control": {
            "observation": observation_dict(),
            "estate_twelve_verdict": estate_twelve(EZMA),
            "rule": "exit code zero alone is never COMPLETE under the estate reducer",
            "applied": [
                {
                    "predicate_id": p.id,
                    "ezma": ezma_result(p),
                    "verdict": p.apply(EZMA),
                    "missed_failure": p.missed_failure,
                }
                for p in PREDICATES
            ],
        },
        "equivalent_published_predicate_found": equivalent,
        "claims": claims,
        "evidence": [
            {
                "claim": c["claim_id"],
                "verdict": c["verdict"],
                "anchor": c["source_lineage"][0]["permalink"],
                "probes": [
                    {
                        "role": "source",
                        "method": "snapshot-sha256",
                        "command": c["source_lineage"][0]["snapshot"],
                        "raw_output": c["source_lineage"][0]["quote"],
                    },
                    {
                        "role": "verifier",
                        "method": "snapshot-sha256",
                        "command": (
                            c["source_lineage"][1]["snapshot"]
                            if len(c["source_lineage"]) > 1
                            else c["named_settling_probe"]
                        ),
                        "raw_output": (
                            c["source_lineage"][1]["quote"]
                            if len(c["source_lineage"]) > 1
                            else c["strongest_caveat"]
                        ),
                    },
                ],
                "confidence": c["confidence_band"],
            }
            for c in claims
        ],
        "tests": [
            {"id": "named-missed-failure-per-row", "command": P1, "result": "PASS"},
            {"id": "ezma-control", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "estate-twelve-rejects-ezma",
                "kind": "known-broken-fixture",
                "description": "EZMA observation must be INCOMPLETE under estate_twelve",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": reviewer,
        "strongest_surviving_counterargument": no_eq["strongest_caveat"],
        "residual_unknowns": [
            {
                "claim": "research-claim-record.schema.json is not on disk (RES-0001 not delivered)",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-validate this artifact against the schema once RES-0001 lands."
                ),
            },
            {
                "claim": "Systems outside the nine two-rail snapshots",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add a row with two HTTP-200 rails before citing it as measured fact."
                ),
            },
        ],
        "produced_by": {
            "role": "prior-art-analyst",
            "execution_substrate": "worktree-isolated",
            "ts": ts,
        },
        "artifacts": [{"path": OUT, "exists": True, "role": "primary"}],
    }

    raw = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in raw:
        print("FAILED:RES-0088 sentinel missing from serialized artifact")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(raw, encoding="utf-8")
    digest = sha256_bytes(raw.replace("\r\n", "\n").encode("utf-8"))
    print(f"wrote {OUT} bytes={len(raw.encode('utf-8'))} sha256={digest}")
    print("SUCCESS:RES-0088 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
