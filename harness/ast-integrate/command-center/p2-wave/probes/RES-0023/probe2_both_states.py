#!/usr/bin/env python3
"""Probe 2: both-states control on the same hooks file.

Clean file (no extra key) must load the SessionStart command hook.
The identical file plus top-level `$schema` must load zero hooks.
The research artifact must cite the upstream deny_unknown_fields line.
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
CLEAN = HERE / "fixtures" / "hooks.clean.json"
EXTRA = HERE / "fixtures" / "hooks.schema-extra.json"


def main() -> int:
    contract = H.load_contract()
    clean = H.load_hooks_file(CLEAN.read_text(encoding="utf-8"), contract)
    extra = H.load_hooks_file(EXTRA.read_text(encoding="utf-8"), contract)
    print(
        json.dumps(
            {
                "clean_ok": clean["ok"],
                "clean_handlers": clean["handlers"],
                "extra_ok": extra["ok"],
                "extra_handlers": extra["handlers"],
                "source_line": contract["source_line"],
                "struct_line": contract["struct_line"],
            },
            sort_keys=True,
        )
    )
    if not clean["ok"] or clean["handlers"] < 1:
        print("FAILED:RES-0023-probe2 clean file did not load hooks")
        return 1
    if extra["ok"] or extra["handlers"] != 0:
        print("FAILED:RES-0023-probe2 extra-key file still loaded hooks")
        return 1
    # Negative control: if the loader were silent in both states, both
    # handler counts would be equal. They must differ.
    if clean["handlers"] == extra["handlers"]:
        print("FAILED:RES-0023-probe2 silent in both states")
        return 1
    if not ART.is_file():
        print("FAILED:RES-0023-probe2 research artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if "#[serde(deny_unknown_fields)]" not in text:
        print("FAILED:RES-0023-probe2 artifact missing strictness attribute")
        return 1
    pair = doc.get("observed_loaded_unloaded_pair") or {}
    if pair.get("loaded_clean_handlers") != clean["handlers"]:
        print("FAILED:RES-0023-probe2 artifact clean handlers mismatch", pair)
        return 1
    if pair.get("unloaded_extra_key_handlers") != 0:
        print("FAILED:RES-0023-probe2 artifact extra handlers mismatch", pair)
        return 1
    src = doc.get("strictness_source_line") or {}
    if int(src.get("line") or 0) != int(contract["source_line"]):
        print("FAILED:RES-0023-probe2 source line mismatch", src, contract["source_line"])
        return 1
    sentinel = (
        "SUCCESS:RES-0023 in the receipt AND the upstream source line for the "
        "strictness attribute plus an observed loaded/unloaded pair"
    )
    if sentinel not in text:
        print("FAILED:RES-0023-probe2 catalog sentinel absent")
        return 1
    print("SUCCESS:RES-0023-probe2 both-states loaded/unloaded pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
