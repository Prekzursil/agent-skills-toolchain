"""IMP-0005: inventory diff classifies added / removed / grown paths."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inventory_diff as inv  # noqa: E402


def test_added_removed_grown_classification() -> None:
    previous = {
        "artifact": "payload-inventory",
        "plugin": "demo",
        "version": "1.0.0",
        "total_bytes": 30,
        "file_count": 3,
        "entries": [
            {"path": "kept.txt", "size": 10, "sha256": "a" * 64, "rule": "r"},
            {"path": "gone.txt", "size": 5, "sha256": "b" * 64, "rule": "r"},
            {"path": "grew.bin", "size": 15, "sha256": "c" * 64, "rule": "r"},
        ],
        "forbidden_classes_checked": ["vcs"],
        "forbidden_matches": [],
    }
    current = {
        "artifact": "payload-inventory",
        "plugin": "demo",
        "version": "1.1.0",
        "total_bytes": 110,
        "file_count": 3,
        "entries": [
            {"path": "kept.txt", "size": 10, "sha256": "a" * 64, "rule": "r"},
            {"path": "new.txt", "size": 20, "sha256": "d" * 64, "rule": "r"},
            # same path, larger size → grown (even if hash also changed)
            {"path": "grew.bin", "size": 80, "sha256": "e" * 64, "rule": "r"},
        ],
        "forbidden_classes_checked": ["vcs"],
        "forbidden_matches": [],
    }
    diff = inv.inventory_diff(previous, current)
    assert diff["artifact"] == "payload-inventory-diff"
    assert diff["added"] == ["new.txt"]
    assert diff["removed"] == ["gone.txt"]
    assert len(diff["grown"]) == 1
    g = diff["grown"][0]
    assert g["path"] == "grew.bin"
    assert g["bytes_before"] == 15
    assert g["bytes_after"] == 80
    assert g["delta_bytes"] == 65
    assert diff["bytes_before"] == 30
    assert diff["bytes_after"] == 110
    assert diff["files_before"] == 3
    assert diff["files_after"] == 3


def test_shrunk_path_is_not_grown() -> None:
    previous = {
        "entries": [{"path": "x", "size": 100, "sha256": "a" * 64, "rule": "r"}],
        "total_bytes": 100,
        "file_count": 1,
    }
    current = {
        "entries": [{"path": "x", "size": 40, "sha256": "b" * 64, "rule": "r"}],
        "total_bytes": 40,
        "file_count": 1,
    }
    diff = inv.inventory_diff(previous, current)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["grown"] == []
