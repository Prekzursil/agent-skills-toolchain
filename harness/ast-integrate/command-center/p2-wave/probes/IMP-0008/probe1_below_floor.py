#!/usr/bin/env python3
"""Probe 1: synthetic below-floor client must be refused with the exact floor named.

Signal (1) of IMP-0008 evidence_requirement. Does not score live CLI parsing.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.client_negotiate import (  # noqa: E402
    load_manifest,
    negotiate,
    preflight_install,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe1-below-floor.raw.json"


def main() -> int:
    manifest = load_manifest()
    floor = manifest["min_client_version"]
    below = "0.0.1"
    n = negotiate(manifest, "claude-code", below)
    dest = Path(tempfile.mkdtemp(prefix="imp0008-p1-")) / "would-install"
    gate = preflight_install(dest, manifest, "claude-code", below, write=True)
    named = floor in n.message
    doc = {
        "probe": "probe1-below-floor",
        "unit_id": "IMP-0008",
        "floor": floor,
        "synthetic_version": below,
        "allowed": n.allowed,
        "reason": n.reason,
        "message": n.message,
        "required_version": n.required_version,
        "message_names_required_version": named,
        "dest_exists_after_refuse": dest.exists(),
        "dest_has_payload": gate["dest_has_payload"],
        "installed": gate["installed"],
        "pass": False,
    }
    ok = (
        n.allowed is False
        and n.reason == "below-floor"
        and named
        and n.required_version == floor
        and dest.exists() is False
        and gate["installed"] is False
        and gate["dest_has_payload"] is False
    )
    doc["pass"] = ok
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0008-probe1 below-floor did not refuse with named required version")
        return 1
    print("SUCCESS:IMP-0008-probe1 below-floor refused; message names required version")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
