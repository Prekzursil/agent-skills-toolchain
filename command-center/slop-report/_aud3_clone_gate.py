"""AUDIT probe 3: replicate the REAL CI gate-lint-format in a fresh LF clone.

CI (.github/workflows/quality.yml:86-93) does exactly:
    pip install ruff==0.15.17
    ruff check --output-format=github .
    ruff format --check .
so this replicates that, pinned, in a clone -- never the moving worktree (the builder's
own detector failure #2 was a worktree reading that contradicted itself).

Measures, for each of the lane's three commits, the gate at COMMIT and at COMMIT^, so
"this lane added zero gate failures" is attributed per commit rather than assumed.

Controls (both states, must all pass or no verdict here is citable):
  C1  EOL pin        : 0 CRLF across tracked .py in the clone
  C2  nested config : tools/mcp/patent-search-mcp/pyproject.toml PRESENT (its absence is
                      what produced the builder's own false red)
  C3  mangle        : a known-clean file, deliberately mangled, MUST make format --check fire
  C4  T2 no-exclude : removing `"command-center/_*.py"` from ruff.toml MUST make the gate
                      go red -- otherwise the exclusion is decoration, not load-bearing
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = "C:/Users/Prekzursil/source/ast-integrate"
RUFF = ["uvx", "ruff@0.15.17"]
out = {"controls": {}, "gate": {}}


def run(args, cwd, timeout=1200):
    r = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )
    return r.returncode, r.stdout, r.stderr


def git(cwd, *a):
    return run(["git", *a], cwd)


def ruff_gate(clone):
    """Return the two CI readings plus the set of files format --check would reformat."""
    crc, cso, cse = run([*RUFF, "check", "--output-format=github", "."], clone)
    n_err = None
    m = re.search(r"Found (\d+) error", cso + cse)
    if m:
        n_err = int(m.group(1))
    frc, fso, fse = run([*RUFF, "format", "--check", "."], clone)
    fails = sorted(
        {
            ln.split("Would reformat:", 1)[1].strip()
            for ln in (fso + fse).splitlines()
            if "Would reformat:" in ln
        }
    )
    m2 = re.search(r"(\d+) files? already formatted", fso + fse)
    return {
        "check_rc": crc,
        "check_errors": n_err,
        "format_rc": frc,
        "n_would_reformat": len(fails),
        "n_already_formatted": int(m2.group(1)) if m2 else None,
        "would_reformat": fails,
        "green": crc == 0 and frc == 0,
    }


tmp = Path(tempfile.mkdtemp(prefix="aud_clone_"))
clone = tmp / "repo"
rc, so, se = run(
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
out["clone_err_tail"] = (se or "")[-300:]
if rc != 0:
    print(json.dumps(out, indent=2))
    raise SystemExit(1)

# ---- C1: EOL pin ----
rc, so, _ = git(str(clone), "ls-files", "*.py")
py_tracked = [x for x in so.splitlines() if x.strip()]
crlf = 0
for rel in py_tracked:
    p = clone / rel
    if p.exists():
        with open(p, "rb") as fh:
            if b"\r\n" in fh.read():
                crlf += 1
out["controls"]["C1_eol_pin"] = {
    "tracked_py": len(py_tracked),
    "files_with_crlf": crlf,
    "pass": crlf == 0,
}

# ---- C2: nested ruff/pyproject configs present ----
rc, so, _ = git(str(clone), "ls-files", "*pyproject.toml", "*ruff.toml")
cfgs = [x for x in so.splitlines() if x.strip()]
nested = "tools/mcp/patent-search-mcp/pyproject.toml"
out["controls"]["C2_nested_config"] = {
    "n_configs": len(cfgs),
    "nested_present": (clone / nested).exists(),
    "pass": (clone / nested).exists() and len(cfgs) > 1,
}

# ---- the per-commit gate readings ----
commits = ["f5b596e6", "fa87d1a2", "ebe02d62"]
order = []
for c in commits:
    rc, so, _ = git(str(clone), "rev-parse", f"{c}^")
    order.append((c + "^", so.strip()))
    order.append((c, c))
seen = {}
for label, rev in order:
    if rev in seen:
        out["gate"][label] = {"same_as": seen[rev]}
        continue
    rc, so, se = git(str(clone), "checkout", "--force", rev)
    if rc != 0:
        out["gate"][label] = {"checkout_failed": se[-200:]}
        continue
    out["gate"][label] = ruff_gate(str(clone))
    seen[rev] = label

# ---- back to HEAD for the remaining controls ----
git(str(clone), "checkout", "--force", "ebe02d62")
head_read = out["gate"].get("ebe02d62")

# ---- C4: T2, strip the exclusion line -> the gate MUST go red ----
rt = clone / "ruff.toml"
orig = rt.read_bytes()
txt = orig.decode("utf-8")
needle = '    "command-center/_*.py",'
found = needle in txt or '"command-center/_*.py"' in txt
txt2 = "\n".join(
    ln for ln in txt.splitlines(True) if '"command-center/_*.py"' not in ln
)
rt.write_bytes(txt2.encode("utf-8"))
t2 = ruff_gate(str(clone))
rt.write_bytes(orig)
out["controls"]["C4_exclusion_is_load_bearing"] = {
    "needle_found_in_ruff_toml": found,
    "with_exclusion": {
        "check_rc": head_read["check_rc"],
        "format_rc": head_read["format_rc"],
        "n_would_reformat": head_read["n_would_reformat"],
    },
    "without_exclusion": {
        "check_rc": t2["check_rc"],
        "check_errors": t2["check_errors"],
        "format_rc": t2["format_rc"],
        "n_would_reformat": t2["n_would_reformat"],
    },
    "delta_would_reformat": t2["n_would_reformat"] - head_read["n_would_reformat"],
    "n_root_probes_in_t2_failset": len(
        [f for f in t2["would_reformat"] if re.match(r"^command-center[\\/]_", f)]
    ),
    "states_distinguishable": t2["green"] is False
    and head_read["format_rc"] == head_read["format_rc"],
    "pass": (not t2["green"])
    and t2["n_would_reformat"] > head_read["n_would_reformat"],
}

# ---- C3: mangle a known-clean file -> format --check MUST fire ----
victim = None
for rel in py_tracked:
    if rel.startswith("platform/lib/") and (clone / rel).exists():
        victim = rel
        break
c3 = {"victim": victim}
if victim:
    vp = clone / victim
    vorig = vp.read_bytes()
    vp.write_bytes(vorig + b"\n\n\nx    =    1\n")
    m = ruff_gate(str(clone))
    vp.write_bytes(vorig)
    c3.update(
        {
            "mangled_format_rc": m["format_rc"],
            "mangled_n_would_reformat": m["n_would_reformat"],
            "victim_in_failset": any(
                victim.replace("/", "\\") in f or victim in f
                for f in m["would_reformat"]
            ),
            "pass": m["format_rc"] != 0
            and m["n_would_reformat"] > head_read["n_would_reformat"],
        }
    )
out["controls"]["C3_mangle"] = c3

out["all_controls_pass"] = all(v.get("pass") for v in out["controls"].values())
print(json.dumps(out, indent=2))
Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
shutil.rmtree(tmp, ignore_errors=True)
