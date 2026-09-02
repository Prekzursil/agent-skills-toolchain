"""Probe 2: tool-layer OS resolution (argv, realpath, inode, case-fold).

Mechanically different from probe 1: no display renderer, no naive listing join.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from fixtures import (
    CASE_LOWER,
    CASE_UPPER,
    DASH_NAME,
    HOMOGLYPH_CONFIG,
    LATIN_CONFIG,
    NEWLINE_NAME,
    ORDINARY,
    PAYLOADS,
    RTL_NAME,
    hex_name,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _load_fold():
    tools_cc = REPO / "tools" / "command-center"
    sys.path.insert(0, str(tools_cc))
    from reconcile_delivery import _fold  # type: ignore

    return _fold


def cat_argv(tree: Path, args: list[str]) -> dict:
    try:
        proc = subprocess.run(
            ["cat", *args],
            cwd=str(tree),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        return {"rc": 124, "stdout": "", "stderr": "TIMEOUT", "timeout": True}
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    return {
        "rc": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timeout": False,
    }


def inode_of(tree: Path, name: str) -> int:
    return os.stat(tree / name).st_ino


def unquoted_ifs_words(name: str) -> list[str]:
    """POSIX unquoted IFS split (space/tab/newline) without executing a shell."""
    parts = re.split(r"[ \t\n]+", name)
    return [p for p in parts if p]


def probe2_measure(tree: Path) -> dict:
    dash_payload = PAYLOADS[DASH_NAME]
    without = cat_argv(tree, [DASH_NAME])
    with_end = cat_argv(tree, ["--", DASH_NAME])
    ordinary = cat_argv(tree, ["--", ORDINARY])
    newline_argv = cat_argv(tree, ["--", NEWLINE_NAME])
    rtl_argv = cat_argv(tree, ["--", RTL_NAME])
    latin_ino = inode_of(tree, LATIN_CONFIG)
    twin_ino = inode_of(tree, HOMOGLYPH_CONFIG)
    lower_ino = inode_of(tree, CASE_LOWER)
    upper_ino = inode_of(tree, CASE_UPPER)
    fold_fn = _load_fold()
    lower_stem = CASE_LOWER.rsplit(".", 1)[0]
    upper_stem = CASE_UPPER.rsplit(".", 1)[0]
    fold_lower = fold_fn(lower_stem)
    fold_upper = fold_fn(upper_stem)
    ordinary_real = os.path.realpath(str(tree / ORDINARY))
    return {
        "probe": "probe2-tool-resolve",
        "ordinary": ORDINARY,
        "ordinary_basename": os.path.basename(ordinary_real),
        "ordinary_payload": ordinary["stdout"],
        "ordinary_open_ok": ordinary["rc"] == 0
        and ordinary["stdout"] == PAYLOADS[ORDINARY],
        "dash_name": DASH_NAME,
        "dash_without_endopts": without,
        "dash_with_endopts": with_end,
        "dash_without_has_payload": dash_payload in without["stdout"],
        "dash_with_has_payload": dash_payload in with_end["stdout"],
        "dash_parsed_as_flag": dash_payload not in without["stdout"]
        and dash_payload in with_end["stdout"],
        "homoglyph_latin_inode": latin_ino,
        "homoglyph_twin_inode": twin_ino,
        "homoglyph_same_inode": latin_ino == twin_ino,
        "homoglyph_latin_payload": (tree / LATIN_CONFIG).read_text(encoding="utf-8"),
        "homoglyph_twin_payload": (tree / HOMOGLYPH_CONFIG).read_text(
            encoding="utf-8"
        ),
        "case_lower_inode": lower_ino,
        "case_upper_inode": upper_ino,
        "case_os_same_inode": lower_ino == upper_ino,
        "case_fold_lower": fold_lower,
        "case_fold_upper": fold_upper,
        "case_fold_collides": fold_lower == fold_upper,
        "case_fold_source": "tools/command-center/reconcile_delivery.py:_fold",
        "newline_name_hex": hex_name(NEWLINE_NAME),
        "newline_argv_payload": newline_argv["stdout"],
        "newline_argv_ok": newline_argv["rc"] == 0
        and newline_argv["stdout"] == PAYLOADS[NEWLINE_NAME],
        "newline_unquoted_ifs_words": unquoted_ifs_words(NEWLINE_NAME),
        "newline_unquoted_splits": unquoted_ifs_words(NEWLINE_NAME) != [NEWLINE_NAME],
        "rtl_name_hex": hex_name(RTL_NAME),
        "rtl_argv_ok": rtl_argv["rc"] == 0
        and rtl_argv["stdout"] == PAYLOADS[RTL_NAME],
        "rtl_realpath_basename": os.path.basename(
            os.path.realpath(str(tree / RTL_NAME))
        ),
    }
