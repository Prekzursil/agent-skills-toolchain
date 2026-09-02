#!/usr/bin/env python3
"""Terminal HUD emit for TST-0245: colour is a scarce channel.

Every coded signal is a (glyph, text-token, optional SGR) triple. Colour
never travels alone. NO_COLOR is never-wrap, not wrap-then-strip.

ASCII glyphs only (single-cell width). Palette is capped at four roles
because deuteranopia collapses red/green and a 16-colour terminal is the
floor this estate actually has.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

# Colour is scarce: four roles, four SGR codes. A fifth role is a defect.
MAX_PALETTE = 4
CSI = "\x1b["
RESET = "\x1b[0m"

# Deuteranopia-collapsible pair: fail red (31) and ok green (32).
DEUTERANOPE_CLASS = {
    "31": "grey",
    "32": "grey",
    "33": "yellow",
    "36": "cyan",
}


@dataclass(frozen=True)
class Signal:
    role: str
    glyph: str
    token: str
    sgr: str
    meaning: str

    def body(self, payload: str) -> str:
        return f"{self.glyph} {self.token} {payload}"

    def paint(self, payload: str, *, color: bool) -> str:
        body = self.body(payload)
        if not color:
            return body
        return f"{CSI}{self.sgr}m{body}{RESET}"


PALETTE: dict[str, Signal] = {
    "ok": Signal("ok", "+", "OK", "32", "within threshold"),
    "warn": Signal("warn", "!", "WARN", "33", "near or past a soft threshold"),
    "fail": Signal("fail", "x", "FAIL", "31", "hard threshold breach"),
    "info": Signal("info", "i", "INFO", "36", "status, not a threshold"),
}

if len(PALETTE) > MAX_PALETTE:
    raise RuntimeError("palette cap violated at import")


# Deterministic fixture: one hard breach, one warn, one ok, one info.
FIXTURE_SNAPSHOT: dict[str, Any] = {
    "error_rate": 0.12,
    "error_rate_threshold": 0.05,
    "latency_ms": 80,
    "latency_ms_threshold": 200,
    "disk_free_pct": 8,
    "disk_free_pct_threshold": 10,
    "jobs_open": 3,
}


def color_from_env(env: Mapping[str, str] | None) -> bool:
    """NO_COLOR wins (https://no-color.org/). FORCE_COLOR enables when unset."""
    env = env or {}
    if "NO_COLOR" in env:
        return False
    if env.get("FORCE_COLOR"):
        return True
    return False


def lines_for(snapshot: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Return (role, payload) rows. Payloads never include SGR."""
    err = float(snapshot["error_rate"])
    err_t = float(snapshot["error_rate_threshold"])
    lat = float(snapshot["latency_ms"])
    lat_t = float(snapshot["latency_ms_threshold"])
    disk = float(snapshot["disk_free_pct"])
    disk_t = float(snapshot["disk_free_pct_threshold"])
    jobs = int(snapshot["jobs_open"])

    err_role = "fail" if err > err_t else "ok"
    err_payload = f"error_rate={err} threshold={err_t}"
    if err_role == "fail":
        err_payload += " BREACH"

    lat_role = "ok" if lat <= lat_t else "warn"
    lat_payload = f"latency_ms={lat} threshold={lat_t}"

    disk_role = "ok" if disk >= disk_t else "warn"
    disk_payload = f"disk_free_pct={disk} threshold={disk_t}"
    if disk_role == "warn":
        disk_payload += " LOW"

    info_payload = f"jobs_open={jobs}"
    return [
        (err_role, err_payload),
        (lat_role, lat_payload),
        (disk_role, disk_payload),
        ("info", info_payload),
    ]


def render_hud(
    snapshot: Mapping[str, Any] | None = None,
    *,
    color: bool,
    pairing: str = "glyph-token",
) -> str:
    """Render the HUD.

    pairing:
      glyph-token — production path; every coded cell has glyph + token.
      color-only  — known-broken mutant; colour is the only signal.
    """
    rows = lines_for(snapshot or FIXTURE_SNAPSHOT)
    out: list[str] = []
    for role, payload in rows:
        sig = PALETTE[role]
        if pairing == "color-only":
            # Numbers only — no glyph, no token, no BREACH/LOW word.
            raw = payload.replace(" BREACH", "").replace(" LOW", "")
            if color:
                out.append(f"{CSI}{sig.sgr}m{raw}{RESET}")
            else:
                out.append(raw)
        elif pairing == "glyph-token":
            out.append(sig.paint(payload, color=color))
        else:
            raise ValueError(f"unknown pairing {pairing!r}")
    return "\n".join(out) + "\n"


def palette_census() -> list[dict[str, str]]:
    return [
        {
            "role": s.role,
            "glyph": s.glyph,
            "token": s.token,
            "sgr": s.sgr,
            "meaning": s.meaning,
            "cvd_class": DEUTERANOPE_CLASS.get(s.sgr, s.sgr),
        }
        for s in PALETTE.values()
    ]


def unique_sgr_codes(items: Iterable[Signal] | None = None) -> set[str]:
    src = items if items is not None else PALETTE.values()
    return {s.sgr for s in src}


def mutant_oversize_palette() -> dict[str, Signal]:
    """Regression seed: an uncapped palette. Not used for live emit."""
    extra = {
        f"extra{i}": Signal(f"extra{i}", ".", f"E{i}", str(30 + (i % 8)), "surplus")
        for i in range(MAX_PALETTE + 1, MAX_PALETTE + 5)
    }
    return {**PALETTE, **extra}
