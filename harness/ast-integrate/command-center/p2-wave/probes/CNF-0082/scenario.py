"""Source-class fixtures for CNF-0082 rediscovery control.

Declared classes follow IMP-0209 / WFA-0143: local, marketplace, repo, docs,
papers. Plants live as workflow documents on disk. An index.json ghost in each
class is an injection trap the scout must not consult.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SOURCE_CLASSES = ("local", "marketplace", "repo", "docs", "papers")
GOAL = "certify-and-publish-workflow"
GOAL_TOKENS = frozenset({"certify", "publish", "workflow", "marketplace"})
PLANT_SCORE = 95
INFERIOR_SCORE = 25
REBUILD_SCORE = 42
GHOST_SCORE = 99

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0082/probe1_rediscovery.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0082/probe2_ranking.py"
)
OUT_REL = "command-center/confirmation/CNF-0082-scout-rediscovery.json"
SCHEMA_REL = "command-center/schema/detector-control.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0082 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every declared source "
    "class received a plant and has a recorded found-or-blind verdict. Any "
    "other terminal state is FAILED:CNF-0082 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Would the scout rediscover a workflow that already exists, or would it "
    "propose rebuilding it? Plant a known-present, clearly superior workflow "
    "in each searched source class and answer: does the scout find it in "
    "every class, and in which class is it blind? Spec line 11331 names "
    "ignoring an existing superior workflow as a required regression case."
)


def plant_id(cls: str) -> str:
    return f"wf.cnf0082.{cls}.superior"


def plant_rel(cls: str) -> str:
    return (
        "command-center/p2-wave/probes/CNF-0082/fixtures/sources/"
        f"{cls}/wf-cnf0082-{cls}-superior.json"
    )


def class_root(cls: str) -> Path:
    return FIXTURES / "sources" / cls


def _dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def ensure_fixtures() -> Path:
    """Write a deterministic corpus. Safe to call from emit and from probes."""
    for cls in SOURCE_CLASSES:
        root = class_root(cls)
        _dump(
            root / f"wf-cnf0082-{cls}-superior.json",
            {
                "goal": GOAL,
                "goal_tokens": sorted(GOAL_TOKENS),
                "id": plant_id(cls),
                "plant": True,
                "quality_score": PLANT_SCORE,
                "source_class": cls,
                "superior": True,
                "title": f"Certified marketplace publish ({cls} incumbent)",
            },
        )
        _dump(
            root / f"wf-cnf0082-{cls}-inferior.json",
            {
                "goal": GOAL,
                "goal_tokens": sorted(GOAL_TOKENS),
                "id": f"wf.cnf0082.{cls}.inferior",
                "plant": False,
                "quality_score": INFERIOR_SCORE,
                "source_class": cls,
                "superior": False,
                "title": f"Ad-hoc publish script ({cls})",
            },
        )
        _dump(
            root / "index.json",
            {
                "entries": [
                    {
                        "goal_tokens": sorted(GOAL_TOKENS),
                        "id": f"wf.cnf0082.{cls}.ghost",
                        "quality_score": GHOST_SCORE,
                        "title": "Index-injected ghost (must not be found)",
                    }
                ],
                "note": "injected index — scout must not consult this file",
            },
        )
    _dump(
        class_root("local") / "wf-cnf0082-local-nonmatching.json",
        {
            "goal": "unrelated-alpha-beta",
            "goal_tokens": ["unrelated", "alpha", "beta"],
            "id": "wf.cnf0082.local.nonmatching",
            "plant": False,
            "quality_score": 99,
            "source_class": "local",
            "superior": True,
            "title": "Non-matching high-score decoy (invalid plant)",
        },
    )
    return FIXTURES
