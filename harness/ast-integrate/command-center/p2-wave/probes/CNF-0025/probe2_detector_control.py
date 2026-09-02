#!/usr/bin/env python3
"""Probe 2: independent DETECTOR CONTROL re-run (reviewer). Does not trust emit.py."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_ok as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0025-repro-specificity.json"
REPROS = HERE / "repros"
COMPONENTS = HERE / "fixtures" / "components"
CNF23_GEN = HERE.parent / "CNF-0023" / "generated"
CNF23_UNFIXED = HERE.parent / "CNF-0023" / "fixtures" / "unfixed"
CNF23_FIXED = HERE.parent / "CNF-0023" / "fixtures" / "fixed"

ACCEPTED = (
    ("repro_unquoted_apostrophe", "repro_unquoted_apostrophe.py", "defective-quoting"),
    ("repro_empty_required", "repro_empty_required.py", "defective-empty-gate"),
)
HEALTHY = ("healthy-alpha", "healthy-beta", "healthy-gamma")
NONSPECIFIC = REPROS / "repro_nonspecific.py"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0025-probe2 {msg}")
    return 1


def invoke(script: Path, component: Path) -> int:
    proc = subprocess.run(
        [sys.executable, "-B", str(script), str(component)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return int(proc.returncode)


def copy_tree(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.is_file():
            (dest / item.name).write_bytes(item.read_bytes())


def catalog_sentinel() -> str:
    catalog = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0025":
            return str(unit.get("completion_sentinel") or "")
    return ""


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = catalog_sentinel()
    if not sentinel or sentinel not in text:
        return fail("completion_sentinel absent")
    errors = S.iter_errors(doc)
    if errors:
        return fail(f"schema {errors[0].message}")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    blob = " ".join(
        str(reviewer.get(k) or "") for k in ("scope", "notes", "reviewer_id")
    )
    if "detector control" not in blob.lower():
        return fail("reviewer scope is not detector-control")

    payload = S.payload(doc)

    for repro_id, filename, broken in ACCEPTED:
        script = REPROS / filename
        code_broken = invoke(script, COMPONENTS / broken)
        print(f"control {repro_id} known-broken={broken} exit={code_broken}")
        if code_broken != 2:
            return fail(f"{repro_id} did not fire on known-broken {broken}")
        silent = []
        for hid in HEALTHY:
            code = invoke(script, COMPONENTS / hid)
            print(f"control {repro_id} healthy={hid} exit={code}")
            if code != 0:
                return fail(f"{repro_id} fired on healthy {hid}")
            silent.append(hid)
        if len(silent) < 3:
            return fail(f"{repro_id} fewer than 3 healthy silents")

    ns_alpha = invoke(NONSPECIFIC, COMPONENTS / "healthy-alpha")
    print(f"nonspecific on healthy-alpha exit={ns_alpha}")
    if ns_alpha != 2:
        return fail("nonspecific control did not fire on healthy")
    q_ids = [q.get("repro_id") for q in (payload.get("quarantined") or [])]
    if "repro_nonspecific" not in q_ids:
        return fail("artifact did not quarantine nonspecific repro")

    with tempfile.TemporaryDirectory(prefix="cnf0025-dc-") as tmp:
        planted = Path(tmp) / "planted-quoting"
        copy_tree(COMPONENTS / "healthy-alpha", planted)
        (planted / "inline.sh").write_text(
            "#!/bin/sh\npython3 -c 'print('hello')'\n", encoding="utf-8"
        )
        planted_code = invoke(REPROS / "repro_unquoted_apostrophe.py", planted)
        print(f"planted-apostrophe-on-healthy-copy exit={planted_code}")
        if planted_code != 2:
            return fail("quoting repro silent after planting defect on healthy copy")

        fixed = Path(tmp) / "fixed-quoting"
        copy_tree(COMPONENTS / "defective-quoting", fixed)
        (fixed / "inline.sh").write_text(
            '#!/bin/sh\npython3 -c "print(\'hello\')"\n', encoding="utf-8"
        )
        fixed_code = invoke(REPROS / "repro_unquoted_apostrophe.py", fixed)
        print(f"fixed-quoting-copy exit={fixed_code}")
        if fixed_code != 0:
            return fail("quoting repro still fires after fixing known-broken copy")

        planted_gate = Path(tmp) / "planted-empty"
        copy_tree(COMPONENTS / "healthy-beta", planted_gate)
        (planted_gate / "REQUIRED.txt").write_bytes(b"")
        gate_fire = invoke(REPROS / "repro_empty_required.py", planted_gate)
        print(f"planted-empty-REQUIRED-on-healthy-copy exit={gate_fire}")
        if gate_fire != 2:
            return fail("empty-required repro silent after planting empty gate")

        filled = Path(tmp) / "filled-gate"
        copy_tree(COMPONENTS / "defective-empty-gate", filled)
        (filled / "REQUIRED.txt").write_text("gate-ok\n", encoding="utf-8")
        gate_fixed = invoke(REPROS / "repro_empty_required.py", filled)
        print(f"filled-REQUIRED-copy exit={gate_fixed}")
        if gate_fixed != 0:
            return fail("empty-required repro still fires after filling gate")

        for filename in ("r_apostrophe.py", "r_option_id.py", "r_sidecar.py", "r_pin.py"):
            script = CNF23_GEN / filename
            unfixed_code = invoke(script, CNF23_UNFIXED)
            if unfixed_code == 0:
                return fail(f"CNF-0023 {filename} silent on unfixed")
            for name in HEALTHY:
                dest = Path(tmp) / f"cnf23-{filename}-{name}"
                shutil.copytree(CNF23_FIXED, dest)
                (dest / "COMPONENT-ID.txt").write_text(name + "\n", encoding="utf-8")
                code = invoke(script, dest)
                if code != 0:
                    return fail(f"CNF-0023 {filename} fired on healthy copy {name} exit={code}")
            print(f"cnf23 {filename} unfixed={unfixed_code} three-healthy-silent")

    dc = payload.get("detector_control") or {}
    if dc.get("known_broken_fired") is not True:
        return fail("artifact detector_control.known_broken_fired is not true")
    if int(dc.get("known_healthy_silent_count") or 0) < 6:
        return fail("artifact known_healthy_silent_count < 6 (2 repros x 3 healthy)")

    print("reviewer_id=" + str(reviewer.get("reviewer_id")))
    print("SUCCESS:CNF-0025-probe2 detector-control re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
