#!/usr/bin/env python3
"""Prove recompute.py never imported the sealed fusion-lane scorer."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FORBIDDEN_IMPORTS = ("import fusion_lane", "from fusion_lane")
FORBIDDEN_TOKENS = ("WFA-0117-FUSION-LANE-CANARY",)


def recompute_source() -> str:
    return (HERE / "recompute.py").read_text(encoding="utf-8")


def is_blind() -> dict:
    text = recompute_source()
    import_hits = [tok for tok in FORBIDDEN_IMPORTS if tok in text]
    token_hits = [tok for tok in FORBIDDEN_TOKENS if tok in text]
    return {
        "ok": not import_hits and not token_hits,
        "import_hits": import_hits,
        "token_hits": token_hits,
        "path": "command-center/p2-wave/probes/WFA-0117/recompute.py",
    }
