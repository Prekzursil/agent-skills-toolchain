#!/usr/bin/env python3
"""Run the WFA-0092 repair regression suite and its revert-mutation campaign."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from defects import DEFECTS, scanner_both_states

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARTIFACT_REL = "command-center/wfa/WFA-0092-repair-regression-suite.json"
SENTINEL = "SUCCESS:WFA-0092"
SCHEMA_REF = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture"


@dataclass
class TestRow:
    id: str
    repair_unit: str
    title: str
    ok: bool
    result: dict[str, Any]


@dataclass
class SuiteResult:
    green: bool
    rows: list[TestRow]
    scanner: dict[str, Any]
    extras: dict[str, Any] = field(default_factory=dict)

    def by_id(self) -> dict[str, TestRow]:
        return {r.id: r for r in self.rows}


def repaired_tree() -> dict[str, bool]:
    return {d.id: True for d in DEFECTS}


def mutant_tree(defect_id: str) -> dict[str, bool]:
    tree = repaired_tree()
    if defect_id not in tree:
        raise KeyError(defect_id)
    tree[defect_id] = False
    return tree


def run_suite(tree: dict[str, bool], root: Path) -> SuiteResult:
    root.mkdir(parents=True, exist_ok=True)
    scanner = scanner_both_states()
    rows: list[TestRow] = []
    for d in DEFECTS:
        dtmp = root / d.id
        dtmp.mkdir(parents=True, exist_ok=True)
        raw = d.run(tree[d.id], dtmp)
        ok = bool(d.check(raw))
        rows.append(
            TestRow(
                id=d.id,
                repair_unit=d.repair_unit,
                title=d.title,
                ok=ok,
                result=_jsonable(raw),
            )
        )
    green = scanner["ok"] is True and all(r.ok for r in rows)
    return SuiteResult(green=green, rows=rows, scanner=scanner)


def run_campaign(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    baseline = run_suite(repaired_tree(), root / "baseline")
    mutants: list[dict[str, Any]] = []
    for d in DEFECTS:
        result = run_suite(mutant_tree(d.id), root / "mutant" / d.id)
        target = result.by_id()[d.id]
        extra_red = [r.id for r in result.rows if (not r.ok) and r.id != d.id]
        survived = target.ok is True
        mutants.append(
            {
                "defect_id": d.id,
                "repair_unit": d.repair_unit,
                "title": d.title,
                "operator": "revert-fix",
                "repaired_verdict": "GREEN" if baseline.by_id()[d.id].ok else "RED",
                "mutant_suite_verdict": "GREEN" if result.green else "RED",
                "target_went_red": (not target.ok),
                "extra_red": extra_red,
                "survived": survived,
                "independent": (not extra_red) and (not survived),
            }
        )
    survivors = [m["defect_id"] for m in mutants if m["survived"]]
    independent = all(m["independent"] for m in mutants)
    ok = (
        baseline.green
        and not survivors
        and independent
        and len(mutants) == len(DEFECTS)
        and all(m["mutant_suite_verdict"] == "RED" for m in mutants)
        and all(m["repaired_verdict"] == "GREEN" for m in mutants)
    )
    return {
        "ok": ok,
        "baseline_green": baseline.green,
        "scanner": baseline.scanner,
        "baseline_rows": [_row_public(r) for r in baseline.rows],
        "mutations": mutants,
        "surviving_mutants": survivors,
        "surviving_mutant_count": len(survivors),
        "independent": independent,
        "defect_count": len(DEFECTS),
    }


def verdict_fingerprint(campaign: dict[str, Any]) -> str:
    """Path-independent digest so Linux and a Windows/CI rerun can compare."""
    payload = {
        "baseline_green": campaign["baseline_green"],
        "surviving_mutants": list(campaign["surviving_mutants"]),
        "mutations": [
            {
                "defect_id": m["defect_id"],
                "repair_unit": m["repair_unit"],
                "repaired_verdict": m["repaired_verdict"],
                "mutant_suite_verdict": m["mutant_suite_verdict"],
                "target_went_red": m["target_went_red"],
                "extra_red": list(m["extra_red"]),
                "survived": m["survived"],
                "independent": m["independent"],
            }
            for m in campaign["mutations"]
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def platform_stable_verdicts(campaign: dict[str, Any], repeats: int = 3) -> dict[str, Any]:
    """Re-run the campaign `repeats` times; fingerprints must match."""
    import tempfile

    fps: list[str] = [verdict_fingerprint(campaign)]
    for i in range(repeats - 1):
        with tempfile.TemporaryDirectory(prefix=f"wfa0092-plat-{i}-") as td:
            again = run_campaign(Path(td))
        fps.append(verdict_fingerprint(again))
    return {
        "repeats": repeats,
        "fingerprints": fps,
        "same_verdicts": len(set(fps)) == 1,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "os_name": platform.system(),
    }


def _row_public(r: TestRow) -> dict[str, Any]:
    return {
        "defect_id": r.id,
        "repair_unit": r.repair_unit,
        "title": r.title,
        "verdict": "GREEN" if r.ok else "RED",
        "ok": r.ok,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def load_artifact(repo: Path | None = None) -> dict[str, Any]:
    path = (repo or REPO) / ARTIFACT_REL
    return json.loads(path.read_text(encoding="utf-8"))
