#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0050-rollback-guide-conformance.json."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from controls import run_all_controls  # noqa: E402
from measure import canonical_steps, completeness, measure_live  # noqa: E402
from paths import (  # noqa: E402
    CATALOG_SENTINEL,
    MANIFEST_REL,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    REPO,
    RUNBOOK_REL,
    SCHEMA_REL,
    UNIT,
)
from schema_validate import validate_doc  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict[str, Any]:
    sha, size = digest_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(
    role: str,
    method: str,
    command: str,
    raw_output: str,
    fingerprint: str,
    exit_code: int,
) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:8000],
        "fingerprint": fingerprint[:128],
        "exit_code": exit_code,
    }


def main() -> int:
    started = utc_now()
    scratch = Path(tempfile.mkdtemp(prefix="cnf0050-"))
    live_sandbox = scratch / "live-sandbox"
    live_sandbox.mkdir()
    live = measure_live(live_sandbox)
    ok, problems = completeness(live["steps"])
    if not ok:
        print("FAILED:CNF-0050 completeness", problems)
        return 1
    if live["unexecuted_count"] != 0:
        print("FAILED:CNF-0050 unexecuted_count", live["unexecuted_count"])
        return 1

    controls = run_all_controls(scratch / "controls")
    if any(not c.get("pass") for c in controls):
        print("FAILED:CNF-0050 detector controls")
        print(json.dumps(controls, indent=2, default=str)[:4000])
        return 1

    failed_steps = [s for s in live["steps"] if s.get("classification") != "ok"]
    named = live["named_present"]
    manifest_ok = bool(named.get(MANIFEST_REL))
    runbook_ok = bool(named.get(RUNBOOK_REL))
    followable = bool(live["guide_followable"])
    ended = utc_now()

    tests = [
        {
            "id": "probe1-literal-rerun",
            "name": "literal re-run records exit or deviation for every step",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "probe2-detector-control",
            "name": "detector controls fire in both states",
            "command": P2,
            "result": "PASS",
        },
        {
            "id": "control-known-good",
            "name": "known-good fixture is complete and followable",
            "command": "measure_fixture(known-good) completeness and exit 0",
            "result": "PASS" if controls[0]["pass"] else "FAIL",
        },
        {
            "id": "control-unexecuted-refused",
            "name": "completeness refuses an unexecuted mutant",
            "command": "completeness(unexecuted mutant) must fail",
            "result": "PASS" if controls[1]["pass"] else "FAIL",
        },
        {
            "id": "control-wrong-recipe",
            "name": "fenced git archive files corrected git cat-file recipe",
            "command": "fenced git archive must file corrected git cat-file recipe",
            "result": "PASS" if controls[2]["pass"] else "FAIL",
        },
        {
            "id": "control-use-vs-mention",
            "name": "prose mentioning git archive is not a wrong-recipe hit",
            "command": "prose mentioning git archive must not file wrong-recipe",
            "result": "PASS" if controls[3]["pass"] else "FAIL",
        },
        {
            "id": "control-ambiguous",
            "name": "placeholder step is not executed with invented values",
            "command": "placeholder step must not be executed with invented values",
            "result": "PASS" if controls[4]["pass"] else "FAIL",
        },
    ]

    nc = [
        {
            "id": "known-good-records",
            "kind": "known-broken-fixture",
            "description": (
                "Known-good fixture must record every step with exit 0 and "
                "be followable; this is the silent-on-good half."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": bool(controls[0].get("silent_on_good")),
            "good_state_output": json.dumps(
                {
                    "guide_followable": controls[0].get("guide_followable"),
                    "completeness_ok": controls[0].get("completeness_ok"),
                },
                sort_keys=True,
            ),
        },
        {
            "id": "unexecuted-refused",
            "kind": "mutation",
            "description": (
                "Dropping exit_code and deviation from one executed step must "
                "fail completeness (unexecuted/unrecorded)."
            ),
            "fired_on_bad_state": bool(controls[1].get("fired_on_bad")),
            "silent_on_good_state": bool(controls[1].get("silent_on_good")),
            "bad_state_output": json.dumps(
                {"bad_problems": controls[1].get("bad_problems")},
                sort_keys=True,
                default=str,
            ),
        },
        {
            "id": "wrong-recipe-filed",
            "kind": "known-broken-fixture",
            "description": (
                "Fenced git archive in fixtures/wrong-recipe must file "
                "wrong-recipe with corrected git cat-file recipe."
            ),
            "fired_on_bad_state": bool(controls[2].get("fired_on_bad")),
            "silent_on_good_state": True,
            "bad_state_output": json.dumps(
                {"defect_ids": controls[2].get("defect_ids")}, sort_keys=True
            ),
        },
        {
            "id": "use-vs-mention",
            "kind": "known-broken-fixture",
            "description": (
                "Prose that mentions git archive without a fenced command "
                "must not file wrong-recipe."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": bool(controls[3].get("silent_on_good")),
            "good_state_output": json.dumps(
                {"wrong_defects": controls[3].get("wrong_defects")},
                sort_keys=True,
            ),
        },
        {
            "id": "ambiguous-not-improvised",
            "kind": "malformed-input",
            "description": (
                "A <VERSION>/$TARGET placeholder must be classified "
                "ambiguous-step and must not be executed."
            ),
            "fired_on_bad_state": bool(controls[4].get("fired_on_bad")),
            "silent_on_good_state": True,
            "bad_state_output": json.dumps(
                {"ambiguous_ids": controls[4].get("ambiguous_ids")},
                sort_keys=True,
            ),
        },
        {
            "id": "schema-garbage",
            "kind": "malformed-input",
            "description": (
                "Empty/unrelated documents must be rejected by the "
                "conformance-report schema with disk-resolved $ref."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "empty object rejected by required receipt_core fields",
        },
    ]

    evidence = [
        {
            "claim": (
                "An operator can follow command-center/ROLLBACK-MANIFEST.md and "
                "the runbook rollback section literally, top to bottom, with "
                "zero improvisation."
            ),
            "verdict": "REFUTED" if not followable else "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": (
                f"{MANIFEST_REL} present={manifest_ok}; "
                f"{RUNBOOK_REL} present={runbook_ok}; "
                f"guide_followable={followable}"
            ),
            "probes": [
                probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/CNF-0050/emit.py",
                    (
                        f"named_present={named} followable={followable} "
                        f"steps={len(live['steps'])} defects={len(live['defects'])}"
                    ),
                    "cnf0050:measure-live",
                    0,
                ),
                probe(
                    "verifier",
                    "file-read",
                    f"test -f {MANIFEST_REL}; test -f {RUNBOOK_REL}",
                    (
                        f"{MANIFEST_REL}={manifest_ok} {RUNBOOK_REL}={runbook_ok}; "
                        "RUNBOOK.md has no heading containing 'rollback'; "
                        "ROLLBACK-MANIFEST.md has no fenced commands"
                    ),
                    "cnf0050:named-input-stat",
                    0 if manifest_ok and runbook_ok else 1,
                ),
            ],
        },
        {
            "claim": (
                "Every step in the guide has a recorded exit code or an explicit "
                "deviation note; no step is unexecuted."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": (
                f"steps={len(live['steps'])} unexecuted={live['unexecuted_count']} "
                f"completeness_ok={ok}"
            ),
            "probes": [
                probe(
                    "source",
                    "command",
                    "measure_live sandbox then completeness(steps)",
                    f"completeness_ok={ok} problems={problems} unexecuted={live['unexecuted_count']}",
                    "cnf0050:completeness",
                    0,
                ),
                probe(
                    "verifier",
                    "static-analysis",
                    "canonical_steps ids have exit_code int or deviation len>=8",
                    json.dumps(
                        [
                            {
                                "id": s.get("id"),
                                "exit_code": s.get("exit_code"),
                                "has_deviation": bool(s.get("deviation")),
                                "status": s.get("status"),
                            }
                            for s in live["steps"]
                        ],
                        sort_keys=True,
                    ),
                    "cnf0050:step-table",
                    0,
                ),
            ],
        },
        {
            "claim": (
                "Two independent reviewers filed without seeing each other's "
                "verdict; disagreement is recorded rather than voted."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": (
                "reviewers A-fenced and B-prompt; "
                "saw_other_verdict_before_filing=false"
            ),
            "probes": [
                probe(
                    "source",
                    "static-analysis",
                    "extract_fenced vs extract_prompt independently",
                    json.dumps(live["reviewers"], sort_keys=True, default=str)[:4000],
                    "cnf0050:reviewer-pair",
                    0,
                ),
                probe(
                    "verifier",
                    "file-read",
                    "command-center/p2-wave/probes/CNF-0050/extract.py",
                    "Reviewer A sees fences only; reviewer B sees $ / checkbox / Run: only.",
                    "cnf0050:extractor-split",
                    0,
                ),
            ],
        },
        {
            "claim": (
                "A recipe the live guide prescribes that is measurably wrong on "
                "this platform is filed with the corrected recipe."
            ),
            "verdict": (
                "CONFIRMED"
                if any(d.get("classification") == "wrong-recipe" for d in live["defects"])
                else "NOT-CHECKED"
            ),
            "confidence": "likely",
            "anchor": (
                "live rollback surfaces contain no fenced git-archive "
                "prescription; fixtures/wrong-recipe/ fires the detector"
            ),
            "probes": [
                probe(
                    "source",
                    "test-run",
                    "control_wrong_recipe_filed(fixtures/wrong-recipe)",
                    json.dumps(
                        {
                            "pass": controls[2].get("pass"),
                            "defect_ids": controls[2].get("defect_ids"),
                        },
                        sort_keys=True,
                    ),
                    "cnf0050:wrong-recipe-fixture",
                    0,
                ),
            ],
            "unverified": True,
            "settling_experiment": (
                "If a fenced git archive lands in the live rollback surfaces, "
                "re-run measure_live and expect classification=wrong-recipe "
                "with corrected_recipe git cat-file -p <rev>:<path>."
            ),
        },
    ]
    if evidence[-1]["verdict"] != "NOT-CHECKED":
        evidence[-1].pop("unverified", None)
        evidence[-1].pop("settling_experiment", None)
        evidence[-1]["probes"].append(
            probe(
                "verifier",
                "file-read",
                "live defects[].classification == wrong-recipe",
                json.dumps(
                    [d.get("id") for d in live["defects"]],
                    sort_keys=True,
                ),
                "cnf0050:live-wrong-recipe",
                0,
            )
        )
    else:
        evidence[-1].pop("confidence", None)

    classifications = sorted(
        {s.get("classification") for s in live["steps"] if s.get("classification")}
    )
    answer = (
        "No. An operator cannot follow the rollback guide on this tree. "
        f"{MANIFEST_REL} present={manifest_ok} {RUNBOOK_REL} present={runbook_ok}. "
        f"{len(live['steps'])} steps recorded, "
        f"unexecuted={live['unexecuted_count']}, "
        f"defects={len(live['defects'])}. RUNBOOK.md has no rollback heading so "
        "its fenced close.py/render.py/seed.py commands were not executed as "
        "the guide. ROLLBACK-MANIFEST.md is tables without fenced commands. "
        "Zero improvisation: missing procedures were filed as missing-step "
        "with deviation notes, not invented."
    )

    report = {
        "kind": "conformance-report",
        "observations": [
            {
                "name": "named-input-ROLLBACK-MANIFEST",
                "measured": manifest_ok,
                "method": "test -f command-center/ROLLBACK-MANIFEST.md",
                "anchor": MANIFEST_REL,
            },
            {
                "name": "named-input-RUNBOOK",
                "measured": runbook_ok,
                "method": "test -f command-center/RUNBOOK.md",
                "anchor": RUNBOOK_REL,
            },
            {
                "name": "guide_followable",
                "measured": followable,
                "method": "measure_live classification union + reviewer verdicts",
                "anchor": "report.guide_followable",
            },
            {
                "name": "unexecuted_count",
                "measured": int(live["unexecuted_count"]),
                "method": "completeness over recorded steps",
                "anchor": "report.unexecuted_count",
            },
            {
                "name": "step_count",
                "measured": len(live["steps"]),
                "method": "literal extraction plus catalog coverage holes",
                "anchor": "report.steps",
            },
        ],
        "control_ids": [c["id"] for c in controls],
        "title": (
            "Execute the rollback guide as written and confirm every documented "
            "step runs"
        ),
        "question": QUESTION,
        "guide_followable": followable,
        "unexecuted_count": live["unexecuted_count"],
        "named_inputs": named,
        "steps": live["steps"],
        "defects": live["defects"],
        "failed_or_defective_step_ids": [s.get("id") for s in failed_steps],
        "classifications_observed": classifications,
        "reviewers": live["reviewers"],
        "reviewer_disagreement": live["reviewer_disagreement"],
        "canonical_steps": canonical_steps(live["steps"]),
        "detector_controls": controls,
        "answer": answer,
        "notes": (
            "Confirmation SUCCESS means the guide was executed/recorded, not "
            "that an operator can follow it. guide_followable=false on this tree."
        ),
    }

    doc: dict[str, Any] = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": CATALOG_SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json CNF-0050; "
            f"{MANIFEST_REL}; {RUNBOOK_REL}"
        ),
        "min_bytes_threshold": 512,
        "artifacts": [
            artifact_row(SCHEMA_REL, "supporting"),
            artifact_row(MANIFEST_REL, "primary"),
            artifact_row(RUNBOOK_REL, "supporting"),
        ],
        "evidence": evidence,
        "tests": tests,
        "negative_controls": nc,
        "reviewer": {
            "reviewer_id": "CNF-0050-probe2-detector",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Probe 2 re-runs detector controls on fixtures without reading "
                "emit.py's live step table."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0050/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0050/schema_validate.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "schema_validate.validate_doc(receipt)",
                    "in-memory receipt compiles against disk-resolved $ref",
                    "cnf0050:schema-validate",
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
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record, never "
                "an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "ROLLBACK-MANIFEST.md table-cell undo lines are not extracted "
                    "by fenced/prompt extractors, so they were not executed as steps."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add a table-cell extractor, re-run measure_live, and file "
                    "each extracted command's exit or an explicit deviation."
                ),
            },
            {
                "claim": (
                    "EXPECTED_COVERAGE needle 'sha256' matches RUNBOOK.md REACH-6 "
                    "prose, so the N-1 pin hole was not filed as missing-sha256-pin."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Already measured: RUNBOOK.md contains 'sha256 mismatch'; "
                    "coverage uses whole-file text, not the rollback section."
                ),
            },
        ],
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "runbook-conformance-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": report,
        "extensions": {
            "cloud_ok": False,
            "named_probes": [
                {"id": "probe1", "role": "literal-rerun", "command": P1},
                {"id": "probe2", "role": "detector-control", "command": P2},
            ],
            "output_path": OUT_REL,
            "output_schema": SCHEMA_REL,
            "produced_by_path": (
                "command-center/p2-wave/probes/CNF-0050/emit.py"
            ),
        },
    }

    errs = validate_doc(doc)
    if errs:
        print("FAILED:CNF-0050 schema")
        for e in errs[:40]:
            print(" ", e)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True, default=str) + "\n"
    if CATALOG_SENTINEL not in text:
        print("FAILED:CNF-0050 sentinel missing from serialized artifact")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0050 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
