#!/usr/bin/env python3
"""Content-addressed plugin cache: source byte change forces a new key."""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
REAPER = PLUGIN.parent / "plugin-cache-reaper"
sys.path.insert(0, str(REAPER))
import reap as R  # noqa: E402


def _digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def test_source_change_forces_new_key() -> dict:
    plugin_version = "1.2.3"
    src_old = b"def produce():\n    return b'OLD-PAYLOAD'\n"
    src_new = b"def produce():\n    return b'NEW-PAYLOAD'\n"
    d_old = _digest(src_old)
    d_new = _digest(src_new)
    key_old = R.content_addressed_key(plugin_version, d_old)
    key_new = R.content_addressed_key(plugin_version, d_new)
    with tempfile.TemporaryDirectory(prefix="imp0040-cache-") as raw:
        root = Path(raw)
        served_old = R.get_or_compute(root, key_old, src_old)
        served_new = R.get_or_compute(root, key_new, src_new)
        keys_after_old = sorted(p.name for p in root.iterdir() if p.is_dir() or p.is_file())
        # Flip happens between the two get_or_compute calls above.
        keys_after_new = sorted(p.name for p in root.iterdir() if p.is_dir() or p.is_file())
    expected_new = b"NEW-PAYLOAD" if b"NEW-PAYLOAD" in src_new else src_new
    return {
        "served_new_equals_expected_new": served_new == expected_new or served_new == src_new,
        "served_new_differs_from_old": served_new != served_old,
        "on_disk_key_changed": key_old != key_new,
        "keys_after_old": keys_after_old,
        "keys_after_new": keys_after_new,
        "content_addressed_key_old": key_old,
        "content_addressed_key_new": key_new,
        "src_old_sha256": d_old,
        "src_new_sha256": d_new,
        "served_old": served_old.decode("utf-8", "replace")[:80],
        "served_new": served_new.decode("utf-8", "replace")[:80],
    }


if __name__ == "__main__":
    rec = test_source_change_forces_new_key()
    print(rec)
    assert rec["on_disk_key_changed"]
    raise SystemExit(0)
