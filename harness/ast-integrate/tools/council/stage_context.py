"""Prompt-injection carriers through council stage context (TST-0273).

Every participant-produced or tool-produced text that a later stage sees is a
*carrier*: a position paper, the running transcript, the idea ledger, an evidence
bundle, a tool result, or even a display name. A downstream stage that concatenates
those carriers into its own instruction text can be steered by a directive smuggled
inside one of them.

:func:`assemble` builds the stage context in two modes:

* ``naive=True`` — the known-broken concatenator: instruction and carriers are
  joined into one instruction blob (the positive-control failure mode).
* ``naive=False`` — the defended assembler: the genuine instruction channel is kept
  verbatim, every carrier is wrapped in an ``UNTRUSTED-DATA`` fence, and imperative
  directives inside a fence are neutralised in place (the canary token stays
  readable as DATA, so ``token_reached`` still sees it) with one log line each.

:func:`consume` is the later stage: it executes ``EXECUTE_CANARY:<token>``
directives found in its *instruction channel* and reports anything it obeyed. In
the defended layout the instruction channel never contains carrier text, so the
only directives it can obey are the ones a human actually wrote there.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

CARRIERS: tuple[str, ...] = (
    "position_paper",
    "transcript",
    "idea_ledger",
    "evidence_bundle",
    "tool_result",
    "display_name",
)

FENCE_OPEN = "<<<UNTRUSTED-DATA carrier={carrier} seat={seat} provenance={provenance}>>>"
FENCE_CLOSE = "<<<END-UNTRUSTED-DATA carrier={carrier}>>>"
MODE_NAIVE = "naive-concatenation"
MODE_DEFENDED = "fenced-data"

# A live directive is the execute verb followed by the canary token. Neutralising
# turns the verb into a bracketed, non-executable marker while keeping the token
# text intact so later stages can still *see* the DATA they were handed.
_DIRECTIVE_RE = re.compile(r"EXECUTE_CANARY:([A-Za-z0-9_.-]+)")
_NEUTRALISED_RE = re.compile(r"\[DATA-DIRECTIVE-NEUTRALIZED\]:([A-Za-z0-9_.-]+)")
_IGNORE_RE = re.compile(r"ignore\s+(previous|all|above)\s+instructions", re.IGNORECASE)


def _carrier_text(blob: Any) -> tuple[str, str, str]:
    if isinstance(blob, Mapping):
        return (
            str(blob.get("text") or ""),
            str(blob.get("seat") or "unknown"),
            str(blob.get("provenance") or "participant-artifact"),
        )
    return str(blob or ""), "unknown", "participant-artifact"


def neutralize(text: str, *, carrier: str) -> tuple[str, list[dict[str, Any]]]:
    """Disarm directives in a carrier; return the disarmed text and one log row per hit."""
    log: list[dict[str, Any]] = []
    for match in _DIRECTIVE_RE.finditer(text):
        log.append({"kind": "directive", "carrier": carrier, "token": match.group(1)})
    for match in _IGNORE_RE.finditer(text):
        log.append({"kind": "override-phrase", "carrier": carrier, "phrase": match.group(0)})
    disarmed = _DIRECTIVE_RE.sub(r"[DATA-DIRECTIVE-NEUTRALIZED]:\1", text)
    disarmed = _IGNORE_RE.sub("[DATA-OVERRIDE-PHRASE-NEUTRALIZED]", disarmed)
    return disarmed, log


def assemble(state: Mapping[str, Any], *, naive: bool = False) -> dict[str, Any]:
    """Build the stage context from ``state = {"instruction": str, "carriers": {...}}``."""
    instruction = str(state.get("instruction") or "")
    carriers = state.get("carriers") or {}
    order = [c for c in CARRIERS if c in carriers] + [c for c in carriers if c not in CARRIERS]
    if naive:
        parts = [instruction]
        for name in order:
            text, seat, _prov = _carrier_text(carriers[name])
            parts.append(f"{name} ({seat}): {text}")
        blob = "\n".join(parts)
        return {
            "mode": MODE_NAIVE,
            "assembled": {"instruction": blob, "data": "", "carriers": list(order)},
            "neutralization_log": [],
            "fenced_carriers": [],
        }
    fenced: list[str] = []
    log: list[dict[str, Any]] = []
    for name in order:
        text, seat, prov = _carrier_text(carriers[name])
        disarmed, rows = neutralize(text, carrier=name)
        log.extend(rows)
        fenced.append(
            "\n".join(
                [
                    FENCE_OPEN.format(carrier=name, seat=seat, provenance=prov),
                    disarmed,
                    FENCE_CLOSE.format(carrier=name),
                ]
            )
        )
    return {
        "mode": MODE_DEFENDED,
        "assembled": {
            "instruction": instruction,
            "data": "\n".join(fenced),
            "carriers": list(order),
        },
        "neutralization_log": log,
        "fenced_carriers": list(order),
    }


def consume(assembled: Mapping[str, Any]) -> dict[str, Any]:
    """The later stage: obey directives in the instruction channel, read DATA as data."""
    instruction = str(assembled.get("instruction") or "")
    data = str(assembled.get("data") or "")
    obeyed_tokens = [m.group(1) for m in _DIRECTIVE_RE.finditer(instruction)]
    live_in_data = [m.group(1) for m in _DIRECTIVE_RE.finditer(data)]
    neutralized_in_data = [m.group(1) for m in _NEUTRALISED_RE.finditer(data)]
    obeyed = bool(obeyed_tokens)
    return {
        "action": ("emit-canary:" + ",".join(obeyed_tokens)) if obeyed else "continue-deliberation",
        "obeyed": obeyed,
        "obeyed_tokens": obeyed_tokens,
        "live_tokens_in_data": live_in_data,
        "neutralized_tokens_in_data": neutralized_in_data,
        "instruction_excerpt": instruction[:200],
        "data_excerpt": data[:200],
    }


def token_reached(assembled: Mapping[str, Any], token: str) -> bool:
    """True when the canary text is visible anywhere in the assembled context."""
    return token in str(assembled.get("instruction") or "") or token in str(
        assembled.get("data") or ""
    )
