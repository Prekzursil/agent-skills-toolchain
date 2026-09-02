#!/usr/bin/env python3
"""Probe 2: third-agent survival is author-blind; volume is not a score input."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import experiment as E  # noqa: E402
import judge as J  # noqa: E402
from util import OUT_REL, REPO as ROOT, SENTINEL  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0154-probe2 {msg}")
    return 1


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    judge_imports = _imports_of(HERE / "judge.py")
    print(f"judge_imports={sorted(judge_imports)}")
    if "refute" in judge_imports or "find" in judge_imports:
        return fail("judge.py imports refute or find")
    if "corpus" in judge_imports:
        return fail("judge.py imports corpus gold labels")

    live = E.run_experiment()
    if live["author_swap_invariant"] is not True:
        return fail("author-swap changed survival")
    if doc.get("author_swap_invariant") is not True:
        return fail("artifact author_swap_invariant drifted")

    cmp_live = live["comparison"]
    cmp_art = doc.get("comparison") or {}
    print(
        f"precision honest={cmp_live['honest_precision']} "
        f"noisy={cmp_live['noisy_precision']} "
        f"finder={cmp_live['finder_precision']}"
    )
    print(
        f"surviving_yield_per_hour honest={cmp_live['honest_yield_per_hour']} "
        f"finder={cmp_live['finder_yield_surviving_per_hour']}"
    )
    if not cmp_live["honest_beats_noisy_on_precision"]:
        return fail("honest precision did not beat noisy")
    if not cmp_live["honest_beats_finder_on_precision"]:
        return fail("honest precision did not beat finder")
    if float(cmp_art.get("honest_precision", -1)) != float(cmp_live["honest_precision"]):
        return fail("artifact honest precision drifted")
    if float(cmp_live["finder_precision"]) != 0.0:
        return fail("finder volume findings survived the closed judge")

    schema_rel = "command-center/schema/work-unit.schema.json"
    raw = (ROOT / schema_rel).read_bytes()
    fake = {
        "kind": "style-nit",
        "rel": schema_rel,
        "detail": "could be shorter",
        "author": "planted-noise",
    }
    v_fake = J.survive(raw, fake)
    print(f"planted_nit survive={v_fake['survive']} reason={v_fake['reason']}")
    if v_fake["survive"]:
        return fail("style-nit survived on known-correct schema")

    fake_exists = {
        "kind": "claimed_exists_missing",
        "claimed_path": schema_rel,
        "author": "planted-false-defect",
    }
    v_false = J.survive(raw, fake_exists)
    print(
        f"planted_false_exists survive={v_false['survive']} "
        f"reason={v_false['reason']}"
    )
    if v_false["survive"]:
        return fail("false exists-missing survived on a present schema")

    if live["ranking_honest"][0] != "honest_refuter":
        return fail("honest ranking winner drifted")
    if live["ranking_volume"][0] == "honest_refuter":
        return fail("volume ranking still picked honest_refuter")

    print("third agent is author-blind and does not import the refuter")
    print("volume findings do not survive; honest precision beats noisy and finder")
    print("SUCCESS:RES-0154-probe2 third agent and volume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
