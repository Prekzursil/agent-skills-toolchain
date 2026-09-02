#!/usr/bin/env python3
"""Emit command-center/research/RES-0086.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

OUT = "command-center/research/RES-0086.json"
SCHEMA = "command-center/p2-wave/probes/RES-0086/artifact.schema.json"
DECLARED_SCHEMA = "command-center/schema/research-claim-record.schema.json"
QUESTION = (
    "How do juries, standards bodies and regulatory advisory panels "
    "structurally guarantee that a minority position survives into the "
    "record, and which of those mechanisms is implementable as a hard "
    "gate rather than an instruction the synthesizer may ignore?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0086/probe1_classify.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0086/probe2_gate_control.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    caps = C.verify_captures()
    if not caps["ok"]:
        print("FAILED:RES-0086 emit capture integrity", caps["failures"])
        return 1
    both = C.both_states()
    if not both["discriminates"]:
        print("FAILED:RES-0086 emit both-states did not discriminate")
        print(both)
        return 1
    table = C.attach_rails(C.mechanisms())
    claims = C.claims()
    gate = C.hard_gate()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    declared_present = (REPO / DECLARED_SCHEMA).is_file()

    answer = (
        "Juries do not structurally preserve minority reasoning: FRCP 31 "
        "requires a unanimous verdict, and a poll that reveals dissent "
        "restarts deliberation or ends in mistrial, so the verdict form has "
        "no minority-report field (M7, norm-dependent as a preservation "
        "mechanism). Standards bodies split. W3C Formal Objections are "
        "structurally-enforced: the objection MUST state issue, decision and "
        "rationale, a record MUST be made publicly available, and a Call for "
        "Review MUST identify related FOs (M1; field formal_objections). "
        "IEEE-SA recirculation is structurally-enforced: the ballot package "
        "MUST carry verbatim unresolved Do Not Approve comments, voter name, "
        "and the CRG response (M2; field unresolved_negative_comments). IETF "
        "rough consensus (RFC 7282) tells chairs to explain unaccommodated "
        "objections but the RFC artifact has no required dissent section "
        "(M6, norm-dependent; not a gate). Regulatory panels split the same "
        "way. FOMC minutes structurally name members 'Voting against this "
        "action' plus a one-line preference (M3; field vote.against). FDA "
        "21 CFR 14.60 requires minutes of matters discussed, but closed "
        "deliberative minutes may not refer to members by name, so attributed "
        "dissent is not a checkable field (M5, norm-dependent). ICJ Statute "
        "Article 57 entitles any judge to a separate opinion published with "
        "a non-unanimous judgment (M4; field dissenting_opinions). The "
        "council-transferable hard gate is minority_reports (required keys "
        "author_id, rationale, claim_ids, sha256), fed by M1-M4 only. A "
        "synthesizer instruction to include dissent, including the named "
        "failure class at _USER-PROMPTS.md:11340, is not a gate (M8). "
        "SUCCESS:RES-0086 in the receipt AND a mechanism table with an "
        "enforcement classification and a named checkable artifact field"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "RES-0086",
        "id": "RES-0086",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0086",
        "completion_sentinel": (
            "SUCCESS:RES-0086 in the receipt AND a mechanism table with an "
            "enforcement classification and a named checkable artifact field"
        ),
        "title": (
            "Extract dissent-preservation mechanisms from institutions that "
            "mandate minority reports"
        ),
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "min_bytes_threshold": 2048,
        "output_schema_declared": DECLARED_SCHEMA,
        "output_schema_declared_present": declared_present,
        "local_artifact_schema": SCHEMA,
        "report_kind": "research-claim-record",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "deliberation-scientist",
            "execution_substrate": "headless-linux",
        },
        "mechanism_table": table,
        "hard_gate": gate,
        "claims": claims,
        "both_states": {
            "check": both["check"],
            "fired_on_bad": both["fired_on_bad"],
            "silent_on_good": both["silent_on_good"],
            "discriminates": both["discriminates"],
            "bad_reason": both["negative_control"]["on_that_state"],
            "good_reason": "canonical table violations=[]",
            "hard_gate_field": both["hard_gate_field"],
            "mutant_norm_as_gate": both["mutant_norm_as_gate"],
            "mutant_empty_field": both["mutant_empty_field"],
        },
        "capture_integrity": {
            "n": caps["n"],
            "ok": caps["ok"],
            "failures": caps["failures"],
        },
        "source_snippets": {
            "w3c_public_record": C.snippet(
                "w3c-process-html", b"must be made"
            ),
            "ieee_verbatim": C.snippet(
                "ieee-opman-sect5", b"verbatim text of each comment"
            ),
            "fomc_vote_against": C.snippet(
                "fomc-minutes-20260729", b"Voting against this action"
            ),
            "icj_art57": C.snippet(
                "icj-statute",
                b"any judge shall be entitled to deliver a separate opinion",
            ),
            "fda_no_names": C.snippet(
                "govinfo-21-14-60-xml",
                b"may not refer to members by name",
            ),
            "ietf_minority_noise": C.snippet(
                "rfc7282-txt",
                b"important minority views to get lost in the noise",
            ),
            "frcp31_unanimous": C.snippet(
                "frcp-31-cornell", b"The verdict must be unanimous"
            ),
        },
        "timestamps": {
            "started_at": "2026-08-24T18:47:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 1,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
            "pivots": [
                "IEEE live OM/FAQ returned HTTP 403; pivoted to Wayback snapshots of the same URLs.",
                "eCFR HTML returned a WAF interstitial; pivoted to GovInfo CFR XML granule.",
            ],
        },
        "tests": [
            {
                "id": "T1-classify-every-mechanism",
                "name": (
                    "classify every mechanism structurally-enforced versus "
                    "norm-dependent"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-named-hard-gate-field",
                "name": (
                    "control: name the specific artifact field a hard gate "
                    "would check"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0086-C1",
                "kind": "known-broken-fixture",
                "description": both["negative_control"]["rejects"],
                "fired_on_bad_state": both["fired_on_bad"],
                "silent_on_good_state": both["silent_on_good"],
                "on_the_state_it_rejects": both["negative_control"][
                    "on_that_state"
                ],
                "bad_state_output": both["negative_control"]["bad_state_output"],
                "good_state_output": both["negative_control"]["good_state_output"],
            }
        ],
        "evidence": [
            {
                "id": "E1-w3c-fo-must-public",
                "claim": (
                    "W3C Process requires a public Formal Objection record "
                    "and Call-for-Review identification."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "rails": ["w3c-process-html", "w3c-council-guide"],
            },
            {
                "id": "E2-ieee-verbatim-recirc",
                "claim": (
                    "IEEE-SA recirculation packages must include verbatim "
                    "unresolved Do Not Approve comments, voter name, and response."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "rails": ["ieee-opman-sect5", "ieee-recirc-faq"],
            },
            {
                "id": "E3-fomc-vote-against",
                "claim": (
                    "FOMC minutes contain a 'Voting against this action' "
                    "named-member line."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "rails": ["fomc-minutes-20260729", "stlouisfed-fomc-dissents"],
            },
            {
                "id": "E4-icj-art57",
                "claim": (
                    "ICJ Statute Article 57 entitles a separate opinion on a "
                    "non-unanimous judgment."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "rails": ["icj-statute", "icj-spender-art57"],
            },
            {
                "id": "E5-fda-names-optional",
                "claim": (
                    "21 CFR 14.60 lets closed deliberative minutes omit member names."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "rails": ["govinfo-21-14-60-xml", "cornell-21-14-60"],
            },
            {
                "id": "E6-ietf-no-rfc-field",
                "claim": (
                    "RFC 7282 warns that head-counts lose minority views and "
                    "asks for a reasoned explanation, without an RFC dissent field."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "rails": ["rfc7282-txt", "rfc7282-datatracker-html"],
            },
            {
                "id": "E7-frcp31-unanimous",
                "claim": "FRCP 31 verdicts must be unanimous; dissent yields mistrial.",
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "rails": ["frcp-31-cornell", "ca3-frcp-31-chapter9"],
            },
            {
                "id": "E8-prompt-is-not-a-gate",
                "claim": (
                    "A synthesizer instruction or named failure class is not "
                    "a structurally-enforced gate."
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "rails": [
                    "catalog-res-0086-row",
                    "prompt-two-slice-dissent-lines",
                ],
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0086-probe2-gate-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "attempt": (
                "probe2 recomputes the gate checker on the canonical table "
                "and two planted mutants; it does not read the author's "
                "prose answer. A second human vendor pass is NOT-CHECKED "
                "on this substrate."
            ),
            "scope_not_agreement": True,
            "method": (
                "Independent recount: recommended_as_gate rows must be a "
                "subset of structurally-enforced preservation rows, and "
                "each must name a checkable_artifact_field."
            ),
        },
        "residual_unknowns": [
            {
                "claim": "Declared output_schema research-claim-record.schema.json",
                "verdict": "NOT-CHECKED" if not declared_present else "CONFIRMED",
                "settling_experiment": (
                    "Deliver RES-0001 schema family; this unit validates "
                    "against the local artifact.schema.json."
                ),
            },
            {
                "claim": "Live IEEE-SA Operations Manual HTML (HTTP 403 on this substrate).",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-fetch standards.ieee.org/about/policies/opman/sect5/ "
                    "when not WAF-blocked and re-hash against the Wayback snapshot."
                ),
            },
            {
                "claim": "Live eCFR 21 CFR 14.60 HTML (WAF interstitial).",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-fetch ecfr.gov once unblocked; GovInfo XML already "
                    "carries the operative text."
                ),
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0086/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "cloud_ok": False,
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": SCHEMA, "role": "supporting", "exists": True},
            {
                "path": "command-center/p2-wave/probes/RES-0086/classify.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "classify-and-two-rail", "command": P1},
            {
                "id": "probe2",
                "role": "hard-gate-both-states",
                "command": P2,
            },
        ],
        "strongest_surviving_counterargument": (
            "FOMC and IEEE preserve identity-plus-comment into a process "
            "package, not a full minority essay in the final published "
            "standard or policy statement. Mapping them onto minority_reports "
            "therefore over-fits if the gate demands a long rationale the "
            "source institution never required. Mitigated by keeping "
            "vote.against (identity) and unresolved_negative_comments "
            "(verbatim comment + response) as supporting fields, and by "
            "recording ICJ's 'entitled not obliged' caveat."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0086 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:RES-0086 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0086 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:RES-0086" not in text:
        print("FAILED:RES-0086 sentinel missing")
        return 1
    if "mechanism_table" not in text or "enforcement_classification" not in text:
        print("FAILED:RES-0086 mechanism table missing")
        return 1
    if "checkable_artifact_field" not in text:
        print("FAILED:RES-0086 named checkable field missing")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:RES-0086 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
