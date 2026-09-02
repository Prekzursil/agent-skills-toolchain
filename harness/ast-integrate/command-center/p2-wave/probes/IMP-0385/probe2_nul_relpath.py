#!/usr/bin/env python3
"""Probe 2: NUL / \\\\.\\NUL must not abort the walk (independent of probe 1).

Regression: os.path.relpath against a \\\\.\\NUL path must not abort the walk.
Both-states: a naive relpath walker goes to zero on a planted NUL when
os.path.relpath is made to raise; the production walker still finds the
sibling keep.txt AND the NUL file. Crash-swallowed-as-zero is the failure
class this control is aimed at.

Also: enumeration count with vs without the reserved-name file differs by
exactly one, and neither run raises. Long path (>260 chars) is still listed.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.router.index_build import (  # noqa: E402
    run_nul_seeded_walk,
    safe_relpath,
    walk_files,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0385-probe2 {msg}")
    return 1


def naive_relpath_walk(root: Path):
    """Buggy walker: os.path.relpath unguarded. Used only as the RED state."""
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, str(root))
            files.append(rel)
    return files


def relpath_raises_on_nul(path, start=os.curdir):
    text = str(path).replace("/", "\\")
    leaf = text.rsplit("\\", 1)[-1]
    stem = leaf.split(".")[0].upper()
    if stem == "NUL" or text.startswith("\\\\.\\") or "\\\\.\\NUL" in text:
        raise OSError(22, "Invalid argument — reserved device name", path)
    return os.path.relpath(path, start)


def main() -> int:
    # 1. Device-shaped path must not raise from the production helper.
    try:
        device_rel = safe_relpath(r"\\.\NUL", r"C:\estate")
    except Exception as exc:  # noqa: BLE001
        return fail(f"safe_relpath(\\\\.\\NUL) raised {type(exc).__name__}:{exc}")
    if not device_rel:
        return fail("safe_relpath(\\\\.\\NUL) returned empty")

    try:
        long_win = "\\\\?\\C:\\estate\\" + ("a" * 280) + "\\NUL"
        long_device = safe_relpath(long_win, r"C:\estate")
    except Exception as exc:  # noqa: BLE001
        return fail(f"safe_relpath long \\\\?\\ path raised {type(exc).__name__}:{exc}")

    with tempfile.TemporaryDirectory(prefix="imp0385-nul-") as tmp_s:
        tmp = Path(tmp_s)
        seeded = run_nul_seeded_walk(tmp)
        if seeded.get("aborted"):
            return fail(f"NUL walk aborted errors={seeded.get('errors')}")
        if seeded.get("file_count") != 2:
            return fail(f"NUL tree file_count={seeded.get('file_count')} want=2")
        if not seeded.get("nul_present"):
            return fail("NUL file missing from walk names")
        if not seeded.get("keep_present"):
            return fail("keep.txt missing — crash swallowed as partial walk")
        if "Traceback" in (seeded.get("stderr") or ""):
            return fail("NUL walk leaked a traceback on stderr")

        # With vs without NUL: counts differ by exactly one; neither raises.
        without_dir = tmp / "without"
        without_dir.mkdir()
        (without_dir / "keep.txt").write_text("keep\n", encoding="utf-8")
        without = walk_files(without_dir)
        if without.aborted:
            return fail(f"without-NUL walk aborted {without.errors}")
        if without.file_count != 1:
            return fail(f"without-NUL file_count={without.file_count} want=1")
        if seeded["file_count"] - without.file_count != 1:
            return fail(
                f"with-NUL {seeded['file_count']} minus without {without.file_count} != 1"
            )

        # Long path above 260 characters must still enumerate.
        long_root = tmp / "long"
        chunk = "p" * 70
        long_leaf = long_root / chunk / chunk / chunk / chunk / "SKILL.md"
        long_leaf.parent.mkdir(parents=True, exist_ok=True)
        long_leaf.write_text("---\nname: long-path-skill\n---\n\nlong\n", encoding="utf-8")
        long_path_len = len(str(long_leaf))
        long_walk = walk_files(long_root)
        if long_walk.aborted:
            return fail(f"long-path walk aborted {long_walk.errors}")
        if long_walk.file_count != 1:
            return fail(f"long-path file_count={long_walk.file_count} want=1")
        if long_path_len <= 260:
            return fail(f"long path only {long_path_len} chars, need >260")

        # Both-states: inject Windows-like relpath failure on NUL.
        red_exc = None
        red_count = None
        orig = os.path.relpath
        os.path.relpath = relpath_raises_on_nul  # type: ignore[method-assign]
        try:
            try:
                naive_files = naive_relpath_walk(tmp)
                red_count = len(naive_files)
            except OSError as exc:
                red_exc = f"{type(exc).__name__}:{exc}"
                red_count = 0
            green = walk_files(tmp)
        finally:
            os.path.relpath = orig  # type: ignore[method-assign]

        if red_count != 0 and red_exc is None:
            return fail(
                "naive walker did not hit the planted NUL relpath failure "
                f"(count={red_count}); control is silent in the bad state"
            )
        if green.aborted:
            return fail(
                "production walk aborted under relpath monkeypatch "
                f"errors={green.errors} — still calling os.path.relpath on NUL?"
            )
        green_names = {f.name for f in green.files}
        if "NUL" not in green_names or "keep.txt" not in green_names:
            return fail(f"production walk under monkeypatch names={sorted(green_names)}")
        if green.file_count == 0 and not green.errors:
            return fail("crash-swallowed-as-zero: count=0 with empty errors")

    payload = {
        "probe": "probe2-nul-relpath",
        "unit_id": "IMP-0385",
        "pass": True,
        "reviewer_id": "IMP-0385-probe2-nul-relpath",
        "starts_from": "tests (NUL walk + relpath regression), not author summary",
        "independent": True,
        "safe_relpath_device": device_rel,
        "safe_relpath_long_device": long_device,
        "nul_seeded": {
            "file_count": seeded["file_count"],
            "names": seeded["names"],
            "stderr": seeded["stderr"],
            "stderr_empty_of_traceback": "Traceback" not in (seeded["stderr"] or ""),
            "errors": seeded["errors"],
            "aborted": seeded["aborted"],
            "safe_relpath_nul_file": seeded["safe_relpath_nul_file"],
        },
        "count_with_nul": seeded["file_count"],
        "count_without_nul": without.file_count,
        "counts_differ_by_one": seeded["file_count"] - without.file_count == 1,
        "long_path_chars": long_path_len,
        "long_path_enumerated": long_walk.file_count == 1,
        "both_states": {
            "naive_relpath_red": True,
            "naive_exception": red_exc,
            "naive_count": red_count,
            "production_green": True,
            "production_count": green.file_count,
            "crash_not_swallowed_as_zero": green.file_count > 0,
        },
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"nul_count={seeded['file_count']} without={without.file_count} "
        f"naive_red={red_exc or red_count} long_chars={long_path_len}"
    )
    print("SUCCESS:IMP-0385-probe2 NUL relpath walk survival")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
