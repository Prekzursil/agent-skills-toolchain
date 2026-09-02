#!/usr/bin/env python3
"""Probe 2: parse each step's own output; zero-collect is never success."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
import controls as CTL  # noqa: E402

ART = C.REPO / C.OUT_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:AUD-0042-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if C.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:AUD-0042-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0042-probe2 self-declared", doc.get("state"))
        return 1
    ctl = CTL.run_required_tests()
    gap = doc.get("gap_steps") or []
    local = doc.get("worktree_never_ci_steps") or []
    parse_mismatch = []
    for s in gap + local:
        raw_rel = s.get("raw_rel")
        if not raw_rel:
            parse_mismatch.append(("no-raw", s.get("name")))
            continue
        path = C.REPO / raw_rel
        if not path.is_file():
            parse_mismatch.append(("raw-absent", raw_rel))
            continue
        live = C.parse_summary(path.read_text(encoding="utf-8"))
        for key in ("collected", "passed", "failed", "errored", "counted_as_test_success"):
            if s.get(key) != live.get(key):
                parse_mismatch.append((s.get("name"), key, s.get(key), live.get(key)))
        if live["collected"] == 0 and live["counted_as_test_success"]:
            parse_mismatch.append(("zero-collect-success", s.get("name")))
    live_det = C.run_cmd(C.pytest_argv("tools/detectors/tests"), timeout=30)
    det_sum = C.parse_summary(live_det[1])
    live_ok = det_sum["collected"] > 0
    nonzero = [s for s in (gap + local) if int(s.get("collected") or 0) > 0]
    headline = doc.get("headline") or {}
    headline_ok = int(headline.get("nonzero_collected_step_count") or 0) == len(nonzero)
    passed = bool(
        ctl["pass"]
        and not parse_mismatch
        and live_ok
        and len(nonzero) >= 1
        and headline_ok
        and len(gap) == 32
    )
    payload = {
        "probe": "probe2-result-summaries",
        "unit_id": C.UNIT,
        "pass": passed,
        "control_pass": ctl["pass"],
        "control_empty_collected": ctl["bad"]["summary"]["collected"],
        "control_one_collected": ctl["good"]["summary"]["collected"],
        "parse_mismatch_count": len(parse_mismatch),
        "nonzero_collected_steps": len(nonzero),
        "live_detectors_collected": det_sum["collected"],
        "live_detectors_exit": live_det[0],
        "headline_ok": headline_ok,
        "reviewer_id": "AUD-0042-probe2-result-summaries",
    }
    print(json.dumps(payload, sort_keys=True))
    if not passed:
        print("FAILED:AUD-0042-probe2 result summaries")
        print(json.dumps(parse_mismatch[:12], default=str))
        return 1
    print(
        "SUCCESS:AUD-0042-probe2 parsed summaries; "
        f"nonzero_steps={len(nonzero)} detectors_collected={det_sum['collected']}; "
        f"empty_collect={ctl['bad']['summary']['collected']} "
        f"one_collect={ctl['good']['summary']['collected']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
