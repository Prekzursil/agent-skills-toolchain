"""Regression suite for the PreCompact snapshot hook (D-c002).

Collected by the `gate-tests-coverage hooks regression harness` step in
.github/workflows/quality.yml, which runs `python -m pytest hooks/` over the whole
tree -- so this file needs no new named step to execute.

Two defects are pinned here, both measured against the pre-fix script:

1. `Test-Path $now` was the ONLY admission test, so a PreCompact firing repeatedly on an
   UNCHANGED buffer copied the whole body every time. Measured pre-fix: 4 invocations of a
   93.8 KB now.md produced 4 files / 1 distinct content hash / 375 KB.
2. The retention ring sorted on `LastWriteTime`, but `Copy-Item` PRESERVES the source's
   LastWriteTime, so each snapshot inherited now.md's mtime instead of its own capture
   time. Measured pre-fix with capture order FRESH-then-STALE: the ring evicted STALE --
   the NEWEST snapshot. The restore side is session-scoped
   (hooks/harness-trim/compact-restore.ps1:20), so a wrongly evicted session recovers
   nothing.

The structural checks parse CODE ONLY (full-line `#` comments are stripped first).
Asserting over the raw document would pass vacuously, because the fix's own comments
discuss `LastWriteTime` -- the use-versus-mention trap.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent / "snapshot.ps1"
REPO = HOOK.parents[2]
MIRROR = REPO / "agent-self/config/hooks/precompact-snapshot/snapshot.ps1"
LIVE_LOG = "C:/Users/Prekzursil/.claude/compaction-log.jsonl"

# The two behavioural cases execute the hook, so they are scoped to the only platform it
# can run on rather than to "wherever pwsh happens to exist". This target is Windows-only
# BY CONSTRUCTION: it appends to a hardcoded C:/Users/... log (snapshot.ps1:35), is
# checked in as CRLF (.gitattributes:17 `*.ps1 eol=crlf`), and its paired read-back side
# uses Windows separators (harness-trim/compact-restore.ps1:17). ubuntu-latest ships pwsh,
# so gating on `which pwsh` alone would run them on a platform the hook never targets and
# where FileInfo.CreationTime -- the retention sort key -- has no reliable birthtime.
# The three structural cases above are platform-independent and keep the Linux lane honest.
windows_only = pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("pwsh") is None,
    reason="hook is Windows-only (hardcoded C:/ log path, CRLF, \\-separated restore side)",
)


def code_only(text: str) -> str:
    """Drop full-line comments so a mention in prose cannot satisfy a code assertion."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def test_config_mirror_is_byte_identical() -> None:
    """agent-self/config/ carries a deployable copy; the two must not drift apart."""
    assert MIRROR.is_file(), f"missing mirror: {MIRROR}"
    assert HOOK.read_bytes() == MIRROR.read_bytes(), (
        "hooks/precompact-snapshot/snapshot.ps1 and its agent-self/config mirror "
        "diverged; patch both trees."
    )


def test_retention_ring_does_not_sort_on_inherited_mtime() -> None:
    """Copy-Item preserves the source mtime, so LastWriteTime is not the capture time."""
    code = code_only(HOOK.read_text(encoding="utf-8"))
    assert "Sort-Object LastWriteTime" not in code, (
        "retention ring sorts on LastWriteTime, which Copy-Item inherits from now.md; "
        "it therefore evicts by buffer edit time, not by capture time."
    )
    assert "Sort-Object CreationTime" in code, "ring must order by capture time"


def test_duplicate_body_guard_is_present() -> None:
    """An unchanged buffer must not be admitted again on path existence alone."""
    code = code_only(HOOK.read_text(encoding="utf-8"))
    assert "Get-FileHash" in code, (
        "no content/hash guard before Copy-Item: an unchanged now.md is re-copied in "
        "full on every PreCompact."
    )


@windows_only
def test_unchanged_buffer_is_snapshotted_once(tmp_path: Path) -> None:
    """Behavioural: N compactions of an unchanged buffer leave ONE snapshot body.

    Runs the real hook with only the hardcoded global compaction-log path redirected
    into tmp_path, so the operator's live log is never touched. The copy/retention
    logic under test is unmodified.

    Invocations must land in DISTINCT seconds: the snapshot filename carries a
    per-second stamp, so two writes inside one second reuse the same name and
    `Copy-Item -Force` overwrites -- which would mask the defect.
    """
    src = HOOK.read_text(encoding="utf-8")
    redirected = src.replace(LIVE_LOG, (tmp_path / "compaction-log.jsonl").as_posix())
    assert redirected != src, "log-path redirect did not apply; refusing to touch it"
    hook = tmp_path / "snapshot-under-test.ps1"
    hook.write_text(redirected, encoding="utf-8")

    proj = tmp_path / "proj"
    (proj / ".remember").mkdir(parents=True)
    buf = proj / ".remember/now.md"
    buf.write_text("durable line" * 8000, encoding="utf-8")
    before = buf.read_bytes()

    payload = json.dumps(
        {
            "trigger": "auto",
            "session_id": "sess-AAAA-1111",
            "cwd": str(proj),
            "transcript_path": "x.jsonl",
        }
    )
    for i in range(3):
        subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(hook)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if i < 2:
            time.sleep(1.1)

    snaps = sorted((proj / ".remember/tmp").glob("precompact-*.md"))
    assert len(snaps) == 1, (
        f"3 compactions of an unchanged buffer produced {len(snaps)} snapshot bodies "
        f"({sum(s.stat().st_size for s in snaps)} bytes); expected 1"
    )
    assert snaps[0].read_bytes() == before, "snapshot body must match the buffer"
    assert buf.read_bytes() == before, "hook must not mutate the source buffer"


@windows_only
def test_changed_buffer_still_produces_a_new_snapshot(tmp_path: Path) -> None:
    """Guards the dedup fix itself: a CHANGED buffer must still be captured.

    Deduplicating on content is only safe if it never suppresses a real recovery point.
    Same-second writes reuse one filename, so the edits are spaced into distinct seconds.
    """
    src = HOOK.read_text(encoding="utf-8")
    redirected = src.replace(LIVE_LOG, (tmp_path / "compaction-log.jsonl").as_posix())
    assert redirected != src, "log-path redirect did not apply; refusing to touch it"
    hook = tmp_path / "snapshot-under-test.ps1"
    hook.write_text(redirected, encoding="utf-8")

    proj = tmp_path / "proj"
    (proj / ".remember").mkdir(parents=True)
    buf = proj / ".remember/now.md"
    payload = json.dumps(
        {
            "trigger": "auto",
            "session_id": "sess-BBBB-2222",
            "cwd": str(proj),
            "transcript_path": "x.jsonl",
        }
    )

    bodies = [
        "first turn\n",
        "first turn\nsecond turn\n",
        "first turn\nsecond turn\n3\n",
    ]
    for i, body in enumerate(bodies):
        buf.write_text(body, encoding="utf-8")
        subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(hook)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if i < len(bodies) - 1:
            time.sleep(1.1)

    snaps = sorted((proj / ".remember/tmp").glob("precompact-*.md"))
    assert len(snaps) == len(bodies), (
        f"{len(bodies)} distinct buffer states produced {len(snaps)} snapshots; the "
        "dedup guard must not suppress a changed buffer"
    )
    captured = {s.read_text(encoding="utf-8") for s in snaps}
    assert captured == set(bodies), (
        f"captured bodies do not match the edits: {captured}"
    )
