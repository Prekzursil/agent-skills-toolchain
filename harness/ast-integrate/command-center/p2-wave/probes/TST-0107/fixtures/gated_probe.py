#!/usr/bin/env python3
"""Gated status probe: would spawn a helper. Must not run on an idle session."""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    subprocess.run(["tst0107-probe"], check=False, capture_output=True)
    print("gated-probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
