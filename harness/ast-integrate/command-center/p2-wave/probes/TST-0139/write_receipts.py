#!/usr/bin/env python3
"""Emit TST-0139 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
"""
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
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import http_storm_scheduler as S  # noqa: E402

UID = "TST-0139"
OUT = "command-center/receipts/TST-0139.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/scheduler_report"
IMPL = "tools/command-center/http_storm_scheduler.py"
SENTINEL = "SUCCESS:TST-0139"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0139/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0139/probe2_mislabel_control.py"
)
SUPPORTING = [
    IMPL,
    "command-center/p2-wave/probes/TST-0139/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0139/probe2_mislabel_control.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0139/SUBAGENT-RETURN.json",
        "role": role,
    }


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    norm = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(norm) if data else 0,
        "sha256": hashlib.sha256(norm).hexdigest() if data else "",
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def probe_blob(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
        "exit_code": exit_code,
    }


def main() -> int:
    both = S.both_states()
    detected = S.mislabel_is_detected()
    branches = S.classify_branches_are_distinct()
    if not both["pass"]:
        print("FAILED:TST-0139 both_states", json.dumps(both, sort_keys=True)[:2000])
        return 1
    if not detected["pass"]:
        print("FAILED:TST-0139 mislabel", json.dumps(detected, sort_keys=True)[:2000])
        return 1
    if not branches["pass"]:
        print("FAILED:TST-0139 classify branches", branches)
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0139 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    p1b = probe_blob("verifier", "command", P1, t1, c1)
    p2b = probe_blob("reviewer", "command", P2, t2, c2)
    src = probe_blob(
        "source",
        "in-process",
        "http_storm_scheduler.both_states + mislabel_is_detected",
        json.dumps(
            {
                "both_pass": both["pass"],
                "diverged": both["diverged"],
                "storm_429": both["storm_429"],
                "storm_529": both["storm_529"],
                "concurrency_529": {
                    k: both["concurrency_529"][k]
                    for k in (
                        "min_ceiling",
                        "max_inflight",
                        "ceiling_held",
                        "retry_count",
                        "siblings_continued",
                    )
                },
                "mislabel_pass": detected["pass"],
                "ast_branches": branches,
            },
            sort_keys=True,
        ),
        0,
    )

    s429 = both["storm_429"]
    s529 = both["storm_529"]
    c529 = both["concurrency_529"]
    question = (
        "Does the harness distinguish a 429 (our arrival rate) from a 529 / "
        "vendor-overload (their capacity) and apply different policies? PASS "
        "requires: 429 reduces our arrival rate; 529 does NOT reduce program "
        "concurrency and instead retries the affected unit while siblings continue."
    )
    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "429 and 529 are different policies, and 529 must not shrink concurrency",
        "question": question,
        "question_answer": (
            "YES: injected 429 halves-then-collapses wave-2 arrival rate "
            f"({s429['wave1_rate']:.4f}->{s429['wave2_rate']:.4f}); injected 529 "
            f"leaves rate {s529['wave1_rate']:.4f}->{s529['wave2_rate']:.4f}, holds "
            f"concurrency ceiling {c529['min_ceiling']}, retries "
            f"{c529['retry_count']} units, and siblings continue. Mislabelling "
            "529 as 429 is detected by rate drop plus independent ledger recount. "
            f"{SENTINEL}"
        ),
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0139 question_or_target; "
            "_USER-PROMPTS.md:10570-10583 (logical count vs simultaneous concurrency); "
            "_USER-PROMPTS.md:11008 (Phase 10 layer 20 rate-limit tests)"
        ),
        "output_schema": SCHEMA,
        "min_bytes_threshold": 128,
        "profile": "scheduler-report-429-vs-529",
        "report_kind": "scheduler_report",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "scheduler-tester",
            "execution_substrate": "local-serialized",
        },
        "implementation": {
            "module": IMPL,
            "entry_points": [
                "classify",
                "two_wave_storm",
                "event_storm",
                "both_states",
                "mislabel_is_detected",
            ],
            "policy_429": S.POLICY_429.as_dict(),
            "policy_529": S.POLICY_529.as_dict(),
            "logical_count_vs_simultaneous": (
                "event_storm logical_count is n_units; simultaneous ceiling is "
                "independent and is the only cap 529 is forbidden to shrink"
            ),
        },
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Signal (a): concurrency counter sampled during the injected "
                    f"529 storm. max_inflight={c529['max_inflight']}, "
                    f"min_ceiling={c529['min_ceiling']} (held), "
                    f"retry_count={c529['retry_count']}, "
                    f"siblings_continued={c529['siblings_continued']}. "
                    f"logical_count={c529['logical_count']} is not the "
                    f"simultaneous ceiling {c529['simultaneous_ceiling']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL}:event_storm",
                "confidence": "almost-certain",
                "probes": [src, p1b],
                "concurrency_529": c529,
            },
            {
                "claim": (
                    "Signal (b): per-unit classification in the ledger. Wave-1 "
                    "first attempts under 529 classify as vendor-overload; under "
                    "429 as arrival-rate. Independent reviewer table in probe 2 "
                    "agrees on live 529 and disagrees on the 529-as-429 mutant."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL}:two_wave_storm ledger",
                "confidence": "almost-certain",
                "probes": [src, p2b],
                "live_review": detected["live_review"],
                "mutant_review": detected["mutant_review"],
            },
        ],
        "tests": [
            {
                "id": "TST-0139-T1-both-states",
                "name": (
                    "injected 429 storm MUST reduce arrival rate; injected 529 "
                    "storm must not — a harness that behaves identically for both fails"
                ),
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
                "output_tail": t1[-4000:],
            },
            {
                "id": "TST-0139-T2-mislabel-negative-control",
                "name": "mislabelling 529 as 429 must be detectable by this test",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
                "output_tail": t2[-4000:],
            },
        ],
        "negative_controls": [
            {
                "id": "TST0139-C1-identical-throttle",
                "kind": "known-broken-mutant",
                "description": (
                    "classify_identical_throttle maps both 429 and 529 onto the "
                    "429 policy. both_states requires that mutant to reduce rate "
                    "in BOTH storms, proving the meter is not silent."
                ),
                "fired_on_bad_state": both["identical_mutant_collapses"],
                "silent_on_good_state": both["diverged"],
            },
            {
                "id": "TST0139-C2-mislabel-529-as-429",
                "kind": "known-broken-mutant",
                "description": (
                    "classify_mislabel_529_as_429 returns the 429 policy for 529. "
                    "Wave-2 arrival rate drops and the independent ledger recount "
                    "disagrees. Live classify() stays silent on 529."
                ),
                "fired_on_bad_state": detected["mutant_rate_reduced"],
                "silent_on_good_state": not detected["live_rate_reduced"],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0139-probe2-mislabel-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "control_executed": True,
            "note": (
                "Probe 2 does not reuse the wave-rate both-states assertions. "
                "It reclassifies ledger rows from HTTP status with a local table, "
                "runs the 529-as-429 mutant, and AST-scans classify() for "
                "separate Eq branches."
            ),
        },
        "retry": {
            "count": 0,
            "policy": (
                "up to 3 attempts with full-jitter backoff; a flake rate above "
                "1-in-20 reruns is filed as a DEFECT against the test, never "
                "absorbed as a retry. This run used an injected clock (0 flakes)."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0139/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": P1,
                "artifact_path": IMPL,
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": p1b,
            },
            {
                "consumer": P2,
                "artifact_path": IMPL,
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
                "probe": p2b,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "No B07 dispatcher module existed on this worktree (bucket "
                    "B07 is a catalog token, not a unit id). The live policy "
                    "under test is tools/command-center/http_storm_scheduler.py, "
                    "the sibling of retry_engine.py. A later dispatcher must call "
                    "classify() rather than grepping error text. "
                    "tools/command-center/measure_rate.py measures register-gate "
                    "fire rate, not HTTP arrival, and was not used as the meter."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "When IMP-0220 / IMP-0427 land a dispatcher, re-run "
                    "two_wave_storm against that admission loop and confirm "
                    "429 still reduces first-attempt gap while 529 does not "
                    "lower the concurrency ceiling."
                ),
            }
        ],
        "report": {
            "kind": "scheduler_report",
            "target_verdict": "PASS",
            "storm_429_rate_reduced": s429["rate_reduced"],
            "storm_529_rate_reduced": s529["rate_reduced"],
            "storm_529_concurrency_held": c529["ceiling_held"],
            "mislabel_detected": detected["pass"],
            "ast_distinct_branches": branches["pass"],
            "observations": [
                {
                    "name": "storm_429_wave2_arrival_rate",
                    "measured": float(s429["wave2_rate"]),
                    "method": "two_wave_storm first-attempt interarrival 1/mean_gap",
                    "anchor": f"{IMPL}:two_wave_storm",
                },
                {
                    "name": "storm_529_wave2_arrival_rate",
                    "measured": float(s529["wave2_rate"]),
                    "method": "two_wave_storm first-attempt interarrival 1/mean_gap",
                    "anchor": f"{IMPL}:two_wave_storm",
                },
                {
                    "name": "storm_529_concurrency_ceiling_held",
                    "measured": bool(c529["ceiling_held"]),
                    "method": "event_storm sampled inflight vs simultaneous ceiling",
                    "anchor": f"{IMPL}:event_storm",
                },
                {
                    "name": "mislabel_529_as_429_detected",
                    "measured": bool(detected["pass"]),
                    "method": "rate drop plus independent ledger recount",
                    "anchor": (
                        "command-center/p2-wave/probes/TST-0139/"
                        "probe2_mislabel_control.py"
                    ),
                },
            ],
            "control_ids": [
                "TST0139-C1-identical-throttle",
                "TST0139-C2-mislabel-529-as-429",
            ],
        },
        "notes": (
            "G-1 for TST-0139: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. "
            f"{SENTINEL}"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:TST-0139 sentinel missing from emitted body")
        return 1
    out.write_text(body, encoding="utf-8")

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-states-429-vs-529",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "mislabel-529-as-429-and-ledger-recount",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0139/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0139-probe2-mislabel-control",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0139: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0139 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
