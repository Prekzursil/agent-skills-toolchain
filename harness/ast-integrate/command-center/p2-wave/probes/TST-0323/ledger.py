#!/usr/bin/env python3
"""Population of benchmark verdicts.

Live command-center/bench/results is absent on this worktree. The synthetic
ledger is a frozen stand-in whose gold labels follow protocol.json. It is
not a convenience sample of live runs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_RESULTS = REPO / "command-center" / "bench" / "results"
LIVE_CASES = REPO / "command-center" / "bench" / "cases"
FIXTURE_REL = "command-center/p2-wave/probes/TST-0323/fixtures/ledger.json"
FIXTURE = REPO / FIXTURE_REL

sys.path.insert(0, str(HERE))
import prereg as P  # noqa: E402

# (oracle_type, platform_verdict, n, n_errors)
# Errors sit on the lowest case_id ordinals so the recipe is inspectable.
# judged:fail is majority-wrong: the bias an unstratified sample hides.
RECIPE = (
    ("deterministic", "fail", 20, 1),
    ("deterministic", "pass", 20, 0),
    ("judged", "fail", 20, 12),
    ("judged", "pass", 20, 1),
)


def _tag(oracle_type: str, verdict: str) -> tuple[str, str]:
    o = "DET" if oracle_type == "deterministic" else "JUD"
    return o, verdict.upper()


def synthetic_population() -> list[dict]:
    rows: list[dict] = []
    for oracle, verdict, n, n_err in RECIPE:
        otag, vtag = _tag(oracle, verdict)
        for i in range(1, n + 1):
            error = i <= n_err
            gold = ("fail" if verdict == "pass" else "pass") if error else verdict
            rows.append(
                {
                    "adjudication": {
                        "blind": True,
                        "protocol": "command-center/p2-wave/probes/TST-0323/protocol.json",
                        "synthetic_stand_in": True,
                    },
                    "blocked": False,
                    "case_id": f"SYN-{otag}-{vtag}-{i:04d}",
                    "human_gold": gold,
                    "oracle_type": oracle,
                    "platform_verdict": verdict,
                    "run_id": "run-synthetic-tst-0323",
                }
            )
    return rows


def live_present() -> dict:
    results_dir = LIVE_RESULTS.is_dir()
    cases_dir = LIVE_CASES.is_dir()
    n_results = 0
    if results_dir:
        n_results = sum(1 for p in LIVE_RESULTS.rglob("*") if p.is_file())
    return {
        "cases_dir": cases_dir,
        "results_dir": results_dir,
        "results_file_count": n_results,
        "usable": results_dir and n_results > 0,
    }


def freeze_fixture(rows: list[dict] | None = None) -> dict:
    pop = rows if rows is not None else synthetic_population()
    doc = {
        "kind": "synthetic-stand-in",
        "n": len(pop),
        "reason": (
            "command-center/bench/results/ is absent; gold labels follow "
            "protocol.json on a frozen 2x2 population, not a live human session"
        ),
        "recipe": [
            {
                "n": n,
                "n_errors": n_err,
                "oracle_type": o,
                "platform_verdict": v,
            }
            for o, v, n, n_err in RECIPE
        ],
        "rows": pop,
        "run_id": "run-synthetic-tst-0323",
        "unit_id": "TST-0323",
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = P.sha256_file(FIXTURE)
    return {"path": FIXTURE_REL, "sha256": digest, "bytes": size, "n": len(pop)}


def load_population() -> dict:
    live = live_present()
    rows = synthetic_population()
    return {
        "live": live,
        "rows": rows,
        "source": "synthetic-fixture",
        "source_path": FIXTURE_REL,
        "synthetic": True,
    }
