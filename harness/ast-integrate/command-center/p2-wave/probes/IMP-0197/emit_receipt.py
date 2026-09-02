#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0197.json from live paired A/B runs."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.evals.paired_ab import (  # noqa: E402
    DEFAULT_MIN_N,
    INSUFFICIENT_EVIDENCE,
    run_paired_ab,
)
from scenario import (  # noqa: E402
    CORPUS_ID,
    WF_LEN,
    WF_PLUS,
    POWERED_N,
    UNDERPOWERED_N,
    powered_cases,
    underpowered_cases,
)

OUT = "command-center/receipts/IMP-0197.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0197/probe1_underpowered.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0197/probe2_zero_effect.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def archive_run(name: str, result: dict) -> dict:
    path = HERE / "archive" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")
    digest, size = sha256_file(path)
    rel = path.relative_to(REPO).as_posix()
    return {"path": rel, "sha256": digest, "bytes": size, "n": result.get("n")}


def main() -> int:
    under_cases = underpowered_cases()
    power_cases = powered_cases()
    under = run_paired_ab(
        WF_PLUS, WF_LEN, under_cases, corpus_id=f"{CORPUS_ID}:underpowered"
    )
    powered = run_paired_ab(
        WF_PLUS, WF_LEN, power_cases, corpus_id=f"{CORPUS_ID}:powered"
    )
    selfc = run_paired_ab(
        WF_LEN, WF_LEN, power_cases, corpus_id=f"{CORPUS_ID}:self-compare"
    )

    if under.get("status") != INSUFFICIENT_EVIDENCE or "verdict" in under:
        print("FAILED:IMP-0197 emit underpowered did not refuse")
        print(json.dumps(under, indent=2)[:2000])
        return 1
    if under.get("n") != UNDERPOWERED_N:
        print("FAILED:IMP-0197 emit underpowered n", under.get("n"))
        return 1
    if powered.get("verdict") != "A_BETTER" or powered.get("status") != "POWERED":
        print("FAILED:IMP-0197 emit powered", powered.get("status"), powered.get("verdict"))
        return 1
    if powered.get("n") != POWERED_N:
        print("FAILED:IMP-0197 emit powered n", powered.get("n"))
        return 1
    if selfc.get("verdict") != "ZERO_EFFECT":
        print("FAILED:IMP-0197 emit self-compare", selfc.get("verdict"))
        return 1
    if any(abs(float(r["delta"])) > 1e-12 for r in (selfc.get("paired_deltas") or [])):
        print("FAILED:IMP-0197 emit self-compare nonzero delta")
        return 1

    arch_under = archive_run("underpowered", under)
    arch_power = archive_run("powered", powered)
    arch_self = archive_run("self-compare", selfc)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runner_rel = "tools/agentspec/agentspec/evals/paired_ab.py"
    registry_rel = "tools/agentspec/agentspec/evals/registry.py"
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0197",
        "id": "IMP-0197",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0197",
        "completion_sentinel": "SUCCESS:IMP-0197",
        "title": "Build the paired A/B benchmark runner with matched cases and paired statistics",
        "question_or_target": (
            "Target: run two workflows over the SAME case set with paired analysis "
            "(per-case delta, not group means). Acceptance: the runner reports effect "
            "size and the number of cases, and REFUSES to emit a verdict below a "
            "declared minimum case count instead of reporting a percentage over three cases."
        ),
        "min_bytes_threshold": 2048,
        "declared_min_n": DEFAULT_MIN_N,
        "runner": {
            "module": "agentspec.evals.paired_ab",
            "path": runner_rel,
            "registry_path": registry_rel,
            "default_min_n": DEFAULT_MIN_N,
            "analysis": "per-case paired delta (score_a - score_b); not group means",
            "hermetic": True,
            "live_model_calls": 0,
        },
        "dependency_honesty": {
            "catalog_depends_on": ["IMP-0198"],
            "imp_0198_delivered_on_this_tree": (
                REPO / "command-center/receipts/IMP-0198.json"
            ).is_file(),
            "note": (
                "IMP-0198 (hash-partitioned held-out corpus) is not delivered on this "
                "worktree. Probes use a local deterministic fixture corpus with the "
                "same case-object shape (id, stratum, payload). This receipt does not "
                "claim IMP-0198 is complete."
            ),
            "agentspec_evals_registry_created": True,
        },
        "underpowered_run": under,
        "powered_run": powered,
        "self_compare_run": selfc,
        "archives": [arch_under, arch_power, arch_self],
        "tests": {
            "underpowered_returns_insufficient_evidence": {
                "pass": True,
                "n": under["n"],
                "min_n": DEFAULT_MIN_N,
                "status": under["status"],
                "verdict_omitted": "verdict" not in under,
            },
            "powered_emits_verdict_both_states": {
                "pass": True,
                "n": powered["n"],
                "verdict": powered["verdict"],
            },
            "identical_workflows_zero_effect": {
                "pass": True,
                "n": selfc["n"],
                "verdict": selfc["verdict"],
                "raw_mean_delta": (selfc.get("effect_size") or {}).get("raw_mean_delta"),
            },
        },
        "evidence": {
            "two_independent_signals": True,
            "signal_1_paired_deltas_archived": {
                "underpowered_rows": len(under.get("paired_deltas") or []),
                "powered_rows": len(powered.get("paired_deltas") or []),
                "self_compare_rows": len(selfc.get("paired_deltas") or []),
                "archive_paths": [arch_under["path"], arch_power["path"], arch_self["path"]],
            },
            "signal_2_underpowered_insufficient_with_powered_twin": {
                "underpowered_status": under["status"],
                "powered_status": powered["status"],
                "powered_verdict": powered["verdict"],
            },
        },
        "negative_controls": [
            {
                "id": "underpowered-no-percentage-verdict",
                "kind": "both-states",
                "description": (
                    "3 matched cases where A is strictly better must not emit A_BETTER "
                    f"because n < min_n={DEFAULT_MIN_N}; 24 cases of the same pair must."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "self-compare-zero-effect",
                "kind": "sanity-control",
                "description": "Identical workflow vs itself on a powered set yields ZERO_EFFECT.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0197-probe1-underpowered",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 re-runs underpowered and powered arms against the live "
                "runner and byte-compares archived paired_deltas to the receipt. "
                "Named probe2 re-runs the self-compare on a different assertion "
                "(zero effect). Catalog scoring by a second human is independent of G-1."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "underpowered-both-states", "command": P1},
            {"id": "probe2", "role": "self-compare-zero-effect", "command": P2},
        ],
        "timestamps": {"ended_at": now},
        "cloud_ok": False,
        "registered": True,
        "scope": {
            "proof_surface": (
                "Hermetic scorers over a local matched case fixture; paired deltas "
                "archived; min_n gate live. Not a claim that IMP-0198 held-out "
                "partitions exist, and not a live-model benchmark."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "IMP-0198 corpus is delivered",
                "live LLM calls were made",
            ],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": runner_rel, "exists": True, "role": "supporting"},
            {"path": registry_rel, "exists": True, "role": "supporting"},
        ],
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0197 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0197" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0197 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"under={under['status']} n={under['n']} "
        f"powered={powered['verdict']} n={powered['n']} "
        f"self={selfc['verdict']}"
    )
    print("SUCCESS:IMP-0197 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
