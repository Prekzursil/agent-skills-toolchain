"""Coverage assertion: every observed job maps to exactly one entry surface.

An unmapped job is a design gap, not a footnote. A dual-mapped job is a
duplicate control plane. An invented job with no observed evidence is a persona.
"""
from __future__ import annotations

from typing import Any

SURFACES = frozenset({"command", "cockpit", "catalog"})


def index_jobs(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("job row missing id")
        if row["id"] in out:
            raise ValueError(f"duplicate job id {row['id']}")
        out[row["id"]] = row
    return out


def coverage(
    observed: list[dict[str, Any]], designed: list[dict[str, Any]]
) -> dict[str, Any]:
    obs = index_jobs(observed)
    des = index_jobs(designed)
    unmapped = sorted(set(obs) - set(des))
    invented = sorted(set(des) - set(obs))
    dual: list[str] = []
    bad_surface: list[str] = []
    for job_id, row in des.items():
        surface = row.get("surface")
        if not isinstance(surface, str) or surface not in SURFACES:
            bad_surface.append(job_id)
        # A second surface field is the dual-map smell this checker exists for.
        extra = row.get("surfaces") or row.get("entry_surfaces")
        if extra:
            dual.append(job_id)
    gaps = unmapped + invented + dual + bad_surface
    return {
        "observed_count": len(obs),
        "designed_count": len(des),
        "unmapped": unmapped,
        "invented_personas": invented,
        "dual_mapped": dual,
        "illegal_surface": bad_surface,
        "ok": not gaps,
    }


def assert_coverage(
    observed: list[dict[str, Any]], designed: list[dict[str, Any]]
) -> dict[str, Any]:
    report = coverage(observed, designed)
    if not report["ok"]:
        raise AssertionError(
            "coverage-gap "
            f"unmapped={report['unmapped']} "
            f"invented={report['invented_personas']} "
            f"dual={report['dual_mapped']} "
            f"illegal={report['illegal_surface']}"
        )
    return report
