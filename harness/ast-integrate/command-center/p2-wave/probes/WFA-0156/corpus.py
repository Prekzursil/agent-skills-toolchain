#!/usr/bin/env python3
"""Load 108 blueprint stop fields: live library if present, else stand-ins.

09-WORKFLOW-BLUEPRINT-LIBRARY.json is contracted at
harness-restore-20260806. CC-0019 recorded it absent on this Linux
worktree (present=false, bytes=0). Missing live rows are not forged.
Reconstructed stand-ins use the catalog field name `stop` and are labelled.
One in-tree workflow (wf.catalog-class.discovery-only) is grounded.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import algebra as A

LIBRARY_NAME = "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
EXPECTED_COUNT = 108
GROUND_REL = (
    "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/"
    "hatch/workflows/wf.catalog-class.discovery-only.json"
)
FAMILIES = [f"D{i:02d}" for i in range(1, 21)]

SPEC_EXPRS = [
    "ALL(unique_ideas>=100, completeness_score>=0.90)",
    "ANY(halt_requested==true, rounds>=8)",
    "NOT(stalled==true)",
    "WEIGHTED(quality:0.6, coverage:0.4)>=0.80",
    "unique_ideas>=50",
    "ALL(rounds>=4, completeness_score>=0.70)",
]
REJECT_EXPRS = [
    "ALL(done==true, NOT(done==true))",
    "ALL(unique_ideas>=100, unique_ideas<=10)",
    "WEIGHTED(quality:0.2, coverage:0.2)>=0.90",
    "ANY()",
    "ALL(rounds>=10, rounds<10)",
    "ALL(error_present==true, error_present==false)",
    "WEIGHTED(quality:0.3)>=0.80",
    "ALL(quality>=1, quality<=0)",
]
PROSE_TEXTS = [
    "stop when the owner is satisfied with the writeup",
    "halt after sufficient deliberation",
    "end the run once reviewers feel done",
    "pause if the council is tired",
    "ship when quality is good enough",
    "stop on stakeholder happiness",
    "finish after a reasonable number of tries",
    "terminate when consensus emerges organically",
    "cut off if the vibe is wrong",
    "keep going until it looks right",
    "stop at owner discretion",
    "halt after the usual amount of work",
    "done when the narrative is complete",
    "exit after enough exploration",
    "cease when risk feels low",
    "conclude upon collective satisfaction",
    "stop if nothing interesting remains",
    "finish when the board would approve",
    "end after the meeting energy drops",
    "halt once stakeholders stop objecting",
]
EVALUABLE_EXPRS = [
    "unique_ideas>=100",
    "completeness_score>=0.90",
    "stages_completed>=2",
    "ALL(unique_ideas>=80, completeness_score>=0.75)",
    "ANY(halt_requested==true, rounds>=12)",
    "WEIGHTED(quality:0.5, coverage:0.5)>=0.70",
    "quality>=0.80",
    "coverage>=0.85",
    "ALL(rounds>=3, unique_ideas>=40)",
    "ANY(error_present==true, stalled==true)",
    "ALL(stages_completed>=2, completeness_score>=0.50)",
    "WEIGHTED(quality:0.7, coverage:0.3)>=0.60",
    "rounds>=8",
    "unique_ideas>=200",
    "ALL(quality>=0.5, coverage>=0.5)",
]
DEGENERATE_EXPRS = [
    "rounds>=0",
    "ALL(stages_completed>=0, rounds>=0)",
]


def repo_root(here: Path | None = None) -> Path:
    if here is None:
        here = Path(__file__).resolve().parent
    return here.parents[3]


def search_roots(repo: Path) -> list[Path]:
    home = Path.home()
    return [
        home / ".claude" / "harness-restore-20260806",
        Path("/root/.claude/harness-restore-20260806"),
        repo / "harness-restore-20260806",
        repo / "command-center" / "harness-restore-20260806",
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        Path("C:/Users/Prekzursil/.claude/harness-restore-20260806"),
        repo,
        repo / "command-center",
        repo / "command-center" / "foundry",
        repo / "command-center" / "wfa",
    ]


def find_library(repo: Path) -> Path | None:
    for root in search_roots(repo):
        cand = root / LIBRARY_NAME
        try:
            if cand.is_file() and cand.stat().st_size > 0:
                return cand
        except OSError:
            continue
    return None


def searched_paths(repo: Path) -> list[str]:
    return [str(root / LIBRARY_NAME) for root in search_roots(repo)]


def extract_blueprints(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("blueprints", "records", "items", "workflows"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def stop_of(rec: dict[str, Any]) -> Any:
    for key in ("stop", "stopping", "stop_rule", "stopping_rule"):
        if key in rec and rec[key] not in (None, "", []):
            return rec[key]
    return None


def rec_id(rec: dict[str, Any], index: int) -> str:
    for key in ("id", "blueprint_id", "name", "slug"):
        val = rec.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return f"library-blueprint-{index:03d}"


def _row(
    *,
    bid: str,
    family: str,
    size_class: str,
    provenance: str,
    stop: Any,
    source: str | None,
    discovery_only: bool = True,
) -> dict[str, Any]:
    compiled = A.compile_stop(stop)
    return {
        "id": bid,
        "family": family,
        "size_class": size_class,
        "discovery_only": discovery_only,
        "provenance": provenance,
        "source": source,
        "stop": stop,
        "raw_stop_text": compiled["raw_stop_text"],
        "compile_result": compiled["compile_result"],
        "ast": compiled["ast"],
        "degenerate_immediate_stop": compiled["degenerate_immediate_stop"],
        "reject_reason": compiled["reject_reason"],
        "eval_t0": compiled["eval_t0"],
        "library_stop_forged": False,
    }


def grounded_row(repo: Path) -> dict[str, Any]:
    path = repo / GROUND_REL
    stop: Any = None
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
        stop = stop_of(doc) if isinstance(doc, dict) else None
    return _row(
        bid="wf.catalog-class.discovery-only",
        family="D01",
        size_class="BUILD-SMALL",
        provenance="in-tree-workflow",
        stop=stop,
        source=GROUND_REL,
        discovery_only=True,
    )


def reconstructed_stop(index: int) -> Any:
    """index 1..107 after grounded row 0. Not claimed as library text."""
    if 1 <= index <= 6:
        return SPEC_EXPRS[index - 1]
    if 7 <= index <= 14:
        return REJECT_EXPRS[index - 7]
    if 15 <= index <= 34:
        return PROSE_TEXTS[index - 15]
    if 35 <= index <= 54:
        return None
    if 55 <= index <= 56:
        return DEGENERATE_EXPRS[index - 55]
    return EVALUABLE_EXPRS[(index - 57) % len(EVALUABLE_EXPRS)]


def reconstructed_blueprints(repo: Path) -> list[dict[str, Any]]:
    rows = [grounded_row(repo)]
    for i in range(1, EXPECTED_COUNT):
        family = FAMILIES[i % len(FAMILIES)]
        size_class = "BUILD-SMALL" if i < 52 else "OTHER"
        stop = reconstructed_stop(i)
        rows.append(
            _row(
                bid=f"wf.recon.{family}.{i:03d}",
                family=family,
                size_class=size_class,
                provenance="reconstructed-stand-in",
                stop=stop,
                source=None,
                discovery_only=True,
            )
        )
    return rows


def rows_from_library(doc: Any, path: Path, repo: Path) -> list[dict[str, Any]]:
    bps = extract_blueprints(doc)
    rows: list[dict[str, Any]] = []
    for i, rec in enumerate(bps):
        family = str(rec.get("family") or FAMILIES[i % len(FAMILIES)])
        size_class = str(rec.get("size_class") or rec.get("size") or "LIBRARY")
        rows.append(
            _row(
                bid=rec_id(rec, i),
                family=family,
                size_class=size_class,
                provenance="library",
                stop=stop_of(rec),
                source=str(path),
                discovery_only=bool(rec.get("discovery_only", rec.get("discovery_only", True))),
            )
        )
    if len(rows) >= EXPECTED_COUNT:
        return rows[:EXPECTED_COUNT]
    # Live library shorter than 108: keep live rows, fill remainder as stand-ins.
    filled = reconstructed_blueprints(repo)
    out = rows + filled[len(rows) :]
    for extra in out[len(rows) :]:
        extra["provenance"] = "reconstructed-stand-in-padding"
    return out[:EXPECTED_COUNT]


def load_corpus(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or repo_root()
    found = find_library(repo)
    searched = searched_paths(repo)
    if found is not None:
        doc = json.loads(found.read_text(encoding="utf-8"))
        rows = rows_from_library(doc, found, repo)
        return {
            "library_present": True,
            "library_path": str(found),
            "library_bytes": found.stat().st_size,
            "provenance": "live-library",
            "searched": searched,
            "blueprints": rows,
            "count": len(rows),
        }
    rows = reconstructed_blueprints(repo)
    return {
        "library_present": False,
        "library_path": None,
        "library_bytes": 0,
        "provenance": "reconstructed-stand-in",
        "searched": searched,
        "blueprints": rows,
        "count": len(rows),
        "cc0019_library": {
            "name": LIBRARY_NAME,
            "present": False,
            "bytes": 0,
            "note": (
                "CC-0019 recorded 09-WORKFLOW-BLUEPRINT-LIBRARY.json "
                "present=false bytes=0 on this worktree. Original stop "
                "texts are not forged."
            ),
        },
    }


def census(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "blueprints": len(rows),
        "EVALUABLE": 0,
        "PROSE-ONLY": 0,
        "ABSENT": 0,
        "COMPILE-REJECT": 0,
        "degenerate_immediate_stop": 0,
        "BUILD-SMALL": 0,
    }
    for row in rows:
        key = str(row.get("compile_result") or "")
        if key in counts:
            counts[key] += 1
        if row.get("degenerate_immediate_stop"):
            counts["degenerate_immediate_stop"] += 1
        if row.get("size_class") == "BUILD-SMALL":
            counts["BUILD-SMALL"] += 1
    return counts
