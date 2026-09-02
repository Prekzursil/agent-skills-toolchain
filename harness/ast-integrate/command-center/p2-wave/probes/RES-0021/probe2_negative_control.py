#!/usr/bin/env python3
"""Probe 2: invented flag produces no honouring delta; artifact honesty."""
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
    INVENTED_ENV,
    _cache_dir_delta,
    _flag_delta,
    _plain_env_delta,
    classify,
)
from extract import load_published  # noqa: E402

ART = REPO / "command-center/research/RES-0021.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0021-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    sentinel = (
        "SUCCESS:RES-0021 in the receipt AND a candidate list where every "
        "'honoured' entry cites an observed behaviour delta and every "
        "unconfirmed entry is explicitly marked string-only"
    )
    if sentinel not in text:
        print("FAILED:RES-0021-probe2 catalog sentinel absent")
        return 1

    honoured_n = 0
    for row in doc.get("candidates") or []:
        if row.get("status") == "honoured":
            honoured_n += 1
            bd = row.get("behaviour_delta") or {}
            if not bd.get("observed"):
                print(f"FAILED:RES-0021-probe2 honoured {row.get('name')} has no observed delta")
                return 1
        if row.get("unconfirmed") and row.get("status") != "string-only":
            print(f"FAILED:RES-0021-probe2 unconfirmed {row.get('name')} not string-only")
            return 1
        if row.get("status") == "string-only" and row.get("marked") != "string-only":
            print(f"FAILED:RES-0021-probe2 {row.get('name')} not marked string-only")
            return 1
    if honoured_n < 1:
        print("FAILED:RES-0021-probe2 discriminator dead: no honoured row")
        return 1

    info = describe_client()
    if not info.get("present"):
        print("FAILED:RES-0021-probe2 no client")
        return 1
    launcher = Path(info["launcher"])
    pub = load_published()
    pub_env, pub_flags, pub_cmds = set(pub["env"]), set(pub["flags"]), set(pub["commands"])

    env_raw = _plain_env_delta(launcher, INVENTED_ENV, "1")
    env_live = classify(env_raw, pub_env, pub_flags, pub_cmds, "")
    if env_live["behaviour_delta"]["observed"] or env_live["status"] == "honoured":
        print("FAILED:RES-0021-probe2 invented env produced honouring delta")
        print(json.dumps(env_raw, default=str)[:1500])
        return 1

    cli_raw = _flag_delta(launcher, INVENTED_CLI)
    cli_live = classify(cli_raw, pub_env, pub_flags, pub_cmds, "")
    if cli_live["status"] == "honoured":
        print("FAILED:RES-0021-probe2 invented CLI flag classified honoured")
        return 1

    # Both-states: a known-honoured control must still fire so the invented
    # miss is not a dead detector.
    ncc = classify(_cache_dir_delta(launcher), pub_env, pub_flags, pub_cmds, "")
    if ncc["status"] != "honoured":
        print("FAILED:RES-0021-probe2 known-honoured control silent", ncc["status"])
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-negative-control",
                "unit_id": "RES-0021",
                "invented_env": INVENTED_ENV,
                "invented_env_honour": False,
                "invented_cli": INVENTED_CLI,
                "invented_cli_status": cli_live["status"],
                "known_honoured_control": ncc["name"],
                "pass": True,
            }
        )
    )
    print("SUCCESS:RES-0021-probe2 invented flag negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
