#!/usr/bin/env python3
"""Emit live A1/A2/A6 DESIGN.json into this unit's snapshot tree.

phase3/A*/DESIGN.json is the catalog path for ARC-0003/0010/0038, but a concurrent
ARC-0065 stub writer clobbers those files. ARC-0074 therefore runs those units'
emit_design.py in-process with OUT redirected to
command-center/p2-wave/probes/ARC-0074/dossiers/A{n}/DESIGN.json.

That is not an A9 rebuild: the bytes come from the sibling emitters, not from
catalog titles.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BOOT = HERE / "schema_boot" / "sitecustomize.py"

JOBS = (
    (
        "A1",
        "command-center/p2-wave/probes/ARC-0003/emit_design.py",
        "command-center/p2-wave/probes/ARC-0074/dossiers/A1/DESIGN.json",
        ("A1:precedence.merge", "A1:precedence.new_id_in_overlay"),
    ),
    (
        "A2",
        "command-center/p2-wave/probes/ARC-0010/emit_design.py",
        "command-center/p2-wave/probes/ARC-0074/dossiers/A2/DESIGN.json",
        ("A2:precedence.rule", "A2:hand_edit_rule", "A2:determinism_contract"),
    ),
    (
        "A6",
        "command-center/p2-wave/probes/ARC-0038/emit_design.py",
        "command-center/p2-wave/probes/ARC-0074/dossiers/A6/DESIGN.json",
        ("A6:downgrade_refusal", "A6:tier_map"),
    ),
)


def _load_boot() -> None:
    spec = importlib.util.spec_from_file_location("arc0074_schema_boot", BOOT)
    if spec is None or spec.loader is None:
        raise RuntimeError("schema_boot sitecustomize missing")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)


def _ids(path: Path) -> set[str]:
    sys.path.insert(0, str(HERE))
    try:
        from extract import extract_mechanisms
    finally:
        if sys.path and sys.path[0] == str(HERE):
            sys.path.pop(0)
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"] for m in extract_mechanisms(doc, str(path))}


def _usable(path: Path, required: tuple[str, ...]) -> bool:
    if not path.is_file() or path.stat().st_size < 4000:
        return False
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if doc.get("restored_as_source_dossier_for"):
        return False
    have = _ids(path)
    return set(required) <= have


def run_emit(script_rel: str, out_rel: str) -> int:
    script = REPO / script_rel
    probe_dir = str(script.parent)
    sys.path.insert(0, probe_dir)
    try:
        name = f"arc0074_emit_{script.parent.name}"
        spec = importlib.util.spec_from_file_location(name, script)
        if spec is None or spec.loader is None:
            print(f"FAILED:ARC-0074 restore load {script_rel}")
            return 1
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.OUT = out_rel
        return int(mod.main() or 0)
    finally:
        if sys.path and sys.path[0] == probe_dir:
            sys.path.pop(0)


def restore(force: bool = False) -> int:
    _load_boot()
    for _arch, script, out_rel, required in JOBS:
        dest = REPO / out_rel
        if _usable(dest, required) and not force:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        rc = run_emit(script, out_rel)
        if rc != 0:
            print(f"FAILED:ARC-0074 restore {script} rc={rc}")
            return rc
        if not _usable(dest, required):
            print(f"FAILED:ARC-0074 restore unusable {out_rel}")
            return 1
        # Best-effort mirror to the catalog path; ARC-0065 may clobber it.
        phase = REPO / f"command-center/phase3/{_arch}/DESIGN.json"
        try:
            phase.parent.mkdir(parents=True, exist_ok=True)
            phase.write_bytes(dest.read_bytes())
        except OSError:
            pass
    print("SUCCESS:ARC-0074 restore-sources")
    return 0


def main() -> int:
    return restore(force="--force" in sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
