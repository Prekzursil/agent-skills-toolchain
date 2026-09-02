"""Reproduce TST-0350's declared control NC2 properly, in-process.

NC2: "Point the collector at an empty directory: pytest exits 0 over nothing, so the floor must
reject it. This is the primary defect being guarded."

_b17's attempt used a temp dir OUTSIDE the repo and died on a Windows rootdir/conftest resolution
error (FileNotFoundError WinError 2), so it measured nothing. Recorded, not hidden. This version
uses a scratch dir INSIDE the repo and drives suitefloor's own collect/floor functions.
"""

import inspect
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/measure-guard"))
import suitefloor  # noqa: E402

OUT = {}
print("suitefloor API:", [n for n in dir(suitefloor) if not n.startswith("_")])
for name in ("collect_count", "require_nonempty", "check_suite", "unregistered"):
    fn = getattr(suitefloor, name, None)
    if fn:
        try:
            print(f"\n--- {name}{inspect.signature(fn)}")
            print(
                "    "
                + " ".join((inspect.getdoc(fn) or "(no docstring)").split())[:300]
            )
        except (TypeError, ValueError):
            print(f"\n--- {name} (signature unavailable)")

scratch = ROOT / "command-center/p2-next/_empty_suite_probe"
try:
    scratch.mkdir(parents=True, exist_ok=True)
    # BAD STATE: an empty directory. pytest exits non-failing over nothing; the floor must reject.
    # collect_count returns (count, tail); require_nonempty(count, label, minimum=1) raises.
    n_bad, tail_bad = suitefloor.collect_count(str(scratch))
    print(f"\nBAD STATE  collect_count(empty dir) = {n_bad} :: {tail_bad!r}")
    OUT["bad_state"] = {"collected": n_bad, "tail": tail_bad}
    try:
        suitefloor.require_nonempty(n_bad, "empty-suite-probe")
        OUT["require_nonempty_on_zero"] = {"raised": False}
        print(
            "   require_nonempty(0) -> did NOT raise  *** the guard would be a no-op ***"
        )
    except Exception as exc:  # noqa: BLE001
        OUT["require_nonempty_on_zero"] = {
            "raised": True,
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(f"   require_nonempty(0) -> RAISED {type(exc).__name__}: {exc}")

    # GOOD STATE: the same guard must stay SILENT on a real, above-floor collection.
    good_suite = suitefloor.SUITES[0]
    gn, gtail = suitefloor.collect_count(good_suite.path)
    ok, cnt, msg = suitefloor.check_suite(good_suite)
    silent_on_good = True
    try:
        suitefloor.require_nonempty(gn, good_suite.name)
    except Exception as exc:  # noqa: BLE001
        silent_on_good = False
        print(
            f"   require_nonempty({gn}) unexpectedly RAISED {type(exc).__name__}: {exc}"
        )
    print(
        f"\nGOOD STATE collect_count({good_suite.path}) = {gn} vs floor {good_suite.minimum}"
    )
    print(f"   check_suite({good_suite.name}) -> ok={ok} count={cnt} :: {msg}")
    print(f"   require_nonempty({gn}) stayed silent: {silent_on_good}")
    OUT["good_state"] = {
        "suite": good_suite.name,
        "path": good_suite.path,
        "collected": gn,
        "floor": good_suite.minimum,
        "check_suite_ok": ok,
        "check_suite_msg": msg,
        "require_nonempty_silent": silent_on_good,
    }
    zero_rejected = n_bad == 0 and OUT["require_nonempty_on_zero"]["raised"]
    OUT["nc2_reproduced"] = bool(zero_rejected and silent_on_good and ok)
    OUT["both_states"] = {
        "fired_on_bad_state (zero collection rejected)": bool(zero_rejected),
        "silent_on_good_state (real suite accepted)": bool(silent_on_good and ok),
    }
    print(f"\nNC2 reproduced (zero collection is rejected): {OUT['nc2_reproduced']}")
    print(f"both states: {json.dumps(OUT['both_states'])}")
finally:
    if scratch.exists():
        shutil.rmtree(scratch, ignore_errors=True)

(ROOT / "command-center/p2-next/REVIEW-TST0350-NC2.json").write_text(
    json.dumps(OUT, indent=2, default=str), encoding="utf-8"
)
print(
    "\nSUCCESS:nc2"
    if OUT.get("nc2_reproduced")
    else "\nPARTIAL:nc2 not cleanly reproduced"
)
