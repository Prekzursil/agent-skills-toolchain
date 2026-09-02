#!/usr/bin/env python3
"""Emit WFA-0064 MechanismRecord salvage report plus per-unit receipts.

Does not run tools/command-center/unit_manifest.py --write.
Does not execute RETIRE/REJECT dispositions.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import salvage as S  # noqa: E402

UID = "WFA-0064"
OUT = S.PRIMARY_OUT
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/MechanismRecord"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0064/probe1_incidence_orphans.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0064/probe2_corpus_search_salvage.py"
)
QUESTION = (
    "Which canonical mechanisms are implemented ONLY by candidates headed "
    "for a terminal disposition, so that retiring those candidates would "
    "delete the mechanism from the estate entirely - and for each, is the "
    "mechanism worth extracting before the disposition becomes terminal?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0064/salvage.py",
    "command-center/p2-wave/probes/WFA-0064/probe1_incidence_orphans.py",
    "command-center/p2-wave/probes/WFA-0064/probe2_corpus_search_salvage.py",
    "command-center/p2-wave/probes/WFA-0064/fixtures/estate.json",
    "command-center/p2-wave/probes/WFA-0064/fixtures/corpus/kept-stage-gate.md",
    "command-center/p2-wave/probes/WFA-0064/fixtures/corpus/retire-pre-tool.md",
    "command-center/p2-wave/probes/WFA-0064/fixtures/corpus/reject-quorum.md",
    "command-center/p2-wave/probes/WFA-0064/fixtures/corpus/retire-extraction-miss.md",
    "command-center/p2-wave/probes/WFA-0064/fixtures/corpus/adopt-shared.md",
    "command-center/p2-wave/probes/WFA-0064/fixtures/corpus/retire-stub.md",
    "command-center/p2-wave/probes/WFA-0064/fixtures/corpus/surviving-extraction-miss.md",
    S.VOCAB_OUT,
    S.BLUEPRINT_OUT,
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/WFA-0064/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_doc(analysis: dict, extracts: dict, inputs: dict, recall: dict, both: dict, now: str) -> dict:
    salvaged = analysis["salvaged"]
    worth = [r["id"] for r in salvaged if r.get("worth_extracting")]
    not_worth = [r["id"] for r in salvaged if not r.get("worth_extracting")]
    answer = (
        "Live 284-candidate registry / WFA-0059 matrix / WFA-0071 re-adjudication "
        "are ABSENT on this Linux worktree (see recall_limit). Over the "
        "reconstructed fixture incidence, matrix orphans are "
        + ", ".join(analysis["matrix_orphan_ids"])
        + ". Independent surviving-corpus search, trusted only after canary "
        f"{analysis['canary']['mechanism_id']} was found in "
        f"{analysis['canary']['expected_file']}, classified "
        + ", ".join(analysis["extraction_misses"])
        + " as extraction-miss (not salvage) and confirmed salvage-necessary "
        + ", ".join(analysis["salvage_necessary"])
        + ". Each salvage-necessary mechanism was extracted into the mechanism "
        "vocabulary and a target blueprint (not a note). Worth extracting: "
        + (", ".join(worth) if worth else "(none)")
        + ". Archive-only (not worth reuse): "
        + (", ".join(not_worth) if not_worth else "(none)")
        + ". No terminal disposition was executed. Owner sign-off remains "
        "required before RETIRE/REJECT. SUCCESS:WFA-0064"
    )
    members = []
    for rec in salvaged:
        members.append(
            {
                "record_type": "MechanismRecord",
                "id": rec["id"],
                "name": rec["name"],
                "definition": rec["definition"],
                "implementing_candidates": rec["implementing_candidates"],
                "source_anchors": rec["source_anchors"],
                "licence_class": rec["licence_class"],
                "worth_extracting": rec["worth_extracting"],
                "salvage_status": rec["salvage_status"],
                "vocabulary": rec["vocabulary"],
                "target_blueprint": rec["target_blueprint"],
            }
        )
    return {
        "record_type": "MechanismRecord",
        "id": "wfa.orphan-mechanism-salvage",
        "unit_id": UID,
        "name": "orphan-mechanism-salvage",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0064",
        "completion_sentinel": "SUCCESS:WFA-0064",
        "output_schema": SCHEMA,
        "schema_pack_present": (REPO / "command-center/wfa/schema/wfa-schema-pack.json").is_file(),
        "definition": (
            "Catalog of canonical mechanisms whose only implementing candidates "
            "are RETIRE- or REJECT-bound, after an independent surviving-corpus "
            "search confirmed absence, each extracted into the vocabulary and a "
            "target blueprint."
        ),
        "licence_class": "estate-internal",
        "namespace": "mechanism",
        "question": QUESTION,
        "answer": answer,
        "title": "Salvage mechanisms that exist only inside RETIRE- or REJECT-bound candidates",
        "extraction_rule": analysis["extraction_rule"],
        "terminal_dispositions": analysis["terminal_dispositions"],
        "terminal_candidates": analysis["terminal_candidates"],
        "incidence": analysis["incidence"],
        "incidence_cells": analysis["incidence_cells"],
        "matrix_orphans": analysis["matrix_orphans"],
        "matrix_orphan_ids": analysis["matrix_orphan_ids"],
        "not_orphan": analysis["not_orphan"],
        "empty_implementer_excluded": analysis["empty_implementer_excluded"],
        "corpus_hits": analysis["corpus_hits"],
        "canary": {
            "mechanism_id": analysis["canary"]["mechanism_id"],
            "found": analysis["canary"]["found"],
            "found_in_expected_file": analysis["canary"]["found_in_expected_file"],
            "expected_file": analysis["canary"]["expected_file"],
            "hit_count": analysis["canary"]["hit_count"],
            "silence_trusted": analysis["canary"]["silence_trusted"],
            "surviving_files": analysis["canary"]["surviving_files"],
        },
        "silence_status": analysis["silence_status"],
        "extraction_misses": analysis["extraction_misses"],
        "salvage_necessary": analysis["salvage_necessary"],
        "salvaged_ids": analysis["salvaged_ids"],
        "members": members,
        "vocabulary": [m["vocabulary"] for m in members],
        "target_blueprints": [m["target_blueprint"] for m in members],
        "extracts": extracts,
        "gate": analysis["gate"],
        "both_states": both,
        "note_only_rejected": analysis["note_only_rejected"],
        "all_salvages_extracted": analysis["all_salvages_extracted"],
        "live_inputs": inputs,
        "recall_limit": recall,
        "owner_signoff": {
            "required": True,
            "present": False,
            "scope": "execute RETIRE or REJECT on a candidate",
            "note": (
                "Salvage extraction into vocabulary and blueprints is not an "
                "irreversible terminal disposition and does not self-certify one. "
                "The gate refuses execution while unsalvaged orphans remain and "
                "still refuses execution after salvage until owner sign-off."
            ),
        },
        "tests": [
            {
                "id": "T1-no-terminal-while-unsalvaged",
                "name": "no terminal disposition may be executed while an unsalvaged orphan mechanism depends on it",
                "command": P1,
                "result": "PENDING",
            },
            {
                "id": "T2-canary-before-silence",
                "name": "the direct search must be shown to find a known-present implementation before its silence is trusted",
                "command": P2,
                "result": "PENDING",
            },
            {
                "id": "T3-salvage-is-extraction",
                "name": "salvage means extracting the mechanism into the vocabulary and a target blueprint, not merely noting it",
                "command": P2,
                "result": "PENDING",
            },
        ],
        "evidence": {
            "A": (
                "incidence matrix cells over the reconstructed estate; orphans "
                "are mechanisms whose implementing-candidate set is a non-empty "
                "subset of {RETIRE, REJECT}"
            ),
            "B": (
                "DEFINE-heading search of surviving (non-terminal) files; canary "
                "must hit before silence is trusted; a surviving DEFINE of a "
                "matrix orphan is an extraction miss"
            ),
        },
        "reviewer": {
            "reviewer_id": "WFA-0064-probe2-corpus-search-salvage",
            "verdict": "PENDING",
            "independent": True,
            "notes": (
                "Probe 2 independently re-searches surviving files, requires the "
                "canary hit, rejects note-only salvage, and checks extracts on disk."
            ),
        },
        "environment": {
            "os": platform.platform(),
            "python": sys.version.split()[0],
            "cwd": str(REPO),
            "ts": now,
        },
        "produced_by": {
            "execution_substrate": "local-parallel-linux",
            "role": "archaeologist",
        },
        "cloud_ok": False,
        "scope": {
            "proof_surface": (
                "reconstructed fixture incidence + independent DEFINE search + "
                "extraction bar + terminal gate"
            ),
            "does_not_claim": [
                "the live 284-candidate RETIRE n=24 histogram was recomputed here",
                "WFA-0059 or WFA-0071 artifacts were present",
                "any RETIRE or REJECT was executed",
                "owner sign-off was obtained",
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
            ],
        },
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    estate = S.load_estate()
    analysis = S.analyze(estate)
    if not analysis["canary"]["silence_trusted"]:
        print("FAILED:WFA-0064 emit canary silence untrusted")
        return 1
    if not analysis["all_salvages_extracted"]:
        print("FAILED:WFA-0064 emit salvage bar")
        return 1
    if analysis["gate"]["any_executed"] or analysis["gate"]["before_salvage"].get("executed"):
        print("FAILED:WFA-0064 emit executed a terminal disposition")
        return 1
    extracts = S.write_extracts(analysis)
    inputs = S.live_inputs()
    recall = S.recall_limit(inputs)
    both = S.both_states(estate)
    if not both["pass"]:
        print(f"FAILED:WFA-0064 emit both-states {both}")
        return 1

    doc = build_doc(analysis, extracts, inputs, recall, both, now)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    rc1, t1 = run_cmd(P1)
    rc2, t2 = run_cmd(P2)
    print(f"probe1 rc={rc1}")
    print(t1[-2500:])
    print(f"probe2 rc={rc2}")
    print(t2[-2500:])
    if rc1 != 0 or rc2 != 0:
        print("FAILED:WFA-0064 emit probes")
        return 1

    doc["tests"][0]["result"] = "PASS"
    doc["tests"][1]["result"] = "PASS"
    doc["tests"][2]["result"] = "PASS"
    doc["reviewer"]["verdict"] = "PASS"
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    rc1b, t1b = run_cmd(P1)
    rc2b, t2b = run_cmd(P2)
    if rc1b != 0 or rc2b != 0:
        print("FAILED:WFA-0064 emit re-run after stamp")
        print(t1b[-1500:])
        print(t2b[-1500:])
        return 1

    digest, size = sha256_file(out_path)
    if size < 1024:
        print(f"FAILED:WFA-0064 artifact too small {size}")
        return 1
    if "SUCCESS:WFA-0064" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:WFA-0064 sentinel missing after write")
        return 1

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0064",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "cloud_ok": False,
        "measure_line": None,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1b,
                "role": "incidence-orphans-both-states-gate",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2b,
                "role": "corpus-search-canary-salvage",
                "raw_output": t2b,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0064/SUBAGENT-RETURN.json".replace(
            "SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "WFA-0064-probe2-corpus-search-salvage",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for WFA-0064: live named probes exit 0, salvage artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle. Did not execute "
            "RETIRE/REJECT. Live 284-registry unread is listed in recall_limit."
        ),
    }
    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
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
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:WFA-0064 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
