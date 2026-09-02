"""Hostile path shapes for CNF-0152.

Five catalog instantiations plus an independent sixth (trailing-dot / trailing-space)
that Windows strips and a naive packager silently collides.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

RESERVED_STEMS = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)
RESERVED_RE = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.[^.]+)?$",
    re.IGNORECASE,
)
WIN_MAX_PATH = 260
PHASE0_NUL_ERROR = "path is on mount '\\\\.\\NUL'"

SHAPE_IDS = (
    "a-long-root",
    "b-reserved-device",
    "c-case-collision",
    "d-non-ascii",
    "e-spaces",
)
SIXTH_ID = "f-trailing-dot-space"


@dataclass
class ShapeTree:
    shape_id: str
    title: str
    root: Path
    files: list[Path]
    hazard_paths: list[Path]
    notes: str
    extra: dict = field(default_factory=dict)

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()


def is_reserved_name(name: str) -> bool:
    return bool(RESERVED_RE.match(name))


def reserved_stem(name: str) -> str | None:
    m = RESERVED_RE.match(name)
    return m.group(1).upper() if m else None


def windows_device_path(name: str) -> str | None:
    stem = reserved_stem(name)
    if stem is None:
        return None
    return f"\\\\.\\{stem}"


def naive_win_relpath(path: str, start: str) -> str:
    """Reproduce the Phase-0 enumerator crash on reserved device names.

    POSIX os.path.relpath does not raise on a file literally named NUL.
    Windows does, once the path is the device mount \\\\.\\NUL. The naive
    walker rewrites reserved names onto that mount then calls relpath.
    """
    name = os.path.basename(path.replace("\\", "/"))
    device = windows_device_path(name)
    if device is not None:
        raise ValueError(f"path is on mount '{device}'")
    return os.path.relpath(path, start)


def naive_win_strip_trailing(name: str) -> str:
    return name.rstrip(" .")


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


def _wipe(root: Path) -> None:
    if not root.exists():
        return
    for p in sorted(root.rglob("*"), reverse=True):
        if p.is_file() or p.is_symlink():
            p.unlink()
        elif p.is_dir():
            p.rmdir()
    if root.exists():
        root.rmdir()


def build_all(work: Path) -> dict[str, ShapeTree]:
    work.mkdir(parents=True, exist_ok=True)
    trees = {
        "a-long-root": build_long_root(work / "a-long-root"),
        "b-reserved-device": build_reserved(work / "b-reserved-device"),
        "c-case-collision": build_case(work / "c-case-collision"),
        "d-non-ascii": build_non_ascii(work / "d-non-ascii"),
        "e-spaces": build_spaces(work / "e-spaces"),
        SIXTH_ID: build_trailing(work / SIXTH_ID),
    }
    return trees


def build_long_root(base: Path) -> ShapeTree:
    """Walk root whose absolute path exceeds 260 characters."""
    _wipe(base)
    pad_needed = WIN_MAX_PATH + 1 - len(str(base.resolve()))
    pad = "L" * max(pad_needed, 8)
    root = (base / pad).resolve()
    if len(str(root)) <= WIN_MAX_PATH:
        extra = "M" * (WIN_MAX_PATH + 1 - len(str(root)))
        root = (root / extra).resolve()
    ordinary = _write(root / "ordinary.txt", "control\n")
    deep = _write(root / "nested" / "deep.txt", "deep\n")
    assert len(str(root)) > WIN_MAX_PATH, len(str(root))
    return ShapeTree(
        shape_id="a-long-root",
        title="walk root exceeding 260 characters",
        root=root,
        files=[ordinary, deep],
        hazard_paths=[root, deep],
        notes=(
            "Catalog shape (a). Naive MAX_PATH truncation skips every file "
            "under a root whose absolute path is already past 260."
        ),
        extra={"root_path_length": len(str(root)), "win_max_path": WIN_MAX_PATH},
    )


def build_reserved(base: Path) -> ShapeTree:
    _wipe(base)
    root = base.resolve()
    ordinary = _write(root / "ordinary.txt", "control-not-reserved\n")
    # Put NUL in the root so sorted os.walk hits it before CON/AUX/PRN
    # (and before ordinary.txt: 'NUL' < 'ordinary.txt'). That reproduces
    # the Phase-0 error string rather than a later reserved-name cousin.
    hazards = [_write(root / "NUL", "reserved:NUL\n")]
    for name in ("CON", "AUX", "PRN"):
        hazards.append(_write(root / "devices" / name, f"reserved:{name}\n"))
    return ShapeTree(
        shape_id="b-reserved-device",
        title="Windows reserved device names NUL/CON/AUX/PRN",
        root=root,
        files=[ordinary, *hazards],
        hazard_paths=hazards,
        notes=(
            "Catalog shape (b). Phase-0 enumerator crashed with "
            f"{PHASE0_NUL_ERROR!r} because os.path.relpath cannot handle "
            "a file literally named NUL on Windows. A swallowed crash "
            "reports every count as 0."
        ),
        extra={"reserved_names": [p.name for p in hazards]},
    )


def build_case(base: Path) -> ShapeTree:
    _wipe(base)
    root = base.resolve()
    a = _write(root / "ReadMe.txt", "CASE-A\n")
    b = _write(root / "readme.txt", "CASE-B\n")
    ordinary = _write(root / "other.txt", "control\n")
    # Linux ext4 keeps both; a case-insensitive parser collides them.
    names = sorted(p.name for p in root.iterdir() if p.is_file())
    return ShapeTree(
        shape_id="c-case-collision",
        title="case-distinct sibling names",
        root=root,
        files=[a, b, ordinary],
        hazard_paths=[a, b],
        notes=(
            "Catalog shape (c). Two siblings differing only by case must be "
            "detected, not silently deduplicated by a case-insensitive dict key."
        ),
        extra={
            "on_disk_names": names,
            "case_distinct_siblings_present": (
                "ReadMe.txt" in names and "readme.txt" in names
            ),
        },
    )


def build_non_ascii(base: Path) -> ShapeTree:
    _wipe(base)
    root = base.resolve()
    ordinary = _write(root / "plain.txt", "ascii-control\n")
    cafe = _write(root / "café.txt", "nfc-e-acute\n")
    jp = _write(root / "日本語.txt", "cjk\n")
    return ShapeTree(
        shape_id="d-non-ascii",
        title="non-ASCII path characters",
        root=root,
        files=[ordinary, cafe, jp],
        hazard_paths=[cafe, jp],
        notes=(
            "Catalog shape (d). Naive ASCII-only packaging silently drops "
            "non-ASCII names; hardened walk keeps UTF-8 paths."
        ),
        extra={
            "cafe_codepoints": [hex(ord(c)) for c in "café.txt"],
            "jp_name": "日本語.txt",
        },
    )


def build_spaces(base: Path) -> ShapeTree:
    _wipe(base)
    root = base.resolve()
    ordinary = _write(root / "nospace.txt", "control\n")
    spaced = _write(root / "a file with spaces.txt", "spaced\n")
    nested = _write(root / "dir with spaces" / "inner file.txt", "nested-space\n")
    return ShapeTree(
        shape_id="e-spaces",
        title="paths containing spaces",
        root=root,
        files=[ordinary, spaced, nested],
        hazard_paths=[spaced, nested],
        notes=(
            "Catalog shape (e). Naive shell-split packaging fragments a path "
            "on spaces so the original member is absent from the archive."
        ),
    )


def build_trailing(base: Path) -> ShapeTree:
    """Sixth shape: Windows trailing-dot / trailing-space stripping collision."""
    _wipe(base)
    root = base.resolve()
    keep = _write(root / "readme", "no-dot\n")
    dotted = _write(root / "readme.", "trailing-dot\n")
    spaced = _write(root / "readme ", "trailing-space\n")
    ordinary = _write(root / "ok.txt", "control\n")
    return ShapeTree(
        shape_id=SIXTH_ID,
        title="trailing-dot and trailing-space names (Windows strips them)",
        root=root,
        files=[keep, dotted, spaced, ordinary],
        hazard_paths=[keep, dotted, spaced],
        notes=(
            "Reviewer sixth shape, not in the catalog five. Windows strips "
            "trailing dots and spaces, so readme / readme. / 'readme ' collide. "
            "A naive strip silently keeps one; hardened reports the collision."
        ),
        extra={
            "on_disk_names": sorted(repr(p.name) for p in root.iterdir() if p.is_file())
        },
    )
