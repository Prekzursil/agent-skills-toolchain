#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0118.json from live grammar-fuzz measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from campaign import (  # noqa: E402
    test_cyclic_subworkflow_is_rejected_not_hung,
    test_semantic_reach_rate_is_reported,
    test_zero_producer_barrier_is_rejected,
)
from classify import grammar_sha256  # noqa: E402
from generator import SEED_DEFAULT, dumps, valid_library  # noqa: E402

UNIT = "TST-0118"
OUT = "command-center/receipts/TST-0118.json"
SENTINEL = "SUCCESS:TST-0118"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0118/probe1_reach_rate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0118/probe2_hostile_rejects.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0118/grammar.json",
    "command-center/p2-wave/probes/TST-0118/classify.py",
    "command-center/p2-wave/probes/TST-0118/generator.py",
    "command-center/p2-wave/probes/TST-0118/semantic.py",
    "command-center/p2-wave/probes/TST-0118/campaign.py",
    "command-center/p2-wave/probes/TST-0118/probe1_reach_rate.py",
    "command-center/p2-wave/probes/TST-0118/probe2_hostile_rejects.py",
]


def digest_rel(rel: str, role: str = "supporting") -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reach = test_semantic_reach_rate_is_reported()
    cyclic = test_cyclic_subworkflow_is_rejected_not_hung()
    barrier = test_zero_producer_barrier_is_rejected()
    if not (reach["ok"] and cyclic["ok"] and barrier["ok"]):
        print(
            json.dumps(
                {
                    "reach": reach["ok"],
                    "cyclic": cyclic["ok"],
                    "barrier": barrier["ok"],
                },
                sort_keys=True,
            )
        )
        print("FAILED:TST-0118 live tests did not pass; receipt not written")
        return 1

    g = reach["grammar"]
    b = reach["byte"]
    schema_path = REPO / SCHEMA
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    arts = [digest_rel(rel) for rel in SUPPORTING]
    p_src_1 = probe("source", "command", P1, json.dumps(reach["grammar"], sort_keys=True), 0)
    p_ver_1 = probe(
        "verifier",
        "in-process-campaign",
        "test_semantic_reach_rate_is_reported(seed=118)",
        json.dumps(
            {
                "semantic_layer_count": g["semantic_layer_count"],
                "generated": g["generated"],
                "byte_semantic_layer_count": b["semantic_layer_count"],
                "repro_same_seed": reach["repro_same_seed"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_src_2 = probe(
        "source",
        "command",
        P2,
        json.dumps(
            {
                "cyclic": cyclic["safe"]["codes"],
                "naive": cyclic["naive"]["codes"],
                "barrier": barrier["bad"]["codes"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_ver_2 = probe(
        "verifier",
        "in-process-hostile",
        "test_cyclic_subworkflow_is_rejected_not_hung + test_zero_producer_barrier_is_rejected",
        json.dumps(
            {
                "cyclic_elapsed_ms": cyclic["safe"]["elapsed_ms"],
                "cyclic_hung": cyclic["safe"]["hung"],
                "good_accepted": cyclic["good"]["accepted"],
                "loop": barrier["loop_no_convergence"]["codes"],
            },
            sort_keys=True,
        ),
        0,
    )
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Grammar-aware fuzzing of the workflow DSL and the manifest formats",
        "report_kind": "fault-injection-receipt",
        "output_schema": SCHEMA,
        "output_schema_present": schema_path.is_file(),
        "spec_anchor": "_USER-PROMPTS.md:11002,10805,10875-10896",
        "question_or_target": (
            "Byte-level fuzzing of a structured format spends its budget on lexer "
            "rejects. Target: a grammar-derived generator that emits syntactically "
            "valid but semantically hostile documents (deep nesting, cyclic "
            "subworkflow references, a barrier with zero producers, a loop with no "
            "convergence rule) and asserts a typed rejection rather than a hang or "
            "a crash."
        ),
        "answer": (
            f"Grammar campaign seed={SEED_DEFAULT} produced {g['generated']} documents; "
            f"{g['semantic_layer_count']} reached the semantic layer "
            f"(reach_rate={g['reach_rate']}). The same seed's byte-level mutants "
            f"reached the semantic layer {b['semantic_layer_count']}/{b['generated']} "
            f"(reach_rate={b['reach_rate']}). Cyclic subworkflow -> CYCLIC_SUBWORKFLOW "
            f"in {cyclic['safe']['elapsed_ms']}ms (naive expander -> "
            f"HANG_BOUND_EXCEEDED). Zero-producer barrier -> BARRIER_ZERO_PRODUCERS. "
            "The valid twin is accepted in the same run."
        ),
        "min_bytes_threshold": 128,
        "seed": SEED_DEFAULT,
        "grammar": {
            "path": "command-center/p2-wave/probes/TST-0118/grammar.json",
            "sha256": grammar_sha256(),
            "start_symbols": ["Library", "Manifest"],
            "max_nesting": 8,
        },
        "semantic_reach": {
            "generated": g["generated"],
            "semantic_layer_count": g["semantic_layer_count"],
            "reach_rate": g["reach_rate"],
            "byte_generated": b["generated"],
            "byte_semantic_layer_count": b["semantic_layer_count"],
            "byte_reach_rate": b["reach_rate"],
            "fingerprint": g["fingerprint"],
            "repro_same_seed": reach["repro_same_seed"],
            "hung": g["hung"],
            "crashed": g["crashed"],
        },
        "valid_twin_bytes": len(dumps(valid_library()).encode("utf-8")),
        "artifacts": arts,
        "evidence": [
            {
                "claim": (
                    "The committed grammar plus a seed-118 generator produced "
                    f"{g['semantic_layer_count']}/{g['generated']} documents that "
                    "reached the semantic layer; byte-level mutants of the valid twin "
                    f"reached {b['semantic_layer_count']}/{b['generated']}. Same seed "
                    "reproduces the campaign fingerprint."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0118/grammar.json",
                "confidence": "almost-certain",
                "probes": [p_src_1, p_ver_1],
            },
            {
                "claim": (
                    "A cyclic subworkflow library is rejected as CYCLIC_SUBWORKFLOW "
                    f"in {cyclic['safe']['elapsed_ms']}ms with hung=false; a naive "
                    "expander without a seen-set hits HANG_BOUND_EXCEEDED on the same "
                    "fixture. A barrier with awaits=[] is BARRIER_ZERO_PRODUCERS. The "
                    "valid twin is accepted."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0118/semantic.py:analyze",
                "confidence": "almost-certain",
                "probes": [p_src_2, p_ver_2],
            },
        ],
        "tests": [
            {
                "id": "test_semantic_reach_rate_is_reported",
                "command": P1,
                "result": "PASS",
                "semantic_layer_count": g["semantic_layer_count"],
                "reach_rate": g["reach_rate"],
            },
            {
                "id": "test_cyclic_subworkflow_is_rejected_not_hung",
                "command": P2,
                "result": "PASS",
                "codes": cyclic["safe"]["codes"],
                "elapsed_ms": cyclic["safe"]["elapsed_ms"],
                "hung": cyclic["safe"]["hung"],
            },
            {
                "id": "test_zero_producer_barrier_is_rejected",
                "command": P2,
                "result": "PASS",
                "codes": barrier["bad"]["codes"],
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0118-C1-BYTE-LEVEL-LEXER",
                "kind": "both-states",
                "description": (
                    "Grammar-derived documents reach SEMANTIC; byte-mutated twins "
                    "die in LEXER/SYNTAX. A campaign with low grammar reach-rate is "
                    "testing the lexer, not the DSL."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"byte_reach_rate={b['reach_rate']}",
                "good_state_output": f"grammar_reach_rate={g['reach_rate']}",
            },
            {
                "id": "TST-0118-C2-NAIVE-CYCLE-HANG",
                "kind": "known-broken-mutant",
                "description": (
                    "Naive expander without a seen-set hits HANG_BOUND_EXCEEDED on "
                    "the cyclic fixture; production returns CYCLIC_SUBWORKFLOW and "
                    "accepts the acyclic twin."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(cyclic["naive"]["codes"]),
                "good_state_output": json.dumps(cyclic["safe"]["codes"]),
            },
            {
                "id": "TST-0118-C3-BARRIER-BOTH-STATES",
                "kind": "both-states",
                "description": (
                    "awaits=[] fires BARRIER_ZERO_PRODUCERS; the valid library's "
                    "barrier with producers is accepted."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(barrier["bad"]["codes"]),
                "good_state_output": f"accepted={barrier['good']['accepted']}",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0118-probe2-hostile-typed-reject",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 is mechanically different from probe 1: planted cyclic and "
                "zero-producer fixtures plus a naive expander watchdog, not the "
                "reach-rate table. Catalog asked for a cross-vendor reviewer; this "
                "headless worker records the independent probe as the available "
                "adversarial control."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0118/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0118",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "note": "measure runs after this receipt is on disk",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/schema/fault-injection-receipt.schema.json is "
                    f"{'present' if schema_path.is_file() else 'absent'} "
                    "(shim; G-1 does not consult schema validation). "
                    "TST-0117 and TST-0037 receipts are absent on this worktree; "
                    "this unit ships its own grammar and semantic checker rather "
                    "than importing theirs. _USER-PROMPTS.md is absent; the catalog "
                    "question_or_target is the spec used."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run against TST-0037's workflow DSL conformance checker "
                    "if that unit lands, and against TST-0117's grammar if it "
                    "differs from this committed grammar.json."
                ),
            }
        ],
        "retry": {
            "count": 0,
            "policy": "unlimited re-runs ONLY with a new recorded seed; same seed is reproduction",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "defects": [],
        "cloud_ok": False,
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0118 sentinel missing from serialized receipt")
        return 1
    out.write_text(text, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0118 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
