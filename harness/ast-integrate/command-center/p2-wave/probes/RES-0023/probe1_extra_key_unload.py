#!/usr/bin/env python3
"""Probe 1: a hooks file with one extra top-level key must not load.

The extra key is `$schema`. The loader is the captured HooksFile contract
(deny_unknown_fields + fields description/hooks). Codex CLI is not installed
on this box; this is a live load of the declared serde contract, not a
re-implemented guess of the keys.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import hooks_loader as H  # noqa: E402

ART = REPO / "command-center/research/RES-0023.json"
FIXTURE = HERE / "fixtures" / "hooks.schema-extra.json"


def main() -> int:
    contract = H.load_contract()
    if not contract["deny_unknown_fields"]:
        print("FAILED:RES-0023-probe1 captured HooksFile is not deny_unknown_fields")
        return 1
    if "hooks" not in contract["fields"] or "description" not in contract["fields"]:
        print("FAILED:RES-0023-probe1 unexpected HooksFile fields", contract["fields"])
        return 1
    raw = FIXTURE.read_text(encoding="utf-8")
    result = H.load_hooks_file(raw, contract)
    print(
        json.dumps(
            {
                "deny_unknown_fields": contract["deny_unknown_fields"],
                "fields": contract["fields"],
                "source_line": contract["source_line"],
                "extra_keys": result["extra_keys"],
                "ok": result["ok"],
                "handlers": result["handlers"],
                "error": result["error"],
            },
            sort_keys=True,
        )
    )
    if result["ok"] or result["handlers"] != 0:
        print("FAILED:RES-0023-probe1 extra-key file loaded; hooks were not unloaded")
        return 1
    if "$schema" not in result["extra_keys"]:
        print("FAILED:RES-0023-probe1 $schema not detected as extra key")
        return 1
    if not ART.is_file():
        print("FAILED:RES-0023-probe1 research artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    pair = doc.get("observed_loaded_unloaded_pair") or {}
    if pair.get("unloaded_extra_key_handlers") != 0:
        print("FAILED:RES-0023-probe1 artifact unloaded count mismatch", pair)
        return 1
    if "$schema" not in str(pair.get("extra_key") or ""):
        print("FAILED:RES-0023-probe1 artifact extra_key is not $schema")
        return 1
    print("SUCCESS:RES-0023-probe1 extra-key unload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
