#!/usr/bin/env python3
"""Probe 2: packed artifact extracted *.sh bytes; packer refuses CRLF staging."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN / "tests"))
sys.path.insert(0, str(PLUGIN))

import pack as P  # noqa: E402
import test_eol_policy as tests  # noqa: E402

OUT = HERE / "probe2-packer-extracted.raw.json"


def main() -> int:
    packed = tests.test_packer_refuses_crlf_in_staging_tree()
    src = (PLUGIN / "pack.py").read_text(encoding="utf-8")
    payload = {
        "probe": "probe2-packer-extracted",
        "unit_id": "IMP-0017",
        "pass": True,
        "reader": "git cat-file -p then tar extract of those bytes",
        "good_members": packed["good_members"],
        "extracted_shell_clean": packed["extracted_shell_clean"],
        "packer_refused_crlf_staging": packed["refused"],
        "planted_spec": packed["planted_spec"],
        "refuse_message": packed["message"],
        "packer_calls_git_archive": "git archive" in src,
        "packer_calls_cat_file": "cat-file" in src,
    }
    if (
        not packed["refused"]
        or packed["extracted_shell_clean"] < 2
        or "git archive" in src
        or "cat-file" not in src
    ):
        payload["pass"] = False
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        print("FAILED:IMP-0017-probe2")
        return 1
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        f"extracted_clean={packed['extracted_shell_clean']} "
        f"refused={packed['refused']} planted={packed['planted_spec']}"
    )
    print("SUCCESS:IMP-0017-probe2 packer extracted bytes and CRLF refuse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
