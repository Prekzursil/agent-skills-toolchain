"""Central last-mile coverage for a fail-open branch the per-module lanes left open.

Asserts REAL behavior only: when the OS lock backend keeps refusing the byte-range
lock in ``_FileLock.__enter__`` (another live process holds it), the acquisition
retries until the deadline, then raises ``TimeoutError`` -- it never lets the
backend's ``OSError`` escape, and it chains that ``OSError`` as the cause so the
operator can still see WHY the lock was refused.

History: until the 2026-09-02 reunion this file covered the O_EXCL lockfile's
stale-``stat`` race. That implementation was replaced by the live tree's OS-level
advisory lock (fcntl/msvcrt), which the kernel releases when the holder dies, so a
stale-lock probe no longer exists to race against.
"""

from __future__ import annotations

import pytest

import harness.ledger as L
from harness.ledger import _FileLock


def test_filelock_times_out_instead_of_leaking_the_backend_oserror(
    tmp_path, monkeypatch
):
    lock_path = tmp_path / "locks" / "ledger.lock"
    attempts: list[int] = []

    def refuse(self):
        attempts.append(1)
        raise OSError("resource temporarily unavailable")

    monkeypatch.setattr(L._FileLock, "_acquire", refuse)

    # timeout=0 -> the deadline is already past after the first refusal, so the
    # next check raises TimeoutError rather than leaking the OSError.
    with pytest.raises(TimeoutError, match="ledger lock unavailable") as info:
        _FileLock(lock_path, timeout=0.0).__enter__()

    assert attempts == [1]
    assert isinstance(info.value.__cause__, OSError)
    # The rendezvous file was created and seeded even though the lock was refused;
    # a later holder must lock the SAME inode.
    assert lock_path.is_file()
    assert lock_path.stat().st_size == 1
