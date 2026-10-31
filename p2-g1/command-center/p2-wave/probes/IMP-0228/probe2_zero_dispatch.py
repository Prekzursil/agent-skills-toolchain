"""IMP-0228 probe 2: zero dispatch during replay - counted, not assumed.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0228/probe2_zero_dispatch.py
Both-states on the counter: the LIVE recording path dispatches (rail count > 0) while a
replay over a fresh counting rail stays at exactly 0. AST control: record_run calls the
rail; replay_run never references it. Import scan: the replay modules import none of the
wall-clock/entropy/socket modules.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))

from agentspec.replay_log import (  # noqa: E402
    CountingFakeRail,
    fixture_execute,
    record_run,
    replay_run,
)

BANNED_ROOTS = {"time", "random", "uuid", "socket", "datetime", "secrets", "platform"}


def ast_spawns(src: str) -> dict:
    tree = ast.parse(src)
    record_calls_spawn = False
    replay_refs_spawn = False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name in ("record_run", "replay_run")):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute) and sub.attr == "spawn":
                if node.name == "record_run":
                    record_calls_spawn = True
                elif node.name == "replay_run":
                    replay_refs_spawn = True
    return {"record_fn_calls_dispatch": record_calls_spawn,
            "replay_fn_calls_dispatch": replay_refs_spawn}


def import_scan() -> dict:
    report = {}
    for name in ("replay_log", "replay", "plan", "determinism"):
        p = W / "tools" / "agentspec" / "agentspec" / (name + ".py")
        if not p.is_file():
            report[name] = {"missing": True}
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    roots.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    roots.add(node.module.split(".")[0])
        report[name] = {"imports": sorted(roots),
                        "banned": sorted(roots & BANNED_ROOTS)}
    return report


def main() -> int:
    live = record_run()  # LIVE path: dispatches through the counting rail
    live_dispatch = live.spawns

    replay_rail = CountingFakeRail(fixture_execute)
    result = replay_run(live.log_bytes, rail=replay_rail)
    replay_dispatch = replay_rail.spawns
    verdicts_roundtrip = result.verdicts_b == live.verdicts_b

    src = (W / "tools" / "agentspec" / "agentspec" / "replay_log.py").read_text(
        encoding="utf-8"
    )
    ast_report = ast_spawns(src)
    imports = import_scan()
    banned_hits = sorted(
        {b for v in imports.values() for b in (v.get("banned") or [])}
    )

    doc = {
        "unit_id": "IMP-0228",
        "probe": "probe2-zero-dispatch",
        "id": "zero-dispatch-both-states",
        "live_dispatch": live_dispatch,
        "replay_dispatch": replay_dispatch,
        "counter_both_states": live_dispatch > 0 and replay_dispatch == 0,
        "verdicts_roundtrip": verdicts_roundtrip,
        "ast": ast_report,
        "imports": {k: v.get("imports") for k, v in imports.items()},
        "banned_import_hits": banned_hits,
    }
    doc["pass"] = (
        doc["counter_both_states"]
        and verdicts_roundtrip
        and ast_report["record_fn_calls_dispatch"]
        and not ast_report["replay_fn_calls_dispatch"]
        and not banned_hits
    )
    out = Path(__file__).resolve().parent / "probe2-zero-dispatch.raw.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    if doc["pass"]:
        print("SUCCESS:IMP-0228-probe2 zero dispatch during replay, counted; live path"
              " still dispatches; modules clock-free")
        return 0
    print("FAILED:IMP-0228-probe2 dispatch counter or AST/import control failed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
