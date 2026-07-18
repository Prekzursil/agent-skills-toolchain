#!/usr/bin/env python
"""Self-contained tests for the event-ledger keystone. Run: python test_ledger.py
Uses a temp EVENT_LEDGER_ROOT so it never touches real ledgers."""
from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
fails = []


def check(name, cond):
    print(f"  {'OK ' if cond else 'BAD'}  {name}")
    if not cond:
        fails.append(name)


def main():
    tmp = tempfile.mkdtemp(prefix="ledger-test-")
    os.environ["EVENT_LEDGER_ROOT"] = tmp
    sys.path.insert(0, str(HERE))
    import ledger
    importlib.reload(ledger)
    proj = "C:/fake/projectA"

    print("== core append / seq / replay ==")
    e1 = ledger.append(proj, "goal", text="ship the ledger")
    e2 = ledger.append(proj, "turn", head="aaa111", branch="main", dirty_files=2)
    e3 = ledger.append(proj, "failure", text="1mcp eager-spawns", preconditions="1mcp<=0.32.2")
    check("seq is monotonic 1,2,3", [e1["seq"], e2["seq"], e3["seq"]] == [1, 2, 3])
    rep = ledger.replay(proj, 10)
    check("replay returns 3 events oldest->newest", [r["seq"] for r in rep] == [1, 2, 3])
    st = ledger.state(proj)
    check("state.goal projected", st["goal"] == "ship the ledger")
    check("state.head projected from turn", st["head"] == "aaa111")
    check("open_failures recorded with preconditions",
          len(st["open_failures"]) == 1 and st["open_failures"][0]["preconditions"] == "1mcp<=0.32.2")
    check("aliases records the cwd that mapped into this shard", proj in (st.get("aliases") or []))

    print("== milestone tombstones a failure (supersedes) ==")
    fseq = st["open_failures"][0]["seq"]
    ledger.append(proj, "milestone", text="upgraded 1mcp", supersedes_failures=[fseq])
    st2 = ledger.state(proj)
    check("failure auto-tombstoned", len(st2["open_failures"]) == 0)

    print("== per-project isolation (slug) ==")
    ledger.append("C:/fake/projectB", "goal", text="other")
    check("projectA seq unaffected by projectB", ledger.state(proj)["seq"] == 4)
    check("projectB independent seq", ledger.state("C:/fake/projectB")["seq"] == 1)

    print("== bad field never raises ==")
    try:
        ledger.append(proj, "note", weird=object())
        check("non-serializable field tolerated", True)
    except Exception as ex:
        check(f"non-serializable field tolerated (raised {ex})", False)

    print("== stop-hook honors stop_hook_active (no write) ==")
    def run_hook(modfile, stdin_obj):
        spec = importlib.util.spec_from_file_location(modfile.stem, modfile)
        mod = importlib.util.module_from_spec(spec)
        old_stdin, old_stdout = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(json.dumps(stdin_obj))
        cap = io.StringIO()
        sys.stdout = cap
        try:
            spec.loader.exec_module(mod)
            rc = mod.main()
        finally:
            sys.stdin, sys.stdout = old_stdin, old_stdout
        return rc, cap.getvalue()
    before = ledger.state(proj)["seq"]
    rc, _ = run_hook(HERE / "stop-hook.py", {"cwd": proj, "stop_hook_active": True})
    check("stop-hook exit 0 when active", rc == 0)
    check("stop-hook wrote nothing when active", ledger.state(proj)["seq"] == before)

    print("== sessionstart-replay emits additionalContext ==")
    rc, out = run_hook(HERE / "sessionstart-replay.py", {"cwd": proj, "source": "resume"})
    ok_json = False
    try:
        payload = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
        ctx = payload.get("hookSpecificOutput", {}).get("additionalContext", "")
        ok_json = "Event ledger" in ctx and "ship the ledger" in ctx
    except Exception:
        ok_json = False
    check("replay injects ground-truth context", ok_json)

    print(f"\nRESULT: {'PASS' if not fails else 'FAIL: ' + ', '.join(fails)}  "
          f"({len(fails)} failures)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
