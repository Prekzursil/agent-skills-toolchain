"""ToolUniverse Wearables — Phase 0 pure-logic framework.

Snap-on/off modular "wearables" over a pure-function pipeline:
    resolve(R) -> fetch(G) -> normalize(I) -> verify(J) -> capture(F/L)

Phase 0 ships only the framework spine: the frozen typed Datum, the single
injectable transport_port I/O seam, and the fail-CLOSED egress chokepoint.
No module behaviour (R/I/G/E/J/F/L/#1/#2/#3/#4/K) and no live hook wiring yet.
"""

__all__ = [
    "datum",
    "transport",
    "security",
    "resolve",
    "fetch",
    "normalize",
    "route_prompt",
    "render_table",
    "pipeline",
    "verify",
    "provenance",
    "capture",
    "cron",
]
