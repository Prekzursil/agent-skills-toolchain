"""Deterministic fixture trees for TST-0030 freeze-versus-sample probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from freeze_sample import (  # noqa: E402
    LABEL_FROZEN,
    LABEL_SAMPLED,
    BaselineRefused,
    as_baseline,
    capture_tree,
)

A_BODY = '{"id":"a","n":1}\n'
B_BODY = '{"id":"b","n":2}\n'
B_MUTATED = '{"id":"b","n":99}\n'
C_BODY = '{"id":"c","n":3}\n'
COUNTS = "files=2\n"
MUTATED_REL = "subjects/b.json"
ADDED_REL = "subjects/c.json"
LIVE_REL = "freeze_sample.py"


def plant_quiescent(root: Path) -> Path:
    subjects = root / "subjects"
    subjects.mkdir(parents=True, exist_ok=True)
    (subjects / "a.json").write_bytes(A_BODY.encode("utf-8"))
    (subjects / "b.json").write_bytes(B_BODY.encode("utf-8"))
    (root / "counts.txt").write_bytes(COUNTS.encode("utf-8"))
    return root


def mutate_mid_capture(root: Path) -> None:
    """Sibling-agent mutation: rewrite one subject and add another."""
    (root / MUTATED_REL).write_bytes(B_MUTATED.encode("utf-8"))
    (root / ADDED_REL).write_bytes(C_BODY.encode("utf-8"))


def run_quiescent(root: Path) -> dict:
    plant_quiescent(root)
    result = capture_tree(root)
    promoted = as_baseline(result)
    result["baseline"] = promoted.get("baseline") is True
    return result


def run_mutated(root: Path) -> dict:
    plant_quiescent(root)
    result = capture_tree(root, mid_hook=mutate_mid_capture)
    refused = False
    try:
        as_baseline(result)
    except BaselineRefused:
        refused = True
    result["as_baseline_refused"] = refused
    result["refuse_locus"] = "as_baseline-on-sampled" if refused else None
    return result


def run_live_product_file() -> dict:
    product_dir = REPO / "tools" / "command-center"
    return capture_tree(product_dir, include_relpaths={LIVE_REL})


def compact(result: dict) -> dict:
    return {
        "start_tree_hash": result["start_tree_hash"],
        "end_tree_hash": result["end_tree_hash"],
        "hashes_equal": result["hashes_equal"],
        "label": result["label"],
        "baseline_eligible": result["baseline_eligible"],
        "baseline_refused": result["baseline_refused"],
        "refused_code": result.get("refused_code"),
        "refused_reason": result.get("refused_reason"),
        "changed_paths": result["changed_paths"],
        "changed_path_names": result["changed_path_names"],
        "snapshot": result["snapshot"],
        "anchoring": result["anchoring"],
        "sampled_at": result.get("sampled_at"),
        "started_at": result.get("started_at"),
        "ended_at": result.get("ended_at"),
        "as_baseline_refused": result.get("as_baseline_refused"),
        "baseline": result.get("baseline"),
    }


def assert_quiescent(result: dict) -> list[str]:
    errors: list[str] = []
    if result.get("label") != LABEL_FROZEN:
        errors.append(f"quiescent label={result.get('label')} want FROZEN")
    if result.get("start_tree_hash") != result.get("end_tree_hash"):
        errors.append("quiescent start/end hashes differ")
    if result.get("changed_paths"):
        errors.append(f"quiescent changed_paths={result.get('changed_paths')}")
    if result.get("baseline_eligible") is not True:
        errors.append("quiescent not baseline_eligible")
    if result.get("baseline_refused") is True:
        errors.append("quiescent marked baseline_refused")
    if result.get("anchoring") != "SHA-ANCHORED":
        errors.append(f"quiescent anchoring={result.get('anchoring')}")
    return errors


def assert_mutated(result: dict) -> list[str]:
    errors: list[str] = []
    if result.get("label") != LABEL_SAMPLED:
        errors.append(f"mutated label={result.get('label')} want SAMPLED")
    if result.get("start_tree_hash") == result.get("end_tree_hash"):
        errors.append("mutated start/end hashes equal (end hash was not taken)")
    names = list(result.get("changed_path_names") or [])
    if MUTATED_REL not in names:
        errors.append(f"mutated path {MUTATED_REL} not enumerated: {names}")
    if ADDED_REL not in names:
        errors.append(f"added path {ADDED_REL} not enumerated: {names}")
    if result.get("baseline_eligible") is not False:
        errors.append("mutated still baseline_eligible")
    if result.get("baseline_refused") is not True:
        errors.append("mutated not baseline_refused")
    if result.get("as_baseline_refused") is not True:
        errors.append("as_baseline did not refuse SAMPLED capture")
    if result.get("anchoring") != "SAMPLED-AT-TIME":
        errors.append(f"mutated anchoring={result.get('anchoring')}")
    if not result.get("sampled_at"):
        errors.append("mutated missing sampled_at timestamp")
    return errors


def dumps(obj: object) -> str:
    return json.dumps(obj, indent=1, sort_keys=True)
