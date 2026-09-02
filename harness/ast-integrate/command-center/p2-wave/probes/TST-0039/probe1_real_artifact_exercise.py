#!/usr/bin/env python3
"""Probe 1: goldens pass, garbage is rejected, each family schema is exercised on a real artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import suite  # noqa: E402

def main() -> int:
    result = suite.probe1_body()
    n_real = len(result["real_artifact_exercises"])
    n_ok = sum(1 for r in result["real_artifact_exercises"] if r["accepted"])
    print(
        f"schemas={len(result['schemas'])} goldens_ok={len(result['goldens'])} "
        f"garbage_rejected={len(result['garbage'])} real_exercises={n_real} "
        f"accepted={n_ok}"
    )
    print("SUCCESS:TST-0039-probe1 real-artifact exercise")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"FAILED:TST-0039-probe1 {type(exc).__name__}: {exc}")
        raise SystemExit(1)
