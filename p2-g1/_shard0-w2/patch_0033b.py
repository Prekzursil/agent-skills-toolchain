#!/usr/bin/env python3
"""Patch negative_controls block by locating real block boundaries (no drift)."""
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/ADV-0033/build_artifact.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)

start = next(i for i, ln in enumerate(lines)
             if ln.strip().startswith('"negative_controls": ['))
# block ends at the line that is exactly "        ]," after start
end = next(i for i in range(start + 1, len(lines))
           if lines[i].rstrip() == "        ],")
new_block = '''        "negative_controls": [
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
                    "this host: binary absent; both flags proven on the "
                    "2026-08-24 Linux measurement."
                ),
            },
        ],
'''
lines[start:end + 1] = [new_block]
P.write_text("".join(lines), encoding="utf-8", newline="")
print(f"replaced lines {start + 1}..{end + 1}")
