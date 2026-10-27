"""GROUNDING R2: what does committing bucket (b) COST? Run the CI-pinned ruff on it.

R3 (round 1) measured this for command-center. platform/ was never measured. A bucket-(b) file
that fails `ruff check` / `ruff format --check` turns main RED for every sibling PR the moment
it is added, because quality.yml runs both REPO-WIDE.

Both-states control: a deliberately-mangled copy MUST fire; a known-clean tracked file must not.
Read-only w.r.t. the repo (writes only under the system temp dir).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

RUFF_PIN = "ruff@0.15.17"  # the CI pin
REPO = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
).stdout.strip()


def run(args, cwd=None):
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


out = {
    "repo": REPO,
    "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "ruff_pin": RUFF_PIN,
}

cls = json.load(
    open(
        os.path.join(REPO, "command-center", "slop-report", "_g2_classify.out.json"),
        encoding="utf-8",
    )
)
bucket_b = [
    d["path"]
    for d in cls["detail"]
    if d["bucket"].startswith("b_") and d["path"].endswith(".py")
]
bucket_d = [
    d["path"]
    for d in cls["detail"]
    if d["bucket"].startswith("d_") and d["path"].endswith(".py")
]
out["bucket_b_py_n"] = len(bucket_b)
out["bucket_d_py_n"] = len(bucket_d)

# Stage a copy so ruff sees the project's real pyproject config (a bare temp dir defaults to
# line-length 88 vs this project's setting -> a false CI-red on clean files).
tmp = tempfile.mkdtemp(prefix="g2cost_")
try:
    for cfg in ("pyproject.toml", "ruff.toml", ".ruff.toml", "setup.cfg"):
        src = os.path.join(REPO, cfg)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(tmp, cfg))
            out.setdefault("config_copied", []).append(cfg)

    def stage(paths, sub):
        base = os.path.join(tmp, sub)
        staged = []
        for p in paths:
            dst = os.path.join(base, p.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                shutil.copy2(os.path.join(REPO, p.replace("/", os.sep)), dst)
                staged.append(p)
            except OSError:
                pass
        return base, staged

    def ruff(kind, target):
        args = [
            "uvx",
            RUFF_PIN,
            *(["check"] if kind == "check" else ["format", "--check"]),
            target,
        ]
        r = run(args, cwd=tmp)
        return {"rc": r.returncode, "tail": (r.stdout or r.stderr or "")[-1500:]}

    for name, paths in (("bucket_b", bucket_b), ("bucket_d", bucket_d)):
        base, staged = stage(paths, name)
        out[f"{name}_staged"] = len(staged)
        if staged:
            out[f"{name}_ruff_check"] = ruff("check", base)
            out[f"{name}_ruff_format"] = ruff("format", base)

    # ---- BOTH-STATES CONTROL
    ctrl_dir = os.path.join(tmp, "control")
    os.makedirs(ctrl_dir, exist_ok=True)
    clean = os.path.join(ctrl_dir, "clean_ctl.py")
    with open(clean, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('"""Clean control."""\n\n\ndef f() -> int:\n    return 1\n')
    mangled = os.path.join(ctrl_dir, "mangled_ctl.py")
    with open(mangled, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("import os\nl = 1\ndef  f( ):\n     x=2\n     return    x\n")
    out["control_clean_check"] = ruff("check", clean)
    out["control_clean_format"] = ruff("format", clean)
    out["control_mangled_check"] = ruff("check", mangled)
    out["control_mangled_format"] = ruff("format", mangled)
    out["control_distinguishes"] = (
        out["control_clean_check"]["rc"] == 0
        and out["control_clean_format"]["rc"] == 0
        and out["control_mangled_check"]["rc"] != 0
        and out["control_mangled_format"]["rc"] != 0
    )
finally:
    shutil.rmtree(tmp, ignore_errors=True)

json.dump(out, sys.stdout, indent=1)
