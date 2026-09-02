#!/usr/bin/env python3
"""Probe 2: a disabled server spawns zero processes (process table).

Writes a disable at the inert scope (project) and shows the process table
still has the server — config intent is not evidence. Then writes the same
disable at the effective scope (user) and shows the process table count is
zero. Other enabled servers still spawn, so a dead enumerator cannot fake zero.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

SESSIONS = 2
TARGET = H.TARGET_SERVER


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0102-probe2 {msg}")
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tst0102-p2-"))
    base = H.new_config(H.SERVERS, enabled=True)
    (tmp / "phases").mkdir(parents=True, exist_ok=True)

    tokens = {
        "enabled": H.make_token("enabled"),
        "inert": H.make_token("inert"),
        "effective": H.make_token("effective"),
    }
    try:
        # Phase A: all enabled at user. Target must be live in the process table.
        H.write_config(tmp / "enabled", base)
        H.spawn_sessions(base, n_sessions=SESSIONS, mode="shared", token=tokens["enabled"])
        live_enabled = H.count_server(tokens["enabled"], TARGET)
        all_enabled = len(H.census(tokens["enabled"]))
        if live_enabled < 1:
            return _fail("baseline: enabled server not in process table")
        if all_enabled != len(H.SERVERS):
            return _fail(f"baseline shared count {all_enabled} != {len(H.SERVERS)}")
        H.kill_token(tokens["enabled"])

        # Phase B: disable at inert (project) scope. Config looks disabled; table still live.
        inert_cfg = H.set_enabled(base, "project", TARGET, False)
        project_says_disabled = (
            inert_cfg["scopes"]["project"]["servers"][TARGET]["enabled"] is False
        )
        still_effective = H.is_effectively_enabled(inert_cfg, TARGET)
        H.write_config(tmp / "inert-project-disable", inert_cfg)
        H.spawn_sessions(
            inert_cfg, n_sessions=SESSIONS, mode="shared", token=tokens["inert"]
        )
        live_inert = H.count_server(tokens["inert"], TARGET)
        if not project_says_disabled:
            return _fail("project disable did not land in config")
        if not still_effective:
            return _fail("project disable incorrectly affected effective scope")
        if live_inert < 1:
            return _fail(
                "inert-scope disable cleared the process table; "
                "cannot distinguish inert config from a real disable"
            )
        H.kill_token(tokens["inert"])

        # Phase C: disable at effective (user) scope. Process table must be zero for target.
        effective_cfg = H.set_enabled(inert_cfg, "user", TARGET, False)
        user_says_disabled = (
            effective_cfg["scopes"]["user"]["servers"][TARGET]["enabled"] is False
        )
        H.write_config(tmp / "effective-user-disable", effective_cfg)
        H.spawn_sessions(
            effective_cfg,
            n_sessions=SESSIONS,
            mode="shared",
            token=tokens["effective"],
        )
        live_effective = H.count_server(tokens["effective"], TARGET)
        others = {
            name: H.count_server(tokens["effective"], name)
            for name in H.SERVERS
            if name != TARGET
        }
        if not user_says_disabled:
            return _fail("user disable did not land in config")
        if H.is_effectively_enabled(effective_cfg, TARGET):
            return _fail("user disable did not become effective")
        if live_effective != 0:
            return _fail(
                f"effective disable still has {live_effective} {TARGET} processes"
            )
        if any(c != 1 for c in others.values()):
            return _fail(
                f"other servers missing after target disable: {others} "
                "(a dead enumerator would report zero for everyone)"
            )

        payload = {
            "probe": "probe2-disabled-server-zero",
            "unit_id": "TST-0102",
            "instrument": "os-process-table",
            "target_server": TARGET,
            "inert_scope": "project",
            "effective_scope": "user",
            "sessions": SESSIONS,
            "baseline_target_live": live_enabled,
            "inert_disable_config_says_disabled": project_says_disabled,
            "inert_disable_still_effective": still_effective,
            "inert_disable_process_table_count": live_inert,
            "inert_disable_process_table_still_live": live_inert >= 1,
            "effective_disable_config_says_disabled": user_says_disabled,
            "effective_disable_process_table_count": live_effective,
            "effective_disable_process_table_zero": live_effective == 0,
            "other_servers_after_effective_disable": others,
            "config_alone_is_not_evidence": project_says_disabled and live_inert >= 1,
            "pass": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            f"inert_live={live_inert} effective_zero={live_effective} "
            f"others={others} config_alone_not_evidence=True"
        )
        print("SUCCESS:TST-0102-probe2 disabled-server-spawns-zero")
        return 0
    finally:
        for tok in tokens.values():
            H.kill_token(tok)


if __name__ == "__main__":
    raise SystemExit(main())
