#!/usr/bin/env python3
"""Runtime contract tests for ``_dispatch/dispatch.py`` itself.

``test_wiring.py`` / ``test_manifest_presence.py`` audit the manifest DOCUMENTS.
This module audits what ``dispatch.run()`` actually DOES with them, and covers two
defects that the document-level tests structurally cannot see:

1. PATH CONTAINMENT.  ``run()`` used to hand ``os.path.join(hooks_root, script)``
   straight to ``_load_module`` -> ``spec.loader.exec_module``.  A ``script`` of
   ``"../outside.py"`` or ``"/abs/outside.py"`` therefore imported and EXECUTED code
   from outside the configured hook tree, before any worker thread or per-check
   timeout existed.  Every script in the shipped manifest is relative and clean, so
   no document-level assertion could catch the missing guard.

2. DISARMED BLOCK REQUESTS.  ``_call_main`` discarded its return value, so a
   manifest-listed check that returned a non-zero would-be exit code had that
   result silently dropped: measured on ``journey-coverage/check.py`` under
   ``JOURNEY_COVERAGE_MODE=block``, which returns 2 and wrote only to stderr, so the
   dispatched route produced NO host-readable output at all.  The dispatcher is
   inject-only and stays that way -- but a disarmed gate must now be VISIBLE.

Every containment assertion is paired with an inside-the-root control, so an empty
"nothing was loaded" reading can never pass as proof (a detector that reports zero
in both states measures nothing).
"""

from __future__ import annotations

import importlib.util
import io
import json
import types
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "_c06_dispatch_under_test", HERE / "dispatch.py"
)
assert _SPEC is not None and _SPEC.loader is not None
dispatch = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dispatch)


class _Recorder:
    """Stand-in for ``_load_module`` that records paths instead of executing them."""

    def __init__(self, module: types.ModuleType | None = None) -> None:
        self.paths: list[str] = []
        self._module = module

    def __call__(self, script_path: str, uniq_name: str):
        self.paths.append(script_path)
        return self._module


def _manifest(root: Path, script: str, event: str = "SessionStart") -> dict:
    return {
        "hooks_root": str(root),
        "events": {
            "SessionStart": {"checks": []},
            "Stop": {"checks": []},
            event: {
                "checks": [
                    {"name": "probe", "script": script, "args": [], "timeout": 5}
                ]
            },
        },
    }


def _module_returning(rc, emitted: str = "") -> types.ModuleType:
    mod = types.ModuleType("fake_check")

    def main():
        if emitted:
            print(emitted)
        return rc

    mod.main = main  # type: ignore[attr-defined]
    return mod


@pytest.fixture()
def hooks_root(tmp_path: Path) -> Path:
    root = tmp_path / "hooks"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "hook.py").write_text("def main():\n    return 0\n", "utf-8")
    (tmp_path / "outside.py").write_text("def main():\n    return 0\n", "utf-8")
    return root


# --- 1. path containment ----------------------------------------------------


@pytest.mark.parametrize(
    "script",
    [
        "../outside.py",
        "pkg/../../outside.py",
        "pkg/../..//outside.py",
        "/outside/absolute.py",
    ],
)
def test_manifest_script_may_not_escape_the_hooks_root(
    hooks_root: Path, monkeypatch: pytest.MonkeyPatch, script: str
):
    rec = _Recorder()
    monkeypatch.setattr(dispatch, "_load_module", rec)

    assert dispatch.run("SessionStart", "{}", _manifest(hooks_root, script)) is None
    assert rec.paths == [], (
        f"escaping script {script!r} reached the loader: {rec.paths}"
    )


def test_relative_script_inside_the_root_still_loads(
    hooks_root: Path, monkeypatch: pytest.MonkeyPatch
):
    """CONTROL for the four assertions above -- without it, an always-empty
    ``rec.paths`` (a broken detector) would report them all as passing."""

    rec = _Recorder()
    monkeypatch.setattr(dispatch, "_load_module", rec)

    dispatch.run("SessionStart", "{}", _manifest(hooks_root, "pkg/hook.py"))
    assert rec.paths == [str((hooks_root / "pkg" / "hook.py").resolve())]


def test_resolve_script_rejects_the_root_itself(hooks_root: Path):
    assert dispatch._resolve_script(str(hooks_root), ".") is None
    assert dispatch._resolve_script(str(hooks_root), "pkg/hook.py") is not None


def test_every_shipped_manifest_script_survives_containment():
    """The real manifest must not be collateral damage of the guard.

    2026-10-17 blocking-mode contract update: a check may now carry an absolute
    ``exec_path`` instead of a contained ``script`` (owner-reviewed bridge for
    out-of-tree guards such as ``estate-deny-guard``), but ONLY under ``exec``
    mode -- an absolute path that slipped into import mode would be exactly the
    containment escape this suite exists to catch. So: ``script`` checks (import
    or exec) must still resolve inside ``hooks_root``; ``exec_path`` checks must
    declare ``exec`` truthy and are exempt from root containment by design (the
    live-host absolute path does not exist in a checkout or on CI).
    """

    manifest = dispatch._load_manifest()
    root = manifest.get("hooks_root") or str(HERE.parent)
    checks = [
        check
        for event in (manifest.get("events") or {}).values()
        for check in (event.get("checks") or [])
    ]
    assert checks, "shipped manifest exposed no checks -- detector is broken"
    contained = 0
    rejected = []
    unguarded = []
    for c in checks:
        if c.get("exec_path"):
            if not c.get("exec"):
                unguarded.append(
                    f"{c.get('name')!r} carries exec_path without exec mode -- "
                    "an absolute import target is a containment escape"
                )
            continue
        contained += 1
        if dispatch._resolve_script(root, c["script"]) is None:
            rejected.append(c["script"])
    assert not unguarded, f"exec_path outside exec mode: {unguarded}"
    assert not rejected, f"containment rejected shipped manifest scripts: {rejected}"
    assert contained, "no script-based checks survived -- containment half is vacuous"


# --- 2. disarmed block requests --------------------------------------------


def test_blocking_return_is_surfaced_instead_of_silently_dropped(
    hooks_root: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(dispatch, "_load_module", _Recorder(_module_returning(2)))

    agg = dispatch.run("Stop", "{}", _manifest(hooks_root, "pkg/hook.py", "Stop"))
    assert agg is not None, "a check that returned 2 produced no host-readable output"
    assert "'probe'" in agg and "exit status 2" in agg


def test_blocking_note_accompanies_the_checks_own_message(
    hooks_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """End-to-end through ``main()``, which is what installs the thread-local stdout
    proxy -- calling ``run()`` directly would let the check's ``print`` escape to the
    real stdout and the aggregate would look empty for the wrong reason.

    This is the journey-coverage shape: the check emits its finding AND asks to
    block. Both must reach the model.
    """

    emitted = (
        '{"hookSpecificOutput": {"hookEventName": "Stop", '
        '"additionalContext": "JOURNEY-COVERAGE: uncovered"}}'
    )
    monkeypatch.setattr(
        dispatch, "_load_module", _Recorder(_module_returning(2, emitted))
    )
    monkeypatch.setattr(
        dispatch, "_load_manifest", lambda: _manifest(hooks_root, "pkg/hook.py", "Stop")
    )
    monkeypatch.setattr(dispatch.sys, "stdin", io.StringIO("{}"))

    assert dispatch.main(["stop"]) == 0
    payload = json.loads(capsys.readouterr().out.strip())
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "JOURNEY-COVERAGE: uncovered" in ctx
    assert "exit status 2" in ctx


@pytest.mark.parametrize("rc", [0, None, True, False, "2"])
def test_non_blocking_returns_add_no_note(
    hooks_root: Path, monkeypatch: pytest.MonkeyPatch, rc
):
    """CONTROL: only a genuine non-zero int is a block request. ``True`` is an
    ``int`` subclass and must NOT be read as exit status 1."""

    monkeypatch.setattr(dispatch, "_load_module", _Recorder(_module_returning(rc)))

    agg = dispatch.run("Stop", "{}", _manifest(hooks_root, "pkg/hook.py", "Stop"))
    assert agg is None, f"return {rc!r} was wrongly reported as a block: {agg!r}"


def test_dispatcher_still_exits_zero_when_a_check_requests_a_block(
    hooks_root: Path, monkeypatch: pytest.MonkeyPatch
):
    """The dispatcher stays inject-only. Surfacing the request must not start
    blocking sessions through the back door."""

    monkeypatch.setattr(dispatch, "_load_module", _Recorder(_module_returning(2)))
    monkeypatch.setattr(
        dispatch, "_load_manifest", lambda: _manifest(hooks_root, "pkg/hook.py", "Stop")
    )
    monkeypatch.setattr(dispatch.sys, "stdin", io.StringIO("{}"))

    assert dispatch.main(["stop"]) == 0
