#!/usr/bin/env python3
"""IMP-0017 probe1: git cat-file blob byte-scan for 0x0D over shipped shells."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import eol_policy as eol  # noqa: E402
import pack as pack_mod  # noqa: E402

PROBE = Path(__file__).resolve().parent
RAW = PROBE / "probe1-catfile-blobs.raw.txt"
MEAS = PROBE / "probe1-measurement.json"


def main() -> int:
    lines: list[str] = [
        "NAMED PROBE 1: GIT CAT-FILE BLOB CR SCAN (SHIPPED SHELLS)",
        "PROBE-1-BEGIN:IMP-0017",
        f"repo={REPO}",
        "reader=git cat-file -p (NOT worktree, NOT git archive)",
        "prefix=tools/plugin",
    ]
    attrs = eol.load_repo_gitattributes(REPO, "HEAD")
    eol.assert_gitattributes_eol_lf(attrs)
    globs = sorted(eol.parse_gitattributes_eol_lf(attrs))
    lines.append(f"gitattributes_eol_lf_globs={json.dumps(globs)}")

    doc = pack_mod.load_allowlist(REPO / "tools/plugin/payload-allowlist.json")
    rules = pack_mod.compile_rules(doc)
    candidates = pack_mod.git_ls_tree(REPO, "HEAD", prefix="tools/plugin")
    members = pack_mod.expand_members(candidates, rules)
    shells = [m for m in members if eol.is_shell_path(m)]
    lines.append(f"shipped_shell_count={len(shells)}")
    lines.append(f"shipped_shells={json.dumps(shells)}")

    per_file: list[dict] = []
    total_cr = 0
    for rel in shells:
        git_path = f"tools/plugin/{rel}"
        blob = eol.git_cat_file_blob(REPO, "HEAD", git_path)
        # Prove we did not use worktree for the gate.
        cr = eol.count_cr(blob)
        total_cr += cr
        row = {
            "path": git_path,
            "bytes": len(blob),
            "cr_count": cr,
            "reader": "git-cat-file-p",
        }
        per_file.append(row)
        lines.append(
            f"blob path={git_path} bytes={len(blob)} cr={cr} "
            f"sha12={__import__('hashlib').sha256(blob).hexdigest()[:12]}"
        )

    ok = total_cr == 0 and len(shells) >= 1
    meas = {
        "shipped_shell_count": len(shells),
        "total_cr": total_cr,
        "zero_cr": total_cr == 0,
        "gitattributes_ok": True,
        "eol_lf_globs": globs,
        "per_file": per_file,
        "reader": "git-cat-file-p",
        "used_git_archive": False,
        "used_worktree_read": False,
        "probe_1_confirmed": ok,
    }
    MEAS.write_text(json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines.extend(
        [
            f"total_cr={total_cr}",
            f"zero_cr={total_cr == 0}",
            f"probe_1_confirmed={ok}",
            "PROBE-1-COMPLETE:IMP-0017",
            "SUCCESS:IMP-0017-probe1" if ok else "FAILED:IMP-0017-probe1",
        ]
    )
    raw = "\n".join(lines) + "\n"
    RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
