#!/usr/bin/env python3
"""Fixture matrix for IMP-0016 interpreter discovery."""
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import interpreter_probe as ip  # noqa: E402


def _write_fake(directory: Path, name: str, banner: str) -> Path:
    path = directory / name
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' '{banner}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n",
        encoding="utf-8",
        newline="\n",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def main() -> int:
    fail = False
    with tempfile.TemporaryDirectory(prefix="imp0016-tests-") as tmp:
        root = Path(tmp)
        _write_fake(root, "python3", "Python 3.10.0")
        below = ip.probe_one(ip._normalize_decl({"id": "python3", "name": "python3", "floor": "3.11.0"}), str(root))
        print(f"below-floor verdict={below['verdict']} remediation={below['remediation']}")
        if below["verdict"] != "BELOW_FLOOR" or not below["remediation"]:
            print("FAILED: below-floor")
            fail = True

        _write_fake(root, "node", "v20.11.0")
        at_floor = ip.probe_one(ip._normalize_decl({"id": "node", "name": "node", "floor": "20.0.0"}), str(root))
        print(f"at-floor verdict={at_floor['verdict']}")
        if at_floor["verdict"] != "OK":
            print("FAILED: at-floor")
            fail = True

        missing = ip.probe_one(ip._normalize_decl({"id": "pwsh", "name": "pwsh", "floor": "7.0.0"}), str(root))
        print(f"missing verdict={missing['verdict']}")
        if missing["verdict"] != "MISSING" or not missing["remediation"]:
            print("FAILED: missing")
            fail = True

        extra = root / "alt"
        extra.mkdir()
        _write_fake(root, "bash", "GNU bash, version 5.2.0")
        _write_fake(extra, "bash", "GNU bash, version 5.2.0")
        amb = ip.probe_one(
            ip._normalize_decl({"id": "bash", "name": "bash", "floor": "5.0.0"}),
            str(root) + os.pathsep + str(extra),
        )
        print(f"ambiguous verdict={amb['verdict']} n={len(amb['all_paths'])}")
        if amb["verdict"] != "AMBIGUOUS":
            print("FAILED: ambiguous")
            fail = True

        hide = ip.probe_one(ip._normalize_decl({"id": "python3", "name": "python3", "floor": "3.11.0"}), str(extra))
        print(f"negative-control hide verdict={hide['verdict']} silent_fallback={hide['silent_fallback']}")
        if hide["verdict"] != "MISSING" or hide["silent_fallback"]:
            print("FAILED: hide-from-PATH")
            fail = True

    if fail:
        print("FAILED:IMP-0016-tests")
        return 1
    print("SUCCESS:IMP-0016-tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
