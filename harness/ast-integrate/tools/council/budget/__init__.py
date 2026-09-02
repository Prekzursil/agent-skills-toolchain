"""Council budget package: the CNL-0008 budget dials as four independent modules.

Each dial lives in its own submodule; import the submodule directly, as every
probe and ``tools/council/cli/runtime.py`` do:

* ``council.budget.engagement`` -- minimum-engagement floor and speaking-ceiling
  tracker measured in content units, not message count (IMP-0299 / ADV-0094):
  ``EngagementPolicy``, ``EngagementTracker``, ``score_text``,
  ``apply_eviction_handoff``.
* ``council.budget.governor`` -- per-dimension budget governor that stops a run and
  stamps ``BUDGET_EXHAUSTED`` on the partial output (IMP-0298): ``BudgetGovernor``,
  ``run_fixture``, ``marker_is_load_bearing``, ``governor_token_count``.
* ``council.budget.preflight`` -- owner cost ceiling / approval gate evaluated before
  a council starts (IMP-0352): ``CouncilPlan``, ``OwnerCeiling``, ``OwnerApproval``,
  ``estimate_cost``, ``calibrate``, ``preflight``.
* ``council.budget.transport`` -- independent UTF-8 ceil-div-4 token estimate used to
  cross-check the governor's whitespace-word count (IMP-0298):
  ``transport_token_count``.

The package deliberately exports only its submodule names. A package-level
``__getattr__`` would shadow the real submodules under the repo-root ``council``
``__path__`` shim, and eager re-exports would make importing one dial import all four.
"""
from __future__ import annotations

__all__ = ["engagement", "governor", "preflight", "transport"]
