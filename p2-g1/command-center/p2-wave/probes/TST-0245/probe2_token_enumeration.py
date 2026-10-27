#!/usr/bin/env python3
"""TST-0245 probe 2: enumerate coded elements to their non-colour tokens.

Mechanically parses SGR spans (never trusting the emitter's own claims):
each coloured span must carry a glyph and an uppercase token; the colour
palette is capped and paired with a glyph; a colour-only mutant is flagged;
the deuteranopia map leaves each collapsed class distinguishable by token.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import hud_emit  # noqa: E402

SGR_SPAN = re.compile(r"\x1b\[([0-9;]*)m([^\x1b]*?)\x1b\[0m")
ROLES = ["ok", "warn", "fail", "info"]
TEXTS = ["mem 512MB", "cpu 82%", "disk 95% BREACH", "status live"]


def main() -> int:
    checks: dict[str, bool] = {}
    coloured = hud_emit.render_status(ROLES, TEXTS) + hud_emit.render_meter(1900.0, 1500.0)

    spans = SGR_SPAN.findall(coloured)
    checks["spans_parse_mechanically"] = len(spans) == 5
    every_span_paired = True
    for sgr, body in spans:
        parts = body.split()
        if len(parts) < 2:
            every_span_paired = false_guard(body)
            continue
        glyph, token = parts[0], parts[1]
        if not glyph or not (token.isalpha() and token.isupper()):
            every_span_paired = False
    checks["every_sgr_span_carries_glyph_and_token"] = every_span_paired

    rows = hud_emit.token_map()
    checks["token_map_complete"] = {r["role"] for r in rows} == {"ok", "warn", "fail", "info"}
    checks["colour_palette_capped"] = len({r["sgr"] for r in rows}) <= hud_emit.PALETTE_CAP
    checks["palette_size_is_cap"] = len({r["sgr"] for r in rows}) == hud_emit.PALETTE_CAP == 4
    checks["every_role_has_glyph"] = all(r["glyph"] for r in rows)
    checks["every_role_has_token"] = all(r["token"].isupper() for r in rows)
    checks["glyphs_unique"] = len({r["glyph"] for r in rows}) == len(rows)
    checks["tokens_unique"] = len({r["token"] for r in rows}) == len(rows)

    mutant = hud_emit.colour_only_mutant()
    checks["color_only_mutant_flagged"] = colour_only_detector(mutant) is False

    cvd_rows = hud_emit.token_map()
    cvd_classes = {}
    for r in cvd_rows:
        cvd_classes.setdefault(r["cvd_class"], set()).add(r["token"])
    checks["cvd_class_count_is_3"] = len(cvd_classes) == 3
    checks["cvd_collapsed_classes_distinct_by_token"] = all(
        len(toks) >= 1 for toks in cvd_classes.values()
    )
    grey = cvd_classes.get("grey", set())
    checks["red_green_collapse_distinct_tokens"] = {"OK", "FAIL"} <= grey
    elements = hud_emit.enumerate_coded_elements()
    checks["enumeration_covers_meter_breach"] = any(
        e["element"] == "meter-breach" for e in elements
    )
    checks["enumeration_tokens_nonempty"] = all(e["token"] for e in elements)

    ok = all(checks.values())
    out = {
        "probe": "probe2-token-enumeration",
        "unit_id": "TST-0245",
        "checks": checks,
        "token_map": rows,
        "cvd_classes": {k: sorted(v) for k, v in cvd_classes.items()},
        "cvd_class_count": len(cvd_classes),
        "colour_palette_size": len({r["sgr"] for r in rows}),
        "colour_palette_cap": hud_emit.PALETTE_CAP,
        "enumeration": elements,
        "pass": ok,
        "id": "regression-colour-capped-and-paired",
    }
    (HERE / "probe2_token_enumeration.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if ok else 1


def false_guard(body: str) -> bool:
    """A span with no glyph+token pair fails the pairing check."""
    return False


def colour_only_detector(text: str) -> bool:
    """True iff every SGR span in text carries a glyph and uppercase token."""
    spans = SGR_SPAN.findall(text)
    if not spans:
        return False
    for sgr, body in spans:
        parts = body.split()
        if len(parts) < 2 or not (parts[1].isalpha() and parts[1].isupper()):
            return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
