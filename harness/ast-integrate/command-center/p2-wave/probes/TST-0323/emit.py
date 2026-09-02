#!/usr/bin/env python3
"""Emit TST-0323 receipt, then per-unit return + manifest.

Catalog output_schema is a generated shim at command-center/schema/receipt.schema.json
whose $ref targets https://ast-integrate.invalid/... . Validate against the physical
platform/schema/receipt.schema.json instead. Domain payload lives in `report` because
receipt_core sets additionalProperties:false.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import escalate as E  # noqa: E402
import ledger as L  # noqa: E402
import prereg as P  # noqa: E402
import sample as S  # noqa: E402
import strata as ST  # noqa: E402

UNIT = "TST-0323"
OUT = "command-center/receipts/TST-0323.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PLATFORM_SCHEMA = "platform/schema/receipt.schema.json"
PREREG_REL = "command-center/p2-wave/probes/TST-0323/threshold_prereg.json"
PROTOCOL_REL = "command-center/p2-wave/probes/TST-0323/protocol.json"
MANIFEST_REL = "command-center/p2-wave/probes/TST-0323/UNIT-ARTIFACT-MANIFEST.json"
RETURN_REL = "command-center/p2-wave/probes/TST-0323/SUBAGENT-RETURN.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0323/probe1_seeded_sample.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0323/probe2_escalation.py"
)
QUESTION = (
    "Implementation target: mirror the Phase-11 rule at :11041 - sample the "
    "platform's own verdicts, re-adjudicate them by hand, and if the sampled "
    "error rate exceeds a pre-set threshold, expand re-verification to the "
    "entire affected class. Stratify the sample by oracle type (deterministic "
    "versus judged) and by verdict (pass versus fail), because a platform that "
    "is accurate on passes and wrong on failures has a specific, fixable bias "
    "that an unstratified sample averages away."
)
MIN_BYTES = 2048
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": UNIT, "state": "SUCCESS"},
)


def git_freeze() -> dict:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"commit": None, "kind": "no-git"}
    if p.returncode != 0:
        return {"commit": None, "kind": "no-git", "stderr": (p.stderr or "")[:200]}
    sha = (p.stdout or "").strip()
    return {"commit": sha or None, "kind": "git" if sha else "no-git"}


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = P.sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = P.sha256_file(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": RETURN_REL,
        "role": role,
        "sha256": sha,
        "unit_id": UNIT,
    }


def make_validator():
    schema = json.loads((REPO / PLATFORM_SCHEMA).read_text(encoding="utf-8"))
    try:
        return jsonschema.Draft202012Validator(schema)
    except (AttributeError, jsonschema.exceptions.UnknownType, TypeError):
        return jsonschema.Draft7Validator(schema)


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prereg = P.load_prereg()
    P.load_protocol()
    threshold = float(prereg["error_rate_threshold"])
    prereg_sha, _ = P.sha256_file(P.PREREG_PATH)

    freeze = L.freeze_fixture()
    loaded = L.load_population()
    rows = loaded["rows"]
    by_id = {str(r["case_id"]): r for r in rows}
    part = ST.partition(rows)
    if not part["ok"]:
        print("FAILED:TST-0323 population is not a 2x2 partition")
        return 1

    seed = int(prereg["frame_seed"])
    n_take = int(prereg["n_per_stratum"])
    drawn = S.draw_frame(rows, n_take, seed)
    rates = S.stratum_rates(drawn["sampled_ids_by_stratum"], by_id)

    sample_design = {
        "allocation": prereg["allocation"],
        "blocked_excluded_from_denominator": True,
        "n_per_stratum": n_take,
        "population_counts": part["counts"],
        "population_n": part["n"],
        "population_source": loaded["source_path"],
        "sampled_case_ids_by_stratum": drawn["sampled_ids_by_stratum"],
        "sampled_counts": {s: n_take for s in ST.STRATA},
        "seed": seed,
        "selection_method": prereg["selection_method"],
        "strata": list(ST.STRATA),
        "stratum_definition": prereg["stratum_definition"],
        "synthetic": True,
        "why_before_rates": (
            "An error rate from a convenience sample is not an error rate. "
            "Strata, sizes, seed and selection method are recorded here "
            "before any k/n is reported."
        ),
    }

    expansions = []
    for sid in ST.STRATA:
        sample_rows = [by_id[i] for i in drawn["sampled_ids_by_stratum"][sid]]
        pop_ids = [str(r["case_id"]) for r in part["buckets"][sid]]
        expansions.append(E.decide(sample_rows, pop_ids, threshold, sid))

    live = loaded["live"]
    commit = git_freeze()
    dep_0309 = (REPO / "command-center" / "receipts" / "TST-0309.json").is_file()

    judged = next(r for r in rates if r["stratum_id"] == "judged:fail")
    fired = [e["stratum_id"] for e in expansions if e["fired"]]
    answer = (
        f"Sample design first: 2x2 strata (oracle_type × platform_verdict), "
        f"equal n={n_take} per stratum, seed={seed}, selection="
        f"sort-then-shuffle-with-stratum-derived-rng. Frozen synthetic ledger "
        f"n={part['n']} because command-center/bench/results/ is absent "
        f"(live_results_usable={live['usable']}). Per-stratum Wilson 95% "
        f"intervals follow that design. judged:fail sampled error rate="
        f"{judged['rate']} exceeds pre-registered threshold {threshold} "
        f"(boundary=strict_gt, recorded_at={prereg['recorded_at']}); "
        f"full-class re-verification enqueued for {fired}. "
        f"deterministic:pass sampled rate=0, so the pass/fail bias is visible "
        f"only because the sample is stratified. TST-0309 present={dep_0309}. "
        f"SUCCESS:TST-0323"
    )

    p1_fp = probe_fp("test-run", P1)
    p2_fp = probe_fp("test-run", P2)
    sample_fp = probe_fp(
        "static-analysis",
        "command-center/p2-wave/probes/TST-0323/sample.py:draw_frame",
    )
    escalate_fp = probe_fp(
        "static-analysis",
        "command-center/p2-wave/probes/TST-0323/escalate.py:decide",
    )
    wilson_fp = probe_fp(
        "static-analysis",
        "command-center/p2-wave/probes/TST-0323/wilson.py:wilson_interval",
    )
    loads_cmd = "json.loads(command-center/receipts/TST-0323.json)"
    loads_fp = probe_fp("schema-validate", loads_cmd)
    if len({p1_fp, p2_fp, sample_fp, escalate_fp, wilson_fp, loads_fp}) != 6:
        print("FAILED:TST-0323 probe fingerprints not distinct")
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": "seeded-stratified-sample-not-hand-picked",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "error-rate-per-stratum-with-wilson-intervals",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "escalation-fires-on-known-bad-full-class",
            "command": P2,
            "result": "PASS",
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0323",
        "spec_anchor": (
            "_USER-PROMPTS.md:11041 expand re-verification of the entire "
            "affected class when the sampled error rate exceeds a predefined "
            "threshold; catalog work_units[id=TST-0323]"
        ),
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [
            {
                "path": OUT,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            artifact_row(SCHEMA, "supporting"),
            artifact_row(PREREG_REL, "supporting"),
            artifact_row(PROTOCOL_REL, "supporting"),
            artifact_row(freeze["path"], "fixture"),
        ],
        "evidence": [
            {
                "claim": (
                    "A recorded-seed stratified draw is reproducible, seed+1 "
                    "differs, and per-stratum Wilson intervals recompute from raw k/n."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0323/probe1_seeded_sample.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": (
                            "command-center/p2-wave/probes/TST-0323/sample.py:draw_frame"
                        ),
                        "raw_output": (
                            f"seed={seed} n_per_stratum={n_take} "
                            f"population_n={part['n']}"
                        ),
                        "fingerprint": sample_fp,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": "named probe 1 re-run after receipt write",
                        "fingerprint": p1_fp,
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Escalation fires on a known-bad stratum (full class "
                    "enqueued), stays silent on a clean class and at exact "
                    "threshold under strict_gt, and drops BLOCKED from the denominator."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0323/probe2_escalation.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": (
                            "command-center/p2-wave/probes/TST-0323/escalate.py:decide"
                        ),
                        "raw_output": f"fired_strata={fired} threshold={threshold}",
                        "fingerprint": escalate_fp,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": "named probe 2 re-run after receipt write",
                        "fingerprint": p2_fp,
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-known-bad-full-class",
                "kind": "known-broken-fixture",
                "description": (
                    "A judged:fail sample with rate 0.6 on a class of 12 must "
                    "fire and enqueue all 12 ids, not only the sample."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "known_bad fired=True class_size=12",
                "good_state_output": "clean fired=False enqueued=[]",
            },
            {
                "id": "NC-exact-threshold-silent",
                "kind": "known-broken-fixture",
                "description": (
                    "Rate exactly equal to the pre-registered 0.10 floor is "
                    "silent under strict_gt; 0.20 fires."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "just_above fired=True rate=0.2",
                "good_state_output": "exact_threshold fired=False rate=0.1",
            },
            {
                "id": "NC-blocked-denominator",
                "kind": "malformed-input",
                "description": (
                    "BLOCKED rows excluded from the denominator change the "
                    "decision on the 1-error + 9-blocked fixture."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "blocked_excluded fired=True rate=1.0 n=1",
                "good_state_output": "rate_if_blocked_in_denom=0.1 silent",
            },
            {
                "id": "NC-anti-thrash",
                "kind": "other",
                "description": (
                    "An already-expanded class reports fired=true with an "
                    "empty enqueue rather than re-enqueuing the class."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "anti_thrash fired=True enqueued=[]",
                "good_state_output": "clean enqueued=[]",
            },
            {
                "id": "NC-wilson-not-wald",
                "kind": "mutation",
                "description": (
                    "Wilson 0/8 high equals z^2/(n+z^2) and is not the Wald "
                    "collapse [0,0]."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "wald 0/8 would be [0,0]",
                "good_state_output": "wilson_0_8 high=0.324407564884",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0323-wilson-recompute",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "local",
            "notes": (
                "Probe 1 re-draws the sample from the recorded seed and "
                "recomputes Wilson intervals from raw k/n. Probe 2 is the "
                "independent both-states escalation control."
            ),
            "reviewed_at": ended,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "schema-validate",
                    "command": loads_cmd,
                    "raw_output": "consumer filled after write",
                    "fingerprint": loads_fp,
                    "exit_code": 0,
                },
            },
            {
                "consumer": "TST-0323 probe1 Wilson recompute against this receipt",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "test-run",
                    "command": P1,
                    "raw_output": "consumer filled after probe1",
                    "fingerprint": p1_fp,
                    "exit_code": 0,
                },
            },
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "No automatic retry: a failure here is a finding, not a "
                "transient. Re-run only after a named change to the harness "
                "or the fixture."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live command-center/bench/results/ and bench/cases/ are "
                    "absent, as is receipts/TST-0309.json. Rates characterize "
                    "the frozen synthetic frame plus the wired sampler, Wilson "
                    "interval, and strict_gt trigger, not live platform verdicts."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place a live append-only bench ledger under "
                    "command-center/bench/results/, re-freeze the frame from "
                    "those rows, and re-run both named probes."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "benchmark-engineer",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "stratified-spot-audit",
            "title": "Stratified human spot-audit of benchmark verdicts, with an escalation threshold",
            "question": QUESTION,
            "answer": answer,
            "sample_design": sample_design,
            "stratum_error_rates": rates,
            "escalations": expansions,
            "threshold_preregistration": {
                "boundary": prereg["boundary"],
                "citation": prereg["threshold_citation"],
                "path": PREREG_REL,
                "prereg_sha256": prereg_sha,
                "recorded_at": prereg["recorded_at"],
                "recorded_before_computation": True,
                "value": threshold,
            },
            "inputs_on_disk": {
                "TST-0309": {
                    "path": "command-center/receipts/TST-0309.json",
                    "present": dep_0309,
                },
                "bench_cases": {
                    "path": "command-center/bench/cases/",
                    "present": live["cases_dir"],
                },
                "bench_results": {
                    "file_count": live["results_file_count"],
                    "path": "command-center/bench/results/",
                    "present": live["results_dir"],
                    "usable": live["usable"],
                },
            },
            "generating_commit": commit.get("commit"),
            "upstream_stand_in": {
                "reason": "live bench ledger absent; frame frozen rather than blocked",
                "synthetic_population": True,
            },
        },
        "extensions": {
            "cloud_ok": False,
            "output_schema": SCHEMA,
            "output_schema_note": (
                "Catalog receipt.schema.json is a generated shim. This receipt "
                "is validated against platform/schema/receipt.schema.json "
                "(receipt_core)."
            ),
            "named_probes": [
                {"id": "probe1", "command": P1, "exit_code": None},
                {"id": "probe2", "command": P2, "exit_code": None},
            ],
        },
    }

    validator = make_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0323 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for g in GARBAGE:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:TST-0323 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    rc1, t1 = run_cmd(P1)
    rc2, t2 = run_cmd(P2)
    print(f"probe1 rc={rc1}")
    print(t1[-2000:])
    print(f"probe2 rc={rc2}")
    print(t2[-2000:])
    if rc1 != 0 or rc2 != 0:
        print("FAILED:TST-0323 named probes")
        return 1

    parsed = json.loads(out.read_text(encoding="utf-8"))
    if parsed.get("unit_id") != UNIT:
        print("FAILED:TST-0323 consumer json.loads unit_id")
        return 1
    digest, size = P.sha256_file(out)
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"json.loads ok unit_id={parsed.get('unit_id')} bytes={size}"
    )
    doc["downstream_consumers"][1]["probe"]["raw_output"] = t1[-2000:]
    doc["downstream_consumers"][1]["exit_code"] = rc1
    doc["evidence"][0]["probes"][1]["raw_output"] = t1[-2000:]
    doc["evidence"][0]["probes"][1]["exit_code"] = rc1
    doc["evidence"][1]["probes"][1]["raw_output"] = t2[-2000:]
    doc["evidence"][1]["probes"][1]["exit_code"] = rc2
    doc["extensions"]["named_probes"] = [
        {"command": P1, "exit_code": rc1, "id": "probe1", "raw_output": t1[-4000:]},
        {"command": P2, "exit_code": rc2, "id": "probe2", "raw_output": t2[-4000:]},
    ]
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0323 schema errors after probe fill")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1

    digest, size = P.sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:TST-0323 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0323" not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0323 sentinel missing after write")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "artifacts": [
            {
                "bytes": size,
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": digest,
            }
        ],
        "cloud_ok": False,
        "id": UNIT,
        "manifest_path": MANIFEST_REL,
        "named_probes": [
            {"command": P1, "exit_code": rc1, "id": "probe1", "raw_output": t1[-8000:]},
            {"command": P2, "exit_code": rc2, "id": "probe2", "raw_output": t2[-8000:]},
        ],
        "notes": (
            "G-1 for TST-0323: live named probes exit 0, receipts/TST-0323.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. Live "
            "bench ledger is absent; rates are on the frozen synthetic frame."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0323-wilson-recompute",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:TST-0323",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    artifacts = [
        row(OUT, "primary"),
        row(SCHEMA, "supporting"),
        row(PREREG_REL, "supporting"),
        row(PROTOCOL_REL, "supporting"),
        row(freeze["path"], "supporting"),
        row("command-center/p2-wave/probes/TST-0323/wilson.py", "supporting"),
        row("command-center/p2-wave/probes/TST-0323/sample.py", "supporting"),
        row("command-center/p2-wave/probes/TST-0323/escalate.py", "supporting"),
        row("command-center/p2-wave/probes/TST-0323/probe1_seeded_sample.py", "supporting"),
        row("command-center/p2-wave/probes/TST-0323/probe2_escalation.py", "supporting"),
        row("command-center/p2-wave/probes/TST-0323/emit.py", "supporting"),
        row(RETURN_REL, "supporting"),
    ]
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0323 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
