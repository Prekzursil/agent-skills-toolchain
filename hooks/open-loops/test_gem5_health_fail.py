#!/usr/bin/env python3
"""GEM-5 regression: health_fail open-loop silent when Plane B OK; fires on fail.

Runs WITHOUT pytest: `python test_gem5_health_fail.py`.
Never prints secrets from health JSON — only status/live/needed assertions.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="ol-gem5-")
os.environ["OPEN_LOOPS_DIR"] = _TMP
os.environ["EVENT_LEDGER_ROOT"] = os.path.join(_TMP, "ledger")

sys.path.insert(0, str(Path(__file__).resolve().parent))
# `_common` is a DIR-LOCAL name shared by bg-registry/, memory-spool/ and this
# dir. Under a full `pytest hooks/` run those siblings are collected first and
# cache THEIR `_common` in sys.modules, so a plain `import _common` here binds
# the wrong module and collection dies on the GEM-5 attributes below (the
# 2026-10-18 suite-abort). Pop the cache and re-resolve against THIS dir — the
# same idiom dispatch.py::_SHARED_NAMES uses for exactly this collision.
sys.modules.pop("_common", None)
import _common as C  # noqa: E402
import resurface  # noqa: E402
import trigger_match  # noqa: E402
import add  # noqa: E402

C.OL_DIR = Path(_TMP)
C.TRIGGERS_FILE = Path(_TMP) / "triggers.jsonl"

_FAILS: list[str] = []
ACTION = C.GEM5_COOKIE_BRIDGE_ACTION


def ok(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def _write_health(path: Path, status: str, live: int, needed: int) -> Path:
    # status/live/needed only — no tokens in fixture
    path.write_text(
        json.dumps({"status": status, "live": live, "needed": needed}),
        encoding="utf-8",
    )
    return path


def reset() -> None:
    try:
        C.TRIGGERS_FILE.unlink()
    except FileNotFoundError:
        pass


def _register(health_path: Path) -> None:
    reset()
    rc = add.main(
        [
            "--health-fail",
            str(health_path),
            "--action",
            ACTION,
            "--recurring",
            "--ttl",
            "0",
            "--source",
            "gem-5",
        ]
    )
    ok("add.py --health-fail registers", rc == 0)
    t = C.load_triggers()
    ok("stored one health_fail trigger", len(t) == 1)
    ok(
        "pred type is health_fail",
        t and t[0]["condition"]["preds"][0]["type"] == "health_fail",
    )
    ok("action is fixed GEM-5 cookie-bridge text", t and t[0]["action"] == ACTION)
    ok("recurring so it re-surfaces after recover→fail", t and t[0]["recurring"] is True)


def main() -> int:
    hdir = Path(_TMP) / "health"
    hdir.mkdir(parents=True, exist_ok=True)

    # ---- predicate unit: OK / live=2 silent --------------------------------
    ok_path = _write_health(hdir / "ok.json", "OK", 2, 2)
    ok("plane_b_health_failed False on OK live=2", not C.plane_b_health_failed(ok_path))
    ok(
        "eval_pred health_fail False on OK",
        not C.eval_pred({"type": "health_fail", "value": str(ok_path)}, {}),
    )

    # ---- ALL_METHODS_FAILED fires ------------------------------------------
    fail_path = _write_health(hdir / "fail.json", "ALL_METHODS_FAILED", 0, 2)
    ok(
        "plane_b_health_failed True on ALL_METHODS_FAILED",
        C.plane_b_health_failed(fail_path),
    )

    # ---- PARTIAL live < needed fires; live >= needed silent ----------------
    partial_bad = _write_health(hdir / "partial_bad.json", "PARTIAL", 1, 2)
    partial_ok = _write_health(hdir / "partial_ok.json", "PARTIAL", 2, 2)
    ok(
        "PARTIAL live<needed fires",
        C.plane_b_health_failed(partial_bad),
    )
    ok(
        "PARTIAL live>=needed silent",
        not C.plane_b_health_failed(partial_ok),
    )

    # ---- missing / corrupt fail-open silent --------------------------------
    ok(
        "missing health file silent",
        not C.plane_b_health_failed(hdir / "nope.json"),
    )
    bad = hdir / "corrupt.json"
    bad.write_text("{not-json", encoding="utf-8")
    ok("corrupt health file silent", not C.plane_b_health_failed(bad))

    # ---- SessionStart resurface: silent under OK ---------------------------
    _register(ok_path)
    msg = resurface.build_message({"cwd": _TMP, "source": "startup"})
    ok(
        "resurface SILENT when status=OK live=2 (GEM-5 regression)",
        msg is None or ACTION not in msg,
    )
    ok("resurface fully silent with only health_fail+OK", msg is None)

    # ---- SessionStart resurface: fires under ALL_METHODS_FAILED ------------
    _register(fail_path)
    msg = resurface.build_message({"cwd": _TMP, "source": "startup"})
    ok(
        "resurface FIRES cookie-bridge action on ALL_METHODS_FAILED",
        bool(msg) and ACTION in msg and "cookie-bridge" in msg,
    )
    ok("failure message forbids mint/PAT create", bool(msg) and "do not mint PAT" in msg)

    # ---- UserPromptSubmit: silent OK, fires fail ---------------------------
    _register(ok_path)
    m, _ = trigger_match.select_and_fire(
        {"cwd": _TMP, "prompt": "continue warehouse work", "transcript_path": ""}
    )
    ok("trigger_match silent under OK health", m is None)

    _register(fail_path)
    m, changed = trigger_match.select_and_fire(
        {"cwd": _TMP, "prompt": "continue warehouse work", "transcript_path": ""}
    )
    ok(
        "trigger_match fires under ALL_METHODS_FAILED",
        bool(m) and ACTION in m,
    )
    ok("firing wrote back fired_ts (recurring)", changed)

    # ---- live last_health.json: must be silent if OK/live=2 ----------------
    live = Path(r"C:\Users\Prekzursil\infra\access-resilience\state\last_health.json")
    if live.is_file():
        data = json.loads(live.read_text(encoding="utf-8", errors="replace"))
        st = str(data.get("status") or "")
        lv = data.get("live")
        nd = data.get("needed")
        # assert fields only — never print probe/token material
        failed = C.plane_b_health_failed(live)
        if st.upper() == "OK" and int(lv or 0) >= int(nd or 0):
            ok(
                f"LIVE last_health silent (status={st} live={lv} needed={nd})",
                not failed,
            )
            _register(live)
            msg = resurface.build_message({"cwd": _TMP, "source": "startup"})
            ok(
                "LIVE resurface does not surface GEM-5 cookie-bridge under OK",
                msg is None or ACTION not in msg,
            )
        else:
            ok(
                f"LIVE last_health would fire (status={st} live={lv}) — expect True",
                failed,
            )
    else:
        ok("LIVE last_health.json present", False)

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
