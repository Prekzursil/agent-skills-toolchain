"""Detector control for the lane-4 preset gate: prove it goes RED on seeded defects.

A gate that has only ever been green is indistinguishable from a no-op. This probe copies
the 17 owned presets and their manifest into a TEMP directory (nothing in the shared
platform/council/presets/ tree is touched), repoints the gate at the copy, confirms the
unmutated copy is GREEN, then applies one seeded defect at a time and requires the gate to
turn RED for each. Every mutation is reverted before the next.

Each mutation targets a DIFFERENT one of the gate's checks, so a single over-broad check
cannot account for all the kills.

Run: python platform/council/_probe_gate_mutation_control.py
"""

from __future__ import annotations

import copy
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from typing import Any, Callable, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import validate_presets_lane4 as G  # noqa: E402

SUBJECT = "C-H63-rule-authoring-review.councilspec.json"


def _run_gate() -> int:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = G.main([])
    return rc


def _load(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


# ------------------------------------------------------------------ mutations
# Each returns (label, which gate check it should trip, mutate_spec, mutate_manifest)
def mutations() -> List[Tuple[str, str, Callable, Callable]]:
    def drop_source(spec):
        spec["stopping"].pop("source_expression", None)

    def drift_source(spec):
        spec["stopping"]["source_expression"] = (
            "custom:named_routes_verified_present == true AND "
            "custom:both_states_example_given == true AND objections_open == 3"
        )

    def unknown_key(spec):
        spec["stopping_rules"] = {"legacy": True}

    def count_incoherent(spec):
        spec["participants"]["count"]["min"] = 9
        spec["participants"]["count"]["max"] = 4

    def gut_notes(spec):
        spec["metadata"]["notes"] = "SOURCE DESIGN: C-H63. EDITABLE DIALS: rule_path."

    def drop_dials_section(spec):
        spec["metadata"]["notes"] = spec["metadata"]["notes"].replace(
            "EDITABLE DIALS", "dials"
        )

    def drop_charter(spec):
        spec["objective"].pop("charter", None)

    def add_leaf_note(spec):
        spec["stopping"]["expression"]["all_of"][0]["note"] = (
            "explains the metric inline"
        )

    def noop(_spec):
        pass

    def flip_negative_probe(man):
        for case in man["cases"]:
            if case["file"] == SUBJECT:
                case["metrics_not_satisfying"]["objections_open"] = 0

    def understate_warnings(man):
        for case in man["cases"]:
            if case["file"] == SUBJECT:
                case["expected_warnings"] = []

    def delist_subject(man):
        man["cases"] = [c for c in man["cases"] if c["file"] != SUBJECT]

    def man_noop(_man):
        pass

    return [
        ("source_expression removed", "check 3 / documentation", drop_source, man_noop),
        (
            "source_expression drifts from the tree",
            "SEM-001 + check 3",
            drift_source,
            man_noop,
        ),
        ("unknown top-level key added", "JSON Schema", unknown_key, man_noop),
        ("participants.count.min > max", "SEM-002", count_incoherent, man_noop),
        ("metadata.notes truncated", "editability floor", gut_notes, man_noop),
        (
            "EDITABLE DIALS section removed",
            "editability sections",
            drop_dials_section,
            man_noop,
        ),
        ("objective.charter removed", "written-mandate check", drop_charter, man_noop),
        (
            "leaf `note` added alongside source_expression",
            "SEM-001 (the documented conflict)",
            add_leaf_note,
            man_noop,
        ),
        (
            "negative probe made satisfying",
            "both-states control",
            noop,
            flip_negative_probe,
        ),
        (
            "declared warnings understated",
            "warning-set equality",
            noop,
            understate_warnings,
        ),
        (
            "preset delisted from the manifest",
            "owned-file bookkeeping",
            noop,
            delist_subject,
        ),
    ]


def main() -> int:
    src_dir = os.path.join(HERE, "presets")
    tmp_root = tempfile.mkdtemp(prefix="lane4-gate-control-")
    tmp_dir = os.path.join(tmp_root, "presets")
    os.makedirs(tmp_dir)

    with open(
        os.path.join(src_dir, "LANE-4-MANIFEST.json"), "r", encoding="utf-8"
    ) as fh:
        manifest = json.load(fh)
    owned = [c["file"] for c in manifest["cases"]]
    for name in owned:
        shutil.copy2(os.path.join(src_dir, name), os.path.join(tmp_dir, name))
    shutil.copy2(
        os.path.join(src_dir, "LANE-4-MANIFEST.json"),
        os.path.join(tmp_dir, "LANE-4-MANIFEST.json"),
    )

    G.PRESETS_DIR = tmp_dir
    G.MANIFEST = os.path.join(tmp_dir, "LANE-4-MANIFEST.json")

    subject_path = os.path.join(tmp_dir, SUBJECT)
    man_path = G.MANIFEST
    pristine_spec = _load(subject_path)
    pristine_man = _load(man_path)

    control_rc = _run_gate()
    print(
        f"[CONTROL] unmutated copy of {len(owned)} presets -> gate rc={control_rc} "
        f"({'GREEN' if control_rc == 0 else 'RED'})"
    )
    if control_rc != 0:
        print(
            "FAILED:gate-mutation-control the control copy is already red; nothing below is "
            "interpretable"
        )
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1

    killed, survived = 0, []
    for label, target, mut_spec, mut_man in mutations():
        spec = copy.deepcopy(pristine_spec)
        man = copy.deepcopy(pristine_man)
        mut_spec(spec)
        mut_man(man)
        _save(subject_path, spec)
        _save(man_path, man)
        rc = _run_gate()
        verdict = "KILLED" if rc != 0 else "SURVIVED"
        if rc != 0:
            killed += 1
        else:
            survived.append(label)
        print(f"  [{verdict:8}] {label:<48} -> trips {target}")
        _save(subject_path, pristine_spec)
        _save(man_path, pristine_man)

    after_rc = _run_gate()
    print(
        f"[RESTORE] gate rc={after_rc} ({'GREEN' if after_rc == 0 else 'RED'}) - the temp copy "
        "is back to its pristine state"
    )
    shutil.rmtree(tmp_root, ignore_errors=True)

    total = len(mutations())
    print()
    print(f"mutations: {total}  killed: {killed}  survived: {len(survived)} {survived}")
    ok = killed == total and after_rc == 0
    print(
        "SUCCESS:gate-mutation-control every seeded defect turned the gate red"
        if ok
        else f"FAILED:gate-mutation-control {len(survived)} mutation(s) survived"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
