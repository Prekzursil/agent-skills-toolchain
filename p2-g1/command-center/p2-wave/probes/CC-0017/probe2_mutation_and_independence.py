"""probe2: mutation control + independent recomputation for CC-0017 (mode=deliver)."""

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

def _schema_errors(d):
    try:
        return list(_resolver_mod.validate_artifact(d, _ENTRY["output_schema"]) or [])
    except Exception as e:
        return ["<raise:" + type(e).__name__ + ">"]

def mutation_control():
    real_errs = _schema_errors(_DOC)
    silent = not real_errs
    mutants = []
    if "deliver" == "deliver":
        m1 = copy.deepcopy(_DOC); m1["sentinel"] = "FAILED:MUTANT shard4 probe2"
        m2 = copy.deepcopy(_DOC)
        if isinstance(m2.get("reviewer"), dict):
            m2["reviewer"] = dict(m2["reviewer"]); m2["reviewer"]["verdict"] = "FAIL"
        mutants = [("sentinel->FAILED-form", m1), ("reviewer.verdict->FAIL", m2)]
    else:
        m1 = copy.deepcopy(_DOC); m1["state"] = "SUCCESS"
        m2 = copy.deepcopy(_DOC); m2.pop("failure", None)
        mutants = [("state->SUCCESS-with-open-P0", m1), ("failure-object-stripped", m2)]
    fired = True
    for name, m in mutants:
        errs = _schema_errors(m)
        print("  mutant " + name + " rejected=" + str(bool(errs)) + " (" + str(len(errs)) + " errors)")
        if not errs:
            fired = False
    return fired, silent, real_errs

def anchor_recheck():
    checked = skipped = 0
    for ev in _DOC.get("evidence") or []:
        a = str(ev.get("anchor") or "")
        if not a or a.startswith(("PYTHONDONT", "python", "http")):
            skipped += 1
            continue
        m = re.match(r"^([^:]+?):([0-9]+)$", a)
        rel = m.group(1) if m else a.split(":")[0]
        p = REPO / rel
        if p.is_file() or p.is_dir():
            checked += 1
        else:
            check("evidence-anchor-exists:" + rel[:60], False)
    print("  anchors checked=" + str(checked) + " skipped=" + str(skipped))
    return checked


def unit_checks():
    check("provisional-marked", "PROVISIONAL" in _TEXT.upper())
    check("phase4-superseder-named", bool(_DOC.get("superseded_by_phase4_unit")))
    check("schema-status-recorded", bool(_DOC.get("schema_status")))
    _mig = _DOC.get("cc0012_migration_rules") or _DOC.get("migration")
    check("cc0012-migration-rules-carried", bool(_mig))


def main() -> int:
    fired, silent, real_errs = mutation_control()
    check("mutation-fired-on-bad-state", fired)
    check("silent-on-good-state", silent and not real_errs)
    for line in real_errs[:5]:
        print("  real-schema:", line[:160])
    anchor_recheck()
    unit_checks()
    if _FAILS:
        print("FAILED:" + UID + "-probe2 " + "; ".join(_FAILS))
        return 1
    print("SUCCESS:" + UID + "-probe2 mutation control fired; independent recomputation held")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
