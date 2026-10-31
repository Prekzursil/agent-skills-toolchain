#!/usr/bin/env python3
"""IMP-0057 command surface: local-only privacy/telemetry verbs.

These commands are the surface this unit owns. They must complete with
OS-level egress blocked. They never call a transport.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

from privacy import (  # noqa: E402
    default_posture,
    load_consent,
    posture_for,
    try_egress,
)
from telemetry import LocalSink  # noqa: E402

UNIT = "IMP-0057"
VERSION = "0.0.0-imp0057-local"


def cmd_help(_args: list[str]) -> int:
    names = " ".join(sorted(COMMANDS))
    print(f"{UNIT} privacy CLI (local-only default)")
    print(f"commands: {names}")
    return 0


def cmd_version(_args: list[str]) -> int:
    print(json.dumps({"unit": UNIT, "version": VERSION, "posture": default_posture()}))
    return 0


def cmd_telemetry_status(_args: list[str]) -> int:
    consent = load_consent(_consent_path(_args))
    doc = {
        "posture": posture_for(consent),
        "default_posture": default_posture(),
        "egress_enabled": False,
        "consent_present": consent is not None,
        "transport_wired": False,
    }
    print(json.dumps(doc, sort_keys=True))
    return 0


def cmd_consent_show(_args: list[str]) -> int:
    path = _consent_path(_args)
    consent = load_consent(path)
    if consent is None:
        print(json.dumps({"consent": None, "path": str(path) if path else None}))
        return 0
    print(json.dumps({"consent": consent.as_dict()}, sort_keys=True))
    return 0


def cmd_doctor(_args: list[str]) -> int:
    from static_audit import audit_tree

    findings = audit_tree()
    consent = load_consent(_consent_path(_args))
    ok = default_posture() == "LOCAL_ONLY" and not findings and consent is None
    doc = {
        "ok": ok,
        "posture": default_posture(),
        "static_findings": len(findings),
        "consent_present": consent is not None,
        "egress": "denied-default",
    }
    print(json.dumps(doc, sort_keys=True))
    return 0 if ok else 1


def cmd_inventory(_args: list[str]) -> int:
    files = sorted(p.name for p in PLUGIN.iterdir() if p.is_file())
    print(json.dumps({"root": "tools/plugin", "files": files}))
    return 0


def cmd_local_event(_args: list[str]) -> int:
    """Write a sanitized local event. Forbidden fields are dropped, not sent."""
    sink_path = Path(_args[0]) if _args else Path("tools/plugin/.telemetry.jsonl")
    sink = LocalSink(sink_path)
    record = sink.emit(
        {
            "event": "cli.local_event",
            "unit_id": UNIT,
            "ok": True,
            "prompt": "SHOULD-BE-STRIPPED",
            "path": "/home/owner/secret.py",
            "file_contents": "SHOULD-BE-STRIPPED",
        }
    )
    if "prompt" in record or "path" in record or "file_contents" in record:
        print("FAILED:local sink retained a forbidden field", file=sys.stderr)
        return 1
    print(json.dumps({"written": True, "record": record}, sort_keys=True))
    return 0


def cmd_try_egress(_args: list[str]) -> int:
    """Explicit opt-in attempt. Must fail closed without consent."""
    url = _args[0] if _args else "https://example.invalid/telemetry"
    consent = load_consent(_consent_path(_args[1:]))
    try:
        try_egress(url, {"event": "probe", "prompt": "nope"}, consent)
    except Exception as exc:
        print(json.dumps({"denied": True, "error": str(exc)}))
        return 0
    print("FAILED:try-egress did not deny", file=sys.stderr)
    return 1


def _consent_path(args: list[str]) -> Path | None:
    if "--consent" in args:
        i = args.index("--consent")
        if i + 1 < len(args):
            return Path(args[i + 1])
    return None


COMMANDS = {
    "help": cmd_help,
    "version": cmd_version,
    "telemetry-status": cmd_telemetry_status,
    "consent-show": cmd_consent_show,
    "doctor": cmd_doctor,
    "inventory": cmd_inventory,
    "local-event": cmd_local_event,
    "try-egress": cmd_try_egress,
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return cmd_help([])
    name, rest = argv[0], argv[1:]
    if name in {"-h", "--help"}:
        name = "help"
    fn = COMMANDS.get(name)
    if fn is None:
        print(f"unknown command: {name}", file=sys.stderr)
        return 2
    return int(fn(rest))


if __name__ == "__main__":
    raise SystemExit(main())
