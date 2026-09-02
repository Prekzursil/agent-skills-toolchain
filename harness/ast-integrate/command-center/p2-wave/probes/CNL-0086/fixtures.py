"""Council transcripts for CNL-0086 echo-chamber / independence-loss.

Pathology is shared private sources + shared warrants, or post-exposure
copy of a peer's warrants. Generation-independence is a decoy: the
shared-source planted-bad sets generated_independently=True on every
first pass (ADV-0135 attack 4).

Vote agreement is a decoy: known-good fixtures converge on the same
conclusion with disjoint private sources and disjoint warrants.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

PUBLIC = ["SRC-QUESTION-PACKET"]
CONCLUSION_FAIL_CLOSED = "fail-closed-on-vendor-timeout"
CONCLUSION_RETRY = "retry-then-open"
CONCLUSION_FALLBACK = "degrade-to-cached-auth"

# Distinct warrants: token overlap is low so a lexical decoy cannot
# substitute for warrant-id overlap.
W_ERROR_BUDGET = "W-error-budget-burn-from-p99-slo"
W_CASCADE = "W-incident-2024-03-cascade-when-retries-amplified-load"
W_LIABILITY = "W-msa-clause-12-fail-open-shifts-chargeback-liability"
W_FAQ_RETRY = "W-vendor-faq-retry-three-times"
W_FAQ_TIMEOUT = "W-vendor-faq-treat-timeout-as-soft-fail"
W_PEER_COPY_A1 = "W-error-budget-burn-from-p99-slo"  # same as W_ERROR_BUDGET when copied
W_B_SLO_MATH = "W-new-slo-math-after-seeing-A-still-independent-derivation"
W_C_CONTRACT = "W-new-contract-reading-after-seeing-A-still-independent-clause"
W_B_FIRST = "W-queue-depth-retry-looks-cheap-locally"
W_C_FIRST = "W-cached-auth-covers-the-read-path-only"
W_PACKET_A = "W-question-packet-timeout-budget-is-150ms"
W_PACKET_B = "W-question-packet-lists-two-vendors-with-no-shared-retry-policy"
W_PACKET_C = "W-question-packet-requires-an-explicit-customer-visible-failure-mode"
W_EASY_A = "W-addition-2-plus-2-via-peano"
W_EASY_B = "W-addition-2-plus-2-via-set-cardinality"
W_EASY_C = "W-addition-2-plus-2-via-abacus"


def _fp(
    sources: list[str],
    warrants: list[str],
    claims: list[str],
    conclusion: str,
    generated_independently: bool = True,
    text: str = "",
) -> dict[str, Any]:
    return {
        "generated_independently": generated_independently,
        "sources": list(sources),
        "warrants": list(warrants),
        "claims": list(claims),
        "conclusion": conclusion,
        "text": text,
    }


def _p(
    pid: str,
    first_pass: dict[str, Any],
    later: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": pid,
        "role": "peer",
        "first_pass": first_pass,
        "later_turns": list(later or []),
    }


def _run(
    rid: str,
    participants: list[dict[str, Any]],
    question: str,
    public: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": rid,
        "question_id": "vendor-timeout-policy",
        "question": question,
        "public_premises": list(PUBLIC if public is None else public),
        "participants": participants,
    }


Q_HARD = (
    "On payment-vendor timeout, should the charge path fail closed, retry, "
    "or degrade to cached authorization?"
)
Q_EASY = "What is 2+2, and give an independent derivation?"


def planted_bad_shared_source() -> dict[str, Any]:
    """ADV-0135 #4: independently GENERATED briefs, one retrieved source."""
    text_a = (
        "I independently retrieved VendorFAQ and wrote a brief: retry three "
        "times, treat timeout as a soft fail, then continue the charge."
    )
    text_b = (
        "Working from the FAQ I pulled myself: three retries, timeout is a "
        "soft failure, proceed with the payment attempt."
    )
    text_c = (
        "My own first-pass notes from the same FAQ document: retry thrice "
        "and classify vendor timeout as soft-fail so checkout stays open."
    )
    src = ["SRC-RETRIEVED-VENDOR-FAQ"]
    w = [W_FAQ_RETRY, W_FAQ_TIMEOUT]
    claims = ["C-retry-is-safe", "C-timeout-is-soft"]
    return _run(
        "planted-bad-shared-source",
        [
            _p("A", _fp(src, w, claims, CONCLUSION_RETRY, True, text_a)),
            _p("B", _fp(src, w, claims, CONCLUSION_RETRY, True, text_b)),
            _p("C", _fp(src, w, claims, CONCLUSION_RETRY, True, text_c)),
        ],
        Q_HARD,
    )


def known_present() -> dict[str, Any]:
    run = planted_bad_shared_source()
    run["id"] = "known-present"
    return run


def planted_bad_sequential() -> dict[str, Any]:
    """Independent first passes, then peers copy A's warrants after exposure."""
    return _run(
        "planted-bad-sequential-anchor",
        [
            _p(
                "A",
                _fp(
                    ["SRC-SRE-WORKBOOK"],
                    [W_ERROR_BUDGET],
                    ["C-burn-slo"],
                    CONCLUSION_FAIL_CLOSED,
                    True,
                    "From the SRE workbook: retries burn the error budget.",
                ),
                later=[
                    {
                        "round": 2,
                        "warrants": [W_ERROR_BUDGET],
                        "claims": ["C-burn-slo"],
                        "conclusion": CONCLUSION_FAIL_CLOSED,
                    }
                ],
            ),
            _p(
                "B",
                _fp(
                    ["SRC-QUEUE-METRICS"],
                    [W_B_FIRST],
                    ["C-retry-looks-cheap"],
                    CONCLUSION_RETRY,
                    True,
                    "Queue depth makes a retry look locally cheap.",
                ),
                later=[
                    {
                        "round": 2,
                        "warrants": [W_ERROR_BUDGET],
                        "claims": ["C-burn-slo"],
                        "conclusion": CONCLUSION_FAIL_CLOSED,
                    }
                ],
            ),
            _p(
                "C",
                _fp(
                    ["SRC-CACHE-DESIGN"],
                    [W_C_FIRST],
                    ["C-cache-covers-reads"],
                    CONCLUSION_FALLBACK,
                    True,
                    "Cached auth only covers the read path.",
                ),
                later=[
                    {
                        "round": 2,
                        "warrants": [W_ERROR_BUDGET],
                        "claims": ["C-burn-slo"],
                        "conclusion": CONCLUSION_FAIL_CLOSED,
                    }
                ],
            ),
        ],
        Q_HARD,
    )


def known_good_genuine_convergence() -> dict[str, Any]:
    """Same conclusion, disjoint private sources, disjoint warrants."""
    return _run(
        "known-good-genuine-convergence",
        [
            _p(
                "A",
                _fp(
                    ["SRC-SRE-WORKBOOK"],
                    [W_ERROR_BUDGET],
                    ["C-burn-slo"],
                    CONCLUSION_FAIL_CLOSED,
                    True,
                    "SRE workbook: p99 error-budget math forbids retry amplification.",
                ),
            ),
            _p(
                "B",
                _fp(
                    ["SRC-INCIDENT-2024-03"],
                    [W_CASCADE],
                    ["C-retries-cascaded"],
                    CONCLUSION_FAIL_CLOSED,
                    True,
                    "Incident 2024-03: retries amplified load and cascaded the outage.",
                ),
            ),
            _p(
                "C",
                _fp(
                    ["SRC-MSA-CLAUSE-12"],
                    [W_LIABILITY],
                    ["C-liability-shifts"],
                    CONCLUSION_FAIL_CLOSED,
                    True,
                    "MSA clause 12: fail-open on timeout shifts chargeback liability.",
                ),
            ),
        ],
        Q_HARD,
    )


def clean_late_agreement() -> dict[str, Any]:
    """Independent first passes, then new warrants (not copies) then same conclusion."""
    return _run(
        "clean-late-agreement",
        [
            _p(
                "A",
                _fp(
                    ["SRC-SRE-WORKBOOK"],
                    [W_ERROR_BUDGET],
                    ["C-burn-slo"],
                    CONCLUSION_FAIL_CLOSED,
                    True,
                    "Fail closed from error-budget arithmetic.",
                ),
            ),
            _p(
                "B",
                _fp(
                    ["SRC-QUEUE-METRICS"],
                    [W_B_FIRST],
                    ["C-retry-looks-cheap"],
                    CONCLUSION_RETRY,
                    True,
                    "First pass still prefers retry from queue-depth.",
                ),
                later=[
                    {
                        "round": 2,
                        "warrants": [W_B_SLO_MATH],
                        "claims": ["C-revised-slo"],
                        "conclusion": CONCLUSION_FAIL_CLOSED,
                    }
                ],
            ),
            _p(
                "C",
                _fp(
                    ["SRC-CACHE-DESIGN"],
                    [W_C_FIRST],
                    ["C-cache-covers-reads"],
                    CONCLUSION_FALLBACK,
                    True,
                    "First pass still prefers cached auth.",
                ),
                later=[
                    {
                        "round": 2,
                        "warrants": [W_C_CONTRACT],
                        "claims": ["C-revised-liability"],
                        "conclusion": CONCLUSION_FAIL_CLOSED,
                    }
                ],
            ),
        ],
        Q_HARD,
    )


def clean_public_premises_only() -> dict[str, Any]:
    """Sharing the question packet is allowed; private sources empty."""
    return _run(
        "clean-public-premises-only",
        [
            _p(
                "A",
                _fp(
                    list(PUBLIC),
                    [W_PACKET_A],
                    ["C-150ms-budget"],
                    CONCLUSION_FAIL_CLOSED,
                    True,
                    "Packet timeout budget 150ms cannot absorb retries.",
                ),
            ),
            _p(
                "B",
                _fp(
                    list(PUBLIC),
                    [W_PACKET_B],
                    ["C-two-vendors"],
                    CONCLUSION_FAIL_CLOSED,
                    True,
                    "Packet names two vendors with no shared retry policy.",
                ),
            ),
            _p(
                "C",
                _fp(
                    list(PUBLIC),
                    [W_PACKET_C],
                    ["C-visible-failure"],
                    CONCLUSION_FAIL_CLOSED,
                    True,
                    "Packet requires a customer-visible failure mode, not silent retry.",
                ),
            ),
        ],
        Q_HARD,
    )


def clean_easy_distinct_paths() -> dict[str, Any]:
    """Easy question, same answer, three independent derivations. Must be SILENT."""
    return _run(
        "clean-easy-distinct-paths",
        [
            _p(
                "A",
                _fp(
                    ["SRC-PEANO"],
                    [W_EASY_A],
                    ["C-succ-succ-0-twice"],
                    "4",
                    True,
                    "Peano: S(S(0))+S(S(0))=S(S(S(S(0)))).",
                ),
            ),
            _p(
                "B",
                _fp(
                    ["SRC-SET-CARD"],
                    [W_EASY_B],
                    ["C-union-disjoint-pairs"],
                    "4",
                    True,
                    "Two disjoint 2-sets have cardinality 4.",
                ),
            ),
            _p(
                "C",
                _fp(
                    ["SRC-ABACUS"],
                    [W_EASY_C],
                    ["C-two-beads-twice"],
                    "4",
                    True,
                    "Abacus: two beads, then two more, read four.",
                ),
            ),
        ],
        Q_EASY,
        public=[],
    )


def no_first_pass() -> dict[str, Any]:
    run = _run(
        "no-first-pass",
        [
            {
                "id": "A",
                "role": "peer",
                "first_pass": None,
                "later_turns": [],
            },
            {
                "id": "B",
                "role": "peer",
                "first_pass": None,
                "later_turns": [],
            },
        ],
        Q_HARD,
    )
    return run


def clean_fixtures() -> list[dict[str, Any]]:
    return [
        known_good_genuine_convergence(),
        clean_late_agreement(),
        clean_public_premises_only(),
        clean_easy_distinct_paths(),
    ]


def all_named() -> dict[str, dict[str, Any]]:
    return {
        "planted-bad-shared-source": planted_bad_shared_source(),
        "known-present": known_present(),
        "planted-bad-sequential-anchor": planted_bad_sequential(),
        "known-good-genuine-convergence": known_good_genuine_convergence(),
        "clean-late-agreement": clean_late_agreement(),
        "clean-public-premises-only": clean_public_premises_only(),
        "clean-easy-distinct-paths": clean_easy_distinct_paths(),
        "no-first-pass": no_first_pass(),
    }


def dumps() -> dict[str, Any]:
    return {k: deepcopy(v) for k, v in all_named().items()}
