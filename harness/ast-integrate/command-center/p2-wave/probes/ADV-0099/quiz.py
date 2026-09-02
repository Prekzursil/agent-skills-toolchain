"""Probe 2 engine: known-answer calibration and discriminating control."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUIZ = HERE / "fixtures/quiz.json"

UNANSWERABLE = "UNANSWERABLE"
MIN_SEPARATION = 0.5
EXPERT_AUTHORITY = 5
LAY_AUTHORITY = 1
GATE_MARGIN = 0.25


def _norm(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def load_quiz() -> dict:
    return json.loads(QUIZ.read_text(encoding="utf-8"))


def items_for(domain: str, quiz: dict) -> tuple[list[dict], list[dict]]:
    block = quiz["domains"][domain]
    return list(block["verifiable"]), list(block["unanswerable"])


def score_answerer(answerer_id: str, domain: str, quiz: dict) -> dict:
    profile = quiz["answerers"][answerer_id]
    verifiable, unanswerable = items_for(domain, quiz)
    answers = profile["answers"]
    v_correct = 0
    v_rows = []
    for item in verifiable:
        given = answers.get(item["id"], "")
        ok = _norm(given) == _norm(item["answer"])
        v_correct += int(ok)
        v_rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "expected": item["answer"],
                "given": given,
                "correct": ok,
            }
        )
    u_rows = []
    u_correct = 0
    for item in unanswerable:
        given = answers.get(item["id"], "")
        ok = _norm(given) == _norm(UNANSWERABLE)
        u_correct += int(ok)
        u_rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "expected": UNANSWERABLE,
                "given": given,
                "correct": ok,
                "guessed": _norm(given) not in {"", _norm(UNANSWERABLE)},
            }
        )
    n_v = len(verifiable)
    accuracy = (v_correct / n_v) if n_v else 0.0
    return {
        "answerer_id": answerer_id,
        "claimed_domain": profile["claimed_domain"],
        "claimed_level": profile["claimed_level"],
        "domain": domain,
        "verifiable_correct": v_correct,
        "verifiable_n": n_v,
        "accuracy": accuracy,
        "unanswerable_correct": u_correct,
        "unanswerable_n": len(unanswerable),
        "verifiable": v_rows,
        "unanswerable": u_rows,
    }


def naive_authority(claimed_domain: str, task_domain: str) -> int:
    if claimed_domain and claimed_domain == task_domain:
        return EXPERT_AUTHORITY
    return LAY_AUTHORITY


def gated_authority(accuracy: float, baseline: float) -> int:
    if accuracy > baseline + GATE_MARGIN:
        return EXPERT_AUTHORITY
    return LAY_AUTHORITY


def run_calibration() -> dict:
    quiz = load_quiz()
    crypto_g = score_answerer("genuine-crypto", "cryptography", quiz)
    crypto_c = score_answerer("claimed-crypto", "cryptography", quiz)
    crypto_u = score_answerer("genuine-unicode", "cryptography", quiz)
    crypto_l = score_answerer("lay", "cryptography", quiz)
    uni_g = score_answerer("genuine-crypto", "unicode", quiz)
    uni_c = score_answerer("claimed-crypto", "unicode", quiz)
    uni_u = score_answerer("genuine-unicode", "unicode", quiz)
    uni_l = score_answerer("lay", "unicode", quiz)

    separation_crypto = abs(crypto_g["accuracy"] - crypto_c["accuracy"])
    genuine_strong_on_claim = crypto_g["accuracy"] > uni_g["accuracy"]
    claimed_strong_off_claim = uni_c["accuracy"] > crypto_c["accuracy"]
    unicode_strong_on_claim = uni_u["accuracy"] > crypto_u["accuracy"]
    flat = separation_crypto < MIN_SEPARATION
    discriminating = (
        not flat
        and genuine_strong_on_claim
        and claimed_strong_off_claim
        and unicode_strong_on_claim
        and crypto_g["accuracy"] >= 0.75
        and crypto_c["accuracy"] <= 0.25
    )
    baseline = crypto_l["accuracy"]
    naive = {
        "genuine-crypto": naive_authority("cryptography", "cryptography"),
        "claimed-crypto": naive_authority("cryptography", "cryptography"),
        "genuine-unicode": naive_authority("unicode", "cryptography"),
        "lay": naive_authority("", "cryptography"),
    }
    gated = {
        "genuine-crypto": gated_authority(crypto_g["accuracy"], baseline),
        "claimed-crypto": gated_authority(crypto_c["accuracy"], baseline),
        "genuine-unicode": gated_authority(crypto_u["accuracy"], baseline),
        "lay": gated_authority(crypto_l["accuracy"], baseline),
    }
    hallucinated_gets_naive_premium = naive["claimed-crypto"] == EXPERT_AUTHORITY
    hallucinated_refused_gated = gated["claimed-crypto"] == LAY_AUTHORITY
    genuine_keeps_gated = gated["genuine-crypto"] == EXPERT_AUTHORITY
    return {
        "pass": discriminating
        and hallucinated_gets_naive_premium
        and hallucinated_refused_gated
        and genuine_keeps_gated,
        "discriminating": discriminating,
        "flat_accuracy": flat,
        "min_separation": MIN_SEPARATION,
        "separation_crypto": separation_crypto,
        "baseline_lay_crypto_accuracy": baseline,
        "scores": {
            "cryptography": {
                "genuine-crypto": crypto_g,
                "claimed-crypto": crypto_c,
                "genuine-unicode": crypto_u,
                "lay": crypto_l,
            },
            "unicode": {
                "genuine-crypto": uni_g,
                "claimed-crypto": uni_c,
                "genuine-unicode": uni_u,
                "lay": uni_l,
            },
        },
        "naive_authority_for_crypto_task": naive,
        "gated_authority_for_crypto_task": gated,
        "hallucinated_gets_naive_premium": hallucinated_gets_naive_premium,
        "hallucinated_refused_gated": hallucinated_refused_gated,
        "genuine_keeps_gated": genuine_keeps_gated,
        "control": {
            "id": "domain-separation",
            "requirement": (
                "control: include a domain where the participant genuinely "
                "performs well and one where it does not, and require the "
                "measurement to separate them; a flat accuracy result means "
                "the question set is not discriminating"
            ),
            "genuine_crypto_acc_crypto": crypto_g["accuracy"],
            "genuine_crypto_acc_unicode": uni_g["accuracy"],
            "claimed_crypto_acc_crypto": crypto_c["accuracy"],
            "claimed_crypto_acc_unicode": uni_c["accuracy"],
            "separated": discriminating,
        },
        "catalog_probe": (
            "Probe 2 (mechanically different): behavioural - pose questions "
            "with known answers inside the claimed domain and measure accuracy "
            "against the claimed expertise level, which converts an assertion "
            "into a measurement."
        ),
    }
