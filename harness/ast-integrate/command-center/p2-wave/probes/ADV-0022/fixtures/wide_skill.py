#!/usr/bin/env python3
"""Wider-permission sibling body. Writes a beacon inside its own root."""
from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    beacon = Path(os.environ["ADV0022_SIBLING_BEACON"]).resolve()
    beacon.parent.mkdir(parents=True, exist_ok=True)
    beacon.write_text("sibling-ran\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
