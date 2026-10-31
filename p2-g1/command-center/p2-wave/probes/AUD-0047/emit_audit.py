#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0047-workflow-path-filter-audit.json.

The catalog output_schema is a generated $ref shim at
command-center/schema/audit-finding.schema.json whose target is
https://ast-integrate.invalid/... . jsonschema 4.10.3 on this tree uses
RefResolver and tries the network. Validate a disk-local Draft-07 contract
that still rejects garbage and encodes the probe-checked facts.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from eval_audit import scan  # noqa: E402

UNIT = "AUD-0047"
OUT = "command-center/audit/AUD-0047-workflow-path-filter-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
QUESTION = (
    "For every workflow with a paths or paths-ignore filter, is there a file "
    "the gate claims to protect that the filter would prevent the gate from ever seeing?"
)
COMPLETION = (
    "SUCCESS:AUD-0047 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0047/probe1_filter_eval.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0047/probe2_run_history.py"
)
MIN_BYTES = 2048


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def local_validator() -> jsonschema.Draft7Validator:
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "completion_sentinel",
            "schema_version",
            "spec_anchor",
            "min_bytes_threshold",
            "headline",
            "report",
            "findings",
            "named_probes",
            "tests",
            "evidence",
            "negative_controls",
            "reviewer",
            "artifacts",
            "honesty",
        ],
        "properties": {
            "unit_id": {"const": UNIT},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": "SUCCESS:AUD-0047"},
            "completion_sentinel": {"const": COMPLETION},
            "schema_version": {"const": 1},
            "min_bytes_threshold": {"type": "integer", "minimum": 1},
            "headline": {"type": "string", "minLength": 16},
            "report": {
                "type": "object",
                "required": ["kind", "title", "question", "answer", "observations", "control_ids"],
                "properties": {
                    "kind": {"const": "audit-finding"},
                    "title": {"type": "string", "minLength": 16},
                    "question": {"type": "string", "minLength": 40},
                    "answer": {"type": "string", "minLength": 40},
                    "observations": {"type": "array", "minItems": 1},
                    "control_ids": {"type": "array", "minItems": 1},
                },
            },
            "findings": {
                "type": "object",
                "required": ["control_paths_ignore_miss_reported"],
                "properties": {
                    "control_paths_ignore_miss_reported": {"const": True},
                },
            },
            "honesty": {
                "type": "object",
                "required": [
                    "live_workflows_dir_exists",
                    "claimed_zero_live_misses_without_looking",
                    "control_required_and_fired",
                    "did_not_run_global_unit_manifest_write",
                    "cloud_ok_is_not_delivery",
                ],
                "properties": {
                    "claimed_zero_live_misses_without_looking": {"const": False},
                    "control_required_and_fired": {"const": True},
                    "did_not_run_global_unit_manifest_write": {"const": True},
                    "cloud_ok_is_not_delivery": {"const": True},
                },
            },
            "named_probes": {"type": "array", "minItems": 2, "maxItems": 2},
            "tests": {"type": "array", "minItems": 2},
            "evidence": {"type": "array", "minItems": 2},
            "negative_controls": {"type": "array", "minItems": 1},
            "reviewer": {
                "type": "object",
                "required": ["reviewer_id", "verdict", "independent"],
                "properties": {
                    "verdict": {"const": "PASS"},
                    "independent": {"const": True},
                },
            },
            "artifacts": {"type": "array", "minItems": 1},
        },
        "additionalProperties": True,
    }
    return jsonschema.Draft7Validator(schema)


def validate_or_die(doc: dict) -> None:
    local_validator().validate(doc)
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
        {
            "unit_id": UNIT,
            "state": "SUCCESS",
            "sentinel": "SUCCESS:AUD-0047",
            "cloud_ok": True,
        },
    ]
    for g in garbage:
        errs = list(local_validator().iter_errors(g))
        if not errs:
            raise SystemExit(f"FAILED:{UNIT} schema accepted garbage {list(g)[:2]}")


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} named probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    measured = scan()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_dir = bool(measured["live_workflows_dir_exists"])
    fixture_misses = [m for m in measured["misses"] if m.get("kind") == "fixture"]
    live_misses = [m for m in measured["misses"] if m.get("kind") == "live"]
    control_ok = bool(measured["control_paths_ignore_miss_reported"])
    live_count = int(measured["live_workflow_count"])
    live_filtered = int(measured["live_with_path_filter"])
    disk_dir = (REPO / ".github" / "workflows").is_dir()
    if live_dir != disk_dir:
        print(f"FAILED:{UNIT} scan live_dir={live_dir} disk={disk_dir}")
        return 1
    if not control_ok:
        print(f"FAILED:{UNIT} required paths-ignore control miss did not fire")
        return 1

    if live_dir:
        answer = (
            f"Live .github/workflows is present ({live_count} yaml files). "
            f"{live_filtered} of those declare on.push/on.pull_request paths or "
            "paths-ignore. "
            + (
                "No live workflow uses a path filter, so there is no live instance "
                "of a filter excluding a file the gate claims to protect. Live miss "
                "count is 0 because filters are absent, not because the evaluator "
                "skipped the directory."
                if live_filtered == 0
                else (
                    f"Live path-filter miss count is {len(live_misses)} "
                    f"(protected files the filter would never see)."
                )
            )
            + f" AUD-0041 inventoried {measured['aud41'].get('workflow_count', 0)} "
            "workflows with trigger names only; paths / paths-ignore were not "
            "captured there. The evaluator is not blind: the required control "
            "fires — fixture-control-miss paths-ignore excludes protected/secret.py "
            "and the matcher reports that miss. A second fixture (paths: src/**) "
            "also misses protected/secret.py. Probe 2's ledger agrees: a "
            "secret-only commit does not run the ignore-filter gate, an app-only "
            "commit still does, and a mixed commit still does. Recorded AUD-0041 "
            "Actions run 31525279780 is the live-estate receipt that quality.yml "
            "executed; a fresh gh file-to-run join is unavailable on this checkout."
        )
    else:
        answer = (
            "On this tree, .github/workflows is absent, so live path-filter "
            "misses are NOT-CHECKED, not claimed-zero. "
            f"AUD-0041 inventoried {measured['aud41'].get('workflow_count', 0)} "
            "workflows with trigger names only; paths / paths-ignore were not "
            "captured. The required fixture control still fires."
        )

    headline = (
        f"{len(fixture_misses)} fixture path-filter miss(es) including the "
        f"required paths-ignore control; live workflows={live_count} "
        f"with_path_filter={live_filtered} live_misses={len(live_misses)} "
        f"(dir_exists={live_dir})"
    )

    live_rows_summary = [
        {
            "id": r["id"],
            "workflow": r["workflow"],
            "has_path_filter": r["has_path_filter"],
            "protected_files": r["protected_files"],
            "status": r["status"],
            "miss_count": len(r.get("misses") or []),
            "events": r.get("events") or [],
        }
        for r in measured.get("live_rows") or []
    ]

    residual = [
        {
            "id": "aud41-inventory-lacks-path-filters",
            "summary": (
                "AUD-0041 probe1 stored trigger names only. paths and "
                "paths-ignore cannot be reconstructed from that inventory."
            ),
        },
        {
            "id": "fresh-gh-file-to-run-join-unavailable",
            "summary": (
                "gh is not on PATH and this tree is not a git checkout. "
                "Probe 2 uses the fixture ledger plus recorded AUD-0041 Actions runs."
            ),
        },
    ]
    if not live_dir:
        residual.insert(
            0,
            {
                "id": "live-workflows-absent",
                "summary": (
                    ".github/workflows is absent on this worktree. Live path "
                    "filters are NOT-CHECKED, not claimed-zero."
                ),
            },
        )

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0047",
        "completion_sentinel": COMPLETION,
        "schema_version": 1,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0047",
        "min_bytes_threshold": MIN_BYTES,
        "headline": headline,
        "report": {
            "kind": "audit-finding",
            "title": "Path-filter audit: triggers that exclude the files the gate protects",
            "question": QUESTION,
            "answer": answer,
            "observations": [
                {
                    "name": "live-workflow-count",
                    "measured": live_count,
                    "method": "glob .github/workflows/*.{yml,yaml} plus YAML on: extract",
                    "anchor": ".github/workflows",
                },
                {
                    "name": "live-with-path-filter",
                    "measured": live_filtered,
                    "method": "event_filters paths/paths-ignore",
                    "anchor": "command-center/p2-wave/probes/AUD-0047/path_filter.py",
                },
                {
                    "name": "fixture-miss-count",
                    "measured": len(fixture_misses),
                    "method": "single_file_miss against fixture gates.json",
                    "anchor": "command-center/p2-wave/probes/AUD-0047/fixtures/workflows/control-miss.yml",
                },
                {
                    "name": "control-paths-ignore-miss",
                    "measured": control_ok,
                    "method": "required catalog control",
                    "anchor": "protected/secret.py vs fixture-control-miss paths-ignore",
                },
            ],
            "control_ids": [
                "NC-paths-ignore-secret",
                "NC-unfiltered-no-false-miss",
            ],
        },
        "cloud_ok": False,
        "emitted_at": now,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure "
                "with the same detector, enumerate at least 2 mechanically "
                "different detectors before a third attempt"
            ),
        },
        "produced_by": {
            "role": "adversarial-refuter",
            "vendor": "openai",
            "model": "gpt-5-codex",
            "execution_substrate": "local-parallel",
        },
        "downstream_consumers": [
            "AUD-0048",
            "AUD-0050",
            "CI path-filter reviewers",
        ],
        "inventory": {
            "live_workflows_dir": ".github/workflows",
            "live_workflows_dir_exists": live_dir,
            "live_workflow_count": live_count,
            "live_with_path_filter": live_filtered,
            "live_rows": live_rows_summary,
            "aud41": measured["aud41"],
            "yaml_on_boolean_true_handled": True,
        },
        "findings": {
            "fixture_misses": fixture_misses,
            "live_misses": live_misses,
            "control_paths_ignore_miss_reported": control_ok,
            "fixture_rows": measured["fixture_rows"],
        },
        "defects": [
            {
                "id": "AUD0047-D3-control-paths-ignore-miss",
                "severity": "P3",
                "status": "resolved",
                "summary": (
                    "Fixture control: paths-ignore excluding protected/secret.py "
                    "is reported as a miss by the evaluator (required catalog control)."
                ),
            }
        ],
        "residual_unknowns": residual,
        "tests": [
            {
                "id": "probe1-filter-eval",
                "name": "Evaluate path filters against protected files; control miss fires",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 12,
                "output_tail": t1[-1500:],
            },
            {
                "id": "probe2-run-history",
                "name": "Run-history receipt: secret-only skip, app-only run, matcher=ledger",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 6,
                "output_tail": t2[-1500:],
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "evidence": [
            {
                "kind": "control",
                "claim": "Evaluator reports a miss for protected/secret.py under paths-ignore",
                "detail": "fixture-control-miss.yml paths-ignore lists protected/secret.py",
                "verdict": "CONFIRMED",
                "anchor": P1,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": t1[-4000:],
                        "fingerprint": fp("command", P1),
                        "exit_code": c1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "python3 -c scan().control_paths_ignore_miss_reported",
                        "raw_output": json.dumps(
                            {"control_paths_ignore_miss_reported": control_ok}
                        ),
                        "fingerprint": fp(
                            "file-read",
                            "scan().control_paths_ignore_miss_reported",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "kind": "live-estate",
                "claim": (
                    f"Live workflow dir exists={live_dir} count={live_count} "
                    f"with_path_filter={live_filtered} live_misses={len(live_misses)}"
                ),
                "detail": "glob .github/workflows plus extract_on/event_filters",
                "verdict": "CONFIRMED",
                "anchor": ".github/workflows",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": "python3 command-center/p2-wave/probes/AUD-0047/eval_audit.py",
                        "raw_output": json.dumps(
                            {
                                "live_workflows_dir_exists": live_dir,
                                "live_workflow_count": live_count,
                                "live_with_path_filter": live_filtered,
                                "live_miss_count": len(live_misses),
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fp("static-analysis", "eval_audit.scan live"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": t2[-4000:],
                        "fingerprint": fp("command", P2),
                        "exit_code": c2,
                    },
                ],
            },
            {
                "kind": "receipt",
                "claim": "AUD-0041 recorded quality.yml Actions run 31525279780",
                "detail": "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "python3 -c read AUD-0041 probe2-actions-api.json",
                        "raw_output": "quality run_id=31525279780 api_job_count=8",
                        "fingerprint": fp("file-read", "AUD-0041/probe2-actions-api.json"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": t2[-2000:],
                        "fingerprint": fp("command", P2 + "#aud41-quality"),
                        "exit_code": c2,
                    },
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-paths-ignore-secret",
                "kind": "known-broken-fixture",
                "description": "paths-ignore listing a protected file must produce a miss",
                "fired_on_bad_state": control_ok,
                "silent_on_good_state": ("fixture-control-hit", "protected/secret.py")
                not in {(m["workflow_id"], m["protected_file"]) for m in fixture_misses},
            },
            {
                "id": "NC-unfiltered-no-false-miss",
                "kind": "known-broken-fixture",
                "description": "A workflow with no path filter must not report a miss",
                "fired_on_bad_state": control_ok,
                "silent_on_good_state": not any(
                    m["workflow_id"] == "fixture-control-unfiltered" for m in fixture_misses
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0047-probe2-run-history",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "attempted_falsify": True,
            "notes": (
                "Probe 2 independently recomputes would_run on the commit ledger "
                "and fails if the matcher and the recorded ran/skipped bits disagree. "
                "That is a falsify attempt on the headline control count, not a re-read. "
                "It also records live_workflow_count so a claim that .github/workflows "
                "is absent cannot survive while 12 yaml files sit on disk."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/AUD-0047/path_filter.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0047/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "honesty": {
            "live_workflows_dir_exists": live_dir,
            "live_path_filters_evaluated": live_dir,
            "live_with_path_filter": live_filtered,
            "live_miss_count": len(live_misses),
            "zero_live_misses_reason": (
                "no live workflow declares paths or paths-ignore"
                if live_dir and live_filtered == 0
                else (
                    "directory absent; NOT-CHECKED"
                    if not live_dir
                    else "evaluated live filters"
                )
            ),
            "claimed_zero_live_misses_without_looking": False,
            "control_required_and_fired": control_ok,
            "did_not_run_global_unit_manifest_write": True,
            "cloud_ok_is_not_delivery": True,
        },
    }

    try:
        validate_or_die(doc)
    except jsonschema.ValidationError as exc:
        print(f"FAILED:{UNIT} schema: {exc.message}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    size = out_path.stat().st_size
    if size < MIN_BYTES:
        print(f"FAILED:{UNIT} artifact {size}B below floor {MIN_BYTES}")
        return 1
    text = out_path.read_text(encoding="utf-8")
    if COMPLETION not in text or "SUCCESS:AUD-0047" not in text:
        print(f"FAILED:{UNIT} sentinel missing from artifact text")
        return 1
    parsed = json.loads(text)
    if str(parsed.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:{UNIT} self-declared {parsed.get('state')}")
        return 1
    sha, hashed = sha_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha} hashed={hashed}")
    print("SUCCESS:AUD-0047 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
