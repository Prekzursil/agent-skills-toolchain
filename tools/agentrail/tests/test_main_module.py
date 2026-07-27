"""``python -m agentrail`` -- both arms of the ``__main__`` guard, with NO subprocess.

The usual reason a ``__main__`` guard carries ``# pragma: no cover`` is that the only obvious way
to run it is to spawn a process, which the hermeticity rule forbids. :func:`runpy.run_path`
re-executes the file IN-PROCESS with ``__name__ == "__main__"``, so both the True arm (here) and
the False arm (the plain import) are measured without spawning anything.
"""

from __future__ import annotations

import importlib
import json
import runpy
import sys
from pathlib import Path

import pytest

import agentrail

MAIN_PY = Path(agentrail.__file__).with_name("__main__.py")


def test_importing_the_module_does_not_run_the_cli() -> None:
    """The FALSE arm of the guard: importing must be inert."""
    module = importlib.import_module("agentrail.__main__")
    assert module.main.__module__ == "agentrail.cli"
    assert module.__name__ == "agentrail.__main__"


def test_executing_the_module_runs_the_cli_and_exits_with_its_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The TRUE arm: run_path gives the file ``__name__ == '__main__'`` in this process."""
    monkeypatch.setattr(sys, "argv", ["agentrail", "rails"])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(MAIN_PY), run_name="__main__")
    assert caught.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"
    assert payload["terminal"] == "SUCCESS:rails"


def test_a_failing_command_exits_non_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["agentrail", "--config", "/absent.toml", "rails"])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(MAIN_PY), run_name="__main__")
    assert caught.value.code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "error"
