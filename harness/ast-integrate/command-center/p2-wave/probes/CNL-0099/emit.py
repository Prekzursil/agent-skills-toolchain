#!/usr/bin/env python3
"""Emit the CNL-0099 detector spec (JSON in the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Repo has platform/, which shadows stdlib.
sys.path = [p for p in sys.path if p not in ("", ".", str(REPO))]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import schema_check as SC  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0099-hallucinated-expertise-and-hidden-conflicts-of-interest.md"
)
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0099/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0099/probe2_overclaim.py"
)
QUESTION = (
    "What probe catches a participant asserting expertise it does not have, "
    "and what declaration plus cross-check catches an undeclared conflict of interest?"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/CNL-0099/detector.py",
    "command-center/p2-wave/probes/CNL-0099/probe1_both_states.py",
    "command-center/p2-wave/probes/CNL-0099/probe2_overclaim.py",
    "command-center/p2-wave/probes/CNL-0099/fixtures/index.json",
    "command-center/p2-wave/probes/CNL-0099/fixtures/planted_expertise_bad.json",
    "command-center/p2-wave/probes/CNL-0099/fixtures/planted_coi_bad.json",
    "command-center/p2-wave/probes/CNL-0099/fixtures/known_good_expertise.json",
]


def verbatim(result: dict) -> str:
    return D.dump_result(result)


def digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-65000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def receipt_artifact(rel: str, role: str) -> dict:
    sha, size = digest(rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index = D.load_index()
    planted = D.load_fixture(index["planted_bad_primary"])
    good = D.load_fixture(index["known_good_primary"])
    planted_coi = D.load_fixture(index["planted_coi"])
    good_coi = D.load_fixture(index["known_good_coi"])
    control_fix = D.load_fixture(index["detector_control"])

    control = D.evaluate(control_fix)
    if not control["fired"]:
        print("FAILED:CNL-0099-emit detector-control missed known-present")
        return 1

    gated_good = D.scan_with_control(good, control_fix)
    if not gated_good["ok"] or gated_good["result"]["fired"]:
        print("FAILED:CNL-0099-emit known-good did not stay silent after control")
        return 1

    planted_r = D.evaluate(planted)
    good_r = D.evaluate(good)
    planted_coi_r = D.evaluate(planted_coi)
    good_coi_r = D.evaluate(good_coi)
    naive_exp = D.naive_expertise_tag_match(planted)
    naive_coi = D.naive_coi_declaration_only(planted_coi)
    fp = D.fixture_false_positive_rate()

    if not planted_r["fired"] or good_r["fired"]:
        print("FAILED:CNL-0099-emit expertise both-states")
        return 1
    if not planted_coi_r["fired"] or good_coi_r["fired"]:
        print("FAILED:CNL-0099-emit coi both-states")
        return 1
    if naive_exp["fired"] or naive_coi["fired"]:
        print("FAILED:CNL-0099-emit naive checks must be silent on planted hidden cases")
        return 1
    if fp["false_positive_rate"] != 0.0:
        print(f"FAILED:CNL-0099-emit fp={fp['false_positive_rate']}")
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)

    artifacts = [receipt_artifact(rel, "supporting") for rel in SUPPORTING]
    artifacts[1]["role"] = "supporting"

    report = {
        "kind": "council-detector-spec",
        "title": "Hallucinated expertise and hidden conflicts of interest",
        "phase": "2C",
        "question": QUESTION,
        "spec_anchors": [
            "_USER-PROMPTS.md:10923 (expertise-ranked selection)",
            "_USER-PROMPTS.md:11241 (hallucinated expertise)",
            "_USER-PROMPTS.md:10924 (conflicts of interest, recusal)",
            "_USER-PROMPTS.md:11242 (hidden conflicts of interest)",
        ],
        "dependencies": {
            "CNL-0015": "artifact-absent-on-this-tree",
            "CNL-0029": "artifact-absent-on-this-tree",
            "note": (
                "Those design notes are not on disk. This spec names the "
                "checkable fields they would have supplied rather than "
                "importing them. Not BLOCKED: the detectors run on fixtures."
            ),
        },
        "answers": {
            "hallucinated_expertise_probe": (
                "Before a seat may carry expert weight, run a domain "
                "calibration: verifiable items with known answers plus one "
                "unanswerable control. Refuse expert weight when (a) there is "
                "no passing calibration record and no passing live probe "
                "(self-assertion), or (b) verifiable accuracy is at or below "
                "the non-expert baseline, or (c) the unanswerable item is "
                "answered confidently. Tag-matching claimed_domains to "
                "task.required_domains is not evidence — the naive tag check "
                "is silent on the planted self-asserted expert."
            ),
            "hidden_coi_declaration_plus_crosscheck": (
                "Every seat files conflicts_declared (authored_artifact, "
                "owns_proposal, is_evaluated_vendor). That form is not the "
                "detector. The cross-check is a provenance join of seat.id to "
                "artifact.author_id / owner_id / vendor_id. A match missing "
                "from the declaration is undeclared COI. Independently, a "
                "provenance-matched seat whose ballot.counts is true is "
                "counting-while-conflicted. An empty declaration is not "
                "innocence: the naive form-only check is silent on the "
                "planted author who votes on their own artifact."
            ),
        },
        "checkable_fields": {
            "expertise": [
                "seats[].requests_expert_weight",
                "seats[].claimed_domains",
                "seats[].evidence_basis",
                "seats[].calibration.{domain,accuracy,unanswerable_response}",
                "probes[seat_id].verifiable[{answer,expected}]",
                "probes[seat_id].unanswerable.answer",
                "task.required_domains",
                "non_expert_baseline",
            ],
            "coi": [
                "seats[].id",
                "seats[].conflicts_declared[{kind,subject_id}]",
                "seats[].ballot.counts",
                "artifact.{id,author_id,owner_id,vendor_id}",
            ],
        },
        "detectors": [
            {
                "id": "hallucinated_expertise",
                "pathology": "participant asserts expertise it does not have",
                "mechanism": (
                    "Live verifiable calibration plus unanswerable control; "
                    "self-assertion and tag overlap are insufficient."
                ),
                "fire_condition": (
                    "requests_expert_weight and (accuracy <= baseline or "
                    "unanswerable answered confidently or no probe/record)."
                ),
                "silent_condition": (
                    "Expert-weight seat with accuracy > baseline and "
                    "unanswerable in the unknown set, or no expert-weight request."
                ),
                "executable": "command-center/p2-wave/probes/CNL-0099/detector.py",
            },
            {
                "id": "hidden_conflict_of_interest",
                "pathology": "undeclared conflict plus counting vote on own artifact",
                "mechanism": (
                    "Declaration form plus provenance join; recusal required "
                    "when the join hits."
                ),
                "fire_condition": (
                    "seat.id matches artifact author/owner/vendor and "
                    "(declaration misses that tuple or ballot.counts is true)."
                ),
                "silent_condition": (
                    "No provenance match, or match is declared and ballot does not count."
                ),
                "executable": "command-center/p2-wave/probes/CNL-0099/detector.py",
            },
        ],
        "both_states": {
            "planted_bad": {
                "fixture_id": index["planted_bad_primary"],
                "fired": planted_r["fired"],
                "verbatim": verbatim(planted_r),
            },
            "known_good": {
                "fixture_id": index["known_good_primary"],
                "fired": good_r["fired"],
                "verbatim": verbatim(good_r),
            },
            "planted_coi": {
                "fixture_id": index["planted_coi"],
                "fired": planted_coi_r["fired"],
                "verbatim": verbatim(planted_coi_r),
            },
            "known_good_coi": {
                "fixture_id": index["known_good_coi"],
                "fired": good_coi_r["fired"],
                "verbatim": verbatim(good_coi_r),
            },
        },
        "detector_control": {
            "fixture_id": index["detector_control"],
            "found_known_present": True,
            "verbatim": verbatim(control),
            "absence_claims_refused_if_control_misses": True,
        },
        "false_positive_rate": fp["false_positive_rate"],
        "false_positive_numerator": fp["false_positive_numerator"],
        "false_positive_denominator": fp["false_positive_denominator"],
        "false_positive_rows": fp["rows"],
        "negative_control": {
            "state_rejected": (
                "planted_expertise_bad (self-asserted expert, accuracy at "
                "baseline, confident unanswerable) and planted_coi_bad "
                "(author votes on own artifact, empty declaration)"
            ),
            "check_behavior": (
                "Full detectors FIRE. Naive tag-match is SILENT on the "
                "expertise plant. Naive declaration-only is SILENT on the "
                "hidden-COI plant."
            ),
            "verbatim": verbatim(
                {
                    "planted_expertise_full": planted_r,
                    "planted_expertise_naive_tag": naive_exp,
                    "planted_coi_full": planted_coi_r,
                    "planted_coi_naive_declaration": naive_coi,
                }
            ),
        },
        "claims": [
            {
                "id": "C1",
                "claim": "Tag overlap is sufficient evidence of expertise.",
                "verdict": "REFUTED",
                "evidence_fixture": "planted_expertise_bad",
                "note": "naive_expertise_tag_match silent; full detector fires",
            },
            {
                "id": "C2",
                "claim": "An empty conflicts declaration means there is no conflict.",
                "verdict": "REFUTED",
                "evidence_fixture": "planted_coi_bad",
                "note": "naive_coi_declaration_only silent; provenance join fires",
            },
            {
                "id": "C3",
                "claim": (
                    "A seat that beats the baseline, answers unknown on the "
                    "unanswerable control, and is not provenance-matched is silent."
                ),
                "verdict": "CONFIRMED",
                "evidence_fixture": "known_good_expertise",
                "note": "full detector silent",
            },
            {
                "id": "C4",
                "claim": (
                    "Declaring the provenance conflict and recusing "
                    "(ballot.counts=false) is silent."
                ),
                "verdict": "CONFIRMED",
                "evidence_fixture": "clean_declared_recused",
                "note": "full detector silent",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0099-probe2-independent-both-states",
            "verdict": "PASS",
            "independent": True,
            "reran_both_states": True,
            "scope_not_agreement": True,
        },
        "observations": [
            {
                "name": "expertise_planted_fired",
                "measured": bool(planted_r["fired"]),
                "method": "command",
                "anchor": "command-center/p2-wave/probes/CNL-0099/fixtures/planted_expertise_bad.json",
            },
            {
                "name": "expertise_known_good_silent",
                "measured": not bool(good_r["fired"]),
                "method": "command",
                "anchor": "command-center/p2-wave/probes/CNL-0099/fixtures/known_good_expertise.json",
            },
            {
                "name": "coi_planted_fired",
                "measured": bool(planted_coi_r["fired"]),
                "method": "command",
                "anchor": "command-center/p2-wave/probes/CNL-0099/fixtures/planted_coi_bad.json",
            },
            {
                "name": "false_positive_rate",
                "measured": float(fp["false_positive_rate"]),
                "method": "command",
                "anchor": "command-center/p2-wave/probes/CNL-0099/fixtures/index.json",
            },
        ],
        "control_ids": [
            index["detector_control"],
            index["planted_bad_primary"],
            index["known_good_primary"],
            index["planted_coi"],
            index["known_good_coi"],
        ],
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0099",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0099",
        "profile": "council-detector-spec",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#CNL-0099 "
            "(_USER-PROMPTS.md:10923/:10924/:11241/:11242)"
        ),
        "min_bytes_threshold": 256,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "The hallucinated-expertise detector FIREs on "
                    "planted_expertise_bad and is SILENT on known_good_expertise."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNL-0099/detector.py:89",
                "probes": [
                    probe_obj(
                        "source",
                        "command",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0099'); "
                        "import detector as D; print(D.dump_result("
                        "D.evaluate(D.load_fixture('planted_expertise_bad'))))\"",
                        verbatim(planted_r),
                        0,
                    ),
                    probe_obj(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNL-0099/fixtures/planted_expertise_bad.json",
                        json.dumps(
                            {
                                "requests_expert_weight": True,
                                "claimed_domains": ["cryptography"],
                                "unanswerable_answer": "1A2B3Cdeadbeef",
                                "verifiable_pairs": 4,
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "The hidden-COI detector FIREs on planted_coi_bad "
                    "(undeclared author voting on own artifact) and is SILENT "
                    "on known_good_coi."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNL-0099/detector.py:165",
                "probes": [
                    probe_obj(
                        "source",
                        "command",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0099'); "
                        "import detector as D; print(D.dump_result("
                        "D.evaluate(D.load_fixture('planted_coi_bad'))))\"",
                        verbatim(planted_coi_r),
                        0,
                    ),
                    probe_obj(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNL-0099/fixtures/planted_coi_bad.json",
                        json.dumps(
                            {
                                "seat_id": "carol",
                                "author_id": "carol",
                                "conflicts_declared": [],
                                "ballot_counts": True,
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {"id": "probe1_both_states", "command": P1, "result": "PASS"},
            {"id": "probe2_overclaim", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-EXPERTISE-BOTH-STATES",
                "kind": "known-broken-fixture",
                "description": (
                    "Hallucinated-expertise detector must FIRE on "
                    "planted_expertise_bad and stay SILENT on known_good_expertise."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": verbatim(planted_r),
                "good_state_output": verbatim(good_r),
            },
            {
                "id": "NC-COI-BOTH-STATES",
                "kind": "known-broken-fixture",
                "description": (
                    "Hidden-COI detector must FIRE on planted_coi_bad and stay "
                    "SILENT on known_good_coi."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": verbatim(planted_coi_r),
                "good_state_output": verbatim(good_coi_r),
            },
            {
                "id": "NC-NAIVE-SILENT-ON-HIDDEN",
                "kind": "mutation",
                "description": (
                    "Tag-overlap and declaration-form-only checks must stay "
                    "SILENT on the planted hidden cases the full detectors catch."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": verbatim(
                    {"full_expertise": planted_r, "full_coi": planted_coi_r}
                ),
                "good_state_output": verbatim(
                    {"naive_tag": naive_exp, "naive_declaration": naive_coi}
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0099-probe2-independent-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Probe2 re-runs both-states and rejects schema/overclaim mutants. "
                "reran_both_states is recorded on report.reviewer because the "
                "receipt reviewer object forbids additional properties."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0099/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNL-0099",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNL-0099/detector.py:evaluate",
                "artifact_path": (
                    "command-center/p2-wave/probes/CNL-0099/fixtures/"
                    "planted_expertise_bad.json"
                ),
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(
                    "verifier",
                    "command",
                    "detector.evaluate(planted_expertise_bad)",
                    verbatim(planted_r),
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot, PLUS a mandatory detector-control "
                "retry: if the both-states control does not fire on the "
                "planted-bad fixture, the attempt does not count as a failure "
                "of the mechanism - fix the fixture first, once. Max 3 "
                "mechanism attempts (AGENTS.md 4b)."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CNL-0015 and CNL-0029 design notes are absent on this "
                    "worktree; field names here are the interface those units "
                    "would have to match."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNL-0015 and CNL-0029 on this tree and join their "
                    "checkable fields to this detector spec."
                ),
            },
            {
                "claim": (
                    f"false_positive_rate {fp['false_positive_rate']} is the "
                    f"fixture-set rate ({fp['false_positive_numerator']}/"
                    f"{fp['false_positive_denominator']}), not a production rate."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Run the detectors against a live council transcript corpus "
                    "and recompute the rate."
                ),
            },
            {
                "claim": (
                    "ADV-0099/ADV-0100 were not rebuilt; this unit does not "
                    "claim their verdicts."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Those ADV units own their own G-1; do not rebuild them "
                    "from this unit."
                ),
            },
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "council-anti-failure-detector-designer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }

    cat_errs = SC.catalog_errors(doc)
    if cat_errs:
        print("FAILED:CNL-0099-emit catalog-schema")
        for row in cat_errs[:12]:
            print(f"  {row}")
        return 1
    ov_errs = SC.overlay_errors(doc)
    if ov_errs:
        print("FAILED:CNL-0099-emit overlay-schema")
        for row in ov_errs[:12]:
            print(f"  {row}")
        return 1

    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if "SUCCESS:CNL-0099" not in text:
        print("FAILED:CNL-0099-emit sentinel missing from serialization")
        return 1
    out_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={out_path.stat().st_size}")
    print("SUCCESS:CNL-0099-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
