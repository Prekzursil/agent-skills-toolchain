#!/usr/bin/env python3
"""Probe 1: 72/72 presets and 58/58 protocols validate; jsonschema agrees.

Independent engine is tools/council/schema/jsonschema_cli.py (validator_for,
the selector used by python3 -m jsonschema) plus one live python3 -m jsonschema
invocation from a non-repo cwd so stdlib platform is not shadowed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0261"
VALIDATE = REPO / "tools/council/validate.py"
JSCLI = REPO / "tools/council/schema/jsonschema_cli.py"
SCHEMA = REPO / "tools/council/schema/councilspec.schema.json"
LIBRARY = REPO / "tools/council/schema/library.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def run(cmd: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    return json.loads(text)


def ensure_library() -> None:
    if LIBRARY.is_file():
        return
    sys.path.insert(0, str(REPO / "tools"))
    from council.schema.library import write_library  # noqa: WPS433

    write_library(LIBRARY)


def main() -> int:
    ensure_library()
    c1, t1 = run(["python3", "-B", str(VALIDATE), "--library", "--report"])
    if c1 != 0:
        return fail(f"validate.py --library rc={c1} tail={t1[-1500:]}")
    vrep = json.loads(t1)
    if vrep.get("protocols") != 58 or vrep.get("presets") != 72:
        return fail(f"counts protocols={vrep.get('protocols')} presets={vrep.get('presets')}")
    if not vrep.get("ok") or not vrep.get("count_ok"):
        return fail(f"library not ok invalid={vrep.get('invalid')}")
    if not all(i.get("valid") for i in vrep.get("items") or []):
        return fail("validate.py item valid flags incomplete")

    c2, t2 = run(["python3", "-B", str(JSCLI), "--library", "--report"])
    if c2 != 0:
        return fail(f"jsonschema_cli --library rc={c2} tail={t2[-1500:]}")
    jrep = json.loads(t2)
    if jrep.get("protocols") != 58 or jrep.get("presets") != 72:
        return fail(f"jsonschema counts {jrep.get('protocols')} {jrep.get('presets')}")
    if not jrep.get("ok"):
        return fail(f"jsonschema_cli invalid={jrep.get('invalid')}")

    v_map = {i["id"]: bool(i["valid"]) for i in vrep["items"]}
    j_map = {i["id"]: bool(i["valid"]) for i in jrep["items"]}
    if set(v_map) != set(j_map):
        return fail(f"id-set mismatch v={len(v_map)} j={len(j_map)}")
    disagree = [i for i in sorted(v_map) if v_map[i] != j_map[i]]
    if disagree:
        return fail(f"item-for-item disagree {disagree[:8]}")
    if sum(1 for v in v_map.values() if v) != 130:
        return fail(f"valid count {sum(v_map.values())} != 130")

    lib = json.loads(LIBRARY.read_text(encoding="utf-8"))
    spec = lib["example_spec"]
    preset = lib["presets"][0]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        spec_path = tmp_path / "spec.json"
        preset_path = tmp_path / "preset.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        preset_path.write_text(json.dumps(preset), encoding="utf-8")
        # Independent jsonschema CLI from a non-repo cwd (stdlib platform).
        for inst in (spec_path, preset_path):
            rc, out = run(
                [
                    "python3",
                    "-m",
                    "jsonschema",
                    "-i",
                    str(inst),
                    str(SCHEMA),
                ],
                cwd=Path("/tmp"),
            )
            if rc != 0:
                return fail(f"python3 -m jsonschema {inst.name} rc={rc} {out[-800:]}")

    payload = {
        "pass": True,
        "probe": "probe1-library-and-jsonschema-agree",
        "unit_id": UNIT,
        "protocols": 58,
        "presets": 72,
        "items_valid": 130,
        "agreement": True,
        "disagreements": [],
        "python_m_jsonschema": True,
        "example_spec_valid": True,
        "engine": jrep.get("engine"),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "protocols=58 presets=72 items_valid=130 agreement=True "
        "python3_-m_jsonschema=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 72/72 presets and 58/58 protocols validate; jsonschema agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
