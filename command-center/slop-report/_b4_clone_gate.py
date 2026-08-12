"""BUILD R1 -- run the CI ruff gate in a REAL FRESH CLONE of HEAD.

Supersedes _b3_head_blob_gate.py, whose verdict ("HEAD is CI-RED, 4 files") was a FALSE RED
of my own making: it materialised only `*.py` into a bare temp dir, so
`tools/mcp/patent-search-mcp/pyproject.toml` -- which carries `[tool.ruff] line-length = 100`
-- was absent and the root ruff.toml (no line-length, i.e. ruff's default 88) applied
instead. 16 tracked pyproject/ruff config files exist; a partial materialisation cannot
reproduce ruff's per-file config discovery.

A real clone gives: every config file, every .gitignore, and a real .git so
`respect-gitignore` behaves as it does in CI. `core.autocrlf=false` + `core.eol=lf` force an
LF checkout, because THIS box otherwise converts LF -> CRLF on checkout (git says so) while
CI checks out LF on Linux, and ruff can format the two forms differently.

CONTROLS (both states, on the clone itself):
  C1 LF        : the clone must contain 0 CRLF in tracked .py -- else the EOL pin failed and
                 the whole reading is against the wrong bytes.
  C2 CONFIG    : the nested pyproject.toml must be PRESENT in the clone. Its absence is
                 exactly what produced the false red, so this is the control for that bug.
  C3 FIRES     : mangling one clean file in the clone must turn `ruff format --check` red.
                 If it stays green the harness measures nothing.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
PIN = ["uvx", "ruff@0.15.17"]
OUT = os.path.join(ROOT, "command-center/slop-report/_b4_clone_gate.out.json")
NESTED_CFG = "tools/mcp/patent-search-mcp/pyproject.toml"
VICTIM = "ci/check_skill_dual_write.py"


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
    tmp = tempfile.mkdtemp(prefix="clonegate_")
    clone = os.path.join(tmp, "repo")
    out = {"rev_at_start": rev}
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
        out["clone_rc"] = rc
        if rc != 0:
            out["clone_err"] = t[-800:]
            raise SystemExit(json.dumps(out, indent=1))
        run(["git", "checkout", "--quiet", "--detach", rev], clone)
        out["clone_head"] = subprocess.run(
            ["git", "-C", clone, "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()

        py = [
            p
            for p in subprocess.run(
                ["git", "-C", clone, "ls-files"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout.splitlines()
            if p.endswith(".py")
        ]
        crlf = 0
        for p in py:
            fp = os.path.join(clone, p.replace("/", os.sep))
            if os.path.exists(fp):
                with open(fp, "rb") as fh:
                    crlf += fh.read().count(b"\r\n")
        out["controls"] = {
            "C1_clone_py_files": len(py),
            "C1_total_crlf_in_clone": crlf,
            "C1_lf_checkout_ok": crlf == 0,
            "C2_nested_config_present": os.path.exists(
                os.path.join(clone, NESTED_CFG.replace("/", os.sep))
            ),
        }

        rc_l, t_l = run([*PIN, "check", ".", "--output-format=concise"], clone)
        rc_f, t_f = run([*PIN, "format", "--check", "."], clone)
        out["gate_lint_format"] = {
            "ruff_check_rc": rc_l,
            "ruff_check_tail": t_l.strip().splitlines()[-3:],
            "ruff_check_findings": [
                x.strip()
                for x in t_l.splitlines()
                if ": " in x and not x.startswith("Found")
            ][:40],
            "ruff_format_rc": rc_f,
            "ruff_format_would_reformat": fmt_list(t_f),
            "ruff_format_tail": t_f.strip().splitlines()[-1:],
        }

        # C3: mangle one clean file IN THE CLONE -> must fire
        vp = os.path.join(clone, VICTIM.replace("/", os.sep))
        with open(vp, "rb") as fh:
            orig = fh.read()
        with open(vp, "wb") as fh:
            fh.write(orig.replace(b"import ", b"import  ", 1))
        rc_bad, t_bad = run([*PIN, "format", "--check", "."], clone)
        with open(vp, "wb") as fh:
            fh.write(orig)
        out["controls"]["C3_mangled_fires"] = VICTIM in fmt_list(t_bad)
        out["controls"]["C3_mangled_rc"] = rc_bad

        c = out["controls"]
        out["controls_verdict"] = (
            "PASS"
            if c["C1_lf_checkout_ok"]
            and c["C2_nested_config_present"]
            and c["C3_mangled_fires"]
            else "FAIL"
        )
        out["verdict"] = (
            "HEAD is CI-GREEN on gate-lint-format"
            if rc_l == 0 and rc_f == 0
            else "HEAD is CI-RED on gate-lint-format"
        )
        out["supersedes"] = (
            "_b3_head_blob_gate.out.json verdict 'HEAD is CI-RED, 4 files under "
            "tools/mcp/patent-search-mcp' -- REFUTED as a false red (missing nested "
            "pyproject.toml with line-length=100)."
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1)[:4000])
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
