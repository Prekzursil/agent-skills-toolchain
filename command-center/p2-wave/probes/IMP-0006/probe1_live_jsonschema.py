#!/usr/bin/env python3
"""IMP-0006 probe1: live `.claude-plugin/plugin.json` validates green (jsonschema)."""

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
    v = M.validate_with_jsonschema(instance, schema)
    meas = {
        "ok": v.ok,
        "library": v.library,
        "error_code": v.error_code,
        "message": v.message,
        "manifest": M.MANIFEST_RELPATH,
        "schema": M.SCHEMA_RELPATH,
        "probe_1_confirmed": bool(v.ok),
        "top_level_keys": sorted(instance.keys()),
        "required_in_schema": list(schema.get("required") or []),
    }
    (PROBE / "probe1-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NAMED PROBE 1: LIVE MANIFEST VALIDATES (jsonschema)",
        "PROBE-1-BEGIN:IMP-0006",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"repo={REPO}",
        f"manifest={M.MANIFEST_RELPATH}",
        f"schema={M.SCHEMA_RELPATH}",
        f"library={v.library}",
        f"ok={v.ok}",
        f"error_code={v.error_code}",
        f"top_level_keys={','.join(sorted(instance.keys()))}",
        f"probe_1_confirmed={v.ok}",
        "PROBE-1-COMPLETE:IMP-0006",
        "SUCCESS:IMP-0006-probe1" if v.ok else "FAILED:IMP-0006-probe1",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe1-live-jsonschema.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if v.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
