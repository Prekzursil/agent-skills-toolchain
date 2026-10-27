#!/usr/bin/env python3
"""The normalized result envelope shared by all ten ``compute_*`` verbs.

Every verb returns the SAME shape so a caller never has to special-case a
provider: ``{ok, provider, handle?, kind?, id?, state?, ..., error?}``. A few
verbs add fields on top of that base -- ``compute_exec`` adds
``stdout``/``stderr``/``exit_code``; ``compute_cost`` adds
``balance``/``currency``/``spend_per_hr``/``note`` -- but the base contract is
constant.

Two safety gates also live here, because they are pure policy (no I/O):

* ``needs_confirm`` -- a destructive/billable action (terminate, delete) called
  without ``confirm=True`` is REFUSED with a ``would`` preview instead of run.
* ``dry_run`` -- ``compute_provision`` / ``compute_teardown`` with
  ``dry_run=True`` return the request that WOULD be sent, uncalled.
"""

from __future__ import annotations

from typing import Any


def ok(provider: str, **extra: Any) -> dict:
    """A success envelope for ``provider`` with any extra normalized fields."""
    return {"ok": True, "provider": provider, **extra}


def err(provider: str, error: str, **extra: Any) -> dict:
    """A failure envelope carrying a human-readable ``error`` string."""
    return {"ok": False, "provider": provider, "error": error, **extra}


def needs_confirm(provider: str, action: str, would: dict) -> dict:
    """Refuse an unconfirmed destructive/billable action, previewing ``would``.

    The caller re-issues the exact same call with ``confirm=True`` to proceed;
    ``would`` shows precisely what that will do.
    """
    return {
        "ok": False,
        "provider": provider,
        "error": f"{action} needs confirm=true (irreversible or billable)",
        "would": would,
    }


def dry_run(provider: str, action: str, request: dict, **extra: Any) -> dict:
    """Return the request an action WOULD issue, without calling the provider."""
    return {
        "ok": True,
        "provider": provider,
        "dry_run": True,
        "action": action,
        "request": request,
        **extra,
    }
