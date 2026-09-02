#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0239.json benchmark receipt."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0239.json"
UID = "TST-0239"
SENTINEL = "SUCCESS:TST-0239"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0239/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0239/probe2_scaling.py"
)
QUESTION = (
    "What is the first-command-after-install latency versus warm, and does "
    "the cold path contain an unbounded index build? PASS requires cold-start "
    "under its ceiling on a representative install size and O(n) behavior "
    "characterized, not assumed."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {"path": rel, "sha256": sha, "bytes": size}


def main() -> int:
    live = S.measure_all()
    if not live.get("pass"):
        print("FAILED:TST-0239 emit live measurement did not pass")
        print(json.dumps({k: live.get(k) for k in ("pass", "answer", "both_states", "scaling")}, indent=2)[:8000])
        return 1

    p1 = {
        "id": "probe1",
        "command": P1,
        "role": "both-states-warm-faster",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0239/probe1_both_states.py"
        ),
    }
    p2 = {
        "id": "probe2",
        "command": P2,
        "role": "scaling-and-unbounded-index-detector",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0239/probe2_scaling.py"
        ),
    }
    if p1["fingerprint"]["sha256"] == p2["fingerprint"]["sha256"]:
        print("FAILED:TST-0239 emit source/verifier probe files identical")
        return 1

    both = live["both_states"]
    scaling = live["scaling"]
    ans = live["answer"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    census_rel = "tools/plugin/census.py"
    census_sha, census_bytes = sha256_file(REPO / census_rel)
    fc_rel = "command-center/p2-wave/probes/TST-0239/first_command.py"
    fc_sha, fc_bytes = sha256_file(REPO / fc_rel)

    doc = {
        "answer": ans,
        "artifacts": [
            {
                "exists": True,
                "path": OUT,
                "role": "primary",
            },
            {
                "exists": True,
                "path": fc_rel,
                "role": "first-command-harness",
                "sha256": fc_sha,
                "bytes": fc_bytes,
            },
            {
                "exists": True,
                "path": census_rel,
                "role": "cold-walk-census",
                "sha256": census_sha,
                "bytes": census_bytes,
            },
        ],
        "both_states": both,
        "claim_id": "TST-0239-cold-vs-warm-first-command",
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
        "evidence": [
            {
                "claim": (
                    "On a clean isolated profile of representative size, median "
                    "warm first-command is measurably faster than median cold; "
                    "two consecutive warms do not produce that contrast; deleting "
                    "the capability-index cache restores cold-like cost."
                ),
                "kind": "timed-cold-and-warm-clean-profile",
                "path": "command-center/p2-wave/probes/TST-0239/probe1_both_states.py",
                "cold_median_ms": both["cold_median_ms"],
                "warm_median_ms": both["warm_median_ms"],
                "cold_over_warm": both["cold_over_warm"],
            },
            {
                "claim": (
                    "Cold first-command at 1x, 4x, and 16x installed-capability "
                    "counts has log-log exponent under the linear ceiling; a "
                    "planted quadratic nested-census mutant is slower with a "
                    "higher exponent, so O(n) is measured rather than assumed."
                ),
                "kind": "scaling-curve-three-install-sizes",
                "path": "command-center/p2-wave/probes/TST-0239/probe2_scaling.py",
                "exponent_1x_16x": scaling["exponent_1x_16x"],
                "characterization": scaling["characterization"],
                "quadratic_mutant_detected": scaling["quadratic_mutant_detected"],
            },
        ],
        "evidence_requirement": (
            "two independent signals: (a) timed cold and warm runs on a clean "
            "profile, and (b) a scaling curve across 3 install sizes"
        ),
        "min_bytes_threshold": 2048,
        "named_probes": [p1, p2],
        "question": QUESTION,
        "registered": True,
        "report_kind": "benchmark_result",
        "residual_unknowns": [
            {
                "claim": (
                    "Production tools/router/index_build.py (IMP-0385) is absent "
                    "on this worktree. Measurements are of the first-command "
                    "harness in probes/TST-0239/first_command.py, which walks "
                    "install trees through tools.plugin.census.tree_files."
                ),
                "settling_experiment": (
                    "Re-run both probes against IMP-0385 once that crawler exists."
                ),
                "verdict": "NOT-CHECKED-PRODUCTION-CRAWLER",
            }
        ],
        "reviewer": {
            "independent": True,
            "notes": (
                "Probe 2 re-times 1x/4x/16x cold builds and a quadratic nested "
                "census mutant; it does not reuse probe 1's warm/cold samples."
            ),
            "reviewer_id": "TST-0239-probe2-scaling",
            "verdict": "PASS",
        },
        "scaling": scaling,
        "schema_version": 1,
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "IMP-0385 tools/router/index_build.py was present",
                "user ~/.claude profile was timed",
            ],
            "proof_surface": (
                "isolated tempfile profiles; tools.plugin.census walk on cold; "
                "capability-index.json cache on warm; 1x/4x/16x linear vs "
                "quadratic nested census."
            ),
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "tests": {
            "both_states_warm_faster": {
                "pass": both["pass"],
                "cold_over_warm": both["cold_over_warm"],
            },
            "cache_delete_restores_cold": {
                "pass": both["cache_delete_restores_cold"],
            },
            "scaling_1x_4x_16x": {
                "pass": scaling["pass"],
                "exponent_1x_16x": scaling["exponent_1x_16x"],
                "characterization": scaling["characterization"],
            },
            "quadratic_mutant_detector": {
                "pass": scaling["quadratic_mutant_detected"],
                "quadratic_exponent_1x_4x": scaling["quadratic_exponent_1x_4x"],
            },
        },
        "title": "Cold-start versus warm-start latency are both measured and bounded",
        "ts": now,
        "unit_id": UID,
        "verdict": "PASS",
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
