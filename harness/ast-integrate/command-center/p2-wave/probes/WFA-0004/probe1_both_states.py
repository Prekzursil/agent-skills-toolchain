#!/usr/bin/env python3
"""Probe 1: both-states control for the one-sided compat CI invariant.

Green: symmetrised library, invariant ok.
Red: one reciprocal declaration removed, invariant not ok, CLI --expect-red.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from wfa_compat.check import drop_one_reciprocal, run_invariant  # noqa: E402
from wfa_compat.library import (  # noqa: E402
    library_from_adj,
    load_or_reconstruct,
    symmetrise,
)


def dump_lib(path: Path, adj: dict[str, set[str]]) -> None:
    path.write_text(
        json.dumps(
            library_from_adj(adj, origin="probe1-temp"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    loaded = load_or_reconstruct(REPO)
    after = symmetrise(loaded["adj"])
    green = run_invariant(after)
    if not green["ok"]:
        print(
            json.dumps(
                {"pass": False, "why": "symmetrised-not-green", "green": green},
                sort_keys=True,
                default=str,
            )
        )
        print("FAILED:WFA-0004-probe1 symmetrised library did not pass invariant")
        return 1

    mutated = drop_one_reciprocal(after)
    red = run_invariant(mutated)
    if red["ok"] or int(red["onesided"]) < 1:
        print(
            json.dumps(
                {"pass": False, "why": "mutation-stayed-green", "red": red},
                sort_keys=True,
                default=str,
            )
        )
        print("FAILED:WFA-0004-probe1 dropping one reciprocal did not go red")
        return 1

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "tools")
    cli = [sys.executable, "-B", str(REPO / "tools" / "wfa_compat" / "check.py")]
    with tempfile.TemporaryDirectory(prefix="wfa0004-p1-") as raw:
        tmp = Path(raw)
        good = tmp / "good.json"
        bad = tmp / "bad.json"
        dump_lib(good, after)
        dump_lib(bad, mutated)
        g = subprocess.run(
            cli + ["--library", str(good)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
        )
        b = subprocess.run(
            cli + ["--library", str(bad), "--expect-red"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
        )
        if g.returncode != 0 or b.returncode != 0:
            print(
                json.dumps(
                    {
                        "pass": False,
                        "why": "cli-mismatch",
                        "green_cli": g.returncode,
                        "red_cli": b.returncode,
                        "green_out": ((g.stdout or "") + (g.stderr or ""))[-800:],
                        "red_out": ((b.stdout or "") + (b.stderr or ""))[-800:],
                    },
                    sort_keys=True,
                )
            )
            print("FAILED:WFA-0004-probe1 CLI both-states")
            return 1

    payload = {
        "pass": True,
        "probe": "probe1-both-states",
        "unit_id": "WFA-0004",
        "origin": loaded["origin"],
        "green_ok": True,
        "red_onesided": red["onesided"],
        "cli_green_exit": 0,
        "cli_red_expect_red_exit": 0,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0004-probe1 both-states: invariant green; "
        "one reciprocal removed goes red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
