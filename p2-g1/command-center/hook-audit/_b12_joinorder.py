"""B12. Does an over-ceiling check timeout actually cost anything, or is it only untidy?

Round 4 measured that `Stop/git-hygiene` declares a 90 s budget inside a 35 s event budget and
called the surplus "unreachable". `hook_predeploy_gate.lint_budget_ceiling` encodes that as an
L2 finding. Both stop at "55 s cannot be used", which reads as cosmetic -- a number nobody can
spend. This probe asks the question neither round asked: what does the DISPATCHER do with it.

Mechanism, read from `hooks/_dispatch/dispatch.py:349-372` and then EXECUTED here rather than
asserted:

    start = time.monotonic()                              # :360, once, after all threads start
    for (chk, _mod, buf, rc_sink), t in zip(loaded, threads):   # :362, MANIFEST ORDER
        budget = float(chk.get("timeout") or 8)           # :364
        remaining = max(0.0, budget - (time.monotonic() - start))   # :367 ABSOLUTE deadline
        t.join(timeout=remaining)                         # :368

Checks run concurrently but are COLLECTED sequentially, each with an absolute deadline of
`start + its own declared timeout`. So the declared timeout is not decoration: it is how long
`run()` is willing to sit at that index before giving up. A check declaring more than the event
ceiling can therefore hold `run()` past the ceiling -- and per the vendor contract the timeout is
per-hook-COMMAND, and our dispatcher is ONE command holding N checks, so the cancellation lands
on the whole dispatcher and EVERY check on that event loses its output together.

ARMS (identical worker, only the DECLARED timeout differs -- that is the variable the manifest
fix changes, so nothing else may move):

    A_over_ceiling   slow declares 6 s inside a 2 s ceiling -> run() should overrun the ceiling
    B_under_ceiling  slow declares 1 s inside a 2 s ceiling -> run() should return inside it

CONTROLS:
    C1 arms_discriminate      A overruns the ceiling and B does not. Without this the probe is
                              measuring the sleep, not the declared budget.
    C2 fast_output_visible    the trailing check's additionalContext is collected in the GOOD
                              arm. A probe that can never see output cannot claim output is lost.
    C3 real_dispatcher        the module under test is the repo's dispatch.py (has run/_extract_ctx
                              and its MANIFEST resolves to hooks/_dispatch/manifest.json), not a
                              local re-implementation of the loop.
    C4 slow_actually_dropped  in the GOOD arm the slow check is cut off (its output is absent),
                              which is the cost of the fix and is reported, not hidden.

Re-runnable:  python command-center/hook-audit/_b12_joinorder.py
Evidence:     command-center/hook-audit/B12-JOINORDER.json
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DISPATCH = REPO / "hooks" / "_dispatch" / "dispatch.py"
REPO_MANIFEST = REPO / "hooks" / "_dispatch" / "manifest.json"
OUT = Path(__file__).resolve().parent / "B12-JOINORDER.json"

# The synthetic worker sleeps longer than either declared budget, so the ONLY thing that decides
# how long run() waits is the manifest's `timeout` field.
SLOW_SLEEP_S = 5.0
CEILING_S = 2.0

SLOW_SRC = """import time
import json

def main(argv=None):
    time.sleep({sleep})
    print(json.dumps({{"hookSpecificOutput": {{"additionalContext": "SLOW-RAN"}}}}))
    return 0
"""

FAST_SRC = """import json

def main(argv=None):
    print(json.dumps({"hookSpecificOutput": {"additionalContext": "FAST-RAN"}}))
    return 0
"""


def load_dispatch():
    spec = importlib.util.spec_from_file_location("b12_dispatch", DISPATCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_root(tmp: Path) -> None:
    (tmp / "slow").mkdir(parents=True, exist_ok=True)
    (tmp / "fast").mkdir(parents=True, exist_ok=True)
    (tmp / "slow" / "check.py").write_text(
        SLOW_SRC.format(sleep=SLOW_SLEEP_S), encoding="utf-8"
    )
    (tmp / "fast" / "check.py").write_text(FAST_SRC, encoding="utf-8")


def manifest_for(root: Path, slow_timeout: float) -> dict:
    return {
        "hooks_root": str(root),
        "events": {
            "Stop": {
                "settings_matcher": "",
                "settings_timeout": CEILING_S,
                "checks": [
                    {
                        "name": "slow",
                        "script": "slow/check.py",
                        "args": [],
                        "timeout": slow_timeout,
                    },
                    {
                        "name": "fast",
                        "script": "fast/check.py",
                        "args": [],
                        "timeout": 1,
                    },
                ],
            }
        },
    }


def run_arm(dispatch, root: Path, slow_timeout: float) -> dict:
    man = manifest_for(root, slow_timeout)
    t0 = time.monotonic()
    out = dispatch.run("Stop", "{}", man)
    wall = time.monotonic() - t0
    text = out or ""
    return {
        "declared_slow_timeout_s": slow_timeout,
        "event_ceiling_s": CEILING_S,
        "run_wall_s": round(wall, 3),
        "overran_ceiling": wall > CEILING_S,
        "fast_output_collected": "FAST-RAN" in text,
        "slow_output_collected": "SLOW-RAN" in text,
    }


def real_manifest_violations() -> dict:
    """The live defect this synthetic arm stands in for, read from the real manifest.

    The ceiling comes from `hook_predeploy_gate.enforced_ceilings` (settings.json), NOT from the
    manifest's `settings_timeout` mirror. That distinction is load-bearing: the mirror is stale on
    2 of 4 events, and reading it is what made round 4 report `PreToolUse/edit-checkpoints` as an
    EQUALS violation. Its declared 15 s sits under the ENFORCED 20 s, so it fits and was never a
    defect. Falls back to the mirror when settings cannot be read, so a fresh clone still gets an
    answer rather than silence.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import hook_predeploy_gate as gate

    enforced = gate.enforced_ceilings(gate.LIVE_SETTINGS)
    doc = json.loads(REPO_MANIFEST.read_text(encoding="utf-8"))
    rows = []
    for event, node in (doc.get("events") or {}).items():
        mirror = node.get("settings_timeout")
        ceiling = enforced.get(event, mirror)
        if not isinstance(ceiling, (int, float)):
            continue
        for chk in node.get("checks") or []:
            declared = chk.get("timeout")
            if isinstance(declared, (int, float)) and declared > ceiling:
                rows.append(
                    {
                        "event": event,
                        "check": chk.get("name"),
                        "declared_s": declared,
                        "ceiling_s": ceiling,
                        "ceiling_source": "enforced" if event in enforced else "mirror",
                    }
                )
    return {
        "checks_scanned": sum(
            len(n.get("checks") or []) for n in doc["events"].values()
        ),
        "ceiling_source_per_event": {
            ev: ("enforced" if ev in enforced else "mirror") for ev in doc["events"]
        },
        "violations": rows,
    }


def main() -> int:
    dispatch = load_dispatch()

    c3 = (
        hasattr(dispatch, "run")
        and hasattr(dispatch, "_extract_ctx")
        and Path(dispatch.MANIFEST).resolve() == REPO_MANIFEST.resolve()
    )

    tmp = Path(tempfile.mkdtemp(prefix="b12_join_"))
    # dispatch.main() installs these proxies at :407-408 before calling run(); a probe that
    # calls run() directly must do the same or every check's print() escapes to the real
    # stdout and the buffers read EMPTY. Control C2 caught exactly that on the first run --
    # without it this probe would have reported "all output is lost" in BOTH arms.
    real_out, real_in = sys.stdout, sys.stdin
    try:
        build_root(tmp)
        sys.stdout = dispatch._ThreadStdout(real_out)
        sys.stdin = dispatch._ThreadStdin(real_in)
        bad = run_arm(dispatch, tmp, slow_timeout=6)
        good = run_arm(dispatch, tmp, slow_timeout=1)
    finally:
        sys.stdout, sys.stdin = real_out, real_in
        shutil.rmtree(tmp, ignore_errors=True)

    real = real_manifest_violations()

    controls = {
        "C1_arms_discriminate": bool(
            bad["overran_ceiling"] and not good["overran_ceiling"]
        ),
        "C2_fast_output_visible": bool(good["fast_output_collected"]),
        "C3_real_dispatcher": bool(c3),
        "C4_slow_dropped_in_good_arm": bool(not good["slow_output_collected"]),
        "C5_real_manifest_readable": real["checks_scanned"] >= 20,
    }

    blob = {
        "probe": "_b12_joinorder.py",
        "mechanism_source": "hooks/_dispatch/dispatch.py:360-372",
        "slow_worker_sleep_s": SLOW_SLEEP_S,
        "arms": {"A_over_ceiling": bad, "B_under_ceiling": good},
        "over_ceiling_budget_is_honoured_past_the_cap": bad["overran_ceiling"],
        "within_ceiling_budget_returns_in_time": not good["overran_ceiling"],
        "real_manifest": real,
        "controls": controls,
    }
    OUT.write_text(json.dumps(blob, indent=1) + "\n", encoding="utf-8")

    failed = [k for k, v in controls.items() if not v]
    if failed:
        print(f"FAILED:b12-joinorder controls failed: {', '.join(failed)}")
        return 2
    print(
        f"A(declared 6s in {CEILING_S}s ceiling): run() took {bad['run_wall_s']}s "
        f"-> overran={bad['overran_ceiling']}"
    )
    print(
        f"B(declared 1s in {CEILING_S}s ceiling): run() took {good['run_wall_s']}s "
        f"-> overran={good['overran_ceiling']}, fast collected={good['fast_output_collected']}"
    )
    for row in real["violations"]:
        print(
            f"REAL {row['event']}/{row['check']}: declares {row['declared_s']}s "
            f"inside {row['ceiling_s']}s ({row['kind']})"
        )
    print(
        f"SUCCESS:b12-joinorder {len(real['violations'])} real violation(s); controls 5/5"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
