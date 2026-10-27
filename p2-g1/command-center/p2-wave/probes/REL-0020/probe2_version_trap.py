#!/usr/bin/env python3
# REL-0020 probe2: version-string trap + live mutations (resume 2026-10-25).
# The version file is NOT the invalidation signal: with stale bytes still
# executing, flipping the version file to the candidate version changes
# nothing about behaviour. Mutations: editing the cached payload's behaviour
# marker must move the observed behaviour (the oracle reads executed bytes,
# not a string), and deleting the unpacked cache shifts the resolution hit.
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
    print("FAILED:REL-0020-probe2 " + str(msg))
    return 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rel0020-p2-"))
    try:
        c = D.Client(tmp / "canary")
        c.seed_poison()
        c.install(refresh=False)
        before = c.execute()
        vfile = c.version_file()
        print("before: behaviour=" + str(before["behaviour"]) + " version_file=" + vfile)
        if before["behaviour"] != D.OLD_MARKER or vfile != D.NEW_VERSION:
            return fail("trap-not-armed")
        # version flip only: behaviour unchanged
        r = c.execute()
        if r["behaviour"] != D.OLD_MARKER:
            return fail("version-flip-changed-behaviour")
        print("version-trap: file says " + vfile + " while executed=" + str(r["behaviour"])
              + " hit=" + str(r["hit"]))
        # mutation: rewrite the cached payload marker -> observed behaviour moves
        p = c.caches["bytecode"] / "rel0020-canary-plugin.pyc"
        payload = json.loads(p.read_bytes().decode("utf-8"))
        payload["behaviour"] = "BEHAVE-MUTATED-PROBE"
        p.write_bytes(json.dumps(payload).encode())
        rm = c.execute()
        print("mutation: behaviour=" + str(rm["behaviour"]) + " hit=" + str(rm["hit"]))
        if rm["behaviour"] != "BEHAVE-MUTATED-PROBE":
            return fail("mutation-not-observed")
        # mutation: delete bytecode -> hit shifts down the resolution order
        shutil.rmtree(c.caches["bytecode"])
        rs = c.execute()
        print("delete-bytecode: behaviour=" + str(rs["behaviour"]) + " hit=" + str(rs["hit"]))
        if rs["hit"] != "unpacked-user-cache":
            return fail("resolution-shift-not-observed:" + json.dumps(rs))
        rec = json.loads((REPO / "command-center/receipts/REL-0020.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        # w4s12: receipt_core.profile is a string slug; the isolation-profile
        # facts moved verbatim to extensions.execution_profile_preserved
        profile = rec.get("profile")
        if not isinstance(profile, dict):
            profile = (rec.get("extensions") or {}).get("execution_profile_preserved") or {}
        if profile.get("fresh_per_attempt") is not True or profile.get("destroyed_after") is not True:
            return fail("receipt-profile-drift")
        ro = rec.get("resolution_order") or []
        if not ro or ro[0] != "bytecode":
            return fail("receipt-resolution-order-drift")
        print("receipt resolution_order=" + json.dumps(ro))
        print("SUCCESS:REL-0020-probe2 version-trap-and-mutations")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
