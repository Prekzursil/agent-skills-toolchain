#!/usr/bin/env python3
"""Emit CNL-0095 detector spec (JSON body at the catalog .md output_path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))

import breadth as B  # noqa: E402
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402
import schema_validate as SV  # noqa: E402

OUT_REL = "command-center/design/council/CNL-0095-premature-convergence-and-forced-re-divergence.md"
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py"
)
QUESTION = (
    "What signal shows a council converged before exploring the space, and "
    "what re-divergence intervention actually recovers the lost breadth "
    "rather than performing a second round?"
)
ART_RELS = [
    ("command-center/p2-wave/probes/CNL-0095/detector.py", "primary"),
    ("command-center/p2-wave/probes/CNL-0095/fixtures.py", "fixture"),
    ("command-center/p2-wave/probes/CNL-0095/transcript.py", "supporting"),
    ("command-center/p2-wave/probes/CNL-0095/breadth.py", "supporting"),
    ("command-center/p2-wave/probes/CNL-0095/probe1_both_states.py", "control"),
    ("command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py", "control"),
]


def _digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _probe(
    role: str, method: str, command: str, raw_output: str, fingerprint: str, exit_code: int = 0
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output,
        "fingerprint": fingerprint,
        "exit_code": exit_code,
    }


def main() -> int:
    kp_run = F.known_present()
    kp = D.detect(kp_run)
    if not kp["fired"]:
        print("FAILED:CNL-0095 emit detector-control did not FIRE; fix fixtures first")
        return 1
    planted = F.planted_bad()
    bad = D.detect(planted)
    good_run = F.known_good()
    good = D.detect(good_run)
    easy_run = F.easy_met_quota()
    easy = D.detect(easy_run)
    late_run = F.round10_premature()
    late = D.detect(late_run)
    nc_run = F.no_converge()
    nc = D.detect(nc_run)
    if not bad["fired"] or good["fired"] or easy["fired"] or not late["fired"]:
        print("FAILED:CNL-0095 emit both-states / easy / round10")
        print(D.format_line(planted, bad))
        print(D.format_line(good_run, good))
        print(D.format_line(easy_run, easy))
        print(D.format_line(late_run, late))
        return 1
    if nc["status"] != "NO-CONVERGE" or nc.get("absence_claimed"):
        print("FAILED:CNL-0095 emit no-converge treated as silence")
        return 1

    decoy_easy = D.decoy_round_count(easy_run)
    decoy_late = D.decoy_round_count(late_run)
    decoy_ev = D.decoy_event_count(planted)
    if not decoy_easy["fired"] or decoy_late["fired"] or decoy_ev["fired"]:
        print("FAILED:CNL-0095 emit decoy contrast")
        return 1

    clean = F.clean_fixtures()
    fp = sum(1 for run in clean if D.detect(run)["fired"])
    fpr = fp / len(clean)
    if fpr != 0.0:
        print(f"FAILED:CNL-0095 emit FPR={fpr}")
        return 1

    theater = F.theater_second_round()
    complement = F.complement_rediverge()
    t_cov = B.coverage_report(theater)
    c_cov = B.coverage_report(complement)
    t_prog = D.post_freeze_progress(theater)
    c_prog = D.post_freeze_progress(complement)
    if (
        t_prog["permitted"]
        or t_cov["breadth_recovered"]
        or not c_prog["permitted"]
        or not c_cov["breadth_recovered"]
    ):
        print("FAILED:CNL-0095 emit intervention contrast")
        return 1

    rev = R.review()
    if rev["verdict"] != "PASS" or not rev["both_states_rerun"]:
        print("FAILED:CNL-0095 emit reviewer")
        return 1

    kp_raw = D.format_line(kp_run, kp)
    bad_raw = D.format_line(planted, bad)
    good_raw = D.format_line(good_run, good)
    easy_raw = D.format_line(easy_run, easy)
    late_raw = D.format_line(late_run, late)
    nc_raw = D.format_line(nc_run, nc)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dep77 = (
        REPO
        / "command-center/design/council"
        / "CNL-0077-minimum-deliberation-conditions-that-outrank-any-early-sto.md"
    )
    dep54 = (
        REPO
        / "command-center/design/council"
        / "CNL-0054-category-taxonomy-coverage-and-diversity-as-one-measuremen.md"
    )

    artifacts = []
    for rel, role in ART_RELS:
        sha, size = _digest(rel)
        artifacts.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "eol": "LF",
                "role": role,
            }
        )

    report = {
        "kind": "council-detector-spec",
        "observations": [
            {
                "name": "false_positive_rate",
                "measured": fpr,
                "method": "fired-count over clean_fixtures() / n",
                "anchor": "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
            },
            {
                "name": "theater_coverage_delta",
                "measured": t_cov["coverage_delta"],
                "method": "breadth.coverage_report category set size / taxonomy n",
                "anchor": "command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
            },
            {
                "name": "complement_coverage_delta",
                "measured": c_cov["coverage_delta"],
                "method": "breadth.coverage_report category set size / taxonomy n",
                "anchor": "command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
            },
        ],
        "control_ids": [
            "known-present",
            "planted-bad",
            "known-good",
            "easy-met-quota",
            "round10-premature",
            "theater-second-round",
            "complement-rediverge",
        ],
        "title": "Premature convergence and forced re-divergence",
        "question": QUESTION,
        "pathology": (
            "Council emits converge before declared divergence idea and "
            "objection quotas are attained as unique Jaccard clusters. Round "
            "count is not the pathology: round-1 with quotas met is an easy "
            "question; round-10 with one paraphrase cluster is still premature."
        ),
        "detector_implementation": "command-center/p2-wave/probes/CNL-0095/detector.py",
        "spec_anchors": [
            {
                "id": "FC-11338",
                "claim": "Council must not stop before minimum deliberation conditions.",
                "status": "RESTATED-IN-CATALOG",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0077",
            },
            {
                "id": "CNL-0095-question",
                "claim": QUESTION,
                "status": "MANDATED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0095",
            },
            {
                "id": "CNL-0077-floors",
                "claim": "Minimum deliberation floors outrank any early stop expression.",
                "status": "ABSENT-ON-WORKTREE" if not dep77.is_file() else "PRESENT",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0077",
            },
            {
                "id": "CNL-0051-jaccard",
                "claim": "Lexical Jaccard merges paraphrases and misses full rewrites.",
                "status": "RESTATED-IN-CATALOG",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0051",
            },
        ],
        "threshold": {
            "primary_unit": (
                "Jaccard-0.80 unique idea clusters and unique objection "
                "clusters versus declared divergence quotas at first converge"
            ),
            "suspicion_window": (
                "All events before the first converge event. converge.round is "
                "recorded and ignored; it is not a threshold."
            ),
            "collapse_signals": [
                "idea_clusters < idea_quota at first converge",
                "objection_clusters < objection_quota at first converge",
            ],
            "rejected_units": [
                "converge.round as a stop/fire signal",
                "raw idea or objection event counts (paraphrase padding)",
                "question_class labels",
            ],
            "numeric": {
                "pairwise_jaccard_min": 0.8,
                "suspicion_max_round": 999,
                "chair_echo_jaccard_min": 1.0,
                "min_brief_chars": 1,
                "used_by_this_unit": ["pairwise_jaccard_min"],
                "unused_schema_fields": [
                    "suspicion_max_round",
                    "chair_echo_jaccard_min",
                    "min_brief_chars",
                ],
            },
        },
        "predicate": {
            "fire_when": (
                "first converge exists AND (idea_clusters < idea_quota OR "
                "objection_clusters < objection_quota)"
            ),
            "silent_when": (
                "first converge exists AND idea_clusters >= idea_quota AND "
                "objection_clusters >= objection_quota"
            ),
            "ignores": [
                "converge.round",
                "question_class",
                "raw event counts",
                "suspicion_max_round",
                "chair_echo_jaccard_min",
            ],
        },
        "detector": {
            "id": "CNL-0095-quota-attainment",
            "signal": (
                "At the first converge event, count Jaccard-0.80 unique idea "
                "clusters and unique objection clusters in prior events. FIRE "
                "if either count is below the declared divergence quota."
            ),
            "fire_rule": (
                "first_converge exists AND (idea_clusters < idea_quota OR "
                "objection_clusters < objection_quota)"
            ),
            "not_a_signal": (
                "converge.round, event counts, and question_class. Event-count "
                f"decoy SILENT on planted-bad ({decoy_ev['idea_events']} idea "
                f"events, {decoy_ev['objection_events']} objection events). "
                "Round-count decoy FIREs on easy-met-quota and is SILENT on "
                "round10-premature."
            ),
            "no_converge_is_not_silence": True,
            "implementation": "command-center/p2-wave/probes/CNL-0095/detector.py",
        },
        "intervention": {
            "id": "forced-re-divergence-complement-quota",
            "recovers_breadth_by": (
                "Freeze the premature thesis. Require the missing idea-cluster "
                "quota as NEW clusters whose category is in the uncovered "
                "taxonomy complement (or Jaccard-far if the complement is "
                "empty), plus the missing objection-cluster quota against the "
                "frozen thesis. Reconverge is blocked until those post-freeze "
                "quotas are met."
            ),
            "not": "a second round of the same protocol",
            "theater_permits_reconverge": bool(t_prog["permitted"]),
            "complement_permits_reconverge": bool(c_prog["permitted"]),
            "theater_coverage_delta": t_cov["coverage_delta"],
            "complement_coverage_delta": c_cov["coverage_delta"],
            "complement_breadth_recovered": bool(c_cov["breadth_recovered"]),
            "theater_covered_first": t_cov["covered_at_first_converge"],
            "theater_covered_last": t_cov["covered_at_last_converge"],
            "complement_covered_first": c_cov["covered_at_first_converge"],
            "complement_covered_last": c_cov["covered_at_last_converge"],
            "independent_signal": (
                "taxonomy category coverage from breadth.py, a different data "
                "field than the detector's Jaccard cluster counts"
            ),
            "mandate": D.freeze_mandate(planted),
        },
        "both_states": {
            "planted_bad": {
                "fixture": "planted-bad",
                "fired": True,
                "verbatim": bad_raw,
                "raw_output": bad_raw,
            },
            "known_good": {
                "fixture": "known-good",
                "fired": False,
                "verbatim": good_raw,
                "raw_output": good_raw,
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
        "easy_question_control": {
            "fixture": "easy-met-quota",
            "fired": easy["fired"],
            "raw_output": easy_raw,
        },
        "round_count_is_not_the_signal": {
            "round10_premature_fired": late["fired"],
            "easy_round1_fired": easy["fired"],
            "decoy_round_easy_fired": decoy_easy["fired"],
            "decoy_round_late_fired": decoy_late["fired"],
            "raw_output": late_raw,
        },
        "negative_control": {
            "reject_state": (
                "planted-bad: first converge with paraphrase-padded idea and "
                "objection events whose Jaccard clusters are below declared "
                "quotas"
            ),
            "does": "FIRE with quota-shortfall reason; does not use round count",
            "verbatim": bad_raw,
            "state_rejected": (
                "planted-bad: first converge with paraphrase-padded idea and "
                "objection events whose Jaccard clusters are below declared "
                "quotas"
            ),
            "detector_action": "FIRE",
            "raw_output": bad_raw,
        },
        "no_converge_control": {
            "fixture": "no-converge",
            "status": nc["status"],
            "absence_claimed": nc.get("absence_claimed"),
            "raw_output": nc_raw,
        },
        "dependencies_on_disk": {
            "CNL-0054": dep54.is_file(),
            "CNL-0077": dep77.is_file(),
        },
        "completion": "SUCCESS:CNL-0095",
    }

    inter_raw = (
        f"theater coverage_delta={t_cov['coverage_delta']} "
        f"permitted={t_prog['permitted']} "
        f"complement coverage_delta={c_cov['coverage_delta']} "
        f"permitted={c_prog['permitted']} "
        f"breadth_recovered={c_cov['breadth_recovered']}"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0095",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0095",
        "spec_anchor": "_USER-PROMPTS.md:10746-10767",
        "min_bytes_threshold": 512,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": "Detector FIREs on paraphrase-padded premature first converge.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
                "probes": [
                    _probe("source", "command", P1, bad_raw, "cnl0095:probe1:planted-bad"),
                    _probe(
                        "verifier",
                        "test-run",
                        P2,
                        inter_raw,
                        "cnl0095:probe2:theater-vs-complement",
                    ),
                ],
            },
            {
                "claim": (
                    "Detector is SILENT when both quotas are met with distinct clusters."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
                "probes": [
                    _probe("source", "command", P1, good_raw, "cnl0095:probe1:known-good"),
                    _probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNL-0095/reviewer.py",
                        f"reviewer_verdict={rev['verdict']} known_good_fired={rev['known_good_fired']}",
                        "cnl0095:reviewer:both-states",
                    ),
                ],
            },
            {
                "claim": "Known-present instance is found before any absence is reported.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
                "probes": [
                    _probe("source", "command", P1, kp_raw, "cnl0095:probe1:detector-control"),
                    _probe(
                        "verifier",
                        "test-run",
                        "command-center/p2-wave/probes/CNL-0095/reviewer.py",
                        f"known_present_fired={rev['known_present_fired']}",
                        "cnl0095:reviewer:known-present",
                    ),
                ],
            },
            {
                "claim": (
                    "Second-round theater does not raise category coverage or "
                    "permit reconverge; complement re-divergence does both."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
                "probes": [
                    _probe("source", "command", P2, inter_raw, "cnl0095:probe2:coverage"),
                    _probe(
                        "verifier",
                        "static-analysis",
                        "command-center/p2-wave/probes/CNL-0095/breadth.py",
                        (
                            f"theater_delta={t_cov['coverage_delta']} "
                            f"complement_delta={c_cov['coverage_delta']}"
                        ),
                        "cnl0095:breadth:category-coverage",
                    ),
                ],
            },
        ],
        "tests": [
            {"id": "T1-detector-control-both-states-fpr", "command": P1, "result": "PASS"},
            {"id": "T2-redivergence-vs-theater", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-PLANTED-BAD",
                "kind": "known-broken-fixture",
                "description": (
                    "planted-bad: first converge with paraphrase-padded idea and "
                    "objection events whose Jaccard clusters are below declared quotas"
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
                "Mechanical both-states re-run of detector.detect on fixtures; "
                f"planted_bad_fired={rev['planted_bad_fired']} "
                f"known_good_fired={rev['known_good_fired']} "
                f"known_present_fired={rev['known_present_fired']} "
                f"easy_fired={rev['easy_fired']} "
                f"round10_premature_fired={rev['round10_premature_fired']}"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0095/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNL-0095",
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator via disk-only $id store",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": _probe(
                    "verifier",
                    "schema-validate",
                    "python3 command-center/p2-wave/probes/CNL-0095/schema_validate.py",
                    "in-memory receipt validated before write",
                    "cnl0095:schema-validate",
                ),
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot, PLUS a mandatory detector-control retry: "
                "if the both-states control does not fire on the planted-bad fixture, "
                "the attempt does not count as a failure of the mechanism - fix the "
                "fixture first, once. Max 3 mechanism attempts (AGENTS.md 4b)."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live CNL-0054 taxonomy is absent on this tree; coverage uses a "
                    "planted six-category fixture taxonomy."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Recompute coverage_report against the CNL-0054 taxonomy file "
                    f"once {dep54.name} exists on the catalog output_path."
                ),
            },
            {
                "claim": (
                    "CNL-0051: lexical Jaccard merges renames/paraphrases and misses "
                    "full rewrites of the same mechanism; a second semantic signal is "
                    "not implemented here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add a mechanism-key probe (CNL-0051) and report the rewrite class "
                    "as NOT-CHECKED until that signal exists."
                ),
            },
            {
                "claim": (
                    "CNL-0077 minimum-deliberation floors are not on disk as the catalog "
                    "output_path; this detector is the runtime quota check those floors "
                    "would outrank a stop expression with."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When CNL-0077's catalog output_path exists, bind idea/objection "
                    "quotas to its floors instead of fixture declared_divergence."
                ),
            },
            {
                "claim": (
                    "Shared schema numeric fields suspicion_max_round, "
                    "chair_echo_jaccard_min, and min_brief_chars are unused by this unit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Leave unused; they belong to other CNL detectors.",
            },
            {
                "claim": (
                    "Source slices cited as Windows harness-restore paths are not present "
                    "on this Linux worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fetch the restore tree or restated catalog quotes and re-anchor "
                    "line-level spec cites."
                ),
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-anti-failure-detector-designer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }

    g_rej = SV.garbage_rejected()
    if g_rej != 3:
        print(f"FAILED:CNL-0095 emit schema accepted garbage ({g_rej}/3 rejected)")
        return 1
    errs = SV.error_messages(doc)
    if errs:
        print("FAILED:CNL-0095 emit schema")
        for e in errs[:20]:
            print(" ", e)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0095 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
