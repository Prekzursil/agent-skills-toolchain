"""Both-states tests for IMP-0434 atomic receipt writer."""

from __future__ import annotations

import json
import os
from pathlib import Path

import atomic_receipt as ar
import pytest


def test_write_read_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    doc = {"unit_id": "IMP-0434", "state": "SUCCESS", "n": 1}
    target = Path("command-center/receipts/roundtrip.json")
    ar.write_json_atomic(target, doc)
    assert target.is_file()
    assert ar.read_json(target) == doc
    # no leftover temps
    assert list(target.parent.glob(".*.tmp")) == []


def test_replace_overwrites_previous_completely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    target = Path("out/receipt.json")
    ar.write_json_atomic(target, {"v": 1})
    ar.write_json_atomic(target, {"v": 2, "extra": True})
    assert ar.read_json(target) == {"v": 2, "extra": True}


def test_kill_mid_write_leaves_old_or_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Broken state: writer dies after creating a temp but before replace.

    Good state: successful write leaves a complete file and no temps.
    """
    monkeypatch.chdir(tmp_path)
    target = Path("out/receipt.json")
    ar.write_json_atomic(target, {"ok": True})
    old = target.read_bytes()

    real_replace = os.replace

    def boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        # Simulate process death after temp exists, before publish.
        raise OSError("simulated kill before replace")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="simulated kill"):
        ar.write_json_atomic(target, {"partial": True, "pad": "x" * 1000})

    # Target must still be the old complete file (never half-new).
    assert target.read_bytes() == old
    assert json.loads(old.decode()) == {"ok": True}
    # Temps cleaned by the except path
    assert list(target.parent.glob(".*.tmp")) == []

    monkeypatch.setattr(os, "replace", real_replace)
    ar.write_json_atomic(target, {"ok": True, "v": 2})
    assert ar.read_json(target)["v"] == 2


def test_first_write_failure_leaves_no_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    target = Path("out/first.json")

    def boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        raise OSError("simulated kill before first publish")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        ar.write_json_atomic(target, {"n": 1})
    assert not target.exists()
    assert list(target.parent.glob(".*.tmp")) == []
