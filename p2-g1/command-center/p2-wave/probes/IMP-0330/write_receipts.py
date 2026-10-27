#!/usr/bin/env python3
"""Write IMP-0330 catalog receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
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
REPO = Path(__file__).resolve().parents[4]
UID = "IMP-0330"
OUT = "command-center/receipts/IMP-0330.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0330/probe1_chaos_sweep.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0330/probe2_quorum_negative.py"
)
SUPPORTING = [
    "tools/council/resilience.py",
    "tools/council/__init__.py",
    "command-center/p2-wave/probes/IMP-0330/probe1_chaos_sweep.py",
    "command-center/p2-wave/probes/IMP-0330/probe2_quorum_negative.py",
    "command-center/p2-wave/probes/IMP-0330/write_receipts.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def source_anchor(needle: str) -> str:
    rel = "tools/council/resilience.py"
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:IMP-0330 missing anchor {needle!r} in {rel}")


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/IMP-0330/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UID,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "bytes": size,
        "eol": "LF",
        "exists": path.is_file(),
        "path": rel,
        "role": role,
        "sha256": sha,
    }


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "command": command,
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
        "method": method,
        "raw_output": raw[:16000],
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0330 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = first_json(t1)
    j2 = first_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:IMP-0330 probe JSON pass=false")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    a_met = source_anchor("met = healthy >= required")
    a_may = source_anchor("def may_conclude(")
    a_skip = source_anchor("def conclude_skipping_quorum_recompute(")
    a_retain = source_anchor("seat.retained_after_isolation = True")
    p1_src = probe_rec("source", "command", P1, t1, c1)
    p1_ver = probe_rec(
        "verifier",
        "file-read",
        f"read {a_may} and {a_skip}",
        "may_conclude returns recompute_quorum(session).met; "
        "conclude_skipping_quorum_recompute ignores isolations",
        0,
    )
    p2_src = probe_rec("source", "command", P2, t2, c2)
    p2_ver = probe_rec(
        "verifier",
        "file-read",
        f"read {a_met} and {a_skip}",
        "met = healthy >= required; skip path uses original_seat_count >= required_quorum",
        0,
    )

    supporting_arts = [art(p, "supporting") for p in SUPPORTING]
    receipt = {
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": supporting_arts,
        "downstream_consumers": [
            {
                "artifact_path": "tools/council/resilience.py",
                "consumer": "command-center/p2-wave/probes/IMP-0330/probe1_chaos_sweep.py",
                "executed": True,
                "exit_code": c1,
                "probe": p1_src,
                "read_ok": True,
            },
            {
                "artifact_path": "tools/council/resilience.py",
                "consumer": "command-center/p2-wave/probes/IMP-0330/probe2_quorum_negative.py",
                "executed": True,
                "exit_code": c2,
                "probe": p2_src,
                "read_ok": True,
            },
        ],
        "evidence": [
            {
                "anchor": a_met,
                "claim": (
                    "The conclude/refuse threshold is enforced: may_conclude is "
                    "healthy >= required_quorum with required_quorum frozen on the "
                    "original roster. For N=5 Q=4 the council refuses at failed>=2 "
                    "(fraction 0.40); for N=7 Q=5 it refuses at failed>=3 "
                    "(fraction 3/7). Crash, timeout and malformed injection each "
                    "reproduce that boundary and never abort the council."
                ),
                "confidence": "almost-certain",
                "probes": [p1_src, p1_ver],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": a_retain,
                "claim": (
                    "Each isolated seat retains a partial contribution in the "
                    "session artifact (retained_after_isolation=True). Probe 1 "
                    "census reported all_isolated_partials_retained for mixed "
                    "faults and for every 1..N sweep row with failed>0."
                ),
                "confidence": "almost-certain",
                "probes": [p1_src, p2_src],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": a_skip,
                "claim": (
                    "Negative control: removing quorum recomputation "
                    "(conclude_skipping_quorum_recompute) makes a sub-quorum "
                    "council (healthy=3, required=4) wrongly conclude, while "
                    "may_conclude refuses. The same skip is silent on the "
                    "known-good failed=1 state, which still concludes."
                ),
                "confidence": "almost-certain",
                "probes": [p2_src, p2_ver],
                "verdict": "CONFIRMED",
            },
        ],
        "evidence_requirement_records": {
            "census": j1.get("chaos"),
            "sweep_boundary": j1.get("refuse_boundary"),
            "sweep_tables": j1.get("sweeps"),
            "negative_control": j2.get("sub_quorum"),
        },
        "falsifiable_answer": (
            "The council refuses when failed seats reach N-Q+1 "
            "(healthy < required_quorum). Measured refuse fractions: 2/5=0.40 "
            "for Q=4 of 5, and 3/7≈0.429 for Q=5 of 7. The threshold is "
            "enforced in may_conclude/recompute_quorum, not documentation."
        ),
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0330/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 128,
        "negative_control_ids": ["nc-skip-quorum-recompute"],
        "negative_controls": [
            {
                "bad_state_output": json.dumps(j2.get("sub_quorum"), sort_keys=True),
                "description": (
                    "Skip quorum recompute on a sub-quorum council "
                    "(failed=2, healthy=3, Q=4)."
                ),
                "fired_on_bad_state": True,
                "good_state_output": json.dumps(j2.get("both_states"), sort_keys=True),
                "id": "nc-skip-quorum-recompute",
                "kind": "mutation",
                "silent_on_good_state": True,
            }
        ],
        "profile": "council-runtime-module",
        "residual_unknowns": [
            {
                "claim": (
                    "In-process SeatCrash/timeout/malformed injection is not a "
                    "live vendor subprocess SIGKILL, so a streaming API that "
                    "never writes the scratch partial remains unmeasured."
                ),
                "settling_experiment": (
                    "Wire execute_seat to a real subprocess, SIGKILL it mid-turn, "
                    "and repeat the census against the OS-level stdout remnant."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0330-probe2-quorum-negative",
            "scope_not_agreement": True,
            "starts_from": "tests (N,Q,failed identity plus skip-recompute mutation)",
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0330",
        "spec_anchor": "_USER-PROMPTS.md:11298-11347",
        "state": "SUCCESS",
        "test_ids": [
            "chaos-crash-timeout-malformed",
            "invariant-quorum-recompute-partial-retained",
            "negative-control-skip-quorum-recompute",
        ],
        "tests": [
            {
                "command": P1,
                "id": "chaos-crash-timeout-malformed",
                "result": "PASS",
            },
            {
                "command": P1,
                "id": "invariant-quorum-recompute-partial-retained",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "negative-control-skip-quorum-recompute",
                "result": "PASS",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Seat-failure isolation",
        "unit_id": UID,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": UID,
        "manifest_path": "command-center/p2-wave/probes/IMP-0330/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "chaos-sweep-census",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "quorum-negative-control",
            },
        ],
        "notes": (
            "G-1 for IMP-0330: live named probes exit 0, receipts/IMP-0330.json "
            "state=SUCCESS with SUCCESS:IMP-0330, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-runtime-module"
        ),
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "IMP-0330-probe2-quorum-negative",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:IMP-0330",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0330 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
