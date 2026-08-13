"""BUILD-R1 probe: are the two timing-out gates HUNG or merely SLOW?

_b1 used a 120 s cap and r2_pathrefs.py / r3_corpus_parity_gate.py both hit it.
A cap is not a diagnosis: "exceeded 120 s" is consistent with both a 121 s run and an
infinite loop. Re-run each with a 900 s cap and record wall-clock, so the CI timeout can
be set from a measurement instead of a guess.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

SLOW = ["r2_pathrefs.py", "r3_corpus_parity_gate.py"]
TIMEOUT_SEC = 900


def main() -> int:
    out = []
    for name in SLOW:
        started = time.monotonic()
        rec: dict[str, object] = {"gate": name}
        try:
            proc = subprocess.run(
                [sys.executable, str(HERE / name)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEC,
            )
            rec["returncode"] = proc.returncode
            rec["state"] = "SLOW_BUT_FINITE"
            rec["stdout_tail"] = proc.stdout.replace("\r\n", "\n")[-1500:]
            rec["stderr_tail"] = proc.stderr.replace("\r\n", "\n")[-1500:]
        except subprocess.TimeoutExpired:
            rec["state"] = "HUNG_OR_OVER_900S"
        rec["wall_sec"] = round(time.monotonic() - started, 1)
        print(
            f"{name}: {rec['state']} rc={rec.get('returncode')} {rec['wall_sec']}s",
            flush=True,
        )
        out.append(rec)

    (HERE / "_b2_slowgate_probe.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
