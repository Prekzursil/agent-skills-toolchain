"""Planted error/rollback product for BLD-0045 covered-but-unasserted controls."""

from __future__ import annotations

SIDE_LOG: list[tuple[str, int]] = []


def side_effect_only(x: int) -> int:
    """Called for its append side effect; the suite never asserts the return."""
    SIDE_LOG.append(("side", x))
    return x * 2


def asserted_value(x: int) -> int:
    """Return is load-bearing: a test feeds it into assert."""
    return x + 1


class RollbackError(Exception):
    """Commit failed; apply_with_rollback must unwind."""


def apply_with_rollback(payload: dict, fail: bool = False) -> dict:
    """Try-commit then except-rollback. Except-arm effects are unasserted by design."""
    ledger = {
        "committed": False,
        "rolled_back": False,
        "payload": dict(payload),
        "error": None,
    }
    try:
        if fail:
            raise RollbackError("commit-failed")
        ledger["committed"] = True
        return ledger
    except RollbackError as exc:
        ledger["committed"] = False
        ledger["rolled_back"] = True
        ledger["error"] = type(exc).__name__
        ledger["payload"] = {}
        return ledger


def maybe_double(flag: bool, n: int) -> int:
    """Two-arm if. The suite takes only the True arm so branch coverage must show partial."""
    if flag:
        return n * 2
    else:
        return n
