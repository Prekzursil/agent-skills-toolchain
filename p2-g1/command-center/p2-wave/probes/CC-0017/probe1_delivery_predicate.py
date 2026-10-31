"""probe1: G-1 delivery predicate for CC-0017 (mode=deliver), exit 0 = green."""

import copy
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "CC-0017"
sys.path.insert(0, str(REPO / "platform" / "lib"))
_spec = importlib.util.spec_from_file_location("schema_resolver_probe", REPO / "platform" / "lib" / "schema_resolver.py")
_resolver_mod = importlib.util.module_from_spec(_spec)
sys.modules["schema_resolver_probe"] = _resolver_mod
_spec.loader.exec_module(_resolver_mod)

def _load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_ENTRY = None
_CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
for _u in _CAT["work_units"]:
    if isinstance(_u, dict) and _u.get("id") == UID:
        _ENTRY = _u
        break
assert _ENTRY is not None, "catalog entry missing for " + UID
_OUT = REPO / _ENTRY["output_path"]
_TEXT = _OUT.read_text(encoding="utf-8")
_DOC = json.loads(_TEXT)
_FAILS = []
def check(name, cond):
    ok = bool(cond)
    print(("  ok  " if ok else " FAIL ") + name)
    if not ok:
        _FAILS.append(name)

def main() -> int:
    mode = "deliver"
    schema = _ENTRY["output_schema"]
    errs = _resolver_mod.validate_artifact(_DOC, schema)
    check("parses-and-schema-valid(" + str(len(errs)) + " errors)", not errs)
    if mode == "deliver":
        st = str(_DOC.get("state") or "")
        check("state==SUCCESS", st == "SUCCESS")
        cs = str(_ENTRY.get("completion_sentinel") or "")
        check("catalog-sentinel-in-text", cs in _TEXT)
        rev = _DOC.get("reviewer") or {}
        check("reviewer-PASS-independent", rev.get("verdict") == "PASS" and rev.get("independent") is True)
        check("evidence>=2", len(_DOC.get("evidence") or []) >= 2)
        ts = _DOC.get("tests") or []
        check("tests>=1-all-PASS", len(ts) >= 1 and all(t.get("result") == "PASS" for t in ts))
        nc = _DOC.get("negative_controls") or []
        check("neg-controls>=1-both-states-true", len(nc) >= 1 and all(
            c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True for c in nc))
        dc = _DOC.get("downstream_consumers") or []
        check("downstream>=1-executed-read", len(dc) >= 1 and all(
            c.get("executed") is True and c.get("read_ok") is True for c in dc))
    else:
        st = str(_DOC.get("state") or "")
        check("state==BLOCKED", st == "BLOCKED")
        f = _DOC.get("failure") or {}
        check("failure-classified", bool(f.get("classification")) and bool(f.get("reason")))
    mr = _DOC.get("manifest_registration") or {}
    man = REPO / str(mr.get("manifest_path") or "x")
    check("manifest-registered+file-exists", mr.get("registered") is True and man.is_file())
    rows = [a for a in ((json.loads(man.read_text(encoding="utf-8")).get("artifacts") if man.is_file() else None) or [])
            if isinstance(a, dict) and a.get("unit_id") == UID and a.get("path") == _ENTRY["output_path"].replace("\\", "/")]
    check("manifest-has-unit-row", bool(rows))
    for line in errs[:5]:
        print("  schema:", line[:160])
    if _FAILS:
        print("FAILED:" + UID + "-probe1 " + "; ".join(_FAILS))
        return 1
    print("SUCCESS:" + UID + "-probe1 delivery predicate green")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
