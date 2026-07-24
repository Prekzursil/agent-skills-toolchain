#!/usr/bin/env python3
"""Mechanical acceptance test for the vendored governed-run orchestrator template.

Asserts three things the workflow-authoring adoption promised (DOD-03):

  1. ``templates/governed-run-orchestrator.md`` is the PRISTINE reusable template,
     not a filled instance: it still carries the ``<GOAL>``/``<DoD>`` slot tags, the
     unfilled bracketed instructional sentinels, the ``## MAIN INSTRUCTION BODY``
     heading, and at least one ``- DOD-NN | State:`` row.
  2. The vendored file carries a provenance header naming its frozen source sha.
  3. ``SKILL.md`` has the "Governed single-shot run" section that links the template
     with a relative path, and that link target exists on disk.

Stdlib-only and location-independent (paths are resolved relative to this file), so
the byte-identical copy under both dual-write roots (``skills/`` and ``.agents/skills/``)
passes unchanged. Runnable two ways:

    python test_governed_run_template.py     # standalone: prints PASS/FAIL, exits 0/1
    pytest test_governed_run_template.py      # discovered as test_* functions
"""

from __future__ import annotations

import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
RELATIVE_LINK = "templates/governed-run-orchestrator.md"
TEMPLATE = SKILL_DIR / "templates" / "governed-run-orchestrator.md"
SKILL_MD = SKILL_DIR / "SKILL.md"
SECTION_HEADING = "## Governed single-shot run"
FROZEN_SHA = "c38cabd29348812ef19efef27f838252dc452d162b50fead07c6d875c0fe1515"

# Slot-only bracketed placeholders that a PRISTINE (unfilled) template retains but a filled
# instance replaces with real prose. Each is verified to live ONLY inside a <GOAL>/<DoD> slot
# (absent from a filled instance), so requiring all three makes this test reject a filled
# instance: one from the GOAL slot, one from a DoD State cell, one from a DoD Evidence cell.
UNFILLED_SENTINELS = (
    "[State one durable end-state in imperative, outcome language.]",
    "[One externally observable final condition.]",
    "[first signal/source.]",
)


def _template_text() -> str:
    assert TEMPLATE.is_file(), f"vendored template missing: {TEMPLATE}"
    return TEMPLATE.read_text(encoding="utf-8")


def _skill_text() -> str:
    assert SKILL_MD.is_file(), f"SKILL.md missing: {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


def test_template_exists() -> None:
    assert TEMPLATE.is_file(), f"vendored template missing: {TEMPLATE}"


def test_template_retains_goal_dod_slots() -> None:
    text = _template_text()
    for tag in ("<GOAL>", "</GOAL>", "<DoD>", "</DoD>"):
        assert tag in text, (
            f"template lost the {tag} slot tag (not a reusable template)"
        )


def test_template_slots_are_unfilled() -> None:
    text = _template_text()
    for sentinel in UNFILLED_SENTINELS:
        assert sentinel in text, (
            f"template is missing the unfilled sentinel {sentinel!r} "
            "-- a filled instance was vendored instead of the pristine template"
        )


def test_template_has_main_instruction_body() -> None:
    assert "## MAIN INSTRUCTION BODY" in _template_text(), (
        "template is missing the '## MAIN INSTRUCTION BODY' section heading"
    )


def test_template_has_dod_nn_rows() -> None:
    assert re.search(r"(?m)^- DOD-\d{2} \| State:", _template_text()), (
        "template has no '- DOD-NN | State:' row -- the DoD slot format was lost"
    )


def test_template_has_provenance_header() -> None:
    text = _template_text()
    assert FROZEN_SHA in text, "provenance header is missing the frozen source sha256"
    assert "final-workflow-prompt.TEMPLATE.md" in text, (
        "provenance header does not name its source path"
    )


def test_skill_md_has_section_and_relative_link() -> None:
    text = _skill_text()
    assert SECTION_HEADING in text, (
        f"SKILL.md is missing the {SECTION_HEADING!r} section"
    )
    assert RELATIVE_LINK in text, (
        f"SKILL.md does not link the template with the relative path {RELATIVE_LINK!r}"
    )


def test_skill_md_link_target_exists() -> None:
    target = SKILL_DIR / RELATIVE_LINK
    assert target.is_file(), f"SKILL.md link target does not exist on disk: {target}"


def _main() -> int:
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:  # noqa: PERF203 - report every failure, do not stop
            failures += 1
            print(f"FAIL  {test.__name__}: {exc}")
        else:
            print(f"PASS  {test.__name__}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
