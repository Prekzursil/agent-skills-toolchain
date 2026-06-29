#!/usr/bin/env python3
r"""Tests for heartbeat. Runs WITHOUT pytest: `python test_heartbeat.py`.

Proves the banner reads the three ledgers correctly, ALWAYS fires at SessionStart, and
stays SILENT on a healthy throttled Stop. Direct invocation with sample stdin + sample
ledger state.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

_ROOT = Path(tempfile.mkdtemp(prefix="hb-"))
# Point every ledger path at the throwaway root BEFORE import reads the env.
os.environ["BG_REGISTRY_DIR"] = str(_ROOT / "bg")
os.environ["MEMORY_SPOOL_DIR"] = str(_ROOT / "spool")
os.environ["MCP_LIVENESS_STATE_DIR"] = str(_ROOT / "liveness")
os.environ["HEARTBEAT_CRITICAL_JSON"] = str(_ROOT / "critical.json")
os.environ["HEARTBEAT_STATE_DIR"] = str(_ROOT / "hbstate")
os.environ["HEARTBEAT_THROTTLE_SEC"] = "900"

import heartbeat as H  # noqa: E402

_FAILS = []


def ok(name, cond):
    print(("PASS" if cond else "FAIL") + f": {name}")
    if not cond:
        _FAILS.append(name)


def _mk(*parts) -> Path:
    p = _ROOT.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _set_bg(records_by_session):
    bg = _ROOT / "bg"
    bg.mkdir(parents=True, exist_ok=True)
    for f in bg.glob("*.ndjson"):
        f.unlink()
    for sess, recs in records_by_session.items():
        with (bg / f"{sess}.ndjson").open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")


def _set_spool(n):
    sp = _ROOT / "spool"
    sp.mkdir(parents=True, exist_ok=True)
    for f in sp.glob("*"):
        f.unlink()
    for i in range(n):
        (sp / f"169000000{i}-k{i}.json").write_text("{}", encoding="utf-8")
    (sp / ".reported.json").write_text("{}", encoding="utf-8")  # dot-file must be ignored


def _set_mem(sid, last_state):
    lv = _ROOT / "liveness"
    lv.mkdir(parents=True, exist_ok=True)
    (lv / f"{H._safe(sid)}.json").write_text(json.dumps({"last_state": last_state}), encoding="utf-8")


def _set_reharness(n_tools):
    reg = _mk("reharness-registry.json")
    reg.write_text(json.dumps({"tools": {f"t{i}": {"port": 8000 + i} for i in range(n_tools)}}),
                   encoding="utf-8")
    (_ROOT / "critical.json").write_text(json.dumps({"reharness": {"registry": str(reg)}}),
                                         encoding="utf-8")


def _invoke(mode, stdin_obj):
    buf = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(json.dumps(stdin_obj))
    try:
        with redirect_stdout(buf):
            H.main([mode])
    finally:
        sys.stdin = old
    return buf.getvalue()


def fired(out):
    return "[health]" in out


def main():  # noqa: C901
    # --- ledger readers ---
    _set_bg({"sessA": [
        {"id": "a1", "status": "running"},
        {"id": "a2", "status": "running"},
        {"id": "a3", "status": "running"}, {"id": "a3", "status": "done"},  # folds to done
    ]})
    ok("bg_open_count folds running vs done", H.bg_open_count() == 2)

    _set_spool(1)
    ok("spool_unflushed_count ignores dot-files", H.spool_unflushed_count() == 1)

    _set_mem("S", "down")
    ok("mem_state down -> DOWN", H.mem_state("S") == "DOWN")
    _set_mem("S", "up")
    ok("mem_state up -> up", H.mem_state("S") == "up")
    ok("mem_state missing -> ?", H.mem_state("UNKNOWN_SID") == "?")

    _set_reharness(2)
    ok("reharness_summary counts registered tools", H.reharness_summary() == "2reg")
    _set_reharness(0)
    ok("reharness_summary empty -> off", H.reharness_summary() == "off")

    # --- SessionStart ALWAYS emits the banner ---
    _set_bg({"sessA": [{"id": "a1", "status": "running"}, {"id": "a2", "status": "running"}]})
    _set_spool(1)
    _set_mem("S", "down")
    out = _invoke("sessionstart", {"session_id": "S"})
    ok("SessionStart emits the banner",
       fired(out) and "bg:2open" in out and "spool:1unflushed" in out and "mem:DOWN" in out)

    # --- Stop healthy -> SILENT ---
    _set_bg({})            # no running work
    _set_spool(0)
    _set_mem("S2", "up")
    # fresh throttle state for S2
    out = _invoke("stop", {"session_id": "S2"})
    ok("Stop silent when healthy (0 open, 0 spool, mem up)", not fired(out))

    # --- Stop noteworthy + throttle elapsed -> emits ---
    _set_bg({"sessB": [{"id": "b1", "status": "running"}]})
    H.THROTTLE_SEC = 0  # force past the throttle window
    out = _invoke("stop", {"session_id": "S3"})
    ok("Stop emits when noteworthy + throttle elapsed", fired(out) and "bg:1open" in out)

    # --- Stop noteworthy but WITHIN throttle -> silent ---
    H.THROTTLE_SEC = 900
    H._mark_emit("S4")  # pretend we just emitted
    out = _invoke("stop", {"session_id": "S4"})
    ok("Stop silent within throttle window even if noteworthy", not fired(out))

    # --- probe mode prints banner + SUCCESS marker ---
    buf = io.StringIO()
    with redirect_stdout(buf):
        H.main(["probe"])
    pout = buf.getvalue()
    ok("probe prints banner + SUCCESS marker", "[health]" in pout and "SUCCESS:heartbeat" in pout)

    # --- FAIL-OPEN on bad stdin ---
    old = sys.stdin
    sys.stdin = io.StringIO("garbage {{{")
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = H.main(["sessionstart"])
    finally:
        sys.stdin = old
    # bad stdin -> session_id "default"; SessionStart still emits a banner, never raises.
    ok("fail-open: bad stdin returns 0 and never raises", rc == 0)

    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): {_FAILS}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
