#!/usr/bin/env python3
"""Probe 2: census verdicts come from shared_judge.evaluate, not a local copy."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import extract as X  # noqa: E402
import shared_judge as SJ  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0021.completion-census.json"
EMITTERS = ["emit_census.py", "census.py", "extract.py"]


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0021-probe2 {msg}")
    return 1


def banned_defs(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and (
            node.name in {"evaluate", "evaluate_spec"}
            or node.name.startswith("_c")
            and len(node.name) <= 4
            and node.name[2:].isdigit()
        ):
            bad.append(node.name)
    return bad


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = X.census_body(doc)
    red = body.get("reducer") or doc.get("reducer") or {}
    if red.get("imported_not_inlined") is not True:
        return fail("reducer.imported_not_inlined is not true")
    if "shared_judge" not in str(red.get("module") or ""):
        return fail("reducer.module is not shared_judge")

    for name in EMITTERS:
        bad = banned_defs(HERE / name)
        if bad:
            return fail(f"{name} locally defines predicate helpers {bad}")
        src = (HERE / name).read_text(encoding="utf-8")
        if name in {"emit_census.py", "census.py"} and "shared_judge" not in src:
            return fail(f"{name} does not import/mention shared_judge")

    census_src = (HERE / "census.py").read_text(encoding="utf-8")
    if "SJ.evaluate" not in census_src and "shared_judge.evaluate" not in census_src:
        return fail("census.py does not call shared_judge.evaluate")

    claims, _ = X.collect(REPO)
    planted = next((c for c in claims if c.get("subject") == "SYN-0021-PLANTED"), None)
    if planted is None:
        return fail("planted claim not extracted")
    catalog = C.load_catalog(REPO)
    live = C.join_claim(planted, catalog, REPO)
    if live["backed"] or live["predicate"]["failing_condition_id"] != 2:
        return fail(f"unpatched join {live['predicate']}")

    orig = SJ.evaluate

    def always_pass(receipt, repo=None):
        return {
            "verdict": "PASS",
            "ok": True,
            "failing_condition_id": None,
            "reason": "patched always PASS",
            "conditions": [],
            "source": "probe2-monkeypatch",
        }

    SJ.evaluate = always_pass
    try:
        patched = C.join_claim(planted, catalog, REPO)
    finally:
        SJ.evaluate = orig
    if patched["backed"] is not True or patched["downgrade"] != "none":
        return fail("monkeypatch of shared_judge.evaluate did not change census join")
    if patched["predicate"].get("source") != "probe2-monkeypatch":
        return fail("join did not observe patched evaluate source")

    restored = C.join_claim(planted, catalog, REPO)
    if restored["backed"] or restored["predicate"]["failing_condition_id"] != 2:
        return fail("evaluate was not restored after monkeypatch")

    print(
        "import_surface=shared_judge.evaluate "
        "emitters_have_no_local_cN=true "
        "monkeypatch_changes_join=true "
        f"planted_source={live['predicate'].get('source')}"
    )
    print("SUCCESS:SYN-0021-probe2 verdicts come from the shared reducer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
