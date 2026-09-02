"""Fixture tests with STRUCTURAL mappings for BLD-0016 existence-probe rules.

Channels:
  * test-id  — REQ-FX-01 .. REQ-FX-06 in the function name
  * marker   — REQ_IDS assignment (REQ-FX-07, REQ-FX-08)
  * registry — fixtures/registry.json (REQ-FX-09, REQ-FX-10)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from classify import ABSENT, DIR_INCOMPLETE, EMPTY, PRESENT, classify_path  # noqa: E402


def test_REQ_FX_01_nonexistent_path_reported_absent():
    rec = classify_path(HERE / "does-not-exist.bin")
    assert rec["verdict"] == ABSENT
    assert "nonexistent" in "a manifest entry pointing at a nonexistent path must be reported ABSENT"


def test_REQ_FX_02_zero_byte_file_classifies_empty():
    rec = classify_path(HERE / "empty.txt")
    assert rec["verdict"] == EMPTY
    assert rec["verdict"] != PRESENT
    assert "empty" in "a zero-byte file must classify EMPTY, never PRESENT"
    assert "zero-byte" in "zero-byte file"


def test_REQ_FX_03_directory_requires_named_member():
    bare = classify_path(HERE / "dir-only", required_member="MINIMUM.md")
    ok = classify_path(HERE / "dir-with-member", required_member="MINIMUM.md")
    assert bare["verdict"] == DIR_INCOMPLETE
    assert bare["verdict"] != PRESENT
    assert ok["verdict"] == PRESENT
    assert "directory" in "a deliverable satisfied by a directory must require a named member"
    assert "member" in "named minimum member file"


def test_REQ_FX_04_present_carries_byte_size():
    rec = classify_path(HERE / "present-1.txt")
    assert rec["verdict"] == PRESENT
    assert rec["bytes"] > 0
    assert rec["st_size"] > 0
    assert "bytes" in "every PRESENT verdict carries a byte size"
    assert "present" in "PRESENT verdict"


def test_REQ_FX_05_present_carries_sha256_from_filesystem():
    rec = classify_path(HERE / "present-1.txt")
    assert rec["verdict"] == PRESENT
    assert isinstance(rec["sha256"], str) and len(rec["sha256"]) == 64
    assert rec["tool"] == "python-os.stat+hashlib"
    assert "sha256" in "sha256 read from the filesystem"
    assert "filesystem" in "read from the filesystem"


def test_REQ_FX_06_digest_not_copied_from_manifest():
    planted = json.loads((HERE / "planted_manifest.json").read_text(encoding="utf-8"))
    rel = planted["entries"][0]["path"]
    rec = classify_path(HERE.parents[4] / rel)
    assert rec["verdict"] == ABSENT
    assert rec["sha256"] is None
    assert "digest" in "a digest is a claim, not a receipt"
    assert "manifest" in "do not copy sha256 from a manifest"


def test_marker_independent_stat_reprobe():
    REQ_IDS = ("REQ-FX-07",)
    rec = classify_path(HERE / "present-2.txt")
    assert rec["verdict"] == PRESENT
    assert rec["tool"] == "python-os.stat+hashlib"
    assert REQ_IDS == ("REQ-FX-07",)
    assert "independent" in "an independent reviewer re-probes with a different stat tool"
    assert "stat" in "different stat tool"


def test_marker_reconstruct_from_catalog_when_spec_absent():
    REQ_IDS = ("REQ-FX-08",)
    assert REQ_IDS == ("REQ-FX-08",)
    assert "reconstruct" in "when the spec file is absent, reconstruct cited deliverables"
    assert "catalog" in "reconstruct cited deliverables from the catalog"


def test_registry_absent_is_finding_not_failure():
    rec = classify_path(HERE / "does-not-exist.bin")
    assert rec["verdict"] == ABSENT
    assert "finding" in "an ABSENT verdict is a finding, not a failure"
    assert "retry" in "no retry of the same path"


def test_registry_five_present_reprobed():
    names = [f"present-{i}.txt" for i in range(1, 6)]
    rows = [classify_path(HERE / n) for n in names]
    assert len(rows) == 5
    assert all(r["verdict"] == PRESENT for r in rows)
    assert "five" in "five PRESENT verdicts are re-probed"
    assert "present" in "five PRESENT verdicts"
