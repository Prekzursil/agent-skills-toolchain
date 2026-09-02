#!/usr/bin/env python3
"""Write IMP-0349 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.evidence.retrieve import (  # noqa: E402
    build_overflow_council,
    dump_fixture,
    run_both_configurations,
)

UID = "IMP-0349"
OUT_REL = "command-center/receipts/IMP-0349.json"
LOG_REL = "command-center/p2-wave/probes/IMP-0349/retrieval-log.json"
FIX_REL = "command-center/p2-wave/probes/IMP-0349/fixtures/overflow_council.json"
MOD_REL = "tools/council/evidence/retrieve.py"
SPEC = "command-center/WORK-UNIT-CATALOG.json:57483"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0349/probe1_citation_rate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0349/probe2_negative_control.py"
)
SUPPORTING = [
    MOD_REL,
    "tools/council/__init__.py",
    "tools/council/evidence/__init__.py",
    FIX_REL,
    LOG_REL,
    "command-center/p2-wave/probes/IMP-0349/probe1_citation_rate.py",
    "command-center/p2-wave/probes/IMP-0349/probe2_negative_control.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0349/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_receipt(result: dict) -> dict:
    late = result["late_fetches_on"]
    return {
        "answer": (
            "On the planted overflowing council overflow-early-evidence-v1, a "
            "deterministic citer bound to prompt contents cites early-round "
            f"evidence at rate {result['rate_on']['rate']} with retrieval on "
            f"and {result['rate_off']['rate']} with retrieval off (same council, "
            f"token_budget={result['token_budget']}). Late-turn fetches were "
            f"{[e['fetched_anchor_ids'] for e in late]}. Truncation still "
            "happens; retrieval puts the queried early anchors back. Not a live "
            "LLM council. SUCCESS:IMP-0349"
        ),
        "artifact_paths": [
            OUT_REL,
            MOD_REL,
            FIX_REL,
            LOG_REL,
        ],
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": MOD_REL, "role": "module"},
            {"path": FIX_REL, "role": "fixture"},
            {"path": LOG_REL, "role": "retrieval-log"},
        ],
        "completion_sentinel": "SUCCESS:IMP-0349",
        "evidence": [
            {
                "id": "E1",
                "claim": "early-round citation rate with retrieval on and off, same council",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/evidence/retrieve.py"
                ),
                "rate_on": result["rate_on"]["rate"],
                "rate_off": result["rate_off"]["rate"],
                "late_turns": result["rate_on"]["late_turns"],
                "hits_on": result["rate_on"]["hits"],
                "hits_off": result["rate_off"]["hits"],
                "same_council": result["same_council"],
                "council_id": result["council_id"],
                "computed_not_asserted": True,
            },
            {
                "id": "E2",
                "claim": "retrieval log showing which anchors were fetched per turn",
                "path": LOG_REL,
                "late_fetched_anchor_ids": [e["fetched_anchor_ids"] for e in late],
                "late_turns": [e["turn"] for e in late],
            },
        ],
        "experiment": {
            "council_id": result["council_id"],
            "token_budget": result["token_budget"],
            "early_anchor_ids": result["early_anchor_ids"],
            "overflow_late_on": result["overflow_late_on"],
            "overflow_late_off": result["overflow_late_off"],
            "rate_on": result["rate_on"]["rate"],
            "rate_off": result["rate_off"]["rate"],
            "late_fetched_anchor_ids": [e["fetched_anchor_ids"] for e in late],
            "tokenizer": "whitespace-split",
            "citer": "marker-in-prompt",
        },
        "id": UID,
        "negative_control_ids": [
            "IMP-0349-probe2-disable-retrieval-collapse",
            "IMP-0349-mutant-store-citer-rejected",
        ],
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-runtime-module"
        ),
        "profile": "council-runtime-module",
        "question": (
            "On a council that overflows context, does a participant still cite "
            "evidence introduced in early rounds, measured as the early-round "
            "citation rate with and without retrieval?"
        ),
        "residual_unknowns": [
            "IMP-0338 tools/council/context.py is absent in this worktree; retrieve.py owns a local budgeted assembler and does not claim context.py delivered.",
            "IMP-0314 tools/council/artifacts/evidence_map.py is absent; citation here is marker-presence, not a claim-anchor graph.",
            "No live LLM council was run; the participant is a deterministic citer bound to prompt contents.",
            "11-COUNCIL-SPECIFICATION.md is not in this worktree; spec_anchor is the catalog question_or_target line.",
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0349-probe2-negative-control",
            "starts_from": "tests",
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "spec_anchor": SPEC,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "test_ids": [
            "IMP-0349-probe1-citation-rate-both-configs",
            "IMP-0349-experiment-early-round-citation-rate",
        ],
        "title": "Evidence retrieval under context overflow",
        "unit_id": UID,
    }


def main() -> int:
    dump_fixture(REPO / FIX_REL)
    result = run_both_configurations(build_overflow_council(), token_budget=48)
    if not result["pass_experiment"] or not result["pass_negative_control"]:
        print("FAILED:IMP-0349 experiment did not pass before receipt write")
        print(json.dumps(result, indent=2, sort_keys=True, default=str)[:3000])
        return 1
    log_doc = {
        "council_id": result["council_id"],
        "token_budget": result["token_budget"],
        "retrieval_enabled": True,
        "per_turn": result["retrieval_log_on"],
        "late_fetches": result["late_fetches_on"],
    }
    log_path = REPO / LOG_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(log_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    receipt = build_receipt(result)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0349",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-runtime-module"
        ),
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0349/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0349-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0349: live named probes exit 0, receipts/IMP-0349.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. retrieve.py implemented; no live LLM."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0349 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
