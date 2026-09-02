"""Mechanical selection-provenance classifier for BLD-0022.

Speaker is an input field, never inferred from wording. An agent-authored
sentence that says "Select X" cannot become OWNER-EXPLICIT.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

OWNER_EXPLICIT = "OWNER-EXPLICIT"
OWNER_IMPLIED = "OWNER-IMPLIED"
AGENT_ASSUMED = "AGENT-ASSUMED"

_SELECT = re.compile(
    r"\b(select|selected|choose|chose|chosen|pick|picked|accept|accepted|"
    r"bind|binding|is|equals|=)\b",
    re.IGNORECASE,
)
_NEG = re.compile(
    r"\b(not|never|don't|do not|didn't|did not|reject|rejected|unselected|"
    r"instead of|rather than|must not)\b",
    re.IGNORECASE,
)
_OWNER_READING = re.compile(
    r"\b(owner|delegat(?:e|ed|ion)|reading the owner|you proceed|\bgo\b)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Utterance:
    speaker: str
    path: str
    line: int
    text: str

    @property
    def anchor(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class Verdict:
    classification: str
    owner_quote: str | None = None
    owner_quote_anchor: str | None = None
    agent_summary: str | None = None
    inference: str | None = None
    routed_to_owner: bool = False
    matched_utterances: list[str] = field(default_factory=list)

    def as_row(
        self,
        option_id: str,
        treated_as: str,
        source: str,
    ) -> dict:
        return {
            "id": option_id,
            "treated_as": treated_as,
            "classification": self.classification,
            "owner_quote": self.owner_quote,
            "owner_quote_anchor": self.owner_quote_anchor,
            "agent_summary": self.agent_summary,
            "inference": self.inference,
            "routed_to_owner": self.routed_to_owner,
            "source": source,
            "matched_utterances": list(self.matched_utterances),
        }


def _window(text: str, token: str, radius: int = 80) -> str:
    low = text.lower()
    needle = token.lower()
    idx = low.find(needle)
    if idx < 0:
        return text
    start = max(0, idx - radius)
    end = min(len(text), idx + len(token) + radius)
    return text[start:end]


def mentions_token(text: str, token: str) -> bool:
    return token.lower() in text.lower()


def selects(text: str, token: str) -> bool:
    """True when this sentence treats token as chosen, not merely mentioned."""
    if not mentions_token(text, token):
        return False
    window = _window(text, token)
    if _NEG.search(window):
        return False
    if token.upper() == "PR-ONLY":
        # Release-mode control: "Release mode is PR-ONLY" is the known explicit form.
        return bool(
            re.search(r"release\s+mode", text, re.IGNORECASE) and _SELECT.search(window)
        ) or bool(re.search(r"\bis\s+PR-ONLY\b", text, re.IGNORECASE))
    return bool(_SELECT.search(window) or _SELECT.search(text))


def is_owner_speaker(speaker: str) -> bool:
    return str(speaker).strip().lower() == "owner"


def classify(token: str, utterances: list[Utterance]) -> Verdict:
    """Classify one selected id or decision token against a speaker-labeled corpus."""
    owner_hits: list[Utterance] = []
    implied_hits: list[Utterance] = []
    assumed_hits: list[Utterance] = []

    for u in utterances:
        if not mentions_token(u.text, token) and not (
            token.upper() == "PR-ONLY" and "release mode" in u.text.lower()
        ):
            # PR-ONLY can also be the whole decision token in a release-mode sentence.
            if not (token.upper() == "PR-ONLY" and "pr-only" in u.text.lower()):
                continue
        if is_owner_speaker(u.speaker):
            if selects(u.text, token):
                owner_hits.append(u)
        else:
            # Agent text is never an owner quote, even when it uses first person "Select".
            if _OWNER_READING.search(u.text) and mentions_token(u.text, token):
                implied_hits.append(u)
            elif selects(u.text, token) or mentions_token(u.text, token):
                assumed_hits.append(u)

    if owner_hits:
        hit = owner_hits[0]
        return Verdict(
            classification=OWNER_EXPLICIT,
            owner_quote=hit.text.strip(),
            owner_quote_anchor=hit.anchor,
            agent_summary=None,
            inference=None,
            routed_to_owner=False,
            matched_utterances=[h.anchor for h in owner_hits],
        )

    if implied_hits:
        hit = implied_hits[0]
        return Verdict(
            classification=OWNER_IMPLIED,
            owner_quote=None,
            owner_quote_anchor=None,
            agent_summary=hit.text.strip(),
            inference=(
                "Agent text cites the owner or a delegation without a speaker=owner "
                "sentence that itself selects this token. Evidence requirement: that "
                "is OWNER-IMPLIED at best."
            ),
            routed_to_owner=False,
            matched_utterances=[h.anchor for h in implied_hits],
        )

    if assumed_hits:
        hit = assumed_hits[0]
        return Verdict(
            classification=AGENT_ASSUMED,
            owner_quote=None,
            owner_quote_anchor=None,
            agent_summary=hit.text.strip(),
            inference=(
                "Agent recorded this id as selected with no owner quotation and no "
                "owner-reading citation."
            ),
            routed_to_owner=True,
            matched_utterances=[h.anchor for h in assumed_hits],
        )

    return Verdict(
        classification=AGENT_ASSUMED,
        owner_quote=None,
        owner_quote_anchor=None,
        agent_summary=None,
        inference="Treated as SELECTED with no corpus utterance naming this token.",
        routed_to_owner=True,
        matched_utterances=[],
    )
