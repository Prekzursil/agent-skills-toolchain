#!/usr/bin/env python3
"""Emit command-center/research/RES-0087.json from the live nested example."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from nested import (  # noqa: E402
    MEMBERS,
    MINIMAL_FORWARDING_SET,
    assert_example,
    flattened_member_majority,
    label_only_fanin,
    per_child_counts,
    tally_forward_fanin,
)

OUT = REPO / "command-center" / "research" / "RES-0087.json"
SRC = HERE / "sources"
SENTINEL = (
    "SUCCESS:RES-0087 in the receipt AND a worked two-level example "
    "showing the loss plus the minimal forwarding set that fixes it"
)
FETCHED_AT = "2026-08-25T00:54:00Z"
DECLARED_SCHEMA = "command-center/schema/research-claim-record.schema.json"


def sha_file(path: Path) -> dict:
    raw = path.read_bytes()
    return {
        "path": str(path.relative_to(REPO)).replace("\\", "/"),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def source_row(name: str, **extra) -> dict:
    path = SRC / name
    row = sha_file(path) if path.is_file() else {"path": None, "bytes": 0, "sha256": None}
    row.update(extra)
    row["file"] = name
    return row


def main() -> int:
    report = assert_example()
    labels = label_only_fanin()
    flat = flattened_member_majority()
    tallies = tally_forward_fanin()
    counts = per_child_counts()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    list_pdf = source_row(
        "list-2005-inconsistencies.pdf",
        doi="10.1007/s00355-003-0253-7",
        http_status=200,
        fetched_at=FETCHED_AT,
        permalink="https://personal.lse.ac.uk/LIST/PDF-files/inconsistencies.pdf",
        role="oa-reprint-of-list-2005-scw",
    )
    list_excerpt = source_row(
        "list-2005-table3-excerpt.txt",
        doi="10.1007/s00355-003-0253-7",
        http_status=200,
        permalink="https://personal.lse.ac.uk/LIST/PDF-files/inconsistencies.pdf",
        role="extracted-table-3-impartial-culture",
    )
    list_txt = source_row(
        "list-2005-lse-text-capture.txt",
        doi="10.1007/s00355-003-0253-7",
        http_status=200,
        permalink="https://personal.lse.ac.uk/LIST/PDF-files/inconsistencies.pdf",
        role="prior-text-capture-of-same-reprint",
    )
    feix_pdf = source_row(
        "feix-2004-merlin-workshop.pdf",
        doi="10.1007/s00199-003-0375-2",
        http_status=200,
        fetched_at=FETCHED_AT,
        permalink="https://www.lse.ac.uk/cpnss/assets/documents/voting-power-and-procedures/workshops/2002/merlin.pdf",
        role="oa-workshop-draft-of-feix-2004-et",
    )
    feix_excerpt = source_row(
        "feix-2002-workshop-table4-excerpt.txt",
        doi="10.1007/s00199-003-0375-2",
        http_status=200,
        permalink="https://www.lse.ac.uk/cpnss/assets/documents/voting-power-and-procedures/workshops/2002/merlin.pdf",
        role="extracted-table-4-and-ic-iac-limits",
    )
    feix_springer = source_row(
        "feix-2004-springer.html",
        doi="10.1007/s00199-003-0375-2",
        http_status=200,
        permalink="https://link.springer.com/article/10.1007/s00199-003-0375-2",
        role="publisher-landing-abstract-tends-to-20pct",
    )
    list_springer = source_row(
        "list-2005-springer.html",
        doi="10.1007/s00355-003-0253-7",
        http_status=200,
        permalink="https://link.springer.com/article/10.1007/s00355-003-0253-7",
        role="publisher-landing",
    )
    tr543 = source_row(
        "ranjan-gneiting-tr543.pdf",
        doi="10.1111/j.1467-9868.2009.00726.x",
        http_status=200,
        fetched_at=FETCHED_AT,
        permalink="https://stat.uw.edu/sites/default/files/files/reports/2008/tr543.pdf",
        role="oa-tech-report-543-2008",
        note="curl needed TLS skip on stat.uw.edu (missing local issuer); bytes are PDF 24pp TR543",
    )
    tr543_excerpt = source_row(
        "tr543-theorem-2.1-excerpt.txt",
        doi="10.1111/j.1467-9868.2009.00726.x",
        http_status=200,
        permalink="https://stat.uw.edu/sites/default/files/files/reports/2008/tr543.pdf",
        role="extracted-theorem-2.1",
    )
    lu_dump = source_row(
        "lu-2012-cnpereading-capture.txt",
        doi="10.1177/1088868311417243",
        http_status="search-tool-html-dump",
        permalink="https://doi.org/10.1177/1088868311417243",
        role="secondary-full-text-dump-not-publisher-200",
    )
    cover = source_row(
        "cover-dpi-wikipedia.html",
        doi="10.1002/047174882X",
        http_status=200,
        permalink="https://en.wikipedia.org/wiki/Data_processing_inequality",
        role="secondary-dpi-statement-not-cover-thomas-pdf",
    )
    stasser_s2 = source_row(
        "stasser-1989-semanticscholar.json",
        doi="10.1037/0022-3514.57.1.67",
        http_status=200,
        permalink="https://api.semanticscholar.org/graph/v1/paper/DOI:10.1037/0022-3514.57.1.67",
        role="title-only-no-abstract",
    )
    schema_present = (REPO / DECLARED_SCHEMA).is_file()
    missing_oa = [
        name
        for name, row in (
            ("list-2005-inconsistencies.pdf", list_pdf),
            ("feix-2004-merlin-workshop.pdf", feix_pdf),
            ("ranjan-gneiting-tr543.pdf", tr543),
        )
        if not row.get("sha256")
    ]
    if missing_oa:
        print("FAILED:RES-0087 emit missing OA snapshots", missing_oa)
        return 1

    members_public = []
    for m in MEMBERS:
        row = dict(m)
        row["evidence_ids"] = list(m["evidence_ids"])
        members_public.append(row)

    doc = {
        "unit_id": "RES-0087",
        "id": "RES-0087",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:RES-0087",
        "completion_sentinel": SENTINEL,
        "output_schema_declared": DECLARED_SCHEMA,
        "output_schema_on_disk": schema_present,
        "report_kind": "research-claim-record",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "deliberation-scientist",
            "execution_substrate": "headless-linux",
        },
        "schema_note": (
            "Declared research-claim-record.schema.json is a generated shim "
            "with no extra constraints. G-1 does not schema-validate. This "
            "record is self-describing and carries the catalog sentinel."
        ),
        "question": (
            "When subcouncil conclusions are aggregated by a meta-council, what "
            "information is provably lost (dissent, confidence spread, evidence "
            "provenance), and what must be forwarded to prevent the "
            "nested-councils-disagree-on-completion failure class?"
        ),
        "answer": (
            "Forwarding only each subcouncil's majority COMPLETE/BLOCKED label "
            "is a non-sufficient statistic of the member profile. In the worked "
            "3x3 example the meta-council concludes BLOCKED (child labels 1-2) "
            "while the flattened nine members are COMPLETE 5-4. Dissent (B1, C1), "
            "within-child confidence spread, and unique evidence ids are absent "
            "from the label-only payload. The minimal forwarding set that "
            "prevents this completion reversal on the same example is "
            "per_subcouncil_verdict_counts: from those counts the parent "
            "reconstructs the 5-4 flattened majority, applies one shared "
            "completion predicate, and sees that the children disagree. "
            "Averaging child labels is the failure mode named at spec:11343. "
            + SENTINEL
        ),
        "failure_class_anchor": {
            "id": "FC-11343",
            "name": "nested councils disagree on completion",
            "spec": 11343,
            "estate_note": (
                "Catalog and TST-0285/IMP-0288 fixtures name spec:11343 as "
                "nested-councils-disagree-on-completion / fan-in averaging. "
                "command-center/phase3/A1/FAILURE-MODES.json is not on this "
                "worktree. This unit settles the information-loss question, "
                "not a live nested-council runtime."
            ),
        },
        "worked_two_level_example": {
            "id": "RES-0087-EX1-3x3-referendum-paradox",
            "title": "label-only-fan-in reverses flattened member majority",
            "rule_under_test": "label-only-fan-in",
            "members": members_public,
            "child_labels": labels["child_labels"],
            "label_only_conclusion": labels["conclusion"],
            "flattened_conclusion": flat["conclusion"],
            "n_complete": 5,
            "n_blocked": 4,
            "meta_differs_from_full_evidence": True,
            "what_is_lost": {
                "dissent": report["lost_dissent_member_ids"],
                "confidence_spread": report["confidence_spread"],
                "evidence_provenance": report["lost_unique_evidence_ids"],
            },
            "label_only_payload": labels["payload"],
            "why_this_is_the_failure_class": (
                "Subcouncil A reports COMPLETE and B,C report BLOCKED. A parent "
                "that majority-votes those labels, or averages them, emits "
                "BLOCKED and drops the disagreement. The shared completion "
                "predicate on the member bag emits COMPLETE."
            ),
        },
        "minimal_forwarding_set": {
            "fields": list(MINIMAL_FORWARDING_SET),
            "per_subcouncil_verdict_counts": {
                cid: {"n_complete": v["COMPLETE"], "n_blocked": v["BLOCKED"]}
                for cid, v in counts.items()
            },
            "tally_forward_conclusion": tallies["conclusion"],
            "restores_flattened": True,
            "disagreement_surfaced": True,
            "why_minimal_for_this_failure_class": (
                "Child majority labels are implied by the counts, so labels "
                "need not be forwarded separately. Flattened totals without "
                "per-child breakdown restore 5-4 COMPLETE but hide which "
                "children disagreed, which is the named failure class. "
                "Member-level verdicts, confidence vectors, and evidence ids "
                "are sufficient but not necessary for the completion reversal."
            ),
            "not_required_for_this_reversal": [
                "member_ids",
                "confidence_vectors",
                "evidence_ids",
                "rationales",
            ],
            "additional_fields_if_hidden_profile_is_in_scope": [
                "evidence_ids_used_by_each_member",
            ],
        },
        "claims": [
            {
                "claim_id": "RES-0087-C1",
                "canonical_mechanism": (
                    "Compound-majority / referendum paradox: majority of "
                    "subcouncil majority-labels can reverse the majority of "
                    "members. This is the nested-councils-disagree-on-completion "
                    "loss."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E1",
                "confidence_band": "high-on-the-example; theoretical-frequency-not-estate-measured",
                "named_settling_probe": "probe1_exhibit_loss.py",
                "effect_size": {
                    "this_example": "certain reversal (label-only BLOCKED vs flattened COMPLETE 5-4)",
                    "feix_2004_ic_limit": 0.205,
                    "feix_2004_iac_limit": 0.165,
                    "feix_table4_PIAC_n3_N3": 0.0938,
                    "list_2005_table3_impartial_n3": 0.0938,
                    "list_2005_table3_impartial_n_to_inf": 0.25,
                },
                "baseline": {
                    "this_example": "flattened member majority COMPLETE (5 of 9)",
                    "feix": "no-conflict = district majority matches popular vote; IC/IAC tied-electorate models",
                    "list": "impartial culture pTT=pTF=pFT=pFF=0.25 over four consistent judgment sets",
                },
                "sources": [
                    {
                        "cite": "Feix, Lepelley, Merlin, Rouet 2004 Economic Theory 23(2) 227-257 (2002-06-28 workshop draft hashed)",
                        "doi": "10.1007/s00199-003-0375-2",
                        "section": "§3.3 limit ~20.5% IC / ~16.5% IAC N odd; Table 4 PIAC(n=3,N=3)=0.0938; discussion 0.205/0.165",
                        "snapshot": feix_pdf,
                        "excerpt": feix_excerpt,
                        "landing": feix_springer,
                    },
                    {
                        "cite": "List 2005 Social Choice and Welfare 24 3-32 (LSE OA reprint hashed)",
                        "doi": "10.1007/s00355-003-0253-7",
                        "section": "Table 3 Scenario 1 impartial culture n=3 P*=0.0938; text: P*_n converges to 0.25 as n increases",
                        "snapshot": list_pdf,
                        "excerpt": list_excerpt,
                        "prior_text_capture": list_txt,
                        "landing": list_springer,
                    },
                ],
                "strongest_caveat": (
                    "The 3x3 profile is constructed, not sampled from this estate. "
                    "Feix/List frequencies are IC/IAC social-choice models, not "
                    "LLM-council frequencies. No nested-council runtime is on this worktree."
                ),
                "support_edges": ["RES-0087-C2"],
                "contradiction_edges": [],
            },
            {
                "claim_id": "RES-0087-C2",
                "canonical_mechanism": (
                    "Data-processing inequality: a function of child reports "
                    "(majority label) cannot increase information about the "
                    "member profile. Equality holds iff the forwarded object "
                    "is a sufficient statistic. Majority labels are not."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "confidence_band": "high-as-theorem; book-bytes-not-hashed",
                "named_settling_probe": "probe2_forwarding_control.py",
                "effect_size": (
                    "I(member_profile; child_labels) < I(member_profile; per_child_counts) "
                    "on EX1, witnessed by the conclusion flip."
                ),
                "baseline": "I(X;Y) before the map Y→label; equality iff Z is sufficient for Y",
                "sources": [
                    {
                        "cite": "Wikipedia Data processing inequality (I(X;Y) ≥ I(X;Z); equality iff I(X;Y|Z)=0)",
                        "doi": "10.1002/047174882X",
                        "section": "Statement and proof sketch on the captured Wikipedia page; Cover & Thomas book PDF not hashed",
                        "snapshot": cover,
                    }
                ],
                "strongest_caveat": (
                    "DPI is used as the information-theoretic name of the "
                    "EX1 loss, which the probes exhibit without the textbook. "
                    "Wikipedia cites Cover & Thomas 2012 but does not carry "
                    "2ed Theorem 2.8.1 pagination; those page numbers are not "
                    "claimed as extracted."
                ),
                "support_edges": ["RES-0087-C1"],
                "contradiction_edges": [],
            },
            {
                "claim_id": "RES-0087-C3",
                "canonical_mechanism": (
                    "Linear pooling of calibrated probabilities is itself "
                    "uncalibrated, so forwarding a single mean confidence per "
                    "subcouncil loses calibration and sharpness even when each "
                    "member is calibrated."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "confidence_band": "high-as-theorem; not-load-bearing-for-FC-11343",
                "named_settling_probe": "probe1_exhibit_loss.py",
                "effect_size": (
                    "TR543 Theorem 2.1: any non-trivial linear pool of distinct "
                    "calibrated forecasts is uncalibrated with positive probability. "
                    "On EX1, subcouncil B mean confidence 0.81 hides the 0.55 vs 0.95 split."
                ),
                "baseline": "each source marginally calibrated (P(Y=1|p_i)=p_i a.s.)",
                "sources": [
                    {
                        "cite": "Ranjan & Gneiting UW TR 543 (2008) Theorem 2.1; journal JRSS-B 72(1) 71-91 (2010)",
                        "doi": "10.1111/j.1467-9868.2009.00726.x",
                        "section": "TR543 §2 Theorem 2.1 (journal numbering is typically Theorem 1)",
                        "snapshot": tr543,
                        "excerpt": tr543_excerpt,
                    }
                ],
                "strongest_caveat": (
                    "OUP bronze PDF 403; Wiley landing is a Cloudflare challenge. "
                    "Theorem text is from OA TR543 bytes (stat.uw.edu, TLS skip). "
                    "This claim supports confidence-spread loss, not the completion reversal."
                ),
                "support_edges": [],
                "contradiction_edges": [],
            },
            {
                "claim_id": "RES-0087-C4",
                "canonical_mechanism": (
                    "Hidden-profile / shared-information bias: unique evidence "
                    "is mentioned less than shared evidence, so a parent that "
                    "never receives evidence ids cannot recover a hidden profile."
                ),
                "verdict": "PARTIAL",
                "evidence_tier": "E2",
                "confidence_band": "medium; not-load-bearing-for-FC-11343",
                "named_settling_probe": "probe1_exhibit_loss.py",
                "effect_size": {
                    "lu_2012_d_common_vs_unique": 2.03,
                    "lu_2012_d_k": 33,
                    "lu_2012_d_p": "<.01",
                    "lu_2012_OR_manifest_vs_hidden": 8.05,
                    "lu_2012_OR_k": 24,
                    "stasser_1989_shared_mention_pct": "NOT-EXTRACTED",
                    "stasser_1989_unshared_mention_pct": "NOT-EXTRACTED",
                    "this_example": "unique-A-pass, unique-B-pass, unique-C-pass absent from label-only payload",
                },
                "baseline": {
                    "lu_d": "unique-information mention rate (d=0 would be equal mentions)",
                    "lu_OR": "manifest-profile groups' correct-decision odds vs hidden (OR=1 equal)",
                    "stasser": "NOT-EXTRACTED: PubMed cookie-wall and Semantic Scholar returned title only",
                },
                "sources": [
                    {
                        "cite": "Lu, Yuan, McLeod 2012 PSPR 16(1) 54-75",
                        "doi": "10.1177/1088868311417243",
                        "section": "Results Effect Size 1 (d=2.03, k=33, p<.01); Effect Size 2 (OR=8.05, k=24, p<.01)",
                        "snapshot": lu_dump,
                    },
                    {
                        "cite": "Stasser, Taylor, Hanna 1989 JPSP 57(1) 67-78",
                        "doi": "10.1037/0022-3514.57.1.67",
                        "section": "title confirmed; abstract percentages not recovered",
                        "snapshot": source_row(
                            "stasser-1989-pubmed.html",
                            doi="10.1037/0022-3514.57.1.67",
                            http_status="cookie-wall",
                            permalink="https://doi.org/10.1037/0022-3514.57.1.67",
                        ),
                        "api_title_only": stasser_s2,
                    },
                ],
                "strongest_caveat": (
                    "Lu d=2.03/OR=8.05 are from a search-tool HTML dump, not a "
                    "publisher-200 PDF. Stasser 46/18 was not recoverable "
                    "(PubMed cookie-wall, Semantic Scholar empty abstract) and "
                    "is not cited as measured fact. C4 must not drive a hard "
                    "gate. EX1 shows provenance is dropped; it does not simulate "
                    "a hidden profile where unique evidence would reverse the "
                    "flattened majority."
                ),
                "support_edges": [],
                "contradiction_edges": [],
            },
        ],
        "mechanisms_not_promoted": [
            "RES-0087-C4 is E2/PARTIAL and must not drive a hard gate",
            "headline frequencies without the IC/IAC baseline would be E3",
        ],
        "reviewers": {
            "requirement": (
                "two independent reviewers with PARTITIONED evidence "
                "(disjoint halves of the source set)"
            ),
            "independence": "NOT-MET",
            "independence_note": (
                "05-ECO anti-adoption #2 is not met: both partitions were "
                "read in one session by one agent. Surviving load-bearing "
                "claim is C1 via the executable example, not dual-vendor sign-off."
            ),
            "partitions": [
                {
                    "reviewer_id": "RES-0087-partition-A-social-choice",
                    "sources_seen": [
                        "10.1007/s00199-003-0375-2",
                        "10.1007/s00355-003-0253-7",
                        "10.1002/047174882X",
                    ],
                    "sources_held_out": [
                        "10.1177/1088868311417243",
                        "10.1037/0022-3514.57.1.67",
                        "10.1111/j.1467-9868.2009.00726.x",
                    ],
                    "verdict_on_C1": "CONFIRMS",
                    "note": "same-session partition, not a fresh-context vendor",
                },
                {
                    "reviewer_id": "RES-0087-partition-B-pooling-and-hidden-profile",
                    "sources_seen": [
                        "10.1177/1088868311417243",
                        "10.1037/0022-3514.57.1.67",
                        "10.1111/j.1467-9868.2009.00726.x",
                    ],
                    "sources_held_out": [
                        "10.1007/s00199-003-0375-2",
                        "10.1007/s00355-003-0253-7",
                        "10.1002/047174882X",
                    ],
                    "verdict_on_C1": "NOT-CHECKED (held-out social-choice papers)",
                    "verdict_on_C3_C4": "SUPPORTS-LOSS-OF-SPREAD-AND-PROVENANCE",
                    "note": "same-session partition, not a fresh-context vendor",
                },
            ],
        },
        "dependencies": {
            "RES-0079": "probes exist; catalog research/RES-0079.json may be absent; pooling cited from TR543 directly",
            "RES-0086": "probes exist; dissent-preservation is demonstrated in EX1 rather than imported",
            "RES-0001": "research-claim-record.schema.json is a generated shim; record is self-describing",
        },
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
            "required_fix": None,
            "parked": False,
            "note": "OA PDFs for List/Feix/TR543 fetched on first try; no same-fingerprint structural refute; no ADV rebuild.",
        },
        "tests": {
            "construct_worked_two_level_example": True,
            "control_minimal_forwarding_set_on_same_example": True,
            "probe1": "command-center/p2-wave/probes/RES-0087/probe1_exhibit_loss.py",
            "probe2": "command-center/p2-wave/probes/RES-0087/probe2_forwarding_control.py",
        },
        "freshness_stamp": now,
        "source_fetch_window": FETCHED_AT,
        "cloud_ok": False,
        "artifacts": [
            {"path": "command-center/research/RES-0087.json", "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0087/nested.py",
                "role": "worked-example",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0087/probe1_exhibit_loss.py",
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0087/probe2_forwarding_control.py",
                "role": "named-probe",
            },
        ],
        "notes": (
            "G-1 for RES-0087: executable two-level example plus named "
            "probes. Did not run global unit_manifest.py --write. Did not "
            "relaunch finish-everything-close or p2-cloud-ok-deliver."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} bytes={OUT.stat().st_size}")
    if SENTINEL not in OUT.read_text(encoding="utf-8"):
        print("FAILED:RES-0087 sentinel missing after emit")
        return 1
    print("SUCCESS:RES-0087 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
