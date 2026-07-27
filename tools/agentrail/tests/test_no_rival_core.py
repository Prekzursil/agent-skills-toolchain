"""ANTI-DUPLICATION -- proven mechanically, not promised in prose.

The lane this package was built in had one named failure mode: building a RIVAL core beside
agentspec instead of consuming it. These tests walk agentrail's own source and fail on any
redeclaration of a name agentspec owns, and they check the two properties the brief singles
out -- reason strings are a SUBSET of the closed taxonomy, and the argv cap is IMPORTED.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentspec import argv as spec_argv
from agentspec import oracle as spec_oracle
from agentspec import taxonomy as spec_taxonomy
from agentspec.argv import PROMPT_TRANSPORTS, WINDOWS_CMDLINE_CAP, RailSpec
from agentspec.taxonomy import REASONS, family

import agentrail
from agentrail import plan as rail_plan
from agentrail import rails as rail_rails
from agentrail import report as rail_report
from rival_scan import (
    OWNED_CONSTANTS,
    OWNED_FUNCTIONS,
    OWNED_TYPES,
    imported_names,
    rival_declarations,
)

PACKAGE_ROOT = Path(agentrail.__file__).parent
SOURCE_FILES = tuple(sorted(PACKAGE_ROOT.rglob("*.py")))


def test_the_package_has_source_to_scan() -> None:
    """A scanner that silently found nothing to scan would be a broken detector."""
    assert len(SOURCE_FILES) >= 8
    assert {path.name for path in SOURCE_FILES} >= {
        "rails.py",
        "resolve.py",
        "plan.py",
        "report.py",
        "runner.py",
        "cli.py",
    }


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda path: path.name)
def test_no_module_redeclares_anything_agentspec_owns(path: Path) -> None:
    rivals = rival_declarations(path.read_text(encoding="utf-8"), path.name)
    assert rivals == (), "\n".join(str(rival) for rival in rivals)


def test_the_argv_cap_is_imported_and_identical_not_re_typed() -> None:
    """The number 32767 is measured; a second copy of it is a drift hazard."""
    source = (PACKAGE_ROOT / "rails.py").read_text(encoding="utf-8")
    assert "WINDOWS_CMDLINE_CAP" in imported_names(source, "rails.py", "agentspec")
    assert rail_rails.WINDOWS_CMDLINE_CAP is WINDOWS_CMDLINE_CAP
    assert rail_rails.RailRow(name="x").cap == spec_argv.WINDOWS_CMDLINE_CAP


def test_the_rail_type_is_agentspecs_own_class() -> None:
    built = rail_rails.RailRow(name="x").rail_spec("exe", transport="stdin")
    assert type(built) is RailSpec
    assert type(built).__module__ == "agentspec.argv"


def test_every_reason_agentrail_can_originate_is_in_the_closed_taxonomy() -> None:
    assert set(rail_report.AGENTRAIL_REASONS) <= set(REASONS)
    assert rail_report.AGENTRAIL_REASONS == tuple(sorted(rail_report.AGENTRAIL_REASONS))


def test_every_inline_reason_in_the_source_resolves_to_a_taxonomy_member() -> None:
    """Catches a reason minted inline, which the AGENTRAIL_REASONS tuple alone would miss.

    Scans the reason FIELD -- the argument actually passed as a reason, and every class-level
    ``reason`` attribute -- not every string in the file. An earlier draft matched any
    hyphenated literal and flagged ``"utf-8"``: a use-vs-mention error, and a detector that
    fires in the good state is as broken as one that stays silent in the bad state.
    """
    found: list[tuple[str, str]] = []
    for path in SOURCE_FILES:
        for literal in _reason_fields(path.read_text(encoding="utf-8")):
            found.append((path.name, literal))
            assert family(literal), f"{path.name}: {literal!r} is not a taxonomy member"
    assert found, "the reason-field scanner found nothing to check"


def test_the_inline_reason_scanner_would_catch_a_minted_reason() -> None:
    """The detector control: prove the scanner sees a bad reason before trusting its silence.

    ``resolution_failure`` is in here because it was MISSING from ``REASON_SINKS``: its reason
    is the THIRD positional, the old index rule could only express 0 or 1, and an injected
    ``resolution_failure(unit_id, "codex", "rail-was-grumpy", tried=())`` left the gate green.
    Every sink is now driven at its declared index, so a new one cannot be half-added.
    """
    minted = _reason_fields(
        'transport_failure("u1", "rail-was-grumpy", detail="d")\n'
        'resolution_failure("u1", "codex", "rail-was-sulky", tried=())\n'
        'failure_line("u1", "rail-was-quiet")\n'
        'plan_retry("rail-was-tired", attempt=1)\n'
        'class Boom(ValueError):\n    reason = "totally-invented"\n'
    )
    assert set(minted) == {
        "rail-was-grumpy",
        "rail-was-sulky",
        "rail-was-quiet",
        "rail-was-tired",
        "totally-invented",
    }
    assert not any(family(literal) for literal in minted)


def test_every_declared_reason_sink_is_a_real_callable_at_its_declared_index() -> None:
    """A watchlist entry naming a function that does not exist would pass forever.

    Checks the NAME resolves and that the declared index is inside the callable's real
    positional signature -- the two ways this table can be wrong without anything going red.
    """
    import inspect

    from agentspec.retry import plan_retry
    from agentspec.terminal import failure_line

    from agentrail.report import resolution_failure, transport_failure

    resolved = {
        "transport_failure": transport_failure,
        "failure_line": failure_line,
        "resolution_failure": resolution_failure,
        "plan_retry": plan_retry,
    }
    assert set(resolved) == set(REASON_SINKS), (
        "every sink must be resolved and checked here"
    )
    for name, func in resolved.items():
        positional = [
            parameter
            for parameter in inspect.signature(func).parameters.values()
            if parameter.kind
            in {parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD}
        ]
        index = REASON_SINKS[name]
        assert index < len(positional), f"{name}: index {index} is out of range"
        assert "reason" in positional[index].name, (
            f"{name}: positional {index} is {positional[index].name!r}, not the reason"
        )


def test_the_transport_enum_is_agentspecs_and_is_not_widened() -> None:
    assert rail_rails.PROMPT_TRANSPORTS is PROMPT_TRANSPORTS
    assert PROMPT_TRANSPORTS == ("file", "stdin")
    assert "argv" not in PROMPT_TRANSPORTS
    assert set(PROMPT_TRANSPORTS) < set(rail_rails.NATIVE_TRANSPORTS), (
        "NATIVE_TRANSPORTS describes what a vendor CLI wants; it must never leak into the "
        "transports agentrail is allowed to use"
    )


def test_the_completion_gate_and_retry_come_from_agentspec() -> None:
    plan_source = (PACKAGE_ROOT / "plan.py").read_text(encoding="utf-8")
    report_source = (PACKAGE_ROOT / "report.py").read_text(encoding="utf-8")
    assert {"build_for_rail", "plan_retry"} <= imported_names(
        plan_source, "plan.py", "agentspec"
    )
    assert {"judge", "observe"} <= imported_names(
        report_source, "report.py", "agentspec"
    )
    assert rail_report.judge is spec_oracle.judge
    assert rail_plan.plan_retry.__module__ == "agentspec.retry"


def test_the_win_arg_limit_label_is_a_real_taxonomy_member() -> None:
    assert rail_plan.WIN_ARG_LIMIT in REASONS
    assert spec_taxonomy.is_reason(rail_plan.WIN_ARG_LIMIT)


def test_the_scanner_watches_names_that_actually_exist_in_agentspec() -> None:
    """A watchlist of typos would pass forever. Every entry must resolve in agentspec."""
    modules = (
        "argv",
        "oracle",
        "taxonomy",
        "envelope",
        "retry",
        "spec",
        "terminal",
        "progress",
        "dispatchpolicy",
        "validate",
        "clock",
    )
    available: set[str] = set()
    for name in modules:
        module = __import__(f"agentspec.{name}", fromlist=["_"])
        available.update(vars(module))
    missing = (OWNED_CONSTANTS | OWNED_TYPES | OWNED_FUNCTIONS) - available
    assert missing == set(), f"watchlist names absent from agentspec: {sorted(missing)}"


REASON_SINKS: dict[str, int] = {
    "transport_failure": 1,
    "failure_line": 1,
    "resolution_failure": 2,
    "plan_retry": 0,
}
"""Callables that CONSUME a reason, mapped to the POSITIONAL INDEX it arrives at.

Two repairs, both measured:

* Was a set plus an inline ``index = 1 if name in {...} else 0``, which could not express a
  third position -- so ``resolution_failure(unit_id, rail_name, reason, ...)`` was omitted and
  an injected ``resolution_failure(u, "codex", "rail-was-grumpy", tried=())`` left this gate
  GREEN. Nothing could actually ship one (``transport_failure`` raises ``UnknownReason`` at
  runtime), but a static gate advertising defence-in-depth it does not have is worse than no
  gate, because it is trusted.
* ``rail_exit`` was listed and is NOT a sink: ``agentspec.taxonomy.rail_exit(exit_code: int)``
  PRODUCES a reason from an int. A watchlist entry that can never match is the same class of
  fake coverage as the row above, pointing the other way.
"""


def _reason_fields(source: str) -> tuple[str, ...]:
    """Every string literal used AS a reason: the reason argument, and ``reason`` attributes."""
    import ast

    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            found.extend(_reason_arg(node))
        elif isinstance(node, ast.Assign):
            found.extend(_reason_attribute(node))
    return tuple(found)


def _reason_arg(node: object) -> tuple[str, ...]:
    import ast

    assert isinstance(node, ast.Call)
    name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
    if name not in REASON_SINKS:
        return ()
    index = REASON_SINKS[name]
    if len(node.args) <= index:
        return ()
    candidate = node.args[index]
    if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
        return (candidate.value,)
    return ()


def _reason_attribute(node: object) -> tuple[str, ...]:
    import ast

    assert isinstance(node, ast.Assign)
    if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
        return ()
    return tuple(
        node.value.value
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "reason"
    )
