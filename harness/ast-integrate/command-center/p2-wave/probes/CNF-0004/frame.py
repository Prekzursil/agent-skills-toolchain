#!/usr/bin/env python3
"""Sampling frame for CNF-0004.

Uses command-center/confirmation/CNF-0003-sampling-frame.json when present.
Otherwise derives strata from catalog id prefixes with a pre-registered seed
and the power-n0 sample size from escalate.DETECT_N0. That derivation is
labelled as such; it is not a claim that CNF-0003 delivered.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from escalate import DETECT_N0, SAMPLE_SEED, finite_sample_n

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
CNF0003_REL = "command-center/confirmation/CNF-0003-sampling-frame.json"


def _rng(class_id: str, seed: int = SAMPLE_SEED) -> random.Random:
    material = f"{seed}:{class_id}".encode("utf-8")
    n = int(hashlib.sha256(material).hexdigest()[:16], 16)
    return random.Random(n)


def load_catalog_ids(repo: Path) -> dict[str, list[str]]:
    catalog = json.loads((repo / CATALOG_REL).read_text(encoding="utf-8"))
    units = catalog.get("work_units") or []
    by: dict[str, list[str]] = {}
    for u in units:
        uid = str((u or {}).get("id") or "")
        if "-" not in uid:
            continue
        pref = uid.split("-", 1)[0]
        by.setdefault(pref, []).append(uid)
    for pref in by:
        by[pref] = sorted(set(by[pref]))
    return by


def derive_prefix_frame(repo: Path) -> dict[str, Any]:
    groups = load_catalog_ids(repo)
    strata = []
    for class_id, population in sorted(groups.items()):
        n = finite_sample_n(len(population), DETECT_N0)
        rng = _rng(class_id)
        sample = sorted(rng.sample(population, n)) if n else []
        strata.append(
            {
                "class_id": class_id,
                "population_n": len(population),
                "sample_n": len(sample),
                "additional_if_fail": len(population) - len(sample),
                "census_already": len(sample) == len(population),
                "population_ids": population,
                "sample_ids": sample,
            }
        )
    return {
        "source": "catalog-prefix-derived",
        "cnf0003_present": False,
        "cnf0003_path": CNF0003_REL,
        "seed": SAMPLE_SEED,
        "detect_n0": DETECT_N0,
        "stratum_count": len(strata),
        "strata": strata,
    }


def load_frame(repo: Path) -> dict[str, Any]:
    path = repo / CNF0003_REL
    if path.is_file() and path.stat().st_size > 0:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict) and (doc.get("strata") or doc.get("frame")):
            return {
                "source": "CNF-0003-sampling-frame.json",
                "cnf0003_present": True,
                "cnf0003_path": CNF0003_REL,
                "raw": doc,
                "strata": doc.get("strata") or doc.get("frame") or [],
            }
    return derive_prefix_frame(repo)
