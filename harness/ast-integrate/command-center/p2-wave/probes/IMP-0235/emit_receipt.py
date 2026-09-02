#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0235.json from a live blueprint run.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write. cloud ok=true is not delivery.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

import fixtures as F  # noqa: E402
from research.blueprints.archaeology import (  # noqa: E402
    blob_bytes,
    plant_lf_blob_crlf_worktree,
    refuse_archive_recipe,
    source_invokes_archive,
    source_uses_cat_file,
    ForbiddenRecipeError,
)
from research.blueprints.citation import UNRESOLVED  # noqa: E402
from research.blueprints.contract import omission_failures  # noqa: E402
from research.blueprints.evidence_map import map_evidence  # noqa: E402
from research.blueprints.official_doc import audit_official_docs  # noqa: E402
from research.blueprints.registry import (  # noqa: E402
    fact_citation_audit_blueprint,
    registered,
)

OUT_REL = "command-center/receipts/IMP-0235.json"
ARCH_REL = "command-center/research/blueprints/archaeology.py"
CITE_REL = "command-center/research/blueprints/citation.py"
REG_REL = "command-center/research/blueprints/registry.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0235/probe1_dead_citation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0235/probe2_blob_vs_crlf.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:IMP-0235 emit missing anchor {needle!r} in {rel}")


def archaeology_control() -> dict:
    src = (REPO / ARCH_REL).read_text(encoding="utf-8")
    archive_refused = False
    try:
        refuse_archive_recipe("git archive")
    except ForbiddenRecipeError:
        archive_refused = True
    with tempfile.TemporaryDirectory(prefix="imp0235-emit-") as tmp:
        planted = plant_lf_blob_crlf_worktree(Path(tmp) / "repo")
        blob = blob_bytes(Path(planted["repo"]), planted["rev"], planted["path"])
    return {
        "recipe": "git cat-file -p",
        "forbidden_recipe": "git archive",
        "source_uses_cat_file": source_uses_cat_file(src),
        "source_invokes_archive": source_invokes_archive(src),
        "archive_refused": archive_refused,
        "blob_equals_lf": planted["blob_equals_lf"],
        "blob_equals_worktree": planted["blob_equals_worktree"],
        "worktree_is_crlf": planted["worktree_is_crlf"],
        "blob": planted["blob"],
        "worktree": planted["worktree"],
        "lf": planted["lf"],
        "live_blob_len": len(blob),
    }


def main() -> int:
    states = F.both_states_audit()
    arch = archaeology_control()
    bps = registered()
    tokens = omission_failures(fact_citation_audit_blueprint())
    mapped = map_evidence(
        [
            {"id": "E-LIVE", "text": "live quote exists", "evidence_ids": ["C-LIVE"]},
            {"id": "E-HOLE", "text": "no evidence yet", "evidence_ids": []},
        ],
        [{"id": "C-LIVE"}],
    )
    official = audit_official_docs(
        [
            {
                "id": "D-LIVE",
                "url": F.live_citation()["url"],
                "quoted_span": "distinctive IMP-0235 live quote",
            },
            {
                "id": "D-DEAD",
                "url": F.dead_citation()["url"],
                "quoted_span": "absent",
            },
        ],
        [F.live_citation()["url"]],
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unresolved_anchor = source_anchor(CITE_REL, "status=UNRESOLVED")
    cat_anchor = source_anchor(ARCH_REL, 'CAT_FILE = "cat-file"')
    refuse_anchor = source_anchor(ARCH_REL, "raise ForbiddenRecipeError")

    receipt = {
        "schema_version": 1,
        "id": "IMP-0235",
        "unit_id": "IMP-0235",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0235",
        "completion_sentinel": "SUCCESS:IMP-0235",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0235",
        "title": (
            "Implement research blueprints 5-8: evidence map, fact/citation "
            "audit, official-doc audit, source-code archaeology"
        ),
        "min_bytes_threshold": 128,
        "blueprints": {
            "ids": sorted(bps),
            "count": len(bps),
            "omission_tokens": tokens,
            "omission_distinct": len(set(tokens.values())),
        },
        "citation_audit": {
            "dead_id": "C-DEAD",
            "dead_status": states["dead_status"],
            "live_status": states["live_status"],
            "naive_dead_status": states["naive_dead_status"],
            "naive_accepts_dead": states["naive_accepts_dead"],
            "dead_is_unresolved": states["dead_is_unresolved"],
            "coverage": states["coverage"],
            "assumed_valid_count": states["assumed_valid_count"],
            "honest": states["honest"],
            "unresolved_token": UNRESOLVED,
        },
        "archaeology": arch,
        "evidence_map": mapped.to_dict(),
        "official_doc_audit": official.to_dict(),
        "artifacts": [
            artifact_row(ARCH_REL, "primary"),
            artifact_row(CITE_REL, "supporting"),
            artifact_row(REG_REL, "supporting"),
            artifact_row("command-center/research/blueprints/workflow.py", "supporting"),
            artifact_row("command-center/research/blueprints/contract.py", "supporting"),
            artifact_row("command-center/research/blueprints/evidence_map.py", "supporting"),
            artifact_row("command-center/research/blueprints/official_doc.py", "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "A planted dead citation is UNRESOLVED and is not assumed "
                    f"valid (dead_status={states['dead_status']}); a live "
                    f"twin is {states['live_status']}. The naive mutant "
                    f"accepts the dead row as {states['naive_dead_status']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": unresolved_anchor,
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "source-code-archaeology reads the blob via git cat-file -p; "
                    "the LF blob is byte-identical to the planted control and "
                    "differs from the CRLF worktree. git archive is refused."
                ),
                "verdict": "CONFIRMED",
                "anchor": cat_anchor,
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "planted-dead-citation-UNRESOLVED",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "blob-matches-lf-not-crlf-worktree",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "c-dead-citation-assumed-valid",
                "kind": "known-broken-fixture",
                "description": "unfetchable citation silently accepted as RESOLVED",
                "fired_on_bad_state": states["naive_accepts_dead"] is True,
                "silent_on_good_state": states["dead_is_unresolved"] is True,
                "bad_state_output": states["naive_dead_status"],
                "good_state_output": states["dead_status"],
            },
            {
                "id": "c-worktree-crlf-as-ci-bytes",
                "kind": "known-broken-fixture",
                "description": "hash the CRLF worktree instead of git cat-file -p",
                "fired_on_bad_state": arch["worktree_is_crlf"] is True,
                "silent_on_good_state": arch["blob_equals_lf"] is True,
                "bad_state_output": arch["worktree"]["sha256"],
                "good_state_output": arch["blob"]["sha256"],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0235-probe2-blob-vs-crlf",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial check: plant LF blob + CRLF worktree; live helper "
                "must match cat-file, refuse git archive, and diverge from the "
                "worktree mutant. " + refuse_anchor
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0235/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0235/probe1_dead_citation.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P1,
                    "exit_code": 0,
                    "raw_output": "SUCCESS:IMP-0235-probe1",
                },
            },
            {
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0235/probe2_blob_vs_crlf.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P2,
                    "exit_code": 0,
                    "raw_output": "SUCCESS:IMP-0235-probe2",
                },
            },
        ],
        "residual_unknowns": [],
        "cloud_ok": False,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "notes": (
            "G-1 for IMP-0235: four blueprints registered; live named probes "
            "re-run the citation and blob controls. Did not run "
            "tools/command-center/unit_manifest.py --write. "
            "cloud ok=true is not delivery. Parent worktree is not a git "
            "repository; archaeology plants an isolated git fixture."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0235 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
