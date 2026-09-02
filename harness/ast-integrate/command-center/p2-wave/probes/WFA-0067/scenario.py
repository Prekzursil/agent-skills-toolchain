"""Estate copy + planted mutations for WFA-0067 probes.

CI form is a bare ``python tools/command-center/mechanism_registry_gate.py``
(no extra flags). Planted estates copy the gate script so ``repo_root()``
resolves to the temp tree.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import mechanism_registry_gate as mech  # noqa: E402

GATE_REL = "tools/command-center/mechanism_registry_gate.py"
CI_INVOCATION = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {GATE_REL}"
VALIDATE_CI = "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/command-center/validate.py"


def copy_estate(dst: Path) -> None:
    (dst / "command-center" / "wfa").mkdir(parents=True, exist_ok=True)
    (dst / "tools" / "command-center").mkdir(parents=True, exist_ok=True)
    for rel in (mech.REL_REGISTRY, mech.REL_INCIDENCE, mech.REL_NAMESPACES, GATE_REL):
        shutil.copy2(REPO / rel, dst / rel)


def dump(root: Path, rel: str, doc: dict) -> None:
    (root / rel).write_text(
        json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load(root: Path, rel: str) -> dict:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def bare_cli(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(root / GATE_REL)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def live_cli() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(REPO / GATE_REL)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def live_validate_cli() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(REPO / "tools" / "command-center" / "validate.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def plant_undefined(root: Path) -> None:
    doc = load(root, mech.REL_REGISTRY)
    doc["mechanisms"].append(
        {
            "id": "MX-0099",
            "definition": "",
            "discriminating_example": "planted undefined-id control",
        }
    )
    dump(root, mech.REL_REGISTRY, doc)


def plant_dangling(root: Path) -> None:
    doc = load(root, mech.REL_INCIDENCE)
    doc["artifacts"].append(
        {"path": "planted-unknown-ref.json", "mechanism_ids": ["MX-9999"]}
    )
    dump(root, mech.REL_INCIDENCE, doc)


def plant_collision(root: Path) -> None:
    doc = load(root, mech.REL_REGISTRY)
    doc["mechanisms"].append(
        {
            "id": "M-16",
            "definition": "planted collision with the option namespace",
            "discriminating_example": "option id M-16 from 07-OPTION-UNIVERSE",
        }
    )
    dump(root, mech.REL_REGISTRY, doc)


def plant_deleted_block(root: Path) -> None:
    doc = load(root, mech.REL_REGISTRY)
    del doc["mechanisms"]
    dump(root, mech.REL_REGISTRY, doc)


def out_of(proc: subprocess.CompletedProcess[str]) -> str:
    return ((proc.stdout or "") + (proc.stderr or "")).strip()
