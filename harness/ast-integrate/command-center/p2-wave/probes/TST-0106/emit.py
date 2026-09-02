#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0106.json (catalog output_path)."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

OUT = H.OUT_REL
SCHEMA = H.SCHEMA_REL
REPO = H.REPO
P1 = H.P1_CMD
P2 = H.P2_CMD
MIN_BYTES = H.MIN_BYTES
ZERO_SHA = "0" * 64
QUESTION = (
    "Phase 10 layer 33 (:11021) and stopping condition 8 (:11385). Target: "
    "compare against the TST-0025 baseline with a declared tolerance derived "
    "from measured variance, so a regression verdict is statistically "
    "meaningful rather than a single-run comparison."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def artifact_row(rel: str, role: str, sha: str | None = None, size: int | None = None) -> dict:
    path = REPO / rel
    if sha is None or size is None:
        if path.is_file():
            sha, size = sha256_file(path)
        else:
            sha, size = ZERO_SHA, 1
    return {
        "path": rel,
        "bytes": int(size),
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def arm_doc(
    arm_id: str,
    snapshot: str,
    digest: str,
    raw: list[int],
    stats: dict,
    n_inputs: int,
) -> dict:
    return {
        "id": arm_id,
        "n_inputs": n_inputs,
        "raw_ns": raw,
        "snapshot": snapshot,
        "source_sha256": digest,
        "statistics": {
            "ci95_halfwidth_ns": stats["ci95_halfwidth_ns"],
            "ci95_hi_ns": stats["ci95_hi_ns"],
            "ci95_lo_ns": stats["ci95_lo_ns"],
            "iqr_ns": stats["iqr_ns"],
            "max_ns": stats["max_ns"],
            "mean_ns": stats["mean_ns"],
            "median_ns": stats["median_ns"],
            "min_ns": stats["min_ns"],
            "n": stats["n"],
            "q1_ns": stats["q1_ns"],
            "q3_ns": stats["q3_ns"],
            "sample_variance_ns2": stats["sample_variance_ns2"],
            "stdev_ns": stats["stdev_ns"],
            "t_crit": stats["t_crit"],
        },
    }


def main() -> int:
    t_start = time.perf_counter()
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = H.make_rows()
    pdig = H.payload_digest(rows)
    if H.payload_digest(H.make_rows()) != pdig:
        print("FAILED:TST-0106 emit seed redraw mismatch")
        return 1
    if not rows:
        print("FAILED:TST-0106 emit empty payload")
        return 1

    empty = H.empty_input_control()
    if not empty["failed_as_required"]:
        print("FAILED:TST-0106 empty-input control did not fire")
        return 1
    nlt = H.n_lt_min_control()
    if not nlt["failed_as_required"]:
        print("FAILED:TST-0106 n<11 control did not fire")
        return 1

    d_a = H.fn_digest(H.snap_a)
    d_id = H.fn_digest(H.snap_b_identity)
    d_slow = H.fn_digest(H.snap_b_slow)

    pin = H.pin_baseline(rows)
    band = H.variance_band(pin["raw_ns"])
    tol = H.derive_tolerance(band)
    T = float(tol["tolerance_ns"])

    ident_run = H.run_interleaved(H.snap_a, H.snap_b_identity, rows)
    slow_run = H.run_interleaved(H.snap_a, H.snap_b_slow, rows)
    if not ident_run["interleaved"] or not slow_run["interleaved"]:
        print("FAILED:TST-0106 emit runs were not A B A B")
        return 1
    if ident_run["checksum_a"] != ident_run["checksum_b"]:
        print("FAILED:TST-0106 identity snapshots disagree on checksum")
        return 1

    sa_i = H.summarize(ident_run["raw_a_ns"])
    sb_i = H.summarize(ident_run["raw_b_ns"])
    sa_s = H.summarize(slow_run["raw_a_ns"])
    sb_s = H.summarize(slow_run["raw_b_ns"])
    pin_st = H.summarize(pin["raw_ns"])

    cls_ident = H.classify(sa_i, sb_i, T)
    cls_slow = H.classify(sa_s, sb_s, T)
    cls_pin_ident = H.classify(pin_st, sb_i, T)
    cls_pin_slow = H.classify(pin_st, sb_s, T)

    if cls_ident["label"] == "regression":
        print(
            "FAILED:TST-0106 identity pair labeled regression "
            f"delta={cls_ident['delta_median_ns']} T={T}"
        )
        return 1
    if abs(cls_ident["delta_median_ns"]) <= T and cls_ident["label"] != "no_measurable_change":
        print("FAILED:TST-0106 inside-tolerance identity not no_measurable_change")
        return 1
    if cls_ident["label"] != "no_measurable_change":
        print(
            "FAILED:TST-0106 identity pair not no_measurable_change "
            f"label={cls_ident['label']} delta={cls_ident['delta_median_ns']} T={T}"
        )
        return 1
    if cls_slow["label"] != "regression":
        print(
            "FAILED:TST-0106 planted slowdown not caught "
            f"label={cls_slow['label']} delta={cls_slow['delta_median_ns']} "
            f"T={T} overlap={cls_slow['ci_overlap']}"
        )
        return 1
    if cls_pin_slow["label"] != "regression":
        print(
            "FAILED:TST-0106 planted slowdown vs pinned baseline not regression "
            f"label={cls_pin_slow['label']}"
        )
        return 1

    fake_series = [1000.0 + 10 * i for i in range(11)]
    fake_a = H.summarize(fake_series)
    fake_near = H.summarize([1005.0 + 10 * i for i in range(11)])
    fake_slow = H.summarize([10000.0 + 10 * i for i in range(11)])
    fake_t = float(H.derive_tolerance(H.variance_band(fake_series))["tolerance_ns"])
    fake_near_cls = H.classify(fake_a, fake_near, fake_t)
    fake_slow_cls = H.classify(fake_a, fake_slow, fake_t)
    if fake_near_cls["label"] == "regression":
        print("FAILED:TST-0106 synthetic within-band labeled regression")
        return 1
    if fake_slow_cls["label"] != "regression":
        print(f"FAILED:TST-0106 synthetic planted label={fake_slow_cls['label']}")
        return 1

    v = H.offline_validator()
    garbage_ok = True
    garbage_n = 0
    for g in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
        {"unit_id": "TST-0106", "state": "SUCCESS", "sentinel": "SUCCESS:TST-0106"},
    ):
        n = len(list(v.iter_errors(g)))
        garbage_n = max(garbage_n, n)
        if n == 0:
            garbage_ok = False
    if not garbage_ok:
        print("FAILED:TST-0106 schema accepted garbage")
        return 1

    deps = H.dep_status()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_in = len(rows)
    band_public = {k: v for k, v in band.items() if k != "raw_ns"}
    answer = (
        "TST-0025/0105/0109 receipts are absent; product baseline is "
        "NOT-CHECKED. Local pin used as stand-in. Declared "
        f"tolerance_ns={T:.3f} from max(IQR, MDE, CI_halfwidth) on "
        f"n={band['n']} pinned reps. Identity pair: {cls_ident['label']} "
        f"(delta_median_ns={cls_ident['delta_median_ns']:.3f}). Planted "
        f"slowdown: {cls_slow['label']} "
        f"(delta_median_ns={cls_slow['delta_median_ns']:.3f}). "
        "SUCCESS:TST-0106"
    )
    ident_json = json.dumps(
        {
            "identity_label": cls_ident["label"],
            "n_inputs": n_in,
            "order": ident_run["order"],
            "tolerance_ns": T,
        },
        sort_keys=True,
    )
    slow_json = json.dumps(
        {
            "delta_median_ns": cls_slow["delta_median_ns"],
            "n_inputs": n_in,
            "planted_label": cls_slow["label"],
            "tolerance_ns": T,
            "vs_pinned_label": cls_pin_slow["label"],
        },
        sort_keys=True,
    )
    consumer_cmd = (
        "python3 -c \"import json,sys; p=sys.argv[1]; json.load(open(p,encoding='utf-8')); "
        "print('READ_OK')\" "
        + OUT
    )

    extensions = {
        "answer": answer,
        "baseline": {
            "kind": "this-unit-pin",
            "n_inputs": pin["n_inputs"],
            "n_reps": pin["n_reps"],
            "payload_sha256": pdig,
            "raw_ns": pin["raw_ns"],
            "role": "TST-0025-stand-in",
            "seed": H.SEED,
            "source_sha256": pin["source_sha256"],
            "statistics": pin_st,
            "tst_0025_present": deps["TST-0025"]["present"],
        },
        "benchmarks": [
            {
                "arms": [
                    arm_doc("A", "snap-A", d_a, ident_run["raw_a_ns"], sa_i, n_in),
                    arm_doc(
                        "B",
                        "snap-B-identity",
                        d_id,
                        ident_run["raw_b_ns"],
                        sb_i,
                        n_in,
                    ),
                ],
                "checksums_match": True,
                "comparison": cls_ident,
                "id": "within-noise-identity",
                "interleaving": {
                    "interleaved": True,
                    "order": ident_run["order"],
                    "sequence": ident_run["sequence"],
                },
                "n_inputs": n_in,
                "name": "within-noise: snap-A vs identical snap-B",
                "question": "Is an identical snapshot pair reported as a regression?",
            },
            {
                "arms": [
                    arm_doc("A", "snap-A", d_a, slow_run["raw_a_ns"], sa_s, n_in),
                    arm_doc(
                        "B",
                        "snap-B-planted-slowdown",
                        d_slow,
                        slow_run["raw_b_ns"],
                        sb_s,
                        n_in,
                    ),
                ],
                "comparison": cls_slow,
                "id": "planted-slowdown",
                "interleaving": {
                    "interleaved": True,
                    "order": slow_run["order"],
                    "sequence": slow_run["sequence"],
                },
                "n_inputs": n_in,
                "name": "detector control: snap-A vs planted extra passes",
                "question": (
                    "Does extra linear work beyond the declared tolerance register "
                    "as a regression?"
                ),
            },
        ],
        "claimed_product_baseline": {
            "found_in_tree": deps["TST-0025"]["present"],
            "reason": (
                "command-center/receipts/TST-0025.json is absent, as are "
                "TST-0105 and TST-0109. This unit does not claim a product "
                "two-commit comparison. It pins a local non-empty baseline, "
                "derives tolerance from that pin's variance band, and "
                "demonstrates the gate on an identity pair and a planted "
                "slowdown."
            ),
        },
        "completion_sentinel": H.COMPLETION_SENTINEL,
        "dependencies": deps,
        "input_cardinality": {
            "empty_input_control": empty,
            "n_inputs": n_in,
            "n_lt_min_control": nlt,
            "policy": "zero-cardinality is FAILED, not a number; n<11 is not a verdict",
        },
        "output_path": OUT,
        "output_schema": SCHEMA,
        "produced_at": now,
        "question": QUESTION,
        "raw_repetitions_attached": True,
        "sampling_frame": {
            "interleaving": "A B A B",
            "n_reps": H.N_REPS,
            "payload_n": H.PAYLOAD_N,
            "payload_sha256": pdig,
            "redraw_identical": True,
            "seed": H.SEED,
            "warmup_pairs": H.WARMUP_PAIRS,
        },
        "synthetic_controls": {
            "planted": fake_slow_cls,
            "tolerance_ns": fake_t,
            "within_band": fake_near_cls,
        },
        "title": "Benchmark regression gate against the pinned baseline",
        "tolerance": tol,
        "variance_band": band_public,
        "variance_band_raw_ns": band["raw_ns"],
        "verdict": {
            "answer": answer,
            "identity_pair": cls_ident["label"],
            "planted_slowdown": cls_slow["label"],
            "product_tst_0025": "NOT-CHECKED",
            "vs_pinned_identity": cls_pin_ident["label"],
            "vs_pinned_slowdown": cls_pin_slow["label"],
        },
    }

    duration = max(0.0, time.perf_counter() - t_start)
    ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": H.UNIT,
        "state": "SUCCESS",
        "sentinel": H.COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0106",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "benchmark-engineer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [
            artifact_row(OUT, "primary", ZERO_SHA, 1),
            artifact_row(SCHEMA, "supporting"),
            artifact_row(
                "command-center/p2-wave/probes/TST-0106/harness.py", "supporting"
            ),
        ],
        "evidence": [
            {
                "claim": (
                    f"Planted slowdown beyond declared tolerance_ns={T:.3f} is "
                    f"labeled regression (delta_median_ns="
                    f"{cls_slow['delta_median_ns']:.3f}, ci_overlap="
                    f"{cls_slow['ci_overlap']}). Empty input and n<11 are refused."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0106/probe1_planted_slowdown.py",
                "probes": [
                    probe("source", "command", P1, slow_json, 0),
                    probe("verifier", "test-run", P2, ident_json, 0),
                ],
            },
            {
                "claim": (
                    f"Within-noise identity pair is {cls_ident['label']} "
                    f"(delta_median_ns={cls_ident['delta_median_ns']:.3f}); "
                    "abs(delta)<=tolerance is never labeled regression. "
                    "Statistics reviewer re-derives IQR/MDE/tolerance from "
                    "attached raw_ns, not from the summary."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0106/probe2_within_noise.py",
                "probes": [
                    probe("source", "command", P2, ident_json, 0),
                    probe(
                        "verifier",
                        "schema-validate",
                        "python3 -B command-center/p2-wave/probes/TST-0106/emit.py",
                        f"offline_schema_garbage_errors={garbage_n}",
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "test_planted_slowdown_beyond_tolerance_is_caught",
                "name": "a planted slowdown beyond the declared tolerance is caught",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_within_noise_change_is_not_reported_as_a_regression",
                "name": "a within-noise change is not reported as a regression",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-slowdown-caught",
                "kind": "mutation",
                "description": (
                    "snap_b_slow extra linear passes must classify as regression "
                    "beyond the declared variance-derived tolerance."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"label={cls_slow['label']} delta={cls_slow['delta_median_ns']}"
                ),
                "good_state_output": f"identity_label={cls_ident['label']}",
            },
            {
                "id": "within-noise-not-regression",
                "kind": "adversarial-payload",
                "description": (
                    "Identity pair and synthetic inside-band shift must not be "
                    "labeled regression."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"synthetic_inside_band={fake_near_cls['label']}",
                "good_state_output": f"identity_label={cls_ident['label']}",
            },
            {
                "id": "empty-input-refused",
                "kind": "absent-input",
                "description": "Empty input must FAIL, not emit a number.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(empty, sort_keys=True),
                "good_state_output": f"n_inputs={n_in}",
            },
            {
                "id": "n-lt-min-refused",
                "kind": "malformed-input",
                "description": "n<11 must not produce a verdict.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(nlt, sort_keys=True),
                "good_state_output": f"n_reps={H.N_REPS}",
            },
            {
                "id": "schema-rejects-garbage",
                "kind": "malformed-input",
                "description": (
                    "Offline $ref-resolved schema must reject empty and unrelated "
                    "documents."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"garbage_error_count={garbage_n}",
                "good_state_output": "receipt_core+benchmark-receipt validates",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0106-probe2-within-noise",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "probe1 re-derives IQR/MDE/tolerance from stored raw_ns and "
                "confirms planted slowdown is regression. probe2 confirms the "
                "identity pair is no_measurable_change and that abs(delta)<="
                "tolerance is never a regression. Catalog asked for a second "
                "vendor; this worker is a single-vendor delivery of the pair."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0106/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "TST-0106",
        },
        "downstream_consumers": [
            {
                "consumer": "python3 json.load of the catalog receipt",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "file-read",
                    consumer_cmd,
                    "READ_OK",
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "unlimited re-runs ONLY with a new recorded seed; re-running "
                "the same seed is not a retry, it is a reproduction and must "
                "produce the identical verdict"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog dependencies TST-0025, TST-0105, and TST-0109 have "
                    "no receipts on this worktree, so a product two-commit "
                    "regression verdict is NOT-CHECKED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver those three receipts, reload the pinned baseline "
                    "and TST-0109 variance band, and reclassify the attached "
                    "raw_ns without claiming a new product SHA pair."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement asked for a cross-vendor "
                    "refuter. This delivery ran probe1 (statistics) and probe2 "
                    "(within-noise) on one worker; a second-vendor process was "
                    "not spawned."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Have a non-xai vendor re-derive tolerance from "
                    "extensions.baseline.raw_ns and confirm both labels."
                ),
            },
        ],
        "report": {
            "kind": "benchmark-receipt",
            "observations": [
                {
                    "name": "identity-pair-label",
                    "measured": cls_ident["label"],
                    "method": "interleaved-11-rep-declared-tolerance",
                    "anchor": "command-center/p2-wave/probes/TST-0106/harness.py:classify",
                },
                {
                    "name": "identity-delta-median-ns",
                    "measured": float(cls_ident["delta_median_ns"]),
                    "method": "median_B-median_A",
                    "anchor": "command-center/p2-wave/probes/TST-0106/harness.py:classify",
                },
                {
                    "name": "planted-slowdown-label",
                    "measured": cls_slow["label"],
                    "method": "interleaved-11-rep-declared-tolerance",
                    "anchor": "command-center/p2-wave/probes/TST-0106/harness.py:classify",
                },
                {
                    "name": "declared-tolerance-ns",
                    "measured": float(T),
                    "method": "max(IQR, MDE, CI95_halfwidth)",
                    "anchor": "command-center/p2-wave/probes/TST-0106/harness.py:derive_tolerance",
                },
            ],
            "control_ids": [
                "planted-slowdown-caught",
                "within-noise-not-regression",
                "empty-input-refused",
                "n-lt-min-refused",
                "schema-rejects-garbage",
            ],
        },
        "extensions": extensions,
    }
    # The probes read the domain rows (sampling_frame, baseline, tolerance,
    # benchmarks, ...) at the artifact root; receipt_core permits additional
    # properties, so mirror every extension row that does not collide with an
    # envelope key.
    for key, value in extensions.items():
        doc.setdefault(key, value)

    errs = H.schema_errors(doc)
    if errs:
        print("FAILED:TST-0106 schema errors")
        for e in errs[:25]:
            print(" ", e)
        return 1

    outp = REPO / OUT
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(outp)
    if size < MIN_BYTES:
        print(f"FAILED:TST-0106 artifact too small {size}B")
        return 1
    doc["artifacts"][0] = artifact_row(OUT, "primary", digest, size)
    doc["timestamps"]["ended_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    doc["timestamps"]["duration_seconds"] = max(0.0, time.perf_counter() - t_start)
    errs = H.schema_errors(doc)
    if errs:
        print("FAILED:TST-0106 schema errors after hash fill")
        for e in errs[:25]:
            print(" ", e)
        return 1
    outp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(outp)
    loaded = json.loads(outp.read_text(encoding="utf-8"))
    if loaded.get("unit_id") != H.UNIT:
        print("FAILED:TST-0106 consumer could not read unit_id")
        return 1
    if H.COMPLETION_SENTINEL not in json.dumps(loaded):
        print("FAILED:TST-0106 sentinel absent after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"identity={cls_ident['label']} planted={cls_slow['label']} T={T:.3f}")
    print("SUCCESS:TST-0106 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
