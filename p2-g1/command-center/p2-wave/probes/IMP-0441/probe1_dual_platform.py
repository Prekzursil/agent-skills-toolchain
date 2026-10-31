#!/usr/bin/env python3
"""IMP-0441 probe1: both real gates exit zero on LF (Linux CI) AND on a
CRLF-materialised sibling (the Windows working-tree byte form), and the
repo .gitattributes carries eol=lf for every hashed extension."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EOL_PY = REPO / "tools" / "command-center" / "eol_policy.py"

spec = importlib.util.spec_from_file_location("imp0441_eol_policy", EOL_PY)
M = importlib.util.module_from_spec(spec)
sys.modules["imp0441_eol_policy"] = M
spec.loader.exec_module(M)


def fail(msg: str) -> int:
    print("FAILED:IMP-0441-probe1 " + str(msg))
    return 1


def main() -> int:
    # (a) repo .gitattributes carries the required eol=lf rules.
    missing = M.check_gitattributes(REPO / ".gitattributes")
    if missing:
        return fail(f"gitattributes missing eol=lf rules: {missing}")

    # (b) the shipped CLI agrees (its own --check path).
    cli = subprocess.run(
        [sys.executable, "-B", str(EOL_PY), "--check"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    if cli.returncode != 0:
        return fail(f"eol_policy --check exit {cli.returncode}: {cli.stdout} {cli.stderr}")

    # (c) the real validate.py / render.py CLIs exit zero on the LF tree
    # (Linux CI form) and on the CRLF-materialised sibling (Windows
    # working-tree byte form). dual_platform invokes the real CLIs.
    tmp = Path(tempfile.mkdtemp(prefix="imp0441-probe1-"))
    result = M.dual_platform(tmp)
    gates = result["linux_lf"]
    sim = result["windows_crlf_sim"]
    if not result["linux_green"]:
        return fail(f"LF tree gate red: validate={gates['validate']['exit_code']} render={gates['render']['exit_code']}")
    if not result["windows_green_after"]:
        return fail(
            "CRLF tree gate red: validate=%s render=%s" % (
                sim["validate"]["exit_code"], sim["render"]["exit_code"])
        )
    if sim["validate"]["exit_code"] != 0 or sim["render"]["exit_code"] != 0:
        return fail("windows exit codes non-zero")
    if gates["validate"]["exit_code"] != 0 or gates["render"]["exit_code"] != 0:
        return fail("linux exit codes non-zero")

    print(json.dumps({
        "probe": "probe1-dual-platform",
        "unit_id": "IMP-0441",
        "gitattributes_rules": sorted(M.REQUIRED_EOL_LF),
        "gitattributes_missing": [],
        "eol_policy_check_exit": cli.returncode,
        "linux_lf_validate_exit": gates["validate"]["exit_code"],
        "linux_lf_render_exit": gates["render"]["exit_code"],
        "windows_crlf_validate_exit": sim["validate"]["exit_code"],
        "windows_crlf_render_exit": sim["render"]["exit_code"],
        "linux_green": result["linux_green"],
        "windows_green_after": result["windows_green_after"],
        "sentinel": "SENTINEL:IMP-0441:GATES-GREEN-BOTH-PLATFORMS",
    }, indent=2))
    print("SUCCESS:IMP-0441-probe1 both real gates exit zero on LF and CRLF trees; .gitattributes carries eol=lf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
