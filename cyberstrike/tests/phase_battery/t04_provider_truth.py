#!/usr/bin/env python3
"""T-4 (CRITICAL) provider-truth regression - wires the Phase-1 detector in.

Detector EXISTS from Phase-1: scripts/phase1_provider_truth.py (receipt
phase1/T-4.json, verdict PASS at git HEAD 2c0f3c6). This battery entry makes
it a PERMANENT regression gate (audit CS-01: prose presenting OpenAI/Astra/
Daybreak as a cockpit brain while `openai` sits in disabled_providers, and
phantom "registered" model claims).

Both-states control, reconstructed per run via git-show (no temp checkout):
  baseline pair (2c0f3c6 config.md + cyberstrike.json) MUST produce findings
  >= 2 with detector rc=1 (broken state fires);
  live pair (worktree files) MUST produce 0 findings with rc=0.

A detector silent in both states measures nothing - the baseline leg is the
control that keeps this gate honest. Never prints credential values (the
detector emits structural fields only; so does this wrapper).
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    REPO, SCRIPTS, BASELINE_REV, SUCCESS, FAILED,
    VerdictRecorder, git_show, py_run, json_from_completed,
)

DETECTOR = SCRIPTS / "phase1_provider_truth.py"


def run_detector(rec: VerdictRecorder, cfg: Path, docs: Path) -> dict:
    r = py_run(DETECTOR, ["--config", str(cfg), "--docs", str(docs), "--json"])
    parsed = json_from_completed(r)
    rec.hit("T-4", "detector_run", config=cfg.name, docs=docs.name,
            rc=r.returncode, count=(parsed or {}).get("count"),
            stderr=(r.stderr or "")[:300])
    return {"rc": r.returncode, "parsed": parsed,
            "stderr_head": (r.stderr or "")[:300]}


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    if not DETECTOR.is_file():
        rec.record("T-4", FAILED, reason="detector missing",
                   anchors=[DETECTOR])
        return FAILED

    with tempfile.TemporaryDirectory(prefix="t4-baseline-") as td:
        base_cfg = Path(td) / "cyberstrike.json"
        base_doc = Path(td) / "config.md"
        base_cfg.write_text(git_show(BASELINE_REV, "cyberstrike.json"),
                            encoding="utf-8")
        base_doc.write_text(git_show(BASELINE_REV, "config.md"),
                            encoding="utf-8")

        base = run_detector(rec, base_cfg, base_doc)
        live = run_detector(rec, REPO / "cyberstrike.json", REPO / "config.md")

        base_count = (base["parsed"] or {}).get("count", -1)
        live_count = (live["parsed"] or {}).get("count", -1)
        base_ok = base["rc"] == 1 and base_count >= 2   # control fires
        live_ok = live["rc"] == 0 and live_count == 0    # clean now
        both = {
            "baseline_rev": BASELINE_REV,
            "baseline": {"rc": base["rc"], "count": base_count},
            "live": {"rc": live["rc"], "count": live_count},
            "control_fires_in_broken_state": base_ok,
            "live_clean": live_ok,
        }
        ok = base_ok and live_ok
        rec.record("T-4", SUCCESS if ok else FAILED,
                   details={"detector": str(DETECTOR),
                            "baseline_source": "git show "
                            f"{BASELINE_REV}:{{cyberstrike.json,config.md}}"},
                   both_states=both,
                   anchors=[DETECTOR, REPO / "cyberstrike.json",
                            REPO / "config.md"],
                   reason=None if ok else
                   "detector failed both-states (control silent or live dirty)")
        return SUCCESS if ok else FAILED


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args()
    with VerdictRecorder(meta={"test": "T-4"}) as rec:
        status = run(rec)
        print(f"T-4 {status}")
        return 0 if status == SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())
