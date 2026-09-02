"""Mechanical failure-behaviour extractor for WFA-0040.

Four modes are scored separately. Absence is UNDEFINED, never a safe-default.
A timeout_seconds bound is not timeout behaviour. An on_error aggregate is
not all four modes. Memory-until-end is a write-as-you-go violation.
"""
from __future__ import annotations

import re
from typing import Any

from corpus import FOUR_MODES, MODE_SPEC

# Quote-level patterns. Substring "timeout" inside timeout_seconds is NOT used;
# we scan prose fields only and require these phrases.
PARTIAL_RE = re.compile(
    r"(partial result|partial artifact|write-as-you-go|write as you go|"
    r"holds results in memory|held in memory|buffer(?:s|ed)? until the end|"
    r"write(?:s)? nothing|wrote nothing|durable on disk|"
    r"flush(?:es)? the bytes already written|single write at completion|"
    r"in memory until the end)",
    re.IGNORECASE,
)
HUNG_RE = re.compile(
    r"(hung unit|hung agent|one hung|deadlock(?:s)? the (?:cohort|batch|phase)|"
    r"blocks? a (?:large )?batch|per-unit pipeline|classify(?:ies)? STALLED|"
    r"release the slot)",
    re.IGNORECASE,
)
TIMEOUT_RE = re.compile(
    r"(on a timeout|on timeout|when timed out|timed-out unit|"
    r"timeout classif|FAILED:timeout|per-agent deadline|"
    r"classifies the unit FAILED:timeout)",
    re.IGNORECASE,
)
DEAD_RE = re.compile(
    r"(dead monitor|monitor dies|monitor liveness|orchestrator death|"
    r"stall detection from mtimes|heartbeat gap|"
    r"treat the worker as live|idle work read as dead)",
    re.IGNORECASE,
)

MODE_RE = {
    "partial_result": PARTIAL_RE,
    "hung_unit": HUNG_RE,
    "timeout": TIMEOUT_RE,
    "dead_monitor": DEAD_RE,
}

WAYG_VIOLATION_RE = re.compile(
    r"(holds results in memory|held in memory until|in memory until the end|"
    r"buffer(?:s|ed)? until (?:the )?end|write(?:s)? only at (?:the )?(?:end|completion)|"
    r"single write at completion|write nothing|wrote nothing)",
    re.IGNORECASE,
)
WAYG_COMPLIANT_RE = re.compile(
    r"(write-as-you-go|write as you go|durable on disk|"
    r"flush(?:es)? a durable|flush the bytes already written)",
    re.IGNORECASE,
)

PROSE_KEYS = (
    "does",
    "mechanisms",
    "notes",
    "runtime",
    "evidence",
    "description",
    "name",
)

FORBIDDEN_STATUSES = frozenset(
    {
        "GRACEFUL",
        "SAFE-DEFAULT",
        "SAFE_DEFAULT",
        "ASSUMED",
        "OK",
        "FINE",
        "HANDLED",
        "DEFAULT",
        "INFERRED",
    }
)

FAULTS = {
    "partial_result": (
        "Kill the process after the first stage has produced bytes but before "
        "the completion sentinel is written."
    ),
    "hung_unit": (
        "Inject one sibling that never returns while the rest of the cohort "
        "is ready to finish."
    ),
    "timeout": (
        "Hold one unit past its declared deadline and observe the terminal class."
    ),
    "dead_monitor": (
        "Stop the monitor process while the worker keeps running, then read "
        "the health signal."
    ),
}


def _quote_span(text: str, match: re.Match[str], radius: int = 80) -> str:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def defining_text(candidate: dict[str, Any]) -> tuple[str, list[str]]:
    used: list[str] = []
    chunks: list[str] = []
    for key in PROSE_KEYS:
        val = candidate.get(key)
        if isinstance(val, str) and val.strip():
            used.append(key)
            chunks.append(val.strip())
        elif isinstance(val, (list, dict)) and val:
            used.append(key)
            chunks.append(str(val))
    return "\n".join(chunks), used


def _mode_record(text: str, mode: str) -> dict[str, Any]:
    spec = MODE_SPEC[mode]
    rx = MODE_RE[mode]
    m = rx.search(text or "")
    if m is None:
        return {
            "status": "UNDEFINED",
            "quote": None,
            "inferred_safe_default": False,
            "spec_class": spec["class_id"],
            "spec_name": spec["name"],
            "note": (
                "No defining text for this mode. Recorded UNDEFINED; not inferred "
                "as graceful or safe-default."
            ),
        }
    return {
        "status": "EVIDENCED",
        "quote": _quote_span(text, m),
        "match": m.group(0),
        "inferred_safe_default": False,
        "spec_class": spec["class_id"],
        "spec_name": spec["name"],
        "note": "Quoted from defining text. Four modes are independent columns.",
    }


def write_as_you_go(text: str) -> dict[str, Any]:
    viol = WAYG_VIOLATION_RE.search(text or "")
    comp = WAYG_COMPLIANT_RE.search(text or "")
    if viol is not None:
        return {
            "status": "VIOLATION",
            "flagged": True,
            "quote": _quote_span(text, viol),
            "mandate": "fan-out-contract.md C1 write-as-you-go",
            "note": (
                "Candidate holds or delays results until the end. Flagged against "
                "the write-as-you-go mandate."
            ),
        }
    if comp is not None:
        return {
            "status": "COMPLIANT",
            "flagged": False,
            "quote": _quote_span(text, comp),
            "mandate": "fan-out-contract.md C1 write-as-you-go",
            "note": "Defining text requires durable incremental writes.",
        }
    return {
        "status": "UNDECLARED",
        "flagged": False,
        "quote": None,
        "mandate": "fan-out-contract.md C1 write-as-you-go",
        "note": (
            "No write-as-you-go or memory-until-end quote. UNDECLARED, not inferred "
            "compliant."
        ),
    }


def fault_injection(mode: str, rec: dict[str, Any]) -> dict[str, Any]:
    injected = FAULTS[mode]
    if rec.get("status") != "EVIDENCED":
        return {
            "injected_fault": injected,
            "observable": "UNDEFINED",
            "note": (
                "A behaviour that cannot be described as an observable is recorded "
                "UNDEFINED rather than assumed graceful."
            ),
        }
    observables = {
        "partial_result": (
            "Bytes already produced remain on disk without a completion sentinel, "
            "or the write-as-you-go violation is visible as zero durable output."
        ),
        "hung_unit": (
            "Hung sibling classified STALLED; remaining units reach a terminal state."
        ),
        "timeout": "Unit terminal class is FAILED:timeout (or the named timeout class).",
        "dead_monitor": (
            "Worker is not declared dead solely because the monitor process died; "
            "heartbeat gap is the observable."
        ),
    }
    return {
        "injected_fault": injected,
        "observable": observables[mode],
        "note": "Sketch names the injected fault and the observable it would produce.",
    }


def extract_one(candidate: dict[str, Any]) -> dict[str, Any]:
    text, fields = defining_text(candidate)
    modes = {mode: _mode_record(text, mode) for mode in FOUR_MODES}
    wayg = write_as_you_go(text)
    sketches = {mode: fault_injection(mode, modes[mode]) for mode in FOUR_MODES}
    statuses = [modes[m]["status"] for m in FOUR_MODES]
    no_behaviour = all(s == "UNDEFINED" for s in statuses)
    for rec in modes.values():
        if str(rec.get("status") or "").upper() in FORBIDDEN_STATUSES:
            raise RuntimeError(f"extractor emitted forbidden status {rec['status']}")
        if rec.get("inferred_safe_default") is True:
            raise RuntimeError("extractor inferred a safe-default")
    return {
        "candidate_id": str(candidate.get("id") or ""),
        "family": candidate.get("family"),
        "name": candidate.get("name"),
        "corpus_tag": candidate.get("corpus_tag"),
        "origin": candidate.get("origin"),
        "provenance": candidate.get("provenance"),
        "defining_fields": fields,
        "modes": modes,
        "write_as_you_go": wayg,
        "fault_injection": sketches,
        "no_failure_behaviour": no_behaviour,
        "evidenced_mode_count": sum(1 for s in statuses if s == "EVIDENCED"),
        "undefined_mode_count": sum(1 for s in statuses if s == "UNDEFINED"),
    }


def extract_all(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [extract_one(c) for c in candidates]


def census(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_mode = {m: {"EVIDENCED": 0, "UNDEFINED": 0} for m in FOUR_MODES}
    wayg = {"VIOLATION": 0, "COMPLIANT": 0, "UNDECLARED": 0}
    none = 0
    by_tag: dict[str, int] = {}
    for row in rows:
        tag = str(row.get("corpus_tag") or "unknown")
        by_tag[tag] = by_tag.get(tag, 0) + 1
        if row.get("no_failure_behaviour"):
            none += 1
        w = (row.get("write_as_you_go") or {}).get("status")
        if w in wayg:
            wayg[w] += 1
        modes = row.get("modes") or {}
        for m in FOUR_MODES:
            st = (modes.get(m) or {}).get("status")
            if st in per_mode[m]:
                per_mode[m][st] += 1
    return {
        "n": len(rows),
        "no_failure_behaviour_n": none,
        "per_mode": per_mode,
        "write_as_you_go": wayg,
        "by_corpus_tag": by_tag,
        "four_modes_reported_separately": True,
        "aggregate_column_absent": True,
    }
