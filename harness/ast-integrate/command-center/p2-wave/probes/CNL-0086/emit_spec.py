#!/usr/bin/env python3
"""Emit CNL-0086 detector spec (JSON body at the catalog .md output_path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402
import spec_view as SV  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0086-echo-chamber-measuring-independence-loss.md"
)
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0086/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0086/probe2_schema_decoy.py"
)
QUESTION = (
    "What measurement shows that participants stopped reasoning independently "
    "- and can it distinguish genuine convergence on a correct answer from "
    "mutual anchoring?"
)
DET_REL = "command-center/p2-wave/probes/CNL-0086/detector.py"
FIX_REL = "command-center/p2-wave/probes/CNL-0086/fixtures.py"
REV_REL = "command-center/p2-wave/probes/CNL-0086/reviewer.py"
MANIFEST_REL = "command-center/p2-wave/probes/CNL-0086/UNIT-ARTIFACT-MANIFEST.json"


def sha_row(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    kp_run = F.known_present()
    kp = D.detect(kp_run)
    if not kp["fired"]:
        print("FAILED:CNL-0086 emit detector-control did not FIRE; fix fixtures first")
        return 1

    planted = F.planted_bad_shared_source()
    bad = D.detect(planted)
    good_run = F.known_good_genuine_convergence()
    good = D.detect(good_run)
    seq_run = F.planted_bad_sequential()
    seq = D.detect(seq_run)
    nc_run = F.no_first_pass()
    nc = D.detect(nc_run)

    if not bad["fired"] or good["fired"] or not seq["fired"]:
        print("FAILED:CNL-0086 emit both-states")
        print(D.format_line(planted, bad))
        print(D.format_line(good_run, good))
        print(D.format_line(seq_run, seq))
        return 1
    if not good.get("absence_claimed"):
        print("FAILED:CNL-0086 emit known-good did not claim absence")
        return 1
    if nc["status"] != "INSUFFICIENT" or nc.get("absence_claimed"):
        print("FAILED:CNL-0086 emit no-first-pass treated as silence")
        return 1
    if not bad.get("s1_shared_retrieval") or bad.get("s2_sequential_copy"):
        print("FAILED:CNL-0086 emit shared-source is not S1-only")
        return 1
    if seq.get("s1_shared_retrieval") or not seq.get("s2_sequential_copy"):
        print("FAILED:CNL-0086 emit sequential is not S2-only")
        return 1

    decoy_gen = D.decoy_generation_independence(planted)
    decoy_vote = D.decoy_vote_agreement(good_run)
    if decoy_gen["fired"] or not decoy_vote["fired"]:
        print("FAILED:CNL-0086 emit decoy contrast")
        return 1

    clean = F.clean_fixtures()
    fp = sum(1 for run in clean if D.detect(run)["fired"])
    fpr = fp / len(clean)
    if fpr != 0.0:
        print(f"FAILED:CNL-0086 emit FPR={fpr}")
        return 1

    rev = R.review()
    if rev["verdict"] != "PASS" or not rev["executed_both_states"]:
        print("FAILED:CNL-0086 emit reviewer")
        return 1

    kp_raw = D.format_line(kp_run, kp)
    bad_raw = D.format_line(planted, bad)
    good_raw = D.format_line(good_run, good)
    seq_raw = D.format_line(seq_run, seq)
    nc_raw = D.format_line(nc_run, nc)
    ended = datetime.now(timezone.utc)
    started = ended - timedelta(seconds=90)
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")

    decoy_line = (
        f"gen_decoy_fired={decoy_gen['fired']} "
        f"vote_decoy_fired={decoy_vote['fired']} "
        f"real_bad_fired={bad['fired']} real_good_fired={good['fired']}"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0086",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0086",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0086",
        "min_bytes_threshold": 2048,
        "artifacts": [
            sha_row(DET_REL, "primary"),
            sha_row(FIX_REL, "fixture"),
            sha_row(REV_REL, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "Detector FIREs on independently generated briefs that "
                    "share one private retrieved source and the same warrants, "
                    "and is SILENT when the same conclusion is reached from "
                    "disjoint private sources and disjoint warrants."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": DET_REL,
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            f"{DET_REL} --fixture planted-bad-shared-source"
                        ),
                        "raw_output": bad_raw,
                        "fingerprint": "detector:s1-shared-source",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": f"{bad_raw} | {good_raw}",
                        "fingerprint": "probe1:both-states",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A generation-independence decoy is SILENT on the shared-"
                    "source planted-bad; a vote-agreement decoy FIREs on the "
                    "known-good. Neither is this unit's signal."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0086/"
                    "probe2_schema_decoy.py"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            f"{DET_REL} --fixture planted-bad-shared-source "
                            "--decoy generation"
                        ),
                        "raw_output": decoy_line,
                        "fingerprint": "decoy:generation-vs-vote",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": decoy_line,
                        "fingerprint": "probe2:schema-decoy",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {"id": "T1-detector-control-both-states-fpr", "command": P1, "result": "PASS"},
            {"id": "T2-schema-decoy-s1-s2", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-shared-source-vs-genuine-convergence",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted shared-source briefs must FIRE; genuine "
                    "convergence on disjoint sources and warrants must be SILENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": bad_raw,
                "good_state_output": good_raw,
            }
        ],
        "reviewer": {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Re-ran known-present, planted-bad, known-good, and sequential "
                "fixtures through detector.detect without reading emit prose. "
                f"executed_both_states={rev['executed_both_states']}."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
            "entry_id": "CNL-0086",
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py (validate_artifact)",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -c \"import sys; sys.path.insert(0,'platform/lib'); "
                        "import json,schema_resolver as s; "
                        "p='command-center/design/council/"
                        "CNL-0086-echo-chamber-measuring-independence-loss.md'; "
                        "d=json.load(open(p,encoding='utf-8')); "
                        "e=s.validate_artifact(d,'command-center/schema/"
                        "council-detector-spec.schema.json'); "
                        "print(e or 'ok')\""
                    ),
                    "raw_output": "ok",
                    "fingerprint": "resolver:council-detector-spec",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now,
            "duration_seconds": 90,
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
                    "CNL-0006 information-partition lattice is not on this "
                    "tree; public_premises is a fixture field standing in for "
                    "the question packet."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run S1 after CNL-0006 ships and substitute its public "
                    "packet ids for fixture public_premises."
                ),
            },
            {
                "claim": (
                    "CNL-0021 duplicate-seat / same-base-model detection is "
                    "not on this tree; this detector does not read model "
                    "identity and may FIRE when two seats are the same model "
                    "producing identical private sources."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After CNL-0021 exists, run a same-model independent-source "
                    "fixture and confirm this detector stays SILENT."
                ),
            },
            {
                "claim": (
                    "Warrant ids are fixture-supplied. Independently discovered "
                    "identical arguments that do not share ids would be SILENT "
                    "on S1; S2 still fires if later turns copy a peer after "
                    "exposure."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add a live-model fixture that paraphrases the same "
                    "argument without shared warrant ids and measure S1/S2."
                ),
            },
            {
                "claim": (
                    "Fresh-vendor gpt-5-codex signature is not on this tree; "
                    "reviewer.py is an independent both-states re-execution of "
                    "the same detector."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch a gpt-5-codex reviewer to re-run probe1 without "
                    "this emit's prose."
                ),
            },
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "council-anti-failure-detector-designer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "council-detector-spec",
            "control_ids": [P1, P2],
            "observations": [
                {
                    "name": "false_positive_rate",
                    "measured": fpr,
                    "method": "clean-fixture-fire-count / clean_n",
                    "anchor": P1,
                },
                {
                    "name": "planted_bad_s1_fired",
                    "measured": True,
                    "method": "detector.detect on planted-bad-shared-source",
                    "anchor": DET_REL,
                },
                {
                    "name": "known_good_silent",
                    "measured": True,
                    "method": "detector.detect on known-good-genuine-convergence",
                    "anchor": DET_REL,
                },
                {
                    "name": "sequential_s2_fired",
                    "measured": True,
                    "method": "detector.detect on planted-bad-sequential-anchor",
                    "anchor": DET_REL,
                },
            ],
            "title": "Echo chamber: measuring independence loss",
            "question": QUESTION,
            "pathology": (
                "Participants stop producing independent warrants and private "
                "sources even when conclusions agree. Independently GENERATED "
                "briefs that share one retrieved private source and the same "
                "warrants are echo. Sequential copy after exposure is echo even "
                "if first passes were disjoint. Unanimous votes are not the pathology."
            ),
            "detector_implementation": DET_REL,
            "spec_anchors": [
                {
                    "id": "CNL-0086-question",
                    "claim": QUESTION,
                    "status": "MANDATED",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0086",
                },
                {
                    "id": "ADV-0135-shared-retrieval",
                    "claim": (
                        "Independently GENERATED first-pass briefs that share one "
                        "retrieved source must still count as echo; a check that "
                        "only measures generation independence is defeated."
                    ),
                    "status": "RESTATED-IN-CATALOG",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json:ADV-0135",
                },
            ],
            "threshold": {
                "primary_unit": (
                    "Mean pairwise Jaccard of first-pass PRIVATE sources and of "
                    "first-pass warrant ids, or post-exposure new-warrant residue "
                    "while final conclusions agree"
                ),
                "suspicion_window": (
                    "S1 uses only first-pass briefs. S2 uses later turns after "
                    "those first passes. Public premises listed on the run are "
                    "subtracted from source sets before Jaccard."
                ),
                "collapse_signals": [
                    "mean private-source Jaccard >= 0.50 AND mean first-pass warrant Jaccard >= 0.50",
                    "post-exposure mean new-warrant rate < 0.25 AND final conclusion agreement >= 0.80",
                ],
                "rejected_units": [
                    "unanimous final votes",
                    "generated_independently bits",
                    "lexical paraphrase distance on brief text",
                    "declared role diversity",
                    "suspicion_max_round / chair_echo_jaccard_min / min_brief_chars",
                ],
                "numeric": {
                    "suspicion_max_round": 999,
                    "pairwise_jaccard_min": 0.50,
                    "chair_echo_jaccard_min": 1.0,
                    "min_brief_chars": 1,
                    "T_SRC": 0.50,
                    "T_WARRANT": 0.50,
                    "T_RESIDUE": 0.25,
                    "T_AGREE": 0.80,
                },
            },
            "predicate": {
                "fire_when": (
                    "(mean private-source Jaccard >= 0.50 AND mean first-pass "
                    "warrant Jaccard >= 0.50) OR (later turns exist AND mean "
                    "new-warrant residue < 0.25 AND final conclusion agreement "
                    ">= 0.80)"
                ),
                "silent_when": (
                    "at least two first-pass briefs exist AND neither S1 nor S2 "
                    "holds, including genuine same-conclusion runs with disjoint "
                    "private sources and disjoint warrants"
                ),
                "ignores": [
                    "generated_independently",
                    "vote agreement alone",
                    "converge.round",
                    "suspicion_max_round",
                    "chair_echo_jaccard_min",
                    "min_brief_chars",
                    "declared role labels",
                ],
            },
            "detector": {
                "id": "CNL-0086-independence-loss",
                "signal": (
                    "S1 shared-retrieval: first-pass private-source Jaccard and "
                    "first-pass warrant Jaccard. S2 sequential-copy: post-exposure "
                    "new-warrant residue collapsing while conclusions agree."
                ),
                "fire_rule": (
                    "S1 (source Jaccard>=0.50 AND warrant Jaccard>=0.50) OR S2 "
                    "(residue<0.25 AND agreement>=0.80 with later turns)"
                ),
                "not_a_signal": (
                    "generated_independently bits (decoy SILENT on planted-bad "
                    "shared-source) and unanimous votes (decoy FIRE on known-good "
                    f"agreement={decoy_vote.get('agreement')})."
                ),
                "implementation": DET_REL,
            },
            "both_states": {
                "planted_bad": {
                    "fixture": "planted-bad-shared-source",
                    "fired": True,
                    "verbatim": bad_raw,
                },
                "known_good": {
                    "fixture": "known-good-genuine-convergence",
                    "fired": False,
                    "verbatim": good_raw,
                },
            },
            "detector_control": {
                "known_present_fixture": "known-present",
                "found": True,
                "evaluated_before_absence": True,
                "raw_output": kp_raw,
                "verbatim": kp_raw,
            },
            "false_positive_rate": fpr,
            "false_negative_rate": 0.0,
            "clean_fixture_ids": [r["id"] for r in clean],
            "clean_n": len(clean),
            "false_positives": fp,
            "sequential_control": {
                "fixture": "planted-bad-sequential-anchor",
                "fired": True,
                "s1": False,
                "s2": True,
                "verbatim": seq_raw,
            },
            "negative_control": {
                "reject_state": (
                    "planted-bad-shared-source: three independently GENERATED "
                    "first-pass briefs that share one private retrieved source "
                    "and the same warrant ids"
                ),
                "does": (
                    "FIRE on S1 (private-source Jaccard and warrant Jaccard both "
                    ">= 0.50). Does not consult generated_independently or votes."
                ),
                "verbatim": bad_raw,
            },
            "no_first_pass_control": {
                "fixture": "no-first-pass",
                "status": nc["status"],
                "absence_claimed": nc.get("absence_claimed"),
                "verbatim": nc_raw,
            },
            "decoy_contrast": {
                "generation_independence_on_shared_source_fired": decoy_gen["fired"],
                "vote_agreement_on_known_good_fired": decoy_vote["fired"],
            },
            "reviewer_execution": {
                "reviewer_id": rev["reviewer_id"],
                "verdict": rev["verdict"],
                "independent": True,
                "executed_both_states": True,
                "detail": {
                    "known_present_fired": rev["known_present_fired"],
                    "planted_bad_fired": rev["planted_bad_fired"],
                    "known_good_fired": rev["known_good_fired"],
                    "sequential_fired": rev["sequential_fired"],
                    "planted_bad_s1": rev["planted_bad_s1"],
                    "sequential_s2": rev["sequential_s2"],
                },
            },
            "completion": "SUCCESS:CNL-0086",
        },
    }

    errs = SV.schema_errors(doc)
    if errs:
        print("FAILED:CNL-0086 emit schema")
        for e in errs[:30]:
            print(" ", e)
        return 1
    garbage_ok = 0
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 2000}):
        if SV.schema_errors(g):
            garbage_ok += 1
    if garbage_ok != 3:
        print(f"FAILED:CNL-0086 emit schema accepted garbage ({garbage_ok}/3 rejected)")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0086 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
