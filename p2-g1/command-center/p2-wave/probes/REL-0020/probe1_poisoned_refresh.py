#!/usr/bin/env python3
# REL-0020 probe1: poisoned-state invalidation (resume 2026-10-25).
# Seed the stale v1 payload into EVERY cache location, install the candidate
# with the refresh step, and require the client to EXECUTE new bytes. Also
# fire the recorded controls: refresh disabled still runs old bytes, an EMPTY
# cache is silent in both states (invalid in both directions), and a partial
# refresh (bytecode only) stays masked by the unpacked cache.
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("rel0020_drill", HERE / "drill.py")
D = importlib.util.module_from_spec(spec)
sys.modules["rel0020_drill"] = D
spec.loader.exec_module(D)


def fail(msg):
    print("FAILED:REL-0020-probe1 " + str(msg))
    return 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rel0020-p1-"))
    try:
        # poisoned + refresh: the assertion the empty-cache test cannot make
        c = D.Client(tmp / "canary")
        c.seed_poison()
        c.install(refresh=True)
        r = c.execute()
        print("poisoned+refresh: behaviour=" + str(r["behaviour"]) + " hit=" + str(r["hit"]))
        if r["behaviour"] != D.NEW_MARKER:
            return fail("refresh-did-not-invalidate:" + json.dumps(r))

        # control: refresh disabled -> old bytes still execute (detector fires)
        c2 = D.Client(tmp / "canary-norefresh")
        c2.seed_poison()
        c2.install(refresh=False)
        r2 = c2.execute()
        print("poisoned+refresh-disabled: behaviour=" + str(r2["behaviour"]) + " hit=" + str(r2["hit"]))
        if r2["behaviour"] != D.OLD_MARKER:
            return fail("refresh-disabled-control-did-not-fire")

        # control: EMPTY cache, no refresh -> new bytes via install-tree anyway
        c3 = D.Client(tmp / "canary-empty")
        c3.install(refresh=False)
        r3 = c3.execute()
        print("empty+refresh-disabled: behaviour=" + str(r3["behaviour"]) + " hit=" + str(r3["hit"]))
        if r3["behaviour"] != D.NEW_MARKER:
            return fail("empty-cache-control-drift")

        # control: partial refresh (bytecode only) -> still masked
        c4 = D.Client(tmp / "canary-partial")
        c4.seed_poison()
        shutil.rmtree(c4.caches["bytecode"])
        c4.install(refresh=False)
        r4 = c4.execute()
        print("partial-refresh(bytecode-only): behaviour=" + str(r4["behaviour"]) + " hit=" + str(r4["hit"]))
        if r4["behaviour"] != D.OLD_MARKER or r4["hit"] != "unpacked-user-cache":
            return fail("partial-refresh-control-drift:" + json.dumps(r4))

        rec = json.loads((REPO / "command-center/receipts/REL-0020.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        if "SUCCESS:REL-0020" not in json.dumps(rec):
            return fail("sentinel-absent")
        ctl = rec.get("controls") or {}
        if ctl.get("detector_fires_when_refresh_disabled") is not True or \
           ctl.get("empty_cache_silent_in_both_states") is not True or \
           ctl.get("partial_refresh_bytecode_only_still_masked") is not True:
            return fail("receipt-controls-drift")
        reachable = [l["id"] for l in rec.get("locations") or [] if l.get("reachable")]
        if not reachable:
            return fail("receipt-locations-drift")
        print("receipt-recorded reachable locations: " + json.dumps(reachable))
        print("SUCCESS:REL-0020-probe1 poisoned-refresh")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
