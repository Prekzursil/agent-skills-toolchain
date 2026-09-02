#!/usr/bin/env python3
"""Probe 2: pre-fix Windows run was red; attributes mutation is detected.

Control 1 — historical defect: hash RAW CRLF working-tree bytes (the pre-fix
REACH-6 / cc-render path). That must disagree with the recorded LF digests.
LF-normalised hashes must still match, so after-green is not silence in both
states.

Control 2 — policy checker: removing `*.md eol=lf` from a copy of
.gitattributes must turn eol_policy.py --check red; the live file stays green.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import eol_policy as eol  # noqa: E402


def _mutate_drop_md_rule(src: Path, dst: Path) -> None:
    lines = []
    dropped = False
    for line in src.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped.startswith("*.md") and "eol=lf" in stripped:
            dropped = True
            continue
        lines.append(line)
    if not dropped:
        raise RuntimeError("mutant did not drop *.md eol=lf — control is inert")
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0441-p2-"))
    lf_root = tmp / "lf" / "command-center"
    crlf_root = tmp / "crlf" / "command-center"
    eol.build_min_command_center(lf_root)
    eol.materialize_eol(lf_root, crlf_root, "crlf")
    prefix = eol.prefix_raw_hash_red(crlf_root)
    live_missing = eol.check_gitattributes()
    live_rc = eol.main(["--check"])
    mutant = tmp / "mutant.gitattributes"
    _mutate_drop_md_rule(eol.GITATTRIBUTES, mutant)
    mutant_missing = eol.check_gitattributes(mutant)
    mutant_rc = eol.main(["--check", "--gitattributes", str(mutant)])
    ok = (
        prefix["both_prefix_red"]
        and prefix["both_postfix_match"]
        and prefix["register_crlf_count"] > 0
        and live_missing == []
        and live_rc == 0
        and "*.md" in mutant_missing
        and mutant_rc == 1
    )
    payload = {
        "probe": "probe2-prefix-was-red",
        "unit_id": "IMP-0441",
        "prefix": prefix,
        "live_gitattributes_missing": live_missing,
        "live_eol_policy_exit": live_rc,
        "mutant_missing": mutant_missing,
        "mutant_eol_policy_exit": mutant_rc,
        "pass": ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    print(
        f"prefix_red={prefix['both_prefix_red']} postfix_match={prefix['both_postfix_match']} "
        f"crlf={prefix['register_crlf_count']} live_rc={live_rc} mutant_rc={mutant_rc}"
    )
    if not ok:
        print("FAILED:IMP-0441-probe2 pre-fix red control or attributes mutation")
        return 1
    print("SUCCESS:IMP-0441-probe2 pre-fix Windows was red; md-rule mutation detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
