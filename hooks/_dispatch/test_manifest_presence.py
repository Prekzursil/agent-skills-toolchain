#!/usr/bin/env python3
"""A6 presence-test — the wired-dormant Stop gate must stay listed.

Guards against a manifest rebuild silently DROPPING the gate A6 wired in. Reads
the sibling ``manifest.json`` and asserts ``dark-surface`` appears under
``events.Stop.checks`` (mirroring the already-live ``journey-coverage`` entry;
``wire-check`` was live there too until the 2026-08-27 Stop rebalance moved it
to ``events.SessionStart`` -- see ``REBALANCED_TO_SESSIONSTART`` below), that
every Stop check names an existing script, and that the manifest stays
structurally sane.

SCOPE CORRECTION (2026-07-25). This file previously also listed
``test-tamper-guard`` in ``WIRED_BY_A6`` and asserted it under
``events.Stop.checks``. That claim is REFUTED — recorded here rather than
silently deleted, so the dead end is not re-walked:

* ``test-tamper-guard/guard.py`` is a **PreToolUse** hook that **exits 2 to
  BLOCK** the tool call (guard.py:2, :13, :299) and emits
  ``hookEventName: "PreToolUse"`` (guard.py:326). ``dispatch.py`` is
  inject-only and cannot honour exit 2, so ``test_wiring.py`` REQUIRES the
  gate to stay standalone (``REQUIRED_STANDALONE_HANDLERS["PreToolUse"]``,
  test_wiring.py:148-150; rationale :144-147). It already is — one standalone
  ``settings.json`` PreToolUse entry, matcher ``Bash``, timeout 20.
* Folding it into ``events.Stop.checks`` would silently DISARM the block and
  run a tool-call gate at session end, where there is no tool call to gate.
  That is a regression, not a fix.
* The original assertion never held anywhere: no commit on any ref has ever
  carried ``test-tamper-guard`` in ``_dispatch/manifest.json``.

``test_test_tamper_guard_is_not_a_dispatch_check`` below now asserts the
opposite, correct invariant — strictly stronger protection than the false one
it replaces.

Run:
    pytest hooks/_dispatch/test_manifest_presence.py -v

SCOPE CORRECTION (2026-10-17, blocking-mode wave). The invariant
"an exit-2 gate must never be folded into the dispatcher" assumed the
dispatcher was permanently inject-only. It no longer is: dispatch.py now runs
``exec``-mode checks as SUBPROCESSES whose real exit code, stderr and decision
JSON are propagated (exit-code BLOCK > JSON deny > allow/rewrite precedence;
pinned by test_blocking_mode.py). test-tamper-guard/guard.py, ulysses/enforce.py
and the other former standalone guards are therefore deliberately consolidated
as exec checks with ``blocking_rc: true``, which PRESERVES the block instead of
disarming it. The guard that still matters -- and that the test below now
enforces -- is the MODE contract: a known exit-2 gate may appear in the
manifest ONLY in exec mode with ``blocking_rc: true``; listing one as an
import-mode (in-process) check would fire its ``main()`` at import time under
the wrong argv and is still a silent disarm.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

MANIFEST = Path(__file__).resolve().parent / "manifest.json"

# The gate A6 wired out of dormancy. wire-check + journey-coverage were ALREADY
# live (Correction 1) and are intentionally NOT asserted here — A6 must not touch them.
# test-tamper-guard is deliberately ABSENT from this tuple: see the module docstring
# (it is an exit-2 PreToolUse gate that must stay standalone).
WIRED_BY_A6 = ("dark-surface",)

# Scripts that are known exit-2 BLOCKING gates. Since the 2026-10-17
# blocking-mode wave they MAY be consolidated into the dispatcher, but only in
# exec mode with blocking_rc (see test_blocking_gates_in_the_manifest_must_run_
# in_exec_blocking_mode); an import-mode entry still silently disarms them.
REQUIRED_STANDALONE_SCRIPTS = ("test-tamper-guard/guard.py",)

# A6 wired dark-surface at Stop but NOT its PostToolUse producer, so the gate was
# live-but-inert: dark-surface/check.py:190-202 reads <tmp>/edit-validate/<sid>.edits
# and returns [] on any missing file, and :217-230 only emits for a file in that
# list.  Its SOLE producer is edit-validate/record.py:19-40.  stub-ledger/report.py
# returns 0 on a completion-claim Stop turn to "defer to dark-surface", so while the
# producer was unregistered NEITHER half fired on exactly the turns that matter --
# the same GREEN-not-LIVE shape the dark-surface entry itself was added to catch.
# Route pinned to test_wiring.EXPECTED_DISPATCH_ROUTES["PostToolUse"].
DARK_SURFACE_PRODUCER = "edit-validate/record"
DARK_SURFACE_PRODUCER_SCRIPT = "edit-validate/record.py"
DARK_SURFACE_PRODUCER_MATCHER = "Edit|Write|MultiEdit"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _stop_checks() -> list[dict]:
    return _manifest()["events"]["Stop"]["checks"]


def _stop_check_names() -> list[str]:
    return [c.get("name") for c in _stop_checks()]


def test_manifest_is_valid_json():
    data = _manifest()
    assert isinstance(data, dict)
    assert "events" in data and "Stop" in data["events"]


@pytest.mark.parametrize("name", WIRED_BY_A6)
def test_wired_gate_present_under_stop(name):
    assert name in _stop_check_names(), f"{name} missing from events.Stop.checks"


def test_both_wired_gates_present():
    names = set(_stop_check_names())
    assert set(WIRED_BY_A6).issubset(names)


def test_wired_gate_entries_shape():
    by_name = {c["name"]: c for c in _stop_checks()}
    expected = {
        "dark-surface": {
            "script": "dark-surface/check.py",
            "emits": True,
            # NOT "none". The shadow gate appends a JSONL record to
            # ~/.agents/state/harness/shadow/shadow-<day>.jsonl (check.py:115-145),
            # whereas the neighbouring side_effect="none" Stop checks
            # (honest-signal, journey-coverage) write nothing at all.
            "side_effect": "shadow-sink",
            "isolate": None,
        },
    }
    for name in WIRED_BY_A6:
        entry = by_name[name]
        for field, value in expected[name].items():
            assert entry[field] == value, (
                f"{name}.{field}={entry[field]!r}, expected {value!r}"
            )


def test_blocking_gates_in_the_manifest_must_run_in_exec_blocking_mode():
    """A known exit-2 gate may be consolidated ONLY as exec + blocking_rc.

    guard.py:13/:299 exit 2 to BLOCK and :326 emits hookEventName "PreToolUse".
    Under the 2026-10-17 blocking-mode contract (see the module docstring and
    test_blocking_mode.py) that block SURVIVES consolidation when the check
    runs as a subprocess with its real exit code propagated. It is silently
    disarmed -- the defect this guard has always existed to catch -- when the
    entry is import-mode (no ``exec``), because the in-process worker cannot
    honour a bare ``sys.exit(main())`` argv/stdin contract, or when
    ``blocking_rc`` is absent, because main() then drops the non-zero rc.
    """

    data = _manifest()
    violations = []
    for event, spec in data["events"].items():
        by_script = {c.get("script"): c for c in spec.get("checks", [])}
        for banned in REQUIRED_STANDALONE_SCRIPTS:
            check = by_script.get(banned)
            if check is None:
                continue
            if not check.get("exec"):
                violations.append(
                    f"{banned} is an import-mode events.{event} check — the "
                    "exit-2 block is disarmed; exec mode is required"
                )
            if not check.get("blocking_rc"):
                violations.append(
                    f"{banned} lacks blocking_rc — main() would drop its "
                    "non-zero exit code"
                )
    assert not violations, "; ".join(violations)


def test_wired_gates_reference_existing_scripts():
    """hooks_root/<script> must exist on disk for each A6-wired gate."""
    data = _manifest()
    root = Path(data["hooks_root"])
    if not root.exists():
        pytest.skip(f"hooks_root not present in this context: {root}")
    by_name = {c["name"]: c for c in data["events"]["Stop"]["checks"]}
    for name in WIRED_BY_A6:
        script = by_name[name]["script"]
        assert (root / script).exists(), f"{name} -> {script} missing under {root}"


def test_stop_check_names_unique_and_nonempty():
    names = _stop_check_names()
    assert all(names), "every Stop check must have a non-empty name"
    assert len(names) == len(set(names)), "Stop check names must be unique"


def test_journey_coverage_producer_is_wired():
    """A wired CONSUMER whose only PRODUCER is unwired reports a false negative.

    ``journey-coverage/check.py`` is registered under ``events.Stop.checks`` and its
    docstring (check.py:14-16) names "the claim-guard Bash-exit ledger" as external
    signal #2; it reads that ledger in ``_ok_commands`` (check.py:144-162) and treats a
    missing file as ``[]``.  The ONLY writer of that ledger is
    ``claim-guard/ledger-write.py``.  While the writer was in no manifest event and no
    ``settings.json`` entry, ``_ok_commands`` always returned ``[]``, so a journey suite
    that had just passed was still reported as "NOT run this turn".

    Asserted explicitly (not derived from the manifest) so dropping the producer cannot
    make its own regression test pass.  ``matcher`` is pinned because the writer only
    records ``tool_name == "Bash"`` (ledger-write.py:177-179): a wider matcher would add
    invocations that record nothing, a narrower one records nothing at all.
    """
    post = _manifest()["events"]["PostToolUse"]["checks"]
    by_script = {c.get("script"): c for c in post}
    producer = by_script.get("claim-guard/ledger-write.py")
    assert producer is not None, (
        "journey-coverage is wired under events.Stop.checks but its ledger producer "
        "claim-guard/ledger-write.py is absent from events.PostToolUse.checks, so the "
        "Stop consumer can only ever see an empty ledger"
    )
    assert producer.get("matcher") == "Bash", (
        f"claim-guard/ledger-write matcher={producer.get('matcher')!r}, expected 'Bash'"
    )
    assert producer.get("emits") is False, (
        "claim-guard/ledger-write is record-only and must never inject context"
    )
    assert "journey-coverage" in _stop_check_names(), (
        "precondition: this contract only matters while the consumer is wired at Stop"
    )


def test_a6_did_not_touch_already_live_gates():
    """wire-check + journey-coverage were already live — they must remain registered.

    Until 2026-08-27 both sat under ``events.Stop``. The wave A-c rebalance (below) moved
    wire-check to ``events.SessionStart``; journey-coverage is one of the two Stop tail gates
    that rebalance exists to un-starve, so it stays exactly where it was.
    """
    assert "journey-coverage" in _stop_check_names()
    assert "wire-check" in _sessionstart_check_names()


# 2026-08-27 wave A-c, CONSOLIDATED-GEM-DECISIONS TIER-0 #2 (REC: ADOPT) executed as
# WAVE-ABCD-EXECUTION row A(c) DONE -- both records are tracked at .agents/*.md. The two
# measured-slow advisory checks were DEMOTED from Stop (35s ceiling, 9 checks whose budgets
# summed 144s, tail gates starved) to SessionStart, whose ceiling was raised 20 -> 35 IN
# LOCKSTEP with the settings.json dispatch entry so the moved budgets stay reachable. The
# repo manifest carried the pre-rebalance layout until PR #290 was reconciled (2026-09-01).
REBALANCED_TO_SESSIONSTART = {"wire-check": 25, "git-hygiene": 30}
STOP_TAIL_GATES = ("journey-coverage", "dark-surface")


def _sessionstart_check_names() -> list[str]:
    return [c.get("name") for c in _manifest()["events"]["SessionStart"]["checks"]]


def test_stop_rebalance_moved_slow_advisory_checks_to_sessionstart():
    """The rebalance is a MOVE, not a drop and not a duplicate.

    Each demoted check must be registered under SessionStart with the budget it had at Stop
    (``slow``, inject-only), and must be gone from Stop -- a copy left behind would put the
    oversubscription straight back. The two tail gates the move protects must still be at
    Stop, or the rebalance removed the cost and threw away the benefit.
    """
    start = {c["name"]: c for c in _manifest()["events"]["SessionStart"]["checks"]}
    stop_names = set(_stop_check_names())
    for name, budget in REBALANCED_TO_SESSIONSTART.items():
        assert name in start, f"{name} missing from events.SessionStart.checks"
        assert name not in stop_names, f"{name} still registered at Stop after the move"
        entry = start[name]
        assert entry["script"] == f"{name}/check.py"
        assert entry["timeout"] == budget, f"{name}.timeout={entry['timeout']!r}"
        assert entry["emits"] is True and entry["slow"] is True, entry
    for gate in STOP_TAIL_GATES:
        assert gate in stop_names, (
            f"tail gate {gate} left Stop; the rebalance was for it"
        )


def test_every_check_budget_fits_its_event_ceiling():
    """A per-check budget above its event's ``settings_timeout`` is INERT, not generous.

    dispatch.py:360-372 joins each check with an absolute deadline of start+timeout inside
    ONE dispatcher command that the vendor cancels at the event ceiling, so an over-ceiling
    budget holds run() past the cancellation point and every check on the event loses its
    output together (git-hygiene's own ``timeout_rationale``; hook_predeploy_gate L2). This
    is the invariant the rebalance had to preserve when it moved 25s and 30s budgets onto an
    event whose ceiling was 20s -- hence the lockstep raise to 35.
    """
    events = _manifest()["events"]
    over = [
        f"{event}/{c.get('name')}: {c.get('timeout')}s > {spec['settings_timeout']}s"
        for event, spec in events.items()
        for c in spec.get("checks", [])
        if isinstance(c.get("timeout"), (int, float))
        and c["timeout"] > spec["settings_timeout"]
    ]
    assert not over, "check budgets above their event ceiling:\n" + "\n".join(over)


def _posttooluse_checks() -> list[dict]:
    return _manifest()["events"]["PostToolUse"]["checks"]


def test_dark_surface_producer_is_wired_at_posttooluse():
    """A Stop consumer is INERT unless the producer of its input is registered too.

    Wiring dark-surface at Stop while leaving edit-validate/record unregistered
    left the gate permanently silent: no .edits file is ever written, so
    ``_edited_files`` returns [] on every turn and the stub scan has nothing to
    scan.  Asserting the consumer's presence alone cannot catch that -- this is
    the missing half.
    """
    assert "dark-surface" in set(_stop_check_names()), (
        "precondition: dark-surface must be the registered Stop consumer"
    )
    names = [c.get("name") for c in _posttooluse_checks()]
    assert DARK_SURFACE_PRODUCER in names, (
        f"{DARK_SURFACE_PRODUCER!r} missing from events.PostToolUse.checks, so "
        "dark-surface at Stop can never see an edited file and is wired-but-inert "
        f"(PostToolUse currently registers {names})"
    )


def test_dark_surface_producer_route_matches_its_consumer():
    """The producer must fire on exactly the file-editing tools dark-surface reads.

    A narrower matcher (e.g. ``Write``) would silently drop Edit/MultiEdit paths
    from the .edits feed and re-open the same blind spot for those tools only.
    """
    check = next(
        (c for c in _posttooluse_checks() if c.get("name") == DARK_SURFACE_PRODUCER),
        None,
    )
    assert check is not None, f"{DARK_SURFACE_PRODUCER!r} not registered"
    assert check.get("script") == DARK_SURFACE_PRODUCER_SCRIPT
    assert set((check.get("matcher") or "").split("|")) == set(
        DARK_SURFACE_PRODUCER_MATCHER.split("|")
    ), f"producer matcher {check.get('matcher')!r} must cover Edit|Write|MultiEdit"
    assert check.get("emits") is False, (
        "the producer only appends to a file; it must not claim to emit context"
    )


def test_dark_surface_producer_script_exists_in_this_tree():
    """The registered script must exist beside the manifest, not only on the host.

    ``test_wired_gates_reference_existing_scripts`` resolves ``hooks_root``, which
    is an absolute live Windows path and is skipped everywhere else -- so on CI
    nothing checked that the newly wired script is actually in the repo.
    """
    assert (MANIFEST.parent.parent / DARK_SURFACE_PRODUCER_SCRIPT).is_file()
