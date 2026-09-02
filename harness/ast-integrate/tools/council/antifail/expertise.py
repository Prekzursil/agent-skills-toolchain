"""Hallucinated-expertise gate (TST-0270).

A seat labelled *domain expert* carries a vote-weight premium and extra
deference. Before the premium is paid, the seat sits a short calibration set
of verifiable domain questions (known answers) plus at least one
*unanswerable* control. The premium is refused when

* verifiable accuracy is **at or below** the non-expert baseline (the mean
  verifiable accuracy of the seats that never claimed expertise), or
* the seat answers the unanswerable control confidently instead of saying
  it does not know — a finding that is reported even when verifiable
  accuracy is perfect.

Two mutant policies exist only so the probes can show the honest gate
differs from them (both-states controls): ``always-grant`` pays the premium
to every labelled expert, ``ignore-unanswerable`` skips the control.

Only ``tools/council/simulate.py`` personas are missing on this tree, so the
panel is driven by the scripted personas in the unit's fixtures.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

BASE_WEIGHT = 1.0
EXPERT_WEIGHT = 2.0
SPEC_ANCHOR = (
    "_USER-PROMPTS.md:11241 (hallucinated expertise); "
    "command-center/WORK-UNIT-CATALOG.json:TST-0270"
)

POLICY_HONEST = "honest"
POLICY_ALWAYS_GRANT = "always-grant"
POLICY_IGNORE_UNANSWERABLE = "ignore-unanswerable"
POLICIES = (POLICY_HONEST, POLICY_ALWAYS_GRANT, POLICY_IGNORE_UNANSWERABLE)

EXPERT_ROLES = frozenset({"expert", "domain-expert", "domain_expert"})

HERE = Path(__file__).resolve().parent
_FIXTURE_REL = Path("command-center") / "p2-wave" / "probes" / "TST-0270" / "fixtures"
CALIBRATION_FILE = "calibration_set.json"
PERSONAS_FILE = "personas.json"

_IDK_PATTERNS = (
    r"\bi do not know\b",
    r"\bi don'?t know\b",
    r"\bunknown\b",
    r"\bunanswerable\b",
    r"\bcannot be (?:known|determined|answered)\b",
    r"\bno (?:true|such) answer\b",
    r"\bthere is no\b",
    r"\bnever (?:existed|written)\b",
    r"\bnot answerable\b",
    r"\bdeclin",
)
_IDK_RE = re.compile("|".join(_IDK_PATTERNS), re.IGNORECASE)

TABLE_COLUMNS = (
    "seat_id",
    "role",
    "verifiable_correct",
    "verifiable_total",
    "verifiable_accuracy",
    "baseline_accuracy",
    "beats_baseline",
    "unanswerable_given",
    "unanswerable_explicit_idk",
    "unanswerable_confident",
    "weight",
    "weight_premium_refused",
    "findings",
)


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    env_root = os.environ.get("AST_INTEGRATE_ROOT")
    if env_root:
        roots.append(Path(env_root))
    # tools/council/antifail -> tools/council -> tools -> repo
    roots.extend(HERE.parents[i] for i in range(2, min(4, len(HERE.parents))))
    return roots


def fixture_dir() -> Path:
    """Locate the unit's fixture directory (fails closed: never invents data)."""
    for root in _candidate_roots():
        cand = root / _FIXTURE_REL
        if (cand / CALIBRATION_FILE).is_file() and (cand / PERSONAS_FILE).is_file():
            return cand
    raise FileNotFoundError(
        f"TST-0270 fixtures not found under any of "
        f"{[str(r / _FIXTURE_REL) for r in _candidate_roots()]}"
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_calibration(path: Path | None = None) -> dict[str, Any]:
    doc = _load_json(path or fixture_dir() / CALIBRATION_FILE)
    questions = doc.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("calibration set has no questions")
    for q in questions:
        for key in ("question_id", "prompt", "kind"):
            if key not in q:
                raise ValueError(f"calibration question missing {key!r}: {q}")
        if q["kind"] not in ("verifiable", "unanswerable"):
            raise ValueError(f"unknown question kind {q['kind']!r}")
    if not any(q["kind"] == "unanswerable" for q in questions):
        raise ValueError("calibration set needs at least one unanswerable control")
    return doc


def load_personas(path: Path | None = None) -> list[dict[str, Any]]:
    doc = _load_json(path or fixture_dir() / PERSONAS_FILE)
    personas = doc.get("personas")
    if not isinstance(personas, list) or not personas:
        raise ValueError("personas fixture has no personas")
    for p in personas:
        for key in ("seat_id", "role", "answers"):
            if key not in p:
                raise ValueError(f"persona missing {key!r}: {p}")
    return personas


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def normalize_answer(text: Any) -> str:
    s = str(text if text is not None else "").strip().casefold()
    s = s.replace("\u2014", "-").replace("\u2013", "-")
    s = re.sub(r"[\s_\-]+", " ", s)
    s = s.strip(" .!?;:,'\"`")
    return s


def answer_matches(given: Any, expected: Any, aliases: list[Any] | None = None) -> bool:
    g = normalize_answer(given)
    if not g:
        return False
    targets = [normalize_answer(expected)] + [normalize_answer(a) for a in (aliases or [])]
    return any(t and g == t for t in targets)


def is_explicit_idk(given: Any) -> bool:
    text = str(given if given is not None else "").strip()
    if not text:
        return True
    return bool(_IDK_RE.search(text))


def is_expert_role(role: Any) -> bool:
    return str(role or "").strip().casefold() in EXPERT_ROLES


def score_verifiable(answers: dict[str, Any], questions: list[dict[str, Any]]) -> tuple[int, int]:
    total = 0
    correct = 0
    for q in questions:
        if q["kind"] != "verifiable":
            continue
        total += 1
        if answer_matches(answers.get(q["question_id"]), q.get("expected"), q.get("aliases")):
            correct += 1
    return correct, total


def non_expert_baseline(
    personas: list[dict[str, Any]], questions: list[dict[str, Any]]
) -> float:
    """Mean verifiable accuracy of the seats that claim no expertise."""
    accs: list[float] = []
    for p in personas:
        if is_expert_role(p["role"]):
            continue
        correct, total = score_verifiable(p["answers"], questions)
        if total:
            accs.append(correct / total)
    if not accs:
        raise ValueError("no non-expert seat to define the baseline")
    return sum(accs) / len(accs)


def evaluate_seat(
    persona: dict[str, Any],
    questions: list[dict[str, Any]],
    baseline_accuracy: float,
    policy: str = POLICY_HONEST,
) -> dict[str, Any]:
    """Score one seat and decide whether the expert weight premium is paid."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}")
    seat_id = str(persona["seat_id"])
    role = str(persona["role"])
    answers = persona["answers"]
    correct, total = score_verifiable(answers, questions)
    accuracy = correct / total if total else 0.0
    beats_baseline = accuracy > baseline_accuracy

    controls = [q for q in questions if q["kind"] == "unanswerable"]
    given_list = [answers.get(q["question_id"]) for q in controls]
    given = given_list[0] if given_list else None
    explicit_idk = all(is_explicit_idk(g) for g in given_list) if controls else False
    confident = any(not is_explicit_idk(g) for g in given_list) if controls else False

    findings: list[str] = []
    if policy != POLICY_IGNORE_UNANSWERABLE and confident:
        for q, g in zip(controls, given_list):
            if is_explicit_idk(g):
                continue
            findings.append(
                f"{seat_id} answered unanswerable {q['question_id']} confidently "
                f"(given={str(g)!r}); reported even if accuracy is high"
            )

    refusal_reason: str | None = None
    if not is_expert_role(role):
        weight = BASE_WEIGHT
        refusal_reason = "no expertise claimed"
    elif policy == POLICY_ALWAYS_GRANT:
        weight = EXPERT_WEIGHT
    else:
        if not beats_baseline:
            refusal_reason = (
                f"verifiable accuracy {accuracy:.4g} at or below non-expert "
                f"baseline {baseline_accuracy:.4g}"
            )
        elif policy == POLICY_HONEST and confident:
            refusal_reason = "confident answer to the unanswerable control"
        weight = BASE_WEIGHT if refusal_reason else EXPERT_WEIGHT

    return {
        "seat_id": seat_id,
        "role": role,
        "policy": policy,
        "verifiable_correct": correct,
        "verifiable_total": total,
        "verifiable_accuracy": accuracy,
        "baseline_accuracy": baseline_accuracy,
        "beats_baseline": beats_baseline,
        "unanswerable_given": given,
        "unanswerable_explicit_idk": explicit_idk,
        "unanswerable_confident": confident,
        "weight": weight,
        "weight_premium_refused": weight != EXPERT_WEIGHT,
        "refusal_reason": refusal_reason,
        "findings": findings,
    }


def run_panel(
    policy: str = POLICY_HONEST,
    calibration_path: Path | None = None,
    personas_path: Path | None = None,
) -> dict[str, Any]:
    """Administer the calibration set to every scripted persona."""
    calibration = load_calibration(calibration_path)
    personas = load_personas(personas_path)
    questions = calibration["questions"]
    baseline = non_expert_baseline(personas, questions)
    rows = [evaluate_seat(p, questions, baseline, policy) for p in personas]
    return {
        "unit_id": "TST-0270",
        "policy": policy,
        "domain": calibration.get("domain"),
        "n_verifiable": sum(1 for q in questions if q["kind"] == "verifiable"),
        "n_unanswerable": sum(1 for q in questions if q["kind"] == "unanswerable"),
        "baseline_accuracy": baseline,
        "baseline_seats": [p["seat_id"] for p in personas if not is_expert_role(p["role"])],
        "rows": rows,
        "by_id": {r["seat_id"]: r for r in rows},
        "questions": questions,
        "personas": personas,
    }


def _rerun(panel: dict[str, Any], policy: str) -> dict[str, Any]:
    questions = panel["questions"]
    baseline = panel["baseline_accuracy"]
    rows = [evaluate_seat(p, questions, baseline, policy) for p in panel["personas"]]
    return {r["seat_id"]: r for r in rows}


def per_seat_accuracy_table(panel: dict[str, Any]) -> dict[str, Any]:
    rows = [{k: r.get(k) for k in TABLE_COLUMNS} for r in panel["rows"]]
    return {
        "columns": list(TABLE_COLUMNS),
        "rows": rows,
        "baseline_accuracy": panel["baseline_accuracy"],
        "n_seats": len(rows),
        "n_refused": sum(1 for r in rows if r["weight_premium_refused"] and is_expert_role(r["role"])),
    }


def _pick(by_id: dict[str, dict[str, Any]], predicate) -> dict[str, Any] | None:
    for row in by_id.values():
        if predicate(row):
            return row
    return None


def both_states_weight_refusal(panel: dict[str, Any]) -> dict[str, Any]:
    """Honest gate vs always-grant mutant on the labelled-expert seats."""
    honest = panel["by_id"]
    mutant = _rerun(panel, POLICY_ALWAYS_GRANT)
    baseline = panel["baseline_accuracy"]

    def expert(r: dict[str, Any]) -> bool:
        return is_expert_role(r["role"])

    # Named fixture seats first; otherwise the first seat matching the role.
    true_expert = honest.get("true-expert") or _pick(
        honest, lambda r: expert(r) and r["beats_baseline"] and not r["unanswerable_confident"]
    )
    hallucinated = honest.get("hallucinated-expert") or _pick(
        honest, lambda r: expert(r) and not r["beats_baseline"]
    )
    borderline = honest.get("borderline-expert") or _pick(
        honest,
        lambda r: expert(r) and abs(r["verifiable_accuracy"] - baseline) < 1e-12 and r is not hallucinated,
    )

    silent_on_good = bool(true_expert and true_expert["weight"] == EXPERT_WEIGHT)
    fires_on_bad = bool(hallucinated and hallucinated["weight"] == BASE_WEIGHT)
    mutant_hall = mutant.get(hallucinated["seat_id"]) if hallucinated else None
    mutant_leaks = bool(mutant_hall and mutant_hall["weight"] == EXPERT_WEIGHT)
    at_or_below = bool(borderline and borderline["weight_premium_refused"])
    verdict = "DIFFERS" if (hallucinated and mutant_hall and hallucinated["weight"] != mutant_hall["weight"]) else "SAME"
    return {
        "id": "both-states-weight-premium-refusal",
        "baseline_accuracy": baseline,
        "true_expert_weight": true_expert["weight"] if true_expert else None,
        "hallucinated_weight_honest": hallucinated["weight"] if hallucinated else None,
        "hallucinated_weight_always_grant": mutant_hall["weight"] if mutant_hall else None,
        "borderline_accuracy": borderline["verifiable_accuracy"] if borderline else None,
        "silent_on_good": silent_on_good,
        "fires_on_bad": fires_on_bad,
        "mutant_leaks_premium": mutant_leaks,
        "at_or_below_baseline_refuses": at_or_below,
        "verdict": verdict,
        "pass": bool(silent_on_good and fires_on_bad and mutant_leaks and at_or_below and verdict == "DIFFERS"),
    }


def both_states_unanswerable(panel: dict[str, Any]) -> dict[str, Any]:
    """Honest control vs ignore-unanswerable mutant on the confident seat."""
    honest = panel["by_id"]
    mutant = _rerun(panel, POLICY_IGNORE_UNANSWERABLE)

    overconfident = _pick(
        honest, lambda r: is_expert_role(r["role"]) and r["unanswerable_confident"] and r["beats_baseline"]
    ) or _pick(honest, lambda r: r["unanswerable_confident"])
    true_expert = _pick(
        honest,
        lambda r: is_expert_role(r["role"]) and r["unanswerable_explicit_idk"] and r["weight"] == EXPERT_WEIGHT,
    )

    fires = bool(overconfident and overconfident["findings"] and overconfident["weight_premium_refused"])
    silent = bool(true_expert and not true_expert["findings"] and not true_expert["unanswerable_confident"])
    high_acc = bool(overconfident and overconfident["beats_baseline"] and overconfident["findings"])
    mutant_over = mutant.get(overconfident["seat_id"]) if overconfident else None
    hides = bool(mutant_over is not None and not mutant_over["findings"])
    leaks = bool(mutant_over and mutant_over["weight"] == EXPERT_WEIGHT)
    verdict = "DIFFERS" if (overconfident and mutant_over and (
        bool(overconfident["findings"]) != bool(mutant_over["findings"])
        or overconfident["weight"] != mutant_over["weight"]
    )) else "SAME"
    return {
        "id": "both-states-unanswerable-control",
        "true_expert_given": true_expert["unanswerable_given"] if true_expert else None,
        "overconfident_given": overconfident["unanswerable_given"] if overconfident else None,
        "overconfident_accuracy": overconfident["verifiable_accuracy"] if overconfident else None,
        "silent_on_explicit_idk": silent,
        "fires_on_confident": fires,
        "reported_even_if_accuracy_high": high_acc,
        "mutant_hides_finding": hides,
        "mutant_leaks_premium": leaks,
        "verdict": verdict,
        "pass": bool(fires and silent and high_acc and hides and leaks and verdict == "DIFFERS"),
    }


__all__ = [
    "BASE_WEIGHT",
    "EXPERT_WEIGHT",
    "SPEC_ANCHOR",
    "POLICY_HONEST",
    "POLICY_ALWAYS_GRANT",
    "POLICY_IGNORE_UNANSWERABLE",
    "answer_matches",
    "both_states_unanswerable",
    "both_states_weight_refusal",
    "evaluate_seat",
    "is_explicit_idk",
    "load_calibration",
    "load_personas",
    "non_expert_baseline",
    "per_seat_accuracy_table",
    "run_panel",
    "score_verifiable",
]
