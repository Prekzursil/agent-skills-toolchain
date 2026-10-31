"""Both-states control for the mechanism-registry CI gate.

A probe that is silent in both states measures nothing. Each check below is
proved able to go RED against a deliberately mutated estate BEFORE its silence
on the real tree is treated as evidence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import mechanism_registry_gate as mech

REPO = Path(__file__).resolve().parents[3]
GATE_REL = "tools/command-center/mechanism_registry_gate.py"


def _copy_estate(dst: Path) -> None:
    (dst / "command-center" / "wfa").mkdir(parents=True, exist_ok=True)
    (dst / "tools" / "command-center").mkdir(parents=True, exist_ok=True)
    for rel in (mech.REL_REGISTRY, mech.REL_INCIDENCE, mech.REL_NAMESPACES, GATE_REL):
        shutil.copy2(REPO / rel, dst / rel)


def _bare_cli(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(root / GATE_REL)],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _load(root: Path, rel: str) -> dict:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def _dump(root: Path, rel: str, doc: dict) -> None:
    (root / rel).write_text(
        json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_live_cli_is_green_with_no_flags():
    proc = subprocess.run(
        [sys.executable, "-B", str(REPO / GATE_REL)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, text
    assert "SUCCESS:mech-registry-gate" in text


def test_validate_py_source_arms_the_gate():
    src = (REPO / "tools/command-center/validate.py").read_text(encoding="utf-8")
    assert "mechanism_registry_gate" in src
    assert "mech.check" in src


def test_detects_undefined_id(tmp_path: Path):
    _copy_estate(tmp_path)
    doc = _load(tmp_path, mech.REL_REGISTRY)
    doc["mechanisms"].append(
        {
            "id": "MX-0099",
            "definition": "",
            "discriminating_example": "planted undefined-id control",
        }
    )
    _dump(tmp_path, mech.REL_REGISTRY, doc)
    proc = _bare_cli(tmp_path)
    text = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert "MECH-UNDEF" in text and "MX-0099" in text


def test_detects_dangling_reference(tmp_path: Path):
    _copy_estate(tmp_path)
    doc = _load(tmp_path, mech.REL_INCIDENCE)
    doc["artifacts"].append(
        {"path": "planted-unknown-ref.json", "mechanism_ids": ["MX-9999"]}
    )
    _dump(tmp_path, mech.REL_INCIDENCE, doc)
    proc = _bare_cli(tmp_path)
    text = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert "MECH-DANGLING" in text and "MX-9999" in text


def test_detects_cross_namespace_collision(tmp_path: Path):
    _copy_estate(tmp_path)
    doc = _load(tmp_path, mech.REL_REGISTRY)
    doc["mechanisms"].append(
        {
            "id": "M-16",
            "definition": "planted collision with the option namespace",
            "discriminating_example": "option id M-16 from 07-OPTION-UNIVERSE",
        }
    )
    _dump(tmp_path, mech.REL_REGISTRY, doc)
    proc = _bare_cli(tmp_path)
    text = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert "MECH-COLLIDE" in text and "M-16" in text
    assert "option namespace" in text


def test_deleting_vocabulary_block_turns_gate_red(tmp_path: Path):
    _copy_estate(tmp_path)
    doc = _load(tmp_path, mech.REL_REGISTRY)
    del doc["mechanisms"]
    _dump(tmp_path, mech.REL_REGISTRY, doc)
    proc = _bare_cli(tmp_path)
    text = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode != 0
    assert "MECH-EMPTY" in text and "no-op-hole" in text


def test_copied_estate_good_state_is_silent(tmp_path: Path):
    _copy_estate(tmp_path)
    proc = _bare_cli(tmp_path)
    text = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, text
    assert "SUCCESS:mech-registry-gate" in text


def test_committed_blob_not_working_tree_crlf(tmp_path: Path):
    _copy_estate(tmp_path)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=wfa0067@local",
            "-c",
            "user.name=wfa0067",
            "commit",
            "-m",
            "estate",
        ],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    path = tmp_path / mech.REL_REGISTRY
    lf = path.read_bytes().replace(b"\r\n", b"\n")
    path.write_bytes(lf.replace(b"\n", b"\r\n"))
    work = path.read_bytes()
    assert b"\r\n" in work
    blob, source = mech.read_blob(tmp_path, mech.REL_REGISTRY)
    assert source == "git-cat-file-HEAD"
    assert blob == lf
    assert blob != work
    proc = _bare_cli(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_no_opt_in_flag_arms_the_checks():
    import ast

    src = (REPO / GATE_REL).read_text(encoding="utf-8")
    tree = ast.parse(src)
    armed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name != "add_argument":
            continue
        flags = [
            a.value
            for a in node.args
            if isinstance(a, ast.Constant) and isinstance(a.value, str)
        ]
        joined = " ".join(flags).lower()
        if any(tok in joined for tok in ("--require", "--check", "--enable", "--skip")):
            armed.append(joined)
    assert armed == []
