"""Routing-hook intent-detection LOGIC (WU-1#1) — PURE functions only.

This is the classifier + decision logic ONLY; the live ``settings.json``
``UserPromptSubmit`` registration is deferred. The decision:

  * classify a prompt as biomedical-data intent (regex);
  * emit ``additionalContext`` ("query find_tools FIRST") on intent, UNLESS
    suppressed (TU already used in-session, or within N turns of TU use) or the
    per-session repeat cap is hit;
  * include the one-time ``/biopull`` + ``/wearables`` hint on the FIRST
    emission only;
  * NEVER emit ``updatedInput`` (one-rewriter-per-tool: Bash rewrites belong to
    ``inject-nopager.py``);
  * fail-OPEN: any malformed input -> no emit, never raise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FIND_TOOLS_HINT = "Biomedical-data intent detected — query `find_tools` FIRST before any named biomedical MCP."
ONE_TIME_HINT = "Tip: `/biopull` runs the resolve->fetch->normalize pipeline; `/wearables` toggles modules."

# Biomedical-data intent: assay metrics, affinity terms, named sources, or the
# GABA-B target vocabulary that drives this project.
_INTENT_PATTERN = re.compile(
    r"\b("
    r"ki|kd|ic50|ec50|pic50|pki|pec50|pkd|"
    r"binding\s+affinit\w*|bioactivit\w*|inhibitor|"
    r"chembl|pubchem|bindingdb|gtopdb|uniprot|inchikey|"
    r"gaba[\s-]?b|gabbr[12]|heterodimer|baclofen|phenibut"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouteState:
    """Per-session suppression / cap state (sourced from the ledger live)."""

    tu_used_in_session: bool = False
    turns_since_tu: int | None = None
    suppress_within_turns: int = 3
    emit_count: int = 0
    max_repeats: int = 3


@dataclass(frozen=True)
class RouteDecision:
    """Result of the routing decision. ``updated_input`` is ALWAYS None."""

    emit: bool
    additional_context: str = ""
    updated_input: None = None


def is_biomedical_intent(prompt: object) -> bool:
    """True iff ``prompt`` reads as biomedical-data intent. Fail-open."""
    if not isinstance(prompt, str) or not prompt:
        return False
    return _INTENT_PATTERN.search(prompt) is not None


def _suppressed(state: RouteState) -> bool:
    if state.tu_used_in_session:
        return True
    if (
        state.turns_since_tu is not None
        and state.turns_since_tu <= state.suppress_within_turns
    ):
        return True
    if state.emit_count >= state.max_repeats:
        return True
    return False


def route_decision(prompt: object, state: object) -> RouteDecision:
    """Decide whether to emit the find_tools hint. Pure + fail-open."""
    try:
        if not isinstance(state, RouteState):
            return RouteDecision(emit=False)
        if not is_biomedical_intent(prompt):
            return RouteDecision(emit=False)
        if _suppressed(state):
            return RouteDecision(emit=False)

        context = FIND_TOOLS_HINT
        if state.emit_count == 0:
            context = f"{context}\n{ONE_TIME_HINT}"
        return RouteDecision(emit=True, additional_context=context)
    except Exception:  # fail-OPEN: never raise out of the routing hook
        return RouteDecision(emit=False)
