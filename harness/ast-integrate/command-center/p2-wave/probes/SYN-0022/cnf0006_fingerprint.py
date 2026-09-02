"""CNF-0006 probe fingerprint: (tool, shell, data_field, measurement_kind).

CNF-0006's confirmation-corpus implementation is absent on this worktree
(command-center/confirmation/CNF-0006-probe-independence.json is not on disk).
This module is the catalog-specified tuple, not a fifth axis. Pair status is
computed BEFORE hex comparison so an empty source cannot 'differ' from a
verifier by hashing to a different empty-string tuple.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

AXES = ("tool", "shell", "data_field", "measurement_kind")
ALIASES = {
    "tool": "tool",
    "shell": "shell",
    "data_field": "data_field",
    "field": "data_field",
    "measurement_kind": "measurement_kind",
    "kind": "measurement_kind",
}

UNDECLARED_SOURCE = "UNDECLARED-SOURCE"
UNDECLARED_VERIFIER = "UNDECLARED-VERIFIER"
SAME_PROBE_RERUN = "SAME-PROBE-RERUN"
INDEPENDENT = "INDEPENDENT"


def canonical_probe(probe: Any) -> dict[str, str]:
    out = {axis: "" for axis in AXES}
    if not isinstance(probe, dict):
        return out
    for key, value in probe.items():
        axis = ALIASES.get(str(key))
        if axis is None:
            continue
        out[axis] = str(value or "").strip()
    return out


def as_tuple(probe: Any) -> tuple[str, str, str, str]:
    can = canonical_probe(probe)
    return tuple(can[axis] for axis in AXES)  # type: ignore[return-value]


def is_declared(probe: Any) -> bool:
    return all(axis != "" for axis in as_tuple(probe))


def fingerprint_hex(probe: Any) -> str:
    payload = json.dumps(canonical_probe(probe), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def pair_status(source: Any, verifier: Any) -> str:
    """Independence of a pair. Empty source is zero signals, never 'differs'."""
    if not is_declared(source):
        return UNDECLARED_SOURCE
    if not is_declared(verifier):
        return UNDECLARED_VERIFIER
    if as_tuple(source) == as_tuple(verifier):
        return SAME_PROBE_RERUN
    return INDEPENDENT


def close_verdict(status: str, content_verdict: str) -> str:
    """A rerun must never be CONFIRMED. An undeclared source is a VIOLATION."""
    if status == UNDECLARED_SOURCE:
        return "VIOLATION"
    if status == UNDECLARED_VERIFIER:
        return "VIOLATION"
    if status == SAME_PROBE_RERUN:
        return "NOT-CHECKED"
    return content_verdict
