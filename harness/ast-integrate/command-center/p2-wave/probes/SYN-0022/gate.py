"""Independence gate fixtures for SYN-0022 (CNF-0006 tuple)."""
from __future__ import annotations

from cnf0006_fingerprint import (
    INDEPENDENT,
    SAME_PROBE_RERUN,
    UNDECLARED_SOURCE,
    close_verdict,
    fingerprint_hex,
    pair_status,
)

SOURCE_READY = {
    "tool": "node",
    "shell": "none",
    "data_field": "ready_population",
    "measurement_kind": "JSON field read",
}
VERIFIER_PS = {
    "tool": "pwsh",
    "shell": "powershell",
    "data_field": "ready_population",
    "measurement_kind": "JSON field read",
}


def same_fingerprint_control() -> dict:
    status = pair_status(SOURCE_READY, dict(SOURCE_READY))
    closed = close_verdict(status, "CONFIRMED")
    ok = status == SAME_PROBE_RERUN and closed != "CONFIRMED"
    return {
        "id": "test_source_and_verifier_probe_fingerprints_differ",
        "status": status,
        "closed_verdict": closed,
        "source_fingerprint": fingerprint_hex(SOURCE_READY),
        "verifier_fingerprint": fingerprint_hex(SOURCE_READY),
        "accepted_as_confirmed": False,
        "pass": ok,
    }


def empty_source_control() -> dict:
    verifier = {
        "tool": "python3",
        "shell": "python3",
        "data_field": "json.state",
        "measurement_kind": "SUCCESS-count",
    }
    status = pair_status({}, verifier)
    closed = close_verdict(status, "CONFIRMED")
    ok = status == UNDECLARED_SOURCE and closed == "VIOLATION"
    return {
        "id": "test_a_record_with_an_empty_source_probe_is_a_VIOLATION_not_a_pass",
        "status": status,
        "closed_verdict": closed,
        "pass": ok,
    }


def distinct_fingerprint_control() -> dict:
    status = pair_status(SOURCE_READY, VERIFIER_PS)
    closed = close_verdict(status, "CONFIRMED")
    ok = (
        status == INDEPENDENT
        and fingerprint_hex(SOURCE_READY) != fingerprint_hex(VERIFIER_PS)
        and closed == "CONFIRMED"
    )
    return {
        "id": "distinct_fingerprint_accepted",
        "status": status,
        "closed_verdict": closed,
        "source_fingerprint": fingerprint_hex(SOURCE_READY),
        "verifier_fingerprint": fingerprint_hex(VERIFIER_PS),
        "pass": ok,
    }


def run_gate_controls() -> dict:
    same = same_fingerprint_control()
    empty = empty_source_control()
    distinct = distinct_fingerprint_control()
    return {
        "same_fingerprint_rejected": same["pass"] is True,
        "empty_source_is_violation": empty["pass"] is True,
        "distinct_fingerprint_accepted": distinct["pass"] is True,
        "details": {"same": same, "empty": empty, "distinct": distinct},
    }
