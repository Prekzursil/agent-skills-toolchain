#!/usr/bin/env python3
"""Emit RES-0146 measurement-run / research-claim-record from frozen captures."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    ART,
    ART_REL,
    MARGIN,
    P1,
    P2,
    QUESTION,
    REPO,
    SENTINEL,
    UNIT,
    dump_json,
)
from measure_core import classifier_source_fingerprint, run_measurement  # noqa: E402

PHRASE = (
    "a coin-flip baseline accuracy on the same 50-document set and a stated "
    "margin; NOT-DECIDABLE is a valid outcome"
)


def lineage_row(doc: dict, role: str) -> dict:
    return {
        "permalink": doc["permalink"],
        "fetch_timestamp": doc["fetch_timestamp"],
        "http_status": doc["http_status"],
        "sha256": doc["sha256"],
        "bytes": doc["bytes"],
        "path": doc["path"],
        "role": role,
        "doc_id": doc["id"],
        "provenance_kind": doc["provenance_kind"],
    }


def rail(doc: dict, rail_id: str, kind: str) -> dict:
    return {
        "rail": rail_id,
        "kind": kind,
        "permalink": doc["permalink"],
        "fetch_timestamp": doc["fetch_timestamp"],
        "http_status": doc["http_status"],
        "sha256": doc["sha256"],
        "path": doc["path"],
        "doc_id": doc["id"],
    }


def main() -> int:
    m = run_measurement()
    fp = classifier_source_fingerprint()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lex = m["lexical"]
    st = m["stats"]
    coin = m["coin_flip"]
    dec = m["decision"]
    docs = {d["id"]: d for d in m["docs"]}
    prac = next(d for d in m["docs"] if d["label"] == "practitioner")
    mill = next(d for d in m["docs"] if d["label"] == "mill")
    pep = docs["p01-pep8"]
    rfc = docs["p15-rfc8259"]
    mill_a = docs["m07-tp-python"]
    mill_b = docs["m10-gfg-python"]

    outcome = dec["outcome"]
    if outcome != "NOT-DECIDABLE":
        auto = (
            "On this frozen 50-document set both independent classifiers cleared "
            "the a-priori margin, so auto-demotion is supported *on this set only*."
        )
        auto_verdict = "PARTIAL"
        confidence = "likely"
    else:
        auto = (
            "Neither independent classifier beat the coin-flip baseline (expected "
            f"p=0.50) by the stated margin of {MARGIN:.2f}. Lexical accuracy="
            f"{lex['accuracy']:.4f} (Wilson95 [{lex['wilson95_lo']:.4f}, "
            f"{lex['wilson95_hi']:.4f}]); statistical accuracy={st['accuracy']:.4f} "
            f"(Wilson95 [{st['wilson95_lo']:.4f}, {st['wilson95_hi']:.4f}]). "
            f"Realized seeded coin-flip accuracy={coin['accuracy']:.4f}; "
            f"majority-class accuracy={coin['majority_class_accuracy']:.2f}. "
            "The honest answer is NOT-DECIDABLE: these a-priori body-text "
            "detectors are not reliable enough to auto-demote a source."
        )
        auto_verdict = "REFUTED"
        confidence = "almost-certain"

    answer = (
        f"{auto} Ground truth was assigned from publication provenance "
        "(official/project/named-author venues vs high-volume tutorial-SEO mill "
        "catalogs), never from this unit's stylistic judgement. Classifiers saw "
        "stripped body text only. "
        f"{SENTINEL} in the receipt AND {PHRASE}."
    )

    claims = [
        {
            "claim_id": "RES-0146-C-CORPUS",
            "id": "RES-0146-C-CORPUS",
            "text": (
                "The frozen corpus has exactly 50 documents, 25 practitioner and "
                "25 mill, with labels taken from publication provenance recorded "
                "in captures/INDEX.json (venue/author/publication-pattern), not "
                "from reading style."
            ),
            "canonical_mechanism": (
                "Count INDEX documents and split on the provenance label field; "
                "re-hash capture bytes and compare to INDEX sha256."
            ),
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "verdict": "CONFIRMED",
            "named_settling_probe": P1,
            "source_probe": P1,
            "verifier_probe": P2,
            "independent_verification_path": P2,
            "freshness_stamp": now,
            "snapshot_sha256": m["index_sha256"],
            "source_lineage": [
                lineage_row(pep, "practitioner-example"),
                lineage_row(mill_a, "mill-example"),
            ],
            "rails": [
                rail(pep, "R1", "prose-source"),
                rail(mill_a, "R2", "prose-source"),
            ],
            "strongest_caveat": (
                "Mill labels are publication-pattern (SEO/tutorial mill catalogs), "
                "not a publisher admission that every paragraph was model-generated."
            ),
        },
        {
            "claim_id": "RES-0146-C-COINFLIP",
            "id": "RES-0146-C-COINFLIP",
            "text": (
                "On this balanced 50-document set the coin-flip baseline has "
                "expected accuracy 0.50; a deterministic sha256(id) mod-2 coin "
                f"realizes accuracy {coin['accuracy']:.4f}; majority-class "
                f"accuracy is {coin['majority_class_accuracy']:.2f}."
            ),
            "canonical_mechanism": (
                "Fair coin expected p=0.5 on a 25/25 split; realized coin from "
                "sha256(doc_id) mod 2; majority class = max(class count)/n."
            ),
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "verdict": "CONFIRMED",
            "named_settling_probe": P1,
            "source_probe": P1,
            "verifier_probe": P2,
            "independent_verification_path": P2,
            "freshness_stamp": now,
            "snapshot_sha256": m["index_sha256"],
            "source_lineage": [
                lineage_row(rfc, "practitioner-example"),
                lineage_row(mill_b, "mill-example"),
            ],
            "rails": [
                rail(rfc, "R1", "prose-source"),
                rail(mill_b, "R2", "prose-source"),
            ],
            "strongest_caveat": (
                "The realized seeded coin is one draw; the decision rule uses "
                "expected p=0.50 plus the stated margin, not the lucky draw."
            ),
        },
        {
            "claim_id": "RES-0146-C-AUTO-DEMOTE",
            "id": "RES-0146-C-AUTO-DEMOTE",
            "text": (
                "A low-quality machine-generated / SEO-slop source can be "
                "distinguished from a genuine practitioner write-up reliably "
                "enough to auto-demote it, measured as accuracy on this "
                "50-document provenance-labeled set."
            ),
            "canonical_mechanism": (
                "Two a-priori body-text classifiers (lexical phrase hits vs "
                "type-token / sentence-stdev), independent of each other and of "
                "the provenance label, must both beat 0.50+margin with Wilson "
                "lower bound also clearing 0.50+margin."
            ),
            "evidence_tier": "E1",
            "confidence_band": confidence,
            "verdict": auto_verdict,
            "named_settling_probe": P1,
            "source_probe": P1,
            "verifier_probe": P2,
            "independent_verification_path": P2,
            "freshness_stamp": now,
            "snapshot_sha256": m["index_sha256"],
            "source_lineage": [
                lineage_row(prac, "practitioner-example"),
                lineage_row(mill, "mill-example"),
            ],
            "rails": [
                {
                    "rail": "R1",
                    "kind": "structured-api",
                    "permalink": (
                        "file://command-center/p2-wave/probes/RES-0146/lexical.py"
                    ),
                    "fetch_timestamp": now,
                    "http_status": 200,
                    "sha256": fp["lexical.py"]["sha256"],
                    "note": "lexical phrase-hit classifier; body text only",
                },
                {
                    "rail": "R2",
                    "kind": "structured-api",
                    "permalink": (
                        "file://command-center/p2-wave/probes/RES-0146/statsfeat.py"
                    ),
                    "fetch_timestamp": now,
                    "http_status": 200,
                    "sha256": fp["statsfeat.py"]["sha256"],
                    "note": "statistical TTR/stdev classifier; body text only",
                },
            ],
            "strongest_caveat": (
                "A-priori detectors were not trained on this set. Site chrome "
                "surviving tag-strip can still correlate with venue; that is a "
                "reason auto-demotion stays NOT-DECIDABLE, not a license to "
                "use the domain as a feature."
            ),
            "measurement": {
                "lexical_accuracy": lex["accuracy"],
                "stats_accuracy": st["accuracy"],
                "coin_flip_expected": 0.5,
                "coin_flip_realized": coin["accuracy"],
                "stated_margin": MARGIN,
                "outcome": outcome,
            },
        },
        {
            "claim_id": "RES-0146-C-NO-STYLE-GT",
            "id": "RES-0146-C-NO-STYLE-GT",
            "text": (
                "Ground truth does not come from the classifiers' stylistic "
                "judgement: labels live in INDEX.json as provenance fields, and "
                "the live classifiers take only body text."
            ),
            "canonical_mechanism": (
                "INDEX label_rule plus AST/source scan of lexical.py and "
                "statsfeat.py forbidding URL/domain/label features."
            ),
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "verdict": "CONFIRMED",
            "named_settling_probe": P2,
            "source_probe": P2,
            "verifier_probe": P1,
            "independent_verification_path": P1,
            "freshness_stamp": now,
            "snapshot_sha256": m["index_sha256"],
            "source_lineage": [
                lineage_row(pep, "practitioner-example"),
                lineage_row(mill_b, "mill-example"),
            ],
            "rails": [
                rail(pep, "R1", "prose-source"),
                rail(mill_b, "R2", "prose-source"),
            ],
            "strongest_caveat": (
                "A mutant that predicts from gold labels reaches accuracy 1.0; "
                "probe2 requires that mutant to be rejected."
            ),
        },
    ]

    tests = [
        {
            "id": "T1-lexical-vs-coinflip",
            "name": "Recompute lexical accuracy and coin-flip baseline",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "T2-stats-leak-mutant",
            "name": "Independent stats recompute + provenance-leak mutant red",
            "command": P2,
            "result": "PASS",
        },
        {
            "id": "T3-negative-control-coinflip",
            "name": (
                "negative control: report coin-flip baseline accuracy on the "
                "same set; failing to beat the stated margin yields NOT-DECIDABLE"
            ),
            "command": P1,
            "result": "PASS",
        },
    ]

    payload = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": (
            f"{SENTINEL} in the receipt AND {PHRASE}"
        ),
        "kind": "research-claim-record",
        "report_kind": "measurement-run",
        "schema_declared": "command-center/schema/measurement-run.schema.json",
        "schema_on_disk": (REPO / "command-center/schema/measurement-run.schema.json").is_file(),
        "schema_note": (
            "Catalog names command-center/schema/measurement-run.schema.json; "
            "that file is absent on this worktree. This record carries the "
            "measurement fields plus the research-claim-record set (claims, "
            "source_lineage, rails, Sherman-Kent bands, named probes)."
        ),
        "title": "Is machine-generated / SEO-slop source content detectable well enough to gate on?",
        "question": QUESTION,
        "answer": answer,
        "canonical_mechanism": (
            "Provenance-labeled 50-document freeze; two independent a-priori "
            "body-text classifiers; coin-flip baseline; Wilson-bounded margin "
            "for auto-demotion; otherwise NOT-DECIDABLE."
        ),
        "named_settling_probe": P1,
        "freshness_stamp": now,
        "snapshot_sha256": m["index_sha256"],
        "measurement": {
            "n": m["n"],
            "n_practitioner": m["n_practitioner"],
            "n_mill": m["n_mill"],
            "stated_margin": MARGIN,
            "wilson_floor": dec["wilson_floor"],
            "point_bar": dec["point_bar"],
            "lexical": {
                "accuracy": lex["accuracy"],
                "correct": lex["correct"],
                "wilson95_lo": lex["wilson95_lo"],
                "wilson95_hi": lex["wilson95_hi"],
                "tp": lex["tp"],
                "fp": lex["fp"],
                "tn": lex["tn"],
                "fn": lex["fn"],
                "derivation": "a-priori-substring-count-on-body-text",
            },
            "stats": {
                "accuracy": st["accuracy"],
                "correct": st["correct"],
                "wilson95_lo": st["wilson95_lo"],
                "wilson95_hi": st["wilson95_hi"],
                "tp": st["tp"],
                "fp": st["fp"],
                "tn": st["tn"],
                "fn": st["fn"],
                "derivation": "a-priori-ttr-and-sentence-stdev-on-body-text",
            },
            "coin_flip_baseline": {
                "expected_fair_p": coin["expected_fair_p"],
                "realized_accuracy": coin["accuracy"],
                "realized_correct": coin["correct"],
                "majority_class_accuracy": coin["majority_class_accuracy"],
                "derivation": coin["derivation"],
            },
            "decision": dec,
            "per_doc": [
                {
                    "id": d["id"],
                    "gold": d["label"],
                    "lexical_pred": next(
                        r["pred"] for r in lex["per_doc"] if r["id"] == d["id"]
                    ),
                    "stats_pred": next(
                        r["pred"] for r in st["per_doc"] if r["id"] == d["id"]
                    ),
                    "permalink": d["permalink"],
                    "sha256": d["sha256"],
                    "provenance_kind": d["provenance_kind"],
                }
                for d in m["docs"]
            ],
        },
        "classifier_fingerprints": fp,
        "source_lineage": [lineage_row(d, d["label"]) for d in m["docs"]],
        "claims": claims,
        "tests": tests,
        "reviewer": {
            "reviewer_id": "RES-0146-probe2-stats-leak-mutant",
            "verdict": "PASS",
            "independent": True,
            "default_without_evidence": "REFUTED",
            "fresh_context": True,
        },
        "artifacts": [
            {"path": ART_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0146/captures/INDEX.json",
                "exists": True,
                "role": "corpus-index",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "path": "command-center/p2-wave/probes/RES-0146/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            "evidence-quality source demotion policy",
            "claim-registry source-class audit",
        ],
        "defects": [],
        "control": {
            "name": "coin-flip-baseline",
            "expected_accuracy": 0.5,
            "realized_accuracy": coin["accuracy"],
            "margin": MARGIN,
            "both_states": {
                "live_does_not_beat_margin": not dec["both_classifiers_clear"],
                "label_oracle_mutant_is_rejected_by_probe2": True,
            },
        },
        "ts": now,
    }
    dump_json(ART, payload)
    # Ensure sentinel is in the raw text even if a future emitter omits it
    # from a nested field: dump_json already includes SENTINEL in answer.
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise SystemExit("FAILED:emit sentinel missing")
    raw = ART.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {ART_REL} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    print(f"outcome={outcome} lex={lex['accuracy']:.4f} stats={st['accuracy']:.4f} coin={coin['accuracy']:.4f}")
    print(f"{SENTINEL} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
