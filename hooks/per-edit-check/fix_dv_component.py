"""Fix v2: the component regex \\b(hub)\\b never matches CamelCase (McpHub) —
word chars on both sides defeat the boundary. Switch to substring alternation.

Applies to repo + live copies; idempotent; refuses if neither form is found.
"""
import py_compile
import sys

OLD = 'r"\\b(mcp|hub|server|daemon|hook|skill|task|distro|fleet|service|agent|bridge"\n    r"|entry|rule|plugin|watchdog|registry)\\b|`[^`]+`",'
NEW = 'r"(mcp|hub|server|daemon|hook|skill|task|distro|fleet|service|agent|bridge"\n    r"|entry|rule|plugin|watchdog|registry)|`[^`]+`",'

TARGETS = [
    r"C:\Users\Prekzursil\source\agent-skills-toolchain\hooks\per-edit-check\check.py",
    r"C:\Users\Prekzursil\.claude\hooks\per-edit-check\check.py",
]

for p in TARGETS:
    s = open(p, encoding="utf-8").read()
    if NEW in s:
        print("already fixed:", p)
        continue
    if OLD in s:
        s = s.replace(OLD, NEW, 1)
        open(p, "w", encoding="utf-8", newline="").write(s)
        py_compile.compile(p, doraise=True)
        print("fixed:", p)
    else:
        print("NEEDLE NOT FOUND:", p)
        sys.exit(1)
