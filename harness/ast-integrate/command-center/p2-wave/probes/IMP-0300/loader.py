#!/usr/bin/env python3
"""Load IMP-0300 planted fixtures and the unique-ideas counter."""
from __future__ import annotations

import importlib.util
import json
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MODULE_PATH = REPO / "tools" / "council" / "quota" / "unique_ideas.py"
FIXTURE = HERE / "fixtures" / "planted.json"


def load_counter():
    spec = importlib.util.spec_from_file_location("imp0300_unique_ideas", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {MODULE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def planted_members(doc: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    texts: list[str] = []
    class_ids: list[str] = []
    kinds: list[str] = []
    for cls in doc["classes"]:
        for member in cls["members"]:
            texts.append(member["text"])
            class_ids.append(cls["id"])
            kinds.append(cls["kind"])
    return texts, class_ids, kinds


def distinct_pair_indices(n: int) -> list[tuple[int, int]]:
    return list(combinations(range(n), 2))
