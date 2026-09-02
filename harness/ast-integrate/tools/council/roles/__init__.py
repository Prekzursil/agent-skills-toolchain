"""Council role package: mandates, the runtime guard and the template registry.

Submodules (import them explicitly; this package only names them):

* ``mandate``   -- point-of-use enforcement of the five rights (IMP-0280):
  ``speaking``, ``vote``, ``tool_access``, ``source_access``, ``veto``.
* ``guard``     -- runtime role-enforcement guard, use-vs-mention aware (IMP-0281).
* ``templates`` -- builtin role templates, custom-role authoring, rights-escalation
  and template-drift detectors (IMP-0360).

The package resolves both as ``council.roles`` (through the repo-root ``council``
``__path__`` shim) and as ``tools.council.roles``; the submodules use relative
imports so either spelling yields one coherent package.
"""
from __future__ import annotations

__all__ = ["guard", "mandate", "templates"]
