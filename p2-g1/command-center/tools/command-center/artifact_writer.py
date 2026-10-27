"""B07 artifact writer: length budget is applied to the RESOLVED path.

TST-0202 contract: a junction/symlink alias must not be the measured
quantity. ``write_artifact`` resolves first, then compares character length
to ``WINDOWS_MAX_PATH`` (Win32 MAX_PATH = 260), and refuses with zero
residue when the resolved destination is over budget.

``write_measuring_alias`` is the named defect: it applies the same budget
to the short lexical alias and therefore admits an over-limit write.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

WINDOWS_MAX_PATH = 260

__all__ = (
    "WINDOWS_MAX_PATH",
    "PathBudgetExceeded",
    "alias_length",
    "resolved_length",
    "write_artifact",
    "write_measuring_alias",
)


class PathBudgetExceeded(Exception):
    """Raised before any byte is written when the measured length is over budget.

    ``.check`` is a JSON-ready dict the probes copy on the exception path.
    """

    def __init__(self, message: str, *, check: dict[str, Any]) -> None:
        super().__init__(message)
        self.check = dict(check)
        self.check.setdefault("wrote", False)
        self.check.setdefault("error_name", "PathBudgetExceeded")


def alias_length(path: Path | str) -> int:
    """Character length of the lexical path; does not follow junctions/symlinks."""
    return len(os.fspath(path))


def resolved_length(path: Path | str) -> int:
    """Character length of ``pathlib.Path.resolve()`` (follows symlinks)."""
    return len(os.fspath(Path(path).resolve()))


def _residue_bytes(target: Path) -> int:
    try:
        if target.is_file():
            return int(target.stat().st_size)
    except OSError:
        return 0
    return 0


def _check(
    *,
    measured_length: int,
    measure: str,
    path: Path | str,
    resolved: Path,
    budget: int,
    residue_bytes: int,
    wrote: bool,
) -> dict[str, Any]:
    return {
        "measured_length": int(measured_length),
        "measure": measure,
        "path": os.fspath(path),
        "resolved_path": os.fspath(resolved),
        "budget": int(budget),
        "residue_bytes": int(residue_bytes),
        "wrote": bool(wrote),
    }


def _refuse(
    *,
    measured_length: int,
    measure: str,
    path: Path | str,
    resolved: Path,
    budget: int,
) -> None:
    residue = _residue_bytes(resolved)
    check = _check(
        measured_length=measured_length,
        measure=measure,
        path=path,
        resolved=resolved,
        budget=budget,
        residue_bytes=residue,
        wrote=False,
    )
    raise PathBudgetExceeded(
        (
            f"path budget exceeded: measured_length={measured_length} "
            f"budget={budget} measure={measure} path={os.fspath(path)!r} "
            f"resolved={os.fspath(resolved)!r}"
        ),
        check=check,
    )


def _commit(path: Path | str, data: bytes) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def write_artifact(
    path: Path | str,
    data: bytes,
    *,
    budget: int = WINDOWS_MAX_PATH,
) -> dict[str, Any]:
    """Write ``data`` only when the resolved destination is within ``budget``.

    Measurement is ``pathlib.Path.resolve()``. The short alias is ignored.
    Over-budget destinations raise ``PathBudgetExceeded`` with zero residue.
    """
    dest = Path(path)
    resolved = dest.resolve()
    measured = len(os.fspath(resolved))
    if measured > budget:
        _refuse(
            measured_length=measured,
            measure="resolved",
            path=path,
            resolved=resolved,
            budget=budget,
        )
    _commit(dest, data)
    return _check(
        measured_length=measured,
        measure="resolved",
        path=path,
        resolved=resolved,
        budget=budget,
        residue_bytes=0,
        wrote=True,
    )


def write_measuring_alias(
    path: Path | str,
    data: bytes,
    *,
    budget: int = WINDOWS_MAX_PATH,
) -> dict[str, Any]:
    """Defective control: apply the budget to the unresolved alias.

    A short symlink/junction whose resolved target exceeds ``budget`` is
    admitted. Production code must not call this.
    """
    dest = Path(path)
    resolved = dest.resolve()
    measured = alias_length(dest)
    if measured > budget:
        _refuse(
            measured_length=measured,
            measure="alias",
            path=path,
            resolved=resolved,
            budget=budget,
        )
    _commit(dest, data)
    return _check(
        measured_length=measured,
        measure="alias",
        path=path,
        resolved=resolved,
        budget=budget,
        residue_bytes=0,
        wrote=True,
    )
