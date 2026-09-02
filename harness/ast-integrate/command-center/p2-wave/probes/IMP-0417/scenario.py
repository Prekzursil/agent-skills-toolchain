"""Shared constants and planted-predicate helpers for IMP-0417 probes."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from completion.sites import SITE_FILES, SITE_IDS  # noqa: E402

SENTINEL = "SENTINEL:IMP-0417:REDUCER-SINGLE-SOURCE"
BEFORE_DIR = HERE / "fixtures" / "before"
SITES_DIR = TOOLS / "completion" / "sites"

PLANTED_SOURCE = '''\
"""Planted local predicate — detector-control copy, never a production site."""
from __future__ import annotations

from typing import Any, Mapping

from completion.reducer import judge, observation_from_mapping

SITE_ID = "local_runner"


def check_unit(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("exit_code") == 0:
        return {"verdict": "COMPLETE", "site": SITE_ID, "planted": True}
    obs = observation_from_mapping(
        SITE_ID, payload, exit_code="exit_code", artifact_path="output_path"
    )
    return judge(obs).as_dict()
'''


def before_files() -> list[Path]:
    return sorted(BEFORE_DIR.glob("*.py"))
