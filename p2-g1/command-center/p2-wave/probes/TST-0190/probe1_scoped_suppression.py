#!/usr/bin/env python3
"""TST-0190 probe1 -- MSYS_NO_PATHCONV scoped to revision-ish arguments.

Both assertions in one probe:
  (a) WITH the variable applied (env-prefix scope), the POSIX-style argument
      survives INTACT into the native child's argv (suppression works), and
  (b) WITHOUT the variable, the same argument is CONVERTED by MSYS to a
      Windows path that the child actually resolves (normal conversion works).
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import msys_lane as ML  # noqa: E402

UNIT = "TST-0190"


def main() -> int:
    arg = "/c/Users/Prekzursil"

    rc_s, out_s = ML.child_argv(arg, suppress=True)
    kept = None
    try:
        kept = json.loads(out_s.splitlines()[-1])["argv"][0]
    except Exception:
        pass
    survives_intact = kept == arg

    rc_c, out_c = ML.child_argv(arg, suppress=False)
    conv = None
    try:
        conv = json.loads(out_c.splitlines()[-1])["argv"][0]
    except Exception:
        pass
    converted = conv is not None and conv.replace("/", "\\").lower().startswith("c:") and "users" in conv.lower()

    payload = {
        "probe": "probe1-scoped-suppression",
        "unit_id": UNIT,
        "pass": survives_intact and converted,
        "with_env_prefix": {"rc": rc_s, "child_argv0": kept, "survives_intact": survives_intact},
        "without_env_prefix": {"rc": rc_c, "child_argv0": conv, "msys_converted": converted},
        "measured_lane": "bash -c spawning a native python child (real MSYS conversion path)",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 suppressed_arg_intact=%s unsuppressed_converted=%s"
              % (UNIT, survives_intact, converted))
        return 0
    print("FAILED:%s-probe1 intact=%s converted=%s (%r / %r)"
          % (UNIT, survives_intact, converted, kept, conv))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
