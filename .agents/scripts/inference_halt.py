#!/usr/bin/env python3
"""``INFERENCE_HALT`` kill switch (C7), shared by the inference hub and the probe tool.

Halted means either the environment variable ``INFERENCE_HALT`` is one of
``1`` / ``true`` / ``yes`` (case-insensitive) or the file ``.agents/INFERENCE-HALT``
exists under the repo root. The env wins when both apply; the file's first
non-empty line is the recorded reason. These are the values ``policy.hub.haltEnv``
and ``policy.hub.haltFile`` name in ``.agents/models.json``.

The hub calls ``is_halted()`` on EVERY chat call, not once at startup, so setting
the switch stops the next call of an already-running hub; every chat then returns
the ``HALTED`` error class. Readers (``is_halted``, ``halt_reason``, ``--status``)
never write. ``--set "<reason>"`` and ``--clear`` are the only writes: they create
and remove the file.
"""

from __future__ import annotations

import argparse
import os
import pathlib
from collections.abc import Mapping

HALT_ENV = "INFERENCE_HALT"
HALT_FILE = pathlib.Path(".agents", "INFERENCE-HALT")
HALT_VALUES = frozenset({"1", "true", "yes"})
NO_REASON = "no reason recorded"


def default_repo_root() -> pathlib.Path:
    """The checkout holding this script (``<repo>/.agents/scripts/inference_halt.py``)."""
    return pathlib.Path(__file__).resolve().parents[2]


def halt_file(repo_root: pathlib.Path | None = None) -> pathlib.Path:
    return (repo_root or default_repo_root()) / HALT_FILE


def halt_reason(
    environ: Mapping[str, str] = os.environ, repo_root: pathlib.Path | None = None
) -> str | None:
    """Why inference is halted, or ``None`` when the switch is clear."""
    raw = environ.get(HALT_ENV, "").strip()
    if raw.lower() in HALT_VALUES:
        return f"env {HALT_ENV}={raw}"
    path = halt_file(repo_root)
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    reason = next((line.strip() for line in lines if line.strip()), NO_REASON)
    return f"file {path}: {reason}"


def is_halted(
    environ: Mapping[str, str] = os.environ, repo_root: pathlib.Path | None = None
) -> bool:
    return halt_reason(environ, repo_root) is not None


def set_halt(reason: str, repo_root: pathlib.Path | None = None) -> pathlib.Path:
    path = halt_file(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reason.strip() + "\n", encoding="utf-8")
    return path


def clear_halt(repo_root: pathlib.Path | None = None) -> bool:
    """Remove the halt file; returns whether it existed."""
    path = halt_file(repo_root)
    existed = path.is_file()
    path.unlink(missing_ok=True)
    return existed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--status",
        action="store_true",
        help="report the switch (default): HALTED exits 1, clear exits 0",
    )
    action.add_argument("--set", metavar="REASON", help="create the halt file")
    action.add_argument("--clear", action="store_true", help="remove the halt file")
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=None,
        help="checkout whose .agents/INFERENCE-HALT is read or written",
    )
    args = parser.parse_args(argv)

    if args.set is not None:
        path = set_halt(args.set, args.repo_root)
        print(f"SUCCESS:inference-halt set file={path}")
        return 0
    if args.clear:
        existed = clear_halt(args.repo_root)
        print(
            f"SUCCESS:inference-halt cleared file={halt_file(args.repo_root)} "
            f"existed={str(existed).lower()}"
        )
        return 0
    reason = halt_reason(os.environ, args.repo_root)
    if reason is not None:
        print(f"HALTED:inference {reason}")
        return 1
    print("SUCCESS:inference-halt clear")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
