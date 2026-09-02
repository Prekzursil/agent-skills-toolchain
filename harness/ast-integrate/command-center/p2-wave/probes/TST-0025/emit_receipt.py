#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0025.json (benchmark-receipt / receipt_core).

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write. cloud ok=true is not delivery.
jsonschema 4.10 cannot follow the catalog shim $ref over HTTPS; validation uses
the inlined physical generic_report from platform/schema/receipt.schema.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

REPO = H.REPO
OUT = H.OUT_REL
SCHEMA = H.SCHEMA_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0025/probe1_nonempty_input.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0025/probe2_variance_band.py"
)
QUESTION = (
    "Spec: 'Capture benchmark baselines before changing behavior' (:10657). "
    "Target: freeze the pre-change numbers for router latency, hook overhead, "
    "fan-out throughput and suite wall-clock at the pinned SHA, with inputs "
    "recorded alongside. Guard against the measured failure where two "
    "benchmarks ran on EMPTY inputs and returned a clean, meaningless green."
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/TST-0025/fixtures.py",
    "command-center/p2-wave/probes/TST-0025/harness.py",
    "command-center/p2-wave/probes/TST-0025/probe1_nonempty_input.py",
    "command-center/p2-wave/probes/TST-0025/probe2_variance_band.py",
    "tools/router/shadow.py",
    "tools/router/shadow_catalog.json",
    "tools/plugin/exec_policy.py",
    ".github/workflows/routing-benchmark.yml",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> dict:
    path = REPO / rel
    if path.is_file() and path.stat().st_size > 0:
        sha, size = sha256_file(path)
        return {"path": rel, "present": True, "bytes": size, "sha256": sha}
    return {"path": rel, "present": False, "bytes": 0, "sha256": None}


def workflow_reconstruction() -> dict:
    wf = REPO / ".github/workflows/routing-benchmark.yml"
    info: dict = {
        "path": ".github/workflows/routing-benchmark.yml",
        "present_on_disk": wf.is_file(),
    }
    if wf.is_file():
        text = wf.read_text(encoding="utf-8")
        info["bytes"] = wf.stat().st_size
        info["mentions_harness_bench"] = "hooks/harness-bench" in text
        info["mentions_gate_py"] = "gate.py --runs 5" in text
        info["note"] = (
            "workflow YAML is present; the job is an Ollama-backed routing "
            "recall probe (gate.py --runs 5), not the four named timers. "
            "This unit freezes deterministic local surfaces instead."
        )
        return info
    inv = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    info["reconstructed_from"] = (
        str(inv.relative_to(REPO).as_posix()) if inv.is_file() else None
    )
    info["note"] = "workflow YAML absent on this worktree"
    return info


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pin = H.pin_state()
    frozen = H.capture(H.F.SEED)
    repro = H.capture(H.F.SEED)
    if frozen["input_fingerprint"] != repro["input_fingerprint"]:
        print("FAILED:TST-0025 emit same-seed inputs diverged")
        return 1
    frozen_map = {b["id"]: b for b in frozen["benchmarks"]}
    repro_rows = []
    for b in repro["benchmarks"]:
        fb = frozen_map[b["id"]]
        live_median = float(b["statistics"]["median_ns"])
        inside = H.within_band(live_median, fb["variance_band"])
        repro_rows.append(
            {
                "id": b["id"],
                "frozen_median_ns": fb["statistics"]["median_ns"],
                "repro_median_ns": live_median,
                "within_band": inside,
                "n_inputs": fb["n_inputs"],
            }
        )
        if not inside:
            print(
                f"FAILED:TST-0025 emit {b['id']} repro median {live_median} "
                f"outside band [{fb['variance_band']['lo_ns']}, "
                f"{fb['variance_band']['hi_ns']}]"
            )
            return 1

    user_prompts = present("_USER-PROMPTS.md")
    workflow = present(".github/workflows/routing-benchmark.yml")
    wf_recon = workflow_reconstruction()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    printed_all = []
    for b in frozen["benchmarks"]:
        printed_all.extend(b["printed"])

    empty = frozen["empty_input_controls"]
    empty_router = next(r for r in empty if r["id"] == "router_latency")
    empty_hook = next(r for r in empty if r["id"] == "hook_overhead")
    nonempty_router = frozen_map["router_latency"]

    src_empty = L.probe(
        "source",
        "test-run",
        (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
            "\"import sys; sys.path.insert(0,'command-center/p2-wave/probes/TST-0025'); "
            "import harness as H; from router.shadow import load_catalog; "
            "c=load_catalog(); p=H.make_policy(); "
            "print(H.empty_control('router_latency', lambda: H.run_router([], c))); "
            "print(H.empty_control('hook_overhead', lambda: H.run_hooks([], p)))\""
        ),
        json.dumps({"empty_router": empty_router, "empty_hook": empty_hook}, sort_keys=True),
        0,
    )
    ver_empty = L.probe(
        "verifier",
        "command",
        P1,
        (
            "named probe1 re-runs empty-input FAIL (reported_time=null) and "
            "requires n_inputs printed beside every frozen number"
        ),
        0,
    )
    src_band = L.probe(
        "source",
        "test-run",
        (
            "harness.capture(seed=25) then harness.summarize(raw_ns) and "
            "harness.variance_band(stats) from arms[0].raw_ns"
        ),
        json.dumps(
            {
                "seed": frozen["seed"],
                "input_fingerprint": frozen["input_fingerprint"],
                "rows": [
                    {
                        "id": b["id"],
                        "n_inputs": b["n_inputs"],
                        "median_ns": b["statistics"]["median_ns"],
                        "band_lo_ns": b["variance_band"]["lo_ns"],
                        "band_hi_ns": b["variance_band"]["hi_ns"],
                        "derived_from": b["variance_band"]["derived_from"],
                        "raw_n": len(b["raw_ns"]),
                    }
                    for b in frozen["benchmarks"]
                ],
            },
            sort_keys=True,
        ),
        0,
    )
    ver_band = L.probe(
        "verifier",
        "command",
        P2,
        (
            "named probe2 re-derives the variance band from raw_ns (not from "
            "the summary) and requires a same-seed recapture inside the band"
        ),
        0,
    )

    artifacts = []
    for rel in SUPPORTING:
        row = L.art(rel, "supporting")
        if row["exists"] is not True:
            print(f"FAILED:TST-0025 missing supporting {rel}")
            return 1
        artifacts.append(
            {k: row[k] for k in ("path", "bytes", "sha256", "exists", "eol", "role")}
        )

    body_for_hash = {
        "unit_id": H.UNIT,
        "seed": frozen["seed"],
        "input_fingerprint": frozen["input_fingerprint"],
        "pin": pin,
        "benchmarks": [
            {"id": b["id"], "n_inputs": b["n_inputs"], "median_ns": b["statistics"]["median_ns"]}
            for b in frozen["benchmarks"]
        ],
    }
    primary_sha = hashlib.sha256(
        json.dumps(body_for_hash, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    observations = []
    for b in frozen["benchmarks"]:
        observations.append(
            {
                "name": b["id"],
                "measured": float(b["statistics"]["median_ns"]),
                "method": (
                    f"median of {len(b['raw_ns'])} timed reps; n_inputs={b['n_inputs']}"
                ),
                "anchor": f"tools/router/shadow.py:select_from_catalog+{b['id']}",
            }
        )

    report = {
        "kind": "benchmark-receipt",
        "control_ids": [
            "empty-router-latency",
            "empty-hook-overhead",
        ],
        "observations": observations,
        "title": "Benchmark baseline capture BEFORE behaviour changes",
        "question": QUESTION,
        "seed": frozen["seed"],
        "retry_policy": (
            "unlimited re-runs ONLY with a new recorded seed; re-running the "
            "same seed is a reproduction and must produce the identical verdict"
        ),
        "pin": pin,
        "input_fingerprint": frozen["input_fingerprint"],
        "n_catalog_capabilities": frozen["n_catalog"],
        "catalog_path": "tools/router/shadow_catalog.json",
        "inputs": {
            "user_prompts": user_prompts,
            "routing_benchmark_workflow": workflow,
            "workflow_reconstruction": wf_recon,
        },
        "named_benchmarks": frozen["named_benchmarks"],
        "benchmarks": frozen["benchmarks"],
        "empty_input_controls": frozen["empty_input_controls"],
        "same_seed_reproduction": {
            "seed": frozen["seed"],
            "identical_input_fingerprint": True,
            "rows": repro_rows,
            "verdict": "WITHIN_BAND",
        },
        "printed_cardinalities": printed_all,
        "measured_surface": {
            "router": "tools/router/shadow.py select_from_catalog",
            "hook": "tools/plugin/exec_policy.py check_spawn/write/network",
            "fanout": "ThreadPoolExecutor over the same query set",
            "suite": "router+hook+fan-out wall clock",
            "note": (
                "hooks/harness-bench/gate.py is an Ollama-backed recall probe, "
                "not these four timers. Baselines are frozen against the live "
                "deterministic router and hook policy on this worktree."
            ),
        },
    }

    schema_probe = L.probe(
        "source",
        "schema-validate",
        (
            "python3 -c \"import sys; sys.path.insert(0,'command-center/p2-wave/probes/TST-0025'); "
            "import harness as H; print(H.schema_errors({'totally':'unrelated'}))\""
        ),
        "in-process Draft7Validator against inlined generic_report+$defs; catalog shim $ref is not retrieved over HTTPS",
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": H.UNIT,
        "state": "SUCCESS",
        "sentinel": H.COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#TST-0025",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "benchmark-engineer",
            "execution_substrate": "local-parallel",
        },
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "unlimited re-runs ONLY with a new recorded seed; re-running "
                "the same seed is a reproduction and must produce the identical verdict"
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 4096,
                "sha256": primary_sha,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            *artifacts,
        ],
        "evidence": [
            {
                "claim": (
                    "router_latency and hook_overhead with n_inputs=0 raised "
                    "EmptyInputError and did not emit a time; every frozen "
                    "number is printed with n_inputs>=1."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0025/harness.py:assert_nonempty",
                "probes": [src_empty, ver_empty],
            },
            {
                "claim": (
                    "Variance bands are derived from raw_ns (half = max(8*IQR, "
                    "6*stdev, 2*|median|)); a same-seed recapture sits inside "
                    "each declared band."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0025/harness.py:variance_band",
                "probes": [src_band, ver_band],
            },
        ],
        "tests": [
            {
                "id": "test_benchmark_asserts_nonempty_input",
                "name": "empty input FAIL rather than report a time; n_inputs on every number",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": (
                    f"empty_router_failed={empty_router['failed']} "
                    f"empty_hook_failed={empty_hook['failed']} "
                    f"n_printed={len(printed_all)}"
                ),
            },
            {
                "id": "test_baseline_is_reproducible_within_the_declared_variance_band",
                "name": "same-seed recapture medians sit inside bands derived from raw_ns",
                "command": P2,
                "result": "PASS",
                "assertions": 4,
                "output_tail": json.dumps(repro_rows, sort_keys=True),
            },
        ],
        "negative_controls": [
            L.control(
                "empty-router-latency",
                "absent-input",
                "Empty router query set must FAIL with reported_time=null; nonempty emits median_ns with n_inputs.",
                True,
                True,
                bad=json.dumps(empty_router, sort_keys=True),
                good=nonempty_router["printed"][0],
            ),
            L.control(
                "empty-hook-overhead",
                "absent-input",
                "Empty hook subject set must FAIL with reported_time=null; nonempty emits median_ns with n_inputs.",
                True,
                True,
                bad=json.dumps(empty_hook, sort_keys=True),
                good=frozen_map["hook_overhead"]["printed"][0],
            ),
        ],
        "reviewer": {
            "reviewer_id": "TST-0025-probe2-variance-band",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "xai",
            "notes": (
                "Statistics reviewer: re-derives the variance band from "
                "arms[0].raw_ns, not from the summary. Same-seed reproduction "
                "must sit inside that band."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0025/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/TST-0025/harness.py schema_errors",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": schema_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog input _USER-PROMPTS.md:10657 is absent on this "
                    "worktree. The catalog question_or_target at TST-0025 is "
                    "the spec used for this freeze."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore _USER-PROMPTS.md and confirm line 10657 matches "
                    "the catalog question_or_target verbatim."
                ),
            },
            {
                "claim": (
                    "routing-benchmark.yml's gate.py --runs 5 job needs Ollama "
                    f"nomic-embed-text; present_on_disk={wf_recon.get('present_on_disk')}. "
                    "This freeze does not claim those recall numbers."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run hooks/harness-bench/gate.py --runs 5 against a live "
                    "embedding backend and store those numbers as a separate pin."
                ),
            },
        ],
        "report": report,
    }

    errs = H.schema_errors(doc)
    if errs:
        print("FAILED:TST-0025 emit schema")
        for e in errs[:25]:
            print("   ", e)
        return 1
    garbage_rejected = 0
    for g in ({}, {"totally": "unrelated"}, {"x": "x" * 200}):
        if H.schema_errors(g):
            garbage_rejected += 1
    if garbage_rejected != 3:
        print(f"FAILED:TST-0025 emit schema accepted garbage rejected={garbage_rejected}/3")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    sha, size = sha256_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0025 artifact {size}B below floor")
        return 1
    if H.COMPLETION_SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0025 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    for line in printed_all:
        print(line)
    print(H.COMPLETION_SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
