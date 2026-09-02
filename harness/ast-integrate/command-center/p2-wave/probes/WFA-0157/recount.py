"""Two independent recounts of state gloss vs vocabulary on the 108-array.

Signal A: json.loads + exact membership of the ``state`` field in the vocab set.
Signal B: regex over the raw file that matches the key ``"state"`` but not
``"state_v"``, then exact membership of the captured literals.

Disagreement is a detector failure, not a tie.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from corpus import FIXTURE, VOCAB_STATE, load_blueprints, write_fixture

STATE_KEY_RE = re.compile(r'"state"\s*:\s*"((?:\\.|[^"\\])*)"')


def recount_json(records: list[dict[str, Any]]) -> dict[str, Any]:
    vocab = set(VOCAB_STATE)
    states = [str(r.get("state")) for r in records]
    exact = [s for s in states if s in vocab]
    non = [s for s in states if s not in vocab]
    return {
        "method": "json-field-membership",
        "n": len(states),
        "vocab_exact": len(exact),
        "non_literal": len(non),
        "distinct_literals": len(set(states)),
        "distinct_non_literal": len(set(non)),
        "vocab": list(VOCAB_STATE),
    }


def recount_regex(raw: str) -> dict[str, Any]:
    vocab = set(VOCAB_STATE)
    states = [m.group(1) for m in STATE_KEY_RE.finditer(raw)]
    exact = [s for s in states if s in vocab]
    non = [s for s in states if s not in vocab]
    return {
        "method": "raw-regex-state-key",
        "n": len(states),
        "vocab_exact": len(exact),
        "non_literal": len(non),
        "distinct_literals": len(set(states)),
        "distinct_non_literal": len(set(non)),
        "vocab": list(VOCAB_STATE),
        "pattern": STATE_KEY_RE.pattern,
    }


def live_recount(path: Path = FIXTURE) -> dict[str, Any]:
    if not path.is_file():
        write_fixture(path)
    records = load_blueprints(path)
    raw = path.read_text(encoding="utf-8")
    a = recount_json(records)
    b = recount_regex(raw)
    agree = (
        a["n"] == b["n"]
        and a["vocab_exact"] == b["vocab_exact"]
        and a["non_literal"] == b["non_literal"]
        and a["distinct_literals"] == b["distinct_literals"]
    )
    catalog = {"n": 108, "vocab_exact": 74, "non_literal": 34, "distinct_literals": 36}
    matches_catalog = (
        a["n"] == catalog["n"]
        and a["vocab_exact"] == catalog["vocab_exact"]
        and a["non_literal"] == catalog["non_literal"]
        and a["distinct_literals"] == catalog["distinct_literals"]
    )
    return {
        "path": path.as_posix(),
        "signal_a": a,
        "signal_b": b,
        "signals_agree": agree,
        "catalog_claim": catalog,
        "matches_catalog_claim": matches_catalog,
        "state_v_present_on_all": all("state_v" in r and "size_v" in r for r in records),
    }


def assert_catalog(path: Path = FIXTURE) -> dict[str, Any]:
    doc = live_recount(path)
    if not doc["signals_agree"]:
        raise RuntimeError(f"recount methods disagree: {json.dumps(doc, indent=2)}")
    if not doc["matches_catalog_claim"]:
        raise RuntimeError(f"live recount != catalog 34/108: {json.dumps(doc, indent=2)}")
    if not doc["state_v_present_on_all"]:
        raise RuntimeError("a record is missing state_v or size_v")
    return doc
