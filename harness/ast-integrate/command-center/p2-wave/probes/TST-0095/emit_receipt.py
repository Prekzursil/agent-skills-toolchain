#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0095.json test receipt."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0095.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0095/probe1_extractor_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0095/probe2_gate_dispatch.py"
)
QUESTION = (
    "Failure class :11320. Directly live on this program: 31 option IDs resolve "
    "to two unrelated meanings across two artifacts sharing the M-NN namespace, "
    "and a third and fourth M-NN namespace exist on disk. Target: a namespace-"
    "collision gate over every id-bearing artifact (work units, options, "
    "blueprints, presets) that fails on any id resolving to more than one "
    "definition."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {"path": rel, "sha256": sha, "bytes": size}


def main() -> int:
    tests = S.run_required_tests()
    if not tests["ok"]:
        print("FAILED:TST-0095 emit required tests did not pass")
        print(json.dumps(tests, indent=2, default=str)[:4000])
        return 1
    evidence = S.evidence_bundle()
    live_md = bool(evidence["original_markdown_option_universe_present"]) and bool(
        evidence["original_markdown_architecture_candidates_present"]
    )
    src_probe = {
        "id": "probe1_extractor_control",
        "command": P1,
        "role": "extractor-known-31way-detector-control",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0095/probe1_extractor_control.py"
        ),
    }
    ver_probe = {
        "id": "probe2_gate_dispatch",
        "command": P2,
        "role": "gate-two-definition-and-duplicate-dispatch",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0095/probe2_gate_dispatch.py"
        ),
    }
    if src_probe["fingerprint"]["sha256"] == ver_probe["fingerprint"]["sha256"]:
        print("FAILED:TST-0095 emit source/verifier probe files identical")
        return 1

    by_name = {t["id"]: t for t in tests["tests"]}
    test_rows = [
        {
            "id": "TST-0095-T1",
            "name": "test_extractor_reproduces_the_known_collision_set",
            "result": "PASS" if by_name["test_extractor_reproduces_the_known_collision_set"]["ok"] else "FAIL",
            "detail": {
                "count": by_name["test_extractor_reproduces_the_known_collision_set"]["count"],
                "cc0023_agrees": by_name["test_extractor_reproduces_the_known_collision_set"][
                    "cc0023_agrees"
                ],
            },
        },
        {
            "id": "TST-0095-T2",
            "name": "test_gate_fails_on_any_id_with_two_definitions",
            "result": "PASS" if by_name["test_gate_fails_on_any_id_with_two_definitions"]["ok"] else "FAIL",
            "detail": {
                "planted_id_named": by_name["test_gate_fails_on_any_id_with_two_definitions"][
                    "planted_id_named"
                ],
                "clean_gate_ok": by_name["test_gate_fails_on_any_id_with_two_definitions"][
                    "clean_gate_ok"
                ],
            },
        },
        {
            "id": "TST-0095-T3",
            "name": "test_dispatch_refuses_to_run_two_units_with_the_same_id",
            "result": "PASS" if by_name["test_dispatch_refuses_to_run_two_units_with_the_same_id"]["ok"] else "FAIL",
            "detail": {
                "refused_ids": by_name["test_dispatch_refuses_to_run_two_units_with_the_same_id"][
                    "refused_ids"
                ],
                "ran_ids": by_name["test_dispatch_refuses_to_run_two_units_with_the_same_id"][
                    "ran_ids"
                ],
            },
        },
    ]

    doc = {
        "unit_id": "TST-0095",
        "claim_id": "TST-0095-namespace-collision-gate",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "test-receipt",
        "title": "Duplicate units from colliding catalogs",
        "question": QUESTION,
        "sentinel": "SUCCESS:TST-0095",
        "completion_sentinel": "SUCCESS:TST-0095",
        "min_bytes_threshold": 2048,
        "verdict": "PASS",
        "extractor_proven_on_known_case": True,
        "known_collision_set": evidence["known_collision_set"],
        "known_collision_count": evidence["known_collision_count"],
        "known_multi_definition_ids": evidence["known_multi_definition_ids"],
        "id_to_definitions": evidence["known_id_to_definitions"],
        "namespaces_scanned": evidence["namespaces_scanned"],
        "live_31way_on_this_worktree": live_md,
        "live_catalog": {
            "path": evidence["live_catalog_path"],
            "id_count": evidence["live_catalog_id_count"],
            "record_count": evidence["live_catalog_record_count"],
            "multi_definition_ids": evidence["live_catalog_multi_definition_ids"],
            "option_universe_markdown_present": evidence[
                "original_markdown_option_universe_present"
            ],
            "architecture_candidates_markdown_present": evidence[
                "original_markdown_architecture_candidates_present"
            ],
            "option_id_resolution_present": evidence["option_id_resolution_present"],
        },
        "gate": {
            "fails_on_any_id_with_two_definitions": True,
            "planted_two_definition_fails": True,
            "clean_corpus_passes": True,
            "planted_id": "BP-TWOMEAN",
        },
        "dispatch": {
            "duplicate_id_refused": True,
            "refused_id": "TST-DUP-0001",
            "unique_units_still_run": True,
        },
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "tests": test_rows,
        "evidence": [
            {
                "claim": "Extractor reproduces the known 31-way option∩mech M-1..M-31 set before any live zero is trusted.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0095/fixtures/known-31way/option-universe.json",
            },
            {
                "claim": "Gate fails on any id with two definitions, including a planted BP-TWOMEAN pair, and passes a clean unique-id corpus.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0095/fixtures/planted/blueprint-meaning-a.json",
            },
            {
                "claim": "Dispatch refuses to run two work units with the same id (TST-DUP-0001) while still running unique ids.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0095/fixtures/planted/units-slice-a.json",
            },
            {
                "claim": "Third and fourth M-NN namespaces (wave3 M-16, wave1 M-1/M-3) are present in the reconstructed corpus.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0095/fixtures/known-31way/wave3-deep-research.json",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0095-probe2-gate-dispatch",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-reads planted fixtures from disk and requires the gate "
                "and dispatcher to fire without using probe 1's return value. It "
                "also refuses a live-31-way overclaim when 07-OPTION-UNIVERSE.md "
                "and 13-ARCHITECTURE-CANDIDATES.md are absent."
            ),
        },
        "residual_caveat": (
            "07-OPTION-UNIVERSE.md, 13-ARCHITECTURE-CANDIDATES.md, and "
            "command-center/OPTION-ID-RESOLUTION.json are absent from this "
            "worktree. The known 31-way case is reconstructed from the CC-0023 "
            "namespace tables (option 1-33 ∩ mech 1-31 = 31) and proven as a "
            "detector control before any live catalog zero is trusted. Not a "
            "claim that the historical markdown collision is still on disk here, "
            "and not a claim that cloud ok=true is delivery."
        ),
        "scope": {
            "proof_surface": (
                "namespace-collision extractor + gate over work units, options, "
                "blueprints, and presets; known 31-way M-NN fixture; planted "
                "two-definition blueprint; duplicate work-unit dispatch refusal."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "historical 07-OPTION-UNIVERSE.md is present on this worktree",
            ],
        },
        "cloud_ok": False,
        "registered": True,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0095/collision.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/schema/test-receipt.schema.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "extractor-known-31way-detector-control", "command": P1},
            {"id": "probe2", "role": "gate-two-definition-and-duplicate-dispatch", "command": P2},
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0095 artifact {size}B below floor")
        return 1
    if b"SUCCESS:TST-0095" not in out.read_bytes():
        print("FAILED:TST-0095 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"known_collision_count={evidence['known_collision_count']}")
    print("SUCCESS:TST-0095 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
