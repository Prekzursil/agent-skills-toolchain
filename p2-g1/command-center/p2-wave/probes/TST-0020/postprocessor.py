"""Self-contradicting-output detector for TST-0020.

Asserts declared invariants over a single run's own output BEFORE any number
is published. A contradiction fails the RUN as detector-failure; on failure
nothing numeric is published.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INVARIANTS = json.loads((HERE / "invariants.json").read_text(encoding="utf-8"))["invariants"]


def naive_counts(stdout: str, universe: int) -> dict:
    """The NAIVE parse the pathology attacks.

    The naive reporter compares the whole stdout blob to the bare string "0".
    A doubled zero blob is NOT that string, so it concludes every PR was hit;
    any bare 0 line is also read as "empty intersection". Both claims come
    from ONE run - that contradiction is the defect.
    """
    lines = [ln.strip() for ln in stdout.strip().splitlines()]
    numbers = []
    for ln in lines:
        try:
            numbers.append(int(ln))
        except ValueError:
            pass
    blob_is_plain_zero = stdout.strip() == "0"
    hit = 0 if blob_is_plain_zero else universe
    miss = universe - hit
    intersection = 0 if (0 in numbers or blob_is_plain_zero) else universe
    claims = []
    if hit == universe and hit > 0 and not blob_is_plain_zero:
        claims.append("all_hit")
    if intersection == 0 and lines:
        claims.append("empty_intersection")
    return {
        "hit": hit,
        "miss": miss,
        "intersection": intersection,
        "universe": universe,
        "claims": claims,
        "raw_lines": lines,
    }


def postprocess(counts: dict) -> dict:
    violated = []
    for inv in INVARIANTS:
        kind = inv["kind"]
        if kind == "sum":
            if counts["hit"] + counts["miss"] != counts["universe"]:
                violated.append(inv["id"])
        elif kind == "subset":
            if counts[inv["subset"]] > counts[inv["superset"]]:
                violated.append(inv["id"])
        elif kind == "mutex-claims":
            present = [c for c in inv["claims"] if c in counts.get("claims", [])]
            if len(present) == len(inv["claims"]):
                violated.append(inv["id"])
    if violated:
        return {
            "ok": False,
            "classification": "detector-failure",
            "violated_invariants": violated,
            "message": (
                "DETECTOR-FAILURE: violated invariant " + violated[0]
                + ": the run's own output contradicts itself ("
                + ",".join(counts["raw_lines"]) + "); no number is published."
            ),
            "published_numbers": None,
        }
    return {
        "ok": True,
        "classification": None,
        "violated_invariants": [],
        "message": None,
        "published_numbers": {k: counts[k] for k in ("hit", "miss", "intersection", "universe")},
    }
