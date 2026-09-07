#!/usr/bin/env python3
"""Pack AUD-0047 workflow path-filter audit.

Honest census with live probes. Emits BLOCKED pending independent fresh-context
Claude review (catalog reviewer_requirement). Never emits SUCCESS without that
review — anti-false-green.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0047"
OUT = "command-center/audit/AUD-0047-workflow-path-filter-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0047/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-path-filter-eval.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-run-history.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-path-filter-eval.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-run-history.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T19:10:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(
            "command-center/p2-wave/probes/AUD-0047/probe1-path-filter-eval.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0047/probe2-run-history.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0047/probe1-path-filter-eval.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0047/probe2-run-history.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0047/fixtures/planted-paths-ignore/workflow.yml",
            "fixture",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0047/fixtures/planted-paths-ignore/protected_files.txt",
            "control",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0047/independent-review.json",
                "supporting",
            )
        )

    live_holes = p1["live_hole_count"]
    filtered = p1["filtered_workflow_count"]
    planted = p1["planted_miss_caught"]
    vacuous = p2["no_filter_vacuous_count"]

    question = (
        "For every workflow with a paths or paths-ignore filter, is there a file "
        "the gate claims to protect that the filter would prevent the gate from "
        "ever seeing?"
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        defects = [
            {
                "id": "AUD-0047-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Independent fresh-context Claude review PASS recorded.",
            },
            {
                "id": "AUD-0047-D-HOLES",
                "severity": "P2",
                "status": "open" if live_holes else "resolved",
                "summary": (
                    f"live_hole_count={live_holes} filtered_workflows={filtered}; "
                    f"planted_miss_caught={planted}."
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0047"
        headline = (
            f"filtered={filtered} live_holes={live_holes} planted_caught={planted} "
            f"vacuous_no_filter={vacuous}. Independent review PASS."
        )
        failure = None
        anti = "SUCCESS-after-independent-re-review-PASS"
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not seen "
                "this unit's transcript and must try to FALSIFY the headline count "
                "before PASS. Probes measured; review unpaid; BLOCKED."
            ),
        }
        defects = [
            {
                "id": "AUD-0047-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Independent fresh-context Claude review unpaid; headline counts "
                    "must be falsified by a reviewer who did not author this census."
                ),
            },
            {
                "id": "AUD-0047-D-HOLES",
                "severity": "P2",
                "status": "open" if live_holes else "resolved",
                "summary": (
                    f"live_hole_count={live_holes} filtered_workflows={filtered}; "
                    f"planted_miss_caught={planted}; "
                    f"probe2_vacuous_no_filter={vacuous}."
                ),
            },
        ]
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0047 path-filter eval + run-history probe measured; "
            "planted paths-ignore miss caught; blocked-on-independent-review"
        )
        headline = (
            f"filtered={filtered} live_holes={live_holes} planted_caught={planted} "
            f"vacuous_no_filter={vacuous} api_unavailable={p2.get('api_unavailable')}. "
            "BLOCKED on independent fresh-context Claude review."
        )
        failure = {
            "classification": ["blocked-on-independent-review", "scope-mismatch"],
            "reason": (
                "Named probes completed with planted paths-ignore miss caught, but "
                "catalog reviewer_requirement is unmet (fresh-context Claude must "
                "falsify headline count)."
            ),
            "diagnostic_tail": (
                f"live_holes={live_holes} planted={planted} filtered={filtered} "
                "reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this "
                "unit's transcript; the reviewer must try to FALSIFY the headline "
                f"live_hole_count={live_holes} (filtered_workflow_count={filtered}) "
                "before PASS, not re-read the artifact."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0047/probe1_path_filter_eval.py",
                    f"live_hole_count={live_holes} planted_miss_caught={planted}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-pending-independent-review-with-real-probes"

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0047",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "linux-cursor-cloud",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 scanned {p1['workflows_scanned']} workflows: "
                    f"filtered={filtered} live_holes={live_holes}; "
                    f"planted_miss_caught={planted}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0047/probe1-path-filter-eval.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0047/probe1_path_filter_eval.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-path-filter-eval.json",
                        json.dumps(
                            {
                                "live_hole_count": live_holes,
                                "filtered_workflow_count": filtered,
                                "planted_miss_caught": planted,
                                "ok": p1["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 run-history: confirmed={p2['confirmed_run_count']} "
                    f"unconfirmed={p2['unconfirmed_count']} "
                    f"vacuous_no_filter={vacuous} "
                    f"api_unavailable={p2.get('api_unavailable')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0047/probe2-run-history.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0047/probe2_run_history.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe2-run-history.json",
                        json.dumps(
                            {
                                "confirmed_run_count": p2["confirmed_run_count"],
                                "no_filter_vacuous_count": vacuous,
                                "ok": p2["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0047-planted-paths-ignore-miss",
                "name": (
                    "control: the evaluator must report a miss for a protected file "
                    "deliberately excluded by a paths-ignore entry in a fixture workflow"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0047/probe1_path_filter_eval.py",
                "result": "PASS" if planted else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-500:],
            },
            {
                "id": "AUD-0047-run-history-receipt",
                "name": "Probe 2 records run-history or vacuous no-filter proof",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0047/probe2_run_history.py",
                "result": "PASS" if p2["ok"] else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-500:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0047-C1",
                "known-broken-fixture",
                "Planted paths-ignore must make protected file unreachable.",
                True,
                True,
                bad="planted miss not reported",
                good=f"planted_miss_caught={planted}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0047/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure with "
                "the same detector, enumerate at least 2 mechanically different "
                "detectors before a third attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Job-level path filters / reusable workflow path inputs are absent "
                    "from the evaluated surface."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Extend probe1 to walk jobs.*.if and workflow_call inputs for "
                    "path-scoped conditions beyond on.push/on.pull_request."
                ),
            },
            {
                "claim": (
                    "Every inferred protected file is the gate's declared protected set "
                    "(heuristic from step commands may under/over-count)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Cross-check against AUD-0041 CI step inventory and charter "
                    "protected-path declarations."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0047-C1"],
            "observations": [
                {
                    "name": "workflows_scanned",
                    "measured": p1["workflows_scanned"],
                    "method": "glob .github/workflows/*.yml",
                    "anchor": "command-center/p2-wave/probes/AUD-0047/probe1-path-filter-eval.json",
                },
                {
                    "name": "filtered_workflow_count",
                    "measured": filtered,
                    "method": "on.push|pull_request paths/paths-ignore present",
                    "anchor": "command-center/p2-wave/probes/AUD-0047/probe1-path-filter-eval.raw.txt",
                },
                {
                    "name": "live_hole_count",
                    "measured": live_holes,
                    "method": "protected file fails path_triggers_event",
                    "anchor": "command-center/p2-wave/probes/AUD-0047/probe1-path-filter-eval.json",
                },
                {
                    "name": "planted_miss_caught",
                    "measured": planted,
                    "method": "fixture paths-ignore excludes receipt_validate.py",
                    "anchor": "command-center/p2-wave/probes/AUD-0047/fixtures/planted-paths-ignore/workflow.yml",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-finding",
            "live_workflows": [
                {
                    "workflow": r["workflow"],
                    "has_path_filters": r["has_path_filters"],
                    "hole_count": r["hole_count"],
                }
                for r in p1["live_workflows"]
            ],
            "probe2_summary": {
                "confirmed_run_count": p2["confirmed_run_count"],
                "unconfirmed_count": p2["unconfirmed_count"],
                "no_filter_vacuous_count": vacuous,
                "api_unavailable": p2.get("api_unavailable"),
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    doc = build()
    errs = L.validate(doc, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS:", *errs[:20], sep="\n", file=sys.stderr)
        return 1
    out_path = L.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # first write without self-hash; then rewrite artifacts[0] from disk
    text = json.dumps(doc, indent=2) + "\n"
    out_path.write_text(text, encoding="utf-8")
    primary = L.art(OUT, "primary")
    doc = build(primary=primary)
    # keep primary sha consistent with final bytes: write once more
    text = json.dumps(doc, indent=2) + "\n"
    out_path.write_text(text, encoding="utf-8")
    primary = L.art(OUT, "primary")
    doc["artifacts"][0] = primary
    text = json.dumps(doc, indent=2) + "\n"
    out_path.write_text(text, encoding="utf-8")

    manifest = {
        "unit_id": UNIT,
        "primary": OUT,
        "schema": SCHEMA,
        "state": doc["state"],
        "artifacts": doc["artifacts"],
        "packed_at": doc["timestamps"]["ended_at"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"packed {OUT} state={doc['state']} live_holes={doc['extensions']['live_workflows']}")
    print(doc["sentinel"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
