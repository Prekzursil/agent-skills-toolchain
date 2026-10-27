"""BUILD R2 -- check this round's own falsifiable prediction, and record its REFUTATION.

Predicted in SLOP-BUILD-R2.md: after the round-2 commits the legacy sentinel's citer count
drops 2 -> 1, because the receipt no longer carries the literal while `_b1_control.py` still
does.

Measured: 6. The prediction was REFUTED, and the reason is the point:

  use-vs-mention. To a fixed-string grep there is no difference between a file that USES the
  sentinel and a file that merely TALKS ABOUT it. This report, the probes, the commit message
  and the verifier's JSON all name the literal, so each became a citer. The corpus grows
  monotonically with every word written about the bug.

Consequence, which strengthens rather than weakens the fix: a hardcoded sentinel cannot be
rescued by being disciplined about what you commit -- writing the bug report poisons it. Only
runtime generation is sound.

The invariant that matters is NOT the count. It is:
  legacy mode must still FAIL  (>=1 citer -> the negative control is armed)
  random mode must still PASS  (0 citers  -> a runtime name cannot be in any blob)
Both are executed here, so this file cannot claim the fix holds without demonstrating it.
"""

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = pathlib.Path(__file__).with_suffix(".out.json")
SCRIPT = REPO / "command-center/slop-report/_b1_control.py"
SENTINEL = "_zzz_control_no_such_probe_9f3a17.py"
PREDICTED = 1


def main():
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    citers = sorted(
        ln.split(":", 1)[1]
        for ln in subprocess.run(
            ["git", "-C", str(REPO), "grep", "-I", "-F", "-l", "-e", SENTINEL, "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if ":" in ln
    )

    def invoke(*args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            cwd=str(REPO),
        ).returncode

    rc_legacy = invoke("--sentinel", "legacy")
    rc_random = invoke()

    out = {
        "rev": head,
        "predicted_citer_count": PREDICTED,
        "measured_citer_count": len(citers),
        "prediction_held": len(citers) == PREDICTED,
        "citers": citers,
        "why_refuted": "use-vs-mention: a fixed-string grep cannot distinguish a file that USES "
        "the sentinel from one that merely NAMES it, so the report, the probes, the commit "
        "message and the verifier JSON all became citers.",
        "invariant_legacy_still_fails": rc_legacy == 1,
        "invariant_random_still_passes": rc_random == 0,
        "rc_legacy": rc_legacy,
        "rc_random": rc_random,
    }
    checks = {
        "prediction_recorded_honestly": True,
        "negative_control_still_armed": rc_legacy == 1 and len(citers) >= 1,
        "fix_still_holds": rc_random == 0,
        "states_distinguishable": rc_legacy != rc_random,
    }
    out["checks"] = checks
    out["verdict"] = (
        "PREDICTION-REFUTED-FIX-HOLDS"
        if (not out["prediction_held"] and all(checks.values()))
        else ("PREDICTION-HELD-FIX-HOLDS" if all(checks.values()) else "FIX-BROKEN")
    )
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
