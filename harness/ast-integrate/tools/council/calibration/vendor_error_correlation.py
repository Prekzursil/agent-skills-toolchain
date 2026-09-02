"""Vendor error correlation: do two vendor nameplates buy two independent seats?

A council seat only adds information when its errors are not the same errors another seat
already makes.  This module runs a deterministic, hermetic experiment over ``N_ITEMS`` scored
items spanning several domains and compares three pairings:

* **independent pair** - Claude run 1 versus a Codex arm that answered the identical prompt
  from its own latent competence;
* **cloned pair** - Claude run 1 versus a Codex arm that was fed Claude's answer and mostly
  copies it (the "expensive duplication" a naive nominal count cannot see);
* **same-vendor baseline** - Claude run 1 versus Claude run 2, the noise floor of a vendor
  disagreeing with itself.

For each pair the 2x2 joint error table, the phi coefficient and the effective number of seats
(``2 / (1 + rho)``) are computed in the plain count form so a reviewer can recompute them by
hand.  Prompt parity (both arms saw byte-identical prompts) is checked from prompt digests, with
a planted negative control whose prompts differ.  ``naive_nominal_seats`` is the baseline the
experiment exists to reject: it counts vendor names and ignores the joint table.
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any, Sequence

N_ITEMS = 120
DOMAINS: tuple[str, ...] = (
    "arithmetic",
    "code-review",
    "legal-citation",
    "unit-conversion",
    "date-reasoning",
)
NOMINAL_SEATS = 2
CLONE_COPY_RATE = 0.88
SAME_VENDOR_NOISE = 0.12
SEATS_COLLAPSE_BELOW = 1.30
SEATS_DIVERSITY_AT_LEAST = 1.50

Row = dict[str, Any]


# --------------------------------------------------------------------------- items and arms


def _prompt_digest(item_id: str, domain: str, hint: str = "") -> str:
    return hashlib.sha256(f"{domain}|{item_id}|{hint}".encode("utf-8")).hexdigest()[:16]


def build_items(seed: int, n_items: int = N_ITEMS) -> list[Row]:
    """Deterministic item bank: id, domain, difficulty in [0, 1] and a vendor-latent trap score."""
    if n_items <= 0:
        raise ValueError("n_items must be positive")
    rng = random.Random(seed)
    items: list[Row] = []
    for i in range(n_items):
        domain = DOMAINS[i % len(DOMAINS)]
        items.append(
            {
                "item_id": f"item-{i:03d}",
                "domain": domain,
                "difficulty": round(rng.random(), 4),
                # Latent per-vendor weakness on this item (fixed per item, sampled per vendor).
                "claude_latent": rng.random(),
                "codex_latent": rng.random(),
                "prompt_sha": _prompt_digest(f"item-{i:03d}", domain),
            }
        )
    return items


def _error_probability(difficulty: float) -> float:
    return 0.12 + 0.55 * difficulty


def _row(item: Row, arm: str, vendor: str, wrong: bool, prompt_sha: str, derived_from: str | None) -> Row:
    answer = f"{item['item_id']}:{'wrong' if wrong else 'right'}:{arm}"
    return {
        "item_id": item["item_id"],
        "domain": item["domain"],
        "arm": arm,
        "vendor": vendor,
        "wrong": bool(wrong),
        "correct": not wrong,
        "prompt_sha": prompt_sha,
        "derived_from": derived_from,
        "answer_tokens": max(1, len(answer) // 4),
    }


def simulate_arms(items: Sequence[Row], seed: int) -> dict[str, list[Row]]:
    """Score four arms over the same items.

    ``claude_r1`` / ``claude_r2`` share the Claude latent (same vendor, fresh sampling noise);
    ``codex_independent`` uses the Codex latent; ``codex_clone`` copies Claude run 1's answer
    with probability ``CLONE_COPY_RATE`` and otherwise answers from the Codex latent.
    ``codex_hinted`` is the prompt-parity negative control: it saw a different prompt.
    """
    rng = random.Random(seed * 7919 + 17)
    arms: dict[str, list[Row]] = {k: [] for k in ("claude_r1", "claude_r2", "codex_independent", "codex_clone", "codex_hinted")}
    for item in items:
        p_err = _error_probability(item["difficulty"])
        claude_1 = (item["claude_latent"] + rng.uniform(-SAME_VENDOR_NOISE, SAME_VENDOR_NOISE)) < p_err
        claude_2 = (item["claude_latent"] + rng.uniform(-SAME_VENDOR_NOISE, SAME_VENDOR_NOISE)) < p_err
        codex_own = (item["codex_latent"] + rng.uniform(-SAME_VENDOR_NOISE, SAME_VENDOR_NOISE)) < p_err
        copies = rng.random() < CLONE_COPY_RATE
        clone = claude_1 if copies else codex_own
        sha = item["prompt_sha"]
        arms["claude_r1"].append(_row(item, "claude_r1", "claude", claude_1, sha, None))
        arms["claude_r2"].append(_row(item, "claude_r2", "claude", claude_2, sha, None))
        arms["codex_independent"].append(_row(item, "codex_independent", "codex", codex_own, sha, None))
        arms["codex_clone"].append(
            _row(item, "codex_clone", "codex", clone, sha, "claude_r1" if copies else None)
        )
        hinted_sha = _prompt_digest(item["item_id"], item["domain"], hint="claude-answer-appended")
        arms["codex_hinted"].append(_row(item, "codex_hinted", "codex", clone, hinted_sha, "claude_r1"))
    return arms


# --------------------------------------------------------------------------- statistics


def errors_of(rows: Sequence[Row]) -> list[bool]:
    """Error vector (True = wrong) of one arm, in item order."""
    return [bool(row["wrong"]) for row in rows]


def joint_error_table(errors_a: Sequence[bool], errors_b: Sequence[bool]) -> dict[str, Any]:
    """2x2 table of the two error vectors plus the conditional error rates."""
    if len(errors_a) != len(errors_b):
        raise ValueError("error vectors must be the same length")
    both_wrong = a_only = b_only = both_right = 0
    for a, b in zip(errors_a, errors_b):
        if a and b:
            both_wrong += 1
        elif a:
            a_only += 1
        elif b:
            b_only += 1
        else:
            both_right += 1
    n = len(errors_a)
    a_wrong = both_wrong + a_only
    a_right = b_only + both_right
    return {
        "n": n,
        "both_wrong": both_wrong,
        "a_wrong_only": a_only,
        "b_wrong_only": b_only,
        "both_right": both_right,
        "p_a_wrong": (a_wrong / n) if n else None,
        "p_b_wrong": ((both_wrong + b_only) / n) if n else None,
        "p_b_wrong_given_a_wrong": (both_wrong / a_wrong) if a_wrong else None,
        "p_b_wrong_given_a_right": (b_only / a_right) if a_right else None,
    }


def phi_from_table(table: dict[str, Any]) -> float | None:
    """Phi coefficient in count form: (bb*rr - br*rb) / sqrt(n1*n0*m1*m0); None when degenerate."""
    n_bb = table["both_wrong"]
    n_br = table["a_wrong_only"]
    n_rb = table["b_wrong_only"]
    n_rr = table["both_right"]
    n1 = n_bb + n_br
    n0 = n_rb + n_rr
    m1 = n_bb + n_rb
    m0 = n_br + n_rr
    den = math.sqrt(n1 * n0 * m1 * m0)
    if den == 0:
        return None
    return ((n_bb * n_rr) - (n_br * n_rb)) / den


def phi(errors_a: Sequence[bool], errors_b: Sequence[bool]) -> float | None:
    return phi_from_table(joint_error_table(errors_a, errors_b))


def effective_seats(phi_value: float | None, nominal: int = NOMINAL_SEATS) -> dict[str, Any]:
    """Effective independent seats for a pair: ``2 / (1 + rho)`` with rho the clamped phi."""
    if phi_value is None:
        return {"nominal": nominal, "phi": None, "rho": None, "effective_seats": None}
    rho = max(-0.999999, min(0.999999, phi_value))
    return {"nominal": nominal, "phi": phi_value, "rho": rho, "effective_seats": 2.0 / (1.0 + rho)}


def prompt_parity(rows_a: Sequence[Row], rows_b: Sequence[Row]) -> dict[str, Any]:
    """Both arms must have seen byte-identical prompts item by item."""
    mismatches = [
        a["item_id"]
        for a, b in zip(rows_a, rows_b)
        if a["item_id"] != b["item_id"] or a["prompt_sha"] != b["prompt_sha"]
    ]
    if len(rows_a) != len(rows_b):
        mismatches.append(f"length {len(rows_a)} != {len(rows_b)}")
    return {"ok": not mismatches, "mismatches": mismatches, "checked": min(len(rows_a), len(rows_b))}


def token_spend(rows_a: Sequence[Row], rows_b: Sequence[Row]) -> dict[str, int]:
    a = sum(int(r["answer_tokens"]) for r in rows_a)
    b = sum(int(r["answer_tokens"]) for r in rows_b)
    return {"arm_a": a, "arm_b": b, "total": a + b}


def summarize_pair(rows_a: Sequence[Row], rows_b: Sequence[Row], label: str) -> dict[str, Any]:
    """Joint table, phi, effective seats, prompt parity and token spend for one pair of arms."""
    ea, eb = errors_of(rows_a), errors_of(rows_b)
    table = joint_error_table(ea, eb)
    phi_value = phi_from_table(table)
    return {
        "label": label,
        "arms": [rows_a[0]["arm"] if rows_a else None, rows_b[0]["arm"] if rows_b else None],
        "vendors": sorted({r["vendor"] for r in (*rows_a, *rows_b)}),
        "joint_error_table": table,
        "phi": phi_value,
        "effective_seats": effective_seats(phi_value),
        "prompt_parity": prompt_parity(rows_a, rows_b),
        "token_spend": token_spend(rows_a, rows_b),
    }


def naive_nominal_seats(rows_a: Sequence[Row], rows_b: Sequence[Row]) -> dict[str, Any]:
    """The baseline to reject: count distinct vendor nameplates, ignore the joint error table."""
    vendors = sorted({r["vendor"] for r in (*rows_a, *rows_b)})
    return {
        "nominal": len(vendors),
        "vendors": vendors,
        "phi": None,
        "effective_seats": float(len(vendors)),
        "ignored_joint_table": True,
        "claim": "two vendor names therefore two independent seats",
    }


def _hand_table(errors_a: Sequence[bool], errors_b: Sequence[bool]) -> dict[str, Any]:
    """Independent recomputation of the table via a different code path (set arithmetic)."""
    wrong_a = {i for i, e in enumerate(errors_a) if e}
    wrong_b = {i for i, e in enumerate(errors_b) if e}
    n = len(errors_a)
    both = len(wrong_a & wrong_b)
    a_only = len(wrong_a - wrong_b)
    b_only = len(wrong_b - wrong_a)
    table = {
        "both_wrong": both,
        "a_wrong_only": a_only,
        "b_wrong_only": b_only,
        "both_right": n - both - a_only - b_only,
    }
    return {"table": table, "phi": phi_from_table(table)}


# --------------------------------------------------------------------------- the experiment


def run_independence_experiment(seed: int = 292, n_items: int = N_ITEMS) -> dict[str, Any]:
    """Run the full experiment deterministically for ``seed`` and return every table and finding."""
    items = build_items(seed, n_items)
    arms = simulate_arms(items, seed)
    independent = summarize_pair(arms["claude_r1"], arms["codex_independent"], "claude-r1 vs codex-independent")
    cloned = summarize_pair(arms["claude_r1"], arms["codex_clone"], "claude-r1 vs codex-clone")
    same_vendor = summarize_pair(arms["claude_r1"], arms["claude_r2"], "claude-r1 vs claude-r2")
    parity_negative = summarize_pair(arms["claude_r1"], arms["codex_hinted"], "claude-r1 vs codex-hinted (parity negative)")

    ea = errors_of(arms["claude_r1"])
    hand_independent = _hand_table(ea, errors_of(arms["codex_independent"]))
    hand_cloned = _hand_table(ea, errors_of(arms["codex_clone"]))
    hand_tables_match = (
        hand_independent["table"] == {k: independent["joint_error_table"][k] for k in hand_independent["table"]}
        and hand_cloned["table"] == {k: cloned["joint_error_table"][k] for k in hand_cloned["table"]}
        and hand_independent["phi"] == independent["phi"]
        and hand_cloned["phi"] == cloned["phi"]
    )
    seats_indep = independent["effective_seats"]["effective_seats"]
    seats_clone = cloned["effective_seats"]["effective_seats"]
    findings = {
        "hand_tables_match": hand_tables_match,
        "independent_is_real_diversity": seats_indep is not None and seats_indep >= SEATS_DIVERSITY_AT_LEAST,
        "cloned_is_expensive_duplication": seats_clone is not None and seats_clone < SEATS_COLLAPSE_BELOW,
        "cloned_tracks_same_vendor_floor": (
            cloned["phi"] is not None
            and same_vendor["phi"] is not None
            and abs(cloned["phi"] - same_vendor["phi"]) < 0.20
        ),
        "prompt_parity_negative_fired": not parity_negative["prompt_parity"]["ok"],
        "naive_nominal_overclaims": naive_nominal_seats(arms["claude_r1"], arms["codex_clone"])["effective_seats"]
        > (seats_clone or 0.0),
    }
    return {
        "seed": seed,
        "n_items": len(items),
        "domains": list(DOMAINS),
        "items_per_domain": {d: sum(1 for it in items if it["domain"] == d) for d in DOMAINS},
        "rows": arms,
        "independent_pair": independent,
        "cloned_pair": cloned,
        "same_vendor_baseline": same_vendor,
        "prompt_parity_negative": parity_negative,
        "hand_computed": {"independent": hand_independent, "cloned": hand_cloned},
        "naive_nominal": naive_nominal_seats(arms["claude_r1"], arms["codex_clone"]),
        "findings": findings,
        "live_substrate": {
            "live_arm": "deterministic-simulation",
            "network": False,
            "seed": seed,
            "clone_copy_rate": CLONE_COPY_RATE,
        },
    }


__all__ = [
    "DOMAINS",
    "N_ITEMS",
    "NOMINAL_SEATS",
    "build_items",
    "effective_seats",
    "errors_of",
    "joint_error_table",
    "naive_nominal_seats",
    "phi",
    "phi_from_table",
    "prompt_parity",
    "run_independence_experiment",
    "simulate_arms",
    "summarize_pair",
]
