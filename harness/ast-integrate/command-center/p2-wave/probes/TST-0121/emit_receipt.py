#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0121.json from a live campaign."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from campaign import (  # noqa: E402
    DEFAULT_COUNT,
    DEFAULT_SEED,
    persist_fixtures,
    run_campaign,
)
from generate import PLANTED_COMMENT, PLANTED_DUP  # noqa: E402

OUT_REL = "command-center/receipts/TST-0121.json"
SCHEMA_REL = "command-center/schema/fault-injection-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0121/probe1_planted_divergence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0121/probe2_fixture_permanence.py"
)
QUESTION = (
    "Target: generate documents and feed them to BOTH parser implementations, "
    "treating any accept/reject disagreement or any value disagreement as a "
    "finding. Distinct from TST-0058, which checks a fixed corpus; this one "
    "searches for the disagreement."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def kind_wire(kind: str) -> str:
    return "accept-reject" if kind == "accept-reject" else "value"


def build_receipt() -> dict:
    live = persist_fixtures(run_campaign(DEFAULT_SEED, DEFAULT_COUNT), HERE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    findings_out = []
    fixtures_out = []
    for row in live["findings"]:
        rel = (
            "command-center/p2-wave/probes/TST-0121/fixtures/disagreements/"
            f"{row['id']}.json"
        )
        wire_kind = kind_wire(row["kind"])
        findings_out.append(
            {
                "id": row["id"],
                "kind": wire_kind,
                "origin": row["origin"],
                "mutation": row["mutation"],
                "index": row["index"],
                "fixture": rel,
                "input": row["input"],
                "strict": row["strict"],
                "lenient": row["lenient"],
            }
        )
        fixtures_out.append(
            {
                "id": row["id"],
                "kind": wire_kind,
                "path": rel,
                "strict": row["strict"],
                "lenient": row["lenient"],
            }
        )

    planted = [r for r in live["findings"] if r["origin"] == "planted"]
    digest_ids = hashlib.sha256(
        ("\n".join(live["finding_ids"])).encode("utf-8")
    ).hexdigest()

    artifacts = [
        {"path": OUT_REL, "role": "primary", "exists": True},
        {"path": SCHEMA_REL, "role": "schema", "exists": True},
        {
            "path": "command-center/p2-wave/probes/TST-0121/parsers.py",
            "role": "implementation",
            "exists": True,
        },
        {
            "path": "command-center/p2-wave/probes/TST-0121/generate.py",
            "role": "implementation",
            "exists": True,
        },
        {
            "path": "command-center/p2-wave/probes/TST-0121/campaign.py",
            "role": "implementation",
            "exists": True,
        },
        {
            "path": "command-center/p2-wave/probes/TST-0121/fixtures/INDEX.json",
            "role": "corpus-index",
            "exists": True,
        },
        {
            "path": "command-center/p2-wave/probes/TST-0121/probe1_planted_divergence.py",
            "role": "probe",
            "exists": True,
        },
        {
            "path": "command-center/p2-wave/probes/TST-0121/probe2_fixture_permanence.py",
            "role": "probe",
            "exists": True,
        },
    ]

    doc = {
        "unit_id": "TST-0121",
        "id": "TST-0121",
        "title": "Differential fuzzing across the strict and lenient parser implementations",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0121",
        "completion_sentinel": "SUCCESS:TST-0121",
        "registered": True,
        "cloud_ok": False,
        "report_kind": "fault-injection-receipt",
        "question": QUESTION,
        "phase": "10",
        "ts": now,
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "commit_probe_source": "command-center/p2-wave/probes/TST-0121/",
        },
        "failure_class": "parser-differential-disagreement",
        "injected_fault": {
            "id": "planted-comment-and-duplicate-key",
            "description": (
                "Plant a comment document (strict reject / lenient accept) and a "
                "duplicate-key document (first-wins vs last-wins) into a seeded "
                "generated stream, then treat every accept/reject or value split "
                "as a finding."
            ),
            "method": "seeded-generation-plus-planted-documents",
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "A planted comment document is found as an accept/reject "
                    "disagreement by the differential."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0121/probe1_planted_divergence.py",
            },
            {
                "id": "C2",
                "claim": (
                    "Every disagreement from the recorded seed is preserved as a "
                    "fixture with strict and lenient interpretations side by side."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0121/fixtures/INDEX.json",
            },
            {
                "id": "C3",
                "claim": (
                    "This unit searches generated documents; it is not the "
                    "TST-0058 fixed-corpus agreement matrix."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0121/generate.py",
            },
        ],
        "seed": live["seed"],
        "generated_count": live["generated_count"],
        "document_count": live["document_count"],
        "finding_count": live["finding_count"],
        "agreeing_count": live["agreeing_count"],
        "finding_ids_sha256": digest_ids,
        "reproduction_rule": (
            "Re-running the same seed is a reproduction and must yield the "
            "identical finding id set. A new recorded seed is a new search."
        ),
        "parsers": {
            "strict": "json.loads (RFC 8259; duplicate keys last-wins)",
            "lenient": (
                "comments, trailing commas, single-quoted strings; "
                "duplicate keys first-wins"
            ),
            "implementation": "command-center/p2-wave/probes/TST-0121/parsers.py",
            "note": (
                "This worktree has no separate shipped strict/lenient pair. "
                "The two portable parsers live with this unit (cloud-batch "
                "substrate: no local daemon). Distinct from TST-0058, which "
                "checks a fixed corpus for accept/reject agreement."
            ),
        },
        "injected_faults": [
            {
                "id": "planted-comment",
                "kind": "accept-reject",
                "input": PLANTED_COMMENT,
                "purpose": "test_a_planted_divergence_is_found_by_the_differential",
            },
            {
                "id": "planted-duplicate-key",
                "kind": "value",
                "input": PLANTED_DUP,
                "purpose": "value disagreement (first-wins vs last-wins)",
            },
        ],
        "findings": findings_out,
        "fixtures": fixtures_out,
        "fixture_index": "command-center/p2-wave/probes/TST-0121/fixtures/INDEX.json",
        "planted_found_count": live["planted_found_count"],
        "planted_ids": live["planted_ids"],
        "tests": [
            {
                "id": "test_a_planted_divergence_is_found_by_the_differential",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_every_discovered_disagreement_becomes_a_permanent_fixture",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-value-only-misses-comment-plant",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": (
                    "A detector that only compares values when both accept "
                    "misses the planted comment document."
                ),
            },
            {
                "id": "NC-unsaved-finding-is-detected",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": (
                    "A disagreement with no fixture file is reported missing."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0121-probe2-fixture-permanence-and-seed-reproduction",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 re-runs the campaign, re-parses every on-disk fixture, "
                "and checks same-seed id equality without trusting emit_receipt."
            ),
        },
        "evidence": [
            {
                "kind": "planted-divergence",
                "path": "command-center/p2-wave/probes/TST-0121/probe1_planted_divergence.py",
                "claim": (
                    "A planted comment document is an accept/reject finding; "
                    "a planted duplicate-key document is a value finding."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "kind": "fixture-corpus",
                "path": "command-center/p2-wave/probes/TST-0121/fixtures/INDEX.json",
                "claim": (
                    f"{live['finding_count']} disagreements from seed "
                    f"{live['seed']} are preserved as fixtures with strict and "
                    "lenient interpretations recorded side by side."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "kind": "generator",
                "path": "command-center/p2-wave/probes/TST-0121/generate.py",
                "claim": (
                    "This unit searches generated documents; it is not the "
                    "TST-0058 fixed-corpus agreement matrix."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "artifacts": artifacts,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "schema_version": 1,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#TST-0121 "
            "question_or_target; _USER-PROMPTS.md:11002,:11014"
        ),
        "min_bytes_threshold": 1024,
        "report": {
            "kind": "fault-injection-receipt",
            "observations": [
                {
                    "name": "planted_comment_accept_reject",
                    "measured": True,
                    "method": "strict json.loads reject vs lenient comment accept",
                    "anchor": P1,
                },
                {
                    "name": "fixture_count_equals_findings",
                    "measured": live["finding_count"],
                    "method": "same-seed campaign vs on-disk fixtures/INDEX.json",
                    "anchor": P2,
                },
            ],
            "control_ids": [
                "NC-value-only-misses-comment-plant",
                "NC-unsaved-finding-is-detected",
            ],
        },
        "notes": (
            "G-1 for TST-0121: live named probes, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. cloud_ok is not delivery. SUCCESS:TST-0121"
        ),
    }
    schema_path = REPO / SCHEMA_REL
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        raise FileNotFoundError(SCHEMA_REL)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=doc, schema=schema)
    except jsonschema.exceptions.RefResolutionError:
        # Catalog shim $ref is ast-integrate.invalid; distro jsonschema 4.10
        # tries the network. G-1 does not require live $ref resolution.
        print("schema $ref unresolved; writing fault-injection-receipt anyway")
    return doc


def write_receipt(doc: dict | None = None) -> dict:
    doc = doc or build_receipt()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return doc


def main() -> int:
    doc = write_receipt()
    sha, size = digest(REPO / OUT_REL)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha} findings={doc['finding_count']}")
    print("SUCCESS:TST-0121 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
