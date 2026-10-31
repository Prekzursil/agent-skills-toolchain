"""HUD emit contract for TST-0245: colour never travels alone.

Every coded cell is a (glyph, token, optional SGR) triple. Colour is capped
by PALETTE_CAP and never the sole carrier of a signal: under NO_COLOR, a
monochrome terminal, or a simulated colour-vision deficiency, each coded
element remains distinguishable by glyph and token.
"""
from __future__ import annotations

import os
import re

SGR_RE = re.compile(r"\x1b\[[0-9;]*m")

PALETTE_CAP = 4

ROLES = {
    "ok": {"glyph": "+", "token": "OK", "sgr": "32", "meaning": "within threshold"},
    "warn": {"glyph": "!", "token": "WARN", "sgr": "33", "meaning": "near or past a soft threshold"},
    "fail": {"glyph": "x", "token": "FAIL", "sgr": "31", "meaning": "hard threshold breach"},
    "info": {"glyph": "i", "token": "INFO", "sgr": "36", "meaning": "status, not a threshold"},
}

# Deuteranopia-style collapse map: red (31) and green (32) collapse to one
# perceived class; yellow (33) and cyan (36) remain their own classes.
CVD_MAP = {"32": "grey", "31": "grey", "33": "yellow", "36": "cyan"}


def strip_sgr(text: str) -> str:
    return SGR_RE.sub("", text)


def no_color_active(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    return bool(env.get("NO_COLOR"))


def emit_cell(role: str, text: str, *, env: dict | None = None) -> str:
    """Render one coded cell; honours NO_COLOR by building without SGR."""
    spec = ROLES[role]
    if no_color_active(env):
        return f"{spec['glyph']} {spec['token']} {text}"
    return f"\x1b[{spec['sgr']}m{spec['glyph']} {spec['token']} {text}\x1b[0m"


def render_status(roles: list[str], texts: list[str], *, env: dict | None = None) -> str:
    return "".join(emit_cell(r, t, env=env) for r, t in zip(roles, texts)) + "\n"


def render_meter(value: float, threshold: float, *, env: dict | None = None) -> str:
    """Meter line; a breach is carried by glyph+token, never colour alone."""
    if value > threshold:
        return emit_cell("fail", f"mem {value:.0f}MB BREACH", env=env)
    if value > threshold * 0.8:
        return emit_cell("warn", f"mem {value:.0f}MB near", env=env)
    return emit_cell("ok", f"mem {value:.0f}MB", env=env)


def token_map() -> list[dict]:
    rows = []
    for role, spec in ROLES.items():
        rows.append(
            {
                "role": role,
                "glyph": spec["glyph"],
                "token": spec["token"],
                "sgr": spec["sgr"],
                "meaning": spec["meaning"],
                "cvd_class": CVD_MAP.get(spec["sgr"], "unknown"),
            }
        )
    return rows


def enumerate_coded_elements() -> list[dict]:
    """Every coded element with its non-colour token (probe2 contract)."""
    elements = []
    for row in token_map():
        elements.append(
            {
                "element": f"role:{row['role']}",
                "glyph": row["glyph"],
                "token": row["token"],
                "sgr": row["sgr"],
            }
        )
    elements.append({"element": "meter-breach", "glyph": "x", "token": "FAIL+BREACH", "sgr": "31"})
    return elements


def colour_only_mutant(env: dict | None = None) -> str:
    """A MUTANT cell: SGR colour with NO glyph and NO token (must be flagged)."""
    return "\x1b[35m" + "mem 100MB" + "\x1b[0m"
