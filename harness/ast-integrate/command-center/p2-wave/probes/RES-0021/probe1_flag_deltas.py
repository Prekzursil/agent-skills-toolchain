#!/usr/bin/env python3
"""Probe 1: re-run with/without for each candidate; honoured rows must still delta."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from client import describe_client  # noqa: E402
from inventory import (  # noqa: E402
    INVENTED_CLI,
    INVENTED_CMD,
    INVENTED_ENV,
    _cache_dir_delta,
    _cmd_delta,
    _config_dir_delta,
    _credential_store_delta,
    _flag_delta,
    _invoked_as_delta,
    _plain_env_delta,
    _xdg_cache_delta,
    classify,
)
from extract import load_published  # noqa: E402

ART = REPO / "command-center/research/RES-0021.json"
SENTINEL = "SUCCESS:RES-0021"


def rerun(launcher: Path, name: str, kind: str) -> dict:
    if name == "AGENT_CLI_CREDENTIAL_STORE":
        return _credential_store_delta(launcher)
    if name == "NODE_COMPILE_CACHE":
        return _cache_dir_delta(launcher)
    if name == "XDG_CACHE_HOME":
        return _xdg_cache_delta(launcher)
    if name == "CURSOR_INVOKED_AS":
        return _invoked_as_delta(launcher)
    if name == "CURSOR_CONFIG_DIR":
        return _config_dir_delta(launcher)
    if kind == "flag":
        return _flag_delta(launcher, name)
    if kind == "subcommand":
        return _cmd_delta(launcher, name)
    return _plain_env_delta(launcher, name, "1")


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:RES-0021-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if SENTINEL not in text:
        print("FAILED:RES-0021-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "RES-0021":
        print("FAILED:RES-0021-probe1 unit_id", doc.get("unit_id"))
        return 1
    info = describe_client()
    if not info.get("present"):
        print("FAILED:RES-0021-probe1 no client")
        return 1
    launcher = Path(info["launcher"])
    pub = load_published()
    pub_env, pub_flags, pub_cmds = set(pub["env"]), set(pub["flags"]), set(pub["commands"])
    honoured = 0
    string_only = 0
    for row in doc.get("candidates") or []:
        name = row.get("name")
        kind = row.get("kind") or "env"
        status = row.get("status")
        if status == "honoured":
            honoured += 1
            bd = row.get("behaviour_delta") or {}
            if not bd.get("observed") or not (bd.get("reasons") or []):
                print(f"FAILED:RES-0021-probe1 honoured {name} lacks cited delta")
                return 1
            live_raw = rerun(launcher, name, kind)
            live = classify(live_raw, pub_env, pub_flags, pub_cmds, "")
            if not live["behaviour_delta"]["observed"] or live["status"] != "honoured":
                print(f"FAILED:RES-0021-probe1 live honour lost for {name} status={live['status']}")
                print(json.dumps(live_raw, default=str)[:1500])
                return 1
        elif status == "string-only":
            string_only += 1
            if row.get("marked") != "string-only":
                print(f"FAILED:RES-0021-probe1 {name} not marked string-only")
                return 1
            if name in {INVENTED_ENV, INVENTED_CLI, INVENTED_CMD, "CURSOR_INVOKED_AS"}:
                live_raw = rerun(launcher, name, kind)
                live = classify(live_raw, pub_env, pub_flags, pub_cmds, "")
                if live["status"] == "honoured":
                    print(f"FAILED:RES-0021-probe1 {name} was string-only now honoured")
                    return 1
    if honoured < 1:
        print("FAILED:RES-0021-probe1 expected at least one honoured undocumented surface")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-flag-deltas",
                "unit_id": "RES-0021",
                "honoured": honoured,
                "string_only": string_only,
                "pass": True,
            }
        )
    )
    print("SUCCESS:RES-0021-probe1 with/without deltas re-ran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
