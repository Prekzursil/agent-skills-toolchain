"""agentrail -- the CONFIG-DRIVEN multi-rail dispatch shell over :mod:`agentspec`.

agentrail is the CONSUMER of agentspec and the proof that the spec is vendor-neutral. It
reimplements nothing agentspec already owns:

===============================  =======================================================
concern                          owner
===============================  =======================================================
completion AND-gate              :func:`agentspec.oracle.judge`
closed failure taxonomy          :data:`agentspec.taxonomy.REASONS`
argv cap + prompt routing        :func:`agentspec.argv.build_argv`, ``WINDOWS_CMDLINE_CAP``
win-arg-limit one-shot retry     :func:`agentspec.retry.plan_retry`
result envelope                  :mod:`agentspec.envelope`
terminal markers                 :func:`agentspec.terminal.terminal_line`
progress-stream rejection        :func:`agentspec.progress.classify`
pre-dispatch policy              :func:`agentspec.dispatchpolicy.check_dispatch`
rail declaration type            :class:`agentspec.argv.RailSpec`
===============================  =======================================================

``tests/test_no_rival_core.py`` proves that mechanically, by walking this package's own AST
and failing on any redeclaration of those names.

This module exports ONE constant, mirroring agentspec's import discipline: everything else is
imported from its submodule, so no name has two homes.
"""

from __future__ import annotations

CONFIG_VERSION = "1"
"""The only ``rails.toml`` config version this package accepts."""
