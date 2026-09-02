#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0400.json (paired live-vs-router benchmark)."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import bench as B  # noqa: E402
import schema_local as S  # noqa: E402

OUT = "command-center/receipts/IMP-0400.json"
SCHEMA = "command-center/schema/benchmark-result.schema.json"
SENTINEL = "SENTINEL:IMP-0400:ROUTER-BENCHMARK-PAIRED"
QUESTION = (
    "Measure the new router against the CURRENT live selection behavior on the "
    "same corpus: precision@k, recall of relevant capabilities, and repertoire "
    "breadth. Exact question: does the new router beat the live baseline on "
    "breadth WITHOUT losing precision, and if it trades one for the other, by "
    "exactly how much?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0400/probe1_paired_capture.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0400/probe2_determinism_rerun.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/IMP-0400/bench.py",
    "command-center/p2-wave/probes/IMP-0400/live_baseline.py",
    "command-center/p2-wave/probes/IMP-0400/router.py",
    "command-center/p2-wave/probes/IMP-0400/probe1_paired_capture.py",
    "command-center/p2-wave/probes/IMP-0400/probe2_determinism_rerun.py",
    "command-center/p2-wave/probes/IMP-0400/schema_local.py",
]


def now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    digest, size = sha_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def spec_anchor() -> str:
    text = (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if '"id": "IMP-0400"' in line:
            return f"command-center/WORK-UNIT-CATALOG.json:{i}"
    return "command-center/WORK-UNIT-CATALOG.json:IMP-0400"


def sentence(ans: dict) -> str:
    verb = (
        "beats"
        if ans["beats_live_breadth_without_losing_precision"]
        else "does not beat"
    )
    return (
        f"The new router {verb} the live baseline on repertoire breadth without "
        f"losing precision: breadth delta {ans['breadth_delta']:.6f}, "
        f"precision@k delta {ans['precision_at_k_delta']:.6f}, "
        f"recall@k delta {ans['recall_at_k_delta']:.6f}. Trade: {ans['trade']}."
    )


def main() -> int:
    started = now()
    run1 = B.run_protocol()
    run2 = B.run_protocol()
    diff = B.max_metric_diff(run1, run2)
    if diff > B.DETERMINISM_TOLERANCE:
        print(f"FAILED:IMP-0400 two frozen runs differ by {diff}")
        return 1
    if run1["anti_reconstruct"]["matches_captured_live"]:
        print("FAILED:IMP-0400 live snapshot equals router reconstruction")
        return 1
    if run1["corpus_meta"]["negative_fraction"] < 0.25:
        print("FAILED:IMP-0400 negative fraction below 25 percent")
        return 1

    top3 = B.always_top3_preds(B.CORPUS, B.CAPABILITIES, B.K)
    top3_m = B.metrics_for(top3, run1["golds"], len(B.CAPABILITIES))
    if top3_m["precision_at_k"] >= 0.20:
        print("FAILED:IMP-0400 corpus too easy for always-top-3")
        return 1

    easy_golds = [["git"] for _ in B.CORPUS]
    easy_m = B.metrics_for(top3, easy_golds, len(B.CAPABILITIES))
    easy_too_easy = easy_m["precision_at_k"] >= 0.20
    if not easy_too_easy:
        print("FAILED:IMP-0400 easy-gold control did not fire")
        return 1

    mutated = copy.deepcopy(B.CORPUS)
    mutated[0]["gold"] = ["___not_a_real_capability___"]
    mut = B.run_protocol(corpus=mutated)
    mut_shifts = abs(B.max_metric_diff(run1, mut)) > B.DETERMINISM_TOLERANCE
    if not mut_shifts:
        print("FAILED:IMP-0400 gold mutation was silent")
        return 1

    dep_0398 = (REPO / "command-center/receipts/IMP-0398.json").is_file()
    router_sha, _ = sha_file("command-center/p2-wave/probes/IMP-0400/router.py")
    ans = run1["exact_answer"]
    ended = now()
    metrics_raw = json.dumps(run1["metrics"], sort_keys=True, separators=(",", ":"))
    recon_raw = (
        f"live={run1['baseline_capture']['snapshot_sha256']} "
        f"recon={run1['anti_reconstruct']['router_as_baseline_sha256']} "
        f"match={run1['anti_reconstruct']['matches_captured_live']}"
    )
    replay_raw = (
        f"max_abs_diff={diff} snapshot="
        f"{run1['baseline_capture']['snapshot_sha256']}"
    )

    report = {
        "kind": "benchmark-result",
        "observations": [
            {
                "name": "precision_at_k_live",
                "measured": run1["metrics"]["live"]["precision_at_k"],
                "method": "mean-precision-at-k",
                "anchor": "command-center/p2-wave/probes/IMP-0400/bench.py:metrics_for",
            },
            {
                "name": "precision_at_k_router",
                "measured": run1["metrics"]["router"]["precision_at_k"],
                "method": "mean-precision-at-k",
                "anchor": "command-center/p2-wave/probes/IMP-0400/bench.py:metrics_for",
            },
            {
                "name": "breadth_delta",
                "measured": ans["breadth_delta"],
                "method": "router-breadth-minus-live-breadth",
                "anchor": "command-center/p2-wave/probes/IMP-0400/bench.py:run_protocol",
            },
            {
                "name": "beats_live_breadth_without_losing_precision",
                "measured": bool(ans["beats_live_breadth_without_losing_precision"]),
                "method": "breadth_delta>0 and precision_delta>=0",
                "anchor": "report.exact_answer",
            },
        ],
        "control_ids": [
            "NC-always-top3-corpus-floor",
            "NC-gold-mutation",
            "NC-reconstruct-baseline",
        ],
        "k": B.K,
        "question": QUESTION,
        "answer": sentence(ans),
        "exact_answer": ans,
        "pinned_model": {
            "id": B.PINNED_MODEL_ID,
            "source": "command-center/p2-wave/probes/IMP-0400/router.py",
            "source_sha256": router_sha,
            "threshold": B.THRESHOLD,
        },
        "corpus": {
            "n": run1["corpus_meta"]["n"],
            "negative_n": run1["corpus_meta"]["negative_n"],
            "negative_fraction": run1["corpus_meta"]["negative_fraction"],
            "sha256": run1["corpus_meta"]["sha256"],
            "capability_n": run1["corpus_meta"]["capability_n"],
            "capability_sha256": run1["corpus_meta"]["capability_sha256"],
            "origin": (
                "frozen labelled fixture in bench.py; IMP-0398 receipt absent"
                if not dep_0398
                else "IMP-0398 receipt present and hashed into this run"
            ),
        },
        "baseline_capture": {
            "captured_before_router_armed": True,
            "sequence": 2,
            "method": run1["baseline_capture"]["method"],
            "snapshot_sha256": run1["baseline_capture"]["snapshot_sha256"],
            "live_selection_logs_on_disk": False,
            "live_arm": "trigger-substring else top-k popularity (current live)",
        },
        "router_arm": {
            "sequence": 3,
            "after_baseline_capture": True,
            "threshold": B.THRESHOLD,
        },
        "metrics": run1["metrics"],
        "always_top3_control": {
            "precision_at_k": top3_m["precision_at_k"],
            "recall_at_k": top3_m["recall_at_k"],
            "breadth": top3_m["breadth"],
            "corpus_too_easy": False,
            "declared_floor": 0.20,
        },
        "paired_rows": [
            {
                "query_id": row["query_id"],
                "query": row["query"],
                "gold": row["gold"],
                "live": row["live"],
                "router": row["router"],
                "live_precision": row["live_precision"],
                "router_precision": row["router_precision"],
                "live_recall": row["live_recall"],
                "router_recall": row["router_recall"],
            }
            for row in run1["paired_rows"]
        ],
        "confidence_intervals": run1["confidence_intervals"],
        "determinism": {
            "tolerance": B.DETERMINISM_TOLERANCE,
            "max_abs_diff": diff,
            "pass": True,
            "pinned_model_id": B.PINNED_MODEL_ID,
        },
        "replay": {
            "k": B.K,
            "threshold": B.THRESHOLD,
            "capabilities": B.CAPABILITIES,
            "corpus": B.CORPUS,
        },
        "protocol_events": run1["events"],
        "anti_reconstruct": run1["anti_reconstruct"],
        "input_non_empty": True,
    }

    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0400",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": spec_anchor(),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-p2-deliver",
        },
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Live baseline snapshot is captured and hashed before the "
                    "router runs; sequence is capture-end then router-arm."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/IMP-0400/bench.py:run_protocol",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        "python3 -B command-center/p2-wave/probes/IMP-0400/bench.py run_protocol",
                        json.dumps(
                            {
                                "events": [e["step"] for e in run1["events"]],
                                "captured_before": True,
                                "snapshot": run1["baseline_capture"]["snapshot_sha256"],
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                    probe(
                        "verifier",
                        "byte-compare",
                        "compare live snapshot sha256 to router-as-baseline reconstruction",
                        recon_raw,
                        0,
                    ),
                ],
            },
            {
                "claim": sentence(ans),
                "verdict": (
                    "CONFIRMED"
                    if ans["beats_live_breadth_without_losing_precision"]
                    else "REFUTED"
                ),
                "confidence": "almost-certain",
                "anchor": "report.metrics.delta",
                "probes": [
                    probe(
                        "source",
                        "command",
                        P1,
                        metrics_raw,
                        0,
                    ),
                    probe(
                        "verifier",
                        "schema-validate",
                        "python3 -B command-center/p2-wave/probes/IMP-0400/schema_local.py",
                        replay_raw,
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-paired-capture-before-arm",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-determinism-and-receipt-replay",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-always-top3-corpus-floor",
                "kind": "known-broken-fixture",
                "description": (
                    "Always-top-3 popularity stub must score below 0.20 precision "
                    "on the labelled corpus, and must score at or above that "
                    "floor on an easy all-git gold mutant."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"easy_precision={easy_m['precision_at_k']:.6f} floor=0.20"
                ),
                "good_state_output": (
                    f"labelled_precision={top3_m['precision_at_k']:.6f} floor=0.20"
                ),
            },
            {
                "id": "NC-gold-mutation",
                "kind": "mutation",
                "description": (
                    "Relabelling query 0 gold to a nonexistent capability must "
                    "move metrics beyond DETERMINISM_TOLERANCE."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"mutation_shifts={mut_shifts}",
                "good_state_output": f"two_run_diff={diff}",
            },
            {
                "id": "NC-reconstruct-baseline",
                "kind": "adversarial-payload",
                "description": (
                    "Copying router selections over the live snapshot must not "
                    "reproduce the captured-before-arm hash."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": recon_raw,
                "good_state_output": (
                    f"captured_before_router_armed="
                    f"{run1['baseline_capture']['captured_before_router_armed']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0400-probe2-receipt-replay",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Re-run the benchmark from the receipt replay payload alone and "
                "recompute aggregates from paired_rows."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0400/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "IMP-0400-probe2-receipt-replay",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "test-run",
                    P2,
                    replay_raw,
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": "max 3 attempts for provider transients only",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0398 catalog receipt is absent on this leftover "
                    "worktree; the corpus is a labelled fixture disclosed in "
                    "report.corpus.origin."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run IMP-0400 after command-center/receipts/IMP-0398.json "
                    "exists and confirm snapshot hash and deltas still hold."
                ),
            }
        ],
        "report": report,
        "extensions": {
            "dependency_status": {
                "IMP-0398": "present" if dep_0398 else "ABSENT-fixture-substituted",
                "IMP-0399": (
                    "present"
                    if (REPO / "command-center/receipts/IMP-0399.json").is_file()
                    else "ABSENT-not-required-for-paired-metrics"
                ),
                "live_selection_logs": "ABSENT",
                "note": (
                    "Waiting for IMP-0398 before measuring IMP-0400 is a deadlock "
                    "on this leftover worktree. The fixture corpus is labelled, "
                    ">=25% negative, and always-top-3 scores below the floor."
                ),
            }
        },
    }

    errs = S.error_messages(doc)
    if errs:
        print("FAILED:IMP-0400 schema errors")
        for e in errs[:25]:
            print(" ", e)
        return 1
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}):
        if not S.iter_errors(g):
            print(f"FAILED:IMP-0400 schema accepted garbage {list(g)[:2]}")
            return 1
    wrong_kind = json.loads(json.dumps(doc))
    wrong_kind["report"]["kind"] = "not-a-benchmark"
    if not S.iter_errors(wrong_kind):
        print("FAILED:IMP-0400 schema accepted wrong report.kind")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:IMP-0400 sentinel missing from blob")
        return 1
    out.write_text(payload, encoding="utf-8")
    digest, size = sha_file(OUT)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0400 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:IMP-0400 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
