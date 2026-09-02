"""BUILD R2 / O2 -- reconcile the two blast-radius signals instead of reporting a bare delta.

`_r2_gate_now.out.json` reports two numbers that disagree at rev f009c680:
  208 files leave the gate   (ruff check --show-files, as-is set MINUS widened set)
  247 tracked `_*.py` under command-center (git ls-tree)
delta = -39. An unexplained delta between two signals is a detector-failure smell, so this
decomposes it. If the arithmetic does not close exactly, the number must not be published.

Hypothesis: 208 = (247 underscore-basename files) - (those ALREADY excluded by the committed
config, i.e. the 45 root `command-center/_*.py`) + (non-underscore files the widened glob
sweeps in through a DIRECTORY component, e.g. command-center/p2-wave/_av2_tmp/probe_*.py).

Control: the decomposition must be exact (residual 0). A near-miss is a refutation, not a
rounding error.
"""

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = pathlib.Path(__file__).with_suffix(".out.json")
GATE = pathlib.Path(__file__).with_name("_r2_gate_now.out.json")


def git(*args):
    p = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.stdout


def main():
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    rev = gate["rev_measured"]
    measured_leaving = gate["blast_radius_widen"]["n_files_leaving_the_gate"]

    tracked = [
        p
        for p in git(
            "ls-tree", "-r", "--name-only", rev, "--", "command-center"
        ).splitlines()
        if p.endswith(".py")
    ]
    underscore = [p for p in tracked if p.rsplit("/", 1)[-1].startswith("_")]
    root_probes = [
        p
        for p in underscore
        if p.count("/")
        == 1  # command-center/_x.py -- already excluded by the committed rule
    ]
    nonroot_underscore = [p for p in underscore if p.count("/") > 1]
    # non-underscore files swept in through a directory component whose name starts with "_"
    swept_dirs = [
        p
        for p in tracked
        if not p.rsplit("/", 1)[-1].startswith("_")
        and any(seg.startswith("_") for seg in p.split("/")[:-1])
    ]

    predicted = len(nonroot_underscore) + len(swept_dirs)
    out = {
        "rev": rev,
        "measured_leaving_the_gate": measured_leaving,
        "tracked_py_under_command_center": len(tracked),
        "underscore_basename_total": len(underscore),
        "already_excluded_root_probes": len(root_probes),
        "nonroot_underscore": len(nonroot_underscore),
        "nonunderscore_swept_via_dir_component": len(swept_dirs),
        "swept_dir_examples": sorted(swept_dirs)[:8],
        "predicted_leaving": predicted,
        "residual": measured_leaving - predicted,
        "arithmetic_closes_exactly": measured_leaving == predicted,
    }
    out["decomposition"] = (
        f"{len(underscore)} underscore-basename - {len(root_probes)} already-excluded root "
        f"= {len(nonroot_underscore)}; + {len(swept_dirs)} non-underscore swept in through a "
        f"'_'-prefixed DIRECTORY component = {predicted}"
    )
    out["verdict"] = (
        "RECONCILED" if out["arithmetic_closes_exactly"] else "UNRECONCILED"
    )
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))
    return 0 if out["arithmetic_closes_exactly"] else 1


if __name__ == "__main__":
    sys.exit(main())
