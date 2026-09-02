"""Deterministic scripted-persona CouncilSpec simulator for TST-0293.

tools/council/simulate.py is absent (TST-0257 not delivered). This is the
local sweep substrate, not an ADV/A2 rebuild. A timeout is a FAILED row,
never a slow pass. Same spec+seed => same transcript hash.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from presets import REQUIRED_OUTPUTS, distinctness_key

HARD_ROUND_CAP = 24


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _line(spec: dict[str, Any], role: str, round_i: int, seed: int) -> dict[str, Any]:
    fam = spec["protocol_binding"]["family"]
    material = f"{spec['id']}|{role}|{round_i}|{seed}|{fam}"
    h = int(_digest(material)[:8], 16)
    vote = "aye" if (h % 10) > 2 else "dissent"
    rule = spec["voting"]["rule"]
    if rule.startswith("none") or "no-vote" in rule or "capture-no-vote" in rule:
        vote = "defer"
    if fam == "GENERATIVE" and round_i < spec["budgets"]["max_rounds"] - 1:
        vote = "defer"
    return {
        "role": role,
        "round": round_i,
        "text": f"{role} on {spec['id']} round {round_i}",
        "idea_id": f"idea:{spec['id']}:{role}:r{round_i}:{h % 97}",
        "claim_id": f"claim:{spec['id']}:{role}:r{round_i}",
        "citation": f"cite:{spec['protocol_binding']['protocol_id']}:r{round_i}:{h % 13}",
        "vote": vote,
        "confidence": 40 + (h % 55),
        "dissent": vote == "dissent",
    }


def _should_stop(spec: dict[str, Any], round_i: int, ideas: int) -> bool:
    expr = spec["stopping"]["expression"]
    max_rounds = int(spec["stopping"]["max_rounds"])
    if expr == "NEVER":
        return False
    if round_i >= max_rounds:
        return True
    if "idea_count >=" in expr and ideas >= 8:
        return True
    if "moonshot_candidates" in expr and ideas >= 3:
        return True
    if "explanation_complete" in expr and round_i >= 2:
        return True
    if "oracle_settled" in expr and round_i >= 2:
        return True
    return False


def simulate(spec: dict[str, Any], seed: int = 0) -> dict[str, Any]:
    t0 = time.perf_counter()
    roles = list(spec["roles"])
    max_rounds = int(spec["stopping"]["max_rounds"])
    timed_out = spec["stopping"]["expression"] == "NEVER" or max_rounds > HARD_ROUND_CAP
    bound = HARD_ROUND_CAP if timed_out else min(max_rounds, HARD_ROUND_CAP)

    transcript: list[dict[str, Any]] = []
    ideas: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    votes: list[dict[str, Any]] = []
    confidence: list[dict[str, Any]] = []
    dissent: list[dict[str, Any]] = []
    questions: list[str] = []
    actions: list[str] = []
    rounds_used = 0
    terminal = "TIMEOUT"
    hide = spec["engagement"]["anonymity"] != "none"

    for round_i in range(1, bound + 1):
        rounds_used = round_i
        for idx, role in enumerate(roles):
            shown = f"anon-{idx+1}" if hide and round_i < bound else role
            line = _line(spec, role, round_i, seed)
            transcript.append({"round": round_i, "role": shown, "text": line["text"]})
            ideas.append({"id": line["idea_id"], "role": shown, "round": round_i})
            claims.append({"id": line["claim_id"], "supports": line["idea_id"]})
            evidence.append({"id": line["citation"], "supports": line["claim_id"]})
            votes.append({"round": round_i, "role": shown, "vote": line["vote"]})
            confidence.append({"round": round_i, "role": shown, "confidence": line["confidence"]})
            if line["dissent"]:
                dissent.append({"round": round_i, "role": shown, "reason": line["claim_id"]})
        questions.append(f"unresolved:{spec['id']}:r{round_i}")
        if not timed_out and _should_stop(spec, round_i, len(ideas)):
            terminal = "DONE"
            break
    else:
        if not timed_out:
            terminal = "DONE"

    fam = spec["protocol_binding"]["family"]
    proto = spec["protocol_binding"]["protocol_name"]
    actions.append(f"record-outcome:{spec['id']}:{terminal}")
    if fam == "GENERATIVE":
        actions.append(f"publish-idea-catalog:{len(ideas)}")
    elif fam == "ADVERSARIAL":
        actions.append("publish-attack-and-defense-artifacts")
    elif fam == "JUDICIAL":
        actions.append("publish-claim-rulings")
    elif fam == "FORECASTING":
        actions.append("publish-scored-forecasts")
    else:
        actions.append(f"publish-protocol-artifact:{proto}")

    if not dissent:
        dissent = [{"round": rounds_used, "role": roles[-1], "reason": "named-dissent-slot"}]

    outputs = {
        "transcript": transcript,
        "idea_catalog": ideas,
        "argument_graph": {
            "nodes": claims,
            "edges": [{"src": e["supports"], "dst": e["id"]} for e in evidence],
        },
        "evidence_map": evidence,
        "vote_history": votes,
        "confidence_evolution": confidence,
        "dissent": dissent,
        "unresolved_questions": questions,
        "action_plan": actions,
    }
    missing = [k for k in REQUIRED_OUTPUTS if not outputs.get(k)]
    present = {k: bool(outputs.get(k)) for k in REQUIRED_OUTPUTS}
    row_result = "FAILED" if terminal == "TIMEOUT" else "PASS"
    body = {
        "preset_id": spec["id"],
        "preset_name": spec["name"],
        "protocol_id": spec["protocol_binding"]["protocol_id"],
        "protocol_name": spec["protocol_binding"]["protocol_name"],
        "family": spec["protocol_binding"]["family"],
        "named_at_11200_11225": spec["meta"]["named_at_11200_11225"],
        "terminal_state": terminal,
        "terminal_reason": "timeout" if terminal == "TIMEOUT" else "stopping-expression-or-max-rounds",
        "row_result": row_result,
        "rounds_used": rounds_used,
        "max_rounds": max_rounds,
        "wall_clock_ms": round((time.perf_counter() - t0) * 1000, 3),
        "distinctness_key": list(distinctness_key(spec)),
        "outputs_present": present,
        "outputs_missing": missing,
        "transcript_sha256": _digest(_canon(transcript)),
        "outputs": outputs,
    }
    stable = {k: v for k, v in body.items() if k != "wall_clock_ms"}
    body["run_sha256"] = _digest(_canon(stable))
    return body


def completeness_ok(run: dict[str, Any]) -> bool:
    return (
        run["terminal_state"] == "DONE"
        and not run["outputs_missing"]
        and all(run["outputs_present"].values())
    )
