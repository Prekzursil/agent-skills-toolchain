"""Fixture: judge is bound via importlib.import_module(string), not ImportFrom.

Not a production fan-in site. Used only to prove string-name imports are
resolved to the library object instead of assumed.
"""
from __future__ import annotations

import importlib
from typing import Any, Mapping

_mod = importlib.import_module("completion.reducer")
judge = getattr(_mod, "judge")
observation_from_mapping = getattr(_mod, "observation_from_mapping")

SITE_ID = "dynamic_fixture"


def check_unit(payload: Mapping[str, Any]) -> dict[str, Any]:
    obs = observation_from_mapping(SITE_ID, payload)
    return judge(obs).as_dict()
