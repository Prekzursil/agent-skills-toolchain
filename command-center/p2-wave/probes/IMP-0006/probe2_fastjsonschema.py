#!/usr/bin/env python3
"""IMP-0006 probe2: second library (fastjsonschema) same verdict on same file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import manifest_schema as M  # noqa: E402

PROBE = Path(__file__).resolve().parent
EVIDENCE = (
    "TWO independent signals: (1) the live .claude-plugin/plugin.json validates "
    "green under the new schema; (2) a second validator implementation (a different "
    "JSON-Schema library) reaches the same verdict on the same file, guarding "
    "against a library-specific dialect quirk."
)


def main() -> int:
    schema = M.load_schema(REPO)
    path = REPO / M.MANIFEST_RELPATH
    instance = M.load_manifest(path)
    v1 = M.validate_with_jsonschema(instance, schema)
    v2 = M.validate_with_fastjsonschema(instance, schema)
    agree = v1.ok == v2.ok
    ok = bool(v1.ok and v2.ok and agree)
    meas = {
        "ok": ok,
        "jsonschema_ok": v1.ok,
        "fastjsonschema_ok": v2.ok,
        "agree": agree,
        "libraries": [v1.library, v2.library],
        "manifest": M.MANIFEST_RELPATH,
        "schema": M.SCHEMA_RELPATH,
        "probe_2_confirmed": ok,
        "same_file": True,
        "second_library": "fastjsonschema",
    }
    (PROBE / "probe2-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NAMED PROBE 2: SECOND LIBRARY SAME VERDICT (fastjsonschema)",
        "PROBE-2-BEGIN:IMP-0006",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"repo={REPO}",
        f"manifest={M.MANIFEST_RELPATH}",
        f"schema={M.SCHEMA_RELPATH}",
        f"jsonschema_ok={v1.ok}",
        f"fastjsonschema_ok={v2.ok}",
        f"agree={agree}",
        "second_library=fastjsonschema",
        f"probe_2_confirmed={ok}",
        "PROBE-2-COMPLETE:IMP-0006",
        "SUCCESS:IMP-0006-probe2" if ok else "FAILED:IMP-0006-probe2",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe2-fastjsonschema.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
