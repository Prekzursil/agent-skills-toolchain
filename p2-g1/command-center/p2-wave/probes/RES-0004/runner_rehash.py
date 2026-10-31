#!/usr/bin/env python3
# RES-0004 fresh-process store rehash (the receipt completion_sentinel clause:
# "a snapshot store exists whose every entry re-hashes to its recorded sha256
# in a fresh process"). Loads the store module by path in THIS fresh
# interpreter and verifies every entry.
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("res0004_store", REPO / "command-center/lib/evidence_snapshot/store.py")
S = importlib.util.module_from_spec(spec)
sys.modules["res0004_store"] = S
spec.loader.exec_module(S)


def main():
    res = S.verify_store()
    print("fresh-process rehash: entries=%d ok=%d corrupt=%s"
          % (res["entries"], res["ok"], json_dumps(res["corrupt"])))
    if not res["all_ok"]:
        print("FAILED:RES-0004-runner corrupt-entries:" + ",".join(res["corrupt"]))
        return 1
    print("SUCCESS:RES-0004-runner all-entries-rehash")
    return 0


def json_dumps(v):
    import json
    return json.dumps(v)


if __name__ == "__main__":
    raise SystemExit(main())
