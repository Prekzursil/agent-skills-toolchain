#!/usr/bin/env python3
"""Second half of CNF-0015: MECH tokens vs present-tense collision in doc 17."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402


def analyze(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    line_175 = lines[174] if len(lines) >= 175 else ""
    mech = X.mech_token_count(text)
    present = X.present_tense_collision(text)
    stale = mech == 0 and present
    return {
        "path": str(path),
        "bytes": len(text.encode("utf-8")),
        "line_count": len(lines),
        "line_175": line_175,
        "mech_token_count": mech,
        "present_tense_collision": present,
        "stale_present_tense_with_zero_mech": stale,
        "stale_present_tense_with_zero_mech": stale,
        "stale_present_tense_with_zero_mech": stale,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: decision_log.py <17-DECISION-LOG.md>")
        return 2
    doc = analyze(Path(sys.argv[1]))
    print(json.dumps(doc, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
