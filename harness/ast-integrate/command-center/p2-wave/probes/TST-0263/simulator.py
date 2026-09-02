"""Scripted six-protocol council casts for TST-0263.

tools/council/simulate.py (TST-0257) is absent on this worktree. This harness
emits structured claim/evidence/vote rounds for the six ANONYMOUS protocols
named by CNL-0041 (P20-P25). It does not call live models and does not read
time.time or os.getpid into the transcript.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.gain import (  # noqa: E402
    GAIN_FLOOR,
    METRIC_KIND,
    SAFETY_CAP,
    STOP_PATIENCE,
    bootstrap_mean_diff_ci,
    cohens_d,
    evaluate_stop,
    evaluate_stop_lexical,
    mean,
    round_gain_crosses_floor,
    score_transcript,
    strip_scores,
)

SEED = 263
HORIZON = 10
CLOCK_NS = 1_700_000_000_000_000_000
PID = 263
SEATS = ("proposer", "critic", "judge")

PROTOCOLS: list[dict[str, Any]] = [
    {
        "id": "P20",
        "slug": "delphi-anonymous-rounds",
        "ideas_per_speaker": 1,
        "productive_vote_rotate": False,
    },
    {
        "id": "P21",
        "slug": "wideband-delphi-estimation",
        "ideas_per_speaker": 1,
        "productive_vote_rotate": True,
    },
    {
        "id": "P22",
        "slug": "brainwriting-635",
        "ideas_per_speaker": 2,
        "productive_vote_rotate": False,
    },
    {
        "id": "P23",
        "slug": "silent-start-pooling",
        "ideas_per_speaker": 1,
        "productive_vote_rotate": False,
    },
    {
        "id": "P24",
        "slug": "surprisingly-popular-bts",
        "ideas_per_speaker": 1,
        "productive_vote_rotate": True,
    },
    {
        "id": "P25",
        "slug": "blind-reevaluation",
        "ideas_per_speaker": 1,
        "productive_vote_rotate": True,
    },
]


def _mix(seed: int, protocol_id: str, round_no: int) -> str:
    return hashlib.sha256(
        f"{seed}|{protocol_id}|{round_no}".encode("utf-8")
    ).hexdigest()[:8]


def novel_round(
    protocol: dict[str, Any],
    round_no: int,
    *,
    seed: int = SEED,
    rotate_votes: bool = False,
) -> dict[str, Any]:
    mix = _mix(seed, protocol["id"], round_no)
    claims: list[dict[str, str]] = []
    evidence: list[dict[str, str]] = []
    texts: list[str] = []
    n_ideas = int(protocol["ideas_per_speaker"])
    for seat in SEATS:
        for slot in range(n_ideas):
            cid = f"{protocol['id']}:{seat}:c:r{round_no}:s{slot}"
            eid = f"{protocol['id']}:{seat}:e:r{round_no}:s{slot}"
            text = (
                f"{protocol['slug']} {seat} round {round_no} slot {slot} "
                f"counterexample cx-{protocol['id']}-{round_no}-{slot} mix={mix}"
            )
            claims.append({"id": cid, "text": text, "seat": seat})
            evidence.append(
                {
                    "id": eid,
                    "claim_id": cid,
                    "text": f"evidence for {cid} mix={mix}",
                }
            )
            texts.append(text)
    votes = {"proposer": "advance", "critic": "hold", "judge": "revise"}
    if rotate_votes:
        cycle = ("advance", "hold", "revise")
        votes["critic"] = cycle[(round_no - 1) % 3]
        votes["judge"] = cycle[round_no % 3]
    return {
        "round": round_no,
        "protocol_id": protocol["id"],
        "claims": claims,
        "evidence": evidence,
        "votes": votes,
        "texts": texts,
    }


def paraphrase_round(base: dict[str, Any], round_no: int) -> dict[str, Any]:
    rnd = copy.deepcopy(base)
    rnd["round"] = round_no
    marker = f"nonceword{round_no}qxyz"
    texts: list[str] = []
    for c in rnd["claims"]:
        c["text"] = f"paraphrase {marker} of {c['id']} using novel wording"
        texts.append(c["text"])
    for e in rnd["evidence"]:
        e["text"] = f"paraphrase-evidence {marker} of {e['id']}"
        texts.append(e["text"])
    rnd["texts"] = texts
    return rnd


def simulate(
    protocol: dict[str, Any],
    cast: str,
    *,
    seed: int = SEED,
    horizon: int = HORIZON,
) -> dict[str, Any]:
    rounds: list[dict[str, Any]] = []
    last_novel: dict[str, Any] | None = None
    for r in range(1, horizon + 1):
        if cast == "productive":
            rnd = novel_round(
                protocol,
                r,
                seed=seed,
                rotate_votes=bool(protocol["productive_vote_rotate"]),
            )
            last_novel = rnd
        elif r <= 2:
            rnd = novel_round(protocol, r, seed=seed, rotate_votes=False)
            if r == 2:
                rnd["votes"] = {
                    "proposer": "advance",
                    "critic": "revise",
                    "judge": "hold",
                }
            last_novel = rnd
        elif cast == "looping":
            assert last_novel is not None
            rnd = copy.deepcopy(last_novel)
            rnd["round"] = r
        elif cast == "paraphrase":
            assert last_novel is not None
            rnd = paraphrase_round(last_novel, r)
        else:
            raise ValueError(cast)
        rnd["cast"] = cast
        rnd["protocol_id"] = protocol["id"]
        rounds.append(rnd)
    scored = score_transcript(rounds)
    stop = evaluate_stop(scored)
    lex_stop = evaluate_stop_lexical(scored)
    crossing = round_gain_crosses_floor(scored)
    curve = [
        {
            "round": int(row["round"]),
            "gain": float(row["gain"]),
            "new_claim_count": int(row["new_claim_count"]),
            "new_evidence_count": int(row["new_evidence_count"]),
            "changed_votes": int(row["changed_votes"]),
            "entropy_shift": float(row["entropy_shift"]),
            "lexical_new_token_types": float(row["lexical_new_token_types"]),
            "below_floor": bool(row["below_floor"]),
        }
        for row in scored
    ]
    return {
        "protocol_id": protocol["id"],
        "slug": protocol["slug"],
        "cast": cast,
        "seed": seed,
        "horizon": horizon,
        "metric_kind": METRIC_KIND,
        "floor": GAIN_FLOOR,
        "rounds": scored,
        "curve": curve,
        "stop": stop,
        "lexical_stop": lex_stop,
        "gain_crosses_floor": crossing,
    }


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def digest_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def transcript_payload(result: dict[str, Any]) -> list[dict[str, Any]]:
    return strip_scores(result["rounds"])


def simulate_all(
    *,
    seed: int = SEED,
    horizon: int = HORIZON,
    casts: tuple[str, ...] = ("looping", "productive", "paraphrase"),
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for proto in PROTOCOLS:
        for cast in casts:
            runs.append(simulate(proto, cast, seed=seed, horizon=horizon))
    return {"seed": seed, "horizon": horizon, "runs": runs}


def post_collapse_gains(result: dict[str, Any], start_round: int = 3) -> list[float]:
    return [float(row["gain"]) for row in result["curve"] if int(row["round"]) >= start_round]


def statistics(bundle: dict[str, Any], *, rng_seed: int = SEED) -> dict[str, Any]:
    productive: list[float] = []
    looping: list[float] = []
    by_protocol: dict[str, Any] = {}
    for run in bundle["runs"]:
        pid = run["protocol_id"]
        by_protocol.setdefault(pid, {})
        gains = post_collapse_gains(run)
        by_protocol[pid][run["cast"]] = {
            "gains_from_round_3": gains,
            "mean_from_round_3": mean(gains),
            "curve": run["curve"],
            "stop": run["stop"],
            "gain_crosses_floor": run["gain_crosses_floor"],
        }
        if run["cast"] == "productive":
            productive.extend(gains)
        elif run["cast"] == "looping":
            looping.extend(gains)
    rng = random.Random(rng_seed)
    d = cohens_d(productive, looping)
    lo, hi = bootstrap_mean_diff_ci(productive, looping, rng)
    diff = mean(productive) - mean(looping)
    return {
        "window": "rounds 3..horizon inclusive, six protocols",
        "n_productive": len(productive),
        "n_looping": len(looping),
        "productive_gains": productive,
        "looping_gains": looping,
        "mean_productive": mean(productive),
        "mean_looping": mean(looping),
        "mean_difference": diff,
        "cohens_d": d,
        "bootstrap_n": 2000,
        "bootstrap_alpha": 0.05,
        "bootstrap_ci95_mean_difference": [lo, hi],
        "ci_excludes_zero": lo > 0.0 or hi < 0.0,
        "by_protocol": by_protocol,
        "rng_seed": rng_seed,
    }


def determinism_check(*, seed: int = SEED) -> dict[str, Any]:
    a = simulate_all(seed=seed)
    b = simulate_all(seed=seed)
    other = simulate_all(seed=seed ^ 0xA5)
    payload_a = [transcript_payload(r) for r in a["runs"]]
    payload_b = [transcript_payload(r) for r in b["runs"]]
    payload_o = [transcript_payload(r) for r in other["runs"]]
    ha, hb, ho = digest_obj(payload_a), digest_obj(payload_b), digest_obj(payload_o)
    clock_a = digest_obj({"clock_ns": CLOCK_NS, "events": payload_a})
    clock_b = digest_obj({"clock_ns": CLOCK_NS + 1, "events": payload_a})
    return {
        "seed": seed,
        "run_a_sha256": ha,
        "run_b_sha256": hb,
        "identical": ha == hb,
        "other_seed_sha256": ho,
        "other_seed_diverges": ho != ha,
        "clock_metadata_not_in_event_hash": True,
        "clock_wrapper_changes": clock_a != clock_b,
        "pid": PID,
        "clock_ns": CLOCK_NS,
    }


def node_order(bundle: dict[str, Any]) -> list[str]:
    nodes: list[str] = []
    for run in bundle["runs"]:
        if run["cast"] != "looping":
            continue
        for row in run["curve"]:
            nodes.append(f"{run['protocol_id']}:r{row['round']}")
    return nodes


def fan_out_cardinalities() -> list[dict[str, Any]]:
    rows = []
    for p in PROTOCOLS:
        rows.append(
            {
                "id": p["id"],
                "kind": "speakers",
                "cardinality": len(SEATS) * int(p["ideas_per_speaker"]),
            }
        )
    return rows


def barrier_resolution(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for run in bundle["runs"]:
        if run["cast"] != "looping":
            continue
        stop = run["stop"]
        rows.append(
            {
                "id": f"{run['protocol_id']}-gain-stop",
                "kind": "information_gain_stop",
                "resolved": bool(stop.get("fired")),
                "stop_round": stop.get("stop_round"),
                "collapse_round": stop.get("collapse_round"),
            }
        )
    return rows


def measure() -> dict[str, Any]:
    bundle = simulate_all()
    stats = statistics(bundle)
    det = determinism_check()
    looping_ok = True
    productive_ok = True
    paraphrase_rows: list[dict[str, Any]] = []
    for run in bundle["runs"]:
        stop = run["stop"]
        if run["cast"] == "looping":
            delta = stop.get("delta_from_collapse")
            if not (
                stop.get("fired")
                and stop.get("reason") == "information_gain"
                and stop.get("within_patience")
                and delta is not None
                and int(delta) <= int(STOP_PATIENCE)
                and stop.get("hardcoded_round_cap") is False
            ):
                looping_ok = False
        elif run["cast"] == "productive":
            if stop.get("fired") or stop.get("reason") == "information_gain":
                productive_ok = False
            if any(float(row["gain"]) <= GAIN_FLOOR for row in run["curve"]):
                productive_ok = False
        elif run["cast"] == "paraphrase":
            rest = [row for row in run["curve"] if int(row["round"]) >= 3]
            structured = [float(row["gain"]) for row in rest]
            lexical = [float(row["lexical_new_token_types"]) for row in rest]
            paraphrase_rows.append(
                {
                    "protocol_id": run["protocol_id"],
                    "structured_gains": structured,
                    "lexical_new_token_types": lexical,
                    "structured_mean": mean(structured),
                    "lexical_mean": mean(lexical),
                    "structured_stop_fired": bool(run["stop"].get("fired")),
                    "lexical_stop_fired": bool(run["lexical_stop"].get("fired")),
                }
            )
    return {
        "bundle": bundle,
        "stats": stats,
        "determinism": det,
        "looping_ok": looping_ok,
        "productive_ok": productive_ok,
        "paraphrase_rows": paraphrase_rows,
        "paraphrase_structured_near_zero": all(
            row["structured_mean"] <= GAIN_FLOOR + 1e-12 for row in paraphrase_rows
        ),
        "paraphrase_lexical_positive": all(
            row["lexical_mean"] > 0.0 for row in paraphrase_rows
        ),
        "lexical_would_not_stop": all(
            not row["lexical_stop_fired"] for row in paraphrase_rows
        ),
        "structured_does_stop": all(
            row["structured_stop_fired"] for row in paraphrase_rows
        ),
        "metric_is_lexical": False,
        "metric_kind": METRIC_KIND,
        "node_order": node_order(bundle),
        "fan_out_cardinalities": fan_out_cardinalities(),
        "barrier_resolution": barrier_resolution(bundle),
        "simulate_py_present": (REPO / "tools" / "council" / "simulate.py").is_file(),
        "user_prompts_present": (REPO / "_USER-PROMPTS.md").is_file(),
        "clock_ns": CLOCK_NS,
        "pid": PID,
        "safety_cap": SAFETY_CAP,
        "horizon": HORIZON,
        "floor": GAIN_FLOOR,
        "patience": STOP_PATIENCE,
    }
