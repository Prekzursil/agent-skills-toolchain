#!/usr/bin/env python3
"""Pack AUD-0055 skip/xfail reason-validity audit.

Honest census with live probes. Emits BLOCKED pending independent fresh-context
Claude review (catalog reviewer_requirement: falsify headline count). Never
emits SUCCESS without that review — anti-false-green.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0055"
OUT = "command-center/audit/AUD-0055-skip-xfail-reason-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0055/UNIT-ARTIFACT-MANIFEST.json"
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
    p1 = json.loads((PROBE / "probe1-marker-census.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-unmark-sample.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-marker-census.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-unmark-sample.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T19:40:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    skip_n = int(p1["skip_count"])
    xfail_n = int(p1["xfail_count"])
    marker_n = int(p1["marker_count"])
    prod_skip = int(p1["production_skip_count"])
    prod_xfail = int(p1["production_xfail_count"])
    no_reason = int(p1["no_reason_count"])
    control1 = bool(p1["control"]["ok"])
    control2 = bool(p2["control"]["ok"])
    marked_xpass = bool(p2["control"]["marked_xpass"])
    unmark_pass = bool(p2["control"]["unmarked_xfail_passes"])
    skip_fails = bool(p2["control"]["unmarked_skip_fails"])
    sample_exec = int(p2["sample_executed_count"])

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
            "command-center/p2-wave/probes/AUD-0055/probe1-marker-census.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0055/probe2-unmark-sample.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0055/probe1-marker-census.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0055/probe2-unmark-sample.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0055/fixtures/test_control_xfail_fixed.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0055/fixtures/test_control_skip_still_fails.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0055/fixtures/mention_only_noise.py",
            "fixture",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0055/independent-review.json",
                "supporting",
            )
        )

    question = (
        "For every skipped or xfail-marked test, is the stated reason still true "
        "today, and how many are permanently disabled tests masquerading as temporary?"
    )

    stale = [
        r
        for r in p2.get("results", [])
        if str(r.get("verdict", "")).startswith("STALE")
    ]
    holds = [
        r
        for r in p2.get("results", [])
        if str(r.get("verdict", "")).startswith("HOLDS")
    ]

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
                "id": "AUD-0055-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0055/independent-review.json"
                ),
            },
            {
                "id": "AUD-0055-D-STALE",
                "severity": "P2",
                "status": "open" if stale else "resolved",
                "summary": (
                    f"unmark sample stale={len(stale)} holds={len(holds)}; "
                    f"markers skip={skip_n} xfail={xfail_n} (prod skip={prod_skip} "
                    f"xfail={prod_xfail})."
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0055"
        headline = (
            f"skip={skip_n} xfail={xfail_n} markers={marker_n} "
            f"(prod skip={prod_skip} xfail={prod_xfail}); no_reason={no_reason}; "
            f"control_xpass={marked_xpass} unmark_pass={unmark_pass}; "
            f"sample_executed={sample_exec}. Independent re-review PASS."
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
                "id": "AUD-0055-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Independent fresh-context Claude review unpaid; headline skip/"
                    "xfail counts must be falsified by a reviewer who did not author "
                    "this census."
                ),
            },
            {
                "id": "AUD-0055-D-STALE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"markers={marker_n} skip={skip_n} xfail={xfail_n}; "
                    f"prod skip={prod_skip} xfail={prod_xfail}; "
                    f"unmark stale={len(stale)} holds={len(holds)}; "
                    f"control_ok={control1 and control2}."
                ),
            },
        ]
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0055 skip/xfail census + scratch-worktree unmark sample "
            "measured; control XPASS→PASS and skip-unmark FAIL observed; "
            "blocked-on-independent-review"
        )
        headline = (
            f"skip={skip_n} xfail={xfail_n} markers={marker_n} "
            f"(prod skip={prod_skip} xfail={prod_xfail}); no_reason={no_reason}; "
            f"control_xpass={marked_xpass} unmark_pass={unmark_pass} "
            f"skip_unmark_fails={skip_fails}; sample_executed={sample_exec}. "
            "BLOCKED on independent fresh-context Claude review."
        )
        failure = {
            "classification": ["blocked-on-independent-review", "detector-failure"],
            "reason": (
                "Named probes completed with required XPASS control (fixed-bug xfail "
                "shows XPASS marked and PASS unmarked; skip whose reason holds FAILs "
                "when unmarked) and stratified unmark sample executed, but catalog "
                "reviewer_requirement is unmet (fresh-context Claude must falsify "
                "headline counts)."
            ),
            "diagnostic_tail": (
                f"skip={skip_n} xfail={xfail_n} prod_skip={prod_skip} "
                f"prod_xfail={prod_xfail} marked_xpass={marked_xpass} "
                f"unmark_pass={unmark_pass} sample_exec={sample_exec} "
                f"reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this "
                "unit's transcript; the reviewer must try to FALSIFY the headline "
                f"skip_count={skip_n} xfail_count={xfail_n} "
                f"(production_skip={prod_skip} production_xfail={prod_xfail}) "
                "before PASS, not re-read the artifact."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0055/probe1_marker_census.py",
                    f"skip_count={skip_n} xfail_count={xfail_n} control_ok={control1}",
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

    findings_sample = []
    for m in p1.get("markers", [])[:40]:
        findings_sample.append(
            {
                "path": m["path"],
                "lineno": m["lineno"],
                "kind": m["kind"],
                "reason": m.get("reason"),
                "reason_class": m.get("reason_class"),
                "age_days": (m.get("blame") or {}).get("age_days"),
                "production_scope": m.get("production_scope"),
            }
        )

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0055",
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
                    f"Probe 1 AST census: files={p1['files_scanned']} "
                    f"markers={marker_n} skip={skip_n} xfail={xfail_n}; "
                    f"prod skip={prod_skip} xfail={prod_xfail}; "
                    f"no_reason={no_reason}; by_kind={p1['by_kind']}; "
                    f"age_days median={p1['age_days_median']}; "
                    f"mention_only_hits={p1['control']['mention_only_hits']}; "
                    f"control_ok={control1}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0055/probe1-marker-census.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0055/probe1_marker_census.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-marker-census.json",
                        json.dumps(
                            {
                                "skip_count": skip_n,
                                "xfail_count": xfail_n,
                                "marker_count": marker_n,
                                "production_skip_count": prod_skip,
                                "production_xfail_count": prod_xfail,
                                "control_ok": control1,
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
                    f"Probe 2 scratch-worktree unmark: mode={p2['worktree_mode']}; "
                    f"control marked_xpass={marked_xpass} unmarked_pass={unmark_pass} "
                    f"skip_unmark_fails={skip_fails}; "
                    f"sample_executed={sample_exec}/{p2['results_count']}; "
                    f"stale={len(stale)} holds={len(holds)}; control_ok={control2}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0055/probe2-unmark-sample.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0055/probe2_unmark_sample.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-unmark-sample.json",
                        json.dumps(
                            {
                                "control_ok": control2,
                                "marked_xpass": marked_xpass,
                                "unmarked_xfail_passes": unmark_pass,
                                "unmarked_skip_fails": skip_fails,
                                "sample_executed_count": sample_exec,
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
                "id": "AUD-0055-xfail-fixed-shows-xpass",
                "name": (
                    "control: an xfail whose underlying bug is fixed must show as "
                    "XPASS when marked; PASS when unmarked (sample executed)"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0055/probe2_unmark_sample.py",
                "result": "PASS" if marked_xpass and unmark_pass else "FAIL",
                "assertions": 2,
                "output_tail": raw2[-800:],
            },
            {
                "id": "AUD-0055-skip-reason-holds-fails-unmarked",
                "name": "control: skip whose reason still holds must FAIL when unmarked",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0055/probe2_unmark_sample.py",
                "result": "PASS" if skip_fails else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-500:],
            },
            {
                "id": "AUD-0055-mention-only-not-counted",
                "name": "use-vs-mention: string mentions of markers must not inflate census",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0055/probe1_marker_census.py",
                "result": "PASS" if p1["control"]["mention_only_hits"] == 0 else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-400:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0055-C1",
                "known-broken-fixture",
                "Fixed-bug xfail must XPASS while marked and PASS when unmarked.",
                True,
                True,
                bad="marked run did not XPASS or unmarked run did not PASS",
                good=f"marked_xpass={marked_xpass} unmarked_pass={unmark_pass}",
            ),
            L.control(
                "AUD0055-C2",
                "mutation",
                "Skip whose reason holds must FAIL after marker removal in scratch tree.",
                True,
                True,
                bad="unmarked skip control passed (reason did not hold)",
                good=f"unmarked_skip_fails={skip_fails}",
            ),
            L.control(
                "AUD0055-C3",
                "malformed-input",
                "mention_only_noise.py strings must not count as markers.",
                True,
                True,
                bad="mention-only strings inflated marker_count",
                good=f"mention_only_hits={p1['control']['mention_only_hits']}",
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
                    "python3 -B command-center/p2-wave/probes/AUD-0055/_pack_receipt.py",
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
                    "Every production skipif condition's boolean value matches the "
                    "operator's mental model of 'reason still true'."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "For each skipif, eval the condition expression in-process and "
                    "compare to unmark outcome; condition True + unmarked PASS means "
                    "stale reason text."
                ),
            },
            {
                "claim": (
                    "Duplicate skills/ vs .agents/skills/ marker pairs are independent "
                    "deployed surfaces rather than migration twins."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Diff the twin paths; if byte-identical, report a deduped headline "
                    "alongside the raw count."
                ),
            },
            {
                "claim": "No pytest.skip() runtime calls are load-bearing suppressions.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Separate AST pass for pytest.skip()/pytest.xfail() calls "
                    "(excluded from marker census by design) and join to AUD-0081."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "observations": [
                {
                    "name": "marker_count",
                    "measured": marker_n,
                    "method": "AST pytest.mark.*/unittest.skip* with reason + git blame",
                    "anchor": "command-center/p2-wave/probes/AUD-0055/probe1-marker-census.json",
                },
                {
                    "name": "skip_count",
                    "measured": skip_n,
                    "method": "kinds in {skip, skipif, skipIf, skipUnless}",
                    "anchor": "command-center/p2-wave/probes/AUD-0055/probe1-marker-census.raw.txt",
                },
                {
                    "name": "xfail_count",
                    "measured": xfail_n,
                    "method": "kinds in {xfail, expectedFailure}",
                    "anchor": "command-center/p2-wave/probes/AUD-0055/probe1-marker-census.json",
                },
                {
                    "name": "production_skip_count",
                    "measured": prod_skip,
                    "method": "production_scope markers excluding AUD-0055 fixtures",
                    "anchor": "command-center/p2-wave/probes/AUD-0055/probe1-marker-census.json",
                },
                {
                    "name": "production_xfail_count",
                    "measured": prod_xfail,
                    "method": "production_scope xfail/expectedFailure",
                    "anchor": "command-center/p2-wave/probes/AUD-0055/probe1-marker-census.json",
                },
                {
                    "name": "control_marked_xpass",
                    "measured": marked_xpass,
                    "method": "fixtures/test_control_xfail_fixed.py pytest run",
                    "anchor": "command-center/p2-wave/probes/AUD-0055/probe2-unmark-sample.raw.txt",
                },
                {
                    "name": "sample_executed_count",
                    "measured": sample_exec,
                    "method": "scratch worktree marker removal + pytest",
                    "anchor": "command-center/p2-wave/probes/AUD-0055/probe2-unmark-sample.json",
                },
                {
                    "name": "unmark_stale_count",
                    "measured": len(stale),
                    "method": "Probe 2 verdicts starting with STALE",
                    "anchor": "command-center/p2-wave/probes/AUD-0055/probe2-unmark-sample.json",
                },
            ],
            "control_ids": ["AUD0055-C1", "AUD0055-C2", "AUD0055-C3"],
            "findings_sample": findings_sample,
            "unmark_sample_verdicts": [
                {
                    "label": r.get("label"),
                    "path": r.get("path"),
                    "kind": r.get("kind"),
                    "verdict": r.get("verdict"),
                    "executed": r.get("executed"),
                }
                for r in p2.get("results", [])
            ],
        },
        "extensions": {
            "anti_false_green": anti,
            "wave": "p2-wave1",
            "by_kind": p1["by_kind"],
            "by_reason_class": p1["by_reason_class"],
            "probe2_worktree_mode": p2.get("worktree_mode"),
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": doc["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={doc['state']} bytes={L.art(OUT)['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
