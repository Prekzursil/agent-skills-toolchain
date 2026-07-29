#!/usr/bin/env python3
"""Unit tests for the Lightning AI FastMCP wrapper (``lightning-mcp/server.py``).

No live Lightning account: ``lightning_sdk`` is imported lazily inside each tool,
so the single seam ``_sdk`` is monkeypatched with a fake SDK that records every
mutation. The module is loaded by explicit path as ``lightning_server`` so it
never collides with the other built wrappers' ``server.py`` modules.

The focus is the post-action ``status`` read: ``Studio.status`` / ``Job.status``
are PROPERTIES that perform a separate control-plane GET, so a failure there must
not be reported as a failure of the (already-completed, billable) mutation.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HUB_DIR not in sys.path:
    sys.path.insert(0, HUB_DIR)

_SERVER_PATH = os.path.join(HUB_DIR, "lightning-mcp", "server.py")
_spec = importlib.util.spec_from_file_location("lightning_server", _SERVER_PATH)
lightning_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lightning_server)


# --------------------------------------------------------------------------- #
# Fakes.                                                                       #
# --------------------------------------------------------------------------- #
class _Machine:
    CPU = "CPU"
    T4 = "T4"


class _FakeStudio:
    """A Studio whose ``status`` property can be made to raise, like the real SDK."""

    def __init__(self, events, status_raises=False, status_value="RUNNING"):
        self._events = events
        self._status_raises = status_raises
        self._status_value = status_value

    @property
    def status(self):
        self._events.append("studio.status")
        if self._status_raises:
            raise RuntimeError("status endpoint unavailable")
        return self._status_value

    def start(self, machine):
        self._events.append(("studio.start", machine))

    def switch_machine(self, machine, interruptible=False):
        self._events.append(("studio.switch_machine", machine, interruptible))


class _FakeJob:
    def __init__(self, events, status_raises=False, status_value="PENDING"):
        self._events = events
        self._status_raises = status_raises
        self._status_value = status_value

    @property
    def status(self):
        self._events.append("job.status")
        if self._status_raises:
            raise RuntimeError("status endpoint unavailable")
        return self._status_value


def _install_sdk(monkeypatch, status_raises=False, action_raises=False):
    """Point the module's lazy ``_sdk`` seam at a fake SDK; return the event log."""
    events: list = []
    studio = _FakeStudio(events, status_raises=status_raises)
    job = _FakeJob(events, status_raises=status_raises)

    class _Job:
        @staticmethod
        def run(**kwargs):
            if action_raises:
                raise RuntimeError("job submit rejected")
            events.append(("Job.run", kwargs["name"]))
            return job

    def _studio_factory(name, teamspace=None):
        if action_raises:
            raise RuntimeError("studio unreachable")
        return studio

    sdk = type(
        "_Sdk",
        (),
        {"Machine": _Machine, "Studio": staticmethod(_studio_factory), "Job": _Job},
    )
    monkeypatch.setattr(lightning_server, "_sdk", lambda: (sdk, None))
    return events


# --------------------------------------------------------------------------- #
# A failing post-action status read must NOT mask a completed billable action.  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("call", "mutation"),
    [
        (lambda: lightning_server.lightning_studio_start("demo"), "studio.start"),
        (
            lambda: lightning_server.lightning_studio_switch_machine("demo", "T4"),
            "studio.switch_machine",
        ),
        (lambda: lightning_server.lightning_job_submit("demo", "echo ok"), "Job.run"),
    ],
)
def test_status_read_failure_does_not_fail_a_completed_action(
    monkeypatch, call, mutation
):
    events = _install_sdk(monkeypatch, status_raises=True)

    out = json.loads(call())

    performed = [e[0] if isinstance(e, tuple) else e for e in events]
    assert mutation in performed, events
    # The mutation SUCCEEDED remotely (and bills), so the caller must be told so --
    # otherwise it retries the billable action or skips teardown of a live machine.
    assert out["ok"] is True, out
    assert "status unavailable" in out["status"]
    assert "status endpoint unavailable" in out["status"]


@pytest.mark.parametrize(
    ("call", "expected_status"),
    [
        (lambda: lightning_server.lightning_studio_start("demo"), "RUNNING"),
        (
            lambda: lightning_server.lightning_studio_switch_machine("demo", "T4"),
            "RUNNING",
        ),
        (lambda: lightning_server.lightning_job_submit("demo", "echo ok"), "PENDING"),
    ],
)
def test_status_is_reported_when_the_read_succeeds(monkeypatch, call, expected_status):
    _install_sdk(monkeypatch)
    out = json.loads(call())
    assert out["ok"] is True
    assert out["status"] == expected_status


@pytest.mark.parametrize(
    ("call", "prefix"),
    [
        (
            lambda: lightning_server.lightning_studio_start("demo"),
            "studio_start failed",
        ),
        (
            lambda: lightning_server.lightning_studio_switch_machine("demo", "T4"),
            "studio_switch_machine failed",
        ),
        (
            lambda: lightning_server.lightning_job_submit("demo", "echo ok"),
            "job_submit failed",
        ),
    ],
)
def test_a_real_action_failure_is_still_reported(monkeypatch, call, prefix):
    """The guard must not swallow a failure of the MUTATION itself."""
    _install_sdk(monkeypatch, action_raises=True)
    out = json.loads(call())
    assert out["ok"] is False
    assert out["error"].startswith(prefix)


def test_sdk_missing_is_surfaced(monkeypatch):
    monkeypatch.setattr(lightning_server, "_sdk", lambda: (None, "no lightning_sdk"))
    out = json.loads(lightning_server.lightning_studio_start("demo"))
    assert out == {"ok": False, "error": "no lightning_sdk"}
