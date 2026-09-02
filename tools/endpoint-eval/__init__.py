"""Endpoint eval harness (WU-4): T0 graders, T1 contract suite, T2/T3 definitions, scorer.

The directory name carries a hyphen, so nothing imports this package by name. Tests and
the CLIs put ``tools/endpoint-eval`` on ``sys.path`` and import the flat modules
(``graders.*``, ``fake_endpoint``, ``contract_suite``, ``capability_suite``,
``score_policy``).
"""

from __future__ import annotations
