"""AUDIT R2 probe 4: INDEPENDENT gate measurement -- deliberately NOT the
builder's method.

The builder's `_r2_gate_now.py` measures by `git clone`-ing the repo into a temp
dir. This probe instead materialises the tree by extracting each tracked blob
with `git cat-file -p` (the route windows-shell rule 8b certifies as returning
the stored bytes, 0 CRLF, unlike `git archive`). Two mechanically different
materialisations that agree is a real second signal; a re-run of the builder's
clone would not be.

Question under test (the lane's own stop-ship premise): do the SLOP lane's 6
commits ADD any ruff failure that CI would see?

H1: the slop lane added zero gate failures.
H2: the slop lane committed unformatted/unlinted .py and turned the gate red.

Method: measure ruff (pinned 0.15.17, the CI pin) at the commit BEFORE the
lane's first commit (61e69cf2) and at the lane's last commit (1a3f09f4), over
extracted blobs, with the repo's ruff.toml + every nested pyproject.toml
present, then diff the failing sets.

CONTROLS (each must pass or no reading may be cited):
  K1 CRLF pin  : 0 CRLF bytes across extracted .py. Otherwise `format --check`
                 is measuring line endings, not code.
  K2 config    : ruff.toml AND the nested tools/mcp/patent-search-mcp/
                 pyproject.toml present -- a missing nested config produced a
                 documented FALSE RED in this program before.
  K3 mangle    : a known-clean extracted file, deliberately mangled, MUST make
                 `format --check` fire. A green reading otherwise is
                 indistinguishable from "ruff considered no files".
  K4 nonzero   : ruff must report a plausible number of considered files
                 (>500). A suspiciously small or equal count on both sides is
                 the collection-level mistake this estate has hit before.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

REPO = "C:/Users/Prekzursil/source/ast-integrate"
RUFF = ["uvx", "ruff@0.15.17"]
BEFORE = "61e69cf2"  # parent of the lane's first commit
AFTER = "1a3f09f4"  # the lane's last commit
NESTED_CFG = "tools/mcp/patent-search-mcp/pyproject.toml"


def git(*a, cwd=REPO, binary=False):
    r = subprocess.run(
        ["git", "-C", cwd, *a],
        capture_output=True,
        text=not binary,
        encoding=None if binary else "utf-8",
        errors=None if binary else "replace",
    )
    return r.returncode, r.stdout, r.stderr


def run(cmd, cwd, t=2400):
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


def materialise(rev, dest):
    """Extract every tracked path at `rev` via `git cat-file -p` (stored bytes)."""
    rc, out, _ = git("ls-tree", "-r", "--name-only", rev)
    paths = [p for p in out.splitlines() if p.strip()]
    wanted = [p for p in paths if p.endswith((".py", ".toml", ".cfg", ".ini", ".pyi"))]
    n_crlf = 0
    n_py = 0
    for p in wanted:
        r = subprocess.run(
            ["git", "-C", REPO, "cat-file", "-p", f"{rev}:{p}"],
            capture_output=True,
        )
        if r.returncode != 0:
            continue
        data = r.stdout
        fp = dest / p
        fp.parent.mkdir(parents=True, exist_ok=True)
        with open(fp, "wb") as fh:
            fh.write(data)
        if p.endswith(".py"):
            n_py += 1
            if b"\r\n" in data:
                n_crlf += 1
    return {
        "n_py_extracted": n_py,
        "n_py_with_crlf": n_crlf,
        "n_files_extracted": len(wanted),
    }


def parse_fails(out):
    return sorted(
        ln.split("Would reformat:", 1)[1].strip().replace("\\", "/")
        for ln in out.splitlines()
        if ln.strip().startswith("Would reformat:")
    )


def parse_codes(out):
    return sorted(
        {
            ln.split("title=", 1)[1].split(",", 1)[0]
            for ln in out.splitlines()
            if "title=" in ln
        }
    )


def considered(root):
    rc, out, _ = run(RUFF + ["check", "--show-files", "."], root)
    return {
        ln.strip().replace("\\", "/").replace(str(root).replace("\\", "/") + "/", "")
        for ln in out.splitlines()
        if ln.strip()
    }


def measure(rev, tmp):
    dest = pathlib.Path(tmp) / rev
    dest.mkdir(parents=True, exist_ok=True)
    ext = materialise(rev, dest)
    crc, cso, cse = run(RUFF + ["check", "--output-format=github", "."], dest)
    frc, fso, fse = run(RUFF + ["format", "--check", "."], dest)
    cons = considered(dest)
    res = {
        "rev": rev,
        "extraction": ext,
        "check_rc": crc,
        "check_codes": parse_codes(cso),
        "format_rc": frc,
        "would_reformat": parse_fails(fso),
        "n_would_reformat": len(parse_fails(fso)),
        "n_considered": len(cons),
        "K1_zero_crlf": ext["n_py_with_crlf"] == 0,
        "K2_ruff_toml": (dest / "ruff.toml").is_file(),
        "K2_nested_cfg": (dest / NESTED_CFG).is_file(),
        "K4_considered_plausible": len(cons) > 500,
    }
    # K3 mangle control -- must make format --check fire
    victim = None
    for cand in ["platform/lib/_gen_schema_substrate.py"]:
        if (dest / cand).is_file():
            victim = dest / cand
            break
    if victim is None:
        res["K3_mangle_fires"] = None
    else:
        orig = victim.read_bytes()
        was_failing = cand.replace("\\", "/") in res["would_reformat"]
        victim.write_bytes(b"x   =  1\ndef  f( a ,b ):\n      return    a+b\n")
        mrc, mso, _ = run(RUFF + ["format", "--check", "."], dest)
        now = parse_fails(mso)
        victim.write_bytes(orig)
        res["K3_mangle_fires"] = (cand.replace("\\", "/") in now) and not was_failing
        res["K3_victim"] = cand
    return res


out = {
    "probe": "_aud2_gate_indep",
    "method": "git cat-file -p blob extraction",
    "ruff_pin": "0.15.17",
    "before_rev": BEFORE,
    "after_rev": AFTER,
}

with tempfile.TemporaryDirectory(prefix="aud2gate_") as tmp:
    out["before"] = measure(BEFORE, tmp)
    out["after"] = measure(AFTER, tmp)

b, a = out["before"], out["after"]
set_b, set_a = set(b["would_reformat"]), set(a["would_reformat"])
new_fail = sorted(set_a - set_b)
fixed = sorted(set_b - set_a)
lane_new_fail = [p for p in new_fail if p.startswith("command-center/slop-report/")]

out["new_format_failures"] = new_fail
out["fixed_format_failures"] = fixed
out["new_failures_in_slop_report"] = lane_new_fail
out["check_codes_added"] = sorted(set(a["check_codes"]) - set(b["check_codes"]))
out["considered_delta"] = a["n_considered"] - b["n_considered"]

controls = {
    "K1_before": b["K1_zero_crlf"],
    "K1_after": a["K1_zero_crlf"],
    "K2_before": b["K2_ruff_toml"] and b["K2_nested_cfg"],
    "K2_after": a["K2_ruff_toml"] and a["K2_nested_cfg"],
    "K3_before": b["K3_mangle_fires"],
    "K3_after": a["K3_mangle_fires"],
    "K4_before": b["K4_considered_plausible"],
    "K4_after": a["K4_considered_plausible"],
    "K5_ruff_actually_read_new_files": (a["n_considered"] - b["n_considered"]) > 0,
}
out["controls"] = controls
out["all_controls_pass"] = all(v is True for v in controls.values())

lane_added_failures = bool(new_fail) or bool(out["check_codes_added"])
out["lane_added_gate_failures"] = lane_added_failures
out["verdict"] = (
    "LANE-ADDED-ZERO-GATE-FAILURES"
    if (out["all_controls_pass"] and not lane_added_failures)
    else (
        "CONTROLS-FAILED"
        if not out["all_controls_pass"]
        else "LANE-ADDED-GATE-FAILURES"
    )
)
out["ok"] = out["all_controls_pass"] and not lane_added_failures

with open(
    os.path.join(REPO, "command-center/slop-report/_aud2_gate_indep.out.json"),
    "w",
    encoding="utf-8",
    newline="\n",
) as fh:
    json.dump(out, fh, indent=2)

print(
    json.dumps({k: v for k, v in out.items() if k not in ("before", "after")}, indent=2)
)
print(
    "--- before:",
    {
        k: b[k]
        for k in (
            "check_rc",
            "format_rc",
            "n_would_reformat",
            "n_considered",
            "extraction",
        )
    },
)
print(
    "--- after :",
    {
        k: a[k]
        for k in (
            "check_rc",
            "format_rc",
            "n_would_reformat",
            "n_considered",
            "extraction",
        )
    },
)
sys.exit(0 if out["ok"] else 1)
