"""Adversarial verifier probe 1: replicate the real CI gate in a fresh LF clone.

Replicates .github/workflows/quality.yml:90-93 exactly:
    ruff check --output-format=github .
    ruff format --check .
with the CI pin ruff==0.15.17 (via uvx).

Measures at every revision boundary that matters for the BUILD's published claim
and the AUDIT's D1 counter-claim. Carries three controls:
  C1 EOL pin      -- 0 CRLF among tracked .py, else the clone is not the CI checkout
  C2 nested cfg   -- the nested tools/mcp/patent-search-mcp/pyproject.toml is PRESENT
                     (its absence is what produced the BUILD's false red)
  C3 mangle       -- a known-clean file, mangled, must make `format --check` go RED
                     (both-states: if it does not fire, silence means nothing)
"""

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
RUFF = ["uvx", "ruff@0.15.17"]
REVS = [
    ("fa87d1a2", "build commit 2 -- where the build MEASURED the 8-file reading"),
    ("df6377ab", "sibling SSOT commit -- parent of the build's commit 3"),
    ("ebe02d62", "build commit 3 -- where the build PUBLISHED the 8-file reading"),
    ("de77c002", "HEAD at verifier start"),
]


def run(cmd, cwd, timeout=900):
    p = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, shell=False, timeout=timeout
    )
    return p.returncode, p.stdout, p.stderr


def parse_format(out):
    """Return (n_would_reformat, sorted failing paths) from `ruff format --check`."""
    fails = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Would reformat:"):
            fails.append(line.split("Would reformat:", 1)[1].strip().replace("\\", "/"))
    return len(fails), sorted(fails)


def parse_check(out):
    codes = set()
    for line in out.splitlines():
        # github format: ::error title=RUF001,file=...
        if "title=" in line:
            seg = line.split("title=", 1)[1]
            codes.add(seg.split(",", 1)[0].strip())
    return sorted(codes)


def main():
    tmp = tempfile.mkdtemp(prefix="ver1_clone_")
    clone = pathlib.Path(tmp) / "c"
    res = {"clone_root": str(clone), "revs": {}, "controls": {}}

    rc, so, se = run(
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
    res["clone_rc"] = rc
    if rc != 0:
        res["clone_err"] = se[-2000:]
        print(json.dumps(res, indent=2))
        return 1

    for rev, why in REVS:
        rc, so, se = run(["git", "checkout", "-f", rev], clone)
        entry = {"why": why, "checkout_rc": rc}
        if rc != 0:
            entry["checkout_err"] = se[-800:]
            res["revs"][rev] = entry
            continue
        crc, cso, cse = run(RUFF + ["check", "--output-format=github", "."], clone)
        frc, fso, fse = run(RUFF + ["format", "--check", "."], clone)
        n, fails = parse_format(fso)
        entry.update(
            {
                "check_rc": crc,
                "check_codes": parse_check(cso),
                "check_tail": (cso + cse).strip().splitlines()[-3:],
                "format_rc": frc,
                "n_would_reformat": n,
                "failing_files": fails,
            }
        )
        res["revs"][rev] = entry

    # --- controls, all evaluated at HEAD ---
    run(["git", "checkout", "-f", "de77c002"], clone)

    tracked = run(["git", "ls-files", "*.py"], clone)[1].split()
    crlf = 0
    for rel in tracked:
        p = clone / rel
        try:
            if b"\r\n" in p.read_bytes():
                crlf += 1
        except OSError:
            pass
    res["controls"]["C1_eol_pin"] = {
        "tracked_py": len(tracked),
        "files_with_crlf": crlf,
        "pass": crlf == 0 and len(tracked) > 100,
    }

    cfgs = run(["git", "ls-files", "*pyproject.toml", "*ruff.toml"], clone)[1].split()
    nested = "tools/mcp/patent-search-mcp/pyproject.toml"
    res["controls"]["C2_nested_config"] = {
        "n_configs": len(cfgs),
        "nested_present": (clone / nested).exists(),
        "pass": (clone / nested).exists() and len(cfgs) > 1,
    }

    victim = clone / "platform/lib/_gen_schema_substrate.py"
    if victim.exists():
        orig = victim.read_bytes()
        victim.write_bytes(orig.replace(b"import ", b"import  ", 1))
        frc, fso, _ = run(RUFF + ["format", "--check", "."], clone)
        n2, f2 = parse_format(fso)
        res["controls"]["C3_mangle"] = {
            "victim": "platform/lib/_gen_schema_substrate.py",
            "format_rc": frc,
            "victim_in_failset": "platform/lib/_gen_schema_substrate.py" in f2,
            "pass": frc == 1 and "platform/lib/_gen_schema_substrate.py" in f2,
        }
        victim.write_bytes(orig)
    else:
        res["controls"]["C3_mangle"] = {"pass": False, "err": "victim missing"}

    res["all_controls_pass"] = all(c.get("pass") for c in res["controls"].values())
    out = pathlib.Path(__file__).with_suffix(".out.json")
    out.write_text(json.dumps(res, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(res, indent=2)[:6000])
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
