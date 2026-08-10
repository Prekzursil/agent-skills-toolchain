"""End-to-end tests for the executable workflow blueprints in ``platform/workflows``.

This package holds the FLAGSHIP test suites. The spec requires at least 40 of the 96 built-in
blueprints to be flagship with full end-to-end tests (``_USER-PROMPTS.md:10898``); a flagship
suite here is not a schema re-check - ``_validate_blueprints.py`` already does that for every
document. A flagship suite asserts the blueprint's own LOAD-BEARING MECHANISM, and every such
assertion ships with a both-states control: the predicate must hold on the shipped blueprint AND
fail on a targeted mutant. A predicate that passes in both states measures nothing.
"""
