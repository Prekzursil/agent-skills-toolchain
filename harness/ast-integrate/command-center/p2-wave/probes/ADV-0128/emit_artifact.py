#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0128-offline-and-partition-degrade-loudly.json."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness as H  # noqa: E402


def main() -> int:
    rec = H.write_artifact()
    print(
        f"wrote {H.ARTIFACT_REL} bytes={rec['_disk_bytes']} sha256={rec['_disk_sha256']}"
    )
    print(H.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
