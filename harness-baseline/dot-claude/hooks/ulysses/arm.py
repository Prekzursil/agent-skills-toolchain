#!/usr/bin/env python3
r"""ulysses/arm.py — author Ulysses tripwires at TASK-START (while cold/clear-headed).

The /start-task convention: when you scope a new task, BEFORE diving in, arm the abort
criteria your later (rationalizing) self should be held to. The harness then enforces
them via ulysses/enforce.py (PreToolUse).

SHORTHANDS (the common four):
  python arm.py --task "BC live-mod" --guard-live-game            # HALT on live mem write
  python arm.py --max-edits 4                                     # ASK on 4th edit of a file
  python arm.py --max-calls-since-test 25                         # ASK after 25 untested calls
  python arm.py --guard-path "coverage-thresholds\.json" --guard-action ASK   # coverage gate

GENERIC / freeform:
  python arm.py --add "tool_match:HALT:pattern=mcp__cheatengine__write_.*:desc=live write"
  python arm.py --add "calls_since_test:ASK:threshold=15"

MANAGE:
  python arm.py --show                 # print active tripwires
  python arm.py --override "<reason>"  # log a time-boxed override (lets you disarm/down-edit)
  python arm.py --clear                # remove all tripwires (auto-logs an override)
  python arm.py --replace ...          # start a fresh set instead of appending
  python arm.py --ttl-hours 24         # auto-expire the set after N hours (default 0 = never)
  python arm.py --list-types           # predicate-type help

By default new predicates APPEND to the current task's set (incremental arming). Pure
stdlib; writes ~/.claude/ulysses/tripwires.json . The store is overwritten only via this
CLI or a logged override (see enforce.py disarm guard).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402


def _pid() -> str:
    return uuid.uuid4().hex[:6]


def _parse_add(spec: str) -> dict | None:
    """'TYPE:ACTION[:k=v,k=v]' -> predicate dict."""
    parts = spec.split(":", 2)
    if len(parts) < 2:
        return None
    typ, action = parts[0].strip(), parts[1].strip().upper()
    if typ not in C.PRED_TYPES or action not in C.ACTIONS:
        return None
    pred = {"id": _pid(), "type": typ, "action": action, "desc": typ}
    if len(parts) == 3:
        for kv in parts[2].split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                k, v = k.strip(), v.strip()
                pred[k] = int(v) if (k == "threshold" and v.isdigit()) else v
    return pred


def _shorthand_preds(a) -> list[dict]:
    preds: list[dict] = []
    if a.guard_live_game:
        preds.append(
            {
                "id": _pid(),
                "type": "tool_match",
                "action": "HALT",
                "pattern": a.live_pattern or C.LIVE_WRITE_DEFAULT,
                "desc": "force a write into LIVE game memory (irreversible)",
            }
        )
    if a.max_edits is not None:
        preds.append(
            {
                "id": _pid(),
                "type": "path_reedit",
                "action": "ASK",
                "threshold": int(a.max_edits),
                "desc": f"re-editing the same file >= {a.max_edits} times",
            }
        )
    if a.max_calls_since_test is not None:
        preds.append(
            {
                "id": _pid(),
                "type": "calls_since_test",
                "action": "ASK",
                "threshold": int(a.max_calls_since_test),
                "desc": f"> {a.max_calls_since_test} tool-calls without a passing test",
            }
        )
    if a.guard_path:
        for pat in a.guard_path:
            preds.append(
                {
                    "id": _pid(),
                    "type": "path_match",
                    "action": (a.guard_action or "ASK").upper(),
                    "pattern": pat,
                    "desc": f"touching {pat}",
                }
            )
    if a.guard_tool:
        for pat in a.guard_tool:
            preds.append(
                {
                    "id": _pid(),
                    "type": "tool_match",
                    "action": (a.guard_action or "HALT").upper(),
                    "pattern": pat,
                    "desc": f"using tool ~ {pat}",
                }
            )
    for spec in a.add or []:
        p = _parse_add(spec)
        if p:
            preds.append(p)
    return preds


def cmd_show(as_json: bool) -> int:
    store = C.load_tripwires()
    if as_json:
        print(json.dumps(store or {}, indent=2, ensure_ascii=False))
        return 0
    if not store:
        print("ulysses: no active tripwires")
        return 0
    print(
        f"ulysses task: {store.get('task', '(unnamed)')}  ttl_hours={store.get('ttl_hours', 0)}  "
        f"armed_ts={int(store.get('armed_ts', 0))}"
    )
    for p in store.get("predicates") or []:
        extra = {
            k: v for k, v in p.items() if k not in ("id", "type", "action", "desc")
        }
        print(
            f"  [{p.get('action')}] {p.get('id')} {p.get('type')} {extra}  # {p.get('desc', '')}"
        )
    return 0


def cmd_override(reason: str, as_json: bool) -> int:
    ok = C.log_override(reason)
    win = int(C.OVERRIDE_WINDOW_SEC // 60)
    print(
        json.dumps({"override_logged": ok, "window_min": win})
        if as_json
        else f"ulysses: override logged ({'ok' if ok else 'FAILED'}); valid {win} min: {reason}"
    )
    return 0 if ok else 1


def cmd_clear(as_json: bool) -> int:
    C.log_override("clear via arm.py")  # auditable
    store = {"task": None, "armed_ts": C.now(), "ttl_hours": 0, "predicates": []}
    ok = C.save_tripwires(store)
    print(
        json.dumps({"cleared": ok})
        if as_json
        else f"ulysses: tripwires cleared ({'ok' if ok else 'FAILED'})"
    )
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="author/manage Ulysses tripwires")
    ap.add_argument("--task", default=None)
    ap.add_argument("--ttl-hours", type=float, default=None, dest="ttl_hours")
    ap.add_argument(
        "--replace", action="store_true", help="replace the set instead of appending"
    )
    # shorthands
    ap.add_argument("--guard-live-game", action="store_true", dest="guard_live_game")
    ap.add_argument("--live-pattern", default=None, dest="live_pattern")
    ap.add_argument("--max-edits", type=int, default=None, dest="max_edits")
    ap.add_argument(
        "--max-calls-since-test", type=int, default=None, dest="max_calls_since_test"
    )
    ap.add_argument("--guard-path", action="append", dest="guard_path")
    ap.add_argument("--guard-tool", action="append", dest="guard_tool")
    ap.add_argument(
        "--guard-action",
        default=None,
        dest="guard_action",
        choices=["ASK", "HALT", "SNAPSHOT", "ask", "halt", "snapshot"],
    )
    ap.add_argument("--add", action="append", help="TYPE:ACTION[:k=v,...]")
    # manage
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--override", default=None)
    ap.add_argument("--clear", action="store_true")
    ap.add_argument("--list-types", action="store_true", dest="list_types")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        if a.list_types:
            print("predicate types:")
            print(
                "  tool_match        pattern=<regex>            block/ask on upcoming tool_name"
            )
            print(
                "  path_match        pattern=<regex>            on upcoming file_path / bash cmd"
            )
            print(
                "  path_reedit       threshold=<int>            Nth edit of a file this task"
            )
            print(
                "  calls_since_test  threshold=<int>            > N tool-calls since tests passed"
            )
            print(
                f"actions: {', '.join(C.ACTIONS)}   (HALT=exit-2 block; ASK/SNAPSHOT=inject)"
            )
            return 0
        if a.show:
            return cmd_show(a.json)
        if a.override is not None:
            return cmd_override(a.override, a.json)
        if a.clear:
            return cmd_clear(a.json)

        new_preds = _shorthand_preds(a)
        if not new_preds and a.task is None and a.ttl_hours is None:
            ap.error(
                "nothing to do — pass a shorthand (--guard-live-game/--max-edits/...), "
                "--add, --task, or a management flag (--show/--override/--clear)"
            )

        store = None if a.replace else C.load_tripwires()
        if not store:
            store = {
                "task": a.task,
                "armed_ts": C.now(),
                "ttl_hours": float(a.ttl_hours or 0),
                "predicates": [],
            }
        if a.task is not None:
            store["task"] = a.task
        if a.ttl_hours is not None:
            store["ttl_hours"] = float(a.ttl_hours)
        store["predicates"] = (store.get("predicates") or []) + new_preds
        C.save_tripwires(store)

        if a.json:
            print(json.dumps(store, ensure_ascii=False))
        else:
            print(
                f"ulysses armed: task={store.get('task')!r}  "
                f"{len(store['predicates'])} tripwire(s), +{len(new_preds)} new  "
                f"ttl_hours={store.get('ttl_hours')}"
            )
            for p in new_preds:
                print(f"  + [{p['action']}] {p['type']}  # {p.get('desc', '')}")
        return 0
    except SystemExit:
        raise
    except Exception as e:
        print(f"ulysses: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
