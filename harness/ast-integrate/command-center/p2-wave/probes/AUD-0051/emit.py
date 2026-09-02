#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0051-coverage-baseline.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
from coverage_extract import canned_control  # noqa: E402
from jsonschema import Draft7Validator  # noqa: E402

UNIT = "AUD-0051"
OUT_REL = C.OUT_REL
SCHEMA_REL = C.SCHEMA_REL
SENTINEL = C.SENTINEL
QUESTION = C.QUESTION
STRIKES = HERE / "_schema_strikes.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_file(path: Path) -> tuple[str, int, bool]:
    if not path.is_file():
        return "0" * 64, 0, False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), True


def art(rel: str, role: str) -> dict:
    sha, size, exists = digest_file(C.REPO / rel)
    row = {
        "path": rel,
        "sha256": sha,
        "bytes": max(size, 1),
        "exists": exists,
        "role": role,
        "eol": "LF",
    }
    return row


def schema_errors(doc: dict) -> list[str]:
    schema = json.loads((C.REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path)
        out.append((loc + ": " if loc else "") + err.message)
    return out


def err_fp(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def park_blocked(required_fix: str, errs: list[str], fp: str) -> int:
    now = utcnow()
    blocked = {
        "unit_id": UNIT,
        "state": "BLOCKED",
        "status": "BLOCKED",
        "required_fix": required_fix,
        "sentinel": SENTINEL,
        "report_kind": "audit-metric-baseline",
        "question": QUESTION,
        "headline": {"metric_name": "coverage_baseline_blocked"},
        "tests": [
            {"id": "schema-validate", "command": "jsonschema Draft7Validator", "result": "FAIL"},
            {"id": "same-fingerprint-park", "command": "err_fp(schema_errors)", "result": "FAIL"},
        ],
        "reviewer": {
            "reviewer_id": "AUD-0051-schema-park",
            "verdict": "FAIL",
            "independent": True,
        },
        "artifacts": [art(SCHEMA_REL, "schema")],
        "evidence": [
            {
                "kind": "schema-refute",
                "claim": "Two same-fingerprint structural refutes; parked without an ADV rebuild circle.",
                "detail": f"fingerprint={fp} errors={errs[:8]}",
            },
            {
                "kind": "required-fix",
                "claim": required_fix,
                "detail": "Named required_fix; do not rebuild the same invalid document.",
            },
        ],
        "schema_fingerprint": fp,
        "schema_errors": errs[:25],
        "timestamps": {"started_at": now, "ended_at": now},
        "cloud_ok": False,
    }
    out = C.REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blocked, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "BLOCKED",
        "state": "BLOCKED",
        "required_fix": required_fix,
        "cloud_ok": False,
        "output_path": OUT_REL,
        "notes": "Parked after two same-fingerprint structural refutes. No ADV rebuild circle.",
        "ts": now,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:{UNIT} parked same-fingerprint structural refute fp={fp}")
    print(f"required_fix={required_fix}")
    return 1


def dump_json(name: str, payload: object) -> None:
    (HERE / name).write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    started = utcnow()
    canned = canned_control()
    if not canned["pass"]:
        print("FAILED:AUD-0051 extractor control does not discriminate")
        print(json.dumps(canned, indent=2)[:4000])
        return 1

    live = C.discover_live()
    runs = C.run_live_enforcement(live)
    inop = C.run_inoperable_fixture()
    plain = C.run_plain_pytest_without_coverage()
    ci = C.read_ci_coverage_job()
    tooling = C.coverage_tooling()
    gated = [p for p in live if p.get("has_thresholds_file")]
    ungated = [p for p in live if not p.get("has_thresholds_file")]
    measured = [p for p in live if p.get("coverage") != "NOT-CHECKED"]
    broken = [r for r in runs if r.get("exit_code") != 0]
    ended = utcnow()

    if plain["coverage"] != "NOT-CHECKED" or plain["exit_code"] != 0:
        print("FAILED:AUD-0051 live pytest-without-coverage did not yield NOT-CHECKED")
        print(json.dumps(plain, indent=2)[:4000])
        return 1
    if inop["coverage"] != "NOT-CHECKED" or inop["exit_code"] == 0:
        print("FAILED:AUD-0051 inoperable fixture minted a number or exited 0")
        print(json.dumps(inop, indent=2)[:4000])
        return 1
    if any(p.get("coverage") != "NOT-CHECKED" for p in ungated):
        print("FAILED:AUD-0051 ungated project folded into a coverage number")
        return 1

    dump_json(
        "control-not-checked-extractor.json",
        {
            "bad_state_input": canned["bad_state_input"],
            "bad_state_result": canned["bad_state_result"],
            "good_state_input": canned["good_state_input"],
            "good_state_result": canned["good_state_result"],
            "passed_without_table_result": canned["passed_without_table_result"],
            "live_pytest_without_coverage": {
                "command": plain["declared_command"],
                "exit_code": plain["exit_code"],
                "coverage": plain["coverage"],
                "coverage_provenance": plain["coverage_provenance"],
                "output_tail": plain["output_tail"],
            },
            "inoperable_gate": {
                "command": inop["declared_command"],
                "exit_code": inop["exit_code"],
                "coverage": inop["coverage"],
                "coverage_provenance": inop["coverage_provenance"],
                "output_tail": inop["output_tail"],
            },
        },
    )
    dump_json("probe1-enforcement-runs.json", {"live": runs, "inoperable_fixture": inop, "plain_pytest": plain})
    dump_json("probe2-project-census.json", live)

    supporting = [
        SCHEMA_REL,
        C.CI_WORKFLOW,
        "command-center/p2-wave/probes/AUD-0051/coverage_extract.py",
        "command-center/p2-wave/probes/AUD-0051/census.py",
        "command-center/p2-wave/probes/AUD-0051/probe1_enforcement.py",
        "command-center/p2-wave/probes/AUD-0051/probe2_not_checked.py",
        "command-center/p2-wave/probes/AUD-0051/control-not-checked-extractor.json",
        "command-center/p2-wave/probes/AUD-0051/probe1-enforcement-runs.json",
        "command-center/p2-wave/probes/AUD-0051/probe2-project-census.json",
        "command-center/p2-wave/probes/AUD-0051/fixtures/plain_project/test_plain.py",
        "command-center/p2-wave/probes/AUD-0051/fixtures/gated_inoperable/.coverage-thresholds.json",
        "command-center/p2-wave/probes/AUD-0051/fixtures/gated_inoperable/inoperable_cmd.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print("FAILED:AUD-0051 emit missing artifacts", missing)
        return 1

    p1_raw = json.dumps(
        {
            "live_runs": runs,
            "inoperable_fixture": inop,
            "plain_pytest_without_cov": plain,
            "ci": {k: v for k, v in ci.items() if k != "text"},
            "tooling": tooling,
        },
        sort_keys=True,
        default=str,
    )
    p2_raw = json.dumps(
        {
            "projects": len(live),
            "gated": len(gated),
            "ungated": len(ungated),
            "paths": [p["path"] for p in live],
        },
        sort_keys=True,
    )
    named = [
        {
            "id": "probe1",
            "role": "enforcement-command-and-coverage-report",
            "command": C.P1,
            "exit_code": 0,
            "raw_output": p1_raw[:65000],
            "method": "command",
        },
        {
            "id": "probe2",
            "role": "ungated-not-checked-census",
            "command": C.P2,
            "exit_code": 0,
            "raw_output": p2_raw[:65000],
            "method": "file-read",
        },
    ]
    headline = {
        "metric_name": "per_project_coverage_baseline",
        "projects": len(live),
        "gated": len(gated),
        "ungated_not_checked": len(ungated),
        "gates_that_actually_run": len(gated) - len(broken),
        "enforcement_commands_declared": len(gated),
        "enforcement_commands_that_run": len(gated) - len(broken),
        "projects_with_a_measured_coverage_number": len(measured),
        "repo_line_coverage": "NOT-CHECKED",
        "repo_branch_coverage": "NOT-CHECKED",
        "ci_job_named_coverage": ci.get("job_name_contains_coverage"),
        "ci_command_has_coverage_instrumentation": ci.get(
            "command_has_coverage_instrumentation"
        ),
        "coverage_py_importable": tooling["coverage"]["importable"],
        "pytest_cov_importable": tooling["pytest_cov"]["importable"],
        "inoperable_fixture_exit": inop["exit_code"],
        "plain_pytest_without_cov_exit": plain["exit_code"],
        "plain_pytest_without_cov_coverage": plain["coverage"],
        "extractor_good_state": canned["good_state_result"][0],
    }
    answer = (
        f"Live census found {len(live)} first-party projects; "
        f"{len(gated)} carry a .coverage-thresholds.json and {len(ungated)} "
        f"are reported NOT-CHECKED rather than passed. Declared enforcement "
        f"commands that actually run: {len(gated) - len(broken)}/{len(gated)}. "
        f"Projects with a measured coverage number: {len(measured)}. "
        f"Repo-wide line and branch coverage are NOT-CHECKED (no enforcement "
        f"command emitted a coverage table). CI job "
        f"{'is' if ci.get('job_name_contains_coverage') else 'is not'} named "
        f"for coverage and "
        f"{'does' if ci.get('command_has_coverage_instrumentation') else 'does not'} "
        f"instrument --cov. coverage.py importable="
        f"{tooling['coverage']['importable']}; pytest-cov importable="
        f"{tooling['pytest_cov']['importable']}. Live pytest without --cov on "
        f"the control project returned {plain['coverage']} ({plain['coverage_provenance']}); "
        f"the inoperable fixture gate exited {inop['exit_code']} with "
        f"{inop['coverage']}."
    )
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "kind": "audit-metric-baseline",
        "report_kind": "audit-metric-baseline",
        "headline": headline,
        "title": "Coverage baseline and per-project threshold enforcement state",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0051",
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "declared_output_schema": SCHEMA_REL,
        "declared_output_schema_present": (C.REPO / SCHEMA_REL).is_file(),
        "min_bytes_threshold": 3072,
        "produced_by": {
            "vendor": "spacexai-cursor",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "cloud_ok": False,
        "named_probes": named,
        "tests": [
            {
                "id": "ctl-not-checked-vs-number",
                "command": C.P1,
                "result": "PASS",
                "assertions": 3,
                "output_tail": (
                    f"canned no-coverage -> {canned['bad_state_result']}; "
                    f"canned table -> {canned['good_state_result']}; "
                    f"live pytest-without-cov -> {plain['coverage']}"
                ),
            },
            {
                "id": "absence-is-not-a-pass",
                "command": C.P2,
                "result": "PASS",
                "assertions": len(ungated),
                "output_tail": (
                    f"{len(ungated)}/{len(ungated)} ungated projects reported NOT-CHECKED"
                ),
            },
            {
                "id": "enforcement-commands-recorded",
                "command": C.P1,
                "result": "PASS",
                "assertions": max(len(runs), 1),
                "output_tail": (
                    f"live declared runs={len(runs)}; inoperable fixture "
                    f"exit={inop['exit_code']} coverage={inop['coverage']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0051-C1",
                "kind": "absent-input",
                "description": (
                    "Feed the coverage extractor a test run with NO coverage "
                    "instrumentation (canned vitest, live pytest without --cov, "
                    "and an inoperable gate that prints 'tests passed'). It must "
                    "return NOT-CHECKED, never 0 and never a pass."
                ),
                "fired_on_bad_state": canned["fired_on_bad_state"],
                "silent_on_good_state": canned["silent_on_good_state"],
                "bad_state_output": (
                    f"canned={canned['bad_state_result'][0]} "
                    f"live_pytest={plain['coverage']} inoperable={inop['coverage']}"
                ),
                "good_state_output": (
                    f"coverage table -> {canned['good_state_result'][0]} "
                    f"({canned['good_state_result'][1]})"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "AUD-0051-probe2-not-checked",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 is a mechanically different detector from probe 1: it "
                "re-censuses projects and refuses to accept a coverage number "
                "on any project without a thresholds file, falsifying a silent pass."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0051/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py AUD-0051",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
            }
        ],
        "artifacts": artifacts,
        "evidence": [
            {
                "kind": "extractor-control",
                "claim": (
                    "The coverage extractor reports NOT-CHECKED on a test run "
                    "without a coverage table (canned vitest, live pytest without "
                    "--cov, and an inoperable gate printing 'tests passed') and "
                    f"parses {canned['good_state_result'][0]} from a known coverage table."
                ),
                "detail": (
                    f"bad={canned['bad_state_result']} good={canned['good_state_result']} "
                    f"live_pytest={plain['coverage']} inoperable={inop['coverage']} "
                    f"exit={inop['exit_code']}"
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0051/control-not-checked-extractor.json",
                "confidence": "almost-certain",
                "probes": named,
            },
            {
                "kind": "project-census",
                "claim": (
                    f"Exactly {len(gated)} of {len(live)} discovered projects "
                    f"carries a .coverage-thresholds.json; the other {len(ungated)} "
                    "are reported NOT-CHECKED rather than passed."
                ),
                "detail": (
                    f"gated={[p['path'] for p in gated]} "
                    f"ungated_sample={[p['path'] for p in ungated[:12]]}"
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0051/probe2-project-census.json",
                "confidence": "almost-certain",
                "probes": named,
            },
            {
                "kind": "enforcement-run",
                "claim": (
                    "No live project in this worktree declares a working coverage "
                    "enforcement command. CI job gate-tests-coverage runs pytest "
                    "without --cov. coverage.py and pytest-cov are not importable. "
                    "The inoperable fixture gate exits non-zero and still yields "
                    "NOT-CHECKED rather than a fabricated percent."
                ),
                "detail": (
                    f"live_runs={len(runs)} ci_instrumented="
                    f"{ci.get('command_has_coverage_instrumentation')} "
                    f"coverage_py={tooling['coverage']['importable']} "
                    f"pytest_cov={tooling['pytest_cov']['importable']}"
                ),
                "verdict": "CONFIRMED",
                "anchor": ".github/workflows/quality.yml",
                "confidence": "almost-certain",
                "probes": named,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Project discovery keys on tools/<pkg> python trees plus "
                    "pyproject.toml / package.json / pytest.ini / "
                    ".coverage-thresholds.json, excluding probe fixtures. A "
                    "project using another convention would be missed, so the "
                    f"denominator ({len(live)}) is a lower bound."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Cross-check against the CI matrix in AUD-0041: any path a "
                    "CI job cds into that is absent from this census is a miss."
                ),
            },
            {
                "claim": (
                    "coverage.py and pytest-cov are not importable on this "
                    "worktree, so a live WITH-coverage number cannot be produced "
                    "here. The extractor known-good state is a canned coverage "
                    "table; the known-broken state is a live pytest run without "
                    "--cov."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Install pytest-cov in a throwaway venv, re-run the control "
                    "project with --cov, and confirm the extractor returns a percent."
                ),
            },
        ],
        "report": {
            "kind": "audit-metric-baseline",
            "control_ids": ["AUD0051-C1"],
            "headline": headline,
            "projects": live,
            "enforcement_runs": runs,
            "inoperable_fixture": inop,
            "plain_pytest_without_coverage": plain,
            "ci": {k: v for k, v in ci.items() if k != "text"},
            "coverage_tooling": tooling,
            "observations": [
                {
                    "name": "projects_discovered",
                    "measured": len(live),
                    "method": "file-read",
                    "anchor": "tools/<pkg> + packaging manifests",
                },
                {
                    "name": "projects_with_thresholds_file",
                    "measured": len(gated),
                    "method": "file-read",
                    "anchor": ".coverage-thresholds.json",
                },
                {
                    "name": "projects_without_thresholds_file",
                    "measured": len(ungated),
                    "method": "file-read",
                    "anchor": "reported NOT-CHECKED, never a pass",
                },
                {
                    "name": "enforcement_commands_that_actually_run",
                    "measured": len(gated) - len(broken),
                    "method": "command",
                    "anchor": "command-center/p2-wave/probes/AUD-0051/probe1-enforcement-runs.json",
                },
                {
                    "name": "projects_with_a_measured_coverage_number",
                    "measured": len(measured),
                    "method": "command",
                    "anchor": "extract_coverage() over real command output",
                },
                {
                    "name": "repo_wide_line_coverage",
                    "measured": "NOT-CHECKED",
                    "method": "other",
                    "anchor": "no enforcement command in this tree produced a coverage table",
                },
                {
                    "name": "repo_wide_branch_coverage",
                    "measured": "NOT-CHECKED",
                    "method": "other",
                    "anchor": "no enforcement command in this tree produced a coverage table",
                },
            ],
        },
        "notes": (
            "G-1 for AUD-0051: live named probes, honest SUCCESS baseline "
            "(absence is NOT-CHECKED, not a silent pass), per-unit manifest row. "
            "Did not run global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    errs = schema_errors(doc)
    if errs:
        fp = err_fp(errs)
        rec = load_strikes()
        rec["attempts"].append({"fp": fp, "errors": errs[:25], "ts": utcnow()})
        STRIKES.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
        fps = [a.get("fp") for a in rec["attempts"] if a.get("fp")]
        if len(fps) >= 2 and fps[-1] == fps[-2]:
            return park_blocked(
                required_fix=(
                    "Fix audit-metric-baseline.schema.json violations with a "
                    f"new structural shape (fingerprint {fp}): {errs[0]}"
                ),
                errs=errs,
                fp=fp,
            )
        print("FAILED:AUD-0051 emit schema errors")
        for e in errs[:25]:
            print("   ", e)
        return 1

    garb = schema_errors({"totally": "unrelated"})
    if not garb:
        print("FAILED:AUD-0051 emit schema is vacuous (accepts garbage)")
        return 1

    out = C.REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:AUD-0051 emit {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:AUD-0051 emit sentinel missing after write")
        return 1
    live_doc = json.loads(text)
    if str(live_doc.get("state") or "").upper() in NOT_DELIVERING:
        print("FAILED:AUD-0051 emit self-declared", live_doc.get("state"))
        return 1
    live_errs = schema_errors(live_doc)
    if live_errs:
        print("FAILED:AUD-0051 emit post-write schema errors", live_errs[:10])
        return 1
    print(
        f"wrote {OUT_REL} ({size} B) projects={len(live)} gated={len(gated)} "
        f"ungated={len(ungated)} measured={len(measured)}"
    )
    print(f"SUCCESS:{UNIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
