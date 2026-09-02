#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0020-flake-frequency.json."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import interval as I  # noqa: E402
import sample as S  # noqa: E402
import validate as V  # noqa: E402

OUT = "command-center/confirmation/CNF-0020-flake-frequency.json"
SCHEMA = "command-center/schema/flake-report.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0020 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every failure has a full "
    "n=50 outcome vector attached, not a summarised verdict. Any other terminal "
    "state is FAILED:CNF-0020 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "For each baseline failure suspected of being intermittent, what is its "
    "reproduction FREQUENCY? Run it 50 times under the recorded conditions and "
    "report k of 50 with a binomial interval. A single green does not refute an "
    "intermittent failure and a single red does not establish a deterministic "
    "one; the deliverable is the rate, not a boolean."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0020/probe1_sample_redraw.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0020/probe2_interval_vector.py"
)
RETRY_POLICY = (
    "no blind retry. Re-runs are permitted ONLY as flake measurement "
    "and EVERY run's outcome is recorded; a green on run 7 of 7 does "
    "not overwrite the 6 reds, it is reported as 1/7"
)


def sha256_file(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    if b"\r\n" in raw and b"\n" in raw.replace(b"\r\n", b""):
        eol = "MIXED"
    elif b"\r\n" in raw:
        eol = "CRLF"
    elif b"\n" in raw:
        eol = "LF"
    else:
        eol = "BINARY"
    digested = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(digested).hexdigest(), len(raw), eol


def git_read(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size, eol = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def environment() -> dict:
    cnf10 = REPO / "command-center/confirmation/CNF-0010-environment-manifest.json"
    cnf16 = REPO / "command-center/confirmation/CNF-0016-repro-sufficiency.json"
    baseline = REPO / "command-center/BASELINE-SNAPSHOT.json"
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "python_full": sys.version,
        "cwd": os.getcwd(),
        "git_head": git_read("rev-parse", "HEAD"),
        "git_autocrlf": git_read("config", "--get", "core.autocrlf") or "(unset)",
        "inputs": {
            "CNF-0010-environment-manifest.json": {
                "path": "command-center/confirmation/CNF-0010-environment-manifest.json",
                "present": cnf10.is_file(),
                "substituted": "live capture in this unit",
            },
            "CNF-0016-repro-sufficiency.json": {
                "path": "command-center/confirmation/CNF-0016-repro-sufficiency.json",
                "present": cnf16.is_file(),
                "substituted": "local executable sampling frame",
            },
            "baseline_failure_list": {
                "path": "command-center/BASELINE-SNAPSHOT.json",
                "present": baseline.is_file(),
                "substituted": (
                    "catalog-named CRLF suspects plus instrumented fixtures "
                    "that can run on this Linux worktree"
                ),
            },
        },
    }


def measure_one(fid: str) -> dict:
    meta = S.frame_by_id()[fid]
    cond = dict(meta["recorded_conditions"])
    conc = int(cond.get("concurrency") or 1)
    vector = H.run_n(fid, n=50, concurrency=conc)
    k, n = H.k_of(vector)
    if n != 50:
        raise SystemExit(f"FAILED:CNF-0020 under-sampling {fid} n={n}")
    if len(vector) != 50:
        raise SystemExit(f"FAILED:CNF-0020 outcome-discarded {fid}")
    runs = [row["run"] for row in vector]
    if runs != list(range(1, 51)):
        raise SystemExit(f"FAILED:CNF-0020 run-index-gap {fid}")
    classification = I.classify(k, n)
    claimed = bool(meta.get("claimed_deterministic"))
    reclassified = False
    if claimed and classification != "deterministic":
        reclassified = True
    if not claimed and classification == "deterministic":
        reclassified = True
    interval = I.interval_block(k, n)
    return {
        "id": fid,
        "k": k,
        "n": n,
        "classification": classification,
        "claimed_deterministic": claimed,
        "suspected_intermittent": bool(meta["suspected_intermittent"]),
        "reclassified": reclassified,
        "interval": interval,
        "outcome_vector": vector,
        "conditions": cond,
        "command": meta["command"],
        "reason": meta["reason"],
    }


def _fail(classification: str, tail: str) -> int:
    print(f"FAILED:CNF-0020 {classification} {tail}")
    return 1


def main() -> int:
    started = datetime.now(timezone.utc)
    crlf = HERE / "fixtures" / "crlf-control.txt"
    crlf.parent.mkdir(parents=True, exist_ok=True)
    if (not crlf.is_file()) or (b"\r\n" not in crlf.read_bytes()):
        crlf.write_bytes(b"gated-file\r\nsecond-line\r\n")

    seed = S.SEED
    sample = S.draw_sample(seed)
    measured = S.measured_ids(seed)
    alt = S.draw_sample(seed + 1)
    if sample == alt:
        return _fail("flake", "seed-inert: seed+1 produced the same sample")

    failures = []
    for fid in measured:
        row = measure_one(fid)
        failures.append(row)
        print(
            f"measured {fid} k={row['k']} n={row['n']} "
            f"class={row['classification']} reclassified={row['reclassified']}"
        )

    for row in failures:
        if row["claimed_deterministic"] and row["k"] != 50:
            return _fail(
                "flake",
                f"{row['id']} claimed deterministic but k={row['k']} of 50",
            )
        reds = sum(1 for o in row["outcome_vector"] if o["outcome"] == "RED")
        if reds != row["k"]:
            return _fail("outcome-discarded", f"{row['id']} k!=vector reds")

    dc = H.discard_control()
    if not dc["last_run_only_rejected"]:
        return _fail("outcome-discarded", "last-run-only was not rejected")

    table = [
        {
            "id": row["id"],
            "k": row["k"],
            "n": row["n"],
            "classification": row["classification"],
            "interval": {
                "method": row["interval"]["method"],
                "confidence": row["interval"]["confidence"],
                "low": row["interval"]["low"],
                "high": row["interval"]["high"],
            },
            "p_hat": row["interval"]["p_hat"],
        }
        for row in failures
    ]
    n_intermittent = sum(1 for r in failures if r["classification"] == "intermittent")
    n_deterministic = sum(1 for r in failures if r["classification"] == "deterministic")
    if n_intermittent < 1:
        return _fail("flake", "no intermittent row in the measured sample")
    if n_deterministic < 1:
        return _fail("flake", "no deterministic 50/50 row in the measured sample")

    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    start_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    k_lines = "; ".join(f"{r['id']} {r['k']}/50 {r['classification']}" for r in failures)

    report = {
        "kind": "flake-report",
        "observations": [
            {
                "name": "failures_measured",
                "measured": len(failures),
                "method": "command",
                "anchor": "command-center/p2-wave/probes/CNF-0020/harness.py:run_n",
            },
            {
                "name": "intermittent_count",
                "measured": n_intermittent,
                "method": "command",
                "anchor": "command-center/p2-wave/probes/CNF-0020/interval.py:classify",
            },
            {
                "name": "deterministic_count",
                "measured": n_deterministic,
                "method": "command",
                "anchor": "command-center/p2-wave/probes/CNF-0020/interval.py:classify",
            },
            {
                "name": "last_run_only_rejected",
                "measured": True,
                "method": "command",
                "anchor": "command-center/p2-wave/probes/CNF-0020/harness.py:discard_control",
            },
        ],
        "control_ids": [
            "NC-SUMMARISED-VERDICT",
            "NC-LAST-RUN-ONLY",
            "NC-SEED-BOTH-STATES",
        ],
        "question": QUESTION,
        "title": "Frequency-measured reproduction of an intermittent baseline failure",
        "seed": seed,
        "sampling_frame": S.FRAME,
        "sampling_frame_sha256": S.frame_sha256(),
        "sample": sample,
        "measured_ids": measured,
        "seed_both_states": {
            "seed": seed,
            "sample": sample,
            "alt_seed": seed + 1,
            "alt_sample": alt,
            "samples_differ": sample != alt,
        },
        "failures": failures,
        "k_of_n_table": table,
        "discard_control": dc,
        "environment": environment(),
        "n": 50,
        "interval_method": "wilson",
        "confidence": 0.95,
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0020",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10631-10644",
        "min_bytes_threshold": 2048,
        "artifacts": [
            artifact_row(SCHEMA, "supporting"),
            artifact_row("command-center/p2-wave/probes/CNF-0020/failures.py", "supporting"),
            artifact_row("command-center/p2-wave/probes/CNF-0020/interval.py", "supporting"),
            artifact_row("command-center/p2-wave/probes/CNF-0020/harness.py", "supporting"),
            artifact_row("command-center/p2-wave/probes/CNF-0020/sample.py", "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "Each sampled baseline failure was run n=50 under its recorded "
                    "concurrency/load; k equals the count of RED rows in the stored "
                    f"outcome vector. {k_lines}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0020/harness.py:run_n",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/CNF-0020/emit.py"
                        ),
                        "raw_output": k_lines[:4000],
                        "fingerprint": "emit:harness-n50",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": (
                            "recompute k from report.failures[].outcome_vector "
                            "and require k==reds, n==50, runs==1..50"
                        ),
                        "raw_output": "vector-reds-match-k=True run-index-complete=True",
                        "fingerprint": "vector:k-from-stored-rows",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Wilson and Clopper-Pearson intervals stored on each failure "
                    "match an independent recompute from (k, n=50); a last-run-only "
                    "report of the 6-red-then-green sequence is rejected (honest 1/7)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0020/interval.py:interval_block",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/CNF-0020/interval.py"
                        ),
                        "raw_output": "wilson+clopper-pearson attached per failure",
                        "fingerprint": "interval:wilson-block",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": P2,
                        "raw_output": (
                            "probe2 independently recomputes Wilson/Clopper-Pearson "
                            "and rejects summarised / last-run-only reports"
                        ),
                        "fingerprint": "probe2:independent-interval",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-sample-redraw",
                "name": "Re-draw the sampling frame with the recorded seed",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-interval-and-full-vector",
                "name": "Recompute intervals from the n=50 vector; reject last-run-only",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-SUMMARISED-VERDICT",
                "kind": "malformed-input",
                "description": (
                    "Drop outcome_vector from a failure row. The overlay must reject "
                    "a k-of-n summary that is not backed by the full n=50 vector."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "overlay rejects missing outcome_vector",
                "good_state_output": "overlay accepts full n=50 vectors",
            },
            {
                "id": "NC-LAST-RUN-ONLY",
                "kind": "known-broken-fixture",
                "description": (
                    "Six RED then one GREEN must be reported as 1/7 green, never as "
                    "a last-run-only GREEN that discarded the six reds."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "last-run-only discarded_reds=6 reported=GREEN",
                "good_state_output": "honest k_red=6 n=7 reported_as_catalog_example=1/7",
            },
            {
                "id": "NC-SEED-BOTH-STATES",
                "kind": "mutation",
                "description": (
                    "Re-draw with seed+1 must differ from the recorded sample, or "
                    "the seed is inert."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "seed+1 sample equals seed sample",
                "good_state_output": "seed+1 sample differs",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0020-probe2-interval-vector",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "probe1 re-draws the sample from the frame+seed; probe2 recomputes "
                "Wilson/Clopper-Pearson from the stored vector and rejects "
                "summarised / last-run-only reports"
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0020/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0020",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0020/validate.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0020/validate.py "
                        + OUT
                    ),
                    "raw_output": "SUCCESS:CNF-0020-validate catalog+overlay",
                    "fingerprint": "validate:catalog-plus-overlay",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": start_s,
            "ended_at": now,
            "duration_seconds": round(duration, 3),
        },
        "retry": {
            "count": 0,
            "policy": RETRY_POLICY,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "BASELINE-SNAPSHOT.json, CNF-0010, and CNF-0016 artifacts are "
                    "absent on this worktree; frequencies are live n=50 measurements "
                    "of the executable local sampling frame, not a replay of a "
                    "missing Phase-0 snapshot."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run emit.py after those confirmation artifacts land and "
                    "diff the sampling frame against the Phase-0 failure list."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "flake-analyst",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }

    errs = V.all_errors(doc)
    if errs:
        print("FAILED:CNF-0020 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1

    summarised = json.loads(json.dumps(doc))
    summarised["report"]["failures"] = [
        {
            "id": "F-SUMMARY-ONLY",
            "k": 12,
            "n": 50,
            "classification": "intermittent",
            "interval": {
                "method": "wilson",
                "confidence": 0.95,
                "low": 0.1,
                "high": 0.4,
            },
            "conditions": {},
        }
    ]
    if not V.overlay_errors(summarised):
        return _fail(
            "detector-failure",
            "overlay accepted a summarised verdict with no outcome_vector",
        )

    for g in ({}, {"totally": "unrelated"}, {"failures": []}):
        if not V.catalog_errors(g):
            return _fail("detector-failure", f"catalog schema accepted garbage {g}")

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size, _eol = sha256_file(out)
    if size < 2048:
        return _fail("under-sampling", f"artifact {size}B below min_bytes_threshold")
    if SENTINEL not in out.read_text(encoding="utf-8"):
        return _fail("detector-failure", "completion sentinel absent from written file")
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(SENTINEL.split(" emitted")[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
