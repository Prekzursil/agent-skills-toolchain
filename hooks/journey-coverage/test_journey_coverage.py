#!/usr/bin/env python3
"""Tests for the journey-coverage Stop hook (pure core + modes + fail-open)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "journey_coverage_check", _HERE / "check.py"
)
assert _spec and _spec.loader
jc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jc)


# --------------------------------------------------------------------------- #
# is_done_claim
# --------------------------------------------------------------------------- #
def test_done_claim_detects_assertive():
    assert jc.is_done_claim("The app is done and ready to ship.")
    assert jc.is_done_claim("Everything works end-to-end now.")
    assert jc.is_done_claim("v1.4 is complete.")
    assert jc.is_done_claim("This is production-ready.")


def test_done_claim_suppressed_by_hedge():
    assert not jc.is_done_claim("The app should be ready once you run the tests.")
    assert not jc.is_done_claim("It's almost done.")
    assert not jc.is_done_claim("This might be ready to ship.")
    assert not jc.is_done_claim("")


def test_done_claim_ignores_unrelated():
    assert not jc.is_done_claim("I fixed a bug in the parser.")
    assert not jc.is_done_claim("Running the tests now.")


# --------------------------------------------------------------------------- #
# find_journey_specs
# --------------------------------------------------------------------------- #
def _mk(root: Path, rel: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("// spec\n", encoding="utf-8")


def test_find_journey_specs_globs_and_skips(tmp_path):
    _mk(tmp_path, "app/e2e/golden-journey.spec.ts")
    _mk(tmp_path, "app/e2e/preview.spec.ts")
    _mk(tmp_path, "cypress/e2e/login.cy.js")
    _mk(tmp_path, "sidecar/tests/e2e/real_pipeline.py")
    _mk(tmp_path, "node_modules/pkg/e2e/dep.spec.ts")  # skipped (node_modules)
    _mk(tmp_path, "src/util.ts")  # not a journey
    found = jc.find_journey_specs(str(tmp_path))
    assert "app/e2e/golden-journey.spec.ts" in found
    assert "app/e2e/preview.spec.ts" in found
    assert "cypress/e2e/login.cy.js" in found
    assert "sidecar/tests/e2e/real_pipeline.py" in found
    assert not any("node_modules" in f for f in found)
    assert not any("util.ts" in f for f in found)


def test_find_journey_specs_empty_when_none(tmp_path):
    _mk(tmp_path, "src/index.ts")
    assert jc.find_journey_specs(str(tmp_path)) == []


# --------------------------------------------------------------------------- #
# uncovered_journeys / _ran (the gate's core)
# --------------------------------------------------------------------------- #
def test_uncovered_all_when_no_commands():
    specs = ["app/e2e/golden-journey.spec.ts", "cypress/e2e/login.cy.js"]
    assert jc.uncovered_journeys(specs, []) == specs


def test_covered_by_broad_e2e_runner():
    specs = ["app/e2e/golden-journey.spec.ts", "cypress/e2e/login.cy.js"]
    assert jc.uncovered_journeys(specs, ["npx playwright test --workers=1"]) == []
    assert jc.uncovered_journeys(specs, ["npm run e2e"]) == []


def test_covered_by_named_spec():
    specs = ["app/e2e/golden-journey.spec.ts", "cypress/e2e/login.cy.js"]
    # Only the golden-journey named -> login still uncovered.
    out = jc.uncovered_journeys(specs, ["npx playwright test golden-journey --list"])
    assert out == ["cypress/e2e/login.cy.js"]


def test_covered_by_basename_or_stem():
    specs = ["app/e2e/golden-journey.spec.ts"]
    assert jc.uncovered_journeys(specs, ["node run golden-journey.spec.ts"]) == []


def test_plain_unit_test_run_does_not_cover_journeys():
    # A generic `pytest` / `jest` (NOT an e2e runner) must NOT count as coverage.
    specs = ["app/e2e/golden-journey.spec.ts"]
    assert jc.uncovered_journeys(specs, ["pytest tests/", "jest src/"]) == specs


# --------------------------------------------------------------------------- #
# broad-runner false greens (D-l04 mention-not-use, D-l05 non-running subcmd)
# --------------------------------------------------------------------------- #
_TWO = ["app/e2e/login.spec.ts", "app/e2e/checkout.spec.ts"]


def test_playwright_setup_and_diagnostic_commands_do_not_cover():
    # A playwright invocation that starts NO test must not cover any journey.
    for cmd in (
        "npx playwright install chromium",
        "npx playwright install-deps",
        "npx playwright --version",
        "npx playwright codegen https://example.com",
        "npx playwright show-report",
        "npx playwright open https://example.com",
        "npx playwright test --list",
        "npx playwright test --help",
        "npx cypress install",
    ):
        assert jc.uncovered_journeys(_TWO, [cmd]) == _TWO, cmd


def test_runner_name_merely_mentioned_does_not_cover():
    # The runner NAME printed or searched as text executed no browser.
    for cmd in (
        "printf 'npx playwright test'",
        "echo npx playwright test",
        "cat notes.md | grep 'playwright test'",
        "python -c \"print('npx playwright test')\"",
        "sed -i 's/npm run e2e/npm run unit/' package.json",
    ):
        assert jc.uncovered_journeys(_TWO, [cmd]) == _TWO, cmd


def test_genuine_broad_runners_still_cover_every_journey():
    # Regression guard: the guards above must not break real all-specs runs.
    for cmd in (
        "npx playwright test",
        "npx playwright test --workers=1",
        "npx playwright@1.61.1 test",
        "pnpm exec playwright test --reporter=list",
        "npm run e2e",
        "cypress run",
        "npm ci && npx playwright test",
        "npx playwright test 2>&1 | tee e2e.log",
        'bash -c "npm run e2e"',
        "CI=1 npx playwright test",
    ):
        assert jc.uncovered_journeys(_TWO, [cmd]) == [], cmd


# --------------------------------------------------------------------------- #
# main() end-to-end (warn / block / off / fail-open)
# --------------------------------------------------------------------------- #
def _run_hook(
    payload: dict, env_extra: dict | None = None
) -> subprocess.CompletedProcess:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, str(_HERE / "check.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def _seed(tmp_path, *, done: bool, specs: bool, ledger_cmds: list[str]):
    root = tmp_path / "repo"
    root.mkdir()
    if specs:
        _mk(root, "app/e2e/golden-journey.spec.ts")
    transcript = tmp_path / "t.jsonl"
    text = "The app is done and ready to ship." if done else "Fixed a bug."
    transcript.write_text(
        json.dumps({"type": "assistant", "message": {"content": text}}) + "\n", "utf-8"
    )
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir()
    (ledger_root / "sess.ndjson").write_text(
        "\n".join(json.dumps({"cmd": c, "exit": 0, "ok": True}) for c in ledger_cmds),
        encoding="utf-8",
    )
    payload = {
        "cwd": str(root),
        "transcript_path": str(transcript),
        "session_id": "sess",
    }
    return payload, {"CLAIM_GUARD_LEDGER_ROOT": str(ledger_root)}


def test_warn_when_done_claim_and_uncovered(tmp_path):
    payload, env = _seed(tmp_path, done=True, specs=True, ledger_cmds=["pytest tests/"])
    r = _run_hook(payload, env)
    assert r.returncode == 0
    assert "JOURNEY-COVERAGE" in r.stdout
    assert "golden-journey.spec.ts" in r.stdout


def test_silent_when_journey_covered(tmp_path):
    payload, env = _seed(
        tmp_path, done=True, specs=True, ledger_cmds=["npx playwright test"]
    )
    r = _run_hook(payload, env)
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_silent_when_no_done_claim(tmp_path):
    payload, env = _seed(tmp_path, done=False, specs=True, ledger_cmds=[])
    r = _run_hook(payload, env)
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_silent_when_no_journey_specs(tmp_path):
    payload, env = _seed(tmp_path, done=True, specs=False, ledger_cmds=[])
    r = _run_hook(payload, env)
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_block_mode_exits_2_on_uncovered(tmp_path):
    payload, env = _seed(tmp_path, done=True, specs=True, ledger_cmds=["pytest tests/"])
    r = _run_hook(payload, {**env, "JOURNEY_COVERAGE_MODE": "block"})
    assert r.returncode == 2
    assert "JOURNEY-COVERAGE" in r.stderr


def test_block_mode_also_emits_context_so_the_dispatcher_cannot_swallow_it(tmp_path):
    """This hook's ONLY registration is _dispatch/manifest.json:144-152, and that
    dispatcher aggregates stdout additionalContext while DISCARDING the return code.
    So block mode -- which wrote only stderr and returned 2 -- produced no
    host-readable output at all on its live route: the exit 2 was dropped and the
    finding reached nobody. Emitting the inject-only JSON in block mode too is what
    makes the message survive; standalone, Claude Code ignores stdout on an exit-2
    hook, so this costs nothing there.
    """

    payload, env = _seed(tmp_path, done=True, specs=True, ledger_cmds=["pytest tests/"])
    r = _run_hook(payload, {**env, "JOURNEY_COVERAGE_MODE": "block"})

    assert r.returncode == 2, "block mode must still block when run standalone"
    emitted = json.loads(r.stdout.strip())
    hso = emitted["hookSpecificOutput"]
    assert hso["hookEventName"] == "Stop"
    assert "golden-journey.spec.ts" in hso["additionalContext"]


def test_block_mode_emits_nothing_when_every_journey_ran(tmp_path):
    """CONTROL for the test above: the new print must stay inside the SAME firing
    condition, not turn block mode into an unconditional emitter."""

    payload, env = _seed(
        tmp_path, done=True, specs=True, ledger_cmds=["npx playwright test"]
    )
    r = _run_hook(payload, {**env, "JOURNEY_COVERAGE_MODE": "block"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_block_mode_silent_when_covered(tmp_path):
    payload, env = _seed(
        tmp_path, done=True, specs=True, ledger_cmds=["npx playwright test"]
    )
    r = _run_hook(payload, {**env, "JOURNEY_COVERAGE_MODE": "block"})
    assert r.returncode == 0


def test_block_mode_exits_2_when_only_a_setup_command_ran(tmp_path):
    # End-to-end: `npx playwright install` installed a browser and ran no journey.
    payload, env = _seed(
        tmp_path, done=True, specs=True, ledger_cmds=["npx playwright install chromium"]
    )
    r = _run_hook(payload, {**env, "JOURNEY_COVERAGE_MODE": "block"})
    assert r.returncode == 2
    assert "golden-journey.spec.ts" in r.stderr


def test_warn_mode_fires_when_runner_name_was_only_printed(tmp_path):
    # End-to-end: the ledger's only ok=true command merely PRINTS the runner name.
    payload, env = _seed(
        tmp_path, done=True, specs=True, ledger_cmds=["printf 'npx playwright test'"]
    )
    r = _run_hook(payload, env)
    assert r.returncode == 0
    assert "JOURNEY-COVERAGE" in r.stdout
    assert "golden-journey.spec.ts" in r.stdout


def test_off_mode_never_fires(tmp_path):
    payload, env = _seed(tmp_path, done=True, specs=True, ledger_cmds=[])
    r = _run_hook(payload, {**env, "JOURNEY_COVERAGE_MODE": "off"})
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_fail_open_on_malformed_payload():
    r = _run_hook({"transcript_path": "/nonexistent/x.jsonl", "cwd": "/nonexistent"})
    assert r.returncode == 0


def test_stop_hook_active_is_noop(tmp_path):
    payload, env = _seed(tmp_path, done=True, specs=True, ledger_cmds=[])
    payload["stop_hook_active"] = True
    r = _run_hook(payload, env)
    assert r.returncode == 0 and r.stdout.strip() == ""
