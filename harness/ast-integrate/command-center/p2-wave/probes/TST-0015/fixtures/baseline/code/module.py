"""Fixture module mirroring tools/command-center/validate.py require_complete.

The estate default is False. CI invokes the checker without passing the flag.
The unit test that claims to cover the default passes the flag explicitly.
"""
from __future__ import annotations


def check(payload: dict, *, require_complete: bool = False) -> list[str]:
    findings: list[str] = []
    if require_complete and not payload.get("complete"):
        findings.append("V-FIELDS")
    return findings


def bare_entry(payload: dict) -> list[str]:
    """CI-shaped call: never passes the flag."""
    return check(payload)
