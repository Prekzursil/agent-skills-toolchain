#!/usr/bin/env python3
"""Anecdote-to-claim protocol: copy source spans, never invent required slots.

A practitioner anecdote is TRANSFORMABLE only when the text already states
(1) a specific observable failure and (2) a first-person local action
(when/after/if I|we ...). Required claim fields are exact substrings of the
source. Classification labels may be INFERRED; required slots may not.

A 100% transformation rate on vague input is fabrication.
"""
from __future__ import annotations

import re
from typing import Any

PROTOCOL_ID = "anecdote-span-copy-v1"
DISPOSITION_OK = "TRANSFORMABLE"
DISPOSITION_NO = "NOT-TRANSFORMABLE"

# Structural glue allowed in the local-experiment procedure wrapper only.
PROCEDURE_GLUE = frozenset(
    {
        "locally",
        "and",
        "check",
        "whether",
        "the",
        "source",
        "stated",
        "action",
        "look",
        "for",
        "reproduce",
        "by",
        "performing",
        "looking",
    }
)

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "at",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "as",
        "into",
        "without",
        "a",
    }
)

PRONOUNS = frozenset(
    {"it", "this", "that", "they", "them", "something", "stuff", "things", "someone"}
)

VAGUE_PRE = frozenset(
    {
        "usual",
        "thing",
        "things",
        "stuff",
        "something",
        "whatever",
        "somehow",
        "it",
        "this",
        "that",
        "did",
        "do",
        "doing",
        "does",
        "done",
        "use",
        "used",
        "using",
    }
)

FAILURE_WORDS = frozenset(
    {
        "broke",
        "breaks",
        "broken",
        "fail",
        "fails",
        "failed",
        "failure",
        "crash",
        "crashes",
        "crashed",
        "hang",
        "hangs",
        "hung",
        "error",
        "errors",
        "errored",
        "raise",
        "raises",
        "raised",
        "throw",
        "throws",
        "thrown",
        "timeout",
        "refuse",
        "refuses",
        "refused",
        "reject",
        "rejects",
        "rejected",
        "leak",
        "leaks",
        "leaked",
        "deadlock",
        "deadlocks",
        "segfault",
        "panic",
        "panics",
        "abort",
        "aborts",
        "aborted",
        "wipe",
        "wiped",
        "wipes",
        "drop",
        "drops",
        "dropped",
        "cancel",
        "cancels",
        "cancelled",
        "canceled",
        "convert",
        "converts",
        "converted",
        "traceback",
        "exception",
        "oom",
    }
)

FAILURE_PHRASES = (
    "never fires",
    "timed out",
    "times out",
    "silently converts",
    "database is locked",
    "permissionerror",
    "unicodedecodeerror",
    "health-check fails",
)

TEMPLATES: list[tuple[str, re.Pattern[str]]] = [
    ("obs_when_I_pre", re.compile(r"^(?P<obs>.+?)\s+when I\s+(?P<pre>.+)$", re.I)),
    ("obs_after_I_pre", re.compile(r"^(?P<obs>.+?)\s+after I\s+(?P<pre>.+)$", re.I)),
    ("obs_if_I_pre", re.compile(r"^(?P<obs>.+?)\s+if I\s+(?P<pre>.+)$", re.I)),
    ("when_I_pre_obs", re.compile(r"^when I\s+(?P<pre>.+?),\s*(?P<obs>.+)$", re.I)),
    ("after_I_pre_obs", re.compile(r"^after I\s+(?P<pre>.+?),\s*(?P<obs>.+)$", re.I)),
    ("if_I_pre_obs", re.compile(r"^if I\s+(?P<pre>.+?),\s*(?P<obs>.+)$", re.I)),
    ("obs_when_we_pre", re.compile(r"^(?P<obs>.+?)\s+when we\s+(?P<pre>.+)$", re.I)),
    ("obs_after_we_pre", re.compile(r"^(?P<obs>.+?)\s+after we\s+(?P<pre>.+)$", re.I)),
    ("when_we_pre_obs", re.compile(r"^when we\s+(?P<pre>.+?),\s*(?P<obs>.+)$", re.I)),
    ("after_we_pre_obs", re.compile(r"^after we\s+(?P<pre>.+?),\s*(?P<obs>.+)$", re.I)),
]

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:+-]+")


def normalize(text: str) -> str:
    return " ".join((text or "").split()).strip()


def strip_span(span: str) -> str:
    return (span or "").strip().strip(".,;:").strip()


def tokens(text: str) -> list[str]:
    out: list[str] = []
    for m in TOKEN_RE.finditer(text or ""):
        tok = m.group(0).lower().strip(".,;:")
        if tok:
            out.append(tok)
    return out


def content_tokens(text: str) -> set[str]:
    return {t for t in tokens(text) if t not in STOP and len(t) > 1}


def has_failure(obs: str) -> bool:
    blob = (obs or "").lower()
    if any(p in blob for p in FAILURE_PHRASES):
        return True
    return bool(content_tokens(obs) & FAILURE_WORDS)


def specific_observable(obs: str) -> bool:
    remainder = content_tokens(obs) - FAILURE_WORDS
    if not remainder:
        return False
    return not remainder <= PRONOUNS


def specific_precondition(pre: str) -> bool:
    remainder = content_tokens(pre) - STOP
    if len(remainder) < 2:
        return False
    return not remainder <= VAGUE_PRE


def source_diff(source: str, field: str, extra_allow: frozenset[str] | None = None) -> dict[str, Any]:
    """Flag tokens in *field* that are not present in *source*.

    extra_allow is only for the procedure wrapper (glue words). Required
    slot values must pass with extra_allow=None.
    """
    allow = extra_allow or frozenset()
    src = set(tokens(source))
    inferred: list[dict[str, str]] = []
    for tok in tokens(field):
        if tok in src or tok in allow or tok in STOP:
            continue
        inferred.append(
            {
                "token": tok,
                "inference": (
                    "token is not a substring-token of the source anecdote; "
                    "the protocol must not copy it into a required slot"
                ),
            }
        )
    return {
        "field": field,
        "inferred": inferred,
        "clean": not inferred,
    }


def _reject(reason: str, **extra: Any) -> dict[str, Any]:
    out = {
        "protocol_id": PROTOCOL_ID,
        "disposition": DISPOSITION_NO,
        "reason": reason,
        "precondition": None,
        "observable": None,
        "local_experiment": None,
        "source_diff": None,
        "inferred_labels": [
            {
                "label": "claim_kind",
                "value": None,
                "inference": "no claim emitted; classification withheld",
            }
        ],
        "claim": None,
    }
    out.update(extra)
    return out


def transform(text: str) -> dict[str, Any]:
    """Transform one anecdote. Never invent a required slot."""
    source = normalize(text)
    if len(source) < 12:
        return _reject("too-short")

    match = None
    template_id = None
    for tid, rx in TEMPLATES:
        m = rx.match(source)
        if m:
            match = m
            template_id = tid
            break
    if match is None:
        return _reject("no-when-after-if-first-person-clause")

    obs = strip_span(match.group("obs"))
    pre = strip_span(match.group("pre"))
    if len(obs) < 8 or len(pre) < 8:
        return _reject("span-too-short", template_id=template_id)
    if not has_failure(obs):
        return _reject("observable-lacks-failure-verb", template_id=template_id, observable=obs)
    if not specific_observable(obs):
        return _reject("observable-not-specific", template_id=template_id, observable=obs)
    if not specific_precondition(pre):
        return _reject("precondition-not-specific", template_id=template_id, precondition=pre)
    if obs.lower() not in source.lower() or pre.lower() not in source.lower():
        return _reject("span-not-in-source", template_id=template_id)

    procedure = f"Locally {pre} and check whether {obs}."
    d_pre = source_diff(source, pre)
    d_obs = source_diff(source, obs)
    d_proc = source_diff(source, procedure, extra_allow=PROCEDURE_GLUE)
    if not (d_pre["clean"] and d_obs["clean"] and d_proc["clean"]):
        return _reject(
            "invented-detail-in-required-slot",
            template_id=template_id,
            source_diff={"precondition": d_pre, "observable": d_obs, "procedure": d_proc},
        )

    experiment = {
        "kind": "local-reproduce",
        "do": pre,
        "look_for": obs,
        "procedure": procedure,
    }
    claim = {
        "precondition": pre,
        "observable": obs,
        "local_experiment": experiment,
        "source_span_verified": True,
    }
    return {
        "protocol_id": PROTOCOL_ID,
        "disposition": DISPOSITION_OK,
        "reason": "source-spans-only",
        "template_id": template_id,
        "precondition": pre,
        "observable": obs,
        "local_experiment": experiment,
        "source_diff": {
            "precondition": d_pre,
            "observable": d_obs,
            "procedure": d_proc,
        },
        "inferred_labels": [
            {
                "label": "claim_kind",
                "value": "practitioner-failure-report",
                "inference": (
                    "label is a protocol classification, not a source phrase; "
                    "flagged INFERRED because the anecdote never names this kind"
                ),
            }
        ],
        "claim": claim,
    }
