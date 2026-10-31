#!/usr/bin/env python3
"""Live log-rotation scenarios for TST-0155.

Two independent signals:
  (a) the live reader's consumed complete-line list
  (b) complete lines of rotated-then-live bytes concatenated offline
PASS is exact list equality, not a count that could hide a swap.
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

from reader import (
    FollowReader,
    RecountOnRotateReader,
    StuckFdReader,
    ident_of_path,
    offline_concat_lines,
)

HERE = Path(__file__).resolve().parent
RUNTIME = HERE / "runtime"
N1 = 48
N2 = 27
PRE = "pre.{i:04d}"
POST = "post.{i:04d}"


def _wipe_runtime() -> None:
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME, ignore_errors=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)


def _live_and_rotated(name: str) -> tuple[Path, Path]:
    d = RUNTIME / name
    d.mkdir(parents=True, exist_ok=True)
    live = d / "monitor.log"
    rotated = d / "monitor.log.1"
    return live, rotated


def _poll_until(reader, done: threading.Event, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while not done.is_set() and time.monotonic() < deadline:
        reader.poll()
        time.sleep(0.003)
    reader.catch_up(80)


def _write_lines(path: Path, items: list[str], *, append: bool) -> None:
    mode = "ab" if append else "wb"
    with open(path, mode) as fp:
        for item in items:
            fp.write((item + "\n").encode("utf-8"))
            fp.flush()
            os.fsync(fp.fileno())
            time.sleep(0.0015)


def _rename_rotate(live: Path, rotated: Path) -> dict:
    before = ident_of_path(live)
    os.replace(live, rotated)
    Path(live).write_bytes(b"")
    after = ident_of_path(live)
    rot_id = ident_of_path(rotated)
    return {
        "live_inode_before": None if before is None else before[1],
        "live_inode_after": None if after is None else after[1],
        "rotated_inode": None if rot_id is None else rot_id[1],
        "inode_changed": before != after,
        "rotated_is_old_live": before == rot_id and before is not None,
    }


def _pack(reader, live: Path, rotated: Path, meta: dict) -> dict:
    offline, _frag = offline_concat_lines(rotated, live)
    consumed = list(reader.consumed)
    crash = bool(getattr(reader, "crashed", False))
    return {
        "monitor_lines": consumed,
        "monitor_count": len(consumed),
        "offline_lines": offline,
        "offline_count": len(offline),
        "match": consumed == offline,
        "crashed": crash,
        "crash_exc": getattr(reader, "crash_exc", None),
        "rotations": getattr(reader, "rotations", 0),
        "truncations": getattr(reader, "truncations", 0),
        "recounts": getattr(reader, "recounts", 0),
        "polls": getattr(reader, "polls", 0),
        "live_bytes": live.stat().st_size if live.is_file() else 0,
        "rotated_bytes": rotated.stat().st_size if rotated.is_file() else 0,
        "live_exists": live.is_file(),
        "rotated_exists": rotated.is_file(),
        "partial_remaining": getattr(reader, "partial", b"").decode(
            "utf-8", errors="replace"
        ),
        **meta,
    }


def rotation_between_writes(reader_cls=FollowReader) -> dict:
    live, rotated = _live_and_rotated("between-" + reader_cls.__name__)
    live.write_bytes(b"")
    reader = reader_cls(live)
    reader.poll()
    pre = [PRE.format(i=i) for i in range(N1)]
    post = [POST.format(i=i) for i in range(N2)]
    rotate_meta: dict = {}
    done = threading.Event()

    def writer() -> None:
        nonlocal rotate_meta
        _write_lines(live, pre, append=True)
        rotate_meta = _rename_rotate(live, rotated)
        _write_lines(live, post, append=True)
        done.set()

    t = threading.Thread(target=writer, name="tst0155-between", daemon=True)
    t.start()
    _poll_until(reader, done, 12.0)
    t.join(timeout=4.0)
    reader.catch_up(40)
    packed = _pack(reader, live, rotated, rotate_meta)
    packed["scenario"] = "rotation-between-writes"
    packed["reader"] = reader_cls.__name__
    packed["expected_count"] = N1 + N2
    packed["expected_first"] = pre[0]
    packed["expected_last"] = post[-1]
    packed["pass"] = (
        packed["match"]
        and not packed["crashed"]
        and packed["monitor_count"] == N1 + N2
        and packed["inode_changed"] is True
        and packed["rotated_is_old_live"] is True
        and packed["monitor_lines"][:N1] == pre
        and packed["monitor_lines"][N1:] == post
    )
    reader.close()
    return packed


def no_rotation_control(reader_cls=FollowReader) -> dict:
    live, rotated = _live_and_rotated("none-" + reader_cls.__name__)
    live.write_bytes(b"")
    reader = reader_cls(live)
    reader.poll()
    lines = [PRE.format(i=i) for i in range(N1)] + [
        POST.format(i=i) for i in range(N2)
    ]
    done = threading.Event()

    def writer() -> None:
        _write_lines(live, lines, append=True)
        done.set()

    t = threading.Thread(target=writer, name="tst0155-none", daemon=True)
    t.start()
    _poll_until(reader, done, 12.0)
    t.join(timeout=4.0)
    reader.catch_up(40)
    packed = _pack(reader, live, rotated, {"inode_changed": False})
    packed["scenario"] = "no-rotation"
    packed["reader"] = reader_cls.__name__
    packed["expected_count"] = N1 + N2
    packed["pass"] = (
        packed["match"]
        and not packed["crashed"]
        and packed["monitor_count"] == N1 + N2
        and packed["rotated_exists"] is False
        and packed["monitor_lines"] == lines
    )
    reader.close()
    return packed


def mid_line_rotation(reader_cls=FollowReader) -> dict:
    live, rotated = _live_and_rotated("midline-" + reader_cls.__name__)
    live.write_bytes(b"")
    reader = reader_cls(live)
    reader.poll()
    rotate_meta: dict = {}
    done = threading.Event()

    def writer() -> None:
        nonlocal rotate_meta
        with open(live, "ab") as fp:
            fp.write(b"HEAD-")
            fp.flush()
            os.fsync(fp.fileno())
        # Give the live reader a chance to park the fragment in `partial`
        # before the inode changes. Drain still recovers it if it missed.
        time.sleep(0.05)
        rotate_meta = _rename_rotate(live, rotated)
        with open(live, "ab") as fp:
            fp.write(b"TAIL\n")
            fp.flush()
            os.fsync(fp.fileno())
        done.set()

    t = threading.Thread(target=writer, name="tst0155-mid", daemon=True)
    t.start()
    _poll_until(reader, done, 8.0)
    t.join(timeout=4.0)
    reader.catch_up(40)
    packed = _pack(reader, live, rotated, rotate_meta)
    packed["scenario"] = "rotation-mid-line"
    packed["reader"] = reader_cls.__name__
    packed["expected_lines"] = ["HEAD-TAIL"]
    packed["pass"] = (
        packed["match"]
        and not packed["crashed"]
        and packed["monitor_lines"] == ["HEAD-TAIL"]
        and packed["inode_changed"] is True
        and packed["rotated_is_old_live"] is True
    )
    reader.close()
    return packed


def negative_stuck_fd() -> dict:
    row = rotation_between_writes(StuckFdReader)
    row["negative_id"] = "stuck-fd-misses-post-rotate"
    row["fired_on_bad_state"] = (
        not row["match"]
        and row["monitor_count"] == N1
        and row["offline_count"] == N1 + N2
        and not row["crashed"]
    )
    row["pass"] = row["fired_on_bad_state"]
    return row


def negative_recount() -> dict:
    row = rotation_between_writes(RecountOnRotateReader)
    row["negative_id"] = "recount-on-rotate-double-counts"
    row["fired_on_bad_state"] = (
        not row["match"]
        and row["monitor_count"] == 2 * N1 + N2
        and row["offline_count"] == N1 + N2
        and row["recounts"] == N1
        and not row["crashed"]
    )
    row["pass"] = row["fired_on_bad_state"]
    return row


def run_all() -> dict:
    _wipe_runtime()
    between = rotation_between_writes(FollowReader)
    none = no_rotation_control(FollowReader)
    mid = mid_line_rotation(FollowReader)
    stuck = negative_stuck_fd()
    recount = negative_recount()
    same_count = (
        between["monitor_count"] == none["monitor_count"] == N1 + N2
        and between["offline_count"] == none["offline_count"] == N1 + N2
    )
    ok = (
        between["pass"]
        and none["pass"]
        and mid["pass"]
        and stuck["pass"]
        and recount["pass"]
        and same_count
    )
    return {
        "pass": ok,
        "same_count_no_rotation_vs_rotation": same_count,
        "between": between,
        "no_rotation": none,
        "mid_line": mid,
        "negative_stuck_fd": stuck,
        "negative_recount": recount,
        "n1": N1,
        "n2": N2,
        "expected_total": N1 + N2,
    }


if __name__ == "__main__":
    import json

    doc = run_all()
    slim = {
        "pass": doc["pass"],
        "same_count": doc["same_count_no_rotation_vs_rotation"],
        "between_pass": doc["between"]["pass"],
        "between_match": doc["between"]["match"],
        "between_count": doc["between"]["monitor_count"],
        "offline_count": doc["between"]["offline_count"],
        "no_rotation_pass": doc["no_rotation"]["pass"],
        "mid_pass": doc["mid_line"]["pass"],
        "mid_lines": doc["mid_line"]["monitor_lines"],
        "stuck_fired": doc["negative_stuck_fd"]["fired_on_bad_state"],
        "recount_fired": doc["negative_recount"]["fired_on_bad_state"],
        "stuck_count": doc["negative_stuck_fd"]["monitor_count"],
        "recount_count": doc["negative_recount"]["monitor_count"],
    }
    print(json.dumps(slim, sort_keys=True))
    raise SystemExit(0 if doc["pass"] else 1)
