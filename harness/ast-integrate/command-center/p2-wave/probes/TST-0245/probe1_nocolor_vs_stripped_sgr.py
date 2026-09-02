#!/usr/bin/env python3
"""Named probe 1: NO_COLOR rendering vs coloured rendering after stripping SGR.

Independent of the palette census in probe 2. This probe owns its own CSI
regex and never calls a strip helper from hud_emit.

Both-states: a threshold breach stays visible (glyph + FAIL + BREACH) when
colour is off. The colour-only mutant loses that coded signal after SGR
is stripped — proving the detector can see a colour-only regression.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hud_emit as H  # noqa: E402

# Independent of hud_emit: CSI SGR only, not a shared helper.
SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
BREACH_RE = re.compile(r"(?:^|\n)x FAIL .*BREACH(?:\n|$)")


def fail(msg: str) -> int:
    print(f"FAILED:TST-0245-probe1 {msg}")
    return 1


def strip_sgr(text: str) -> str:
    return SGR_RE.sub("", text)


def breach_visible(text: str) -> bool:
    return BREACH_RE.search(text) is not None


def main() -> int:
    snapshot = dict(H.FIXTURE_SNAPSHOT)
    coloured = H.render_hud(snapshot, color=True, pairing="glyph-token")
    nocolor = H.render_hud(snapshot, color=False, pairing="glyph-token")
    stripped = strip_sgr(coloured)

    if "\x1b[" not in coloured:
        return fail("coloured render contained no CSI — colour path is a no-op")
    if SGR_RE.search(nocolor):
        return fail("NO_COLOR render still contains SGR")
    if SGR_RE.search(stripped):
        return fail("independent SGR strip left CSI behind")
    if coloured == nocolor:
        return fail("coloured and NO_COLOR renders are identical")
    if stripped != nocolor:
        return fail("stripped coloured render != NO_COLOR render")
    if not breach_visible(nocolor):
        return fail("threshold breach not visible in NO_COLOR")
    if not breach_visible(stripped):
        return fail("threshold breach not visible after SGR strip")

    # Colour-only mutant: the same metrics, colour as the only signal.
    mutant_color = H.render_hud(snapshot, color=True, pairing="color-only")
    mutant_plain = H.render_hud(snapshot, color=False, pairing="color-only")
    mutant_stripped = strip_sgr(mutant_color)
    if "\x1b[" not in mutant_color:
        return fail("color-only mutant had no CSI")
    if mutant_stripped != mutant_plain:
        return fail("color-only strip != color-only NO_COLOR")
    if breach_visible(mutant_stripped) or breach_visible(mutant_plain):
        return fail("color-only mutant still carries FAIL/BREACH after strip")
    if "FAIL" in mutant_stripped or "BREACH" in mutant_stripped:
        return fail("color-only mutant leaked a non-colour fail token")

    env_nocolor = H.color_from_env({"NO_COLOR": "1", "FORCE_COLOR": "1"})
    env_force = H.color_from_env({"FORCE_COLOR": "1"})
    env_plain = H.color_from_env({})
    if env_nocolor:
        return fail("NO_COLOR did not win over FORCE_COLOR")
    if not env_force:
        return fail("FORCE_COLOR did not enable colour")
    if env_plain:
        return fail("empty env must not imply colour (non-tty default)")

    sgr_count = len(SGR_RE.findall(coloured))
    payload = {
        "probe": "probe1-nocolor-vs-stripped-sgr",
        "unit_id": "TST-0245",
        "coloured_has_csi": True,
        "nocolor_has_csi": False,
        "stripped_equals_nocolor": stripped == nocolor,
        "breach_visible_nocolor": True,
        "breach_visible_stripped": True,
        "color_only_breach_visible_after_strip": False,
        "sgr_sequences_coloured": sgr_count,
        "nocolor_sha_prefix": __import__("hashlib")
        .sha256(nocolor.encode())
        .hexdigest()[:16],
        "stripped_sha_prefix": __import__("hashlib")
        .sha256(stripped.encode())
        .hexdigest()[:16],
        "no_color_wins_over_force_color": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"stripped_equals_nocolor=True breach_nocolor=True "
        f"color_only_hidden=True sgr={sgr_count}"
    )
    print("SUCCESS:TST-0245-probe1 NO_COLOR equals stripped SGR; breach remains")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
