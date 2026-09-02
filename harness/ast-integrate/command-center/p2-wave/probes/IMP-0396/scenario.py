#!/usr/bin/env python3
"""Load IMP-0396 fixtures and the production no-fit router."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
NOFIT_PATH = REPO / "tools" / "router" / "nofit.py"
INDEX_PATH = HERE / "fixtures" / "capability-index.json"
NOFIT_CORPUS = HERE / "fixtures" / "nofit-corpus.json"
FIT_CORPUS = HERE / "fixtures" / "fit-corpus.json"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0396.json"
SENTINEL = "SENTINEL:IMP-0396:NO-FIT-TERMINAL"


def load_nofit():
    spec = importlib.util.spec_from_file_location("imp0396_nofit", NOFIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {NOFIT_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def capabilities(mod=None) -> list[dict[str, Any]]:
    n = mod or load_nofit()
    return n.load_index(INDEX_PATH)


def nofit_queries(mod=None) -> list[str]:
    n = mod or load_nofit()
    return n.load_queries(NOFIT_CORPUS)


def fit_queries(mod=None) -> list[str]:
    n = mod or load_nofit()
    return n.load_queries(FIT_CORPUS)
