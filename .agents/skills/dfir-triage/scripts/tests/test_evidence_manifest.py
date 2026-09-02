"""Offline tests for evidence_manifest.py — no network, tmp files only.

Each test tests the sibling evidence_manifest.py in the parent dir, so the
dual-write mirror under skills/dfir-triage/ verifies its own copy.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "evidence_manifest.py"
_spec = importlib.util.spec_from_file_location("evidence_manifest", _SCRIPT)
assert _spec and _spec.loader
em = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(em)


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_full_file_digest_matches_hashlib(tmp_path: Path) -> None:
    data = b"the quick brown fox\n" * 100
    p = _write(tmp_path, "evidence.bin", data)
    rec = em.manifest_record(str(p))
    assert rec["exists"] is True
    assert rec["error"] is None
    assert rec["algo"] == "sha256"
    assert rec["size"] == len(data)
    assert rec["bytes_hashed"] == len(data)
    assert rec["digest"] == hashlib.sha256(data).hexdigest()
    assert isinstance(rec["mtime_utc"], str) and rec["mtime_utc"]


def test_offset_and_length_slice(tmp_path: Path) -> None:
    p = _write(tmp_path, "carve.bin", b"0123456789")
    rec = em.manifest_record(str(p), offset=2, length=3)
    assert rec["offset"] == 2
    assert rec["length"] == 3
    assert rec["bytes_hashed"] == 3
    assert rec["digest"] == hashlib.sha256(b"234").hexdigest()


def test_length_clamped_at_eof(tmp_path: Path) -> None:
    p = _write(tmp_path, "tail.bin", b"0123456789")
    rec = em.manifest_record(str(p), offset=8, length=100)
    assert rec["bytes_hashed"] == 2
    assert rec["digest"] == hashlib.sha256(b"89").hexdigest()


def test_alternate_algorithm(tmp_path: Path) -> None:
    data = b"artifact"
    p = _write(tmp_path, "a.bin", data)
    rec = em.manifest_record(str(p), algo="md5")
    assert rec["algo"] == "md5"
    assert rec["digest"] == hashlib.md5(data).hexdigest()


def test_invalid_algorithm_raises(tmp_path: Path) -> None:
    p = _write(tmp_path, "a.bin", b"x")
    with pytest.raises(ValueError):
        em.manifest_record(str(p), algo="not-a-real-algo")


def test_missing_file_record(tmp_path: Path) -> None:
    rec = em.manifest_record(str(tmp_path / "nope.bin"))
    assert rec["exists"] is False
    assert rec["digest"] is None
    assert rec["error"]


def test_directory_is_error(tmp_path: Path) -> None:
    rec = em.manifest_record(str(tmp_path))
    assert rec["error"]
    assert rec["digest"] is None


def test_build_manifest_multiple(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.bin", b"aaaa")
    b = _write(tmp_path, "b.bin", b"bbbbbb")
    records = em.build_manifest([str(a), str(b)])
    assert len(records) == 2
    assert records[0]["digest"] == hashlib.sha256(b"aaaa").hexdigest()
    assert records[1]["size"] == 6


def test_main_json_output_exit_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    p = _write(tmp_path, "e.bin", b"hello")
    rc = em.main([str(p), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list) and len(out) == 1
    assert out[0]["digest"] == hashlib.sha256(b"hello").hexdigest()


def test_main_table_output_exit_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    p = _write(tmp_path, "e.bin", b"hello")
    rc = em.main([str(p)])
    assert rc == 0
    text = capsys.readouterr().out
    assert "sha256" in text
    assert "e.bin" in text


def test_main_missing_file_exit_one(tmp_path: Path) -> None:
    rc = em.main([str(tmp_path / "ghost.bin"), "--json"])
    assert rc == 1


def test_main_no_args_usage_exit_two(capsys: pytest.CaptureFixture) -> None:
    rc = em.main([])
    assert rc == 2
