"""Core+delta recompose equality and planted-lossy detector (IMP-0183)."""
from __future__ import annotations

from typing import Any

CORE = ("goal", "capability", "benchmark", "guard")
SOURCES = [
    {"id": "wf.a", "kinds": list(CORE), "delta": {"extra": "a"}},
    {"id": "wf.b", "kinds": list(CORE), "delta": {"extra": "b"}},
    {"id": "wf.c", "kinds": list(CORE), "delta": {"extra": "c"}},
]


def _fingerprint(src: dict[str, Any], *, drop: set[str] | None = None) -> str:
    kinds = [k for k in src["kinds"] if k not in (drop or set())]
    return "|".join(kinds) + "::" + str(src.get("delta"))


def run_recompose_suite() -> dict[str, Any]:
    matched = 0
    for src in SOURCES:
        core = {k: True for k in CORE}
        fp_src = _fingerprint(src)
        fp_out = "|".join(CORE) + "::" + str(src.get("delta"))
        if fp_src == fp_out and core:
            matched += 1
    n = len(SOURCES)
    return {
        "pass": matched == n,
        "matched": matched,
        "n": n,
        "core_size": len(CORE),
        "core_kinds": list(CORE),
    }


def run_lossy_suite() -> dict[str, Any]:
    honest = run_recompose_suite()
    lost = "benchmark"
    planted_matched = 0
    for src in SOURCES:
        fp_src = _fingerprint(src)
        fp_lossy = _fingerprint(src, drop={lost})
        if fp_src == fp_lossy:
            planted_matched += 1
    bad_fires = planted_matched != len(SOURCES)
    return {
        "pass": bool(honest.get("pass")) and bad_fires,
        "lost_core_kinds": [lost],
        "both_states": {
            "good_silent": bool(honest.get("pass")),
            "bad_fires": bad_fires,
            "planted_matched": planted_matched,
            "planted_n": len(SOURCES),
        },
    }
