"""Score a fixture tree and fingerprint its measure files."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from fixtures import MEASURE_PATHS, SUT_PATH


def materialize(tree: dict[str, str], dest: Path) -> None:
    for rel, content in tree.items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def load_solve(tree_dir: Path):
    spec = importlib.util.spec_from_file_location(
        "adv0088_sut", tree_dir / SUT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load fixture SUT")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.solve


def measure_fingerprint(tree: dict[str, str]) -> str:
    payload = {rel: tree[rel] for rel in MEASURE_PATHS}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def score_tree(tree: dict[str, str], dest: Path) -> dict:
    materialize(tree, dest)
    cases = json.loads((dest / "measure/cases.json").read_text(encoding="utf-8"))
    thr = json.loads((dest / "measure/thresholds.json").read_text(encoding="utf-8"))
    solve = load_solve(dest)
    rows = []
    passed = 0
    for case in cases["cases"]:
        got = solve(int(case["input"]))
        ok = abs(got - int(case["expected"])) <= float(thr["numeric_tolerance"])
        if ok:
            passed += 1
        rows.append(
            {
                "id": case["id"],
                "got": got,
                "expected": case["expected"],
                "pass": ok,
            }
        )
    total = len(cases["cases"])
    ratio = (passed / total) if total else 1.0
    threshold = float(thr["pass_threshold"])
    reported = 1.0 if ratio >= threshold else ratio
    return {
        "passed": passed,
        "total": total,
        "ratio": ratio,
        "pass_threshold": threshold,
        "numeric_tolerance": float(thr["numeric_tolerance"]),
        "reported": reported,
        "cases": rows,
        "fingerprint": measure_fingerprint(tree),
    }
