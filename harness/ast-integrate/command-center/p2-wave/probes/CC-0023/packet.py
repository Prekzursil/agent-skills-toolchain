"""Group UNDECIDABLE references into one foundation-level question per token."""
from __future__ import annotations

from typing import Any

RECOMMENDATION = (
    "Do not assign a namespace without the authors of documents 16, 18 and 19. "
    "Leave the token UNDECIDABLE and fail closed until an owner answer is recorded."
)
TRADEOFF = (
    "Guessing a namespace (LLM classification of a mechanical comparison measured "
    "86 percent accurate on this estate, with 100 percent of the errors pointing at "
    "data loss) versus leaving live cross-references uninterpreted until the owner answers."
)
DEFAULT = (
    "DEFERRED. Leave every listed occurrence as the literal bare M-NN token. "
    "Downstream resolvers must return UNDECIDABLE, never a guessed card."
)


def impact_for(token: str, holders: list[str]) -> str:
    joined = ", ".join(holders) if holders else "no registered namespace"
    extra = ""
    if token == "M-16":
        extra = (
            " A third binding (wave3 Research Harness) is also live on this token."
        )
    elif token in {"M-1", "M-3"}:
        extra = " Wave1 mission-grade ids also occupy this token."
    return (
        f"Any consumer that treats {token} as a single card silently binds the wrong "
        f"record. Candidate namespaces: {joined}.{extra} Impact: false coverage and "
        "silent data loss on any join through this id."
    )


def _stem(path: str) -> str:
    name = path.replace("\\", "/").split("/")[-1]
    for prefix in ("16-", "18-", "19-"):
        if name.startswith(prefix):
            return prefix.rstrip("-")
    return name.split(".")[0][:12]


def group_undecidable(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    undecidable = [r for r in rows if r.get("verdict") == "UNDECIDABLE"]
    by_token: dict[str, list[dict[str, Any]]] = {}
    for row in undecidable:
        by_token.setdefault(row["token"], []).append(row)
    questions: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    for idx, token in enumerate(
        sorted(by_token, key=lambda t: int(t.split("-")[1])), 1
    ):
        cluster = by_token[token]
        qid = f"CC-0023-Q{idx:02d}"
        holders = list(cluster[0].get("candidate_namespaces") or [])
        impact = impact_for(token, holders)
        ref_ids: list[str] = []
        for row in cluster:
            rid = f"ref-{_stem(row['path'])}-L{row['line']}-{token}"
            ref_ids.append(rid)
            refs.append(
                {
                    "id": rid,
                    "token": token,
                    "token_number": row["token_number"],
                    "path": row["path"],
                    "line": row["line"],
                    "verdict": "UNDECIDABLE",
                    "terminal_state": "DEFERRED",
                    "candidate_namespaces": holders,
                    "question_id": qid,
                    "impact_statement": impact,
                }
            )
        questions.append(
            {
                "id": qid,
                "token": token,
                "question": (
                    f"Which namespace does bare token {token} refer to in "
                    "documents 16, 18 and 19?"
                ),
                "recommendation": RECOMMENDATION,
                "strongest_tradeoff": TRADEOFF,
                "default_if_unanswered": DEFAULT,
                "reference_ids": ref_ids,
                "reference_count": len(ref_ids),
                "candidate_namespaces": holders,
                "impact_statement": impact,
            }
        )
    return questions, refs
