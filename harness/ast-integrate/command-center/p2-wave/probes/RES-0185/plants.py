"""Detector-control plants for RES-0185.

Planted conclusions are labelled plant=True and excluded from the program
single-source headline. They must still appear on the map.
"""
from __future__ import annotations

from lineage import locator_from_mapping

PLANT_SINGLE_ID = "RES-0185-PLANT-SINGLE"
PLANT_FOUR_ID = "RES-0185-PLANT-FOUR-CLASS"
PLANT_UNSUPPORTED_ID = "RES-0185-PLANT-UNSUPPORTED"


def _loc(**kwargs) -> dict:
    loc = locator_from_mapping(kwargs)
    if loc is None:
        raise RuntimeError(f"plant locator failed {kwargs!r}")
    return loc


def plants() -> list[dict]:
    return [
        {
            "id": PLANT_SINGLE_ID,
            "unit_id": "RES-0185",
            "kind": "plant",
            "plant": True,
            "text": (
                "Planted single-source conclusion: Celery task_time_limit "
                "defaults to no time limit."
            ),
            "origin_path": "command-center/p2-wave/probes/RES-0185/plants.py",
            "lineage_records": [
                _loc(
                    source_id="plant-celery-task-time-limit",
                    permalink=(
                        "https://docs.celeryq.dev/en/stable/userguide/"
                        "configuration.html"
                    ),
                    source_class="official-docs",
                    sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                )
            ],
        },
        {
            "id": PLANT_FOUR_ID,
            "unit_id": "RES-0185",
            "kind": "plant",
            "plant": True,
            "text": (
                "Planted four-class conclusion: map-over-N barriers appear in "
                "a spec, source, a paper, and an issue tracker."
            ),
            "origin_path": "command-center/p2-wave/probes/RES-0185/plants.py",
            "lineage_records": [
                _loc(
                    source_id="plant-asl-spec",
                    permalink="https://states-language.net/spec.html",
                    source_class="standards",
                    sha256="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                ),
                _loc(
                    source_id="plant-celery-canvas",
                    permalink="https://github.com/celery/celery/blob/main/celery/canvas.py",
                    source_class="source-code",
                    sha256="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
                ),
                _loc(
                    source_id="plant-zheng-arxiv",
                    permalink="https://arxiv.org/abs/2306.05685",
                    arxiv="2306.05685",
                    source_class="papers",
                    sha256="dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
                ),
                _loc(
                    source_id="plant-celery-issue",
                    permalink="https://github.com/celery/celery/issues/1",
                    source_class="issue-trackers",
                    sha256="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                ),
            ],
        },
        {
            "id": PLANT_UNSUPPORTED_ID,
            "unit_id": "RES-0185",
            "kind": "plant",
            "plant": True,
            "text": "Planted conclusion with no recorded lineage.",
            "origin_path": "command-center/p2-wave/probes/RES-0185/plants.py",
            "lineage_records": [],
        },
    ]
