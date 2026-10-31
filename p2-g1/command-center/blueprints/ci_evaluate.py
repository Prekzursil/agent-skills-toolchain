#!/usr/bin/env python3
"""CI hook: evaluate an emitted policy program against a subject JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from blueprints.policy_as_code import evaluate_program  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", required=True)
    parser.add_argument("--subject", required=True)
    args = parser.parse_args(argv)
    program = json.loads(Path(args.program).read_text(encoding="utf-8"))
    subject = json.loads(Path(args.subject).read_text(encoding="utf-8"))
    result = evaluate_program(program, subject)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("decision") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
