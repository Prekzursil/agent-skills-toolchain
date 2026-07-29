#!/usr/bin/env python3
r"""test_no_force_push.py - unit test of the no-force-push gate predicate.

Imports tripwire.py and exercises should_halt() directly: it must return
(True, reason) on the FIRE example and (False, _) on the SILENT example.
The end-to-end exit-2 / fail-open proof is in chaos_no_force_push.py.

The ``test_*`` functions below are the pytest-collectable half. Before they were
added this module defined only ``main()``/helpers, so the CI step that runs the
whole tree (``python -m pytest hooks/ -q --import-mode=importlib``) collected
ZERO tests from it -- measured: "no tests ran in 0.55s". A suite that collects
nothing cannot catch a regression, so the ordering property below was unenforced.

The property they pin (D-f029): the opt-out must NOT be evaluated before the
predicate. A bypassed positive detection has to leave a record on stdout AND
stderr; the pre-fix hook returned exit 0 with both streams empty, which is
byte-indistinguishable from "no force-push was ever attempted".
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
HOOK = HERE / "hook.py"
TRIPWIRE = HERE / "tripwire.py"


def _load_tripwire():
    spec = importlib.util.spec_from_file_location(
        "forged_tripwire_no_force_push", HERE / "tripwire.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _set(d: dict, path: str, val) -> None:
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = val


def _payload(value: str) -> dict:
    kind = FIX["kind"]
    p = dict(FIX.get("extra_payload") or {})
    if kind == "prompt":
        p["prompt"] = value
    elif kind == "command":
        p.setdefault("tool_input", {})["command"] = value
    elif kind == "tool":
        p["tool_name"] = value
    elif kind == "field":
        _set(p, FIX["field"], value)
    return p


def _run_hook(hook_path: Path, value: str, env_extra: dict | None = None):
    """Run a hook process on a payload; return (rc, stdout, stderr)."""
    env = dict(os.environ)
    env.pop("FORGE_NO_FORCE_PUSH_OFF", None)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_extra:
        env.update(env_extra)
    res = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(_payload(value)),
        cwd=str(hook_path.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )
    return res.returncode, (res.stdout or ""), (res.stderr or "")


def _hook_copy(tmp_path: Path) -> Path:
    """Copy hook.py + tripwire.py into tmp_path.

    The ``.disabled`` marker is resolved relative to ``hook.py``, so exercising
    the file kill switch against a COPY keeps the real, wired gate armed even if
    this test is interrupted. Never create ``.disabled`` in the source tree.
    """
    shutil.copy(HOOK, tmp_path / "hook.py")
    shutil.copy(TRIPWIRE, tmp_path / "tripwire.py")
    return tmp_path / "hook.py"


def test_predicate_fires_on_force_push_and_stays_silent_otherwise():
    tw = _load_tripwire()
    halt, reason = tw.should_halt(_payload(FIX["fire_value"]))
    assert halt and reason
    halt2, _ = tw.should_halt(_payload(FIX["silent_value"]))
    assert not halt2


def test_armed_gate_still_blocks_with_exit_2():
    rc, _out, err = _run_hook(HOOK, FIX["fire_value"])
    assert rc == 2, f"armed gate must block the force-push, got rc={rc}"
    assert "refusing git push --force" in err


def test_env_optout_allows_but_announces_the_bypass():
    """D-f029: the env kill switch must not swallow a positive detection."""
    rc, out, err = _run_hook(
        HOOK, FIX["fire_value"], env_extra={"FORGE_NO_FORCE_PUSH_OFF": "1"}
    )
    assert rc == 0, "the documented break-glass must still ALLOW (fail-open)"
    # Pre-fix this was rc=0 with out == err == "": a bypass indistinguishable
    # from "nothing dangerous was attempted".
    assert "GATE BYPASSED" in out, f"bypass must reach stdout, got {out!r}"
    assert "GATE BYPASSED" in err, f"bypass must reach stderr, got {err!r}"
    assert "FORGE_NO_FORCE_PUSH_OFF" in out, "the notice must name the switch used"


def test_disabled_marker_allows_but_announces_the_bypass(tmp_path: Path):
    """Same property for the file kill switch, exercised on a COPY of the hook."""
    hook = _hook_copy(tmp_path)
    (tmp_path / ".disabled").write_text("", encoding="utf-8")
    rc, out, err = _run_hook(hook, FIX["fire_value"])
    assert rc == 0
    assert "GATE BYPASSED" in out and "GATE BYPASSED" in err
    assert ".disabled" in out, "the notice must name the marker, not just 'an opt-out'"


def test_optout_stays_quiet_when_nothing_dangerous_is_detected(tmp_path: Path):
    """The notice is bypass-triggered, not opt-out-triggered: no routine noise."""
    hook = _hook_copy(tmp_path)
    (tmp_path / ".disabled").write_text("", encoding="utf-8")
    rc, out, err = _run_hook(hook, FIX["silent_value"])
    assert rc == 0
    assert out == "" and err == "", f"benign op must stay silent: {out!r} {err!r}"


def test_broken_tripwire_still_fails_open(tmp_path: Path):
    """The import guard must survive the reordering: a corrupt predicate allows."""
    shutil.copy(HOOK, tmp_path / "hook.py")
    (tmp_path / "tripwire.py").write_text(
        "raise ImportError('forged: broken tripwire')\n", encoding="utf-8"
    )
    rc, _out, err = _run_hook(tmp_path / "hook.py", FIX["fire_value"])
    assert rc == 0, "a broken predicate must never block"
    assert "Traceback" not in err


def main() -> int:
    tw = _load_tripwire()
    halt, reason = tw.should_halt(_payload(FIX["fire_value"]))
    assert halt, "should_halt did not fire on the FIRE example"
    assert reason, "should_halt fired but returned an empty reason"
    halt2, _ = tw.should_halt(_payload(FIX["silent_value"]))
    assert not halt2, "should_halt must NOT fire on the SILENT example"
    print(
        f"UNIT-PASS: {FIX['name']} halts on trigger ({reason!r}) and allows otherwise"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"UNIT-FAIL: {exc}")
        sys.exit(1)
