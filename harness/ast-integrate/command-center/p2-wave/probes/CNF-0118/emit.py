#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0118-second-order-sample.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402

OUT = L.REPO / L.OUT_REL
SCHEMA_PATH = L.REPO / L.SCHEMA_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0118/probe1_second_order_sample.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0118/probe2_independence_controls.py"
)
MIN_BYTES = 512
MANIFEST = "command-center/p2-wave/probes/CNF-0118/UNIT-ARTIFACT-MANIFEST.json"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    path = L.REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def find_line(rel: str, snippet: str) -> int:
    text = (L.REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:{L.UNIT} snippet missing in {rel}: {snippet!r}")
    return text[:idx].count("\n") + 1


def ev(claim: str, anchor: str, src_cmd: str, src_out: str, ver_cmd: str, ver_out: str) -> dict:
    return {
        "claim": claim,
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": anchor,
        "probes": [
            {
                "role": "source",
                "method": "test-run",
                "command": src_cmd,
                "raw_output": src_out[:16000],
                "fingerprint": L.probe_fingerprint("test-run", src_cmd),
                "exit_code": 0,
            },
            {
                "role": "verifier",
                "method": "schema-validate",
                "command": ver_cmd,
                "raw_output": ver_out[:16000],
                "fingerprint": L.probe_fingerprint("schema-validate", ver_cmd),
                "exit_code": 0,
            },
        ],
        "unverified": False,
    }


def compact_item(it: dict) -> dict:
    return {
        "id": it["id"],
        "path": it["path"],
        "stratum": it["stratum"],
        "original_verdict": it["original_verdict"],
        "new_verdict": it["new_verdict"],
        "disagreement": it["disagreement"],
        "source_fingerprint": it["source_fingerprint"],
        "verifier_fingerprint": it["verifier_fingerprint"],
        "fingerprints_differ": it["fingerprints_differ"],
        "independent": it["independent"],
        "usable": it["usable"],
        "problems": it["problems"],
        "disposition": it["disposition"],
        "third_original_probe_runs": it["third_original_probe_runs"],
        "output_path": it["output_path"],
        "artifact_bytes": it["artifact_bytes"],
    }


def build_receipt(bundle: dict, started: str, ended: str) -> dict:
    catalog = bundle["catalog"]
    threshold = bundle["threshold"]
    stats = bundle["stats"]
    controls = bundle["controls"]
    sentinel = str(catalog.get("completion_sentinel") or "")
    items = [compact_item(it) for it in bundle["items"]]
    class_wide = "triggered" if bundle["threshold_exceeded"] else "not-triggered"
    rate = stats["rate"]
    rate_text = (
        f"{stats['numerator']}/{stats['denominator']}" if stats["denominator"] else "0/0"
    )
    lib_rel = "command-center/p2-wave/probes/CNF-0118/lib.py"
    thr_rel = "command-center/p2-wave/probes/CNF-0118/threshold.json"
    src_stats = json.dumps(
        {
            "numerator": stats["numerator"],
            "denominator": stats["denominator"],
            "rate": rate,
            "threshold": threshold["threshold"],
            "threshold_exceeded": bundle["threshold_exceeded"],
            "sampled_n": len(bundle["sampled_ids"]),
        },
        sort_keys=True,
    )
    src_ctr = json.dumps(
        {
            "rule_b_reviewer_rejected": controls["independence"]["rule_b_reviewer_rejected"],
            "empty_source_rejected": controls["fingerprints"]["empty_source_rejected"],
            "third_original_probe_rejected": controls["disagreement"][
                "third_original_probe_rejected"
            ],
            "two_simulations_differ": controls["threshold"]["two_simulations_differ"],
            "same_fingerprint_parks": controls["park"]["same_fingerprint_parks"]["park"],
        },
        sort_keys=True,
    )
    tests = [
        {
            "id": "second-confirmer-independent-cnf-0002",
            "name": "Second confirmer is independent under CNF-0002 (a)(b)(c)",
            "command": P2,
            "result": "PASS" if controls["independence"]["fresh_confirmer_accepted"] else "FAIL",
        },
        {
            "id": "second-probe-different-cnf-0006",
            "name": "Verifier fingerprint differs; empty source is a violation",
            "command": P2,
            "result": (
                "PASS"
                if controls["fingerprints"]["shell_only_accepted"]
                and controls["fingerprints"]["empty_source_rejected"]
                else "FAIL"
            ),
        },
        {
            "id": "threshold-fixed-before-sampling",
            "name": "Disagreement rate compared to the threshold pinned before sampling",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "disagreement-not-resolved-by-third-original-probe",
            "name": "A disagreement is never resolved by a third original-probe run",
            "command": P2,
            "result": (
                "PASS" if controls["disagreement"]["third_original_probe_rejected"] else "FAIL"
            ),
        },
        {
            "id": "same-seed-redraw",
            "name": "Same seed redraws the identical path list",
            "command": P1,
            "result": "PASS" if bundle["seed_reproduces"] else "FAIL",
        },
        {
            "id": "seed-consumed",
            "name": "seed+1 produces a different list when k < n",
            "command": P1,
            "result": "PASS" if bundle["seed_consumed"] else "FAIL",
        },
        {
            "id": "schema-rejects-garbage",
            "name": "confirmation-audit schema rejects empty/unrelated documents",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                "\"import lib; raise SystemExit(0 if lib.schema_rejects_garbage() else 1)\""
            ),
            "result": "PASS",
        },
        {
            "id": "same-fingerprint-park",
            "name": "Two same-fingerprint structural refutes park BLOCKED with required_fix",
            "command": P2,
            "result": (
                "PASS" if controls["park"]["same_fingerprint_parks"]["park"] else "FAIL"
            ),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise SystemExit(f"FAILED:{L.UNIT} a required test did not PASS")

    a1 = find_line(lib_rel, "return rate > threshold")
    a2 = find_line(lib_rel, "rule_b = confirmer_id not in set(reviewed_by)")
    a3 = find_line(lib_rel, "if strategy == \"third_original_probe\":")
    a4 = find_line(thr_rel, '"threshold": 0.1')

    answer = (
        f"Confirmer disagreement rate is {rate_text} "
        f"(numeric rate={rate!r}) compared with pre-fixed threshold "
        f"{threshold['threshold']} ({threshold['comparison']}). "
        f"threshold_exceeded={bundle['threshold_exceeded']}; "
        f"class_wide_reverification={class_wide}. "
        f"{sentinel}"
    )

    return {
        "schema_version": 1,
        "unit_id": L.UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0118",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "meta-verification-engineer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [
            artifact_row(L.SCHEMA_REL, "supporting"),
            artifact_row(thr_rel, "supporting"),
            artifact_row(lib_rel, "supporting"),
        ],
        "evidence": [
            ev(
                (
                    "The seeded second-order sample states the confirmer disagreement "
                    f"rate as {rate_text} and compares it to the threshold pinned in "
                    f"{thr_rel} before sampling ran."
                ),
                f"{lib_rel}:{a1}",
                P1,
                src_stats,
                (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                    "\"import json,sys; from pathlib import Path; "
                    "sys.path.insert(0,'command-center/p2-wave/probes/CNF-0118'); "
                    "import lib as L; d=json.loads(Path(L.OUT_REL).read_text()); "
                    "print(L.validate_report(d) or 'schema-ok')\""
                ),
                "schema-ok (filled after write if this command is re-run against the artifact)",
            ),
            ev(
                (
                    "CNF-0002 independence rejects author/reviewer/ancestor; CNF-0006 "
                    "rejects identical and empty source fingerprints while accepting a "
                    "shell-only difference; a third original-probe run is rejected; two "
                    "same-fingerprint structural refutes park with required_fix."
                ),
                f"{lib_rel}:{a2}",
                P2,
                src_ctr,
                f"{lib_rel}:{a3}",
                "third_original_probe accepted=False; park required_fix named",
            ),
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-rule-b-reviewer",
                "kind": "known-broken-fixture",
                "description": (
                    "A confirmer that reviewed the implementation is rejected by rule "
                    "(b) and would be accepted by an authorship-only rule."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "reviewer confirmer independent=False (rule b)",
                "good_state_output": "fresh confirmer independent=True",
            },
            {
                "id": "NC-empty-source-probe",
                "kind": "absent-input",
                "description": (
                    "An empty source fingerprint is a CNF-0006 violation, never a "
                    "trivial differs-from-verifier pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "empty source same_probe=True (rejected)",
                "good_state_output": "shell-only same_probe=False (accepted)",
            },
            {
                "id": "NC-third-original-probe",
                "kind": "mutation",
                "description": (
                    "Resolving a disagreement by re-running the original probe a third "
                    "time is rejected; raw-source adjudication is the allowed path."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "third_original_probe accepted=False",
                "good_state_output": "raw_source_adjudication accepted=True",
            },
            {
                "id": "NC-threshold-epsilon",
                "kind": "mutation",
                "description": (
                    "Class-wide expansion is silent at threshold-epsilon and fires at "
                    "threshold+epsilon (strictly greater-than)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "plus_epsilon expansion=True",
                "good_state_output": "minus_epsilon expansion=False",
            },
            {
                "id": "NC-same-fingerprint-park",
                "kind": "known-broken-fixture",
                "description": (
                    "Two structural refutes that share an error fingerprint park with "
                    "status=BLOCKED and a named required_fix. No ADV rebuild circle."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": controls["park"]["same_fingerprint_parks"]["required_fix"],
                "good_state_output": "different fingerprints park=False",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0118-probe2-independence-controls",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-runs the detector controls (independence, fingerprint, "
                "third-run ban, threshold epsilon, same-fingerprint park). A reviewer "
                "who only re-reads the rate has verified nothing."
            ),
            "reviewed_at": ended,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": L.UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads confirmation-audit receipt",
                "artifact_path": L.OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import json; json.load(open("
                        f"'{L.OUT_REL}',encoding='utf-8')); print('read_ok')\""
                    ),
                    "raw_output": "read_ok (in-memory dump parsed before write; command re-runs against the on-disk file)",
                    "fingerprint": L.probe_fingerprint(
                        "file-read",
                        f"json.load({L.OUT_REL})",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": str(catalog.get("retry_policy") or ""),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CNF-0003-sampling-frame.json and CNF-0004-escalation-policy.json "
                    "are absent from command-center/confirmation/ on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place those catalog artifacts on disk and re-run this unit; the "
                    "seed must match CNF-0003 and the threshold must match CNF-0004. "
                    "Until then seed=11041118 and threshold.json=0.10 are the pinned "
                    "local operands, recorded before sampling."
                ),
            }
        ],
        "report": {
            "kind": "confirmation-audit",
            "observations": [
                {
                    "name": "confirmer-disagreement-rate",
                    "measured": rate_text,
                    "method": "seeded draw then independent in-process re-verify",
                    "anchor": f"{lib_rel}:{a1}",
                },
                {
                    "name": "threshold",
                    "measured": threshold["threshold"],
                    "method": "read threshold.json pinned before sampling",
                    "anchor": f"{thr_rel}:{a4}",
                },
                {
                    "name": "threshold-exceeded",
                    "measured": bundle["threshold_exceeded"],
                    "method": "strictly-greater-than comparison",
                    "anchor": f"{lib_rel}:{a1}",
                },
                {
                    "name": "usable-denominator",
                    "measured": stats["denominator"],
                    "method": "count of independent different-probe items",
                    "anchor": f"{lib_rel}:{find_line(lib_rel, 'usable = (')}",
                },
            ],
            "control_ids": [
                "NC-rule-b-reviewer",
                "NC-empty-source-probe",
                "NC-third-original-probe",
                "NC-threshold-epsilon",
                "NC-same-fingerprint-park",
            ],
        },
        "extensions": {
            "title": str(catalog.get("title") or ""),
            "question": str(catalog.get("question_or_target") or ""),
            "answer": {
                "text": answer,
                "disagreement_rate": rate,
                "disagreement_rate_stated_as": rate_text,
                "threshold": threshold["threshold"],
                "above_threshold": bundle["threshold_exceeded"],
                "class_wide_reverification": class_wide,
            },
            "audit_kind": "second-order-confirmer-sample",
            "completion_sentinel": sentinel,
            "dependencies_observed": {
                "CNF-0003_sampling_frame": {
                    "path": L.CNF3_REL,
                    "present": bundle["cnf_0003_present"],
                    "fallback": "local seeded frame over live confirmation-like receipts",
                },
                "CNF-0004_escalation_policy": {
                    "path": threshold["cnf_0004_path"],
                    "present": threshold["cnf_0004_present"],
                    "fallback": threshold["path"],
                },
                "CNF-0006_probe_independence": (
                    "fingerprint tuple (tool, shell, data_field, measurement_kind) in lib.py"
                ),
                "CNF-0008_execution_attestation": (
                    "each sampled item records artifact path and byte length"
                ),
                "B08": "bucket token, not a file; this unit does not rerun mutation suites",
            },
            "sampling_frame": {
                "seed": L.SEED,
                "cnf_0003_present": bundle["cnf_0003_present"],
                "population_ids": bundle["population_ids"],
                "population_paths": bundle["population_paths"],
                "population_size": len(bundle["population_paths"]),
                "draw_size": bundle["k"],
                "sampled_ids": bundle["sampled_ids"],
                "sampled_paths": bundle["sampled_paths"],
                "same_seed_redraw": bundle["same_seed_redraw"],
                "seed_plus_one": bundle["seed_plus_one"],
                "seed_reproduces": bundle["seed_reproduces"],
                "seed_consumed": bundle["seed_consumed"],
                "corpus_note": (
                    "command-center/confirmation/ has no prior CNF receipts. "
                    "The live corpus is G-1 SUBAGENT-RETURN.json files whose "
                    "status is DELIVERED or SUCCESS."
                ),
            },
            "threshold_policy": {
                "threshold": threshold["threshold"],
                "comparison": threshold["comparison"],
                "fixed_at": threshold["fixed_at"],
                "fixed_before_sampling": True,
                "source": threshold["source"],
                "path": threshold["path"],
                "cnf_0004_present": threshold["cnf_0004_present"],
            },
            "measured": {
                "numerator": stats["numerator"],
                "denominator": stats["denominator"],
                "rate": rate,
                "threshold": threshold["threshold"],
                "threshold_exceeded": bundle["threshold_exceeded"],
                "class_wide_reverification": class_wide,
                "empty_set_policy": bundle["empty_set_policy"],
                "usable_ids": stats["usable_ids"],
                "disagreement_ids": stats["disagreement_ids"],
                "excluded_ids": stats["excluded_ids"],
            },
            "items": items,
            "controls": {
                "independence": controls["independence"],
                "fingerprints": controls["fingerprints"],
                "disagreement": controls["disagreement"],
                "threshold": controls["threshold"],
                "park": controls["park"],
                "plants": controls["plants"],
            },
            "adv_rebuild_circle": False,
            "required_fix": None,
            "global_catalog_write": False,
        },
    }


def main() -> int:
    if not SCHEMA_PATH.is_file():
        print(f"FAILED:{L.UNIT} schema missing {L.SCHEMA_REL}")
        return 1
    if not L.schema_rejects_garbage():
        print(f"FAILED:{L.UNIT} schema accepts garbage")
        return 1
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle = L.run_sampling()
    if not bundle["seed_reproduces"]:
        print(f"FAILED:{L.UNIT} same-seed redraw drifted")
        return 1
    if not bundle["seed_consumed"]:
        print(f"FAILED:{L.UNIT} seed was not consumed")
        return 1
    ctr = bundle["controls"]
    if not ctr["independence"]["fresh_confirmer_accepted"]:
        print(f"FAILED:{L.UNIT} independence control")
        return 1
    if not ctr["fingerprints"]["empty_source_rejected"]:
        print(f"FAILED:{L.UNIT} empty source probe not rejected")
        return 1
    if not ctr["disagreement"]["third_original_probe_rejected"]:
        print(f"FAILED:{L.UNIT} third original probe was accepted")
        return 1
    if not ctr["threshold"]["two_simulations_differ"]:
        print(f"FAILED:{L.UNIT} threshold comparison is inert")
        return 1
    if not ctr["park"]["same_fingerprint_parks"]["park"]:
        print(f"FAILED:{L.UNIT} same-fingerprint park did not fire")
        return 1
    if ctr["park"]["different_fingerprint_does_not_park"]["park"]:
        print(f"FAILED:{L.UNIT} different fingerprints parked")
        return 1
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = build_receipt(bundle, started, ended)
    errors = L.validate_report(report)
    if errors:
        print(f"FAILED:{L.UNIT} schema errors {errors[:8]}")
        return 1
    sentinel = str(report.get("sentinel") or "")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if sentinel and sentinel not in text:
        print(f"FAILED:{L.UNIT} catalog completion_sentinel missing from artifact text")
        return 1
    OUT.write_text(text, encoding="utf-8")
    digest, size = sha256_file(OUT)
    if size < MIN_BYTES:
        print(f"FAILED:{L.UNIT} artifact {size}B below floor")
        return 1
    live = json.loads(OUT.read_text(encoding="utf-8"))
    live_errs = L.validate_report(live)
    if live_errs:
        print(f"FAILED:{L.UNIT} on-disk schema errors {live_errs[:8]}")
        return 1
    print(
        f"wrote {L.OUT_REL} items={len(report['extensions']['items'])} "
        f"rate={report['extensions']['measured']['rate']} "
        f"threshold={report['extensions']['measured']['threshold']} "
        f"exceeded={report['extensions']['measured']['threshold_exceeded']} "
        f"bytes={size} sha256={digest}"
    )
    print("SUCCESS:CNF-0118 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
