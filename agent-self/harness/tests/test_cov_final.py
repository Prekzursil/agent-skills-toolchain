"""Last-mile coverage for the OS-backed ledger lock retry boundary.

The lock file is now a persistent inode whose ownership is represented by an OS byte
lock, not by file presence or mtime.  A transient backend ``OSError`` must therefore
stay inside the acquisition loop and become the stable public ``TimeoutError`` once
the caller's budget is exhausted.
"""

from __future__ import annotations

import pytest

from harness.ledger import _FileLock


def test_filelock_converts_backend_oserror_to_timeout(tmp_path, monkeypatch):
    lock_path = tmp_path / "locks" / "ledger.lock"

    def fail_backend(_lock):
        raise OSError("synthetic OS lock contention")

    monkeypatch.setattr(_FileLock, "_acquire", fail_backend)

    # timeout=0 makes the first failed non-blocking acquisition exhaust the budget.
    with pytest.raises(TimeoutError, match="ledger lock unavailable"):
        _FileLock(lock_path, timeout=0.0).__enter__()
