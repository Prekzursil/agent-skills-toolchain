#!/usr/bin/env python3
"""Delete stale Codex thread rows through the vendor CLI, never raw SQL writes."""

from __future__ import annotations

import argparse
import concurrent.futures
import pathlib
import shutil
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class StaleThread:
    session_id: str
    rollout_path: pathlib.Path


def _normalize_windows_path(path: pathlib.Path) -> pathlib.Path:
    text = str(path)
    if text.startswith("\\\\?\\"):
        text = text[4:]
    return pathlib.Path(text)


def _is_within(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        _normalize_windows_path(path).resolve(strict=False).relative_to(
            root.resolve(strict=False)
        )
        return True
    except ValueError:
        return False


def find_stale_threads(
    database: pathlib.Path, codex_home: pathlib.Path
) -> list[StaleThread]:
    allowed_roots = [codex_home / "sessions", codex_home / "archived_sessions"]
    connection = sqlite3.connect(
        f"file:{database.resolve().as_posix()}?mode=ro", uri=True
    )
    try:
        rows = connection.execute(
            "SELECT id, rollout_path FROM threads ORDER BY created_at, id"
        ).fetchall()
    finally:
        connection.close()

    stale: list[StaleThread] = []
    for raw_id, raw_path in rows:
        try:
            session_id = str(uuid.UUID(str(raw_id)))
        except ValueError:
            continue
        rollout_path = _normalize_windows_path(pathlib.Path(str(raw_path)))
        if not any(_is_within(rollout_path, root) for root in allowed_roots):
            continue
        if rollout_path.is_file():
            continue
        stale.append(StaleThread(session_id, rollout_path))
    return stale


def delete_stale_threads(
    stale: list[StaleThread],
    *,
    codex_command: str,
    limit: int | None,
    timeout_seconds: float,
    workers: int,
) -> tuple[int, int]:
    selected = stale if limit is None else stale[:limit]

    def delete_one(item: StaleThread) -> bool:
        try:
            completed = subprocess.run(
                [codex_command, "delete", "--force", item.session_id],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0

    deleted = 0
    failed_items: list[StaleThread] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(delete_one, item): item for item in selected}
        for index, future in enumerate(
            concurrent.futures.as_completed(futures), start=1
        ):
            if future.result():
                deleted += 1
            else:
                failed_items.append(futures[future])
            if index % 25 == 0:
                print(
                    "SUCCESS:stale-thread-progress "
                    f"attempted={index} deleted={deleted} failed={len(failed_items)}"
                )

    # Transient SQLite/app-server contention is retried serially once.
    persistent_failures: list[StaleThread] = []
    for item in failed_items:
        if delete_one(item):
            deleted += 1
        else:
            persistent_failures.append(item)
    failed = len(persistent_failures)
    return deleted, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-home", type=pathlib.Path, default=pathlib.Path.home() / ".codex"
    )
    parser.add_argument("--database", type=pathlib.Path)
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    database = args.database or args.codex_home / "state_5.sqlite"
    stale = find_stale_threads(database, args.codex_home)
    if args.dry_run:
        print(f"SUCCESS:stale-thread-dry-run candidates={len(stale)}")
        return 0

    codex_command = shutil.which(args.codex_command)
    if not codex_command:
        print("FAILED:stale-thread-cleanup codex-command-not-found")
        return 1

    deleted, failed = delete_stale_threads(
        stale,
        codex_command=codex_command,
        limit=args.limit,
        timeout_seconds=args.timeout_seconds,
        workers=args.workers,
    )
    remaining = find_stale_threads(database, args.codex_home)
    print(
        "SUCCESS:stale-thread-cleanup "
        f"candidates={len(stale)} deleted={deleted} failed={failed} remaining={len(remaining)}"
    )
    # A vendor command can return nonzero after its deletion has committed. The
    # authoritative acceptance condition is the fresh read-only inventory.
    return 1 if failed and remaining else 0


if __name__ == "__main__":
    raise SystemExit(main())
