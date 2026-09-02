"""Per-source-class staleness policy for RES-0171.

RES-0006 (measured per-class half-life table) is a named dependency.
When that measurement artifact is absent, every class uses the
worst-case default and the policy says so: must-revalidate before cite
(RFC 9111 §4.2 / §5.2.2.2 analogue). Heuristic freshness is refused.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

# Reconstructed from WORK-UNIT-CATALOG citations of
# _USER-PROMPTS.md:10681-10717. That spec file is absent on this
# worktree; this list is catalog-reconstructed, not spec-verbatim.
SOURCE_CLASSES: tuple[str, ...] = (
    "official-docs",
    "source-code",
    "papers",
    "forums",
    "archival",
    "public-tor",
    "issue-tracker",
    "blog-post",
    "video-transcript",
    "niche",
    "multilingual",
    "patents-prior-art",
    "standards-regulatory",
    "marketplace",
    "expert-elicitation",
    "owner-decision-log",
)

# Worst-case for "do not cite a page that has since changed": never skip
# origin revalidation. Time bucket is a constant token so identity stays
# clock-free while still recording that the class is unmeasured.
UNMEASURED_TTL_SECONDS = 0
UNMEASURED_BUCKET = "unmeasured:must-revalidate"
RES0006_REL = "command-center/research/RES-0006.json"


def res0006_present(repo: Path) -> bool:
    return (repo / RES0006_REL).is_file() and (repo / RES0006_REL).stat().st_size > 0


def load_measured_ttls(repo: Path) -> dict[str, int]:
    """Return measured TTL seconds per class.

    Absent or unreadable RES-0006 → empty map (every class unmeasured).
    """
    path = repo / RES0006_REL
    if not path.is_file():
        return {}
    try:
        import json

        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    table = doc.get("per_class_half_life") or doc.get("ttl_seconds") or {}
    out: dict[str, int] = {}
    if isinstance(table, dict):
        for k, v in table.items():
            try:
                n = int(v)
            except (TypeError, ValueError):
                continue
            if n > 0:
                out[str(k)] = n
    return out


def ttl_seconds(
    source_class: str,
    measured: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    if source_class not in SOURCE_CLASSES:
        raise ValueError(f"unknown source_class {source_class!r}")
    table = dict(measured or {})
    if source_class in table and int(table[source_class]) > 0:
        return {
            "source_class": source_class,
            "ttl_seconds": int(table[source_class]),
            "measured": True,
            "mode": "fresh-within-ttl-then-revalidate",
            "uses_worst_case_default": False,
        }
    return {
        "source_class": source_class,
        "ttl_seconds": UNMEASURED_TTL_SECONDS,
        "measured": False,
        "mode": "must-revalidate",
        "uses_worst_case_default": True,
        "reason": (
            "no measured TTL from RES-0006; worst-case default is "
            "must-revalidate before cite (heuristic freshness refused)"
        ),
    }


def time_bucket(
    source_class: str,
    now_unix: int,
    measured: Mapping[str, int] | None = None,
) -> str:
    """Discrete bucket. Unmeasured classes use a constant token, not wall-clock."""
    row = ttl_seconds(source_class, measured)
    ttl = int(row["ttl_seconds"])
    if ttl <= 0:
        return UNMEASURED_BUCKET
    if now_unix < 0:
        raise ValueError("now_unix must be >= 0")
    return f"ttl-{ttl}s:b{now_unix // ttl}"


def policy_table(
    repo: Path,
    measured: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    table = dict(measured) if measured is not None else load_measured_ttls(repo)
    rows = [ttl_seconds(c, table) for c in SOURCE_CLASSES]
    unmeasured = [r["source_class"] for r in rows if r["uses_worst_case_default"]]
    return {
        "res0006_path": RES0006_REL,
        "res0006_present": res0006_present(repo),
        "measured_class_count": len(SOURCE_CLASSES) - len(unmeasured),
        "unmeasured_class_count": len(unmeasured),
        "unmeasured_classes": unmeasured,
        "worst_case_default": {
            "mode": "must-revalidate",
            "ttl_seconds": UNMEASURED_TTL_SECONDS,
            "time_bucket": UNMEASURED_BUCKET,
            "heuristic_freshness": False,
        },
        "classes": rows,
        "source_class_list_provenance": (
            "catalog-reconstructed from WORK-UNIT-CATALOG citations of "
            "_USER-PROMPTS.md:10681-10717; spec file absent on this worktree"
        ),
        "source_classes": list(SOURCE_CLASSES),
    }
