#!/usr/bin/env python3
"""CC-0019 probe1: measure harness-restore corpus mount presence (no fabrication)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import corpus_normalize as cn  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
OUT_JSON = PROBE_DIR / "corpus-presence.json"
OUT_RAW = PROBE_DIR / "corpus-presence.raw.txt"


def main() -> int:
    report = cn.corpus_presence_probe()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    OUT_JSON.write_text(text, encoding="utf-8")

    lines = [
        "CC-0019 PROBE1 corpus-presence",
        f"REPO={REPO}",
        f"corpus_present={report['corpus_present']}",
        f"corpus_root={report['corpus_root']!r}",
        f"success_invented={report['success_invented']}",
        f"corpus_fabricated={report['corpus_fabricated']}",
        "candidates:",
    ]
    for row in report["candidates"]:
        lines.append(
            f"  path={row['path']!r} exists={row['exists']} "
            f"n_expected={row['n_expected_present']}"
        )
    if not report["corpus_present"]:
        lines.append(f"blocked_on={report['blocked_on_if_absent']}")
        lines.append("PROBE1_OK=True (honest ABSENT measurement)")
    else:
        lines.append("PROBE1_OK=True (corpus mount FOUND)")
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    # Probe itself always exits 0 when measurement succeeded; absence is data.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
