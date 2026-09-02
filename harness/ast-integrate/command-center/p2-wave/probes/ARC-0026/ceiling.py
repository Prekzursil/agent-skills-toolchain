"""Ceiling test: N simulated sessions, process-count curve, superlinear = P1.

Does not spawn a live MCP farm. Eager stdio is modeled as N * K. A planted
quadratic curve proves the detector can fire. Linear eager multiplication is
still FM-PROCESS-MULT; it is not a P1-superlinear finding.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX_MCP = HERE / "fixtures" / "mcp.json"
SESSIONS = (1, 2, 4, 8, 16)


def stdio_servers_from_mcp(doc: dict[str, Any]) -> list[str]:
    servers = doc.get("mcpServers") or {}
    names: list[str] = []
    for name, spec in servers.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("url") or spec.get("serverUrl"):
            continue
        if spec.get("command"):
            names.append(str(name))
    return sorted(names)


def load_k() -> tuple[int, list[str]]:
    doc = json.loads(FIX_MCP.read_text(encoding="utf-8"))
    names = stdio_servers_from_mcp(doc)
    return len(names), names


def is_superlinear(ns: list[int], ps: list[int]) -> bool:
    """True iff p(n)/n is strictly increasing (faster than linear)."""
    if len(ns) != len(ps) or len(ns) < 3:
        raise ValueError("need >=3 matched points")
    ratios: list[float] = []
    for n, p in zip(ns, ps):
        if n <= 0:
            raise ValueError("n must be positive")
        ratios.append(p / n)
    return all(ratios[i + 1] > ratios[i] + 1e-12 for i in range(len(ratios) - 1))


def curve(kind: str, k: int) -> list[int]:
    out: list[int] = []
    for n in SESSIONS:
        if kind == "eager-stdio":
            out.append(n * k)
        elif kind == "lazy-shared":
            out.append(k)
        elif kind == "planted-superlinear":
            # Pairwise extra copies on top of per-session stdio: n*k + n*(n-1).
            out.append(n * k + n * (n - 1))
        else:
            raise ValueError(kind)
    return out


def run_ceiling() -> dict[str, Any]:
    k, names = load_k()
    ns = list(SESSIONS)
    eager = curve("eager-stdio", k)
    lazy = curve("lazy-shared", k)
    plant = curve("planted-superlinear", k)
    eager_sl = is_superlinear(ns, eager)
    lazy_sl = is_superlinear(ns, lazy)
    plant_sl = is_superlinear(ns, plant)
    ok = (not eager_sl) and (not lazy_sl) and plant_sl and k >= 1
    return {
        "pass": ok,
        "kind": "simulated",
        "sessions": ns,
        "stdio_server_ids": names,
        "k_stdio_from_fixture_mcp": k,
        "eager_stdio_curve": eager,
        "lazy_shared_curve": lazy,
        "planted_superlinear_curve": plant,
        "eager_superlinear": eager_sl,
        "lazy_superlinear": lazy_sl,
        "planted_superlinear": plant_sl,
        "p1_on_eager": eager_sl,
        "p1_on_plant": plant_sl,
        "detector_control_plant_fires": plant_sl,
        "detector_control_linear_silent": not eager_sl,
        "note": (
            "Eager per-session stdio is linear (N*K). That is still process "
            "multiplication. Superlinear is a P1 finding and is reserved for "
            "the planted curve so the detector is shown to fire and go silent."
        ),
    }
