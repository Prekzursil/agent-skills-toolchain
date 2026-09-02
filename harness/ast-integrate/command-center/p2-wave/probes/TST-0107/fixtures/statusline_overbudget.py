#!/usr/bin/env python3
"""Over-budget statusline: nested jq (and known-spawn) via PATH.

This is the mutant that proves the spawn-budget gate is load-bearing.
"""
from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    subprocess.run(["jq", "-n", "."], check=False, capture_output=True)
    subprocess.run(["tst0107-probe"], check=False, capture_output=True)
    model = (payload.get("model") or {}).get("display_name") or "?"
    print(f"{model} jq-shaped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
