"""foundry - the executable Workflow Foundry: ``workflow-scout`` and ``workflow-forge``.

Spec anchor: ``_USER-PROMPTS.md:11025`` ("Ship ``workflow-scout`` and ``workflow-forge`` as
executable meta-workflows") and ``:11282`` (the acceptance bar - a merged workflow is NOT
accepted because it contains more stages).

Modules
-------
* :mod:`foundry.model`       - the canonical capability + hazard vocabularies, loaded from
                              ``platform/schema/workflow-dsl.capability-map.json`` so there is
                              exactly ONE mechanism namespace in the program.
* :mod:`foundry.registry`    - normalizes the five heterogeneous
                              ``platform/registry/workflow-candidates-N.json`` shapes and the
                              live ``platform/workflows/*.json`` DSL corpus into one record type.
* :mod:`foundry.mechanisms`  - mechanism decomposition, semantic diff, duplicate collapse.
* :mod:`foundry.bench`       - the four spec axes (correctness / coverage / recovery / usability)
                              computed by deterministic predicates over a DSL document, plus a
                              cost vector that is deliberately NOT a benefit axis.
* :mod:`foundry.scout`       - CLI: search, verify provenance + license, decompose, recommend.
* :mod:`foundry.forge`       - CLI: fuse, benchmark, certify-or-REJECT, emit, decompose-back.

Nothing here reaches the network. Every artifact this package emits is a pure function of its
inputs: there is no wall-clock timestamp anywhere, so two runs over the same tree are
byte-identical and a diff means an input changed.
"""

from __future__ import annotations

__all__ = ["bench", "forge", "mechanisms", "model", "registry", "scout"]

__version__ = "1.0.0"
