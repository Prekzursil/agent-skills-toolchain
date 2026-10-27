from pathlib import Path
import py_compile, sys

REPO = Path('/home/prekzursil/p2-g1')
EDITS = [
    ("tools/editor/ralph-orchestrator/vendor/tools/e2e/tui_visual_regression.py",
     [('print(f"  ❌ Invalid JSONL: {e}")', 'print(f"  [X] Invalid JSONL: {e}")')]),
    ("tools/monitorcore/monitorcore/agent_tail.py",
     [('print(f"{BOLD}{MAG}║ {name}{R}  {DIM}({m.get(\'agentType\', \'agent\')}){R}")',
       'print(f"{BOLD}{MAG}| {name}{R}  {DIM}({m.get(\'agentType\', \'agent\')}){R}")'),
      ('print(f"{MAG}║{R} {m[\'description\']}")', 'print(f"{MAG}|{R} {m[\'description\']}")'),
      ('print(f"{DIM}║ {os.path.basename(jsonl_path)}{R}")', 'print(f"{DIM}| {os.path.basename(jsonl_path)}{R}")'),
      ('print(f"{DIM}── last {a.backfill} events ──{R}")', 'print(f"{DIM}-- last {a.backfill} events --{R}")'),
      ('print(f"{DIM}── live ──{R}")', 'print(f"{DIM}-- live --{R}")')]),
    ("tools/taskwatch_monitor/cli/app.py",
     [(') → {path}")', ') -> {path}")')]),
    ("tools/triage-router/test_triage_router.py",
     [('(expected fail-safe→opus, got=', '(expected fail-safe->opus, got=')]),
    ("tools/workspace-hooks/anti-degen/test_fingerprint.py",
     [('print("== Test 2: same args, different output each time → NO warning ==")',
       'print("== Test 2: same args, different output each time -> NO warning ==")')]),
    ("tools/workspace-hooks/goal-reinject/test_reinject.py",
     [('print("== no goal → no injection (even on interval boundary) ==")',
       'print("== no goal -> no injection (even on interval boundary) ==")'),
      ('print("== non-write tool → no injection, counter not advanced ==")',
       'print("== non-write tool -> no injection, counter not advanced ==")'),
      ('print("== fail-open: bad stdin → exit 0, no crash ==")',
       'print("== fail-open: bad stdin -> exit 0, no crash ==")')]),
]

for rel, subs in EDITS:
    p = REPO / rel
    raw = p.read_bytes()
    t = raw.decode('utf-8')
    for old, new in subs:
        n = t.count(old)
        if n != 1:
            print('SKIP-MATCH %s count=%d for %r' % (rel, n, old[:60]))
            continue
        t = t.replace(old, new)
    p.write_bytes(t.encode('utf-8'))
    try:
        py_compile.compile(str(p), doraise=True, cfile='/tmp/pyc_scratch.pyc')
        print('OK %s' % rel)
    except Exception as e:
        print('COMPILE-FAIL %s %r' % (rel, e))
print('done')
