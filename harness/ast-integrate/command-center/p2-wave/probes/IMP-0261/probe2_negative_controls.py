#!/usr/bin/env python3
"""Probe 2: unknown section key FAIL; missing stopping rule FAIL.

Both-states: the live validator and the independent jsonschema CLI fire on
the planted-bad fixtures and stay silent on the known-good ones.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0261"
VALIDATE = REPO / "tools/council/validate.py"
JSCLI = REPO / "tools/council/schema/jsonschema_cli.py"
LIBRARY = REPO / "tools/council/schema/library.json"
FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def run(cmd: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def parse(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    return json.loads(text)


def write(name: str, doc: dict) -> Path:
    FIX.mkdir(parents=True, exist_ok=True)
    path = FIX / name
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def ids_of(report: dict) -> set[str]:
    return {v["id"] for v in report.get("violations") or []}


def main() -> int:
    if not LIBRARY.is_file():
        sys.path.insert(0, str(REPO / "tools"))
        from council.schema.library import write_library  # noqa: WPS433

        write_library(LIBRARY)
    lib = json.loads(LIBRARY.read_text(encoding="utf-8"))
    good_spec = copy.deepcopy(lib["example_spec"])
    bad_section = copy.deepcopy(good_spec)
    bad_section["unknown_section"] = {"planted": True}

    good_preset = copy.deepcopy(lib["presets"][0])
    bad_stop = copy.deepcopy(good_preset)
    del bad_stop["stopping"]

    p_good_spec = write("good-spec.json", good_spec)
    p_bad_section = write("unknown-section.json", bad_section)
    p_good_preset = write("good-preset.json", good_preset)
    p_bad_stop = write("missing-stopping.json", bad_stop)

    # --- unknown section key ---
    rc_g, t_g = run(["python3", "-B", str(VALIDATE), str(p_good_spec)])
    rc_b, t_b = run(["python3", "-B", str(VALIDATE), str(p_bad_section)])
    if rc_g != 0:
        return fail(f"good spec refused by validate.py rc={rc_g} {t_g[-800:]}")
    if rc_b == 0:
        return fail("unknown section key was accepted by validate.py")
    bad_rep = parse(t_b)
    good_rep = parse(t_g)
    if "CS-UNKNOWN-SECTION-KEY" not in ids_of(bad_rep):
        return fail(f"CS-UNKNOWN-SECTION-KEY absent {bad_rep}")
    if ids_of(good_rep):
        return fail(f"good spec not silent {good_rep}")

    jg, tg = run(["python3", "-B", str(JSCLI), str(p_good_spec)])
    jb, tb = run(["python3", "-B", str(JSCLI), str(p_bad_section)])
    if jg != 0:
        return fail(f"jsonschema good spec rc={jg} {tg[-800:]}")
    if jb == 0:
        return fail("jsonschema accepted unknown section key")
    jbad = parse(tb)
    extra_msgs = " ".join(e.get("message", "") for e in jbad.get("errors") or [])
    if "unknown_section" not in extra_msgs and "Additional properties" not in extra_msgs:
        return fail(f"jsonschema did not name extra property {jbad}")

    # --- missing stopping ---
    rc_pg, t_pg = run(["python3", "-B", str(VALIDATE), str(p_good_preset)])
    rc_ps, t_ps = run(["python3", "-B", str(VALIDATE), str(p_bad_stop)])
    if rc_pg != 0:
        return fail(f"good preset refused rc={rc_pg} {t_pg[-800:]}")
    if rc_ps == 0:
        return fail("missing stopping was accepted by validate.py")
    stop_rep = parse(t_ps)
    if "CS-STOPPING-MISSING" not in ids_of(stop_rep):
        return fail(f"CS-STOPPING-MISSING absent {stop_rep}")

    jpg, tjpg = run(["python3", "-B", str(JSCLI), str(p_good_preset)])
    jps, tjps = run(["python3", "-B", str(JSCLI), str(p_bad_stop)])
    if jpg != 0:
        return fail(f"jsonschema good preset rc={jpg} {tjpg[-800:]}")
    if jps == 0:
        return fail("jsonschema accepted preset missing stopping")

    payload = {
        "pass": True,
        "probe": "probe2-negative-controls",
        "unit_id": UNIT,
        "unknown_section_fired": True,
        "unknown_section_silent_on_good": True,
        "missing_stopping_fired": True,
        "missing_stopping_silent_on_good": True,
        "named_ids": sorted(ids_of(bad_rep) | ids_of(stop_rep)),
        "jsonschema_agrees": True,
        "bad_section_rc": rc_b,
        "bad_stopping_rc": rc_ps,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "unknown_section=FIRE missing_stopping=FIRE "
        "good_spec=SILENT good_preset=SILENT jsonschema_agrees=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 unknown section key and missing stopping fail closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
