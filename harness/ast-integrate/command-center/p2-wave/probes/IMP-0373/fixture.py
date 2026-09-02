"""Isolated fixture tree for IMP-0373 retain/revert probes."""
from __future__ import annotations

from pathlib import Path

KEEP = b"keep-bytes-v1\n"
CHANGE = b"change-original\n"
UNRELATED = b"unrelated-must-not-move\n"
DEEP = b"nested-deep-original\n"


def build_tree(root: Path) -> dict[str, bytes]:
    """Create a small tree with files a candidate may and may not touch."""
    root.mkdir(parents=True, exist_ok=True)
    mapping = {
        "keep.txt": KEEP,
        "change.txt": CHANGE,
        "unrelated.txt": UNRELATED,
        "nested/deep.txt": DEEP,
    }
    for rel, data in mapping.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return mapping


def in_band() -> dict:
    return {
        "delta": 0.12,
        "noise_band": {"low": -0.5, "high": 0.5},
        "noise_band_source": "measured",
        "higher_is_better": True,
    }


def out_of_band() -> dict:
    return {
        "delta": 2.4,
        "noise_band": {"low": -0.5, "high": 0.5},
        "noise_band_source": "measured",
        "higher_is_better": True,
    }


def assumed_band() -> dict:
    return {
        "delta": 9.9,
        "noise_band": {"low": -0.01, "high": 0.01},
        "noise_band_source": "assumed",
        "higher_is_better": True,
    }
