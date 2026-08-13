"""BUILD R2 / D1 -- the rev-anchored, re-runnable gate reading.

D1 (CONFIRMED by the auditor): round 1 committed `ebe02d62` whose stated purpose was to
publish a fresh post-commit gate reading -- "8 red files, format-only" -- and that reading was
already false at the commit it was published into (14 format failures + an E402). The verifier
then showed the AUDITOR's replacement numbers were stale too, two commits later. Three
successive readings of a moving tree, each published as a standing fact.

The durable fix is not a better number. It is:
  (a) every number carries the rev it was measured at, and
  (b) the measurement is a COMMITTED, re-runnable command, so a reader who needs today's
      answer runs it instead of trusting a timestamp.

This is that command. `python command-center/slop-report/_r2_gate_now.py [--rev <rev>]`
replicates quality.yml:90-93 (`ruff check .` / `ruff format --check .`, ruff pinned 0.15.17)
in a FRESH LF clone -- never the worktree, whose ruff readings this lane already proved
non-load-bearing -- and also re-measures the "widen the exclusion" blast radius.

Controls (all must pass or no reading may be cited):
  C1 EOL pin   : 0 CRLF across tracked .py in the clone. Without this the format verdict is
                 measuring line endings, not code.
  C2 nested cfg: tools/mcp/patent-search-mcp/pyproject.toml present. Its absence is what made
                 round 1's first gate probe report a FALSE RED.
  C3 mangle    : a known-clean file, mangled, must make `format --check` fire -- under BOTH the
                 as-is and the widened config. A green reading otherwise cannot be told apart
                 from "ruff considered nothing".
  C4 subset    : the widened file set must be a strict subset of the as-is set (0 added), else
                 the set-difference arithmetic is not measuring an exclusion.
  C5 anchor    : the string being replaced must exist in ruff.toml, else the widen run no-ops
                 and silently reports "no change".
"""

import argparse
import datetime
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
MANGLE_VICTIM = "platform/lib/_gen_schema_substrate.py"
NESTED_CFG = "tools/mcp/patent-search-mcp/pyproject.toml"


def run(cmd, cwd, t=1800):
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=t,
    )
    return p.returncode, p.stdout, p.stderr


def parse_fails(out):
    f = [
        ln.split("Would reformat:", 1)[1].strip().replace("\\", "/")
        for ln in out.splitlines()
        if ln.strip().startswith("Would reformat:")
    ]
    return len(f), sorted(f)


def measure(clone, tag):
    crc, cso, _ = run(RUFF + ["check", "--output-format=github", "."], clone)
    frc, fso, _ = run(RUFF + ["format", "--check", "."], clone)
    n, fails = parse_fails(fso)
    codes = sorted(
        {
            ln.split("title=", 1)[1].split(",", 1)[0]
            for ln in cso.splitlines()
            if "title=" in ln
        }
    )
    lint_lines = [ln for ln in cso.splitlines() if ln.startswith("::error")][:10]
    return {
        "tag": tag,
        "check_rc": crc,
        "check_codes": codes,
        "check_first_errors": lint_lines,
        "format_rc": frc,
        "n_would_reformat": n,
        "failing_files": fails,
        "GREEN": crc == 0 and frc == 0,
    }


def considered(clone):
    _, so, _ = run(RUFF + ["check", "--show-files", "."], clone)
    return {ln.strip().replace("\\", "/") for ln in so.splitlines() if ln.strip()}


def mangle_fires(clone):
    v = clone / MANGLE_VICTIM
    if not v.exists():
        return False
    ob = v.read_bytes()
    v.write_bytes(ob.replace(b"import ", b"import  ", 1))
    frc, fso, _ = run(RUFF + ["format", "--check", "."], clone)
    _, f = parse_fails(fso)
    v.write_bytes(ob)
    return frc == 1 and MANGLE_VICTIM in f


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--rev", default=None, help="rev to measure (default: current HEAD)"
    )
    args = ap.parse_args(argv)

    rev = (
        args.rev
        or subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    rev = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", rev], capture_output=True, text=True
    ).stdout.strip()

    res = {
        "rev_measured": rev,
        "measured_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"
        ),
        "gate_replicated": "quality.yml:90-93 (ruff==0.15.17: check . / format --check .)",
    }

    tmp = tempfile.mkdtemp(prefix="r2gate_")
    clone = pathlib.Path(tmp) / "c"
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

    # ---- C1 EOL pin --------------------------------------------------------
    _, lsf, _ = run(["git", "ls-files", "--", "*.py"], clone)
    tracked_py = [p for p in lsf.splitlines() if p.strip()]
    crlf = 0
    for rel in tracked_py:
        fp = clone / rel
        try:
            if b"\r\n" in fp.read_bytes():
                crlf += 1
        except OSError:
            pass
    res["C1_eol_pin"] = {
        "tracked_py": len(tracked_py),
        "files_with_crlf": crlf,
        "pass": crlf == 0 and len(tracked_py) > 0,
    }
    res["C2_nested_config_present"] = (clone / NESTED_CFG).exists()

    # ---- as-is -------------------------------------------------------------
    res["A_as_is"] = measure(clone, "committed ruff.toml")
    set_a = considered(clone)
    res["C3a_mangle_fires_as_is"] = mangle_fires(clone)

    # ---- widened -----------------------------------------------------------
    toml = clone / "ruff.toml"
    txt = toml.read_text(encoding="utf-8")
    res["C5_anchor_present"] = OLD in txt
    toml.write_text(txt.replace(OLD, NEW, 1), encoding="utf-8", newline="\n")
    res["B_widened"] = measure(clone, "widened to command-center/**/_*.py")
    set_b = considered(clone)
    res["C3b_mangle_fires_widened"] = mangle_fires(clone)

    left = sorted(set_a - set_b)
    added = sorted(set_b - set_a)
    _, lst, _ = run(
        ["git", "ls-tree", "-r", "--name-only", rev, "--", "command-center"], clone
    )
    ls_match = [
        p
        for p in lst.splitlines()
        if p.rsplit("/", 1)[-1].startswith("_") and p.endswith(".py")
    ]
    res["blast_radius_widen"] = {
        "n_files_leaving_the_gate": len(left),
        "n_files_added": len(added),
        "considered_as_is": len(set_a),
        "considered_widened": len(set_b),
        "independent_signal_ls_tree_underscore_py": len(ls_match),
        "delta_vs_ls_tree": len(left) - len(ls_match),
        "non_underscore_basenames_swept_in": sorted(
            {
                p.rsplit("/", 1)[-1]
                for p in left
                if not p.rsplit("/", 1)[-1].startswith("_")
            }
        )[:12],
    }
    res["C4_widened_is_strict_subset"] = len(added) == 0

    res["controls"] = {
        "C1_eol_pin": res["C1_eol_pin"]["pass"],
        "C2_nested_config": res["C2_nested_config_present"],
        "C3a_mangle_as_is": res["C3a_mangle_fires_as_is"],
        "C3b_mangle_widened": res["C3b_mangle_fires_widened"],
        "C4_strict_subset": res["C4_widened_is_strict_subset"],
        "C5_anchor": res["C5_anchor_present"],
    }
    res["all_controls_pass"] = all(res["controls"].values())

    a = res["A_as_is"]
    res["banner"] = (
        f"gate @ {rev[:8]} ({res['measured_utc']}): ruff check rc={a['check_rc']}"
        f"{' ' + ','.join(a['check_codes']) if a['check_codes'] else ''}, "
        f"format --check rc={a['format_rc']} with {a['n_would_reformat']} would-reformat. "
        f"THIS TREE MOVES -- re-run `python command-center/slop-report/_r2_gate_now.py` "
        f"before citing this line."
    )

    pathlib.Path(__file__).with_suffix(".out.json").write_text(
        json.dumps(res, indent=1), encoding="utf-8", newline="\n"
    )
    print(json.dumps(res, indent=1)[:6000])
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if res["all_controls_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
