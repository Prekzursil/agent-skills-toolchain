#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0176.json confirmation record."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/receipts/CNF-0176.json"
FUSION_OUT = (
    "command-center/p2-wave/probes/CNF-0176/fixtures/certified-fusion/fusion.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0176/probe1_decompose_execute.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0176/probe2_license_control.py"
)
QUESTION = (
    "Question: is the lineage claim real - can the fusion actually be decomposed "
    "back into its source components, and does each recovered component still "
    "execute? Spec:11170 and 11413 require decomposability and lineage "
    "preservation; spec:11334 names lost provenance or license as a failure class. "
    "Decompose, execute each part, and verify the license and credit records survived."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {"path": rel, "sha256": sha, "bytes": size}


def main() -> int:
    live = S.run_confirmation()
    if not live.get("pass"):
        print("FAILED:CNF-0176 emit live confirmation did not pass")
        print(json.dumps({k: live.get(k) for k in sorted(live) if k != "fusion"}, indent=2)[:4000])
        return 1

    fusion_path = REPO / FUSION_OUT
    fusion_path.parent.mkdir(parents=True, exist_ok=True)
    fusion_path.write_text(
        json.dumps(live["fusion"], indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    src_probe = {
        "id": "probe1_decompose_execute",
        "command": P1,
        "role": "decompose-execute-capability-roundtrip",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/CNF-0176/probe1_decompose_execute.py"
        ),
    }
    ver_probe = {
        "id": "probe2_license_control",
        "command": P2,
        "role": "license-strip-and-upstream-credit-chain",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/CNF-0176/probe2_license_control.py"
        ),
    }
    if src_probe["fingerprint"]["sha256"] == ver_probe["fingerprint"]["sha256"]:
        print("FAILED:CNF-0176 emit source/verifier probe files identical")
        return 1

    discrepancies: list[dict] = []
    doc = {
        "unit_id": "CNF-0176",
        "claim_id": "CNF-0176-lineage-decomposability",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "confirmation-record",
        "title": "Decompose a fused workflow back to its sources and confirm the parts still run",
        "question": QUESTION,
        "sentinel": "SUCCESS:CNF-0176",
        "completion_sentinel": "SUCCESS:CNF-0176",
        "min_bytes_threshold": 2048,
        "verdict": "CONFIRMED",
        "confirmer": {
            "identity": "CNF-0176-independent-confirmer",
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "independent-confirmer",
            "execution_substrate": "linux-local",
        },
        "blinding_attestation": {
            "hash": live["blinding"]["sha256"],
            "sha256": live["blinding"]["sha256"],
            "bytes": live["blinding"]["bytes"],
            "excluded": live["blinding"]["excluded"],
            "lazy_instruction_leaked": live["blinding"]["lazy_instruction_leaked"],
            "rule": (
                "Payload is canonical JSON of source repos + fused workflow + smoke "
                "cases. The adjudicator-only certification.json is excluded so an "
                "implementer CONFIRMED cannot substitute for decompose+execute."
            ),
        },
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "baseline_repro": live["original_execute"],
        "corrected_repro": {
            "recovered_match": live["recovered_match"],
            "fusion_execute": live["fusion_execute"],
        },
        "rollback_repro": {
            "roundtrip_ok": live["roundtrip_ok"],
            "fusion_fingerprint": live["fusion_fingerprint"],
            "recompose_fingerprint": live["recompose_fingerprint"],
            "strategy": "union",
            "fusion_id": live["fusion_id"],
        },
        "regression_diff": {
            "capability_losses_on_certified_fusion": live["capability_losses"],
            "planted_lossy": live["planted_lossy"],
            "vanity_gate": live["vanity_gate"],
        },
        "discrepancies": discrepancies,
        "per_component": live["per_component"],
        "license_strip_control": live["license_strip_control"],
        "parse_only_control": live["parse_only_control"],
        "tests": {
            "capability_set_superset": {
                "pass": live["capability_losses"] == [],
                "losses": live["capability_losses"],
                "planted_detector_fired": live["planted_lossy"]["detector_fired"],
            },
            "known_broken_license_strip": {
                "pass": live["license_strip_control"]["detector_fired"],
                "source_id": "wf-alpha",
            },
            "executability_terminal_not_parse": {
                "pass": all(p["executed"] for p in live["per_component"])
                and live["parse_only_control"]["executed"] is False,
            },
            "round_trip_recompose": {
                "pass": live["roundtrip_ok"],
                "fusion_fingerprint": live["fusion_fingerprint"],
            },
            "more_stages_without_capability_refused": {
                "pass": live["vanity_gate"]["accepted"] is False,
                "reason": live["vanity_gate"]["reason"],
            },
        },
        "sources": live["sources"],
        "fusion_id": live["fusion_id"],
        "fusion_path": FUSION_OUT,
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/CNF-0176/engine.py",
                "kind": "decompose-execute-oracle",
                "claim": "decompose is the inverse of union-fusion under structural fingerprint; recovered components execute to the original token lists.",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0176/fixtures/sources/wf-alpha/LICENSE",
                "kind": "upstream-license",
                "claim": "wf-alpha MIT license and Alpha Token Works credit survive fusion and decompose.",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0176/fixtures/sources/wf-beta/LICENSE",
                "kind": "upstream-license",
                "claim": "wf-beta Apache-2.0 license and Beta Rank Lab credit survive fusion and decompose.",
            },
            {
                "path": FUSION_OUT,
                "kind": "certified-fusion",
                "claim": "On-disk certified union fusion carries lineage.sources with license and credit for each component.",
            },
        ],
        "residual_caveat": (
            "No production IMP-0180 fusion engine and no CNF-0175 tournament-certified "
            "fusion exist on this worktree. Confirmation is of a confirmer-constructed "
            "certified union fusion (wf.certified.union-alpha-beta) built from two "
            "source repos with distinct licenses. Not a claim that Workflow Foundry "
            "production fusions were measured, and not a claim that cloud ok=true is delivery."
        ),
        "scope": {
            "proof_surface": (
                "union fusion of wf-alpha (MIT) and wf-beta (Apache-2.0); live execute "
                "of recovered components; license-strip detector; 11170 vanity refusal; "
                "planted rank-capability loss."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "CNF-0175 certified tournament fusion was present",
                "IMP-0180 eight-strategy production decompose API was imported",
            ],
        },
        "reviewer": {
            "reviewer_id": "CNF-0176-probe2-license-chain",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-reads upstream LICENSE/CREDIT files and requires "
                "strip-license to fire independently of probe 1's execute path."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "decompose-execute-capability-roundtrip", "command": P1},
            {"id": "probe2", "role": "license-strip-and-upstream-credit-chain", "command": P2},
        ],
        "cloud_ok": False,
        "registered": True,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": FUSION_OUT, "exists": True, "role": "supporting"},
        ],
    }

    if not doc["source_probe"] or not doc["verifier_probe"]:
        print("FAILED:CNF-0176 emit empty probes with CONFIRMED")
        return 1
    if doc["verdict"] in {"CONFIRMED", "REFUTED"} and not doc["source_probe"]:
        print("FAILED:CNF-0176 emit unsourced CONFIRMED")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0176 artifact {size}B below floor")
        return 1
    # sanity: sentinel in file bytes
    if b"SUCCESS:CNF-0176" not in out.read_bytes():
        print("FAILED:CNF-0176 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"fusion_fp={live['fusion_fingerprint']}")
    print("SUCCESS:CNF-0176 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
