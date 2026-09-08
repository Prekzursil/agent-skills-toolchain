"""IMP-0005: over-budget archives fail closed; ceiling raise is the negative control."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import size_budget as budget_mod  # noqa: E402


def _write_zip(path: Path, members: dict[str, bytes]) -> Path:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_STORED) as zf:
        for name, blob in sorted(members.items()):
            zf.writestr(name, blob)
    path.write_bytes(bio.getvalue())
    return path


def test_over_budget_fails(tmp_path: Path) -> None:
    """Fixture archive larger than declared max_bytes must raise BudgetError."""
    archive = _write_zip(
        tmp_path / "fat.zip",
        {
            "a.txt": b"x" * 200,
            "b.txt": b"y" * 200,
        },
    )
    size_bytes, file_count = budget_mod.measure_archive_zipfile(archive)
    assert size_bytes > 0 and file_count == 2

    # Ceiling *below* measured size → must fail (positive over-budget proof).
    tight_bytes = max(1, size_bytes // 2)
    with pytest.raises(budget_mod.BudgetError, match="exceeds max_bytes"):
        budget_mod.check_budget(archive, max_bytes=tight_bytes, max_files=50)

    # File-count ceiling below measured count also fails.
    with pytest.raises(budget_mod.BudgetError, match="exceeds max_files"):
        budget_mod.check_budget(archive, max_bytes=size_bytes + 1000, max_files=1)

    # Within budget is silent / returns totals.
    totals = budget_mod.check_budget(archive, max_bytes=size_bytes + 1000, max_files=10)
    assert totals.within_budget is True
    assert totals.size_bytes == size_bytes
    assert totals.file_count == file_count


def test_over_budget_fails_via_allowlist(tmp_path: Path) -> None:
    archive = _write_zip(tmp_path / "p.zip", {"only.txt": b"hello-world"})
    size_bytes, _ = budget_mod.measure_archive_zipfile(archive)
    allow = {
        "artifact": "payload-allowlist",
        "policy": "deny-by-default",
        "rules": [{"glob": "only.txt", "reason": "t"}],
        "budget": {"max_bytes": max(1, size_bytes - 1), "max_files": 10},
        "forbidden_classes": {"vcs": [".git"]},
    }
    allow_path = tmp_path / "allow.json"
    allow_path.write_text(json.dumps(allow), encoding="utf-8")
    with pytest.raises(budget_mod.BudgetError):
        budget_mod.assert_archive_within_budget(archive, allow_path)
