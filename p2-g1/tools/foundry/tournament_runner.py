"""Tournament runner: reduces tournament pairs through the ONE shared predicate.

WFA-0134 call site. This module defines no local predicate; the verdict comes
from ``tools.foundry.completion_predicate.evaluate`` and nothing else.
"""
from __future__ import annotations

from typing import Any, Mapping

from tools.foundry.completion_predicate import Verdict, evaluate


def certify_workflow(
    subject: Mapping[str, Any] | None = None,
    *,
    repo: Any = None,
    pair_id: Any = None,
    **kwargs: Any,
) -> Verdict:
    return evaluate(subject, locus="tournament-runner", repo=repo, pair_id=pair_id, **kwargs)


__all__ = ["Verdict", "certify_workflow", "evaluate"]
