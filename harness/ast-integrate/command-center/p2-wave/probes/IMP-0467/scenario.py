"""Live evidence runner for IMP-0467: reserved-name + long-path fixtures."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

import windows_safe_path as wsp  # noqa: E402

ORDINARY_FILES = (
    ("keep/a.txt", "ordinary-a\n"),
    ("keep/b.txt", "ordinary-b\n"),
    ("nested/c.txt", "ordinary-c\n"),
)
NUL_REL = "NUL"
NUL_BODY = "reserved-nul-body\n"
MARKER_NAME = "marker.txt"
MARKER_BODY = "LONGPATH-MARKER-IMP-0467\n"
LONG_TARGET = 280


def _join(root: str, rel: str) -> str:
    return root.rstrip("/\\") + "/" + rel.replace("\\", "/").lstrip("/")


def build_ordinary(root: str) -> None:
    for rel, body in ORDINARY_FILES:
        wsp.write_text(_join(root, rel), body)


def add_nul(root: str) -> str:
    path = _join(root, NUL_REL)
    wsp.write_text(path, NUL_BODY)
    return path


def add_long_path(root: str, target: int = LONG_TARGET) -> dict:
    cur = _join(root, "long")
    os.makedirs(wsp.native_fs_path(cur), exist_ok=True)
    depth = 0
    segment = "D" * 80
    marker = _join(cur, MARKER_NAME)
    while len(marker) < target:
        depth += 1
        cur = _join(cur, segment)
        os.makedirs(wsp.native_fs_path(cur), exist_ok=True)
        marker = _join(cur, MARKER_NAME)
        if depth > 24:
            break
    wsp.write_text(marker, MARKER_BODY)
    rel = wsp.safe_relpath(marker, root)
    return {
        "path": marker,
        "relpath": rel,
        "char_len": len(marker),
        "depth": depth,
        "payload": MARKER_BODY,
        "windows_extended_path": wsp.windows_extended_path(marker),
        "needs_prefix": wsp.needs_extended_length_prefix(marker),
    }


def summarize_walk(result: wsp.WalkResult) -> dict:
    files = result.files()
    return {
        "entry_count": result.entry_count(),
        "file_count": result.file_count(),
        "dir_count": len(result.dirs()),
        "error_count": len(result.errors),
        "errors": result.errors,
        "file_relpaths": sorted(e.relpath for e in files),
        "reserved_file_relpaths": sorted(
            e.relpath for e in files if e.reserved_stem
        ),
        "reserved_stems": sorted(
            {e.reserved_stem for e in files if e.reserved_stem}
        ),
    }


def classify_reserved_table() -> list[dict]:
    rows = []
    for name in (
        "NUL",
        "nul",
        "NUL.txt",
        "CON",
        "AUX",
        "PRN",
        "COM1",
        "LPT9",
        "readme.txt",
        "null",
        "CONSOLE",
    ):
        stem = wsp.reserved_stem(name)
        rows.append(
            {
                "component": name,
                "reserved": stem is not None,
                "stem": stem,
            }
        )
    return rows


def run_evidence() -> dict:
    tmp = tempfile.mkdtemp(prefix="imp0467-")
    try:
        without_root = _join(tmp, "without")
        os.makedirs(without_root, exist_ok=True)
        build_ordinary(without_root)
        walk_without = wsp.walk_tree(without_root)
        oracle_without = wsp.posix_file_count(without_root)
        swallow_without = wsp.swallowing_walk_count(without_root)

        with_root = _join(tmp, "with")
        os.makedirs(with_root, exist_ok=True)
        build_ordinary(with_root)
        nul_path = add_nul(with_root)
        walk_with = wsp.walk_tree(with_root)
        oracle_with = wsp.posix_file_count(with_root)
        swallow_with = wsp.swallowing_walk_count(with_root)
        rel_nul = wsp.safe_relpath(nul_path, with_root)
        naive_error = None
        naive_raised = False
        try:
            wsp.naive_windows_relpath(nul_path, with_root)
        except ValueError as exc:
            naive_raised = True
            naive_error = str(exc)

        long_root = _join(tmp, "longtree")
        os.makedirs(long_root, exist_ok=True)
        build_ordinary(long_root)
        marker = add_long_path(long_root)
        walk_long = wsp.walk_tree(long_root)
        marker_body_read = wsp.read_text(marker["path"])
        marker_found = any(
            e.relpath == marker["relpath"] for e in walk_long.files()
        )

        delta_files = walk_with.file_count() - walk_without.file_count()
        delta_oracle = oracle_with - oracle_without

        return {
            "host_os": os.name,
            "platform": sys.platform,
            "library": "command-center/lib/windows_safe_path.py",
            "reserved_classifier": classify_reserved_table(),
            "without_reserved": {
                **summarize_walk(walk_without),
                "oracle_os_walk_files": oracle_without,
                "swallowing_count": swallow_without,
            },
            "with_reserved": {
                **summarize_walk(walk_with),
                "oracle_os_walk_files": oracle_with,
                "swallowing_count": swallow_with,
                "nul_path": nul_path,
                "nul_relpath": rel_nul,
                "nul_body": NUL_BODY,
            },
            "delta": {
                "library_file_count": delta_files,
                "oracle_file_count": delta_oracle,
                "required": 1,
            },
            "relpath": {
                "safe": rel_nul,
                "is_device_mount": rel_nul.startswith("\\\\.\\")
                or rel_nul.upper().startswith("//./"),
                "naive_raised": naive_raised,
                "naive_error": naive_error,
            },
            "swallow_control": {
                "ordinary_tree_library_entries": walk_without.entry_count(),
                "ordinary_tree_swallow_count": swallow_without,
                "reserved_tree_library_entries": walk_with.entry_count(),
                "reserved_tree_library_files": walk_with.file_count(),
                "reserved_tree_swallow_count": swallow_with,
                "swallow_zeros_reserved_tree": swallow_with == 0,
                "library_nonzero_reserved_tree": walk_with.file_count() > 0,
                # swallowing_walk_count counts FILES, so the silent-on-good
                # comparison must be against the library's file count, not
                # its file+dir entry count.
                "both_states_ordinary_match": swallow_without
                == walk_without.file_count(),
            },
            "long_path": {
                **marker,
                "walk_file_count": walk_long.file_count(),
                "marker_found": marker_found,
                "marker_body_matches": marker_body_read == MARKER_BODY,
                "above_260": marker["char_len"] > 260,
            },
            "neither_walk_raised": True,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def answers(ev: dict) -> dict:
    return {
        "enumerates_completely": ev["delta"]["library_file_count"] == 1
        and ev["neither_walk_raised"]
        and "NUL" in ev["with_reserved"]["reserved_stems"],
        "count_without_reserved_files": ev["without_reserved"]["file_count"],
        "count_with_reserved_files": ev["with_reserved"]["file_count"],
        "delta": ev["delta"]["library_file_count"],
        "neither_run_raised": ev["neither_walk_raised"],
        "relpath_for_NUL": ev["relpath"]["safe"],
        "relpath_is_device_mount": ev["relpath"]["is_device_mount"],
        "naive_windows_relpath_raises": ev["relpath"]["naive_raised"],
        "long_path_chars": ev["long_path"]["char_len"],
        "long_path_above_260": ev["long_path"]["above_260"],
        "swallow_returns_zero_on_reserved": ev["swallow_control"][
            "swallow_zeros_reserved_tree"
        ],
        "library_does_not_return_zero_on_reserved": ev["swallow_control"][
            "library_nonzero_reserved_tree"
        ],
    }
