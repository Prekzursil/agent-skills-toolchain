"""Detector control for the B1 citation detector -- BOTH states.

H1: `citations()` really finds names inside committed blobs.
H2: `citations()` is inert (bad pattern / wrong rev / rc swallowed) and its silence is
    meaningless.

A control that passes under BOTH hypotheses is not a control, so this asserts a COUNT on
each side, not merely that the function returned:

  FIRE : a name that is KNOWN-referenced by a tracked test must come back with >=1 citer,
         and the expected citer path must be among them.
  QUIET: a name that exists nowhere must come back with exactly 0 citers.
  SHAPE: the two must differ. If FIRE and QUIET both return 0 the instrument is dead.

ROUND-2 FIX (the round-1 version of this file was REFUTED, wording kept rather than deleted).
Round 1 used a HARDCODED negative-control sentinel, `_zzz_control_no_such_probe_9f3a17.py`,
and then committed BOTH this script and its receipt. That put the sentinel literal into the
very corpus `citations()` greps, so from the next commit onward the "name that exists nowhere"
existed in two tracked blobs: the control found ITSELF, `quiet_citer_count` went 0 -> 2, and
the committed receipt asserting `PASS` became unreproducible -- any clone re-running the
lane's primary detector control got `FAIL`, rc=1. Measured in `_r2_d2_reproduce.out.json`.

Two changes close it, and a third stops the receipt from rotting:
  1. `--sentinel random` (DEFAULT) generates the absent name at runtime, so no committed byte
     can ever contain it. `--sentinel legacy` reproduces the round-1 fixed name and is EXPECTED
     TO FAIL -- that is the permanent both-states control for this fix, and it cannot silently
     start passing, because the legacy literal is in this file forever.
  2. The receipt records the sentinel's SHAPE, never the literal, so the receipt itself can
     never re-poison the corpus.
  3. Writing the receipt is now opt-in (`--write`). The default run is read-only, so the
     command published as the bucket-(c) regenerator no longer dirties a tracked file and
     no longer exits nonzero on a healthy tree.

`fire_citer_count` GROWS as the repo grows (248 at f5b596e6, 256 two commits later). It is a
rev-anchored observation, not a constant: the checks assert relations (>=1, ==0, fire>quiet),
never a pinned number.
"""

import argparse
import json
import os
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _b1_cited_probes import citations  # noqa: E402

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
RECEIPT_REL = "command-center/slop-report/_b1_control.out.json"

KNOWN_REFERENCED = "_gen_schema_substrate.py"  # tracked test hardcodes this path
EXPECTED_CITER = "platform/lib/test_schema_resolver.py"
# Round-1 sentinel. Kept ONLY so `--sentinel legacy` can reproduce the defect on demand.
LEGACY_SENTINEL = "_zzz_control_no_such_probe_9f3a17.py"
SENTINEL_SHAPE = "<generated per run: _zzz_control_no_such_probe_<uuid4hex>.py>"


def make_sentinel(mode):
    if mode == "legacy":
        return LEGACY_SENTINEL, LEGACY_SENTINEL
    return f"_zzz_control_no_such_probe_{uuid.uuid4().hex}.py", SENTINEL_SHAPE


def head_rev():
    r = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def run(mode):
    sentinel, shown = make_sentinel(mode)
    res = citations([KNOWN_REFERENCED, sentinel])
    fire = res[KNOWN_REFERENCED]
    quiet = res[sentinel]

    checks = {
        "fire_has_citers": len(fire) >= 1,
        "fire_includes_expected_citer": EXPECTED_CITER in fire,
        "quiet_is_zero": len(quiet) == 0,
        "states_distinguishable": len(fire) > len(quiet),
    }
    return {
        "sentinel_mode": mode,
        "measured_at_rev": head_rev(),
        "known_referenced": KNOWN_REFERENCED,
        "fire_citer_count": len(fire),
        "fire_citers": fire[:10],
        "nonexistent": shown,
        "quiet_citer_count": len(quiet),
        "quiet_citers": quiet[:10],
        "counts_drift_with_tree": True,
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sentinel", choices=("random", "legacy"), default="random")
    ap.add_argument(
        "--write",
        action="store_true",
        help="update the committed receipt (default: read-only)",
    )
    args = ap.parse_args(argv)

    out = run(args.sentinel)
    if args.write:
        dst = os.path.join(ROOT, RECEIPT_REL)
        with open(dst, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=1, sort_keys=True)
        out["_wrote"] = RECEIPT_REL
    print(json.dumps(out, indent=1))
    return 0 if out["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
