#!/usr/bin/env python3
"""Live repro-by-component matrix. Scripts are invoked by path, never inlined."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
COMPONENTS = HERE / "fixtures" / "components"
REPROS = HERE / "repros"

REPRO_SCRIPTS = (
    ("repro_unquoted_apostrophe", "repro_unquoted_apostrophe.py"),
    ("repro_empty_required", "repro_empty_required.py"),
    ("repro_nonspecific", "repro_nonspecific.py"),
)

COMPONENT_ORDER = (
    ("defective-quoting", "defective"),
    ("defective-empty-gate", "defective"),
    ("healthy-alpha", "healthy"),
    ("healthy-beta", "healthy"),
    ("healthy-gamma", "healthy"),
)

OWN_TARGET = {
    "repro_unquoted_apostrophe": "defective-quoting",
    "repro_empty_required": "defective-empty-gate",
    "repro_nonspecific": "defective-quoting",
}

FIRE_EXIT = 2


def run_repro(script: Path, component: Path) -> int:
    proc = subprocess.run(
        [sys.executable, "-B", str(script), str(component)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return int(proc.returncode)


def run_matrix() -> dict:
    cells: list[dict] = []
    grid: dict[str, dict[str, int]] = {}
    for repro_id, filename in REPRO_SCRIPTS:
        script = REPROS / filename
        if not script.is_file():
            raise FileNotFoundError(script)
        grid[repro_id] = {}
        for comp_id, role in COMPONENT_ORDER:
            comp = COMPONENTS / comp_id
            if not comp.is_dir():
                raise FileNotFoundError(comp)
            code = run_repro(script, comp)
            if code < 0 or code > 255:
                raise RuntimeError(f"out-of-range exit {code} {repro_id} x {comp_id}")
            grid[repro_id][comp_id] = code
            cells.append(
                {
                    "repro_id": repro_id,
                    "component_id": comp_id,
                    "role": role,
                    "exit_code": code,
                    "fired": code == FIRE_EXIT,
                    "script": str(script.relative_to(REPO)).replace("\\", "/"),
                    "invoked_by_path": True,
                }
            )
    expected = len(REPRO_SCRIPTS) * len(COMPONENT_ORDER)
    if len(cells) != expected:
        raise RuntimeError(f"empty cells: got {len(cells)} want {expected}")
    if any(c.get("exit_code") is None for c in cells):
        raise RuntimeError("empty cell: null exit_code")
    return {
        "repros": [r[0] for r in REPRO_SCRIPTS],
        "components": [{"id": c[0], "role": c[1]} for c in COMPONENT_ORDER],
        "cells": cells,
        "empty_cells": 0,
        "grid": grid,
        "own_target": dict(OWN_TARGET),
        "fire_exit": FIRE_EXIT,
    }


def classify(matrix: dict) -> dict:
    healthy_ids = [c["id"] for c in matrix["components"] if c["role"] == "healthy"]
    accepted: list[str] = []
    quarantined: list[dict] = []
    for repro_id in matrix["repros"]:
        target = OWN_TARGET[repro_id]
        target_code = matrix["grid"][repro_id][target]
        healthy_codes = {hid: matrix["grid"][repro_id][hid] for hid in healthy_ids}
        red_on_healthy = [hid for hid, code in healthy_codes.items() if code == FIRE_EXIT]
        if red_on_healthy:
            quarantined.append(
                {
                    "repro_id": repro_id,
                    "reason": (
                        f"red on healthy component(s) {red_on_healthy} "
                        f"(exit {FIRE_EXIT}); measures environment, not the defect"
                    ),
                    "dependent_conclusions_reopened": True,
                    "red_on_healthy": red_on_healthy,
                    "own_target": target,
                    "own_target_exit_code": target_code,
                }
            )
            continue
        green_healthy = [hid for hid, code in healthy_codes.items() if code == 0]
        if target_code != FIRE_EXIT:
            raise RuntimeError(
                f"{repro_id} did not fire on own target {target} (exit {target_code})"
            )
        if len(green_healthy) < 3:
            raise RuntimeError(
                f"{repro_id} green on {len(green_healthy)} healthy; need >= 3"
            )
        accepted.append(repro_id)
    return {
        "accepted_repros": accepted,
        "quarantined": quarantined,
        "healthy_ids": healthy_ids,
    }


def catalog_sentinel() -> str:
    catalog = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0025":
            return str(unit.get("completion_sentinel") or "")
    raise RuntimeError("CNF-0025 missing from catalog")


CNF23 = HERE.parent / "CNF-0023"
CNF23_GEN = CNF23 / "generated"
CNF23_UNFIXED = CNF23 / "fixtures" / "unfixed"
CNF23_FIXED = CNF23 / "fixtures" / "fixed"
CNF23_SCRIPTS = (
    "r_apostrophe.py",
    "r_option_id.py",
    "r_sidecar.py",
    "r_pin.py",
)


def run_cnf23_specificity() -> dict:
    """Run CNF-0023 mechanised scripts: red on unfixed, green on three healthy copies of fixed."""
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="cnf0025-cnf23-") as tmp:
        healthy: list[tuple[str, Path]] = []
        for name in ("healthy-alpha", "healthy-beta", "healthy-gamma"):
            dest = Path(tmp) / name
            shutil.copytree(CNF23_FIXED, dest)
            (dest / "COMPONENT-ID.txt").write_text(name + "\n", encoding="utf-8")
            healthy.append((name, dest))
        for filename in CNF23_SCRIPTS:
            script = CNF23_GEN / filename
            if not script.is_file():
                raise FileNotFoundError(script)
            unfixed_code = run_repro(script, CNF23_UNFIXED)
            healthy_codes = {hid: run_repro(script, dest) for hid, dest in healthy}
            row = {
                "repro_id": filename,
                "script": str(script.relative_to(REPO)).replace("\\", "/"),
                "invoked_by_path": True,
                "unfixed_exit": unfixed_code,
                "fired_on_unfixed": unfixed_code != 0,
                "healthy_exits": healthy_codes,
                "silent_on_three_healthy": all(code == 0 for code in healthy_codes.values()),
            }
            rows.append(row)
    return {
        "rows": rows,
        "all_specific": all(
            r["fired_on_unfixed"] and r["silent_on_three_healthy"] for r in rows
        ),
        "declared_cnf0023_artifact": "command-center/confirmation/CNF-0023-mechanised-repros.json",
        "declared_cnf0023_present": (
            (REPO / "command-center/confirmation/CNF-0023-mechanised-repros.json").is_file()
        ),
        "scripts_used": [str((CNF23_GEN / f).relative_to(REPO)).replace("\\", "/") for f in CNF23_SCRIPTS],
    }


def _copy_files(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.is_file():
            (dest / item.name).write_bytes(item.read_bytes())


def run_mutation_controls() -> dict:
    """Plant/fix copies: quoting and empty-REQUIRED must track the planted defect."""
    quoting = REPROS / "repro_unquoted_apostrophe.py"
    empty = REPROS / "repro_empty_required.py"
    with tempfile.TemporaryDirectory(prefix="cnf0025-mut-") as tmp:
        planted = Path(tmp) / "planted-quoting"
        _copy_files(COMPONENTS / "healthy-alpha", planted)
        (planted / "inline.sh").write_text(
            "#!/bin/sh\npython3 -c 'print('hello')'\n", encoding="utf-8"
        )
        planted_code = run_repro(quoting, planted)

        fixed = Path(tmp) / "fixed-quoting"
        _copy_files(COMPONENTS / "defective-quoting", fixed)
        (fixed / "inline.sh").write_text(
            '#!/bin/sh\npython3 -c "print(\'hello\')"\n', encoding="utf-8"
        )
        fixed_code = run_repro(quoting, fixed)

        planted_gate = Path(tmp) / "planted-empty"
        _copy_files(COMPONENTS / "healthy-beta", planted_gate)
        (planted_gate / "REQUIRED.txt").write_bytes(b"")
        gate_fire = run_repro(empty, planted_gate)

        filled = Path(tmp) / "filled-gate"
        _copy_files(COMPONENTS / "defective-empty-gate", filled)
        (filled / "REQUIRED.txt").write_text("gate-ok\n", encoding="utf-8")
        gate_fixed = run_repro(empty, filled)

    return {
        "planted_apostrophe_exit": planted_code,
        "fixed_quoting_exit": fixed_code,
        "planted_empty_required_exit": gate_fire,
        "filled_required_exit": gate_fixed,
        "ok": planted_code == FIRE_EXIT
        and fixed_code == 0
        and gate_fire == FIRE_EXIT
        and gate_fixed == 0,
    }


if __name__ == "__main__":
    m = run_matrix()
    c = classify(m)
    print(json.dumps({"matrix": m, "classify": c}, indent=1, sort_keys=True))
