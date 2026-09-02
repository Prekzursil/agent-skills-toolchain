#!/usr/bin/env python3
"""Probe 1: both-states rate (1/min blocks, 1000/min does not) + resume."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from campaign import both_states_rate, resume_test  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center" / "wfa" / "WFA-0029-acquisition-scheduler.json"
SENTINEL = "SUCCESS:WFA-0029"
OUT = HERE / "probe1-both-states-resume.raw.json"


def main() -> int:
    failed: list[str] = []
    both = both_states_rate()
    if not both.get("pass"):
        failed.append("live:both-states")
    with tempfile.TemporaryDirectory(prefix="wfa0029-p1-") as td:
        resume = resume_test(Path(td))
    if not resume.get("pass"):
        failed.append("live:resume")

    art_ok = ART.is_file()
    if not art_ok:
        failed.append("artifact-absent")
        doc = {}
    else:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            failed.append("sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            failed.append(f"self-declared:{st}")
        tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
        for tid in ("both-states-rate", "resume-no-lost-work"):
            row = tests.get(tid)
            if not row or row.get("pass") is not True:
                failed.append(f"artifact:{tid}")
        art_both = doc.get("both_states") or {}
        if art_both.get("blocks_at_1_per_min") is not True:
            failed.append("artifact:1-per-min-not-block")
        if art_both.get("does_not_block_at_1000_per_min") is not True:
            failed.append("artifact:1000-per-min-blocks")
        if abs(float(art_both.get("wait_1_per_min") or 0) - float(both["wait_1_per_min"])) > 1e-6:
            failed.append("artifact:wait-1-mismatch")
        if (doc.get("resume") or {}).get("pass") is not True:
            failed.append("artifact:resume")

    payload = {
        "probe": "probe1-both-states-resume",
        "unit_id": "WFA-0029",
        "both_states": both,
        "resume": {
            "lost_ids": resume.get("lost_ids"),
            "all_done": resume.get("all_done"),
            "crash_recovered_from_inflight": resume.get("crash_recovered_from_inflight"),
            "pass": resume.get("pass"),
        },
        "failed": failed,
        "pass": not failed,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failed:
        print("FAILED:WFA-0029-probe1 both-states/resume")
        print(json.dumps(failed))
        return 1
    print(
        f"wait_1_per_min={both['wait_1_per_min']:.3f} "
        f"wait_1000_per_min={both['wait_1000_per_min']:.4f} "
        f"blocks={both['blocks_at_1_per_min']} "
        f"no_block_1000={both['does_not_block_at_1000_per_min']} "
        f"resume_lost={resume['lost_ids']}"
    )
    print("SUCCESS:WFA-0029-probe1 both-states-rate resume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
