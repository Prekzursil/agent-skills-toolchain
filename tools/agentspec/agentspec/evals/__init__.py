"""agentspec.evals — the HERMETIC eval registry.

A parametrised registry of executable rows (NOT a markdown checklist), run against an
in-process FAKE agent rail with an INJECTED clock. Zero network, zero real vendor calls, so
CI stays hermetic.

Rows are addressed by id. The regression rows R1-R6 and R8 each encode a MEASURED past
failure and go RED if the protection is removed — that is asserted mechanically by
``tests/test_mutations.py``, which swaps a deliberately-broken implementation into the
injected :class:`agentspec.evals.registry.Impl` bundle and requires the row to fail.

Live rows (a real rail) are OPT-IN: they carry ``live=True``, are excluded by
:func:`agentspec.evals.registry.run_all` unless ``include_live=True``, and are deselected by
pytest unless ``--run-live`` is passed (see :mod:`agentspec.evals.pytest_live`).
"""

from __future__ import annotations
