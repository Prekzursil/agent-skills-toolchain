"""CNL-0091 role-collapse detector.

Two mechanically independent signals, combined as mean L1:

  d_act  — L1/2 distance between speech-act class histograms
           (propose / critique / steelman / condition). Bag counts.
  d_sig  — |skew_proposer - skew_critic| on a disjoint role-lexicon
           (implementation-plan markers vs failure-mode markers).

Fire when d_combined = (d_act + d_sig) / 2 is strictly below the
pre-registered collapse gate. Stance/conclusion Jaccard is computed
as a foil and is NEVER consulted for the fire decision: genuine
agreement and role collapse both have low stance distance.

A seat label ("Role: critic") is stripped and ignored.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures.json"

# Pre-registered. Do not retune after seeing fixture distances; fix fixtures.
COLLAPSE_GATE = 0.35

PROPOSE_PHRASES = (
    "i propose",
    "the solution is",
    "recommend that we",
    "ship this design",
)
CRITIQUE_PHRASES = (
    "this fails when",
    "objection:",
    "counterexample:",
    "does not hold",
)
STEELMAN_PHRASES = (
    "steelman:",
    "at its strongest",
    "even granting",
)
CONDITION_PHRASES = (
    "residual risk",
    "conditional on",
    "agree only if",
    "i agree that the conclusion holds",
)
ACT_CLASSES = (
    ("propose", PROPOSE_PHRASES),
    ("critique", CRITIQUE_PHRASES),
    ("steelman", STEELMAN_PHRASES),
    ("condition", CONDITION_PHRASES),
)

# Disjoint from ACT phrase lists: different tokens, different aggregation.
PROPOSER_VOCAB = (
    "implementation plan",
    "primary design",
    "land the change",
    "rollout sequence",
)
CRITIC_VOCAB = (
    "failure mode",
    "burden of proof",
    "falsify",
    "attack surface",
)

LABEL_RE = re.compile(r"^\s*(role|seat|name|participant)\s*:", re.I)
TOKEN_RE = re.compile(r"[a-z0-9]+")


def strip_labels(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not LABEL_RE.match(ln)]
    return "\n".join(lines)


def _count_phrases(text: str, phrases: tuple[str, ...]) -> int:
    t = text.lower()
    return sum(t.count(p) for p in phrases)


def act_histogram(text: str) -> dict[str, float]:
    body = strip_labels(text)
    raw = {name: float(_count_phrases(body, phrases)) for name, phrases in ACT_CLASSES}
    total = sum(raw.values())
    if total <= 0:
        return {name: 0.0 for name, _ in ACT_CLASSES}
    return {k: v / total for k, v in raw.items()}


def l1_half(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)


def vocab_skew(text: str) -> float:
    """0 = proposer-only lexicon, 1 = critic-only lexicon."""
    body = strip_labels(text)
    p = float(_count_phrases(body, PROPOSER_VOCAB))
    c = float(_count_phrases(body, CRITIC_VOCAB))
    denom = p + c
    if denom <= 0:
        return 0.5
    return c / denom


def conclusion_tokens(text: str) -> set[str]:
    for ln in strip_labels(text).lower().splitlines():
        s = ln.strip()
        if s.startswith("conclusion:"):
            return set(TOKEN_RE.findall(s.split(":", 1)[1]))
    return set()


def jaccard_distance(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return 1.0 - (inter / union)


def first_act(text: str) -> str | None:
    """Order-based classifier: earliest matching speech-act phrase. Not a bag."""
    body = strip_labels(text).lower()
    best: str | None = None
    best_pos = 10**9
    for name, phrases in ACT_CLASSES:
        for p in phrases:
            i = body.find(p)
            if 0 <= i < best_pos:
                best_pos = i
                best = name
    return best


def recover_role(text: str) -> str:
    act = first_act(text)
    if act in {"critique", "steelman", "condition"}:
        return "critic"
    return "proposer"


def measure_pair(proposer_text: str, critic_text: str) -> dict[str, Any]:
    hist_p = act_histogram(proposer_text)
    hist_c = act_histogram(critic_text)
    d_act = l1_half(hist_p, hist_c)
    skew_p = vocab_skew(proposer_text)
    skew_c = vocab_skew(critic_text)
    d_sig = abs(skew_p - skew_c)
    d_combined = (d_act + d_sig) / 2.0
    d_stance = jaccard_distance(
        conclusion_tokens(proposer_text), conclusion_tokens(critic_text)
    )
    return {
        "d_act": round(d_act, 6),
        "d_sig": round(d_sig, 6),
        "d_combined": round(d_combined, 6),
        "d_stance": round(d_stance, 6),
        "hist_proposer": hist_p,
        "hist_critic": hist_c,
        "skew_proposer": round(skew_p, 6),
        "skew_critic": round(skew_c, 6),
        "first_act_proposer": first_act(proposer_text),
        "first_act_critic": first_act(critic_text),
        "role_guess_proposer": recover_role(proposer_text),
        "role_guess_critic": recover_role(critic_text),
        "fired": bool(d_combined < COLLAPSE_GATE),
        "gate": COLLAPSE_GATE,
    }


def load_fixtures(path: Path | None = None) -> dict[str, Any]:
    raw = json.loads((path or FIXTURES).read_text(encoding="utf-8"))
    return raw


def pair_from_fixture(fix: dict[str, Any]) -> tuple[str, str]:
    seats = {s["role"]: s["text"] for s in fix["seats"]}
    return seats["proposer"], seats["critic"]


def score_fixture(fix: dict[str, Any]) -> dict[str, Any]:
    p, c = pair_from_fixture(fix)
    m = measure_pair(p, c)
    m["id"] = fix["id"]
    m["kind"] = fix["kind"]
    m["expect_fire"] = bool(fix["expect_fire"])
    return m


def score_all(path: Path | None = None) -> list[dict[str, Any]]:
    doc = load_fixtures(path)
    return [score_fixture(f) for f in doc["fixtures"]]
