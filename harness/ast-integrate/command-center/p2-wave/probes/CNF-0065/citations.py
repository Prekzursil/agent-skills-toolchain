"""Inventory of cited external benchmark numbers on this worktree."""
from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLANTED = HERE / "fixtures" / "planted-citations.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
CNF0027 = REPO / "command-center" / "confirmation" / "CNF-0027-baseline-variance.json"
RESEARCH = REPO / "command-center" / "research"
CLAIM_REG = REPO / "command-center" / "CLAIM-REGISTRY.json"
BASELINE = REPO / "command-center" / "BASELINE-SNAPSHOT.json"


def load_planted() -> dict:
    return json.loads(PLANTED.read_text(encoding="utf-8"))


def verify_planted_in_source(claim: dict) -> None:
    src = REPO / claim["source_path"]
    if not src.is_file():
        raise FileNotFoundError(claim["source_path"])
    text = src.read_text(encoding="utf-8")
    token = str(claim["cited_value"])
    if token not in text and token.lower() not in text.lower():
        raise AssertionError(f"cited token {token!r} not in {claim['source_path']}")


def live_corpus_claims() -> list[dict]:
    catalog_ok = CATALOG.is_file()
    return [
        {
            "id": "CITE-RES-0028-AIDER-TRADEOFF",
            "origin": "live-corpus",
            "source": {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "locator": "RES-0028 inputs 'Aider benchmark writeups' / measured token-accuracy tradeoff",
            },
            "cited_value": None,
            "cited_unit": "unknown-effect-size",
            "metric": "aider-repo-map-accuracy-delta",
            "disclosed_conditions": [],
            "undisclosed_conditions_required": [],
            "catalog_present": catalog_ok,
            "extract_present": (RESEARCH / "RES-0028.json").is_file(),
            "expected_verdict": "NOT-REPRODUCIBLE",
            "missing_prerequisite": (
                "command-center/research/RES-0028.json with the cited effect size "
                "and baseline; Aider eval harness; pinned model routing; the case "
                "set named by the writeup"
            ),
        },
        {
            "id": "CITE-CNF-0027-NOISE-FLOOR",
            "origin": "live-corpus",
            "source": {
                "path": "command-center/confirmation/CNF-0027-baseline-variance.json",
                "locator": "CNF-0065 input: harness noise floor from CNF-0027",
            },
            "cited_value": None,
            "cited_unit": "noise-floor",
            "metric": "cnf0027-noise-floor",
            "disclosed_conditions": [],
            "undisclosed_conditions_required": [],
            "extract_present": CNF0027.is_file(),
            "expected_verdict": "NOT-REPRODUCIBLE",
            "missing_prerequisite": (
                "command-center/confirmation/CNF-0027-baseline-variance.json "
                "(absent on this worktree); Phase-0 BASELINE-SNAPSHOT.json also absent"
            ),
        },
    ]


def frame() -> list[dict]:
    planted_doc = load_planted()
    rows = []
    for claim in planted_doc["claims"]:
        verify_planted_in_source(claim)
        rows.append(
            {
                "id": claim["id"],
                "origin": claim["origin"],
                "source": {
                    "path": claim["source_path"],
                    "locator": claim["locator"],
                },
                "cited_value": claim["cited_value"],
                "cited_unit": claim["cited_unit"],
                "metric": claim["metric"],
                "disclosed_conditions": list(claim.get("disclosed_conditions") or []),
                "undisclosed_conditions_required": list(
                    claim.get("undisclosed_conditions_required") or []
                ),
                "expected_verdict": claim["expected_verdict"],
                "missing_prerequisite": claim.get("missing_prerequisite"),
            }
        )
    rows.extend(live_corpus_claims())
    rows.sort(key=lambda r: r["id"])
    return rows


def sample_ids(ids: list[str], seed: int, k: int) -> list[str]:
    pool = list(ids)
    if k > len(pool):
        raise ValueError("k > frame")
    rng = random.Random(seed)
    return rng.sample(pool, k)


def corpus_absences() -> dict:
    return {
        "research_dir": RESEARCH.is_dir(),
        "claim_registry": CLAIM_REG.is_file(),
        "baseline_snapshot": BASELINE.is_file(),
        "cnf0027": CNF0027.is_file(),
        "res0028_extract": (RESEARCH / "RES-0028.json").is_file(),
    }
