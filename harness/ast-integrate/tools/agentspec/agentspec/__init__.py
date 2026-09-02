"""agentspec — the portable agent-workflow SPEC and the dispatch-safety pure core.

This package is the SINGLE SOURCE OF TRUTH for:

* the vendor-neutral workflow / work-unit SPEC (:mod:`agentspec.spec`, validated by
  :mod:`agentspec.validate`) — any runtime or vendor adapter TRANSLATES to this, so two
  runtimes cannot diverge into rival dialects;
* the shared OBSERVATION ENVELOPE (:mod:`agentspec.envelope`);
* the closed failure TAXONOMY (:mod:`agentspec.taxonomy`);
* DISPATCH SAFETY as pure functions — argv/prompt transport (:mod:`agentspec.argv`), the
  completion AND-gate (:mod:`agentspec.oracle`), progress-stream rejection
  (:mod:`agentspec.progress`), terminal markers (:mod:`agentspec.terminal`), budget
  accounting (:mod:`agentspec.budget`) and the determinism self-check
  (:mod:`agentspec.determinism`).

It is the SINGLE HOME for dispatch safety. A consumer (a runtime, a vendor adapter, a
monitor) imports these functions; it must NOT reimplement them.

Nothing here performs I/O, spawns a process, reads a clock or draws entropy. Time enters
through the injected :class:`agentspec.clock.Clock` port, and
:func:`agentspec.determinism.scan_package` fails the gate if a forbidden time/random call
appears anywhere in this package.
"""

from __future__ import annotations

SPEC_VERSION = "1"
"""The only spec version this package accepts. Bumping it is a reviewed diff."""
