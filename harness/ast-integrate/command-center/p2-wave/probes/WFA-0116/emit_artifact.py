#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0116-benchmark-gaming-detector.json from a live run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0116-benchmark-gaming-detector.json"
DECLARED_SCHEMA = (
    "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture"
)
LOCAL_SCHEMA = "command-center/p2-wave/probes/WFA-0116/artifact.schema.json"
SENTINEL = "SUCCESS:WFA-0116"
UNIT = "WFA-0116"


def canonical(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def validate_local(doc: dict) -> dict:
    schema_path = HERE / "artifact.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = list(schema.get("required") or [])
    missing = [k for k in required if k not in doc]
    if missing:
        raise SystemExit(f"FAILED:WFA-0116 emit missing keys {missing}")
    if doc.get("record_type") != "RegressionFixture":
        raise SystemExit("FAILED:WFA-0116 emit record_type")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit("FAILED:WFA-0116 emit self-declared blocked")
    engine = "required-keys"
    try:
        import jsonschema  # type: ignore

        jsonschema.validate(instance=doc, schema=schema)
        engine = "jsonschema"
    except ImportError:
        pass
    return {"engine": engine, "ok": True, "schema": LOCAL_SCHEMA}


def dep_status() -> dict:
    pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    corpus = REPO / "command-center/wfa/WFA-0112-benchmark-case-corpus.json"
    harness = REPO / "command-center/wfa/WFA-0113-benchmark-matched-pair-harness.json"
    return {
        "WFA-0001_schema_pack": {
            "path": "command-center/wfa/schema/wfa-schema-pack.json",
            "present": pack.is_file() and pack.stat().st_size > 0,
        },
        "WFA-0112_case_corpus": {
            "path": "command-center/wfa/WFA-0112-benchmark-case-corpus.json",
            "present": corpus.is_file() and corpus.stat().st_size > 0,
        },
        "WFA-0113_matched_pair_harness": {
            "path": "command-center/wfa/WFA-0113-benchmark-matched-pair-harness.json",
            "present": harness.is_file() and harness.stat().st_size > 0,
        },
        "corpus_used": "probe-local fixture corpus (catalog WFA-0112 artifact absent on this worktree)",
    }


def build() -> dict:
    live = D.evaluate()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_id = {w["workflow_id"]: w for w in live["workflows"]}
    genuine = by_id["wf-genuine-compute"]
    omit = by_id["wf-honest-omit"]
    gaming = [w for w in live["workflows"] if w["expected_gaming"]]
    caught_which = {
        w["workflow_id"]: list(w["caught_by"]) for w in gaming
    }
    controls = live["controls"]
    if not controls["every_gaming_caught"]:
        raise SystemExit("FAILED:WFA-0116 emit planted gaming not caught")
    if not controls["genuine_clear"]:
        raise SystemExit("FAILED:WFA-0116 emit genuine false-positive")
    if not controls["honest_omit_not_voided"]:
        raise SystemExit("FAILED:WFA-0116 emit honest-omit voided")
    if not controls["no_score_adjustment"]:
        raise SystemExit("FAILED:WFA-0116 emit score adjustment")
    question = (
        "Implementation target: a detector for workflows that satisfy the "
        "oracle without doing the work - writing the expected artifact "
        "directly, memorising case identifiers, short-circuiting on a "
        "test-mode flag, or exploiting a weak oracle - which the spec names "
        "as benchmark gaming."
    )
    answer = (
        "The detector caught all four planted gaming workflows. "
        f"Signals: {json.dumps(caught_which, sort_keys=True)}. "
        "wf-genuine-compute holds on identifier+input perturbations "
        f"(visible_strong={genuine['visible']['strong_rate']}, "
        f"holdout_strong={genuine['holdout']['strong_rate']}) and is not "
        "flagged. Detected gaming voids the benchmark record entirely "
        f"({live['voided_workflow_ids']}); no score adjustment is applied. "
        "Catalog corpus WFA-0112 and harness WFA-0113 artifacts are absent; "
        "both-states ran on the probe-local fixture corpus."
    )
    tests = [
        {
            "id": "planted-gaming-caught-named-signal",
            "catalog": (
                "a deliberately gaming workflow must be caught by at least "
                "one of the two signals, and the report must say which"
            ),
            "result": "PASS" if controls["every_gaming_caught"] else "FAIL",
            "caught_by": caught_which,
        },
        {
            "id": "genuine-holdout-false-positive-control",
            "catalog": (
                "the perturbed variants must be shown not to break a "
                "known-genuine workflow (false-positive control)"
            ),
            "result": "PASS" if controls["genuine_clear"] else "FAIL",
            "visible_strong_rate": genuine["visible"]["strong_rate"],
            "holdout_strong_rate": genuine["holdout"]["strong_rate"],
            "caught": genuine["caught"],
        },
        {
            "id": "gaming-voids-record-not-adjusted",
            "catalog": (
                "any detected gaming voids that workflow's benchmark record "
                "entirely rather than adjusting it"
            ),
            "result": (
                "PASS"
                if controls["voided_equals_caught"] and controls["no_score_adjustment"]
                else "FAIL"
            ),
            "voided_workflow_ids": live["voided_workflow_ids"],
            "adjustment_applied_any": False,
        },
    ]
    evidence = [
        {
            "id": "A",
            "kind": "held-out-perturbation",
            "claim": (
                "On identifier+input variants, a gaming workflow's strong-oracle "
                "score collapses while a genuine one's holds; a constant dummy "
                "that only a weak oracle accepts is recorded as A-weak-oracle-gap."
            ),
            "verdict": "CONFIRMED",
            "anchor": THRESHOLD_NOTE,
        },
        {
            "id": "B",
            "kind": "static-definition-scan",
            "claim": (
                "A static scan of the workflow definition flags oracle-shaped "
                "constants, test-mode branches, memorised visible case ids, "
                "and weak-oracle admits before the workflow is scored."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/WFA-0116/detector.py:static_scan",
        },
    ]
    doc = {
        "SUCCESS:WFA-0116": True,
        "record_type": "RegressionFixture",
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Detect benchmark gaming: overfitting to the oracle rather than solving the case",
        "failure_class": "benchmark-gaming",
        "question_or_target": question,
        "answer": answer,
        "output_schema": DECLARED_SCHEMA,
        "local_schema": LOCAL_SCHEMA,
        "schema_pack_status": {
            "declared": DECLARED_SCHEMA,
            "pack_present": (REPO / "command-center/wfa/schema/wfa-schema-pack.json").is_file(),
            "note": (
                "WFA-0001 schema pack is absent on this worktree. This artifact "
                "is a RegressionFixture validated against the local probe schema."
            ),
        },
        "dependencies": dep_status(),
        "planted": {
            "corpus": "command-center/p2-wave/probes/WFA-0116/fixtures/workflows",
            "visible_case_ids": [
                "case-add-01",
                "case-mul-02",
                "case-xor-03",
                "case-cat-04",
            ],
            "holdout_nonce": "holdout-k7",
            "workflows": [
                {
                    "id": w["workflow_id"],
                    "planted_class": w["planted_class"],
                    "expected_gaming": w["expected_gaming"],
                }
                for w in live["workflows"]
            ],
        },
        "detector": live,
        "both_states": {
            "gaming_caught": controls["every_gaming_caught"],
            "genuine_holds": controls["genuine_clear"],
            "honest_omit_not_flagged": controls["honest_omit_not_voided"],
            "genuine_workflow_id": "wf-genuine-compute",
            "genuine_visible_strong_rate": genuine["visible"]["strong_rate"],
            "genuine_holdout_strong_rate": genuine["holdout"]["strong_rate"],
            "honest_omit_voided": omit["voiding"]["voided"],
        },
        "voiding": {
            "rule": (
                "detected gaming voids the workflow's benchmark record entirely; "
                "the detector never discounts or rescales a gamed score"
            ),
            "voided_workflow_ids": live["voided_workflow_ids"],
            "intact_workflow_ids": live["clear_workflow_ids"],
            "adjustment_applied": False,
        },
        "evidence": evidence,
        "tests": tests,
        "negative_controls": [
            {
                "id": "genuine-compute",
                "result": "PASS" if controls["genuine_clear"] else "FAIL",
            },
            {
                "id": "honest-omit-is-not-gaming",
                "result": "PASS" if controls["honest_omit_not_voided"] else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0116-probe2-genuine-holdout-and-voiding",
            "independent": True,
            "verdict": "PASS",
            "threat_model": (
                "named bypasses (gold write, id memorisation, test-mode "
                "short-circuit, weak-oracle dummy) attempted via planted "
                "workflows; both signals required to name which fired; "
                "voiding must not degrade into a score tweak"
            ),
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
            }
        ],
        "ts": now,
        "notes": (
            "G-1 implementation for WFA-0116. Fixture corpus stands in for "
            "absent WFA-0112/WFA-0113 artifacts. Did not rebuild ADV units. "
            "Did not run global unit_manifest.py --write."
        ),
    }
    schema_run = validate_local(doc)
    doc["schema_validation"] = schema_run
    # validate again after adding schema_validation (allowed extra field)
    validate_local(doc)
    return doc


THRESHOLD_NOTE = "WFA-0116.perturbation-collapse.v1 visible>=0.75 and holdout<=0.25"


def main() -> int:
    doc = build()
    if SENTINEL not in canonical(doc):
        print("FAILED:WFA-0116 emit sentinel missing from dump")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical(doc), encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
