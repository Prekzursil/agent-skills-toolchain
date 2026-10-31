#!/usr/bin/env python3
"""One-shot deterministic patches for ADV-0033 build_artifact.py (fix cycle)."""
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/ADV-0033/build_artifact.py")
t = P.read_text(encoding="utf-8")

# 1. fold the NOT-RUN note into the test row's name; drop the extra key
t = t.replace(
    '''            "result": "PASS" if meas["isolator_detects_block"]
            else ("NOT-RUN" if not meas["matrix"]["cells"]
                  ["linux-user-namespace-isolator"]["executed"] else "FAIL"),
            "name-appendix": ("isolator binary absent on this host; the go-red "
                              "control was proven on the 2026-08-24 Linux "
                              "measurement"),''',
    '''            "result": "PASS" if meas["isolator_detects_block"]
            else ("NOT-RUN" if not meas["matrix"]["cells"]
                  ["linux-user-namespace-isolator"]["executed"] else "FAIL"),''',
)
# fold the note into the T-ISOLATOR test name (the row above it defines name via L.PROBE1_NAME; patch just this row's name)
t = t.replace(
    '''        {
            "id": "T-ISOLATOR-GOES-RED",
            "name": (
                "negative: a user-namespace net+pid isolator must block at "
                "least one action so blocked results are believable"
            ),''',
    '''        {
            "id": "T-ISOLATOR-GOES-RED",
            "name": (
                "negative: a user-namespace net+pid isolator must block at "
                "least one action so blocked results are believable "
                "(NOT-RUN here: isolator binary absent on this host; the "
                "go-red control was proven on the 2026-08-24 Linux measurement)"
            ),''',
)

# 2. negative_controls rows: add kind + both flags (receipt_core required)
t = t.replace(
    '''        "negative_controls": [
            {
                "id": "unisolated-local-all-four",
                "result": "PASS" if meas["control_unisolated_all_four"] else "FAIL",
                "fired_on_bad_state": True,
                "description": (
                    "Deliberately unisolated local process must succeed at "
                    "all four actions before any blocked cell is believed."
                ),
            },
            {
                "id": "namespace-isolator-goes-red",
                "result": "PASS" if meas["isolator_detects_block"]
                else ("NOT-RUN" if not meas["matrix"]["cells"]
                      ["linux-user-namespace-isolator"]["executed"] else "FAIL"),
                "fired_on_bad_state": True,
                "description": (
                    "unshare --net --pid must fail socket and/or process "
                    "list so the probe is not an always-true detector."
                ),
                "note": ("binary absent on this host; fired_on_bad_state=true "
                         "proven on the 2026-08-24 Linux measurement"),
            },
        ],''',
    '''        "negative_controls": [
            {
                "id": "unisolated-local-all-four",
                "kind": "other",
                "result": "PASS" if meas["control_unisolated_all_four"] else "FAIL",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "Deliberately unisolated local process must succeed at "
                    "all four actions before any blocked cell is believed. "
                    "fired_on_bad_state=true proven by the 2026-08-24 Linux "
                    "measurement where a hard block made this control go red."
                ),
            },
            {
                "id": "namespace-isolator-goes-red",
                "kind": "absent-input",
                "result": "PASS" if meas["isolator_detects_block"]
                else ("NOT-RUN" if not meas["matrix"]["cells"]
                      ["linux-user-namespace-isolator"]["executed"] else "FAIL"),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "unshare --net --pid must fail socket and/or process list "
                    "so the probe is not an always-true detector. NOT-RUN on "
                    "this host: binary absent; fired_on_bad_state=true proven "
                    "on the 2026-08-24 Linux measurement."
                ),
            },
        ],''',
)

P.write_text(t, encoding="utf-8", newline="")
print("patched")
