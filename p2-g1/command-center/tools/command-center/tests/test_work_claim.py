"""IMP-0409 work-claim: exclusive acquire, holder renew/release, mutation red."""
from __future__ import annotations

from pathlib import Path

import work_claim as wc


def test_second_acquire_is_typed_denied(tmp_path: Path):
    claims = tmp_path / "claims"
    first = wc.acquire(claims, "IMP-0409", "sess-a", ttl_seconds=60)
    second = wc.acquire(claims, "IMP-0409", "sess-b", ttl_seconds=60)
    assert first["status"] == wc.GRANTED
    assert second["status"] == wc.DENIED
    assert second["reason_code"] == wc.ALREADY_HELD


def test_renew_and_release_are_holder_only(tmp_path: Path):
    claims = tmp_path / "claims"
    granted = wc.acquire(claims, "IMP-0409", "holder", ttl_seconds=60)
    assert granted["status"] == wc.GRANTED
    assert wc.renew(claims, "IMP-0409", "other", ttl_seconds=60)["reason_code"] == wc.NOT_HOLDER
    renewed = wc.renew(claims, "IMP-0409", "holder", ttl_seconds=90)
    assert renewed["status"] == wc.GRANTED
    assert float((renewed["claim"] or {})["expires_at_unix"]) > float(
        (granted["claim"] or {})["expires_at_unix"]
    )
    assert wc.release(claims, "IMP-0409", "other")["reason_code"] == wc.NOT_HOLDER
    assert wc.release(claims, "IMP-0409", "holder")["status"] == wc.GRANTED
    assert not (claims / "IMP-0409.json").exists()


def test_concurrent_acquire_grants_exactly_one(tmp_path: Path):
    report = wc.run_concurrent_acquire(tmp_path, "IMP-0409", n=16)
    assert report["granted"] == 1
    assert report["denied"] == 15
    assert report["reason_counts"] == {wc.ALREADY_HELD: 15}


def test_mutant_without_exclusive_rename_turns_red(tmp_path: Path):
    mutant = wc.run_concurrent_acquire(
        tmp_path, "IMP-0409", n=16, publish=wc.PUBLISH_MUTANT
    )
    assert mutant["granted"] != 1
