#!/usr/bin/env python3
"""IMP-0461 probe2: independent re-walk from the other shell.

Re-resolves "bash" WITHOUT the production resolver (native PATH walk, direct
is_file probes) and asserts the resolver's table matches the independent
walk for both shells. Also proves the defect the resolver prevents: a
first-match-over-concatenated-dirs resolution hides one of the two bash
binaries (wrong_bash_if_single_path), and confirms the resolver's strict
family row points at the Windows system bash, not the msys one."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EI_PY = REPO / "tools" / "launcher" / "explicit_interpreter.py"

spec = importlib.util.spec_from_file_location("imp0461_explicit_interpreter", EI_PY)
E = importlib.util.module_from_spec(spec)
sys.modules["imp0461_explicit_interpreter"] = E
spec.loader.exec_module(E)


def independent_walk(name: str):
    """Native PATH scan; no call into the production resolver."""
    path_dirs = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    found = {"msys": "", "wsl-system": ""}
    for shell_id, dirs in (
        ("msys", [d for d in path_dirs if "/git/" in d.replace(chr(92), "/").lower() or "msys" in d.lower()]),
        ("wsl-system", [d for d in path_dirs if "system32" in d.lower() or "windowsapps" in d.lower()]),
    ):
        for d in dirs:
            for cand in (Path(d) / name, Path(d) / (name + ".exe")):
                if cand.is_file():
                    found[shell_id] = str(cand.resolve())
                    break
            if found[shell_id]:
                break
    return found


def fail(msg):
    print("FAILED:IMP-0461-probe2 " + str(msg))
    return 1


def main() -> int:
    path_dirs = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    msys_dirs = [d for d in path_dirs if "/git/" in d.replace(chr(92), "/").lower() or "msys" in d.lower()]
    sys_dirs = [d for d in path_dirs if "system32" in d.lower() or "windowsapps" in d.lower()]
    shells = {"msys": msys_dirs, "wsl-system": sys_dirs}

    table = E.resolve_name("bash", shells)
    resolver_rows = {r["shell"]: r["path"] for r in table.rows}

    # (a) the independent walk agrees with the resolver for BOTH shells.
    independent = independent_walk("bash")
    for shell_id, ind_path in independent.items():
        res_path = resolver_rows.get(shell_id, "")
        if not ind_path:
            return fail("independent walk found no %s bash" % shell_id)
        if Path(ind_path).resolve() != Path(res_path).resolve():
            return fail(
                "independent walk disagrees with resolver for %s: walk=%s resolver=%s"
                % (shell_id, ind_path, res_path)
            )

    # (b) strict-family row is the WINDOWS SYSTEM bash, not the msys one.
    wsl_row = resolver_rows.get("wsl-system", "").lower()
    if "system32" not in wsl_row:
        return fail("wsl-system row is not the system bash: %s" % resolver_rows.get("wsl-system"))
    msys_row = resolver_rows.get("msys", "").lower()
    if "system32" in msys_row or "git" not in msys_row:
        return fail("msys row is not the Git bash: %s" % resolver_rows.get("msys"))

    # (c) the defect the resolver prevents: first-match over concatenated
    # dirs hides one binary (the two shells really do disagree).
    hidden = E.wrong_bash_if_single_path("bash", shells)
    if not hidden["first_wins_hides_the_other"]:
        return fail("first-wins control did not hide a binary - defect not reproduced")

    print(json.dumps({
        "probe": "probe2-independent-rewalk",
        "unit_id": "IMP-0461",
        "resolver_rows": resolver_rows,
        "independent_walk": independent,
        "agreement": True,
        "strict_family_is_system_bash": "system32" in wsl_row,
        "tolerant_family_is_git_bash": "git" in msys_row,
        "first_wins_hides": hidden["first"],
        "first_wins_hides_the_other": hidden["first_wins_hides_the_other"],
        "method": "native PATH is_file walk, resolver not consulted",
        "sentinel": "SENTINEL:IMP-0461:INTERPRETER-EXPLICIT",
    }, indent=2))
    print("SUCCESS:IMP-0461-probe2 independent re-walk from the other shell matches the resolver; first-wins defect reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
