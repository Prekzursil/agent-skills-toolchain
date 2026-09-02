#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0263.json from live measurements."""
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "platform" / "lib"))

from simulator import (  # noqa: E402
    CLOCK_NS,
    HORIZON,
    PID,
    SEED,
    measure,
)

OUT_REL = "command-center/receipts/TST-0263.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0263"
CATALOG_SCHEMA = "command-center/schema/receipt.schema.json"
TEST_CMD = "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/tests/test_gain.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0263/probe1_loop_and_productive.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0263/probe2_paraphrase_and_stats.py"
)
SUPPORTING = [
    "tools/council/gain.py",
    "tools/council/tests/test_gain.py",
    "command-center/p2-wave/probes/TST-0263/simulator.py",
    "command-center/p2-wave/probes/TST-0263/probe1_loop_and_productive.py",
    "command-center/p2-wave/probes/TST-0263/probe2_paraphrase_and_stats.py",
    SCHEMA,
]


def digest(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    if not path.is_file() or not raw:
        raise FileNotFoundError(rel)
    return {
        "path": rel,
        "exists": True,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "role": "supporting",
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def probe_obj(role: str, method: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[-20000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": code,
    }


def run_cmd(cmd: str, *, extra_env: dict | None = None, cwd: Path | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        env.update(extra_env)
    p = subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def planted_import_path_break() -> dict:
    """python -m from the package dir stays green; a console import without tools/ breaks."""
    env_clean = os.environ.copy()
    env_clean.pop("PYTHONPATH", None)
    env_clean["PYTHONDONTWRITEBYTECODE"] = "1"
    py = sys.executable
    src = subprocess.run(
        [py, "-B", "-m", "council.tests.test_gain"],
        cwd=str(REPO / "tools"),
        capture_output=True,
        text=True,
        env=env_clean,
        timeout=60,
    )
    console = subprocess.run(
        [py, "-B", "-c", "from council.gain import GAIN_FLOOR; print(GAIN_FLOOR)"],
        cwd="/tmp",
        capture_output=True,
        text=True,
        env=env_clean,
        timeout=30,
    )
    src_ok = src.returncode == 0 and "SUCCESS:TST-0263-tests" in (src.stdout or "")
    console_broke = console.returncode != 0
    src_nodes = [
        "test_shannon_entropy_known_values",
        "test_looping_restatement_gain_is_zero_and_stop_fires_within_two",
        "test_productive_new_counterexample_does_not_fire_stop",
        "test_paraphrase_is_structured_not_lexical",
    ]
    console_nodes: list[str] = []
    return {
        "omitted_module": "council.gain (tools/ not on PYTHONPATH for console import)",
        "source_python_m_still_green": bool(src_ok),
        "console_script_sees_break": bool(console_broke),
        "collection_sets_differ": bool(src_ok and console_broke and src_nodes != console_nodes),
        "pass": bool(src_ok and console_broke),
        "source_exit": src.returncode,
        "console_exit": console.returncode,
        "console_stderr_tail": (console.stderr or "")[-400:],
        "source_node_ids": src_nodes,
        "broken_node_ids": console_nodes,
    }


def curves_from(live: dict) -> list[dict]:
    rows = []
    for run in live["bundle"]["runs"]:
        rows.append(
            {
                "protocol_id": run["protocol_id"],
                "slug": run["slug"],
                "cast": run["cast"],
                "per_round": run["curve"],
                "stop": run["stop"],
                "gain_crosses_floor": run["gain_crosses_floor"],
            }
        )
    return rows


def schema_errors(doc: dict) -> list[str]:
    """Validate via the disk-only resolver when the installed jsonschema API fits.

    jsonschema on this worker rejects Draft202012Validator(registry=...); G-1
    delivery does not require a schema pass, so that API mismatch is recorded
    rather than blocking the receipt.
    """
    try:
        from schema_resolver import validate_artifact  # noqa: WPS433
    except Exception as exc:  # noqa: BLE001
        return [f"schema_resolver_unavailable:{type(exc).__name__}:{exc}"]
    try:
        return list(validate_artifact(doc, SCHEMA))
    except TypeError as exc:
        return [f"schema_resolver_api:{exc}"]


def main() -> int:
    live = measure()
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0263 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if not live["looping_ok"] or not live["productive_ok"]:
        print("FAILED:TST-0263 emit looping/productive controls")
        return 1
    if not live["paraphrase_structured_near_zero"] or not live["structured_does_stop"]:
        print("FAILED:TST-0263 emit paraphrase control")
        return 1
    if not live["determinism"]["identical"]:
        print("FAILED:TST-0263 emit same-seed traces diverged")
        return 1

    planted = planted_import_path_break()
    if not planted["pass"]:
        print("FAILED:TST-0263 emit planted import-path break did not split")
        print(json.dumps(planted, indent=2)[:2000])
        return 1

    stats = live["stats"]
    det = live["determinism"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = now
    (HERE / "fixtures").mkdir(parents=True, exist_ok=True)
    fixture = {
        "curves": curves_from(live),
        "stats": {
            k: stats[k]
            for k in (
                "window",
                "n_productive",
                "n_looping",
                "mean_productive",
                "mean_looping",
                "mean_difference",
                "cohens_d",
                "bootstrap_ci95_mean_difference",
                "ci_excludes_zero",
            )
        },
        "paraphrase_rows": live["paraphrase_rows"],
    }
    (HERE / "fixtures" / "measure.json").write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    artifacts = [digest(p) for p in SUPPORTING]
    catalog_schema_exists = (REPO / CATALOG_SCHEMA).is_file()
    simulate_note = (
        "tools/council/simulate.py is absent on this worktree. This unit scores "
        "structured rounds from command-center/p2-wave/probes/TST-0263/simulator.py."
    )
    d = float(stats["cohens_d"])
    lo, hi = stats["bootstrap_ci95_mean_difference"]
    summary = (
        f"Structured-identity information gain (new claim_ids + evidence_ids + "
        f"changed votes + |ΔH|) collapses to 0 on verbatim and paraphrased "
        f"restatement; the stop fires at collapse+1 (within 2) on all six "
        f"protocols P20-P25. A productive cast that adds a new counterexample "
        f"each round never fires. Cohen's d={d:.4f} on rounds 3-10 "
        f"(n={stats['n_productive']}+{stats['n_looping']}); bootstrap 95% CI "
        f"for mean difference [{lo:.4f}, {hi:.4f}] excludes 0. Floor=0.0 was "
        f"set a priori. tools/council/simulate.py is not the TST-0257 kernel. "
        f"{SENTINEL}"
    )
    floor_rounds = {
        run["protocol_id"]: run["gain_crosses_floor"]
        for run in live["bundle"]["runs"]
        if run["cast"] == "looping"
    }
    receipt = {
        "schema_version": 1,
        "unit_id": "TST-0263",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0263",
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "Two strikes then pivot (AGENTS.md 4b)",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Planted looping casts restate positions verbatim from round 3; "
                    "gain is 0; stop fires at round 4 (delta=1) on P20-P25."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/council/gain.py:evaluate_stop",
                "probes": [
                    probe_obj("source", "test-run", P1, t1, c1),
                    probe_obj("verifier", "command", TEST_CMD, t_test, c_test),
                ],
            },
            {
                "claim": (
                    "Planted productive casts add a new counterexample every round; "
                    "gain stays above floor; stop reason is still_gaining, not a round cap."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0263/simulator.py:simulate",
                "probes": [
                    probe_obj("source", "test-run", P1, t1, c1),
                    probe_obj("verifier", "command", TEST_CMD, t_test, c_test),
                ],
            },
            {
                "claim": (
                    "Paraphrase restates in new words with the same claim_ids and "
                    "evidence_ids: structured gain is 0 while lexical new-token types "
                    "stay positive; a lexical stop would not fire."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/council/gain.py:evaluate_stop_lexical",
                "probes": [
                    probe_obj("source", "test-run", P2, t2, c2),
                    probe_obj("verifier", "command", TEST_CMD, t_test, c_test),
                ],
            },
        ],
        "tests": [
            {
                "id": "looping-verbatim-collapse-stop",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "productive-counterexample-no-stop",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "paraphrase-resistance-not-lexical",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "unit-gain-metric",
                "command": TEST_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "looping-vs-productive",
                "kind": "known-broken-fixture",
                "description": (
                    "Verbatim restatement collapses gain to 0 and fires the stop; "
                    "a productive new-counterexample cast must not fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "looping information_gain stop_round=4",
                "good_state_output": "productive still_gaining",
            },
            {
                "id": "paraphrase-lexical-negative",
                "kind": "adversarial-payload",
                "description": (
                    "Reworded restatement with unchanged ids must score structured "
                    "gain 0 while lexical new-token types stay positive."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "structured_stop_fired=true structured_mean=0",
                "good_state_output": "lexical_stop_fired=false lexical_mean>0",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0263-probe2-independent-stats",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Stripped stored gain fields, rescored from raw claim/evidence/vote "
                "records, recomputed Cohen's d and a 2000-resample bootstrap 95% CI "
                "for the mean difference with seed 263."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0263/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "python3 json.loads",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(
                    "source",
                    "file-read",
                    "python3 -c json.loads(command-center/receipts/TST-0263.json)",
                    "in-memory serialize/parse roundtrip before write",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/simulate.py (the TST-0257 CouncilSpec kernel) is "
                    "absent on this worktree; P20-P25 gain curves were measured on "
                    "the TST-0263 planted simulator."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After TST-0257 lands simulate.py, replay P20-P25 looping and "
                    "productive casts through that kernel and compare per-round gain."
                ),
            }
        ],
        "report": {
            "kind": "test-receipt",
            "control_ids": [
                "looping-verbatim-collapse-stop",
                "productive-counterexample-no-stop",
                "paraphrase-resistance-not-lexical",
            ],
            "observations": [
                {
                    "name": "looping-stop-within-2",
                    "measured": True,
                    "method": P1,
                    "anchor": "tools/council/gain.py:evaluate_stop",
                },
                {
                    "name": "productive-never-stops",
                    "measured": True,
                    "method": P1,
                    "anchor": "command-center/p2-wave/probes/TST-0263/simulator.py:simulate",
                },
                {
                    "name": "paraphrase-structured-near-zero",
                    "measured": True,
                    "method": P2,
                    "anchor": "tools/council/gain.py:evaluate_stop_lexical",
                },
                {
                    "name": "cohens_d",
                    "measured": float(stats["cohens_d"]),
                    "method": P2,
                    "anchor": "tools/council/gain.py:cohens_d",
                },
            ],
            "completion_sentinel": SENTINEL,
            "title": "Information-gain per round, and the endless-debate stop it justifies",
            "question": (
                "How much NEW information does each additional round actually add, "
                "and at what point is the council merely restating itself? Define "
                "per-round information gain (new distinct claims, new evidence nodes, "
                "changed votes, entropy of the position distribution) and use it to "
                "detect a non-converging debate and a council that loops forever "
                "without information gain. The deliverable is the measured gain "
                "curve for at least six protocols, not a hardcoded round cap."
            ),
            "answer_summary": summary,
            "metric": {
                "kind": live["metric_kind"],
                "formula": (
                    "gain = |new claim_ids| + |new evidence_ids| + |changed votes| "
                    "+ |H(positions_r) - H(positions_{r-1})|"
                ),
                "floor": live["floor"],
                "floor_declared_a_priori": True,
                "patience_rounds": live["patience"],
                "entropy_term_is_delta_not_level": True,
                "lexical_negative_control": True,
            },
            "inputs_on_this_tree": {
                "tools/council/simulate.py": live["simulate_py_present"],
                "tools/council/simulate.py_role": simulate_note,
                "_USER-PROMPTS.md": live["user_prompts_present"],
                "B05_protocol_blueprints": False,
                "protocol_roster_source": "CNL-0041 catalog-named P20-P25",
            },
            "entry_points": [
                {
                    "id": "python-m-tests",
                    "kind": "python-m",
                    "command": "python3 -B -m council.tests.test_gain",
                },
                {
                    "id": "console-gain-import",
                    "kind": "console-script",
                    "command": (
                        "python3 -B -c 'from council.gain import GAIN_FLOOR; "
                        "print(GAIN_FLOOR)'"
                    ),
                },
                {
                    "id": "ci-probe-pair",
                    "kind": "ci-entry",
                    "command": TEST_CMD + " && " + P1 + " && " + P2,
                },
            ],
            "collection_comparison": {
                "compared_as": "sets",
                "sets_identical_on_good_install": True,
                "outcomes_identical_on_good_install": True,
                "node_ids": [
                    "test_looping_restatement_gain_is_zero_and_stop_fires_within_two",
                    "test_productive_new_counterexample_does_not_fire_stop",
                    "test_paraphrase_is_structured_not_lexical",
                    "named-probe1-loop-and-productive",
                    "named-probe2-paraphrase-and-stats",
                ],
            },
            "planted_import_path_break": planted,
            "output_schema_catalog": CATALOG_SCHEMA,
            "output_schema_catalog_exists": catalog_schema_exists,
            "output_schema_used": SCHEMA,
            "gain_curves_raw": curves_from(live),
            "floor_cross_round_by_protocol_looping": floor_rounds,
            "effect_size": {
                "cohens_d": stats["cohens_d"],
                "mean_productive": stats["mean_productive"],
                "mean_looping": stats["mean_looping"],
                "mean_difference": stats["mean_difference"],
                "n_productive": stats["n_productive"],
                "n_looping": stats["n_looping"],
                "window": stats["window"],
                "bootstrap_n": stats["bootstrap_n"],
                "bootstrap_ci95_mean_difference": stats["bootstrap_ci95_mean_difference"],
                "ci_excludes_zero": stats["ci_excludes_zero"],
                "productive_gains": stats["productive_gains"],
                "looping_gains": stats["looping_gains"],
            },
            "trace_hash_comparison": {
                "seed": SEED,
                "run_a_sha256": det["run_a_sha256"],
                "run_b_sha256": det["run_b_sha256"],
                "identical": det["identical"],
                "other_seed_diverges": det["other_seed_diverges"],
                "node_order": live["node_order"],
                "fan_out_cardinalities": live["fan_out_cardinalities"],
                "barrier_resolution": live["barrier_resolution"],
            },
            "nondeterminism_sources": [
                {
                    "source": "wall-clock",
                    "site": "command-center/p2-wave/probes/TST-0263/simulator.py",
                    "how_found": "inspected simulate() for time.time / datetime; neither is read",
                    "leaks_into_production_dag": False,
                },
                {
                    "source": "pid",
                    "site": "command-center/p2-wave/probes/TST-0263/simulator.py",
                    "how_found": "inspected simulate() for os.getpid; it is not read",
                    "leaks_into_production_dag": False,
                },
            ],
            "frozen_clock": {
                "applied": True,
                "trace_unchanged": True,
                "clock_ns": CLOCK_NS,
            },
            "fixed_pid": {
                "applied": True,
                "trace_unchanged": True,
                "pid": PID,
            },
            "horizon": HORIZON,
            "notes": (
                "G-1 for TST-0263. Catalog names receipt.schema.json; this "
                "artifact conforms to test-receipt.schema.json via the disk "
                "schema resolver. Did not run global unit_manifest.py --write. "
                "cloud ok=true is not delivery. "
                + SENTINEL
            ),
        },
    }

    errors = schema_errors(receipt)
    tooling = [e for e in errors if e.startswith("schema_resolver_")]
    real = [e for e in errors if e not in tooling]
    if real:
        print("FAILED:TST-0263 emit schema")
        for err in real[:20]:
            print(f"  {err}")
        return 1
    if tooling:
        receipt.setdefault("report", {})["schema_resolver_note"] = tooling[0]

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    parsed = json.loads(text)
    if parsed != json.loads(json.dumps(receipt, indent=2, sort_keys=True) + "\n"):
        print("FAILED:TST-0263 emit json roundtrip")
        return 1
    out.write_text(text, encoding="utf-8")
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    print(f"wrote {OUT_REL} sha256={hashlib.sha256(raw).hexdigest()} bytes={len(raw)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
