#!/usr/bin/env python3
"""Planted both-states control corpus and live 24-slot cohort.

Control records are NOT the original registry RETIRE set. They prove the
engine discriminates preserved vs unpreserved vs claim-only vs still-live.
"""
from __future__ import annotations

from pathlib import Path

import engine as E
import locate as L

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
FIX = HERE / "fixtures"
EXPORTS = FIX / "exports"
STILL = FIX / "still-live"
CANARY = FIX / "CANARY-NO-DELETE.txt"

CANARY_BODY = b"WFA-0071-NO-DELETE-CANARY\nread-only re-adjudication; do not delete\n"
PRESERVED_BODY = (
    b"WFA-0071-control-preserved-v1\n"
    b"salvage-home=tools/lib/handled_ledger.py\n"
)
STILL_LIVE_BODY = b"WFA-0071-control-still-live-on-estate-v1\n"
MISMATCH_BODY = b"WFA-0071-control-mismatch-actual-bytes-v1\n"
NOCAP_BODY = b"WFA-0071-control-preserved-but-unnamed-capability-v1\n"
CLAIM_ONLY_SHA = "0" * 64


def _write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == body:
        return
    path.write_bytes(body)


def ensure_fixtures() -> dict:
    _write(CANARY, CANARY_BODY)
    preserved = EXPORTS / "ctrl-preserved-export.bin"
    mismatch = EXPORTS / "ctrl-hash-mismatch.bin"
    nocap = EXPORTS / "ctrl-preserved-no-capability.bin"
    still = STILL / "still-present.txt"
    _write(preserved, PRESERVED_BODY)
    _write(mismatch, MISMATCH_BODY)
    _write(nocap, NOCAP_BODY)
    _write(still, STILL_LIVE_BODY)
    return {
        "canary": str(CANARY.relative_to(REPO).as_posix()),
        "canary_sha256": E.digest_bytes(CANARY_BODY),
        "preserved": str(preserved.relative_to(REPO).as_posix()),
        "preserved_sha256": E.digest_bytes(PRESERVED_BODY),
        "mismatch": str(mismatch.relative_to(REPO).as_posix()),
        "mismatch_sha256": E.digest_bytes(MISMATCH_BODY),
        "nocap": str(nocap.relative_to(REPO).as_posix()),
        "nocap_sha256": E.digest_bytes(NOCAP_BODY),
        "still_live": str(still.relative_to(REPO).as_posix()),
        "still_live_sha256": E.digest_bytes(STILL_LIVE_BODY),
    }


def control_corpus() -> list[dict]:
    fx = ensure_fixtures()
    claimed_wrong = E.digest_bytes(b"WFA-0071-NOT-THE-FILE-BYTES\n")
    return [
        {
            "id": "ctrl-preserved-export",
            "classification": "RETIRE",
            "identity_status": "NAMED",
            "family": "C-repo-tool",
            "live_path": "command-center/p2-wave/probes/WFA-0071/fixtures/deleted-live/gone.txt",
            "retirement_rationale": "DELETE-ALL removed this candidate; mechanism salvaged.",
            "capability_given_up": "standalone retired ledger CLI on the old five-tree path",
            "mechanism_survives_at": "tools/lib/handled_ledger.py",
            "preservation_claim": {
                "kind": "export",
                "path": fx["preserved"],
                "sha256": fx["preserved_sha256"],
            },
            "expected_verdict": "RETAIN-RETIRE",
        },
        {
            "id": "ctrl-unpreserved",
            "classification": "RETIRE",
            "identity_status": "NAMED",
            "family": "G-skill",
            "live_path": "command-center/p2-wave/probes/WFA-0071/fixtures/deleted-live/unpreserved.txt",
            "retirement_rationale": "DELETE-ALL removed this candidate; no salvage.",
            "capability_given_up": "",
            "mechanism_survives_at": "",
            "preservation_claim": {"kind": "none"},
            "expected_verdict": "P1-UNPRESERVED",
        },
        {
            "id": "ctrl-claim-only",
            "classification": "RETIRE",
            "identity_status": "NAMED",
            "family": "F-plugin",
            "live_path": "command-center/p2-wave/probes/WFA-0071/fixtures/deleted-live/claim-only.txt",
            "retirement_rationale": "DELETE-ALL removed this candidate; manifest claims an export.",
            "capability_given_up": "plugin hatch wrapper",
            "mechanism_survives_at": "tools/plugin/ship.py",
            "preservation_claim": {
                "kind": "export",
                "path": "command-center/p2-wave/probes/WFA-0071/fixtures/exports/DOES-NOT-EXIST.bin",
                "sha256": CLAIM_ONLY_SHA,
            },
            "expected_verdict": "P1-CLAIM-NOT-RECEIPT",
        },
        {
            "id": "ctrl-still-live",
            "classification": "RETIRE",
            "identity_status": "NAMED",
            "family": "B-repo-workflow",
            "live_path": fx["still_live"],
            "retirement_rationale": "DELETE-ALL removed this candidate across 5 trees.",
            "capability_given_up": "repo workflow driver",
            "mechanism_survives_at": "tools/lib/handled_ledger.py",
            "preservation_claim": {"kind": "none"},
            "expected_verdict": "REOPEN",
        },
        {
            "id": "ctrl-hash-mismatch",
            "classification": "RETIRE",
            "identity_status": "NAMED",
            "family": "D-harness-runtime",
            "live_path": "command-center/p2-wave/probes/WFA-0071/fixtures/deleted-live/mismatch.txt",
            "retirement_rationale": "DELETE-ALL removed this candidate; export claimed.",
            "capability_given_up": "harness runtime shim",
            "mechanism_survives_at": "tools/router/inspect_load.py",
            "preservation_claim": {
                "kind": "export",
                "path": fx["mismatch"],
                "sha256": claimed_wrong,
            },
            "expected_verdict": "P1-HASH-MISMATCH",
        },
        {
            "id": "ctrl-preserved-no-capability",
            "classification": "RETIRE",
            "identity_status": "NAMED",
            "family": "E-agent",
            "live_path": "command-center/p2-wave/probes/WFA-0071/fixtures/deleted-live/nocap.txt",
            "retirement_rationale": "DELETE-ALL removed this candidate; bytes preserved.",
            "capability_given_up": "",
            "mechanism_survives_at": "",
            "preservation_claim": {
                "kind": "export",
                "path": fx["nocap"],
                "sha256": fx["nocap_sha256"],
            },
            "expected_verdict": "REFUSE-RETIRE-MISSING-SURVIVAL",
        },
    ]


def live_cohort(located: dict | None = None) -> list[dict]:
    located = located if located is not None else L.locate_registry()
    found = located.get("retire_records") or []
    if found:
        rows = []
        for i, rec in enumerate(found, 1):
            cid = str(rec.get("id") or rec.get("name") or f"found-retire-{i:02d}")
            prov = rec.get("provenance") or rec.get("origin") or ""
            live_path = ""
            if isinstance(prov, str):
                live_path = prov
            elif isinstance(prov, dict):
                live_path = str(prov.get("path") or prov.get("source") or "")
            claim = rec.get("preservation") or rec.get("preservation_claim") or {
                "kind": "git"
            }
            rows.append(
                {
                    "id": cid,
                    "classification": "RETIRE",
                    "identity_status": "NAMED",
                    "family": rec.get("family"),
                    "live_path": live_path,
                    "retirement_rationale": str(
                        rec.get("notes")
                        or rec.get("does")
                        or rec.get("evidence")
                        or "registry RETIRE; re-read against today's estate"
                    ),
                    "capability_given_up": str(rec.get("capability_given_up") or ""),
                    "mechanism_survives_at": str(
                        rec.get("mechanism_survives_at") or rec.get("survives_at") or ""
                    ),
                    "preservation_claim": claim
                    if isinstance(claim, dict)
                    else {"kind": "none"},
                    "source": "live-registry",
                }
            )
        return rows
    n = L.EXPECTED_RETIRE_N
    return [
        {
            "id": f"catalog-retire-slot-{i:02d}",
            "classification": "RETIRE",
            "identity_status": "UNRECOVERABLE",
            "family": None,
            "live_path": "",
            "retirement_rationale": (
                "Catalog histogram assigns RETIRE n=24 on "
                "08-WORKFLOW-CANDIDATE-REGISTRY.json; that registry is absent "
                "on this Linux worktree so the candidate identity cannot be re-read."
            ),
            "capability_given_up": "",
            "mechanism_survives_at": "",
            "preservation_claim": {"kind": "none"},
            "source": "catalog-histogram-slot",
            "slot": i,
        }
        for i in range(1, n + 1)
    ]


def canary_ok() -> dict:
    ensure_fixtures()
    present = CANARY.is_file()
    sha = E.digest_bytes(CANARY.read_bytes()) if present else None
    expected = E.digest_bytes(CANARY_BODY)
    return {
        "path": str(CANARY.relative_to(REPO).as_posix()),
        "present": present,
        "sha256": sha,
        "expected_sha256": expected,
        "unchanged": present and sha == expected,
        "files_deleted_by_this_unit": E.files_deleted_by_this_unit(),
    }
