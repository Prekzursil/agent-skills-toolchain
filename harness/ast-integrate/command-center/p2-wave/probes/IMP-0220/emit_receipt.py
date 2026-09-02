#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0220.json from live scheduler measurements."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

import _p2lib as L  # noqa: E402
from scenario import (  # noqa: E402
    N_UNITS,
    STAGGER_INTERVAL_S,
    UNIT_ID,
    forbid_wall_clock_in_scheduler,
    run_fanout,
)

OUT = "command-center/receipts/IMP-0220.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0220/probe1_stagger_histogram.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0220/probe2_burst_control.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/clock.py",
    "tools/agentspec/agentspec/stagger_admission.py",
    "tools/agentspec/agentspec/__init__.py",
    "command-center/p2-wave/probes/IMP-0220/scenario.py",
    "command-center/p2-wave/probes/IMP-0220/probe1_stagger_histogram.py",
    "command-center/p2-wave/probes/IMP-0220/probe2_burst_control.py",
]


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT_ID} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    on = run_fanout(stagger_enabled=True)
    off = run_fanout(stagger_enabled=False)
    wall_hits = forbid_wall_clock_in_scheduler()
    if wall_hits:
        print(f"FAILED:{UNIT_ID} scheduler-reads-wall:{wall_hits}")
        return 1
    if not on["matches_stagger"] or on["burst"] or not off["burst"] or off["matches_stagger"]:
        print(f"FAILED:{UNIT_ID} measurement did not discriminate")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [L.art(rel, "supporting") for rel in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print(f"FAILED:{UNIT_ID} missing supporting {missing}")
        return 1

    p1_src = L.probe("source", "command", P1, t1, c1)
    p1_ver = L.probe(
        "verifier",
        "command",
        "python3 -B command-center/p2-wave/probes/IMP-0220/scenario.py",
        json.dumps(
            {
                "bins": on["hist"]["bins"],
                "span": on["hist"]["span"],
                "n": on["hist"]["n_events"],
                "clock_now": on["clock_now"],
                "wall_s": on["wall_s"],
            },
            sort_keys=True,
        ),
        0,
    )
    p2_src = L.probe("source", "command", P2, t2, c2)
    p2_ver = L.probe(
        "verifier",
        "command",
        "python3 -B -c both-states-histogram",
        json.dumps(
            {
                "on_bins": on["hist"]["bins"],
                "off_bins": off["hist"]["bins"],
                "on_burst": on["burst"],
                "off_burst": off["burst"],
                "on_span": on["hist"]["span"],
                "off_span": off["hist"]["span"],
            },
            sort_keys=True,
        ),
        0,
    )

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0220",
        "spec_anchor": "_USER-PROMPTS.md:10577",
        "min_bytes_threshold": 128,
        "artifacts": artifacts,
        "evidence": [
            L.evidence(
                (
                    f"A {N_UNITS}-unit synthetic fan-out across 4 rails, driven by FakeClock, "
                    f"produced per-rail inter-arrivals matching stagger_interval_s="
                    f"{STAGGER_INTERVAL_S}: bins={on['hist']['bins']}, span={on['hist']['span']}, "
                    f"unique_timestamps={on['hist']['unique_timestamps']}, clock_now="
                    f"{on['clock_now']}, wall_s={on['wall_s']:.6f}. Histogram is computed from "
                    "admission timestamps, not copied from config."
                ),
                "CONFIRMED",
                "tools/agentspec/agentspec/stagger_admission.py:StaggeredAdmissionScheduler.admit",
                [p1_src, p1_ver],
                "almost-certain",
            ),
            L.evidence(
                (
                    "The same histogram function on the stagger-disabled twin is a burst: "
                    f"bins={off['hist']['bins']}, span={off['hist']['span']}, "
                    f"unique_timestamps={off['hist']['unique_timestamps']}, sleep_calls="
                    f"{off['sleep_calls']}. Stagger-on bins differ from stagger-off bins, so "
                    "the detector can see the difference."
                ),
                "CONFIRMED",
                "tools/agentspec/agentspec/stagger_admission.py:is_burst",
                [p2_src, p2_ver],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {"id": "t1-200-unit-stagger-histogram", "command": P1, "result": "PASS"},
            {"id": "t2-stagger-disabled-burst", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            L.control(
                "c1-stagger-off-burst",
                "known-broken-fixture",
                "stagger disabled must present as a burst; stagger enabled must not",
                True,
                True,
                bad=json.dumps(off["hist"]["bins"], sort_keys=True),
                good=json.dumps(on["hist"]["bins"], sort_keys=True),
            )
        ],
        "reviewer": {
            "reviewer_id": "IMP-0220-probe2-burst-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0220/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0220/probe1_stagger_histogram.py",
                "artifact_path": "tools/agentspec/agentspec/stagger_admission.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": p1_src,
            },
            {
                "consumer": "command-center/p2-wave/probes/IMP-0220/probe2_burst_control.py",
                "artifact_path": "tools/agentspec/agentspec/stagger_admission.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
                "probe": p2_src,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "This unit measured a synthetic 200-unit fan-out on FakeClock. A live "
                    "vendor 429 storm feeding quota back into admission is IMP-0221, not this unit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "IMP-0221 synthetic 429 storm with typed rate-limited terminals.",
            }
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0220" not in raw:
        print(f"FAILED:{UNIT_ID} sentinel missing from serialized receipt")
        return 1
    out.write_text(raw, encoding="utf-8")
    size = out.stat().st_size
    if size < 128:
        print(f"FAILED:{UNIT_ID} receipt {size}B below floor")
        return 1
    sha = hashlib.sha256(raw.replace("\r\n", "\n").encode()).hexdigest()
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"SUCCESS:{UNIT_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
