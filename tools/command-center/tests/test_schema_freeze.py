#!/usr/bin/env python3
"""CC-0012 tests: unversioned edit RED; bump+migration GREEN; round-trip; both-states."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import schema_freeze as sf  # noqa: E402

FREEZE = {
    "activated": True,
    "activation_commit": "abc123",
    "frozen_paths": [
        "command-center/schema/receipt.schema.json",
        "platform/schema/receipt.schema.json",
    ],
}


def test_unversioned_frozen_edit_is_red() -> None:
    result = sf.check_edit(
        FREEZE,
        rel_path="command-center/schema/receipt.schema.json",
        old_sha256="aa" * 32,
        new_sha256="bb" * 32,
        version_bumped=False,
        migration_id=None,
        migration_roundtrip_ok=False,
    )
    assert result["verdict"] == "RED"


def test_bump_plus_migration_roundtrip_is_green() -> None:
    result = sf.check_edit(
        FREEZE,
        rel_path="command-center/schema/receipt.schema.json",
        old_sha256="aa" * 32,
        new_sha256="bb" * 32,
        version_bumped=True,
        migration_id="m001-receipt-core-example",
        migration_roundtrip_ok=True,
    )
    assert result["verdict"] == "GREEN"


def test_roundtrip_forward_back_byte_identical() -> None:
    migration = json.loads(
        (
            REPO / "command-center/schema/migrations/m001-receipt-core-example.json"
        ).read_text(encoding="utf-8")
    )
    sample = {"schema_version": 1, "legacy_note": "hello", "keep": 1}
    assert sf.roundtrip_ok(sample, migration)
    forward = sf.migrate_forward(sample, migration)
    assert forward["schema_version"] == 2
    assert "note" in forward and "legacy_note" not in forward


def test_non_frozen_path_is_silent() -> None:
    result = sf.check_edit(
        FREEZE,
        rel_path="README.md",
        old_sha256="aa" * 32,
        new_sha256="bb" * 32,
        version_bumped=False,
        migration_id=None,
        migration_roundtrip_ok=False,
    )
    assert result["verdict"] == "SILENT"
    assert result["frozen"] is False


def test_inactive_freeze_is_silent_even_on_listed_path() -> None:
    inactive = {**FREEZE, "activated": False}
    result = sf.check_edit(
        inactive,
        rel_path="command-center/schema/receipt.schema.json",
        old_sha256="aa" * 32,
        new_sha256="bb" * 32,
        version_bumped=False,
        migration_id=None,
        migration_roundtrip_ok=False,
    )
    assert result["verdict"] == "SILENT"
