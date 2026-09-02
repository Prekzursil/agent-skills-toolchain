"""Planted mtime-only classifier (known-broken control).

Reads timeout as SUCCESS and old mtime as STALLED. Probe 1 must catch both.
"""
from __future__ import annotations

from classify import FAILED, FINISHED, STALLED, SUCCESS, Observation


def classify_mtime_only(obs: Observation) -> str:
    if obs.timed_out:
        return SUCCESS
    age = obs.mtime_age_s
    window = obs.stall_window_s
    if age is not None and window > 0 and age > window:
        return STALLED
    if obs.exit_code == 0:
        return SUCCESS
    if obs.orchestrator_state == "FINISHED":
        return FINISHED
    return FAILED
