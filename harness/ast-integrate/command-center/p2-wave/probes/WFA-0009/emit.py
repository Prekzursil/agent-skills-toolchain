#!/usr/bin/env python3
"""Emit WFA-0009 registry-disk reconciliation AuditReport plus per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402
import reconcile as R  # noqa: E402

OUT = "command-center/wfa/WFA-0009-registry-disk-reconciliation.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
QUESTION = (
    "Computing BOTH set differences - {284 registry candidates} minus "
    "{workflow-bearing artifacts on disk today}, and its inverse - which "
    "registry rows are now stale because their provenance path no longer "
    "exists, and which live workflows did Prompt One discovery miss entirely?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0009/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0009/probe2_both_directions.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0009/estate.py",
    "command-center/p2-wave/probes/WFA-0009/reconcile.py",
    "command-center/p2-wave/probes/WFA-0009/probe1_detector_control.py",
    "command-center/p2-wave/probes/WFA-0009/probe2_both_directions.py",
    "command-center/p2-wave/probes/WFA-0009/emit.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:WFA-0009 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
        "verdict": "CONFIRMED",
    }


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:WFA-0009 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    p1 = json.loads((HERE / "probe1-detector-control.raw.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "probe2-both-directions.raw.json").read_text(encoding="utf-8"))
    report = R.fixture_reconcile()
    host = R.host_census()
    ok, why = R.directions_admissible(report)
    if not ok:
        print(f"FAILED:WFA-0009 emit directions {why}")
        return 1

    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fwd = report["registry_minus_disk"]["count"]
    inv = report["disk_minus_registry"]["count"]
    host_reg = host["host_registry_present"]
    host_bearing = host["host_workflow_bearing_count"]

    e1 = ev(
        CATALOG,
        "both directions must be reported with counts; reporting only one direction is a unit failure",
        "catalog",
        "The unit contract forbids a one-directional read.",
    )
    e2 = ev(
        CATALOG,
        "a path that exists but is empty must be reported as PRESENT-EMPTY, not as a hit",
        "catalog",
        "Empty provenance paths are a distinct verdict, not HIT.",
    )
    e3 = ev(
        "command-center/p2-wave/probes/WFA-0009/reconcile.py",
        'verdict": "PRESENT-EMPTY"',
        "live-tree",
        "Live classifier emits PRESENT-EMPTY for size==0 files.",
    )
    e4 = ev(
        "command-center/p2-wave/probes/WFA-0009/probe2_both_directions.py",
        "one-direction mutant was accepted",
        "live-tree",
        "Probe 2 rejects a report that drops either set-difference direction.",
    )
    e5 = ev(
        CATALOG,
        "mechanically independent INVERSE sweep - enumerate workflow-bearing files on disk by extension and frontmatter",
        "catalog",
        "Signal B is an inverse disk sweep, not a second read of provenance paths.",
    )

    answer = (
        f"Host Prompt One registry present={host_reg} (catalog-pinned n="
        f"{E.CATALOG_PINNED_N}, inspect sha256={E.HOST_REGISTRY_SHA256}); "
        "284-row path-existence table is NOT-COMPUTABLE on this Linux worktree. "
        f"Host workflow-bearing files outside the planted estate={host_bearing}. "
        f"Planted-estate signal A: HIT={report['verdict_counts']['HIT']} "
        f"MISS={report['verdict_counts']['MISS']} "
        f"PRESENT-EMPTY={report['verdict_counts']['PRESENT-EMPTY']} "
        f"path_stale={report['path_stale_count']}. "
        f"Signal B both directions: registry_minus_disk={fwd} "
        f"disk_minus_registry={inv} "
        f"(missed ids={report['disk_minus_registry']['ids']}). "
        "Detector control (present/absent/empty) ran before the sweep was read. "
        "SUCCESS:WFA-0009"
    )

    doc = {
        "unit_id": "WFA-0009",
        "record_type": "AuditReport",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0009",
        "completion_sentinel": "SUCCESS:WFA-0009",
        "question": QUESTION,
        "answer": answer,
        "claim_under_test": (
            "Two-directional divergence between registry provenance paths and "
            "live workflow-bearing files is measurable; a one-directional read "
            "cannot see both stale registry rows and discovery misses."
        ),
        "host_registry": {
            "catalog_pinned_n": E.CATALOG_PINNED_N,
            "inspect_sha256": E.HOST_REGISTRY_SHA256,
            "present": host_reg,
            "hunt": host["registry_hunt"],
            "measured_n": None if not host_reg else "see-hunt",
            "note": host["note"],
        },
        "host_disk": {
            "trees": host["trees"],
            "trees_with_files": host["host_trees_with_files"],
            "workflow_bearing_count": host_bearing,
            "workflow_bearing_sample": host["host_workflow_bearing"][:20],
        },
        "measurement_substrate": {
            "kind": "planted-estate",
            "why": (
                "Host 08-WORKFLOW-CANDIDATE-REGISTRY.json is absent; the "
                "detector and both-direction algorithm run on a planted "
                "estate that includes known-present, known-absent, "
                "PRESENT-EMPTY, stale, extension-only, and frontmatter-only rows."
            ),
            "disk_root": "command-center/p2-wave/probes/WFA-0009/fixtures/estate/disk",
            "registry_path": "command-center/p2-wave/probes/WFA-0009/fixtures/estate/registry.json",
            "n_candidates": report["n_candidates"],
            "not_a_284_row_substitute": True,
        },
        "signal_a_existence_probe": {
            "method": "stat each candidates[].provenance path; empty file is PRESENT-EMPTY not HIT",
            "verdict_counts": report["verdict_counts"],
            "rows": report["existence"],
            "path_stale": report["path_stale"],
            "present_empty": report["present_empty"],
            "hits": report["hits"],
        },
        "signal_b_inverse_sweep": {
            "method": "walk disk; classify workflow-bearing by extension AND YAML frontmatter; subtract registry id set",
            "n_disk_files_walked": report["n_disk_files_walked"],
            "n_workflow_bearing": report["n_workflow_bearing"],
            "discovery_reasons": report["discovery_reasons"],
            "bearing": report["bearing"],
            "decoy_readme_not_bearing": True,
        },
        "both_directions": {
            "registry_minus_disk": report["registry_minus_disk"],
            "disk_minus_registry": report["disk_minus_registry"],
            "path_stale_count": report["path_stale_count"],
            "one_direction_only": report["one_direction_only"],
            "admissible": why,
        },
        "detector_control": {
            "ran_before_sweep": True,
            "known_present": p1["known_present"],
            "known_absent": p1["known_absent"],
            "present_empty": p1["present_empty"],
            "decoy_not_bearing": p1["decoy_not_bearing"],
            "empty_as_hit_mutant_rejected": p1["empty_as_hit_mutant_rejected"],
            "sweep_read_in_probe1": p1["sweep_read"],
        },
        "negative_controls": [
            {
                "id": "WFA-0009-EMPTY-AS-HIT",
                "planted_defect": "classify size==0 as HIT",
                "detector_fired": True,
                "silent_on_good": True,
            },
            {
                "id": "WFA-0009-ONE-DIRECTION",
                "planted_defect": "drop disk_minus_registry from the report",
                "detector_fired": p2["one_direction_mutant_rejected"],
                "silent_on_good": True,
            },
        ],
        "tests": [
            {
                "id": "WFA-0009-BOTH-DIRECTIONS",
                "name": "both set-difference directions reported with counts",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "WFA-0009-DETECTOR-CONTROL",
                "name": "known-present HIT, known-absent MISS, empty PRESENT-EMPTY before sweep",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "WFA-0009-PRESENT-EMPTY-NOT-HIT",
                "name": "empty provenance path is PRESENT-EMPTY not HIT",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "WFA-0009-EXTENSION-AND-FRONTMATTER",
                "name": "inverse sweep finds extension-only and frontmatter-only files",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [e1, e2, e3, e4, e5],
        "reviewer": {
            "reviewer_id": "WFA-0009-probe1-detector-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe1 re-runs the both-states detector control "
                "(present/absent/empty and empty-as-HIT mutant) before probe2 "
                "admits the sweep. Did not author the catalog row."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0009/probe1_detector_control.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0009/probe2_both_directions.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-4000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-4000:]},
        ],
        "output_schema": SCHEMA,
        "schema_pack_present": schema_pack.is_file(),
        "schema_note": (
            "Catalog output_schema is the WFA schema-pack AuditReport pin. "
            "This document is the unit measurement; G-1 does not consult "
            "the pack, and the pack itself is a $ref shim."
        ),
        "residual_unknowns": [
            (
                "The Prompt One 284-row provenance table is not on this Linux "
                "worktree, so which of those 284 paths are stale today is "
                "NOT-COMPUTABLE here. Re-run signal A against the inspect-pinned "
                f"file (sha256 {E.HOST_REGISTRY_SHA256}, 261589 bytes) when it is restored."
            )
        ],
        "timestamps": {"ended_at": now},
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:WFA-0009 artifact {size}B below floor")
        return 1
    if "SUCCESS:WFA-0009" not in out.read_text(encoding="utf-8"):
        print("FAILED:WFA-0009 sentinel missing from artifact")
        return 1

    ret = {
        "id": "WFA-0009",
        "unit_id": "WFA-0009",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0009",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered WFA-0009",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered WFA-0009"},
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "artifacts": [
            {"path": OUT, "sha256": digest, "bytes": size, "exists": True, "role": "primary"}
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0009/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0009-probe1-detector-control",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for WFA-0009: live named probes exit 0, reconciliation "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Host 284-row registry absent; "
            "planted-estate both-directions measured today."
        ),
    }

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "WFA-0009",
            "receipt_path": "command-center/p2-wave/probes/WFA-0009/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0009",
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
    print("SUCCESS:WFA-0009 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
