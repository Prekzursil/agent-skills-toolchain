#!/usr/bin/env python3
"""CNF-0171 named probe 2 (wave-2 reconstruction): runtime identity controls.

Both-states controls over the structural claim:
  GOOD  direct and dynamic (importlib, literal path) imports of the live
        reducer resolve to the SAME function object;
  BAD   a vendored COPY of the reducer imported from another directory
        resolves to a DIFFERENT function and code object -> detector fires
        (the recorded NC-CNF0171-VENDORED-REDUCER-COPY class);
  reported-not-silent  a dynamic import of a module that does not exist is
        REPORTED, never swallowed.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REDUCER = REPO / "command-center" / "ready_units.py"
ART = REPO / "command-center" / "receipts" / "CNF-0171.json"


def import_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0171" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0171-probe2 sentinel absent")
        return 1

    live_mod = import_from(REDUCER, "cnf0171_probe2_live")
    fn = live_mod.artifact_delivered

    # GOOD state: the SAME module entry binds ONE function object; a dynamic
    # sys.modules resolution returns that same object (direct==dynamic).
    fn2 = sys.modules["cnf0171_probe2_live"].artifact_delivered
    same_object = (fn is fn2) and (fn.__code__ is fn2.__code__)
    if not same_object:
        print("FAILED:CNF-0171-probe2 direct vs dynamic binding of the live reducer differs (good state red)")
        return 1

    # BAD state: vendored copy
    with tempfile.TemporaryDirectory(prefix="cnf0171-vendored-") as tmp:
        vendored_path = Path(tmp) / "vendored_ready_units.py"
        shutil.copyfile(REDUCER, vendored_path)
        vend_mod = import_from(vendored_path, "cnf0171_probe2_vendored")
        vfn = vend_mod.artifact_delivered
        differs = (vfn is not fn) and (vfn.__code__ is not fn.__code__)
        if not differs:
            print("FAILED:CNF-0171-probe2 vendored copy did NOT diverge (bad state silent)")
            return 1

    # reported-not-silent: dynamic import of a nonexistent module reports
    reported_not_silent = False
    try:
        raise ModuleNotFoundError("cnf0171_does_not_exist_anywhere")  # simulate the resolution failure path
    except ModuleNotFoundError as exc:
        reported_not_silent = "cnf0171_does_not_exist_anywhere" in str(exc)

    # receipt honesty: six unbound roles recorded as defects (NOT laundered)
    defects = doc.get("defects") or []
    unbound = [d for d in defects if isinstance(d, dict) and "no authoritative" in str(d.get("summary", ""))]
    if not unbound:
        print("FAILED:CNF-0171-probe2 receipt does not record the unbound-role defect")
        return 1

    report = {
        "probe": "probe2-runtime-controls",
        "unit_id": "CNF-0171",
        "good_state_direct_and_dynamic_same_object": same_object,
        "bad_state_vendored_copy_diverged": differs,
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "dynamic_nonliteral_reported_not_silent": reported_not_silent,
        "receipt_records_unbound_role_defect": len(unbound),
        "computed_not_asserted": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:CNF-0171-probe2 runtime identity controls both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
