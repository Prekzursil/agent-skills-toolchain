#!/usr/bin/env python3
"""Write command-center/receipts/CC-0019.json (does not write SUBAGENT-RETURN)."""
from __future__ import annotations

from normalize import write_artifact

if __name__ == "__main__":
    path = write_artifact()
    print(f"wrote {path}")
