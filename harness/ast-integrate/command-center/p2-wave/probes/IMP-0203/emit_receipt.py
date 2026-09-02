#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0203.json — certification record + admission."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import admit as A  # noqa: E402
import fixtures as F  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0203.json"
SCHEMA_REL = "command-center/schema/certification-record.schema.json"
SENTINEL = "SUCCESS:IMP-0203"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main() -> int:
    rec = F.current_record()
    pair = A.both_states_corpus(
        rec,
        live_spec_version=F.SPEC_CURRENT,
        now=F.NOW,
        superseded_corpus=F.CORPUS_SUPERSEDED,
    )
    no_anchor_errs = A.schema_errors(F.no_anchor_record())
    no_ev_errs = A.schema_errors(F.no_evidence_record())
    good_errs = A.schema_errors(rec)
    if good_errs:
        print("FAILED:emit current record is schema-invalid", good_errs)
        return 1
    if pair["current"]["status"] != A.VALID or pair["superseded"]["status"] != A.STALE:
        print("FAILED:emit both-states did not hold", pair)
        return 1
    if not no_anchor_errs or not no_ev_errs:
        print("FAILED:emit schema failed to reject missing evidence/anchor")
        return 1

    schema_path = REPO / SCHEMA_REL
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = {
        "id": "IMP-0203",
        "unit_id": "IMP-0203",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Define the certification record and its admission criteria",
        "schema_version": 1,
        "output_schema": "command-center/schema/receipt.schema.json",
        "certification_schema": SCHEMA_REL,
        "certification_schema_sha256": sha256_file(schema_path),
        "question": (
            "A typed certification record (workflow id, version, corpus version, "
            "evidence, confirmer, tier, expiry). Certification EXPIRES: a certificate "
            "older than its corpus or spec_version is STALE rather than VALID, because "
            "a stored green decays. Certify only workflows that outperform or "
            "materially complement their sources."
        ),
        "certification_record": {
            "schema_id": "certification-record/v1",
            "required_fields": [
                "schema_id",
                "workflow_id",
                "version",
                "corpus_version",
                "spec_version",
                "evidence",
                "confirmer",
                "tier",
                "expiry",
            ],
            "example_current": rec,
            "notes": (
                "corpus_version is the IMP-0201 frozen baseline id. confirmer.cited_paths "
                "are the IMP-0202 independent confirmation citations. Those units are not "
                "required to be delivered on this tree: fixtures stand in for the types."
            ),
        },
        "admission_criteria": {
            "clock": "injected UTC Z stamp; admit.evaluate never reads the wall clock",
            "VALID": (
                "schema-ok AND record.corpus_version == live_corpus_version AND "
                "record.spec_version == live_spec_version AND injected now < expiry"
            ),
            "STALE": (
                "schema-ok AND (corpus mismatch OR spec mismatch OR now >= expiry). "
                "A stored green is not a live green."
            ),
            "INVALID": "schema miss, including evidence without an anchor (path+sha256)",
            "outperform_rule": (
                "evidence.kind is outperform|complement only; a certificate cannot be "
                "formed for a workflow that does not claim one of those kinds"
            ),
            "expiry_inclusive": "now >= expiry is STALE",
        },
        "both_states": {
            "injected_now": F.NOW,
            "current_corpus": F.CORPUS_CURRENT,
            "superseded_corpus": F.CORPUS_SUPERSEDED,
            "current_status": pair["current"]["status"],
            "superseded_status": pair["superseded"]["status"],
            "superseded_reasons": pair["superseded"]["reasons"],
            "current_silent": pair["current"]["reasons"] == [],
        },
        "schema_negative_controls": {
            "no_evidence_rejected": bool(no_ev_errs),
            "no_anchor_rejected": bool(no_anchor_errs),
            "no_evidence_errors": no_ev_errs,
            "no_anchor_errors": no_anchor_errs,
            "current_schema_errors": good_errs,
        },
        "evidence": [
            {
                "claim": "Corpus-superseded certificate reports STALE under an injected clock.",
                "anchor": "command-center/p2-wave/probes/IMP-0203/probe1_stale_valid.py",
                "verdict": "CONFIRMED",
            },
            {
                "claim": "Current certificate (matching corpus+spec, now < expiry) reports VALID.",
                "anchor": "command-center/p2-wave/probes/IMP-0203/probe1_stale_valid.py",
                "verdict": "CONFIRMED",
            },
            {
                "claim": "Schema rejects a record with no evidence anchor.",
                "anchor": "command-center/p2-wave/probes/IMP-0203/probe2_schema_anchor.py",
                "verdict": "CONFIRMED",
            },
        ],
        "tests": [
            {
                "id": "stale-vs-valid-both-states",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0203/probe1_stale_valid.py"
                ),
            },
            {
                "id": "schema-rejects-no-evidence-anchor",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0203/probe2_schema_anchor.py"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0203-probe2-schema-anchor",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Mechanical adversarial check: summary-only evidence is schema-invalid. "
                "No fabricated cross-vendor human review."
            ),
        },
        "dependencies_on_this_tree": {
            "IMP-0201": False,
            "IMP-0202": False,
            "how_this_unit_still_closes": (
                "IMP-0203 defines the record and admission function. Corpus and confirmer "
                "types are named; live 0201/0202 artifacts are not claimed present."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": SCHEMA_REL, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/IMP-0203/admit.py",
                "role": "engine",
            },
        ],
    }
    out_path.write_text(dump(doc), encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out_path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
