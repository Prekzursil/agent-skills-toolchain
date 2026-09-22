#!/usr/bin/env python3
"""CC-0021 named probe: re-measure namespaces + run four catalog controls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools/command-center"))

import option_id_namespace as ns  # noqa: E402

PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-controls.json"
OUT_RAW = PROBE / "probe1-controls.raw.txt"


def main() -> int:
    payload = ns.run_controls(
        scratch_planted=PROBE / "fixtures/planted-bare-m16.md",
        mention_doc=PROBE / "fixtures/mention-collision-quote.md",
    )
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    OUT_JSON.write_text(text, encoding="utf-8")
    # Raw transcript includes printed regex + headline arithmetic.
    raw_lines = [
        "CC-0021 probe1 controls",
        f"REGEX BARE_M_RE={ns.BARE_M_RE.pattern!r}",
        f"REGEX MECH_NN_RE={ns.MECH_NN_RE.pattern!r}",
        f"REGEX FAMILY_M_CARD_RE={ns.FAMILY_M_CARD_RE.pattern!r}",
        f"ARITHMETIC {payload['measure']['arithmetic']}",
        f"live_shared_bare={payload['measure']['live_shared_bare_count']}",
        f"deep_research_m16_refs={payload['measure']['deep_research_m16_refs']}",
        f"deep_research_m16_files={payload['measure']['deep_research_m16_files']}",
        f"ok={payload['ok']}",
    ]
    for name, row in payload["controls"].items():
        raw_lines.append(f"control.{name}.pass={row['pass']}")
    raw_lines.append("--- json ---")
    raw_lines.append(text)
    OUT_RAW.write_text("\n".join(raw_lines), encoding="utf-8")
    print(OUT_RAW.read_text(encoding="utf-8"))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
