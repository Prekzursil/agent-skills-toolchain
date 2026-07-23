#!/usr/bin/env python3
"""Compare skill roots by an LF-normalized, content-addressed census."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

SCHEMA = "skill-surface-census/v1"
_LEAF_DOMAIN = b"skill-surface-leaf/v1\0"
_ROOT_DOMAIN = b"skill-surface-root/v1\0"


class CensusError(RuntimeError):
    """The requested surface could not be censused completely and safely."""


@dataclass(frozen=True)
class SurfaceCensus:
    """Stable counts and content address for one realized skill root."""

    schema: str
    skill_count: int
    file_count: int
    merkle_sha256: str


def _raise_walk_error(error: OSError) -> None:
    raise error


def _skill_files(root: Path) -> tuple[set[str], list[tuple[bytes, Path]]]:
    if root.is_symlink() or not root.is_dir():
        raise CensusError(
            f"skill root is missing, not a directory, or a symlink: {root}"
        )

    try:
        children = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError as exc:
        raise CensusError(f"cannot enumerate skill root: {root}") from exc

    skill_dirs: list[Path] = []
    for child in children:
        if child.is_symlink():
            raise CensusError(
                f"symlink is not a realized skill directory: {child.name}"
            )
        marker = child / "SKILL.md"
        if child.is_dir() and marker.is_file() and not marker.is_symlink():
            skill_dirs.append(child)

    files: list[tuple[bytes, Path]] = []
    for skill_dir in skill_dirs:
        try:
            for dirpath, dirnames, filenames in os.walk(
                skill_dir, onerror=_raise_walk_error, followlinks=False
            ):
                directory = Path(dirpath)
                dirnames.sort()
                filenames.sort()
                for name in dirnames:
                    path = directory / name
                    if path.is_symlink():
                        relative = path.relative_to(root).as_posix()
                        raise CensusError(f"symlink in skill surface: {relative}")
                for name in filenames:
                    path = directory / name
                    relative = path.relative_to(root).as_posix()
                    if path.is_symlink():
                        raise CensusError(f"symlink in skill surface: {relative}")
                    if not path.is_file():
                        raise CensusError(
                            f"non-regular file in skill surface: {relative}"
                        )
                    files.append((relative.encode("utf-8"), path))
        except OSError as exc:
            raise CensusError(
                f"cannot enumerate skill directory: {skill_dir.name}"
            ) from exc

    return {path.name for path in skill_dirs}, sorted(files, key=lambda item: item[0])


def _normalized_digest(path: Path, root: Path) -> bytes:
    relative = path.relative_to(root).as_posix()
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise CensusError(f"cannot read skill file: {relative}") from exc
    if b"\0" not in content[:8000]:
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).digest()


def census_surface(root: Path, *, required_skill: str) -> SurfaceCensus:
    """Return a deterministic census, refusing an unvalidated empty/wrong root.

    A skill is an immediate child with a regular ``SKILL.md``. Every regular file
    below those children is hashed. Text-like files fold CRLF to LF; files with a
    NUL in their first 8 KiB remain byte-exact. Paths are sorted as UTF-8 bytes.
    """
    required_path = Path(required_skill)
    if (
        not required_skill
        or required_path.name != required_skill
        or required_skill in {".", ".."}
    ):
        raise CensusError("required skill must be one direct child name")

    skills, files = _skill_files(root)
    if required_skill not in skills:
        raise CensusError(f"required known-present skill is missing: {required_skill}")

    leaves: list[bytes] = []
    for path_bytes, path in files:
        content_digest = _normalized_digest(path, root)
        leaf = hashlib.sha256(
            _LEAF_DOMAIN
            + len(path_bytes).to_bytes(4, "big")
            + path_bytes
            + content_digest
        ).digest()
        leaves.append(leaf)
    merkle = hashlib.sha256(_ROOT_DOMAIN + b"".join(leaves)).hexdigest()
    return SurfaceCensus(SCHEMA, len(skills), len(files), merkle)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--require-skill", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        expected = census_surface(args.expected, required_skill=args.require_skill)
        actual = census_surface(args.actual, required_skill=args.require_skill)
    except CensusError as exc:
        print(json.dumps({"schema": SCHEMA, "error": str(exc)}), file=sys.stderr)
        return 2

    match = expected == actual
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "expected": asdict(expected),
                "actual": asdict(actual),
                "match": match,
            },
            sort_keys=True,
        )
    )
    return 0 if match else 1


if __name__ == "__main__":
    raise SystemExit(main())
