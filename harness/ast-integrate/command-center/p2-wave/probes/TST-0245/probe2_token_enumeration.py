#!/usr/bin/env python3
"""Named probe 2: enumerate every coded element to its non-colour token.

Mechanically independent of probe 1's strip-and-compare. This probe parses
CSI spans from the coloured wire bytes and walks the palette registry.

Regression seed: colour is capped at four roles and each role is paired
with a glyph + text token. An oversize palette fails. A planted color-only
span is flagged. Deuteranopia collapse of red/green leaves tokens unique.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hud_emit as H  # noqa: E402

# Span parser owned by this probe, not by hud_emit.
SPAN_RE = re.compile(r"\x1b\[([0-9;]+)m(.*?)(?:\x1b\[0m|\x1b\[m)")


def fail(msg: str) -> int:
    print(f"FAILED:TST-0245-probe2 {msg}")
    return 1


def parse_spans(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in SPAN_RE.finditer(text)]


def inner_has_pair(inner: str, glyph: str, token: str) -> bool:
    parts = inner.split()
    return len(parts) >= 2 and parts[0] == glyph and parts[1] == token


def main() -> int:
    census = H.palette_census()
    if len(census) > H.MAX_PALETTE:
        return fail(f"live palette size {len(census)} exceeds cap {H.MAX_PALETTE}")
    if len(census) != H.MAX_PALETTE:
        return fail(f"expected a full scarce palette of {H.MAX_PALETTE}, got {len(census)}")

    glyphs = [c["glyph"] for c in census]
    tokens = [c["token"] for c in census]
    sgrs = [c["sgr"] for c in census]
    if any(len(g) != 1 or ord(g) > 127 for g in glyphs):
        return fail(f"glyphs must be single ASCII cells: {glyphs}")
    if len(set(glyphs)) != len(glyphs):
        return fail(f"duplicate glyphs: {glyphs}")
    if len(set(tokens)) != len(tokens):
        return fail(f"duplicate tokens: {tokens}")
    if any(not t.isalpha() or not t.isupper() for t in tokens):
        return fail(f"tokens must be uppercase alpha: {tokens}")
    if len(set(sgrs)) != len(sgrs):
        return fail(f"duplicate SGR codes: {sgrs}")
    if "31" not in sgrs or "32" not in sgrs:
        return fail("palette must use both red and green so CVD collapse is real")

    coloured = H.render_hud(H.FIXTURE_SNAPSHOT, color=True, pairing="glyph-token")
    spans = parse_spans(coloured)
    if len(spans) < H.MAX_PALETTE:
        return fail(f"wire parse found {len(spans)} CSI spans, expected >= {H.MAX_PALETTE}")

    by_sgr = {c["sgr"]: c for c in census}
    enumerated: list[dict[str, str]] = []
    for sgr, inner in spans:
        codes = [p for p in sgr.split(";") if p]
        fg = codes[-1] if codes else ""
        meta = by_sgr.get(fg)
        if meta is None:
            return fail(f"CSI span sgr={sgr!r} inner={inner!r} is not a palette role")
        if not inner_has_pair(inner, meta["glyph"], meta["token"]):
            return fail(
                f"span inner {inner!r} missing glyph {meta['glyph']!r} "
                f"or token {meta['token']!r}"
            )
        enumerated.append(
            {
                "sgr": fg,
                "glyph": meta["glyph"],
                "token": meta["token"],
                "inner_prefix": inner.split()[0] + " " + inner.split()[1],
                "cvd_class": meta["cvd_class"],
            }
        )

    roles_seen = {e["token"] for e in enumerated}
    if set(tokens) - roles_seen:
        return fail(f"wire missing tokens {set(tokens) - roles_seen}")

    # CVD: red and green collapse. Token identity must remain unique.
    classes = {c["cvd_class"] for c in census}
    if len(classes) >= len(census):
        return fail("CVD collapse did not reduce colour classes (red/green unused?)")
    identities = [(c["glyph"], c["token"]) for c in census]
    if len(set(identities)) != len(identities):
        return fail("glyph+token identities collide")

    # Planted color-only span must be flagged by THIS enumerator.
    mutant = H.render_hud(H.FIXTURE_SNAPSHOT, color=True, pairing="color-only")
    mutant_spans = parse_spans(mutant)
    flagged = []
    for sgr, inner in mutant_spans:
        codes = [p for p in sgr.split(";") if p]
        fg = codes[-1] if codes else ""
        meta = by_sgr.get(fg)
        glyph = meta["glyph"] if meta else ""
        token = meta["token"] if meta else ""
        if not inner_has_pair(inner, glyph, token):
            flagged.append({"sgr": fg, "inner": inner})
    if not flagged:
        return fail("color-only mutant was not flagged — enumerator is vacuous")

    oversize = H.mutant_oversize_palette()
    if len(oversize) <= H.MAX_PALETTE:
        return fail("oversize mutant did not exceed the cap")
    cap_fires = len(oversize) > H.MAX_PALETTE

    payload = {
        "probe": "probe2-token-enumeration",
        "unit_id": "TST-0245",
        "palette_size": len(census),
        "palette_cap": H.MAX_PALETTE,
        "coded_elements": [
            {
                "role": c["role"],
                "glyph": c["glyph"],
                "token": c["token"],
                "sgr": c["sgr"],
                "cvd_class": c["cvd_class"],
            }
            for c in census
        ],
        "wire_spans": enumerated,
        "cvd_classes": sorted(classes),
        "cvd_class_count": len(classes),
        "sgr_count": len(set(sgrs)),
        "color_only_flagged": len(flagged),
        "oversize_palette_size": len(oversize),
        "cap_fires_on_oversize": cap_fires,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"palette={len(census)} cap={H.MAX_PALETTE} cvd_classes={len(classes)} "
        f"color_only_flagged={len(flagged)} oversize={len(oversize)}"
    )
    print("SUCCESS:TST-0245-probe2 every coded element has glyph+token; colour capped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
