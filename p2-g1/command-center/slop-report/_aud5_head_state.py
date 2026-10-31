"""AUDIT probe 5: the ACTUAL state of HEAD, and whether the owner-facing fix works.

Probe 3 found HEAD is red on 14 files and `ruff check` is red too -- not the 8-format-only
the builder's committed artifact reports. So:
  (1) enumerate the lint errors (probe 3 used --output-format=github, which prints no
      "Found N errors" line -- my regex returned null, a detector gap in MY probe 3);
  (2) attribute every one of the 14 format failures to the commit that added the file;
  (3) TEST the builder's owner-facing recommendation -- widen the exclusion to
      `command-center/**/_*.py` -- and see whether it actually turns HEAD green.
Control: a mangled clean file must still make both gates fire under the widened exclusion,
so a green there cannot be the exclusion swallowing the whole repo.
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = "C:/Users/Prekzursil/source/ast-integrate"
RUFF = ["uvx", "ruff@0.15.17"]
out = {}


def run(args, cwd, timeout=1200):
    r = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return r.returncode, r.stdout, r.stderr


def gate(clone):
    crc, cso, cse = run(
        [*RUFF, "check", "."], clone
    )  # DEFAULT format -> prints "Found N errors."
    m = re.search(r"Found (\d+) error", cso + cse)
    codes = sorted(set(re.findall(r"\b([A-Z]{1,4}\d{3,4})\b", cso)))
    files_lint = sorted(
        {
            ln.split(":")[0].strip()
            for ln in cso.splitlines()
            if re.match(r"^\S+\.py:\d+:\d+:", ln)
        }
    )
    frc, fso, fse = run([*RUFF, "format", "--check", "."], clone)
    fails = sorted(
        {
            ln.split("Would reformat:", 1)[1].strip()
            for ln in (fso + fse).splitlines()
            if "Would reformat:" in ln
        }
    )
    return {
        "check_rc": crc,
        "check_errors": int(m.group(1)) if m else None,
        "lint_codes": codes,
        "lint_files": files_lint,
        "format_rc": frc,
        "n_would_reformat": len(fails),
        "would_reformat": fails,
        "green": crc == 0 and frc == 0,
    }


tmp = Path(tempfile.mkdtemp(prefix="aud5_"))
clone = tmp / "repo"
rc, _, se = run(
    [
        "git",
        "clone",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.eol=lf",
        "--no-hardlinks",
        REPO,
        str(clone),
    ],
    str(tmp),
)
out["clone_rc"] = rc
run(["git", "checkout", "--force", "ebe02d62"], str(clone))

# ---- A: HEAD as-is, with full lint detail ----
a = gate(str(clone))
out["A_head_as_is"] = a

# ---- B: attribute each format failure to the commit that ADDED the file ----
attrib = {}
for f in a["would_reformat"]:
    rel = f.replace("\\", "/")
    rc, so, _ = run(
        ["git", "log", "--format=%h %s", "--diff-filter=A", "--", rel], str(clone)
    )
    lines = [x for x in so.splitlines() if x.strip()]
    attrib[rel] = lines[-1] if lines else "?"
out["B_format_failure_attribution"] = attrib
lane = {"f5b596e6", "fa87d1a2", "ebe02d62"}
out["B_any_failure_from_this_lane"] = [
    k for k, v in attrib.items() if v.split()[0] in lane
]

# ---- C: the owner-facing recommendation -- widen the exclusion ----
rt = clone / "ruff.toml"
orig = rt.read_bytes()
txt = orig.decode("utf-8")
widened = txt.replace('"command-center/_*.py",', '"command-center/**/_*.py",')
out["C_widen"] = {"substitution_applied": widened != txt}
rt.write_bytes(widened.encode("utf-8"))
c = gate(str(clone))
out["C_widen"].update(
    {
        "check_rc": c["check_rc"],
        "check_errors": c["check_errors"],
        "format_rc": c["format_rc"],
        "n_would_reformat": c["n_would_reformat"],
        "residual_failures": c["would_reformat"],
        "green": c["green"],
        "builder_claim_widening_makes_it_green": c["green"],
    }
)

# CONTROL for C: under the widened exclusion, a mangled NON-command-center file must still fire.
victim = "platform/lib/_gen_schema_substrate.py"
vp = clone / victim
vorig = vp.read_bytes()
vp.write_bytes(vorig + b"\n\n\ny    =    2\n")
cc = gate(str(clone))
vp.write_bytes(vorig)
out["C_widen"]["control_mangle_still_fires"] = {
    "format_rc": cc["format_rc"],
    "victim_in_failset": any(
        victim in f.replace("\\", "/") for f in cc["would_reformat"]
    ),
    "pass": cc["format_rc"] != 0,
}
rt.write_bytes(orig)

# ---- D: how many tracked files would the widened exclusion remove from the gate? ----
rc, so, _ = run(["git", "ls-files", "command-center/"], str(clone))
n_wide = len(
    [
        x
        for x in so.splitlines()
        if re.match(r"^command-center/(.*/)?_[A-Za-z0-9_]+\.py$", x)
    ]
)
n_narrow = len(
    [x for x in so.splitlines() if re.match(r"^command-center/_[A-Za-z0-9_]+\.py$", x)]
)
out["D_exclusion_blast_radius"] = {
    "tracked_matching_narrow_current": n_narrow,
    "tracked_matching_widened": n_wide,
    "builder_claimed_widened": 144,
}

print(json.dumps(out, indent=2))
Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
shutil.rmtree(tmp, ignore_errors=True)
