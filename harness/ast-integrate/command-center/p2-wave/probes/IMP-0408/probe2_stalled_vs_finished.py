#!/usr/bin/env python3
"""Probe 2: adversarial — stalled vs finished is UNDECIDABLE; mtime cannot stall."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from session_liveness.harness import finished_session, stalled_session  # noqa: E402
from session_liveness.liveness import (  # noqa: E402
    EVIDENCE_WINDOW_SECONDS,
    VERDICT_NOT_ALIVE,
    VERDICT_UNDECIDABLE,
    VERDICTS,
    Observation,
    api_rejects_mtime,
    classify,
    observation_field_names,
    observe,
    stall_versus_finished,
)

PAIR_SLEEP = 1.0


def _quiet_window(handle, seconds: float = PAIR_SLEEP):
    t0 = observe(handle)
    time.sleep(seconds)
    t1 = observe(handle)
    return classify(t0, t1, window_seconds=seconds)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0408-probe2-") as tmp:
        root = Path(tmp)
        with stalled_session(root) as stalled, finished_session(root) as finished:
            stalled_r = _quiet_window(stalled)
            finished_r = _quiet_window(finished)
            pair = stall_versus_finished(stalled_r, finished_r)

            # Ancient mtime is already on the finished fixture (11h). Touch to
            # *now* as the opposite bait: mtime must still not produce STALLED.
            for dirpath, _dn, filenames in os.walk(finished.artifact_dir):
                for name in filenames:
                    os.utime(Path(dirpath) / name, None)
            bait_r = _quiet_window(finished, seconds=0.3)

    injected_cpu_only = classify(
        Observation("cpu", 1, True, 10, 100, 0.0),
        Observation("cpu", 1, True, 90, 100, 20.0),
        window_seconds=EVIDENCE_WINDOW_SECONDS,
    )
    injected_bytes_only = classify(
        Observation("b", 1, True, 10, 100, 0.0),
        Observation("b", 1, True, 10, 900, 20.0),
        window_seconds=EVIDENCE_WINDOW_SECONDS,
    )

    mtime_kw_rejected = api_rejects_mtime({"mtime": 1}) and api_rejects_mtime(
        {"st_mtime": 11 * 3600}
    )
    no_mtime_field = not any("mtime" in n.lower() for n in observation_field_names())
    no_stalled_verdict = "STALLED" not in VERDICTS

    ok = (
        stalled_r.verdict == VERDICT_UNDECIDABLE
        and finished_r.verdict == VERDICT_NOT_ALIVE
        and pair == VERDICT_UNDECIDABLE
        and bait_r.verdict == VERDICT_NOT_ALIVE
        and bait_r.verdict != "STALLED"
        and injected_cpu_only.verdict == VERDICT_UNDECIDABLE
        and injected_bytes_only.verdict == VERDICT_UNDECIDABLE
        and mtime_kw_rejected
        and no_mtime_field
        and no_stalled_verdict
    )
    payload = {
        "bait_mtime_now": bait_r.to_dict(),
        "finished": finished_r.to_dict(),
        "injected_bytes_only": injected_bytes_only.to_dict(),
        "injected_cpu_only": injected_cpu_only.to_dict(),
        "mtime_field_absent": no_mtime_field,
        "mtime_kwarg_rejected": mtime_kw_rejected,
        "no_stalled_in_api": no_stalled_verdict,
        "pair_verdict": pair,
        "pass": bool(ok),
        "probe": "probe2-stalled-vs-finished",
        "reviewer": "adversarial-refuter",
        "stalled": stalled_r.to_dict(),
        "unit_id": "IMP-0408",
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0408-probe2 adversarial stalled-vs-finished / mtime bait")
        return 1
    print(
        "SUCCESS:IMP-0408-probe2 stalled-vs-finished UNDECIDABLE; "
        "mtime cannot represent stall"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
