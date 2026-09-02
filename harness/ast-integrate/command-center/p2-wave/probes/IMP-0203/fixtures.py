"""Deterministic IMP-0203 fixtures. Clock is injected; never wall time."""
from __future__ import annotations

import copy
import hashlib
from typing import Any

# Injected clock. All expiry tests use these instants only.
NOW = "2026-08-24T18:00:00Z"
ISSUED = "2026-08-01T00:00:00Z"
EXPIRY_FUTURE = "2026-09-24T18:00:00Z"
EXPIRY_PAST = "2026-07-24T18:00:00Z"

CORPUS_CURRENT = "corpus-2026.08.1"
CORPUS_SUPERSEDED = "corpus-2026.08.2"
SPEC_CURRENT = "7.0.0"
SPEC_SUPERSEDED = "7.1.0"

ANCHOR_PATH = "command-center/p2-wave/probes/IMP-0203/fixtures/evidence-row.json"
ANCHOR_SHA = hashlib.sha256(b"imp-0203-fixture-evidence\n").hexdigest()


def current_record() -> dict[str, Any]:
    return {
        "schema_id": "certification-record/v1",
        "workflow_id": "wf.paired-benchmark",
        "version": "1.2.0",
        "corpus_version": CORPUS_CURRENT,
        "spec_version": SPEC_CURRENT,
        "evidence": {
            "anchor": {
                "path": ANCHOR_PATH,
                "sha256": ANCHOR_SHA,
            },
            "kind": "outperform",
            "summary": "Paired delta vs source on corpus-2026.08.1; n>=min-cases.",
        },
        "confirmer": {
            "id": "imp-0202-independent-confirmer",
            "kind": "artifact-citing",
            "cited_paths": [ANCHOR_PATH],
        },
        "tier": "standard",
        "issued_at": ISSUED,
        "expiry": EXPIRY_FUTURE,
    }


def no_evidence_record() -> dict[str, Any]:
    rec = current_record()
    rec.pop("evidence")
    return rec


def no_anchor_record() -> dict[str, Any]:
    rec = current_record()
    rec["evidence"] = {
        "kind": "outperform",
        "summary": "Looks good; no path and no digest.",
    }
    return rec


def empty_anchor_path_record() -> dict[str, Any]:
    rec = current_record()
    rec["evidence"] = copy.deepcopy(rec["evidence"])
    rec["evidence"]["anchor"]["path"] = ""
    return rec
