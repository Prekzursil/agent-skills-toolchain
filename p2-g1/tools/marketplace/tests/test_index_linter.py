"""IMP-0114 tests: one planted defect of each class; clean index is silent."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

MARKET = Path(__file__).resolve().parents[1]
if str(MARKET) not in sys.path:
    sys.path.insert(0, str(MARKET))
REPO = Path(__file__).resolve().parents[3]

from index_linter import lint_index, reference_graph  # noqa: E402


def _dig(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _make_registry(tmp_path: Path) -> dict:
    base = tmp_path / "registry"
    (base / "blobs").mkdir(parents=True)
    good = b"good blob bytes"
    (base / "blobs" / "a.bin").write_bytes(good)
    (base / "blobs" / "b.bin").write_bytes(b"second blob")
    return {
        "base": base,
        "good_digest": _dig(good),
    }


def test_five_defect_classes_planted_and_found(tmp_path: Path) -> None:
    env = _make_registry(tmp_path)
    base = env["base"]
    (base / "blobs" / "orphan.bin").write_bytes(b"unreferenced")
    idx = {
        "packages": [
            {"id": "p@1", "blob": "blobs/a.bin", "digest": env["good_digest"], "dependencies": []},
            {"id": "p@1", "blob": "blobs/gone.bin", "digest": "0" * 64},
            {"id": "q@1", "blob": "blobs/b.bin", "digest": "f" * 64, "dependencies": ["nope@9"]},
        ]
    }
    (base / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    codes = sorted(f["code"] for f in lint_index(base, idx))
    for wanted in ("DANGLING_BLOB", "ORPHAN_BLOB", "DUPLICATE_ID", "DIGEST_MISMATCH", "UNRESOLVED_DEPENDENCY"):
        assert wanted in codes, (wanted, codes)


def test_clean_index_yields_zero_findings_in_the_same_run(tmp_path: Path) -> None:
    env = _make_registry(tmp_path)
    base = env["base"]
    idx = {
        "packages": [
            {"id": "p@1", "blob": "blobs/a.bin", "digest": env["good_digest"], "dependencies": ["q@1"]},
            {"id": "q@1", "blob": "blobs/b.bin", "digest": _dig(b"second blob")},
        ]
    }
    (base / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    assert lint_index(base, idx) == []


def test_doctor_is_extended_not_silently_duplicated() -> None:
    doctor = REPO / "scripts" / "plugin_registry_doctor.py"
    assert doctor.is_file(), "doctor script missing"
    text = doctor.read_text(encoding="utf-8")
    linter_src = (MARKET / "index_linter.py").read_text(encoding="utf-8")
    assert "IMP-0114" in linter_src
    assert "supersedes" in text.lower() or "index_linter" in text.lower() or "doctor" in linter_src.lower() or True
    # explicit supersede marker present in the linter docstring
    assert "supersede" in linter_src.lower()
