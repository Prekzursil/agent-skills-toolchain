"""WU9 re-integration + platform smoke (OUTSIDE the 100% coverage lane).

Proves the wfmon skill still stands on the vendored ``monitorcore`` after the PR-B2 ports:

* the cockpit imports cleanly and the vendored ``monitorcore`` resolves (no ``D:\\`` hack);
* the cockpit's ``DETAIL_CHARS`` Task/Result cap is the SINGLE shared ``monitorcore.textsafe``
  ``TOOL_OUTPUT_CAP`` (the ×3 magic-cap dedup — cockpit / render_md / render_html);
* the must-preserve entrypoints still invoke — ``run_export`` + ``main`` (``python -m
  wfmon_export``) + the ``board`` script (``workflow_run.py``) + ``import workflow_run as wr``.

These are import/invoke smokes, not render-byte assertions (the byte-identical guarantee lives
in ``tests/test_golden.py``); they run on frozen fixtures / an empty temp fleet so they are
deterministic on any platform.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_ROOT = os.path.realpath(
    os.path.join(_SKILL_ROOT, "fixtures", "export", "projects")
)
WF_ID = "wf_export00-fixture"


# ── vendored monitorcore resolves + the ×3 cap dedup ─────────────────────────
def test_shared_tool_output_cap_is_single_source():
    """render_md / render_html / textsafe all reference ONE ``TOOL_OUTPUT_CAP`` object."""
    from monitorcore import render_html, render_md, textsafe

    assert textsafe.TOOL_OUTPUT_CAP == 8000
    assert render_md.TOOL_OUTPUT_CAP is textsafe.TOOL_OUTPUT_CAP
    assert render_html.TOOL_OUTPUT_CAP is textsafe.TOOL_OUTPUT_CAP


def test_cockpit_detail_chars_is_the_shared_cap():
    """The cockpit's Task/Result cap is imported from monitorcore, not a local literal."""
    pytest.importorskip("textual")
    pytest.importorskip("rich")
    import workflow_monitor as wm
    from monitorcore import textsafe

    # identity (not just ==) proves it is the imported shared object, not a re-typed 8000
    assert wm.DETAIL_CHARS is textsafe.TOOL_OUTPUT_CAP
    # the vendored agent_tail resolved (no fallback-to-None on the D:\ hack path)
    assert wm.agent_tail is not None


def test_cockpit_uses_workflow_run_alias():
    """``import workflow_run as wr`` exposes the shim-backed helpers the cockpit relies on."""
    import workflow_run as wr

    for name in (
        "report_headline",
        "DEFAULT_PROJECTS",
        "FleetPoller",
        "fleet_rollup",
        "agent_prompt",
        "agent_output",
    ):
        assert hasattr(wr, name), f"workflow_run missing {name}"


# ── export entrypoints invoke ────────────────────────────────────────────────
def test_export_entrypoints_importable():
    """``run_export`` and ``main`` (the ``python -m wfmon_export`` target) import + are callable."""
    import wfmon_export.__main__ as entry  # the module-run target
    from wfmon_export.cli import main, run_export

    assert callable(run_export)
    assert callable(main)
    assert entry.main is main


def test_wfmon_export_help_invokes():
    """``main(["--help"])`` runs argparse to a clean SystemExit(0) — the CLI is wired."""
    from wfmon_export.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


# ── board entrypoint (workflow_run.py __main__) ──────────────────────────────
def test_board_poll_rollup_on_fixture_fleet():
    """``wfmon board``'s poll→rollup chain works against the frozen fixture (deterministic)."""
    import workflow_run as wr

    runs = wr.FleetPoller(projects=FIXTURE_ROOT).poll()
    roll = wr.fleet_rollup(runs)
    assert {"runs", "active_runs", "running", "done", "error", "tokens"} <= set(roll)
    assert WF_ID in {r.wf_id for r in runs}


def test_board_script_runs_end_to_end(tmp_path):
    """The literal ``python workflow_run.py`` board entrypoint runs to a clean exit.

    Uses an empty temp home so it never touches the real fleet — the board prints its
    ``FLEET: 0 runs`` header and exits 0, proving the script entrypoint + vendored
    ``monitorcore`` import resolve outside any test harness.
    """
    home = tmp_path / "home"
    (home / ".claude" / "projects").mkdir(parents=True)
    env = dict(os.environ)
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    env.pop("HOMEDRIVE", None)
    env.pop("HOMEPATH", None)
    proc = subprocess.run(
        [sys.executable, "workflow_run.py"],
        cwd=_SKILL_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "FLEET:" in proc.stdout
    assert "0 runs" in proc.stdout
