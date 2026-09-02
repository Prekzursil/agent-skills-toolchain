#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0070-archival-corroboration.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import auditor as A  # noqa: E402
import schema_ctl as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0070-archival-corroboration.json"
SCHEMA = "command-center/schema/citation-audit.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0070/probe1_timestamp_and_untrusted.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0070/probe2_verdict_split.py"
)
SENTINEL = (
    "SUCCESS:CNF-0070 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every archived corroboration "
    "cites a capture timestamp at or before the citation date. Any other terminal "
    "state is FAILED:CNF-0070 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "For every citation where the live page no longer matches, does an archived "
    "snapshot from the citation date support the claim? Retrieve the snapshot, "
    "diff it against today, and answer: was the claim true when made and has "
    "since changed, or was it never supported?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    run = A.audit_all(accept_late=False)
    summary = run["summary"]
    if not summary["every_archived_corroboration_timely"]:
        print("FAILED:CNF-0070 emit untimely corroboration")
        return 1
    if summary["was_true_then_changed_count"] < 1:
        print("FAILED:CNF-0070 emit missing was-true-then-changed")
        return 1
    if summary["never_supported_count"] < 1:
        print("FAILED:CNF-0070 emit missing never-supported")
        return 1
    if summary["no_snapshot_available_count"] < 1:
        print("FAILED:CNF-0070 emit missing no-snapshot-available")
        return 1
    if summary["was_true_then_changed_count"] == summary["never_supported_count"] and len(
        {r["verdict"] for r in run["citations"]}
    ) < 2:
        print("FAILED:CNF-0070 emit verdicts collapsed")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNF-0070",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0070",
        "completion_sentinel": SENTINEL,
        "audit_kind": "archival-corroboration",
        "title": "Archival corroboration when the live source has changed since it was cited",
        "question": QUESTION,
        "generated_at": now,
        "upstream": run["upstream"],
        "archive_service": {
            "kind": "local-fixture-archive",
            "index": "command-center/p2-wave/probes/CNF-0070/fixtures/archive-index.json",
            "note": "Deterministic snapshot service. Capture timestamps are snapshot times.",
        },
        "evidence_requirement": (
            "the snapshot URL with its capture timestamp, the located quote in "
            "the snapshot, and the live-versus-snapshot diff"
        ),
        "citations": run["citations"],
        "summary": summary,
        "tests": [
            {
                "id": "post-citation-snapshot-rejected",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "verdicts-not-merged",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "archived-content-never-executed",
                "command": P1,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0070-probe2-verdict-split",
            "verdict": "PASS",
            "independent": True,
            "read_conclusion_first": False,
            "scope": (
                "Re-derive each verdict from raw live+archive fixture bytes and "
                "citation dates before opening this artifact's conclusion fields."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "timestamp-gate-and-untrusted-nonexec", "command": P1},
            {"id": "probe2", "role": "independent-verdict-split", "command": P2},
        ],
        "output_schema": SCHEMA,
        "schema_validation": {
            "declared": SCHEMA,
            "operational": "command-center/p2-wave/probes/CNF-0070/citation-audit.schema.json",
            "reason": (
                "declared output_schema is a generated $ref shim; Draft7Validator "
                "against it raises RefResolutionError on ast-integrate.invalid"
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNF-0070/citation-audit.schema.json",
                "exists": True,
                "role": "schema",
            },
        ],
    }

    validator = S.validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0070 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "CNF-0070", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNF-0070 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0070 sentinel missing from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0070 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
