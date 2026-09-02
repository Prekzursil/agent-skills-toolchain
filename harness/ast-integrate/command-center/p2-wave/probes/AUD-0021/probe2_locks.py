#!/usr/bin/env python3
"""Probe 2: lockfile integrity hashes plus npm ls --all exit status.

Catalog control: corrupt one integrity hash in a fixture lock; the checker
must exit non-zero and name that package, and stay silent on the clean copy.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

OUT = HERE / "probe2-locks.json"
CHECKER = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0021/inventory.py check-lock"
)


def run_checker(rel_lock: str) -> tuple[int, str]:
    cmd = f"{CHECKER} {rel_lock} --kind package-lock.json"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def main() -> int:
    live = I.inventory_locks()
    ctl = I.control_fixtures()
    bad_rel = "command-center/p2-wave/probes/AUD-0021/fixture-lock-corrupt.json"
    good_rel = "command-center/p2-wave/probes/AUD-0021/fixture-lock-good.json"
    rc_bad, out_bad = run_checker(bad_rel)
    rc_good, out_good = run_checker(good_rel)

    named_in_subprocess = []
    try:
        blob = json.loads(out_bad[out_bad.find("{") : out_bad.rfind("}") + 1])
        named_in_subprocess = list(blob.get("malformed_integrity") or [])
    except Exception:  # noqa: BLE001
        named_in_subprocess = [
            n for n in ctl["victim_named"] if n and n in out_bad
        ]

    subprocess_fired = rc_bad != 0 and bool(named_in_subprocess)
    subprocess_silent = rc_good == 0
    control_ok = (
        ctl["fired"]
        and ctl["silent"]
        and ctl["desync_fired"]
        and ctl["desync_silent"]
        and subprocess_fired
        and subprocess_silent
        and bool(ctl["victim_named"])
    )

    payload = {
        **live,
        "negative_control": {
            "id": "AUD-0021-C1",
            "kind": "mutation",
            "description": (
                "corrupt ONE integrity hash in a fixture copy of a real lock and "
                "require the checker to exit non-zero and name that package"
            ),
            "fired_on_bad_state": ctl["fired"] and subprocess_fired,
            "silent_on_good_state": ctl["silent"] and subprocess_silent,
            "victim_named": ctl["victim_named"],
            "subprocess_corrupt_exit": rc_bad,
            "subprocess_clean_exit": rc_good,
            "subprocess_named": named_in_subprocess,
            "bad_state_output": out_bad[-2000:],
            "good_state_output": out_good[-2000:],
            "checker_command": CHECKER,
        },
        "desync_control": {
            "id": "AUD-0021-C2",
            "kind": "mutation",
            "description": (
                "plant a declared dependency absent from the lock; integrity "
                "alone cannot see this"
            ),
            "fired_on_bad_state": ctl["desync_fired"],
            "silent_on_good_state": ctl["desync_silent"],
            "bad_state_output": ctl["desync_bad"],
            "good_state_output": ctl["desync_good"],
        },
        "pass": control_ok,
    }
    OUT.write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = {
        "lock_count": live["lock_count"],
        "failing_integrity": live["failing_integrity"],
        "desynced": live["desynced"],
        "manifests_without_a_lock": len(live["manifests_without_a_lock"]),
        "npm_binary": live["npm_binary"],
        "npm_ls_exits": [
            {"dir": r["dir"], "exit_code": r["exit_code"], "problems": r["problem_count"]}
            for r in live["npm_ls"]
        ],
        "control_victim": ctl["victim_named"],
        "control_ok": control_ok,
        "checker_corrupt_rc": rc_bad,
        "checker_clean_rc": rc_good,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not control_ok:
        print("FAILED:AUD-0021-probe2 integrity/desync control did not discriminate")
        print(f"  fired={ctl['fired']} silent={ctl['silent']} victim={ctl['victim_named']}")
        print(f"  subprocess rc_bad={rc_bad} rc_good={rc_good} named={named_in_subprocess}")
        print(f"  desync fired={ctl['desync_fired']} silent={ctl['desync_silent']}")
        return 1
    print(
        "SUCCESS:AUD-0021-probe2 locks={0} failing_integrity={1} victim={2} "
        "checker_corrupt_rc={3}".format(
            live["lock_count"],
            live["failing_integrity"],
            ctl["victim_named"],
            rc_bad,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
