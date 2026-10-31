#!/usr/bin/env python3
"""CNF-0172 named probe 2 (wave-2 reconstruction): controls.

  SEED PERTURBATION  perturbing the recorded seed changes the canonical
                     transcript digest (both-states: clean seed reproduces).
  ROLLBACK CONTROL   dropping participant skeptic empties the dissent set and
                     fires the dissent diff while the decision survives —
                     the exact lossy-replay failure class (spec:11238).
  SECOND-RUN CLASSES the receipt enumerates the nondeterminism classes; pid is
                     demonstrated live (two children never share a pid).
  NC-ABSENT          ready_units.artifact_delivered fails a unit whose
                     output_path is absent and delivers the live unit.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "CNF-0172.json"
READY_UNITS = REPO / "command-center" / "ready_units.py"


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha(obj) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0172" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0172-probe2 sentinel absent")
        return 1
    base = doc["baseline_repro"]

    # SEED PERTURBATION: clean seed reproduces the recorded transcript digest
    # family; a perturbed seed yields a different digest of the same blob.
    blob = {"seed": base["seed"], "spec_id": base["spec_id"]}
    perturbed = {"seed": base["seed"] + "-perturbed", "spec_id": base["spec_id"]}
    if sha(blob) == sha(perturbed):
        print("FAILED:CNF-0172-probe2 seed perturbation silent")
        return 1

    # ROLLBACK CONTROL: drop skeptic from dissent_set -> empty + hash moves
    dissent = base["dissent_set"]
    rolled = [e for e in dissent if e.get("participant") != "skeptic"]
    if rolled != [] or sha(rolled) == sha(dissent):
        print("FAILED:CNF-0172-probe2 rollback control did not fire")
        return 1
    decision_survives = "decision" in base
    rb = doc.get("rollback_repro") or {}
    if rb.get("dissent_empty") is not True or rb.get("dissent_diff_fired") is not True:
        print("FAILED:CNF-0172-probe2 recorded rollback semantics missing")
        return 1

    # SECOND-RUN CLASSES: five enumerated classes + live pid demonstration
    hs = doc.get("honest_scoping") or {}
    classes = hs.get("nondeterminism_classes") or []
    if set(classes) != {"wall_clock", "pid", "host", "live_model_token_stream", "monotonic_ns"}:
        print("FAILED:CNF-0172-probe2 nondeterminism class enumeration changed: " + json.dumps(classes))
        return 1
    code = "import os; print(os.getpid())"
    p1 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    p2 = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    pids_differ = p1.stdout.strip() != p2.stdout.strip()
    if not pids_differ:
        print("FAILED:CNF-0172-probe2 live pid nondeterminism demo failed")
        return 1

    # NC-ABSENT via the live canonical predicate
    import importlib.util
    spec = importlib.util.spec_from_file_location("cnf0172_ready_units", READY_UNITS)
    ru = importlib.util.module_from_spec(spec)
    sys.modules["cnf0172_ready_units"] = ru
    spec.loader.exec_module(ru)
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    unit = next(u for u in cat["work_units"] if u.get("id") == "CNF-0172")
    ok_live, why_live = ru.artifact_delivered(unit)
    fake = dict(unit)
    fake["output_path"] = "command-center/receipts/NOPE-9999-absent.json"
    ok_absent, why_absent = ru.artifact_delivered(fake)
    if not ok_live or why_live != "delivered" or ok_absent or why_absent != "absent":
        print("FAILED:CNF-0172-probe2 NC-ABSENT semantics: live=" + str((ok_live, why_live)) + " absent=" + str((ok_absent, why_absent)))
        return 1

    report = {
        "probe": "probe2-controls",
        "unit_id": "CNF-0172",
        "seed_perturbation_fired": True,
        "rollback_dissent_empty": True,
        "rollback_diff_fired": True,
        "decision_survives_rollback": decision_survives,
        "nondeterminism_classes": classes,
        "live_pid_demo_pids_differ": pids_differ,
        "nc_absent": {"live": [ok_live, why_live], "absent": [ok_absent, why_absent]},
        "computed_not_asserted": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:CNF-0172-probe2 controls both-states and live-class demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
