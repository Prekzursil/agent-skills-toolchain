#!/usr/bin/env python3
"""TST-0193 probe2 -- detector control: deliberately eval one payload through a
real shell; the canary marker MUST appear, proving the probe can detect
substitution. The reference sink then runs the same payload and stays clean.
Exit 0 on pass, 1 on fail.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import param_sink as PS  # noqa: E402

UNIT = "TST-0193"
RUN = HERE / ".run-p2"


def git_bash() -> str:
    from pathlib import Path as P

    c = P(r"C:" + chr(92) + "Program Files" + chr(92) + "Git" + chr(92) + "bin" + chr(92) + "bash.exe")
    return str(c) if c.is_file() else "bash"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)
    RUN.mkdir(parents=True)
    marker = (RUN / "CANARY-MARKER.txt").as_posix()
    evil = "$(echo pwned > '%s')" % marker

    # deliberate eval lane (detector control ONLY): a real shell parses the payload
    subprocess.run([git_bash(), "-c", "eval echo " + "'" + evil + "'"],
                   capture_output=True, text=True, timeout=60)
    detector_can_see_substitution = Path(marker).exists()
    eval_content = Path(marker).read_text(encoding="utf-8", errors="replace") if detector_can_see_substitution else None

    # fresh run dir for the sink lane
    marker2 = (RUN / "second" / "CANARY-MARKER.txt")
    marker2.parent.mkdir(parents=True, exist_ok=True)
    evil2 = "$(echo pwned > '%s')" % marker2.as_posix()
    got = PS.observed([evil2])
    sink_clean = (got == [evil2]) and not marker2.exists()

    payload = {
        "probe": "probe2-detector-control",
        "unit_id": UNIT,
        "pass": detector_can_see_substitution and sink_clean,
        "detector_control": {
            "deliberately_evaled_payload": evil,
            "marker_appeared": detector_can_see_substitution,
            "marker_content_head": (eval_content or "")[:40],
            "note": "proves the canary detects substitution when a shell is in the path",
        },
        "reference_sink": {
            "same_payload_observed": got,
            "literal_passthrough": sink_clean,
            "marker_after_sink": marker2.exists(),
        },
        "payloads_property_tested_in_probe1": 300,
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 detector-fired=%s sink-clean=%s"
              % (UNIT, detector_can_see_substitution, sink_clean))
        return 0
    print("FAILED:%s-probe2 detector=%s sink=%s" % (UNIT, detector_can_see_substitution, sink_clean))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
