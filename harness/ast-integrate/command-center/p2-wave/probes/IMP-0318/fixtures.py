"""Deterministic council snapshots for IMP-0318 probes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

PLANTED_WRONG_N = 12
CORRECT_INSTANT_N = 8
RATE_CORPUS_N = PLANTED_WRONG_N + CORRECT_INSTANT_N

_PLANTED_TOPICS = [
    ("cache", "Ship cache without invalidation?", "ship-cache", "hold-cache"),
    ("secrets", "Persist decrypted secrets in council artifacts?", "persist-secrets", "redact-secrets"),
    ("egress", "Allow unrestricted network egress for tool calls?", "open-egress", "allowlist-egress"),
    ("quorum", "Count silent seats as consenting?", "silence-consent", "silence-absent"),
    ("seed", "Omit the sampling seed from the run artifact?", "omit-seed", "record-seed"),
    ("critic", "Skip recruiting a critic after instant agreement?", "skip-critic", "recruit-critic"),
    ("schema", "Accept schema-invalid ballots as zero?", "zero-invalid", "reject-invalid"),
    ("resume", "Resume a severed stream without a checksum?", "resume-blind", "resume-checked"),
    ("weights", "Let the chair silently reweight late ballots?", "reweight-chair", "freeze-weights"),
    ("partition", "Share partition-private canaries in the transcript?", "share-canary", "hold-canary"),
    ("timeout", "Treat hung adapters as successful abstentions?", "timeout-yes", "timeout-abort"),
    ("logs", "Drop dissent tokens from the persisted transcript?", "drop-dissent", "keep-dissent"),
]

_CORRECT_TOPICS = [
    ("rollback", "Require a rollback plan before the cutover?", "skip-rollback", "require-rollback"),
    ("review", "Require an independent reviewer on the anti-fail module?", "skip-review", "require-review"),
    ("meter", "Publish the outcome-change rate instead of assuming it?", "assume-rate", "publish-rate"),
    ("briefs", "Require independent first-round briefs before unanimity stands?", "skip-briefs", "require-briefs"),
    ("redact", "Redact credentials before persistence?", "keep-creds", "redact-creds"),
    ("seed2", "Record the roster seed in the artifact?", "hide-seed", "show-seed"),
    ("quota", "Cap a single seat's share of surviving claims?", "uncapped", "capped"),
    ("stop", "Evaluate the stopping expression instead of a hidden timer?", "hidden-timer", "eval-stop"),
]


def load_json(name: str) -> dict[str, Any]:
    path = FIX / name
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_planted_wrong() -> dict[str, Any]:
    return load_json("planted-wrong-consensus.json")


def canonical_correct_instant() -> dict[str, Any]:
    return load_json("correct-instant.json")


def canonical_late_legitimate() -> dict[str, Any]:
    return load_json("late-legitimate.json")


def canonical_contested() -> dict[str, Any]:
    return load_json("contested.json")


def _seats() -> list[dict[str, str]]:
    return [
        {"id": "architect", "role": "advocate"},
        {"id": "pragmatist", "role": "chair"},
        {"id": "critic", "role": "critic"},
        {"id": "scribe", "role": "scribe"},
    ]


def _copied_briefs(text: str) -> list[dict[str, Any]]:
    return [
        {
            "participant_id": p["id"],
            "text": text,
            "evidence_ids": [],
            "independent": False,
        }
        for p in _seats()
    ]


def _unanimous_votes(claim_id: str) -> list[dict[str, Any]]:
    conf = [0.95, 0.94, 0.93, 0.92]
    return [
        {
            "participant_id": p["id"],
            "claim_id": claim_id,
            "round": 1,
            "confidence": conf[i],
        }
        for i, p in enumerate(_seats())
    ]


def planted_wrong_variant(index: int) -> dict[str, Any]:
    slug, question, wrong, right = _PLANTED_TOPICS[index]
    # Strong evidence for the right claim, weak for the planted wrong vote.
    strong = 0.88 + (index % 5) * 0.02
    weak = 0.08 + (index % 3) * 0.02
    return {
        "council_id": f"planted-wrong-{index:02d}-{slug}",
        "family": "planted-wrong",
        "question": question,
        "claims": {
            wrong: f"Planted-wrong position for {slug}.",
            right: f"Evidence-backed position for {slug}.",
        },
        "participants": _seats(),
        "briefs": _copied_briefs(f"Agree immediately on {slug}."),
        "votes": _unanimous_votes(wrong),
        "evidence": [
            {
                "id": f"e-right-{index:02d}",
                "supports_claim_id": right,
                "strength": strong,
                "text": (
                    f"Counterexample {index}: the {slug} defect is reproducible "
                    f"and the planted consensus ignores it."
                ),
            },
            {
                "id": f"e-wrong-{index:02d}",
                "supports_claim_id": wrong,
                "strength": weak,
                "text": f"Convenience argument {index} for shipping {slug} as-is.",
            },
        ],
        "rounds_elapsed": 1,
        "disagreement_rounds": 0,
        "expected_trigger": True,
        "expected_first_outcome": wrong,
        "expected_final_outcome": right,
    }


def correct_instant_variant(index: int) -> dict[str, Any]:
    slug, question, alt, right = _CORRECT_TOPICS[index]
    strong = 0.86 + (index % 4) * 0.02
    weak = 0.10 + (index % 3) * 0.02
    return {
        "council_id": f"correct-instant-{index:02d}-{slug}",
        "family": "correct-instant",
        "question": question,
        "claims": {
            alt: f"Weaker alternative on {slug}.",
            right: f"Supported consensus on {slug}.",
        },
        "participants": _seats(),
        "briefs": _copied_briefs(f"Obvious safety call on {slug}."),
        "votes": _unanimous_votes(right),
        "evidence": [
            {
                "id": f"e-support-{index:02d}",
                "supports_claim_id": right,
                "strength": strong,
                "text": f"Primary evidence {index} supporting the {slug} consensus.",
            },
            {
                "id": f"e-alt-{index:02d}",
                "supports_claim_id": alt,
                "strength": weak,
                "text": f"Weak counterexample {index} that should not overturn {slug}.",
            },
        ],
        "rounds_elapsed": 1,
        "disagreement_rounds": 0,
        "expected_trigger": True,
        "expected_first_outcome": right,
        "expected_final_outcome": right,
    }


def rate_corpus() -> list[dict[str, Any]]:
    """20 triggered runs: 12 planted-wrong + 8 correct-instant."""
    rows = [planted_wrong_variant(i) for i in range(PLANTED_WRONG_N)]
    rows.extend(correct_instant_variant(i) for i in range(CORRECT_INSTANT_N))
    if len(rows) != RATE_CORPUS_N:
        raise RuntimeError(f"rate corpus size {len(rows)} != {RATE_CORPUS_N}")
    return rows
