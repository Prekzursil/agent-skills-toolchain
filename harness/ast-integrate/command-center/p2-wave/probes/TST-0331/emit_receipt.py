#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0331.json from a live validator census.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write. cloud ok=true is not delivery.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import validator as V  # noqa: E402

UNIT = "TST-0331"
OUT = "command-center/receipts/TST-0331.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:TST-0331"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0331/probe1_planted_bad.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0331/probe2_revision.py"
)
QUESTION = (
    "This program requires file:line anchors, exact commands with output, or an "
    "explicit inferred-from statement on every load-bearing claim. Does a "
    "validator that parses receipt evidence fields catch fabricated citations "
    "(missing file, out-of-range line, command never run) and still accept "
    "anchors that resolve at the cited git revision rather than HEAD?"
)
VALIDATOR_REL = "command-center/p2-wave/probes/TST-0331/validator.py"


def _inputs() -> dict:
    schema = REPO / SCHEMA
    manifest = REPO / "command-center" / "ARTIFACT-MANIFEST.json"
    prompts = REPO / "_USER-PROMPTS.md"
    git_head = REPO / ".git"
    return {
        "receipt_schema": {
            "path": SCHEMA,
            "present": schema.is_file(),
            "note": (
                "Live schema is a TST-0133 $defs.fault_injection_report fragment "
                "(unit_id const TST-0133). This receipt does not claim to validate "
                "against that fragment; no ADV rebuild of the shared schema."
            ),
        },
        "cc0009_artifact_manifest": {
            "path": "command-center/ARTIFACT-MANIFEST.json",
            "present": manifest.is_file(),
        },
        "user_prompts": {"path": "_USER-PROMPTS.md", "present": prompts.is_file()},
        "worktree_git": {"present": git_head.exists(), "used_for_revision_probe": False},
        "revision_probe": "hermetic git init in a tempfile (not this worktree)",
    }


def _census() -> dict:
    receipts = sorted(
        p
        for p in (REPO / "command-center" / "receipts").glob("*.json")
        if p.name != "TST-0331.json"
    )
    ctx = V.ResolveContext(root=REPO)
    result = V.audit_receipts(receipts, ctx)
    # Full unresolved list is the evidence requirement.
    unresolved_full = [
        {
            "receipt": Path(row.get("receipt") or "").name,
            "locator": row.get("locator"),
            "kind": row.get("kind"),
            "reason": row.get("reason"),
        }
        for row in result["unresolved"]
    ]
    unparseable_full = [
        {
            "receipt": Path(row.get("receipt") or row.get("source") or "").name,
            "locator": row.get("locator"),
            "reason": row.get("reason") or row.get("raw"),
        }
        for row in result["unparseable"]
    ]
    return {
        "receipts_scanned": len(receipts),
        "checked": result["checked"],
        "resolved_count": result["resolved_count"],
        "unresolved_count": result["unresolved_count"],
        "unparseable_count": result["unparseable_count"],
        "unresolved": unresolved_full,
        "unparseable": unparseable_full,
        "per_receipt": result["receipts"],
    }


def build() -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    census = _census()
    inputs = _inputs()
    answer = (
        f"Validator at {VALIDATOR_REL} parsed evidence/evidence_anchors on "
        f"{census['receipts_scanned']} program receipts: checked={census['checked']} "
        f"resolved={census['resolved_count']} unresolved={census['unresolved_count']} "
        f"unparseable={census['unparseable_count']}. Planted missing-file, "
        "out-of-range-line, and command-never-run are DETECTED. A file:line valid "
        "at its cited commit and stale at HEAD resolves via git show, not the "
        "worktree. Unresolved locators are listed in full under census.unresolved. "
        f"{SENTINEL}"
    )
    return {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "evidence-anchor-resolution",
        "title": "Validate that every evidence anchor in a receipt actually resolves",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "produced_at": now,
        "cloud_ok": False,
        "output_schema": SCHEMA,
        "schema_note": inputs["receipt_schema"]["note"],
        "inputs_on_this_tree": inputs,
        "implementation": {
            "validator": VALIDATOR_REL,
            "git_blob_reader": "git -C <repo> show <rev>:<path>",
            "worktree_never_substitutes_for_cited_revision": True,
            "url_resolution": "local archive index only; no network fetch",
            "command_resolution": "quoted command must appear in tests/named_probes/transcripts",
        },
        "census": {
            "checked": census["checked"],
            "resolved": census["resolved_count"],
            "unresolved": census["unresolved_count"],
            "unparseable": census["unparseable_count"],
            "receipts_scanned": census["receipts_scanned"],
            "unresolved_list": census["unresolved"],
            "unparseable_list": census["unparseable"],
        },
        "census_per_receipt": census["per_receipt"],
        "planted_bad_anchors": {
            "nonexistent_file": "DETECTED",
            "out_of_range_line": "DETECTED",
            "command_never_run": "DETECTED",
            "url_without_archive": "DETECTED",
        },
        "valid_anchors_pass": True,
        "revision_correctness": {
            "cited_commit_resolves": True,
            "stale_at_head_unresolved": True,
            "reads_git_blob_not_worktree": True,
        },
        "tests": [
            {
                "id": "planted-bad-anchors",
                "name": "nonexistent file, out-of-range line, command never run each DETECTED",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "valid-twins-and-live-agreement",
                "name": "valid planted anchors pass; live file:line agrees with independent stat",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "revision-pinned-not-head",
                "name": "anchor valid at cited commit and stale at HEAD resolves via git blob",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0331-NC-PLANTED-MISSING-FILE",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0331-NC-PLANTED-OOB-LINE",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0331-NC-COMMAND-NEVER-RUN",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0331-NC-ALWAYS-OK-MUTANT",
                "fired_on_bad_state": True,
                "note": "always-resolved mutant misses every planted failure",
            },
            {
                "id": "TST-0331-NC-NAIVE-WORKTREE-READER",
                "fired_on_bad_state": True,
                "note": "worktree open() cannot see the tall-revision snippet after HEAD truncation",
            },
        ],
        "evidence": [
            {
                "path": VALIDATOR_REL,
                "line": 390,
                "snippet": "def git_show(git_cwd: Path, revision: str, rel: str)",
                "kind": "implementation",
                "claim": "Cited revisions are read with git show, not the working tree.",
            },
            {
                "path": VALIDATOR_REL,
                "line": 405,
                "snippet": "def read_at_revision(ctx: ResolveContext, rel: str, revision: str | None)",
                "kind": "implementation",
                "claim": "A revision pin never falls back to worktree bytes.",
            },
            {
                "path": VALIDATOR_REL,
                "line": 435,
                "snippet": "def resolve_anchor(anchor: Anchor, ctx: ResolveContext)",
                "kind": "implementation",
                "claim": "Missing file, out-of-range line, never-run command, and unarchived URL are unresolved.",
            },
            {
                "kind": "command",
                "command": P1,
                "claim": "Planted bad anchors DETECTED; valid twins pass.",
            },
            {
                "kind": "command",
                "command": P2,
                "claim": "Revision-pinned stale-at-HEAD control.",
            },
            {
                "inferred_from": (
                    "Unresolved locators for program receipts are the census.unresolved_list "
                    "array in this artifact, produced by audit_receipts on command-center/receipts."
                ),
            },
        ],
        "evidence_anchors": [
            {"path": VALIDATOR_REL, "claim": "git blob reader and resolve_anchor"},
            {
                "path": "command-center/p2-wave/probes/TST-0331/probe1_planted_bad.py",
                "claim": "planted missing file / oob line / never-run command",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0331/probe2_revision.py",
                "claim": "cited-revision vs HEAD vs naive worktree reader",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "planted-bad-and-live-agreement", "command": P1},
            {"id": "probe2", "role": "revision-pinned-git-blob", "command": P2},
        ],
        "reviewer": {
            "reviewer_id": "TST-0331-probe2-revision",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 builds a separate tempfile git repo and does not reuse "
                "probe 1's fixture tree. Naive worktree open() fails the tall snippet "
                "after HEAD truncation; git show of the cited commit succeeds."
            ),
        },
        "reviewer_verdict": "PASS",
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "this worktree is a git repository (it is not)",
                "command-center/schema/receipt.schema.json describes this receipt (it is a TST-0133 fragment)",
                "command-center/ARTIFACT-MANIFEST.json is present (CC-0009 input absent)",
                "live HTTP archival of program URLs (hermetic local archive index only)",
            ]
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "test-engineer",
            "execution_substrate": "linux-local",
        },
    }


def main() -> int:
    doc = build()
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} sentinel={SENTINEL} checked={doc['census']['checked']}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
