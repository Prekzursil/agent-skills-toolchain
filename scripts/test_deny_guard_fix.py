"""Self-test for the separator-scoped deny-guard regexes (both-states proof).

False-positive state MUST stop matching; true-violation state MUST still match.
"""
import re
import importlib.util

spec = importlib.util.spec_from_file_location(
    "edg", r"C:\Users\Prekzursil\.agents\scripts\estate-deny-guard.py")
edg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edg)

CASES = [
    # (command, expect_no_verify, expect_force_push, label)
    ('git commit -F "C:/msg.txt" 2>&1 | tail -2; sed -n 5p x', False, False,
     "FALSE-POSITIVE FIXED: commit + later sed -n in same line"),
    ('git commit -m "msg" && rm tmp.txt', False, False, "plain commit"),
    ('git push origin main; tail -f log', False, False,
     "FALSE-POSITIVE FIXED: push + later tail -f in same line"),
    ('git commit --no-verify', True, False, "real --no-verify still blocked"),
    ('git commit -n', True, False, "real -n shorthand still blocked"),
    ('git merge --no-verify x', True, False, "merge --no-verify blocked"),
    ('git push --force origin main', False, True, "real force push blocked"),
    ('git push -f', False, True, "push -f blocked"),
    ('git push --force-with-lease origin x', False, True, "force-with-lease blocked"),
    ('echo start; git push --force origin main', False, True,
     "real violation after separator still caught"),
]

fails = 0
for cmd, exp_nv, exp_fp, label in CASES:
    nv = bool(edg.NO_VERIFY_RE.search(cmd))
    fp = bool(edg.FORCE_PUSH_RE.search(cmd))
    ok = nv == exp_nv and fp == exp_fp
    print(("PASS " if ok else "FAIL ") + label + f"  (nv={nv} fp={fp})")
    fails += 0 if ok else 1

print("SUCCESS all-cases-pass" if fails == 0 else f"FAILED {fails} cases")
raise SystemExit(0 if fails == 0 else 1)
