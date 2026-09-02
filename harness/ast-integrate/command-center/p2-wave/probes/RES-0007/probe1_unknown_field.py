#!/usr/bin/env python3
"""Probe 1: unknown top-level plugin.json key vs Codex HooksFile $schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from validator import (  # noqa: E402
    format_verbatim,
    validate_codex_hooksfile,
    validate_plugin_manifest,
)

FIX = HERE / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def main() -> int:
    control = validate_plugin_manifest(load("valid-minimal.json"))
    unknown = validate_plugin_manifest(load("unknown-top-level.json"))
    hooks_ok = validate_codex_hooksfile(load("codex-hooks-ok.json"))
    hooks_bad = validate_codex_hooksfile(load("codex-hooks-unknown.json"))

    unknown_verbatim = format_verbatim("UNKNOWN-FIELD-PLUGIN-JSON", unknown)
    hooks_verbatim = format_verbatim("UNKNOWN-FIELD-CODEX-HOOKSFILE", hooks_bad)

    checks = [
        ("control_valid", control["valid"] is True),
        ("control_no_unknown", control["unknown_top_level_keys_vs_schemastore_properties"] == []),
        ("unknown_still_schema_valid", unknown["valid"] is True),
        (
            "unknown_key_recorded",
            unknown["unknown_top_level_keys_vs_schemastore_properties"]
            == ["totally_unknown_top_level_field"],
        ),
        ("unknown_docs_mode_warning", unknown["docs_mode_verdict"] == "WARNING"),
        ("hooks_ok_valid", hooks_ok["valid"] is True and hooks_ok["deny_unknown_fields"] is True),
        ("hooks_schema_rejected", hooks_bad["valid"] is False),
        (
            "hooks_error_names_unknown_field",
            any("unknown field `$schema`" in e for e in hooks_bad["errors"]),
        ),
        ("asymmetry_holds", unknown["valid"] is True and hooks_bad["valid"] is False),
    ]
    failed = [name for name, ok in checks if not ok]
    payload = {
        "probe": "probe1_unknown_field",
        "unit_id": "RES-0007",
        "pass": not failed,
        "failed": failed,
        "control": control,
        "unknown_plugin_json": unknown,
        "codex_hooks_ok": hooks_ok,
        "codex_hooks_unknown": hooks_bad,
        "asymmetry": (
            "Claude plugin.json SchemaStore Draft-07 accepts an unknown "
            "top-level key (docs: warning, still loads). Codex HooksFile "
            "still has serde(deny_unknown_fields); a stray $schema is a "
            "hard error. The 05-ECO-plugin-specs asymmetry still holds "
            "on 2026-08-24 sources."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(unknown_verbatim)
    print(hooks_verbatim)
    if failed:
        print("FAILED:RES-0007-probe1 " + ",".join(failed))
        return 1
    print("SUCCESS:RES-0007-probe1 unknown-field warning (plugin.json) vs deny_unknown_fields (HooksFile)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
