"""Hostile filesystem fixtures: reserved names, long paths, cycles (TST-0335)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from harness_walker.paths import extended_length_form


def build_hostile_tree(
    raw,
    *,
    include_nul=True,
    include_long=True,
    include_cycle=True,
    include_plain=True,
    include_secret=False,
    include_dangling=False,
):
    root = Path(raw)
    root.mkdir(parents=True, exist_ok=True)
    meta = {
        "root": str(root),
        "nul_relpath": None,
        "long_relpath": None,
        "long_path": None,
        "long_path_len": 0,
    }
    if include_plain:
        (root / "ok.txt").write_text("ok" + chr(10), encoding="utf-8")
    if include_nul:
        reserved_dir = root / "reserved"
        reserved_dir.mkdir(parents=True, exist_ok=True)
        target = reserved_dir / "NUL"
        created = False
        try:
            ext_path = extended_length_form(target)
            fd = os.open(ext_path, os.O_WRONLY | os.O_CREAT)
            os.write(fd, b"nul-body\n")
            os.close(fd)
            created = True
        except OSError:
            created = False
        if not created:
            target.write_bytes(b"nul-body\n")
        meta["nul_path"] = str(target)
        meta["nul_relpath"] = "reserved/NUL"
    if include_long:
        chunk = "p" * 20
        cur = root
        while len(str(cur)) < 260:
            cur = cur / chunk
            cur.mkdir(parents=True, exist_ok=True)
        long_file = cur / ("leaf" + "x" * 40 + ".txt")
        try:
            os.makedirs(extended_length_form(long_file.parent), exist_ok=True)
            fd = os.open(extended_length_form(long_file), os.O_WRONLY | os.O_CREAT)
            os.write(fd, b"long\n")
            os.close(fd)
        except OSError:
            long_file.parent.mkdir(parents=True, exist_ok=True)
            long_file.write_text("long\n", encoding="utf-8")
        meta["long_path"] = str(long_file)
        meta["long_path_len"] = len(str(long_file))
        try:
            meta["long_relpath"] = str(long_file.relative_to(root)).replace("\\", "/")
        except ValueError:
            meta["long_relpath"] = long_file.name
    if include_cycle:
        cycle_dir = root / "cycle"
        cycle_dir.mkdir(exist_ok=True)
        link = cycle_dir / "back"
        try:
            os.symlink(str(root), str(link), target_is_directory=True)
        except OSError:
            (cycle_dir / "back.txt").write_text("cycle-placeholder\n", encoding="utf-8")
        meta["cycle"] = str(link)
    if include_secret:
        sec_dir = root / "unreadable"
        sec_dir.mkdir(parents=True, exist_ok=True)
        (sec_dir / "secret.txt").write_text("secret\n", encoding="utf-8")
    if include_dangling:
        try:
            os.symlink(
                os.path.join(str(root), "missing-target"),
                str(root / "dangling.link"),
            )
        except OSError:
            (root / "dangling.link").write_text("not-a-link\n", encoding="utf-8")
    return meta
