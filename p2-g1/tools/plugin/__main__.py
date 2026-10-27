"""python -m plugin install --root HOME --source SRC [--dry-run] [--journal-out PATH]."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from plugin.execute import execute


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="plugin")
    sub = parser.add_subparsers(dest="cmd", required=True)
    inst = sub.add_parser("install")
    inst.add_argument("--root", required=True)
    inst.add_argument("--source", required=True)
    inst.add_argument("--dry-run", action="store_true")
    inst.add_argument("--journal-out")
    args = parser.parse_args(argv)
    result = execute(args.cmd, args.root, args.source, dry_run=args.dry_run)
    payload = result.as_dict()
    if args.journal_out:
        path = Path(args.journal_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"journal": result.journal}, indent=2) + "\n", encoding="utf-8")
        payload["journal_out"] = str(path)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
