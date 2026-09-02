"""Vacuity detector for strongest-remaining-caveat fields.

A caveat is SPECIFIC only when it names a fail-condition and an observation
that would reveal the failure, and is not a restatement, further-testing
shrug, or generic disclaimer. A VERIFIED item whose caveat is already fatal
is a labelling error, not a caveat.
"""
from __future__ import annotations

import re
from typing import Any

WORD_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    """
    a an the of to and or is are was were be been being this that it its for on
    in as with from by not no so if then than at we our you your they their
    claim the
    """.split()
)
FAIL_RE = re.compile(
    r"\bfails?\s+if\b|\bfails?\s+when\b|\bwould fail\b|\bclaim fails\b|"
    r"\bunless\b|\bfailure condition\b",
    re.I,
)
OBS_RE = re.compile(
    r"\breveal|\bobserv|\bmeasur|\bcounterexample|\bprobe\b|\bdigest\b|"
    r"\bsha256\b|\bre-?run|\blog line\b|\breceipt\b",
    re.I,
)
FURTHER_RE = re.compile(
    r"further testing recommended|further testing is recommended|"
    r"more testing is needed|additional testing is advised|"
    r"more research is needed|needs more testing",
    re.I,
)
GENERIC_PHRASES = (
    "results may vary",
    "no warranty",
    "provided as-is",
    "as-is without",
    "this is not a guarantee",
    "caveat emptor",
    "use with caution",
    "past performance",
    "in some cases",
    "it depends",
    "this is a caveat",
    "standard disclaimer",
)
FATAL_RE = re.compile(
    r"already (refuted|disproven|false)|cannot hold|has been refuted|"
    r"is (already )?false|does not hold|is disproven",
    re.I,
)
SURVIVING_LABELS = frozenset({"VERIFIED", "INFERRED", "UNVERIFIED", "DEFERRED"})
REJECTED_LABELS = frozenset({"REJECTED"})


def tokens(text: str) -> set[str]:
    return {w for w in WORD_RE.findall(text.lower()) if w not in STOP and len(w) > 1}


def _norm(text: str) -> str:
    return " ".join(WORD_RE.findall(text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_restatement(claim: str, caveat: str, has_fail: bool) -> bool:
    if _norm(claim) == _norm(caveat):
        return True
    ct, vt = tokens(claim), tokens(caveat)
    jac = jaccard(ct, vt)
    if jac >= 0.85:
        return True
    if ct and ct <= vt and not has_fail:
        return True
    if jac >= 0.72 and not has_fail:
        return True
    return False


def assess(claim_text: str, caveat: str) -> dict[str, Any]:
    text = (caveat or "").strip()
    if not text:
        return {
            "vacuous": True,
            "verdict": "VACUOUS",
            "rule": "EMPTY",
            "fail_condition_named": False,
            "observation_named": False,
        }
    has_fail = bool(FAIL_RE.search(text))
    has_obs = bool(OBS_RE.search(text))
    restated = is_restatement(claim_text or "", text, has_fail)
    further = bool(FURTHER_RE.search(text))
    generic = any(p in text.lower() for p in GENERIC_PHRASES)

    if has_fail and has_obs and not restated and not further:
        return {
            "vacuous": False,
            "verdict": "SPECIFIC",
            "rule": "NONE",
            "fail_condition_named": True,
            "observation_named": True,
        }
    if restated:
        rule = "RESTATEMENT"
    elif further:
        rule = "FURTHER_TESTING"
    elif generic:
        rule = "GENERIC_DISCLAIMER"
    elif not has_fail or not has_obs:
        rule = "INCOMPLETE"
    else:
        rule = "RESTATEMENT"
    return {
        "vacuous": True,
        "verdict": "VACUOUS",
        "rule": rule,
        "fail_condition_named": has_fail,
        "observation_named": has_obs,
    }


def is_fatal(caveat: str) -> bool:
    return bool(FATAL_RE.search(caveat or ""))


def label_contradiction(label: str, caveat: str) -> bool:
    """A VERIFIED item with a fatal caveat is a labelling error."""
    return str(label or "").upper() == "VERIFIED" and is_fatal(caveat)


def default_replacement(claim_id: str, claim_text: str) -> str:
    cid = claim_id or "unnamed-claim"
    snippet = " ".join((claim_text or "").split())[:80]
    return (
        f"Claim {cid} fails if the cited artifact is missing, unreadable, or its "
        f"sha256 diverges from the recorded digest for {cid!r} ({snippet!r}); "
        "that would be revealed by re-running the named probe and comparing the "
        "live file digest to the UNIT-ARTIFACT-MANIFEST row."
    )


def enforce(item: dict[str, Any]) -> dict[str, Any]:
    claim_id = str(item.get("id") or item.get("claim_id") or "")
    claim_text = str(item.get("text") or item.get("claim_text") or item.get("claim") or "")
    label = str(item.get("label") or "").upper()
    original = str(item.get("caveat") or item.get("original_caveat") or "")
    preset = str(item.get("replacement") or "").strip()
    judged = assess(claim_text, original)
    replacement = ""
    enforced = original.strip()
    if judged["vacuous"]:
        replacement = preset or default_replacement(claim_id, claim_text)
        enforced = replacement
    remaining = assess(claim_text, enforced)
    contradiction = label_contradiction(label, enforced)
    return {
        "claim_id": claim_id,
        "claim_text": claim_text,
        "label": label,
        "caveat": enforced,
        "original_caveat": original,
        "vacuity_verdict": judged["verdict"],
        "rule_fired": judged["rule"],
        "replacement": replacement,
        "label_contradiction": contradiction,
        "remaining_vacuous": bool(remaining["vacuous"]),
        "remaining_rule": remaining["rule"],
        "fail_condition_named": remaining["fail_condition_named"],
        "observation_named": remaining["observation_named"],
    }
