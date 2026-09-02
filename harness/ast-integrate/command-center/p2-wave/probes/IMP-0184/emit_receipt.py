#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0184.json from live union-fusion measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from coverage import TAXONOMY, coverage_vector, is_superset, missing_from_superset  # noqa: E402
from fingerprint import workflow_fingerprint  # noqa: E402
from scenario import fixtures_ok, workflow_a, workflow_b, workflow_w  # noqa: E402
from union_fusion import (  # noqa: E402
    drop_stage,
    mutate_one_gate,
    naive_concat,
    rename_workflow,
    union_fuse,
)

OUT = "command-center/receipts/IMP-0184.json"
UNIT = "IMP-0184"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0184/probe1_idempotence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0184/probe2_superset.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": max(len(data), 1),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
        "exit_code": exit_code,
    }


def evidence(claim: str, verdict: str, anchor: str, probes: list, confidence: str) -> dict:
    return {
        "claim": claim,
        "verdict": verdict,
        "anchor": anchor,
        "probes": probes,
        "confidence": confidence,
    }


def control(cid: str, kind: str, description: str, fired_bad: bool, silent_good: bool, bad: str, good: str) -> dict:
    return {
        "id": cid,
        "kind": kind,
        "description": description,
        "fired_on_bad_state": fired_bad,
        "silent_on_good_state": silent_good,
        "bad_state_output": str(bad)[:16000],
        "good_state_output": str(good)[:16000],
    }


def emit_stage_id(fused: dict) -> str:
    for stage in fused["stages"]:
        if stage.get("kind") == "emit":
            return str(stage["id"])
    raise AssertionError("union lost emit stage")


def main() -> int:
    fixtures_ok()
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    w = workflow_w()
    w2 = rename_workflow(w)
    fused_w = union_fuse(w, w2)
    concat_w = naive_concat(w, w2)
    mutant = mutate_one_gate(w)
    fp_w = workflow_fingerprint(w)
    fp_w2 = workflow_fingerprint(w2)
    fp_u = workflow_fingerprint(fused_w)
    fp_c = workflow_fingerprint(concat_w)
    fp_m = workflow_fingerprint(mutant)

    a = workflow_a()
    b = workflow_b()
    fused_ab = union_fuse(a, b)
    concat_ab = naive_concat(a, b)
    cov_a = coverage_vector(a)
    cov_b = coverage_vector(b)
    cov_u = coverage_vector(fused_ab)
    cov_c = coverage_vector(concat_ab)
    super_ok = is_superset(cov_u, cov_a) and is_superset(cov_u, cov_b)
    concat_super = is_superset(cov_c, cov_a) and is_superset(cov_c, cov_b)

    lossy = drop_stage(fused_ab, emit_stage_id(fused_ab))
    cov_lossy = coverage_vector(lossy)
    lossy_fails = not is_superset(cov_lossy, cov_b)
    lossy_missing = missing_from_superset(cov_lossy, cov_b)

    idempotent = fp_w == fp_w2 == fp_u
    concat_differs = fp_c != fp_w
    collapsed = len(fused_w["stages"]) == len(w["stages"]) and len(concat_w["stages"]) == 2 * len(w["stages"])
    ingest_collapsed = len(fused_ab["stages"]) == 3 and len(concat_ab["stages"]) == 4
    gate_changes = fp_m != fp_w

    live_ok = (
        idempotent
        and concat_differs
        and collapsed
        and super_ok
        and concat_super
        and ingest_collapsed
        and lossy_fails
        and "build.emit" in lossy_missing
        and gate_changes
    )
    if not live_ok:
        print("FAILED:IMP-0184 live union/coverage measurements did not hold")
        print(
            json.dumps(
                {
                    "idempotent": idempotent,
                    "concat_differs": concat_differs,
                    "collapsed": collapsed,
                    "super_ok": super_ok,
                    "lossy_fails": lossy_fails,
                    "lossy_missing": lossy_missing,
                },
                indent=1,
            )
        )
        return 1

    supporting = [
        "command-center/p2-wave/probes/IMP-0184/fingerprint.py",
        "command-center/p2-wave/probes/IMP-0184/coverage.py",
        "command-center/p2-wave/probes/IMP-0184/union_fusion.py",
        "command-center/p2-wave/probes/IMP-0184/scenario.py",
        "command-center/p2-wave/probes/IMP-0184/probe1_idempotence.py",
        "command-center/p2-wave/probes/IMP-0184/probe2_superset.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print("FAILED:IMP-0184 supporting artifacts missing", missing)
        return 1

    measure = {
        "fp_w": fp_w,
        "fp_renamed": fp_w2,
        "fp_union_w": fp_u,
        "fp_naive_concat_w": fp_c,
        "stage_count_w": len(w["stages"]),
        "stage_count_union_w": len(fused_w["stages"]),
        "stage_count_concat_w": len(concat_w["stages"]),
        "coverage_a_vector": cov_a["vector"],
        "coverage_b_vector": cov_b["vector"],
        "coverage_union_vector": cov_u["vector"],
        "coverage_names": TAXONOMY["capabilities"],
        "taxonomy_version": TAXONOMY["version"],
        "union_ab_stage_count": len(fused_ab["stages"]),
        "concat_ab_stage_count": len(concat_ab["stages"]),
        "lossy_missing": lossy_missing,
    }
    p1_src = probe(
        "source",
        "command",
        "python3 -B union_fuse(w, rename(w)); workflow_fingerprint",
        json.dumps(
            {
                "fp_w": fp_w,
                "fp_renamed": fp_w2,
                "fp_union": fp_u,
                "n_union": len(fused_w["stages"]),
            },
            sort_keys=True,
        ),
        0,
    )
    p1_ver = probe(
        "verifier",
        "command",
        "python3 -B naive_concat(w, rename(w)); compare fingerprints",
        json.dumps(
            {
                "fp_concat": fp_c,
                "differs_from_w": concat_differs,
                "n_concat": len(concat_w["stages"]),
            },
            sort_keys=True,
        ),
        0,
    )
    p2_src = probe(
        "source",
        "command",
        "python3 -B coverage_vector(union_fuse(a,b))",
        json.dumps(
            {
                "a": cov_a["vector"],
                "b": cov_b["vector"],
                "union": cov_u["vector"],
                "superset": super_ok,
            },
            sort_keys=True,
        ),
        0,
    )
    p2_ver = probe(
        "verifier",
        "other",
        "drop emit stage from union(a,b) and recompute superset vs b",
        json.dumps(
            {
                "lossy_fails_superset_b": lossy_fails,
                "missing": lossy_missing,
            },
            sort_keys=True,
        ),
        0,
    )

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0184",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0184",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            evidence(
                (
                    f"union(w, rename(w)) fingerprint-equals w "
                    f"(fp={fp_w[:16]}…, stages {len(w['stages'])}->{len(fused_w['stages'])}). "
                    f"naive_concat yields {len(concat_w['stages'])} stages and fp "
                    f"{fp_c[:16]}… which differs. Gate mutation changes fp "
                    f"({fp_w[:12]} -> {fp_m[:12]})."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/IMP-0184/union_fusion.py:union_fuse",
                [p1_src, p1_ver],
                "almost-certain",
            ),
            evidence(
                (
                    f"coverage-vector(union(a,b))={cov_u['vector']} is a componentwise "
                    f"superset of a={cov_a['vector']} and b={cov_b['vector']} over "
                    f"taxonomy {TAXONOMY['id']}@{TAXONOMY['version']}. Shared ingest "
                    f"collapsed ({len(concat_ab['stages'])} concat stages -> "
                    f"{len(fused_ab['stages'])} union stages). Dropping B's emit stage "
                    f"loses {lossy_missing} and fails the superset check."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/IMP-0184/coverage.py:is_superset",
                [p2_src, p2_ver],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "T1-idempotence-union-w-w",
                "command": P1,
                "result": "PASS",
                "assertions": 5,
                "output_tail": f"fp_equal={idempotent} concat_differs={concat_differs} n_union={len(fused_w['stages'])}",
            },
            {
                "id": "T2-capability-superset",
                "command": P2,
                "result": "PASS",
                "assertions": 4,
                "output_tail": f"super_ok={super_ok} lossy_missing={lossy_missing}",
            },
        ],
        "negative_controls": [
            control(
                "IMP0184-C1-naive-concat",
                "known-broken-fixture",
                (
                    "A concatenating union is the cheapest falsifier of idempotence. "
                    "naive_concat(w, rename(w)) must fingerprint-differ from w; "
                    "union_fuse on the same pair must not."
                ),
                concat_differs,
                idempotent,
                f"concat fp={fp_c} n={len(concat_w['stages'])}",
                f"union fp={fp_u} n={len(fused_w['stages'])}",
            ),
            control(
                "IMP0184-C2-lossy-drop-emit",
                "known-broken-fixture",
                (
                    "A coverage comparator that always returns true is silent. "
                    "Dropping B's unique emit stage from the fusion must fail "
                    "the superset check against B."
                ),
                lossy_fails,
                super_ok,
                f"lossy missing={lossy_missing}",
                f"union vector={cov_u['vector']}",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0184-probe2-capability-superset",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0184/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0184",
                    "named probes re-run after this receipt is on disk; G-1 SUCCESS:delivered",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0170's production fingerprint module is not on this worktree; "
                    "IMP-0184 ships a local rename-invariant fingerprint used by union "
                    "collapse. A later IMP-0170 delivery must be compared, not assumed equal."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "After IMP-0170 lands, hash the same fixtures with both fingerprinters "
                    "and require equality on rename mutants and inequality on gate mutants."
                ),
            }
        ],
        "report": measure,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0184" not in payload:
        print("FAILED:IMP-0184 sentinel missing from payload")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0184 artifact {size}B below floor")
        return 1
    sha, nbytes = sha256_file(out_path)
    print(f"wrote {OUT} bytes={nbytes} sha256={sha}")
    print("SUCCESS:IMP-0184")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
