"""Adversarial verifier probe 4: the gate at the CURRENT head, and the widen fix re-tested.

HEAD moved four times during this verification (de77c002 -> a435ae7c) and a sibling fixed
the E402 that made `ruff check` red. Re-measuring rather than citing my own 20-minute-old
reading -- the same staleness defect I am reporting in the BUILD.

Controls:
  M1 as-is vs widened must be DISTINGUISHABLE on some axis, else the comparison is inert.
  M2 mangle under BOTH configs must fire, else a green reading cannot be told apart from
     "ruff considered nothing".
  M3 the toml anchor must be present before the edit, else the widen run silently no-ops.
"""

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
RUFF = ["uvx", "ruff@0.15.17"]
OLD = '"command-center/_*.py",'
NEW = '"command-center/**/_*.py",'


def run(c, cwd, t=900):
    p = subprocess.run(c, cwd=str(cwd), capture_output=True, text=True, timeout=t)
    return p.returncode, p.stdout, p.stderr


def pf(o):
    f = [
        ln.split("Would reformat:", 1)[1].strip().replace("\\", "/")
        for ln in o.splitlines()
        if ln.strip().startswith("Would reformat:")
    ]
    return len(f), sorted(f)


def measure(clone, tag):
    crc, cso, _ = run(RUFF + ["check", "--output-format=github", "."], clone)
    frc, fso, _ = run(RUFF + ["format", "--check", "."], clone)
    n, fails = pf(fso)
    codes = sorted(
        {
            ln.split("title=", 1)[1].split(",", 1)[0]
            for ln in cso.splitlines()
            if "title=" in ln
        }
    )
    return {
        "tag": tag,
        "check_rc": crc,
        "check_codes": codes,
        "format_rc": frc,
        "n_would_reformat": n,
        "failing_files": fails,
        "GREEN": crc == 0 and frc == 0,
    }


def considered(clone):
    _, so, _ = run(RUFF + ["check", "--show-files", "."], clone)
    return {ln.strip().replace("\\", "/") for ln in so.splitlines() if ln.strip()}


def mangle_fires(clone):
    v = clone / "platform/lib/_gen_schema_substrate.py"
    ob = v.read_bytes()
    v.write_bytes(ob.replace(b"import ", b"import  ", 1))
    frc, fso, _ = run(RUFF + ["format", "--check", "."], clone)
    _, f = pf(fso)
    v.write_bytes(ob)
    return frc == 1 and "platform/lib/_gen_schema_substrate.py" in f


def main():
    rev = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    tmp = tempfile.mkdtemp(prefix="ver4_")
    clone = pathlib.Path(tmp) / "c"
    res = {"rev_measured": rev}
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
        print(json.dumps({"clone_err": se[-1000:]}))
        return 1
    run(["git", "checkout", "-f", rev], clone)

    res["A_as_is"] = measure(clone, "current HEAD, committed ruff.toml")
    set_a = considered(clone)
    res["M2a_mangle_fires_as_is"] = mangle_fires(clone)

    toml = clone / "ruff.toml"
    o = toml.read_text(encoding="utf-8")
    res["M3_anchor_present"] = OLD in o
    toml.write_text(o.replace(OLD, NEW, 1), encoding="utf-8", newline="\n")
    res["B_widened"] = measure(clone, "widened command-center/**/_*.py")
    set_b = considered(clone)
    res["M2b_mangle_fires_widened"] = mangle_fires(clone)

    left = set_a - set_b
    res["files_leaving_the_gate"] = {
        "n": len(left),
        "n_added": len(set_b - set_a),
        "considered_as_is": len(set_a),
        "considered_widened": len(set_b),
        "non_underscore_basenames": sorted(
            {
                p.rsplit("/", 1)[-1]
                for p in left
                if not p.rsplit("/", 1)[-1].startswith("_")
            }
        )[:10],
    }
    res["M1_states_distinguishable"] = (
        res["A_as_is"]["n_would_reformat"] != res["B_widened"]["n_would_reformat"]
        or len(left) > 0
    )
    res["all_controls_pass"] = all(
        [
            res["M1_states_distinguishable"],
            res["M2a_mangle_fires_as_is"],
            res["M2b_mangle_fires_widened"],
            res["M3_anchor_present"],
        ]
    )
    pathlib.Path(__file__).with_suffix(".out.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(res, indent=2)[:4000])
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
