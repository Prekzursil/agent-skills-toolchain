#!/usr/bin/env python3
"""Package size / file-count budget checker (IMP-0005).

Hard-fails when an emitted archive exceeds the allowlist's declared
``max_bytes`` or ``max_files``. Totals are computed from the archive itself
(via stdlib ``zipfile``), never copied from a caller-supplied size.

Independent probes must re-measure OS ``st_size`` and entry count with a
*different* archive library; a mismatch is a detector failure.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


class BudgetError(RuntimeError):
    """Emitted artifact exceeds declared max-bytes or max-file-count."""


@dataclass(frozen=True)
class BudgetTotals:
    """Totals the budget checker computed (signal 1)."""

    archive_path: str
    size_bytes: int
    file_count: int
    max_bytes: int
    max_files: int
    within_budget: bool
    over_bytes: int
    over_files: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_budget(allowlist: Mapping[str, Any] | Path | str) -> tuple[int, int]:
    """Return ``(max_bytes, max_files)`` from an allowlist doc or path."""
    if isinstance(allowlist, (str, Path)):
        doc = json.loads(Path(allowlist).read_text(encoding="utf-8"))
    else:
        doc = dict(allowlist)
    budget = doc.get("budget")
    if not isinstance(budget, dict):
        raise BudgetError("allowlist missing required budget object")
    try:
        max_bytes = int(budget["max_bytes"])
        max_files = int(budget["max_files"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BudgetError(f"allowlist budget malformed: {exc}") from exc
    if max_bytes < 0 or max_files < 0:
        raise BudgetError("budget max_bytes/max_files must be >= 0")
    return max_bytes, max_files


def measure_archive_zipfile(archive: Path | str) -> tuple[int, int]:
    """Compute (size_bytes, file_count) using stdlib zipfile + Path.stat.

    ``size_bytes`` is the on-disk archive size (what the budget constrains).
    ``file_count`` is the number of non-directory zip members.
    """
    path = Path(archive)
    if not path.is_file():
        raise BudgetError(f"archive not found: {path}")
    size_bytes = path.stat().st_size
    with zipfile.ZipFile(path, "r") as zf:
        file_count = sum(1 for info in zf.infolist() if not info.filename.endswith("/"))
    return size_bytes, file_count


def check_budget(
    archive: Path | str,
    *,
    max_bytes: int,
    max_files: int,
) -> BudgetTotals:
    """Measure archive totals and fail closed when over either ceiling."""
    size_bytes, file_count = measure_archive_zipfile(archive)
    over_bytes = max(0, size_bytes - max_bytes)
    over_files = max(0, file_count - max_files)
    within = over_bytes == 0 and over_files == 0
    totals = BudgetTotals(
        archive_path=str(archive),
        size_bytes=size_bytes,
        file_count=file_count,
        max_bytes=max_bytes,
        max_files=max_files,
        within_budget=within,
        over_bytes=over_bytes,
        over_files=over_files,
    )
    if not within:
        parts: list[str] = []
        if over_bytes:
            parts.append(
                f"size {size_bytes} bytes exceeds max_bytes={max_bytes} "
                f"(over by {over_bytes})"
            )
        if over_files:
            parts.append(
                f"file_count {file_count} exceeds max_files={max_files} "
                f"(over by {over_files})"
            )
        raise BudgetError("; ".join(parts))
    return totals


def assert_archive_within_budget(
    archive: Path | str,
    allowlist: Mapping[str, Any] | Path | str,
) -> BudgetTotals:
    """Load budget from allowlist and enforce it against ``archive``."""
    max_bytes, max_files = load_budget(allowlist)
    return check_budget(archive, max_bytes=max_bytes, max_files=max_files)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="IMP-0005 size/file-count budget check")
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--allowlist", type=Path, required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)
    try:
        totals = assert_archive_within_budget(args.archive, args.allowlist)
    except BudgetError as exc:
        print(f"FAILED:budget {exc}", flush=True)
        return 12
    if args.json:
        print(json.dumps(totals.as_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"SUCCESS:budget size_bytes={totals.size_bytes} "
            f"file_count={totals.file_count} "
            f"max_bytes={totals.max_bytes} max_files={totals.max_files}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
