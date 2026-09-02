#!/usr/bin/env python3
"""Mirror a remote worker's NDJSON onto this disk for ``mon cockpit`` pane 4.

The unified monitor never SSHs. This puller is the only network hop: it copies
``<remote>:<remote_path>`` to ``~/.claude/remote-workers/<name>/events.ndjson``
and optionally points ``current`` at that worker.

Works for Scaleway, Databricks log harvest, Modal, a second laptop — anything
that can emit the adapter records (``kind`` + ``unit_id`` + ``ts``).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from monitorcore.remote_workers import EVENTS_NAME, workers_root


def pull_once(
    *,
    name: str,
    source: str,
    identity: str | None,
    remote_path: str,
    home: str | None = None,
) -> Path:
    dest_dir = workers_root(home) / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / EVENTS_NAME
    tmp = dest.with_suffix(".ndjson.partial")
    if source in {"", "local"} or Path(source).is_file():
        src_path = Path(remote_path if source in {"", "local"} else source)
        if not src_path.is_file():
            raise FileNotFoundError(src_path)
        shutil.copyfile(src_path, tmp)
    else:
        cmd = [
            "scp",
            "-q",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
        ]
        if identity:
            cmd.extend(["-i", identity])
        cmd.extend([f"{source}:{remote_path}", str(tmp)])
        subprocess.run(cmd, check=True)
    tmp.replace(dest)
    current = workers_root(home) / "current"
    if current.exists() or current.is_symlink():
        if current.is_symlink() or current.is_dir():
            if current.is_symlink():
                current.unlink()
            elif (
                current / EVENTS_NAME
            ).exists() and current.resolve() != dest_dir.resolve():
                # leave a real directory named current alone if it already holds events
                pass
    if not current.exists():
        try:
            current.symlink_to(dest_dir, target_is_directory=True)
        except OSError:
            current.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dest, current / EVENTS_NAME)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", default="p2-r2e", help="worker directory name")
    ap.add_argument(
        "--source",
        default=os.environ.get("P2_SSH", ""),
        help="user@host, or a local file",
    )
    ap.add_argument("--remote-path", default="/opt/p2/status.jsonl")
    ap.add_argument("--identity", default=os.environ.get("P2_SSH_KEY", ""))
    ap.add_argument(
        "--loop-s", type=float, default=0.0, help="re-pull every N seconds (0=once)"
    )
    args = ap.parse_args()
    try:
        dest = pull_once(
            name=args.name,
            source=args.source,
            identity=args.identity or None,
            remote_path=args.remote_path,
        )
    except Exception as exc:
        print(f"FAILED:remote-pull {exc}")
        return 1
    print(f"SUCCESS:remote-pull {dest}")
    if args.loop_s > 0:
        import time

        while True:
            time.sleep(args.loop_s)
            try:
                pull_once(
                    name=args.name,
                    source=args.source,
                    identity=args.identity or None,
                    remote_path=args.remote_path,
                )
            except Exception as exc:
                print(f"FAILED:remote-pull {exc}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
