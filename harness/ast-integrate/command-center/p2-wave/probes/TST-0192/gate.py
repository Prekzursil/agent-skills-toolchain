"""Policy gate: emitted .sh files are LF and pass real bash -n; *.sh eol=lf is pinned."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from detectors import (
    REPO,
    blob_or_worktree_cr,
    gitattributes_status,
    inventory_sh,
    parse_sh_eol_lf,
    real_bash_n,
)
from emitter import emit


def gitattributes_mutation_control() -> dict[str, Any]:
    """Removing the *.sh eol=lf rule must be visible to the parser."""
    st = gitattributes_status()
    live_ok = bool(st.get("has_sh_eol_lf"))
    stripped = parse_sh_eol_lf("# no shell rule\n*.md text eol=lf\n")
    mutant_silent = stripped["has_sh_eol_lf"] is False
    return {
        "live_has_rule": live_ok,
        "mutant_without_sh_rule_detected": mutant_silent,
        "pass": live_ok and mutant_silent,
    }


def evaluate() -> dict[str, Any]:
    emitted = emit()
    ga = gitattributes_status()
    scripts = []
    failures: list[str] = []
    for path in inventory_sh():
        rel = path.relative_to(REPO).as_posix()
        cr = blob_or_worktree_cr(path, rel)
        bn = real_bash_n(path)
        row = {
            "path": rel,
            "cr_count": cr["cr_count_live"],
            "cr_source": cr["live_source"],
            "blob": cr["blob"],
            "worktree": cr["worktree"],
            "real_bash_n_exit": bn["exit"],
            "real_bash_n": bn,
        }
        scripts.append(row)
        if cr["cr_count_live"] != 0:
            failures.append(f"CR in {rel} count={cr['cr_count_live']}")
        if bn["exit"] != 0:
            failures.append(f"real-bash -n {rel} exit={bn['exit']}")
    if len(scripts) < 2:
        failures.append("fewer than 2 emitted .sh files")
    if not ga.get("has_sh_eol_lf"):
        failures.append("gitattributes missing *.sh eol=lf")
    mut = gitattributes_mutation_control()
    if not mut["pass"]:
        failures.append("gitattributes mutation control failed")
    return {
        "pass": not failures,
        "failures": failures,
        "gitattributes": ga,
        "gitattributes_mutation": mut,
        "scripts": scripts,
        "emitted": emitted,
        "used_git_archive": False,
    }
