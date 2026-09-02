"""Child process for BLD-0027 executed fault scenarios."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _burn(seconds: float) -> None:
    end = time.perf_counter() + seconds
    acc = 0
    while time.perf_counter() < end:
        acc += 1
    if acc < 0:
        raise RuntimeError("unreachable")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: worker.py <mode> <path> [cpu_path]", file=sys.stderr)
        return 2
    mode = argv[0]
    path = Path(argv[1])
    cpu_path = Path(argv[2]) if len(argv) > 2 else path.with_suffix(path.suffix + ".cpu")
    stop = path.with_suffix(path.suffix + ".stop")
    n = 0
    if mode in {"exit0-missing", "exit0"}:
        return 0
    while not stop.exists():
        _write(cpu_path, f"{time.process_time():.6f}\n")
        if mode == "grow":
            with path.open("ab") as handle:
                handle.write(b"x")
                handle.flush()
                os.fsync(handle.fileno())
        elif mode == "quiet":
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(b"seed")
            _burn(0.05)
        elif mode == "heartbeat":
            _write(path, str(n))
            n += 1
        else:
            print(f"unknown mode {mode}", file=sys.stderr)
            return 2
        _burn(0.02)
        time.sleep(0.01)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
