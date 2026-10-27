"""Phase 9 - multi-session and cross-vendor coordination.

Spec: ``C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10965-10983``.

The eleven required surfaces and where each lives:

  ============================================  =======================================
  session discovery                             :mod:`coordination.session`
  work claims                                   :mod:`coordination.claims`
  file leases                                   :mod:`coordination.leases`
  conflict detection                             :mod:`coordination.leases`
  duplicate-work suppression                     :mod:`coordination.claims`
  crash recovery                                 :mod:`coordination.recovery`
  handoff                                        :mod:`coordination.handoff`
  shared completion reducer (DELEGATED)          :mod:`coordination.reducer`
  capability negotiation                         :mod:`coordination.capability`
  vendor-specific adapter boundaries             :mod:`coordination.adapters`
  abstraction leaks (documented)                 ``ABSTRACTION-LEAKS.md``
  ============================================  =======================================

Supporting: :mod:`coordination.store` (atomic records + journal), :mod:`coordination.oslock` (the
second liveness signal), :mod:`coordination.dispatch` (the completion AND-gate and the dispatch
plan audit that resolves the estate's three-way transport contradiction),
:mod:`coordination.errors`.

The completion predicate is NOT re-implemented here. ``coordination.reducer`` delegates to
``platform/lib/completion_predicate.py`` and ships :func:`coordination.reducer.assert_single_reducer`
to keep it that way.

Import as a top-level package with ``platform/`` on ``sys.path`` (see ``conftest.py``); there is
deliberately no ``platform/__init__.py``, because a real package named ``platform`` would shadow
the standard library module.
"""

from __future__ import annotations

__all__ = [
    "adapters",
    "capability",
    "claims",
    "dispatch",
    "errors",
    "handoff",
    "leases",
    "oslock",
    "recovery",
    "reducer",
    "session",
    "store",
]
