#!/usr/bin/env python3
"""Probe 1: hostile fixture walked without crash and without silent omission.

Catalog tests: reserved name, 300-character path, NUL regression.
Independent of probe 2 (fail-closed + loops).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from harness_walker.baseline import naive_walk_crash_as_zero, naive_walk_raise
from harness_walker.fixtures import build_hostile_tree
from harness_walker.paths import extended_length_form, safe_relpath, windows_device_relpath
from harness_walker.walker import result_fingerprint, walk_tree

UNIT = "TST-0335"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0335-p1-") as raw:
        meta = build_hostile_tree(raw)
        first = walk_tree(raw)
        second = walk_tree(raw)

        files = first.readable_file_relpaths()
        fp_a = result_fingerprint(first)
        fp_b = result_fingerprint(second)

        # Control tree without NUL: counts must differ by exactly one file.
        with tempfile.TemporaryDirectory(prefix="tst0335-p1b-") as raw_b:
            build_hostile_tree(raw_b, include_nul=False)
            without = walk_tree(raw_b)
        delta = len(files) - len(without.readable_file_relpaths())

        nul_rel = meta.get("nul_relpath")
        long_rel = meta.get("long_relpath")
        long_form = extended_length_form(meta["long_path"]) if meta.get("long_path") else ""

        raised = None
        try:
            naive_walk_raise(raw)
        except ValueError as exc:
            raised = str(exc)

        swallowed = naive_walk_crash_as_zero(raw)
        safe = safe_relpath(meta["nul_path"], raw)

        payload = {
            "probe": "probe1-hostile-tree-no-crash",
            "unit_id": UNIT,
            "complete": first.complete,
            "entry_count": first.entry_count,
            "file_count": len(files),
            "unread_count": first.unread_count,
            "nul_relpath": nul_rel,
            "nul_in_files": nul_rel in files,
            "nul_reserved_seen": any("NUL" in p for p in first.reserved_names_seen),
            "safe_relpath_nul": safe.replace("\\", "/"),
            "long_path_len": meta["long_path_len"],
            "long_relpath": long_rel,
            "long_path_in_files": long_rel in files if long_rel else False,
            "extended_length_prefixed": long_form.startswith("\\\\?\\"),
            "extended_length_form_head": long_form[:24],
            "count_delta_with_vs_without_nul": delta,
            "phase0_raise": raised,
            "swallowed_zero": swallowed,
            "fingerprint_a": fp_a,
            "fingerprint_b": fp_b,
            "identical_rerun": fp_a == fp_b,
            "loop_detected": first.loop_detected,
            "platform": os.name,
            "euid": os.geteuid() if hasattr(os, "geteuid") else None,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"nul={nul_rel} long_len={meta['long_path_len']} "
            f"delta={delta} complete={first.complete} "
            f"prefixed={payload['extended_length_prefixed']}"
        )

        if not first.complete:
            return fail(f"hostile walk incomplete unread={first.unread}")
        if not payload["nul_in_files"]:
            return fail("NUL file missing from walker output")
        if not payload["nul_reserved_seen"]:
            return fail("reserved-name helper did not flag NUL")
        if safe.replace("\\", "/") != "reserved/NUL":
            return fail(f"safe_relpath returned {safe!r}")
        if meta["long_path_len"] < 300:
            return fail(f"long path len {meta['long_path_len']} < 300")
        if not payload["long_path_in_files"]:
            return fail("300-char path payload missing from walker output")
        if not payload["extended_length_prefixed"]:
            return fail(f"extended-length helper did not prefix {long_form!r}")
        if delta != 1:
            return fail(f"with/without NUL delta {delta} != 1")
        if raised is None or "\\\\.\\NUL" not in raised:
            return fail(f"phase-0 relpath did not raise on NUL: {raised!r}")
        if not swallowed["raised"] or swallowed["count"] != 0:
            return fail(f"swallowed crash was not zero: {swallowed}")
        if fp_a != fp_b:
            return fail("two walks of the same tree hashed differently")
        try:
            windows_device_relpath(meta["nul_path"], raw)
        except ValueError:
            pass
        else:
            return fail("windows_device_relpath did not raise on NUL")

        print(f"SUCCESS:{UNIT}-probe1 hostile fixture walked without crash")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
