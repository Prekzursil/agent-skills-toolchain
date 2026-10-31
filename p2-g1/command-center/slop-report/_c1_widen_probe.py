"""BUILD R1 -- second instance of the same defect, 20 minutes apart. Measure the class fix.

`command-center/grounding/_s2_*.py` x8 were committed by sibling 1e9cfe81 and turn
gate-lint-format RED at HEAD. My own commit hit the identical wall and was only green because
of the `command-center/_*.py` exclusion. So this is a CLASS defect (evidence probe scripts
under command-center/ are committed unformatted and red the repo-wide gate), not two
coincidences -- and a per-lane whack-a-mole exclusion will keep recurring.

Question: does widening the exclusion from `command-center/_*.py` (root only) to
`command-center/**/_*.py` (the whole class) green the gate, and what else does it swallow?

Blast radius matters: an exclusion that also stops linting real source is a bad trade. So
count the TRACKED files each pattern captures before proposing it.

CONTROLS (both states):
  T1 widened   -> expect GREEN
  T2 unwidened -> expect RED on exactly the 8 grounding files
If both come back the same the harness is inert.
"""

import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
PIN = ["uvx", "ruff@0.15.17"]
OUT = os.path.join(ROOT, "command-center/slop-report/_c1_widen_probe.out.json")
OLD = '    "command-center/_*.py",\n'
NEW = '    "command-center/**/_*.py",\n'


def run(args, cwd):
    r = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout + r.stderr


def fmt_list(text):
    return sorted(
        line.split("Would reformat:", 1)[1].strip().replace("\\", "/")
        for line in text.splitlines()
        if "Would reformat:" in line
    )


def main():
    rev = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    tracked = subprocess.run(
        ["git", "-C", ROOT, "ls-files"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()

    # blast radius: what does each pattern capture among TRACKED .py?
    root_only = [p for p in tracked if fnmatch.fnmatch(p, "command-center/_*.py")]
    widened = [
        p
        for p in tracked
        if p.startswith("command-center/")
        and p.endswith(".py")
        and os.path.basename(p).startswith("_")
    ]
    out = {
        "rev": rev,
        "blast_radius": {
            "pattern_root_only": "command-center/_*.py",
            "n_tracked_root_only": len(root_only),
            "pattern_widened": "command-center/**/_*.py",
            "n_tracked_widened": len(widened),
            "newly_swallowed": sorted(set(widened) - set(root_only)),
            "n_newly_swallowed": len(set(widened) - set(root_only)),
        },
    }

    def measure(widen: bool):
        tmp = tempfile.mkdtemp(prefix="widen_")
        clone = os.path.join(tmp, "repo")
        try:
            rc, t = run(
                [
                    "git",
                    "clone",
                    "--no-hardlinks",
                    "--quiet",
                    "-c",
                    "core.autocrlf=false",
                    "-c",
                    "core.eol=lf",
                    ROOT,
                    clone,
                ],
                tmp,
            )
            if rc != 0:
                return {"clone_rc": rc, "err": t[-400:]}
            run(["git", "checkout", "--quiet", "--detach", rev], clone)
            if widen:
                rt = os.path.join(clone, "ruff.toml")
                with open(rt, "r", encoding="utf-8", newline="") as fh:
                    txt = fh.read()
                eol = "\r\n" if txt.count("\r\n") else "\n"
                old = OLD.replace("\n", eol)
                assert txt.count(old) == 1, f"anchor {txt.count(old)}"
                txt = txt.replace(old, NEW.replace("\n", eol), 1)
                with open(rt, "w", encoding="utf-8", newline="") as fh:
                    fh.write(txt)
            rc_l, t_l = run([*PIN, "check", ".", "--output-format=concise"], clone)
            rc_f, t_f = run([*PIN, "format", "--check", "."], clone)
            w = fmt_list(t_f)
            return {
                "widened": widen,
                "check_rc": rc_l,
                "check_tail": t_l.strip().splitlines()[-2:],
                "format_rc": rc_f,
                "n_would_reformat": len(w),
                "would_reformat": w[:12],
                "green": rc_l == 0 and rc_f == 0,
            }
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    out["T1_widened"] = measure(True)
    out["T2_current"] = measure(False)
    checks = {
        "T1_green": bool(out["T1_widened"].get("green")),
        "T2_red": not out["T2_current"].get("green", True),
        "distinguishable": bool(out["T1_widened"].get("green"))
        != bool(out["T2_current"].get("green", True)),
    }
    out["checks"] = checks
    out["controls_verdict"] = "PASS" if all(checks.values()) else "FAIL"
    out["verdict"] = (
        "WIDENING FIXES IT"
        if checks["T1_green"]
        else "WIDENING INSUFFICIENT -- red has another source"
    )
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1)[:3000])
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
