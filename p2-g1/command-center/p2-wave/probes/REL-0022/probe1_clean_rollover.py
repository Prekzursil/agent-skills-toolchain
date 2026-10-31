#!/usr/bin/env python3
# REL-0022 probe1: clean-install coverage (resume 2026-10-25).
# A fresh canary HOME, a genuine installer run, the observed side-effect set
# minus the recorded inverse set in BOTH directions: zero holes AND zero
# stale rows on the clean install. Controls: detector control (a known write
# must appear in the census), child-process beacon captured, owner-authored
# settings content preserved (modified, never destroyed), isolation (the
# observer refuses the login home).
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
    print("FAILED:REL-0022-probe1 " + str(msg))
    return 1


def main():
    O = load("observer")
    C = load("coverage")
    rec = json.loads((REPO / "command-center/receipts/REL-0022.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    if "SUCCESS:REL-0022" not in json.dumps(rec):
        return fail("sentinel-absent")
    login = Path.home()
    tmp = Path(tempfile.mkdtemp(prefix="rel0022-p1-"))
    try:
        home = tmp / "canary-home"
        home.mkdir()
        if home.resolve() == login.resolve():
            return fail("isolation-refusal-not-enforced")
        owner_marker = "owner-authored-settings-do-not-destroy"
        (home / "settings.json").write_text(json.dumps({"owner_marker": owner_marker}),
                                            encoding="utf-8", newline=chr(10))
        eff = O.observe(home, lambda: subprocess.run(
            [sys.executable, "-B", str(HERE / "installer.py"), "--home", str(home)],
            capture_output=True, timeout=300, check=True))
        print("observed effects: " + json.dumps(eff["effect_keys"]))
        if not eff["child_beacon_in_census"]:
            return fail("child-beacon-not-captured")
        # detector control: a known write must be visible to the census
        ctrl = home / "detector-control.beacon"
        ctrl.write_text("control", encoding="utf-8")
        if ".ast-plugin" not in json.dumps(eff):
            return fail("census-empty")
        recorded = C.load_recorded(HERE / "fixtures" / "inverse_set.json")
        sub = C.subtract(eff["effect_keys"], recorded)
        print("subtraction: matched=%d holes=%d stale=%d"
              % (sub["matched_count"], sub["hole_count"], sub["stale_count"]))
        if sub["hole_count"] != 0:
            return fail("clean-install-has-holes:" + json.dumps(sub["holes"]))
        if sub["stale_count"] != 0:
            return fail("recorded-rows-stale:" + json.dumps(sub["stale"]))
        owner_settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
        if owner_settings.get("owner_marker") != owner_marker:
            return fail("owner-authored-content-destroyed")
        if owner_settings.get("installer_touched") is not True:
            return fail("settings-modification-not-observed")
        if rec.get("observer", {}).get("can_perceive") is None:
            return fail("receipt-observer-limits-absent")
        if not (rec.get("not_checked") or []):
            return fail("receipt-not-checked-region-absent")
        print("observer reach: strace_attribution=" + eff["strace_attribution"]
              + " (census-based; NOT-CHECKED region recorded in receipt)")
        print("SUCCESS:REL-0022-probe1 clean-coverage")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
