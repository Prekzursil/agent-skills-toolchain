"""Central last-mile coverage for a fail-open branch the per-module lanes left open.

Asserts REAL behavior only: when the stale-lock mtime probe in ``_FileLock.__enter__``
raises ``OSError`` mid-acquisition (a TOCTOU race where the held lock vanishes under
``stat``), the acquisition swallows it (ledger.py 450-451) and keeps trying until the
deadline, then raises ``TimeoutError`` -- it never lets the ``OSError`` escape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.ledger import _FileLock


def test_filelock_swallows_oserror_from_stale_lock_stat(tmp_path, monkeypatch):
    lock_path = tmp_path / "locks" / "ledger.lock"
    lock_path.parent.mkdir(parents=True)
    # An existing lock file makes the O_EXCL open raise FileExistsError, so the
    # stale-lock cleanup path (which stat()s the lock) is entered.
    lock_path.write_text("4242", encoding="utf-8")

    real_stat = Path.stat

    def raising_stat(self, *args, **kwargs):
        if self == lock_path:
            raise OSError("stale-lock stat race")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", raising_stat)

    # timeout=0 -> the deadline is already past once the stat race is swallowed,
    # so the next check raises TimeoutError rather than leaking the OSError.
    with pytest.raises(TimeoutError, match="ledger lock unavailable"):
        _FileLock(lock_path, timeout=0.0).__enter__()
