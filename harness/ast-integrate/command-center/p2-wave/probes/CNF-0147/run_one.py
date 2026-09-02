#!/usr/bin/env python3
"""Run the confirmation suite once in the current network namespace."""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from suite import Env, all_tests  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--cache-dir", default="")
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()
    cache = Path(args.cache_dir) if args.cache_dir else None
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in all_tests():
        env = Env(port=args.port, cache_dir=cache, attempts=[])
        ok = True
        error = None
        try:
            spec.fn(env)
        except Exception as exc:
            ok = False
            error = f"{type(exc).__name__}: {exc}"
            error += "\n" + traceback.format_exc().splitlines()[-1]
        rows.append(
            {
                "id": spec.id,
                "ok": ok,
                "error": error,
                "declared_network": spec.declared_network,
                "claims_never_download": spec.claims_never_download,
                "attempts": env.attempts,
            }
        )
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"results": rows}, indent=2) + "\n", encoding="utf-8")
    failed = sum(1 for r in rows if not r["ok"])
    print(f"run_one tests={len(rows)} failed={failed} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
