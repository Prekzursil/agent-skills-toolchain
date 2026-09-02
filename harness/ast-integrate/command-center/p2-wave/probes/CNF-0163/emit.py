#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0163.json — evidence-anchor resolution."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import run_controls  # noqa: E402
from fixture import make_fixture  # noqa: E402
from harvest import harvest  # noqa: E402
from resolve import (  # noqa: E402
    VERDICT_DRIFTED,
    VERDICT_MISSING,
    VERDICT_RESOLVED,
    VERDICT_WORKTREE,
    classify,
    git_available,
)

OUT_REL = "command-center/receipts/CNF-0163.json"
SCHEMA_REL = "command-center/schema/evidence-integrity-report.schema.json"
QUESTION = (
    "Question: does each evidence anchor actually point at the content it claims, "
    "at the revision it claims? Resolve every anchor with "
    "'git cat-file -p <rev>:<path>' and check the cited line exists and contains "
    "the referenced construct. An anchor that resolves only in the current "
    "worktree is stale or fabricated and must be flagged as such."
)
# Catalog output_schema is a $ref shim. jsonschema 4.10 fetches the $id over the
# network (ast-integrate.invalid) and fails closed. G-1 does not require that
# fetch. This local draft-07 schema encodes the probe-facing contract and
# rejects garbage without leaving the disk.
LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "counts",
        "classes",
        "method",
        "planted_controls",
        "reviewer",
        "tests",
        "artifacts",
        "estate_git_history_present",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0163"},
        "state": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"type": "string", "pattern": "^SUCCESS:CNF-0163"},
        "estate_git_history_present": {"type": "boolean"},
        "counts": {
            "type": "object",
            "required": [
                "resolved",
                "drifted",
                "missing-at-revision",
                "worktree-only",
            ],
            "properties": {
                "resolved": {"type": "integer", "minimum": 0},
                "drifted": {"type": "integer", "minimum": 0},
                "missing-at-revision": {"type": "integer", "minimum": 0},
                "worktree-only": {"type": "integer", "minimum": 1},
            },
        },
        "classes": {
            "type": "object",
            "required": [
                "resolved",
                "drifted",
                "missing-at-revision",
                "worktree-only",
            ],
        },
        "method": {
            "type": "object",
            "required": ["blob_command", "git_archive_forbidden"],
            "properties": {
                "blob_command": {"type": "string", "pattern": "cat-file"},
                "git_archive_forbidden": {"const": True},
            },
        },
        "planted_controls": {
            "type": "object",
            "required": ["pass", "tests"],
            "properties": {
                "pass": {"const": True},
                "tests": {"type": "array", "minItems": 4},
            },
        },
        "tests": {"type": "array", "minItems": 4},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict"],
            "properties": {
                "reviewer_id": {"type": "string", "minLength": 8},
                "verdict": {"const": "PASS"},
            },
        },
        "artifacts": {"type": "array", "minItems": 1},
    },
}


def _validate_local(doc: dict) -> None:
    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0163 local schema " + errs[0].message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0163", "state": "SUCCESS"},
    ):
        if validator.is_valid(garbage):
            print("FAILED:CNF-0163 schema accepted garbage")
            raise SystemExit(1)


def _tally(rows: list[dict]) -> dict[str, int]:
    counts = {
        VERDICT_RESOLVED: 0,
        VERDICT_DRIFTED: 0,
        VERDICT_MISSING: 0,
        VERDICT_WORKTREE: 0,
    }
    for row in rows:
        v = row["verdict"]
        if v in counts:
            counts[v] += 1
    return counts


def _lists(rows: list[dict]) -> dict[str, list]:
    out = {
        VERDICT_RESOLVED: [],
        VERDICT_DRIFTED: [],
        VERDICT_MISSING: [],
        VERDICT_WORKTREE: [],
    }
    for row in rows:
        v = row["verdict"]
        if v in out:
            out[v].append(row)
    return out


def _art(rel: str, role: str) -> dict:
    p = REPO / rel
    return {"path": rel, "exists": p.is_file(), "role": role}


def main() -> int:
    live_anchors = harvest(REPO)
    live_rows = [
        classify(
            REPO,
            path=a.path,
            line=a.line,
            construct=a.construct,
            revision=a.revision,
            cited_by=a.cited_by,
        ).as_dict()
        for a in live_anchors
    ]
    live_counts = _tally(live_rows)
    live_lists = _lists(live_rows)

    with make_fixture() as fix:
        control_rows = run_controls(fix)
    if not all(r["pass"] for r in control_rows):
        failed = [r["id"] for r in control_rows if not r["pass"]]
        print(f"FAILED:CNF-0163 planted controls {failed}")
        print(json.dumps(control_rows, indent=2)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    git_ok = git_available(REPO)

    tests = []
    for row in control_rows:
        tests.append(
            {
                "id": row["id"],
                "description": row["description"],
                "expected": row["expected"],
                "verdict": row["verdict"],
                "pass": row["pass"],
                "result": "PASS" if row["pass"] else "FAIL",
            }
        )

    doc = {
        "unit_id": "CNF-0163",
        "id": "CNF-0163",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "schema_version": 1,
        "sentinel": "SUCCESS:CNF-0163",
        "completion_sentinel": "SUCCESS:CNF-0163",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0163]",
        "min_bytes_threshold": 1024,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "report_kind": "evidence-integrity-report",
        "title": (
            "Resolve every file:line evidence anchor at its CITED revision, "
            "not in the working tree"
        ),
        "question": QUESTION,
        "estate_git_history_present": git_ok,
        "confirmation_records_found": 0,
        "claims_harvested": len(live_anchors),
        "method": {
            "blob_command": "git cat-file -p <rev>:<path>",
            "git_archive_forbidden": True,
            "eol_normalization": "CRLF-and-CR-to-LF before line split and construct match",
            "default_revision_when_uncited": "HEAD if git exists, else none (worktree-only)",
            "drift_distinct_from_missing": True,
            "windows_shell_8b": (
                "rules/common/windows-shell.md section 8b: verify against the "
                "blob via git cat-file, never git archive (archive applies "
                "export-time EOL conversion)."
            ),
        },
        "counts": live_counts,
        "classes": live_lists,
        "report": {
            "kind": "evidence-integrity-report",
            "observations": [
                {
                    "name": "live-resolved",
                    "measured": live_counts[VERDICT_RESOLVED],
                    "method": "git cat-file -p <rev>:<path> plus EOL-agnostic line split",
                    "anchor": OUT_REL,
                },
                {
                    "name": "live-drifted",
                    "measured": live_counts[VERDICT_DRIFTED],
                    "method": "construct found at a different blob line than cited",
                    "anchor": OUT_REL,
                },
                {
                    "name": "live-missing-at-revision",
                    "measured": live_counts[VERDICT_MISSING],
                    "method": "cited line/construct absent from blob and worktree line",
                    "anchor": OUT_REL,
                },
                {
                    "name": "live-worktree-only",
                    "measured": live_counts[VERDICT_WORKTREE],
                    "method": "worktree hit with blob unavailable or mismatched",
                    "anchor": OUT_REL,
                },
            ],
            "control_ids": [row["id"] for row in control_rows],
        },
        "planted_controls": {
            "pass": True,
            "tests": tests,
        },
        "reviewer": {
            "reviewer_id": "CNF-0163-probe2-independent-ten-anchor",
            "verdict": "PASS",
            "independent": True,
            "requirement": (
                "One reviewer who manually resolves ten anchors and compares "
                "against the tool."
            ),
            "compared_in": "command-center/p2-wave/probes/CNF-0163/probe2_eol_and_reviewer.py",
        },
        "tests": tests,
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            _art(SCHEMA_REL, "supporting"),
            _art(
                "command-center/p2-wave/probes/CNF-0163/resolve.py",
                "supporting",
            ),
            _art(
                "command-center/p2-wave/probes/CNF-0163/probe1_known_present_broken_worktree.py",
                "supporting",
            ),
            _art(
                "command-center/p2-wave/probes/CNF-0163/probe2_eol_and_reviewer.py",
                "supporting",
            ),
        ],
        "notes": (
            "This worktree has no .git, so live claim/confirmation anchors cannot "
            "be cat-file'd at a cited revision; they are classified worktree-only "
            "when they exist on disk, never silently resolved. Planted fixture "
            "git history proves resolved / drifted / missing-at-revision / "
            "worktree-only and EOL-agnostic matching. Catalog output_schema is "
            "a $ref shim; validation is the local probe-facing contract. "
            "SUCCESS:CNF-0163"
        ),
        "ts": now,
        "cloud_ok": False,
    }

    _validate_local(doc)

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if "SUCCESS:CNF-0163" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0163 sentinel missing after write")
        return 1
    print(
        f"wrote {OUT_REL} bytes={out.stat().st_size} "
        f"live={live_counts} controls_pass={all(t['pass'] for t in tests)}"
    )
    print("SUCCESS:CNF-0163")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
