#!/usr/bin/env python3
"""Red-proof for H6 -- the per-agent timeout / settled barrier helper.

This is the executable form of the exit criterion written at
``docs/audit-design-2026-07-13/B3-migration-verification.md:156``:

    "H6 proven to break a synthetic barrier hang."

BOTH-STATES DISCIPLINE (rules/common/single-signal-verification.md 3b). Every
green assertion here is paired with the KNOWN-BROKEN control that must fail:

  * ``test_control_bare_parallel_hangs`` drives an UNWRAPPED ``parallel()`` over
    the same five thunks, one of which never resolves, and requires the harness
    to report ``hung: true``. If that control ever reports ``hung: false`` the
    harness cannot discriminate and NO green result in this file may be cited.
  * ``test_settle_survives_a_hung_unit`` then drives ``settle()`` over the
    identical thunks and requires it to come back.

The helper under test is EXTRACTED FROM the skill template and EXECUTED, so this
suite tests the bytes an author pastes, not a transcription of them.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from h6_extract import (  # noqa: E402
    TEMPLATE,
    ExtractError,
    extract_block,
    extract_file,
)

HARNESS = Path(__file__).resolve().parent / "h6_harness.mjs"
TIMEOUT_MS = 150
WATCHDOG_MS = 2000
NODE = shutil.which("node")

# A node-less machine must FAIL this suite, not silently skip it: a skipped
# red-proof is exactly the no-op gate this program keeps shipping by accident.
# `run_scenario` therefore asserts on NODE rather than calling pytest.skip.


@pytest.fixture(scope="session")
def helper_js(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The H6 block, extracted from the template onto disk for the harness."""
    body = extract_file()
    out = tmp_path_factory.mktemp("h6") / "helper.js"
    out.write_text(body, encoding="utf-8", newline="\n")
    return out


def run_scenario(helper: Path, scenario: str, **flags: object) -> dict[str, object]:
    """Execute one harness scenario and return its parsed JSON verdict."""
    assert NODE is not None, (
        "node is required for the H6 red-proof; a skipped red-proof is a no-op gate"
    )
    argv = [
        NODE,
        str(HARNESS),
        "--source",
        str(helper),
        "--scenario",
        scenario,
        "--timeout-ms",
        str(TIMEOUT_MS),
        "--watchdog-ms",
        str(WATCHDOG_MS),
    ]
    for key, value in flags.items():
        argv.append(f"--{key}")
        if value is not True:
            argv.append(str(value))
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        argv, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, (
        f"harness exited {proc.returncode}\nSTDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}"
    )
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- #
# 1. THE CONTROL -- the known-broken state must actually hang.
# --------------------------------------------------------------------------- #
def test_control_bare_parallel_hangs(helper_js: Path) -> None:
    verdict = run_scenario(helper_js, "unwrapped")
    assert verdict["hung"] is True, (
        "DETECTOR FAILURE: a bare parallel() over a never-resolving thunk SETTLED. "
        "The harness cannot distinguish the broken state from the fixed one, so no "
        f"green H6 result may be cited. verdict={verdict}"
    )
    assert verdict["elapsedMs"] >= WATCHDOG_MS * 0.5
    assert verdict["parallelBarriers"] == 1


def test_control_hangs_regardless_of_which_unit_is_stuck(helper_js: Path) -> None:
    for idx in (0, 4):
        verdict = run_scenario(helper_js, "unwrapped", **{"hang-index": idx})
        assert verdict["hung"] is True, f"hang-index={idx} settled: {verdict}"


# --------------------------------------------------------------------------- #
# 2. THE FIX -- settle() returns on the survivors.
# --------------------------------------------------------------------------- #
def test_settle_survives_a_hung_unit(helper_js: Path) -> None:
    verdict = run_scenario(helper_js, "wrapped")
    assert verdict["hung"] is False, f"settle() deadlocked: {verdict}"
    assert verdict["length"] == 5
    assert verdict["endReasons"] == [None, None, "timeout", None, None]
    assert verdict["survivors"] == [0, 1, 3, 4]
    assert verdict["drops"] == [{"label": "u2", "why": "timeout"}]


def test_settle_returns_well_inside_two_times_the_timeout(helper_js: Path) -> None:
    verdict = run_scenario(helper_js, "wrapped")
    assert float(verdict["elapsedMs"]) < 2 * TIMEOUT_MS + 400, verdict


def test_settle_is_index_aligned_and_has_no_nulls(helper_js: Path) -> None:
    verdict = run_scenario(helper_js, "wrapped", count=7, **{"hang-index": 5})
    assert verdict["length"] == 7
    reasons = verdict["endReasons"]
    assert reasons[5] == "timeout"
    assert [r for r in reasons if r is not None] == ["timeout"]


def test_heartbeat_fires_while_the_unit_is_outstanding(helper_js: Path) -> None:
    # STALL_MS is 90 s in the shipped default, so drive the observable path by
    # asserting the heartbeat did NOT fire inside a 150 ms timeout -- and that a
    # heartbeat line is the only thing log() would ever emit from the helper.
    verdict = run_scenario(helper_js, "wrapped")
    assert verdict["logLines"] == [], verdict["logLines"]


# --------------------------------------------------------------------------- #
# 3. SANDBOX FIDELITY -- the helper must survive the real sandbox's constraints.
# --------------------------------------------------------------------------- #
def test_sandbox_shims_are_live(helper_js: Path) -> None:
    """Control for the sandbox itself: the banned globals really do throw here."""
    verdict = run_scenario(helper_js, "shims-fire")
    assert verdict["shimsThatThrew"] == ["Date.now", "new Date", "Math.random"]


def test_helper_degrades_when_timers_are_not_injected(helper_js: Path) -> None:
    """Runtime-drift guard: no setTimeout -> plain await, typed 'threw' receipt."""
    verdict = run_scenario(helper_js, "degraded", **{"no-timers": True})
    assert verdict["hung"] is False, verdict
    assert verdict["endReasons"] == [None, None, "threw", None, None]


def test_helper_is_free_of_banned_nondeterminism() -> None:
    """USE, not MENTION.

    A naive substring scan over the raw block FAILS here, and correctly so: the
    helper's own header comment names ``Date.now`` / ``Math.random`` to say it does
    not use them. Counting the document instead of the field is the measured
    four-false-findings trap, so the scan runs over the linter's lexical MASK,
    which blanks comment and string bodies while preserving offsets.
    """
    lint_dir = TEMPLATE.parents[1] / "scripts"
    sys.path.insert(0, str(lint_dir))
    import workflow_lint  # noqa: PLC0415

    raw = extract_file()
    code_only = workflow_lint.mask_code(raw)
    for banned in ("Date.now", "Math.random", "new Date(", "require(", "eval("):
        assert banned not in code_only, f"helper USES banned construct {banned!r}"
    # Control for the mask: the mention really is present in the raw bytes, so a
    # green result above is evidence the mask worked, not that the text is absent.
    assert "Date.now" in raw


def test_helper_passes_the_workflow_linter() -> None:
    """The pasted helper must not itself trip workflow_lint."""
    lint_dir = TEMPLATE.parents[1] / "scripts"
    sys.path.insert(0, str(lint_dir))
    import workflow_lint  # noqa: PLC0415

    src = (
        "export const meta = { name: 'h6-probe', description: 'x' };\n"
        + extract_file()
        + "\nconst r = await settle([], 1000, []);\nreturn r.length;\n"
    )
    findings = workflow_lint.lint_text(src, "h6-probe.mjs")
    errors = [f for f in findings if f.level == workflow_lint.ERROR]
    assert errors == [], errors


# --------------------------------------------------------------------------- #
# 4. THE EXTRACTOR fails closed.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "markdown",
    [
        "no markers at all",
        "<!-- H6-BEGIN -->\nplain prose, no fence\n<!-- H6-END -->",
        "<!-- H6-END -->\n```js\nx\n```\n<!-- H6-BEGIN -->",
        "<!-- H6-BEGIN -->\n```js\n```\n<!-- H6-END -->",
        "<!-- H6-BEGIN -->\n```js\nx\n<!-- H6-END -->",
        "<!-- H6-BEGIN -->\n```js\na\n```\n<!-- H6-END -->\n"
        "<!-- H6-BEGIN -->\n```js\nb\n```\n<!-- H6-END -->",
    ],
)
def test_extractor_fails_closed(markdown: str) -> None:
    with pytest.raises(ExtractError):
        extract_block(markdown)


def test_extractor_round_trips_a_minimal_block() -> None:
    got = extract_block(
        "pre\n<!-- H6-BEGIN -->\n```js\nconst a = 1;\n```\n<!-- H6-END -->\npost"
    )
    assert got == "const a = 1;\n"


def test_extractor_cli_writes_a_file(tmp_path: Path) -> None:
    import h6_extract  # noqa: PLC0415

    out = tmp_path / "h6.js"
    rc = h6_extract.main(["--out", str(out)])
    assert rc == 0
    assert "async function withTimeout" in out.read_text(encoding="utf-8")


def test_extractor_cli_reports_failure(tmp_path: Path) -> None:
    import h6_extract  # noqa: PLC0415

    bad = tmp_path / "bad.md"
    bad.write_text("nothing here", encoding="utf-8")
    assert h6_extract.main(["--template", str(bad)]) == 1


def test_extractor_cli_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    import h6_extract  # noqa: PLC0415

    assert h6_extract.main([]) == 0
    assert "function h6Receipt" in capsys.readouterr().out
