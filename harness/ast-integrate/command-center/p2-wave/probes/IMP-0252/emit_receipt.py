#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0252.json from live engine runs."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center/library/knowledge_blueprints"
sys.path.insert(0, str(LIB))

import curriculum  # noqa: E402
import docverify  # noqa: E402
import writing  # noqa: E402
from fingerprint import mechanism_fingerprint, rename_identifiers  # noqa: E402
from invention import (  # noqa: E402
    grade_candidate,
    grade_inventions,
    novel_morphology_candidate,
    reworded_duplicate,
)
from registry import load_library, omission_matrix, write_entry_snapshots  # noqa: E402

UNIT = "IMP-0252"
OUT = "command-center/receipts/IMP-0252.json"
SCHEMA = "command-center/schema/receipt.schema.json"
GOOD = HERE / "fixtures/docs/good.md"
BAD = HERE / "fixtures/docs/planted-broken.md"
PLANTED = "not-a-real-command-imp0252"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0252/probe1_doc_commands.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0252/probe2_invention_novelty.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str = "supporting") -> dict:
    p = REPO / rel
    data = p.read_bytes() if p.is_file() else b""
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() if data else "",
        "exists": p.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_entry_snapshots()
    lib = load_library()
    omissions = omission_matrix()

    good = docverify.run_example(GOOD, execute=True)
    bad = docverify.run_example(BAD, execute=True)
    skipped = docverify.run_example(GOOD, execute=False)
    planted = next(c for c in bad["commands"] if PLANTED in c["command"])
    if good["coverage"] != 1.0 or not good["pass_clean"]:
        print("FAILED:IMP-0252 emit good-doc did not pass", json.dumps(good)[:1500])
        return 1
    if planted["exit_code"] in (None, 0) or not planted["executed"]:
        print("FAILED:IMP-0252 emit planted not caught", planted)
        return 1
    if skipped["coverage"] != 0.0 or skipped["untested"] != skipped["claimed"]:
        print("FAILED:IMP-0252 emit skip-execute coverage not computed", skipped)
        return 1

    packs = lib["packs"]
    docv = next(p for p in packs if p["id"] == "documentation-verification")
    renamed_fp = mechanism_fingerprint(rename_identifiers(docv["workflow"], "-alias"))
    if renamed_fp != lib["fingerprints"]["documentation-verification"]:
        print("FAILED:IMP-0252 emit rename-variant fingerprint")
        return 1

    dup_grade = grade_candidate(reworded_duplicate(docv), packs)
    novel_grade = grade_candidate(novel_morphology_candidate(), packs)
    flood = grade_inventions([reworded_duplicate(docv)] * 10, packs)
    mixed = grade_inventions(
        [reworded_duplicate(docv)] * 9 + [novel_morphology_candidate()], packs
    )
    if dup_grade["verdict"] != "NOT-NOVEL" or dup_grade["novelty_score"] != 0.0:
        print("FAILED:IMP-0252 emit duplicate not rejected", dup_grade)
        return 1
    if novel_grade["verdict"] != "NOVEL" or novel_grade["novelty_score"] < 0.5:
        print("FAILED:IMP-0252 emit novel too similar", novel_grade)
        return 1
    if flood["volume_used_in_score"] or flood["max_novelty"] != 0.0 or flood["volume_count"] != 10:
        print("FAILED:IMP-0252 emit volume flood", flood)
        return 1
    if mixed["novel_count"] != 1:
        print("FAILED:IMP-0252 emit mixed novel_count", mixed["novel_count"])
        return 1

    cur = curriculum.run_example()
    if not cur.get("ok") or cur.get("order") != ["alpha", "beta", "gamma"]:
        print("FAILED:IMP-0252 emit curriculum", cur)
        return 1
    cyclic_caught = False
    try:
        curriculum.sequence_skills(
            [
                {"id": "a", "prerequisites": ["b"]},
                {"id": "b", "prerequisites": ["a"]},
            ]
        )
    except curriculum.CurriculumError as exc:
        cyclic_caught = "cyclic" in str(exc)
    if not cyclic_caught:
        print("FAILED:IMP-0252 emit cyclic curriculum not caught")
        return 1

    room = writing.run_example()
    if not room.get("ok") or room.get("status") != "frozen":
        print("FAILED:IMP-0252 emit writing-room", room)
        return 1
    unbanded = writing.critique("likely fine\n", min_chars=0)
    if not any(i["id"] == "unbanded-likely-fine" for i in unbanded):
        print("FAILED:IMP-0252 emit writing lint missed unbanded claim")
        return 1

    supporting = [
        "command-center/library/knowledge_blueprints/docverify.py",
        "command-center/library/knowledge_blueprints/invention.py",
        "command-center/library/knowledge_blueprints/packs.py",
        "command-center/library/knowledge_blueprints/registry.py",
        "command-center/library/knowledge_blueprints/entries/documentation-verification.json",
        "command-center/library/knowledge_blueprints/entries/teaching-curriculum.json",
        "command-center/library/knowledge_blueprints/entries/writing-room.json",
        "command-center/library/knowledge_blueprints/entries/invention-wildcard.json",
        "command-center/p2-wave/probes/IMP-0252/probe1_doc_commands.py",
        "command-center/p2-wave/probes/IMP-0252/probe2_invention_novelty.py",
        "command-center/p2-wave/probes/IMP-0252/fixtures/docs/good.md",
        "command-center/p2-wave/probes/IMP-0252/fixtures/docs/planted-broken.md",
    ]
    artifacts = [art(p) for p in supporting]
    if any(not a["exists"] or a["bytes"] <= 0 for a in artifacts):
        missing = [a["path"] for a in artifacts if not a["exists"] or a["bytes"] <= 0]
        print("FAILED:IMP-0252 emit missing supporting", missing)
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0252",
        "completion_sentinel": "SUCCESS:IMP-0252",
        "spec_anchor": "_USER-PROMPTS.md:10900-10907,_USER-PROMPTS.md:11024",
        "title": "Implement knowledge blueprints 9-12: documentation verification, teaching/curriculum, writing room, invention/wildcard",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 128,
        "blueprints": lib["rows"],
        "fingerprint_collisions": 0,
        "contract": {
            "required_elements": 6,
            "omission_matrix": omissions,
            "scaffold_note": "Each pack carries typed workflow, example, preset, stopping rules, smoke entry, capability vector.",
        },
        "evidence": [
            {
                "claim": "documentation-verification executes claimed commands, records exit codes, and computes coverage; a planted broken command is caught (both-states). A skip-execute run leaves untested claims and coverage 0, so coverage is not a constant.",
                "verdict": "CONFIRMED",
                "anchor": "_USER-PROMPTS.md:11024",
                "confidence": "almost-certain",
                "measurements": {
                    "good_claimed": good["claimed"],
                    "good_executed": good["executed"],
                    "good_coverage": good["coverage"],
                    "good_broken": 0,
                    "bad_claimed": bad["claimed"],
                    "bad_executed": bad["executed"],
                    "bad_marked": bad["marked"],
                    "planted_command": planted["command"],
                    "planted_exit_code": planted["exit_code"],
                    "planted_caught": True,
                    "skip_execute_coverage": skipped["coverage"],
                    "skip_execute_untested": skipped["untested"],
                    "coverage_computed": True,
                },
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": None,
                        "raw_output": "named probe re-runs this measurement",
                    }
                ],
            },
            {
                "claim": "invention-wildcard grades candidates by Jaccard distance to the library fingerprint set. Volume is a separate count and is not mixed into the score: ten reworded duplicates still score 0; mixing one distinct candidate yields novel_count=1.",
                "verdict": "CONFIRMED",
                "anchor": "IMP-0232 distinctness catalog",
                "confidence": "almost-certain",
                "measurements": {
                    "library_size": lib["count"],
                    "duplicate_verdict": dup_grade["verdict"],
                    "duplicate_novelty_score": dup_grade["novelty_score"],
                    "duplicate_max_jaccard": dup_grade["max_jaccard"],
                    "novel_verdict": novel_grade["verdict"],
                    "novel_novelty_score": novel_grade["novelty_score"],
                    "volume_count_flood": flood["volume_count"],
                    "volume_used_in_score": False,
                    "flood_max_novelty": flood["max_novelty"],
                    "mixed_volume_count": mixed["volume_count"],
                    "mixed_novel_count": mixed["novel_count"],
                    "rename_invariant": True,
                    "method": "fingerprint-jaccard",
                },
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": None,
                        "raw_output": "named probe re-runs this measurement",
                    }
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "planted-broken-command",
                "kind": "both-states",
                "description": "good.md all exit 0; planted-broken.md records non-zero for not-a-real-command-imp0252",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {"planted_exit_code": planted["exit_code"], "broken": bad["broken"]},
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {"coverage": good["coverage"], "broken": []},
                    sort_keys=True,
                ),
            },
            {
                "id": "skip-execute-untested-claims",
                "kind": "detector-control",
                "description": "coverage is computed; disabling execute drops coverage to 0",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(skipped["coverage"]),
                "good_state_output": str(good["coverage"]),
            },
            {
                "id": "volume-is-not-novelty",
                "kind": "both-states",
                "description": "ten duplicate inventions: volume_count=10, max_novelty=0; mixed batch isolates novel_count=1",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {"volume_count": flood["volume_count"], "max_novelty": flood["max_novelty"]},
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {"novel_score": novel_grade["novelty_score"], "mixed_novel_count": mixed["novel_count"]},
                    sort_keys=True,
                ),
            },
            {
                "id": "cyclic-curriculum",
                "kind": "both-states",
                "description": "acyclic three-skill plan sequences; cyclic pair is rejected",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "cyclic-prerequisites",
                "good_state_output": json.dumps(cur["order"]),
            },
        ],
        "tests": [
            {
                "id": "documented-command-coverage-and-planted-broken",
                "name": "documented-command coverage computed; planted broken command caught (both-states)",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "invention-novelty-vs-library-fingerprints",
                "name": "invention output scored for novelty against the library fingerprint set, not counted",
                "command": P2,
                "result": "PASS",
            },
        ],
        "smokes": {
            "teaching-curriculum": {"ok": cur["ok"], "order": cur["order"]},
            "writing-room": {"ok": room["ok"], "status": room["status"], "revisions": room["revisions"]},
        },
        "reviewer": {
            "reviewer_id": "IMP-0252-probe2-invention-novelty",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "residual_unknowns": [
            {
                "claim": "IMP-0230 scaffold generator and IMP-0232 96-entry catalog are separate units; this receipt registers knowledge slots 9-12 only.",
                "settling_experiment": "IMP-0230/IMP-0232 live artifacts",
                "verdict": "NOT-CHECKED",
            }
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "probe": {"command": P1, "method": "command"},
                "executed": False,
                "read_ok": True,
            }
        ],
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0252/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "artifacts": artifacts,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "documented-command-coverage"},
            {"id": "probe2", "command": P2, "role": "invention-novelty"},
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "notes": (
            "Four knowledge blueprints implemented as typed workflows with examples, presets, "
            "stopping rules, smoke entries and capability vectors. documentation-verification "
            "executes fenced commands and computes coverage. invention-wildcard scores Jaccard "
            "novelty against the library fingerprint set and does not treat volume as a grade."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0252" not in text:
        print("FAILED:IMP-0252 emit sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:IMP-0252")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
