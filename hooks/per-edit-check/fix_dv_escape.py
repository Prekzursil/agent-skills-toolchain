"""Fix the over-escaped backslash replace in _check_destructive_verdict.

The raw-string patch emitted fp.replace("\\\\", "/") (four backslashes in source
= two at runtime) which never matches single-backslash Windows paths, so the
/knowledge/ path gate never fired. Correct source: fp.replace("\\", "/").
Applies to BOTH the repo and live copies; refuses if the needle is absent.
"""
import py_compile
import sys

NEEDLE = 'fp.replace("\\\\\\\\", "/")'
REPL = 'fp.replace("\\\\", "/")'

TARGETS = [
    r"C:\Users\Prekzursil\source\agent-skills-toolchain\hooks\per-edit-check\check.py",
    r"C:\Users\Prekzursil\.claude\hooks\per-edit-check\check.py",
]

for p in TARGETS:
    s = open(p, encoding="utf-8").read()
    if NEEDLE in s:
        s = s.replace(NEEDLE, REPL, 1)
        open(p, "w", encoding="utf-8", newline="").write(s)
        py_compile.compile(p, doraise=True)
        print("fixed:", p)
    elif REPL in s:
        print("already fixed:", p)
    else:
        print("NEEDLE NOT FOUND (unexpected):", p)
        sys.exit(1)
