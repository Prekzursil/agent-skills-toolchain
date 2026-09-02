"""Probe 1 engine: classify evidentiary basis of expertise / weight inputs."""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WEIGHTS = REPO / "tools/council/vote/weights.py"
SELECT = REPO / "tools/council/participants/select_expertise.py"
REGISTRY = REPO / "tools/council/participants/registry.py"
BLD_RUNTIME = REPO / "command-center/p2-wave/probes/BLD-0054/runtime.py"
COUNCILS = HERE / "fixtures/councils.json"

BASIS_CALIBRATION = "calibration_record"
BASIS_PAST_ACCURACY = "past_accuracy_score"
BASIS_FREE_TEXT = "free_text_self_assertion"
BASIS_CALLER_NUMBER = "caller_supplied_number_without_quiz"
BASIS_ABSENT = "module_absent"


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _snippet(path: Path, needle: str) -> dict:
    text = path.read_text(encoding="utf-8")
    idx = text.find(needle)
    if idx < 0:
        return {"path": path.relative_to(REPO).as_posix(), "line": 0, "snippet": needle, "found": False}
    line = text[:idx].count("\n") + 1
    return {
        "path": path.relative_to(REPO).as_posix(),
        "line": line,
        "snippet": needle,
        "found": True,
    }


def classify_weights() -> dict:
    src = WEIGHTS.read_text(encoding="utf-8")
    tree = ast.parse(src)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    mentions_expertise = any(
        tok in src.lower()
        for tok in ("expertise", "calibrat", "quiz", "competence", "known-answer")
    )
    authority_assign = _snippet(WEIGHTS, "authority = int(row[\"authority\"])")
    role_ladder = _snippet(WEIGHTS, "AUTHORITY_BY_ROLE")
    return {
        "id": "production-vote-weights",
        "path": WEIGHTS.relative_to(REPO).as_posix(),
        "present": True,
        "used_as": "vote-weight input (Seat.authority / role ladder)",
        "evidentiary_basis": BASIS_CALLER_NUMBER,
        "expertise_tokens_in_ast": sorted(
            n for n in names if "expert" in n.lower() or "calibr" in n.lower() or "quiz" in n.lower()
        ),
        "mentions_expertise_or_calibration": mentions_expertise,
        "authority_integer_trusted": authority_assign["found"],
        "role_ladder_trusted": role_ladder["found"],
        "anchors": [authority_assign, role_ladder],
        "note": (
            "seat_from_mapping accepts a caller integer authority or a role "
            "looked up in AUTHORITY_BY_ROLE. No expertise field is read; no "
            "calibration record or past-accuracy score is required before "
            "the integer becomes vote weight."
        ),
    }


def classify_selector() -> dict:
    return {
        "id": "production-select-expertise",
        "path": SELECT.relative_to(REPO).as_posix(),
        "present": SELECT.is_file(),
        "used_as": "expertise-ranked participant selection",
        "evidentiary_basis": BASIS_ABSENT,
        "note": "tools/council/participants/select_expertise.py is absent; claimed expertise is not verified before seating.",
    }


def classify_registry() -> dict:
    return {
        "id": "production-participant-registry",
        "path": REGISTRY.relative_to(REPO).as_posix(),
        "present": REGISTRY.is_file(),
        "used_as": "declared expertise store",
        "evidentiary_basis": BASIS_ABSENT if not REGISTRY.is_file() else BASIS_FREE_TEXT,
        "note": "tools/council/participants/registry.py is absent; there is no calibration-history pointer on disk.",
    }


def classify_bld0054() -> dict:
    rt = _load_module(BLD_RUNTIME, "adv0099_bld0054_runtime")
    state = rt.CouncilState(
        participants=[
            rt.Participant(
                "expert",
                "e",
                ("1", "1", "1"),
                "domain-authority",
                claimed_domain="cryptography",
                quiz_accuracy=1.0,
            ),
            rt.Participant(
                "other",
                "o",
                ("1", "1", "2"),
                "critic",
                claimed_domain="",
                quiz_accuracy=1.0,
            ),
        ]
    )
    enabled = rt.CouncilRuntime(enabled=["competence-probe"])
    refused_high = rt.apply_competence(enabled, state)
    state_low = rt.CouncilState(
        participants=[
            rt.Participant(
                "expert",
                "e",
                ("1", "1", "1"),
                "domain-authority",
                claimed_domain="cryptography",
                quiz_accuracy=0.2,
            )
        ]
    )
    refused_low = rt.apply_competence(rt.CouncilRuntime(enabled=["competence-probe"]), state_low)
    claimed = _snippet(BLD_RUNTIME, "claimed_domain: str = \"\"")
    quiz = _snippet(BLD_RUNTIME, "quiz_accuracy: float = 1.0")
    gate = _snippet(BLD_RUNTIME, "if p.claimed_domain and p.quiz_accuracy < 0.6:")
    return {
        "id": "bld0054-competence-probe",
        "path": BLD_RUNTIME.relative_to(REPO).as_posix(),
        "present": True,
        "used_as": "competence gate before domain-authority seating",
        "evidentiary_basis": BASIS_CALLER_NUMBER,
        "claimed_domain_basis": BASIS_FREE_TEXT,
        "quiz_accuracy_basis": BASIS_CALLER_NUMBER,
        "self_asserted_accuracy_1_0_refused": "expert" in refused_high,
        "low_accuracy_0_2_refused": "expert" in refused_low,
        "accepts_unmeasured_high_score": "expert" not in refused_high,
        "anchors": [claimed, quiz, gate],
        "note": (
            "apply_competence never poses a question. It trusts "
            "Participant.quiz_accuracy supplied by the caller. A "
            "cryptography claim with quiz_accuracy=1.0 is seated; 0.2 is refused."
        ),
    }


def classify_sample_councils() -> dict:
    sample = json.loads(COUNCILS.read_text(encoding="utf-8"))
    rows = []
    for council in sample.get("sample_councils") or []:
        for p in council.get("participants") or []:
            claim = str(p.get("claimed_expertise") or "")
            if not claim:
                continue
            rows.append(
                {
                    "council_id": council.get("id"),
                    "seat_id": p.get("seat_id"),
                    "claimed_expertise": claim,
                    "self_description": p.get("self_description"),
                    "requested_authority": p.get("requested_authority"),
                    "evidentiary_basis": BASIS_FREE_TEXT,
                    "declared_basis": p.get("evidentiary_basis_declared"),
                }
            )
    return {
        "id": "sample-council-expertise-claims",
        "path": COUNCILS.relative_to(REPO).as_posix(),
        "present": True,
        "used_as": "recorded expertise claims in a sample council",
        "evidentiary_basis": BASIS_FREE_TEXT,
        "claims": rows,
        "note": "Fixture council records a free-text self-assertion and a requested authority integer with declared basis none.",
    }


def run_audit() -> dict:
    inputs = [
        classify_weights(),
        classify_selector(),
        classify_registry(),
        classify_bld0054(),
        classify_sample_councils(),
    ]
    checkable = [
        i
        for i in inputs
        if i.get("evidentiary_basis") in {BASIS_CALIBRATION, BASIS_PAST_ACCURACY}
    ]
    unverifiable = [
        i
        for i in inputs
        if i.get("evidentiary_basis") in {BASIS_FREE_TEXT, BASIS_CALLER_NUMBER, BASIS_ABSENT}
    ]
    bld = next(i for i in inputs if i["id"] == "bld0054-competence-probe")
    weights = next(i for i in inputs if i["id"] == "production-vote-weights")
    pathology = (
        weights["authority_integer_trusted"]
        and not weights["mentions_expertise_or_calibration"]
        and bld["accepts_unmeasured_high_score"]
        and not any(i["id"] == "production-select-expertise" and i["present"] for i in inputs)
    )
    return {
        "pass": True,
        "pathology_confirmed": pathology,
        "checkable_inputs": [i["id"] for i in checkable],
        "unverifiable_inputs": [i["id"] for i in unverifiable],
        "inputs": inputs,
        "catalog_probe": (
            "Probe 1: for each expertise claim used as an input, identify its "
            "evidentiary basis in the code (a calibration record, a past-accuracy "
            "score, or a free-text self-assertion)."
        ),
    }
