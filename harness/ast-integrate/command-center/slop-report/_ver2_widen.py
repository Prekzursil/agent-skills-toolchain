"""Adversarial verifier probe 2: does the BUILD's handed-back fix actually work?

The BUILD's residual (and ebe02d62's commit message) offers the owner two candidate
fixes for the red gate, and states the blast radius of the second as "144 tracked
files leave the gate":

    (i)  ruff format the 8 files        -> 8 files change bytes, 144 stay linted
    (ii) widen the exclusion to `command-center/**/_*.py` -> green

This probe EXECUTES (ii) at HEAD in an isolated clone, by editing the committed
ruff.toml the way the owner would -- NOT via `--extend-exclude` on the CLI, which
REPLACES the toml list instead of adding to it (that is the mistake that produced the
AUDIT's own discarded _aud7 reading).

Controls:
  K1 as-is baseline must be RED   -- if HEAD were already green there is nothing to fix
                                     and both states would look the same.
  K2 mangle-under-widened         -- a mangled platform/lib file must STILL fire under the
                                     widened config. Without this, "format_rc 0" cannot be
                                     told apart from "the exclusion swallowed the repo".
  K3 exclusion actually took      -- the set of files ruff considers must SHRINK; if it does
                                     not, the toml edit silently did nothing.
"""

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
RUFF = ["uvx", "ruff@0.15.17"]
REV = "de77c002"
OLD_GLOB = '"command-center/_*.py",'
NEW_GLOB = '"command-center/**/_*.py",'


def run(cmd, cwd, timeout=900):
    p = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
    )
    return p.returncode, p.stdout, p.stderr


def parse_format(out):
    f = [
        ln.split("Would reformat:", 1)[1].strip().replace("\\", "/")
        for ln in out.splitlines()
        if ln.strip().startswith("Would reformat:")
    ]
    return len(f), sorted(f)


def parse_check(out):
    codes = {}
    for ln in out.splitlines():
        if "title=" in ln:
            c = ln.split("title=", 1)[1].split(",", 1)[0].strip()
            codes[c] = codes.get(c, 0) + 1
    return codes


def considered(clone):
    rc, so, _ = run(RUFF + ["check", "--show-files", "."], clone)
    return {ln.strip().replace("\\", "/") for ln in so.splitlines() if ln.strip()}


def measure(clone, tag):
    crc, cso, cse = run(RUFF + ["check", "--output-format=github", "."], clone)
    frc, fso, _ = run(RUFF + ["format", "--check", "."], clone)
    n, fails = parse_format(fso)
    codes = parse_check(cso)
    return {
        "tag": tag,
        "check_rc": crc,
        "check_codes": codes,
        "check_detail": [
            ln.split("::")[-1] for ln in cso.splitlines() if "title=" in ln
        ][:5],
        "format_rc": frc,
        "n_would_reformat": n,
        "failing_files": fails,
        "GREEN": crc == 0 and frc == 0,
    }


def main():
    tmp = tempfile.mkdtemp(prefix="ver2_widen_")
    clone = pathlib.Path(tmp) / "c"
    res = {"rev": REV}
    rc, _, se = run(
        [
            "git",
            "clone",
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.eol=lf",
            "--no-checkout",
            str(REPO),
            str(clone),
        ],
        REPO,
    )
    if rc != 0:
        print(json.dumps({"clone_err": se[-1500:]}))
        return 1
    run(["git", "checkout", "-f", REV], clone)

    toml = clone / "ruff.toml"
    orig = toml.read_text(encoding="utf-8")
    res["old_glob_present"] = OLD_GLOB in orig

    res["A_as_is"] = measure(clone, "as-is (HEAD, committed ruff.toml)")
    set_as_is = considered(clone)

    # --- apply the owner-facing fix the way an owner would: edit the toml ---
    assert OLD_GLOB in orig, "anchor missing -- edit would have silently no-opped"
    toml.write_text(orig.replace(OLD_GLOB, NEW_GLOB, 1), encoding="utf-8", newline="\n")
    res["B_widened"] = measure(clone, "widened to command-center/**/_*.py")
    set_widen = considered(clone)

    left = sorted(set_as_is - set_widen)
    added = sorted(set_widen - set_as_is)
    res["K3_exclusion_took"] = {
        "n_considered_as_is": len(set_as_is),
        "n_considered_widened": len(set_widen),
        "n_files_leaving_the_gate": len(left),
        "n_files_added": len(added),
        "strict_subset": len(added) == 0 and len(left) > 0,
        "sample_leaving": [p.split("/command-center/")[-1] for p in left[:6]],
        "non_underscore_leavers": [
            p for p in left if not p.rsplit("/", 1)[-1].startswith("_")
        ][:8],
        "pass": len(added) == 0 and len(left) > 0,
    }

    # K2: under the WIDENED config, a mangled non-excluded file must still fire.
    victim = clone / "platform/lib/_gen_schema_substrate.py"
    ob = victim.read_bytes()
    victim.write_bytes(ob.replace(b"import ", b"import  ", 1))
    frc, fso, _ = run(RUFF + ["format", "--check", "."], clone)
    n2, f2 = parse_format(fso)
    res["K2_mangle_under_widened"] = {
        "format_rc": frc,
        "victim_in_failset": "platform/lib/_gen_schema_substrate.py" in f2,
        "pass": frc == 1 and "platform/lib/_gen_schema_substrate.py" in f2,
    }
    victim.write_bytes(ob)

    res["K1_as_is_is_red"] = {
        "check_rc": res["A_as_is"]["check_rc"],
        "format_rc": res["A_as_is"]["format_rc"],
        "pass": not res["A_as_is"]["GREEN"],
    }

    res["ANSWER_widening_makes_gate_green"] = res["B_widened"]["GREEN"]
    res["all_controls_pass"] = all(
        res[k]["pass"]
        for k in ("K1_as_is_is_red", "K2_mangle_under_widened", "K3_exclusion_took")
    )
    pathlib.Path(__file__).with_suffix(".out.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(res, indent=2)[:5000])
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
