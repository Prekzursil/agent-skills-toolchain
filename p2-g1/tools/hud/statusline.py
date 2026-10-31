#!/usr/bin/env python3
"""Minimal statusline renderer.

Comments mention jq / git / sleep because historical shells spawned those;
the live renderer does not. The spawn budget is measured by a PATH shim,
not by grepping this file.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Historical comment surface (detector control): jq git sleep true
SPAWN_CEILING = 4


def render(payload: dict, *, inject_spawn: str = "", slow: bool = False, cancel_ms: int = 0) -> str:
    import subprocess

    if inject_spawn:
        subprocess.run([inject_spawn], check=False, capture_output=True)
    if slow:
        subprocess.run(["true"], check=False, capture_output=True)
        if cancel_ms > 0:
            time.sleep(min(cancel_ms, 20) / 1000.0)
            return "CANCELLED\n"
        subprocess.run(["true"], check=False, capture_output=True)
        return "RENDERED-SLOW\n"
    model = payload.get("model") or "unknown"
    return f"statusline model={model} ok\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--payload", default="")
    p.add_argument("--state-dir", default="")
    p.add_argument("--debounce-ms", default="0")
    p.add_argument("--inject-spawn", default="")
    p.add_argument("--slow", action="store_true")
    p.add_argument("--cancel-ms", type=int, default=0)
    p.add_argument("--no-cancel", action="store_true")
    args = p.parse_args(argv)
    payload = {}
    if args.payload:
        import json

        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    cancel = 0 if args.no_cancel else int(args.cancel_ms or 0)
    sys.stdout.write(
        render(payload, inject_spawn=args.inject_spawn, slow=args.slow, cancel_ms=cancel)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
