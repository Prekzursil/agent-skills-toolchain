#!/usr/bin/env python3
# REL-0022 probe2: mutation controls (resume 2026-10-25).
# (1) hole control: the installer variant that writes an UNRECORDED side
#     effect must turn the subtraction red (hole_count=1, key
#     fs:create:.ast-plugin/cache/unrecorded.bin).
# (2) stale control: an inverse set missing one recorded row must leave that
#     observed effect reported STALE (stale_count=1).
# (3) isolation: the observer must refuse to census the login home.
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def fail(msg):
    print("FAILED:REL-0022-probe2 " + str(msg))
    return 1


def main():
    O = load("observer")
    C = load("coverage")
    rec = json.loads((REPO / "command-center/receipts/REL-0022.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    hm = rec.get("hole_mutation") or {}
    if hm.get("fired") is not True:
        return fail("receipt-hole-mutation-drift")
    tmp = Path(tempfile.mkdtemp(prefix="rel0022-p2-"))
    try:
        # (1) hole control
        home = tmp / "canary-hole"
        home.mkdir()
        (home / "settings.json").write_text(json.dumps({"owner_marker": "keep-me"}),
                                            encoding="utf-8", newline=chr(10))
        eff = O.observe(home, lambda: subprocess.run(
            [sys.executable, "-B", str(HERE / "installer.py"), "--home", str(home),
             "--variant", "unrecorded-write"], capture_output=True, timeout=300, check=True))
        recorded = C.load_recorded(HERE / "fixtures" / "inverse_set.json")
        sub = C.subtract(eff["effect_keys"], recorded)
        print("hole-control: holes=" + json.dumps(sub["holes"]) + " count=" + str(sub["hole_count"]))
        if sub["hole_count"] != 1 or "fs:create:.ast-plugin/cache/unrecorded.bin" not in sub["holes"]:
            return fail("hole-control-did-not-fire")
        # (2) stale control
        home2 = tmp / "canary-stale"
        home2.mkdir()
        (home2 / "settings.json").write_text(json.dumps({"owner_marker": "keep-me"}),
                                             encoding="utf-8", newline=chr(10))
        eff2 = O.observe(home2, lambda: subprocess.run(
            [sys.executable, "-B", str(HERE / "installer.py"), "--home", str(home2),
             "--variant", "skip-timer"], capture_output=True, timeout=300, check=True))
        sub2 = C.subtract(eff2["effect_keys"], recorded)
        print("stale-control: stale=" + json.dumps(sub2["stale"]))
        if sub2["stale_count"] != 1 or sub2["stale"][0] != "fs:create:.ast-plugin/tasks/rel0022.timer":
            return fail("stale-control-did-not-fire")
        # (3) isolation: census refuses the login home
        login = Path.home()
        try:
            O.observe(login, lambda: None)
            return fail("observer-censused-login-home")
        except (PermissionError, ValueError, RuntimeError):
            print("isolation: login-home census refused")
        print("SUCCESS:REL-0022-probe2 mutation-controls")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
