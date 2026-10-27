#!/usr/bin/env python3
"""CNF-0173 confirmer harness: spec:10944 trip-wires + live antifail bind.

This is a confirmer-side oracle, not IMP-0318's production module. It exists
so a confirmer-authored scenario can be shown to be a valid trip condition
and so we can name the control/observable the live runtime *should* emit.
Live bind looks for tools/council/antifail/unanimity.py (and siblings).
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

NEAR_DUP = 0.80
COLLAPSE_FLOOR = 0.85
INSTANT_MAX_FIRST_VOTE_ROUND = 1
LIVE_UNANIMITY = REPO / "tools" / "council" / "antifail" / "unanimity.py"
LIVE_SYCOPHANCY = REPO / "tools" / "council" / "antifail" / "sycophancy.py"
LIVE_ROLE = REPO / "tools" / "council" / "antifail" / "role_collapse.py"
LIVE_NOVELTY = REPO / "tools" / "council" / "antifail" / "novelty.py"
TOKEN_RE = re.compile(r"[a-z0-9]+")

# Variant suffixes like "(variant 3)" are idea-count gaming, not new ideas.
VARIANT_TAIL = re.compile(r"\s*\(variant\s+\d+\)\s*$", re.I)


def tokens(text: str) -> set[str]:
    cleaned = VARIANT_TAIL.sub("", text or "")
    return set(TOKEN_RE.findall(cleaned.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def pairwise_mean_jaccard(texts: list[str]) -> float:
    if len(texts) < 2:
        return 1.0
    acc = 0.0
    n = 0
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            acc += jaccard(tokens(texts[i]), tokens(texts[j]))
            n += 1
    return acc / n if n else 1.0


def first_vote_of(part: dict[str, Any]) -> tuple[int, str]:
    votes = list(part.get("votes") or [])
    for idx, v in enumerate(votes, start=1):
        if str(v).strip():
            return idx, str(v).strip()
    return 0, ""


def independent_briefs(scenario: dict[str, Any]) -> list[str]:
    raw = []
    for p in scenario.get("participants") or []:
        b = str(p.get("brief") or "").strip()
        if b:
            raw.append(b)
    kept: list[str] = []
    for b in raw:
        tb = tokens(b)
        if any(jaccard(tb, tokens(k)) >= NEAR_DUP for k in kept):
            continue
        kept.append(b)
    return kept


def unanimous_at_first_vote(scenario: dict[str, Any]) -> tuple[bool, int, str]:
    declared = int(scenario.get("first_vote_round") or 1)
    choices: list[str] = []
    rounds: list[int] = []
    for p in scenario.get("participants") or []:
        r, v = first_vote_of(p)
        if not v:
            return False, declared, ""
        rounds.append(r)
        choices.append(v)
    first = min(rounds) if rounds else declared
    if not choices:
        return False, first, ""
    same = len(set(choices)) == 1 and all(r == first for r in rounds)
    return same, first, choices[0] if choices else ""


def critic_id_for(scenario: dict[str, Any]) -> str:
    sid = str(scenario.get("id") or "anonymous").split("cnf0173-", 1)[-1]
    return f"critic.independent.{sid}"


def evaluate_instant_unanimity(scenario: dict[str, Any]) -> dict[str, Any]:
    uni, first_round, choice = unanimous_at_first_vote(scenario)
    briefs = independent_briefs(scenario)
    fire = (
        uni
        and first_round <= INSTANT_MAX_FIRST_VOTE_ROUND
        and len(briefs) == 0
    )
    event: dict[str, Any] = {
        "control_id": "instant_unanimity",
        "spec_anchor": "spec:10944",
        "fired": fire,
        "first_vote_round": first_round,
        "unanimous_at_first_vote": uni,
        "independent_brief_count": len(briefs),
        "first_choice": choice,
        "observable": None,
    }
    if not fire:
        return event
    critic = critic_id_for(scenario)
    round_id = "R-blind-1"
    new_decision = choice
    changed = False
    if scenario.get("planted_wrong_consensus") and scenario.get("correct_decision"):
        new_decision = str(scenario["correct_decision"])
        changed = new_decision != choice
    event["observable"] = {
        "kind": "blind_re_evaluation",
        "reevaluation_round_id": round_id,
        "forced_dissent_prompt": (
            "Ignore the round-1 consensus. Produce the strongest "
            "counterexample and a dissenting vote before any score stands."
        ),
        "recruited_critic": critic,
        "role_rotation": ["critic", "engineer", "chair"],
        "strongest_counterexample": (scenario.get("meta") or {}).get(
            "hidden_evidence"
        )
        or "planted hidden evidence was not cited in round 1",
        "decision_before": choice,
        "decision_after": new_decision,
        "second_pass_changed_outcome": changed,
    }
    return event


def evaluate_role_collapse(scenario: dict[str, Any]) -> dict[str, Any]:
    args = [str(p.get("argument") or "") for p in scenario.get("participants") or []]
    sim = pairwise_mean_jaccard(args)
    fire = len(args) >= 2 and sim >= COLLAPSE_FLOOR
    return {
        "control_id": "role_collapse",
        "spec_anchor": "spec:11230",
        "fired": fire,
        "mean_argument_jaccard": round(sim, 6),
        "floor": COLLAPSE_FLOOR,
        "observable": {
            "kind": "role_collapse_flag",
            "collapsed_seats": [p.get("seat") for p in scenario.get("participants") or []],
        }
        if fire
        else None,
    }


def _canonical_idea(text: str) -> str:
    t = VARIANT_TAIL.sub("", text or "")
    return " ".join(TOKEN_RE.findall(t.lower()))


def evaluate_novelty(scenario: dict[str, Any]) -> dict[str, Any]:
    ideas = [str(x) for x in (scenario.get("ideas") or [])]
    claimed = scenario.get("claimed_unique_ideas")
    if claimed is None and not ideas:
        return {
            "control_id": "novelty",
            "spec_anchor": "spec:11236",
            "fired": False,
            "applicable": False,
            "claimed_unique_ideas": None,
            "unique_after_dedup": None,
            "observable": None,
        }
    clusters: list[set[str]] = []
    for idea in ideas:
        tok = tokens(idea)
        placed = False
        for cl in clusters:
            if jaccard(tok, cl) >= NEAR_DUP:
                cl |= tok
                placed = True
                break
        if not placed:
            clusters.append(set(tok))
    unique = len(clusters)
    claimed_n = int(claimed or 0)
    fire = claimed_n >= 100 and unique < 100
    return {
        "control_id": "novelty",
        "spec_anchor": "spec:11236",
        "fired": fire,
        "applicable": True,
        "claimed_unique_ideas": claimed_n,
        "raw_idea_count": len(ideas),
        "unique_after_dedup": unique,
        "observable": {
            "kind": "novelty_reject",
            "claimed": claimed_n,
            "unique_after_dedup": unique,
            "canonical_sample": _canonical_idea(ideas[0]) if ideas else "",
        }
        if fire
        else None,
    }


def evaluate_oracle(scenario: dict[str, Any]) -> dict[str, Any]:
    instant = evaluate_instant_unanimity(scenario)
    collapse = evaluate_role_collapse(scenario)
    novelty = evaluate_novelty(scenario)
    fired = [c for c in (instant, collapse, novelty) if c.get("fired")]
    return {
        "scenario_id": scenario.get("id"),
        "author": scenario.get("author"),
        "domain": scenario.get("domain"),
        "instant_unanimity": instant,
        "role_collapse": collapse,
        "novelty": novelty,
        "controls_fired": [c["control_id"] for c in fired],
        "primary_control": fired[0]["control_id"] if fired else None,
        "primary_observable": (fired[0].get("observable") if fired else None),
    }


def _load_py(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _call_live_fn(fn: Callable, scenario: dict[str, Any]) -> dict[str, Any]:
    try:
        out = fn(scenario)
    except TypeError:
        try:
            out = fn(json.dumps(scenario))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    return {"ok": True, "result": out}


def inspect_live_module(path: Path) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "path": path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path),
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "functions": [],
        "bound": False,
        "call": None,
    }
    if not path.is_file():
        rec["reason"] = "absent"
        return rec
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rec["functions"] = [
            n.name for n in tree.body if isinstance(n, ast.FunctionDef)
        ]
    except (OSError, SyntaxError) as exc:
        rec["reason"] = f"unparseable:{type(exc).__name__}"
        return rec
    try:
        mod = _load_py(path)
    except Exception as exc:  # noqa: BLE001
        rec["reason"] = f"import-failed:{type(exc).__name__}"
        return rec
    if mod is None:
        rec["reason"] = "import-failed"
        return rec
    for name in (
        "evaluate",
        "trigger",
        "detect",
        "check_unanimity",
        "instant_unanimity",
        "apply",
        "run",
    ):
        fn = getattr(mod, name, None)
        if callable(fn):
            rec["bound"] = True
            rec["entry"] = name
            rec["call"] = _call_live_fn(fn, {"id": "cnf0173-live-probe", "participants": []})
            return rec
    rec["reason"] = "no-known-entry-point"
    rec["bound"] = True
    rec["entry"] = None
    return rec


def bind_live() -> dict[str, Any]:
    modules = {
        "unanimity": inspect_live_module(LIVE_UNANIMITY),
        "sycophancy": inspect_live_module(LIVE_SYCOPHANCY),
        "role_collapse": inspect_live_module(LIVE_ROLE),
        "novelty": inspect_live_module(LIVE_NOVELTY),
    }
    any_present = any(m.get("present") for m in modules.values())
    any_fired = False
    named: list[str] = []
    for key, m in modules.items():
        call = m.get("call") or {}
        result = call.get("result")
        fired = False
        if isinstance(result, dict):
            fired = bool(result.get("fired") or result.get("trigger") or result.get("hit"))
        elif result is True:
            fired = True
        if fired:
            any_fired = True
            named.append(key)
    return {
        "any_module_present": any_present,
        "any_live_control_fired": any_fired,
        "live_controls_that_fired": named,
        "modules": modules,
        "production_path": "tools/council/antifail/unanimity.py",
    }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()
